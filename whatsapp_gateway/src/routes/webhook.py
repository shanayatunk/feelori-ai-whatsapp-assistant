# whatsapp_gateway/src/routes/webhook.py

import os
import json
import logging
import hmac
import hashlib
import time
import html
import uuid
import re
from contextlib import contextmanager
from typing import Optional, Tuple, Dict, Any

from flask import Blueprint, request, Response, jsonify, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from redis.exceptions import RedisError

from src.models import db
from src.models.conversation import Conversation, Message
from src.tasks import process_and_reply_task
from src.cache import redis_client

import bleach
import structlog

# Configure structured logging with correlation ID
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger(__name__).bind(
    service="whatsapp_gateway",
    version="1.0.0"
)

# Enhanced Input Validation and Sanitization
class InputValidator:
    PHONE_PATTERN = re.compile(r'^\+?[1-9]\d{8,14}$')
    MESSAGE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,255}$')
    MAX_MESSAGE_LENGTH = 4096
    
    @staticmethod
    def validate_phone_number(phone: str) -> str:
        """Validate and normalize phone number format."""
        if not phone:
            raise ValueError("Phone number is required")
        
        # Remove whitespace
        phone = phone.strip()
        
        if not InputValidator.PHONE_PATTERN.match(phone):
            raise ValueError("Invalid phone number format")
        
        return phone
    
    @staticmethod
    def validate_message_id(message_id: str) -> str:
        """Validate WhatsApp message ID format."""
        if not message_id:
            raise ValueError("Message ID is required")
        
        if not InputValidator.MESSAGE_ID_PATTERN.match(message_id):
            raise ValueError("Invalid message ID format")
        
        return message_id
    
    @staticmethod
    def sanitize_message_content(content: str) -> str:
        """Sanitize and validate message content."""
        if not content:
            raise ValueError("Message content is required")
        
        # Early rejection of extremely long content
        if len(content) > InputValidator.MAX_MESSAGE_LENGTH * 2:
            raise ValueError("Message content too long")
        
        # Remove HTML tags and dangerous content
        content = bleach.clean(content, tags=[], strip=True, strip_comments=True)
        content = html.escape(content)
        
        # Remove control characters except newlines, carriage returns, and tabs
        content = ''.join(
            char for char in content 
            if ord(char) >= 32 or char in '\n\r\t'
        )
        
        # Final length check
        content = content.strip()
        if not content:
            raise ValueError("Message content is empty after sanitization")
        
        if len(content) > InputValidator.MAX_MESSAGE_LENGTH:
            content = content[:InputValidator.MAX_MESSAGE_LENGTH]
        
        return content

# Webhook Blueprint
webhook_bp = Blueprint('webhook', __name__)

# Configuration
WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
WEBHOOK_TIMEOUT = int(os.getenv('WEBHOOK_TIMEOUT', '300'))  # 5 minutes default

# Environment-based rate limits
if os.getenv('FLASK_ENV') == 'production':
    DEFAULT_RATE_LIMITS = ["50 per minute", "500 per hour"]
else:
    DEFAULT_RATE_LIMITS = ["100 per minute", "1000 per hour"]

# Validation
if not WEBHOOK_SECRET:
    raise ValueError("WEBHOOK_SECRET must be configured for security")

if not WHATSAPP_VERIFY_TOKEN:
    raise ValueError("WHATSAPP_VERIFY_TOKEN must be configured")

# Enhanced rate limiting with fallback
def get_rate_limit_key() -> str:
    """Get rate limiting key with proper fallback."""
    correlation_id = getattr(g, 'correlation_id', 'unknown')
    
    try:
        data = request.get_json(silent=True)
        if not data:
            return f"ip:{get_remote_address()}:{correlation_id}"
        
        # Extract phone number safely
        phone = (data.get('entry', [{}])[0]
                    .get('changes', [{}])[0]
                    .get('value', {})
                    .get('messages', [{}])[0]
                    .get('from'))
        
        if phone:
            # Validate phone before using it for rate limiting
            try:
                validated_phone = InputValidator.validate_phone_number(phone)
                return f"phone:{validated_phone}:{correlation_id}"
            except ValueError:
                pass
                
    except (KeyError, IndexError, TypeError):
        pass
    
    # Fallback to IP-based limiting
    return f"ip:{get_remote_address()}:{correlation_id}"

# Initialize rate limiter
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=DEFAULT_RATE_LIMITS,
    storage_uri=os.getenv('REDIS_URL', 'redis://localhost:6379')
)
limiter.init_app(webhook_bp)

# Enhanced signature verification
def verify_webhook_signature(request_obj) -> bool:
    """Enhanced webhook signature verification with timestamp validation."""
    try:
        signature = request_obj.headers.get('X-Hub-Signature-256', '')
        timestamp = request_obj.headers.get('X-Hub-Timestamp')
        
        if not signature or not timestamp:
            logger.warning("Missing signature or timestamp headers")
            return False
        
        # Validate timestamp format and age
        try:
            timestamp_int = int(timestamp)
        except ValueError:
            logger.warning("Invalid timestamp format")
            return False
        
        current_time = int(time.time())
        if abs(current_time - timestamp_int) > WEBHOOK_TIMEOUT:
            logger.warning(
                "Webhook timestamp too old",
                timestamp_age=current_time - timestamp_int
            )
            return False
        
        # Get raw request body
        body = request_obj.get_data()
        
        # Create expected signature
        payload = f"{timestamp}.".encode() + body
        expected_signature = 'sha256=' + hmac.new(
            WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures securely
        is_valid = hmac.compare_digest(signature, expected_signature)
        
        if not is_valid:
            logger.warning("Webhook signature verification failed")
        
        return is_valid
        
    except Exception as e:
        logger.error("Error during signature verification", error=str(e))
        return False

# Improved duplicate detection with atomic operations
def is_duplicate_webhook(message_id: str, phone: str) -> bool:
    """Check for duplicate webhook with atomic Redis operation."""
    try:
        key = f"webhook_seen:{message_id}:{phone}"
        # Atomic set-if-not-exists with expiration
        result = redis_client.set(key, "1", nx=True, ex=300)  # 5 minutes
        return result is None  # None means key already existed
        
    except RedisError as e:
        logger.warning("Redis error during duplicate check", error=str(e))
        # Fail open - allow processing if Redis is unavailable
        return False

# Database transaction context manager
@contextmanager
def db_transaction():
    """Context manager for database transactions with proper cleanup."""
    try:
        yield db.session
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    finally:
        db.session.close()

# Webhook payload extraction and validation
def extract_message_data(payload: Dict[str, Any]) -> Tuple[str, str, str]:
    """Extract and validate message data from webhook payload."""
    try:
        # Navigate the payload structure safely
        entry = payload.get('entry', [])
        if not entry:
            raise ValueError("No entry in payload")
        
        changes = entry[0].get('changes', [])
        if not changes:
            raise ValueError("No changes in entry")
        
        value = changes[0].get('value', {})
        messages = value.get('messages', [])
        if not messages:
            raise ValueError("No messages in value")
        
        message = messages[0]
        
        # Validate message type
        if message.get('type') != 'text':
            raise ValueError("Non-text message type")
        
        # Extract required fields
        customer_phone = message.get('from')
        message_id = message.get('id')
        text_data = message.get('text', {})
        content = text_data.get('body', '')
        
        if not all([customer_phone, message_id, content]):
            raise ValueError("Missing required message fields")
        
        # Validate and sanitize
        customer_phone = InputValidator.validate_phone_number(customer_phone)
        message_id = InputValidator.validate_message_id(message_id)
        content = InputValidator.sanitize_message_content(content)
        
        return customer_phone, message_id, content
        
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"Invalid payload structure: {e}")

# Main webhook handler
@webhook_bp.before_request
def before_webhook_request():
    """Set up correlation ID for request tracking."""
    g.correlation_id = str(uuid.uuid4())
    g.start_time = time.time()
    
    # Bind correlation ID to logger
    structlog.contextvars.bind_contextvars(
        correlation_id=g.correlation_id,
        method=request.method,
        path=request.path
    )

@webhook_bp.after_request
def after_webhook_request(response):
    """Log request completion with metrics."""
    duration = time.time() - getattr(g, 'start_time', time.time())
    
    logger.info(
        "Request completed",
        status_code=response.status_code,
        duration_ms=round(duration * 1000, 2)
    )
    
    # Add correlation ID to response headers for tracing
    response.headers['X-Correlation-ID'] = getattr(g, 'correlation_id', 'unknown')
    return response

@webhook_bp.route('/webhook', methods=['GET', 'POST'])
@limiter.limit("200 per minute")
def handle_webhook():
    """
    Handle webhook verification (GET) and incoming messages (POST).
    """
    if request.method == 'GET':
        return handle_webhook_verification()
    else:
        return handle_incoming_message()

def handle_webhook_verification() -> Response:
    """Handle webhook verification challenge from Meta."""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode == 'subscribe' and token == WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return Response(challenge, status=200, mimetype='text/plain')
    else:
        logger.warning(
            "Webhook verification failed",
            mode=mode,
            token_match=token == WHATSAPP_VERIFY_TOKEN
        )
        return jsonify({'error': 'Forbidden', 'message': 'Invalid verification token'}), 403

def handle_incoming_message() -> Tuple[Response, int]:
    """Handle incoming WhatsApp message webhook."""
    # Verify webhook signature
    if not verify_webhook_signature(request):
        logger.warning("Webhook signature verification failed")
        return jsonify({'error': 'Unauthorized', 'message': 'Invalid signature'}), 401
    
    # Parse JSON payload
    try:
        payload = request.get_json()
        if not payload:
            raise ValueError("Empty or invalid JSON payload")
    except Exception as e:
        logger.warning("Invalid JSON payload", error=str(e))
        return jsonify({'error': 'Bad Request', 'message': 'Invalid JSON'}), 400
    
    logger.debug("Webhook payload received", payload_keys=list(payload.keys()))
    
    try:
        # Extract and validate message data
        customer_phone, message_id, content = extract_message_data(payload)
        
        logger.info(
            "Processing message",
            customer_phone=customer_phone,
            message_id=message_id,
            content_length=len(content)
        )
        
        # Check for duplicates
        if is_duplicate_webhook(message_id, customer_phone):
            logger.info("Duplicate webhook ignored", message_id=message_id)
            return jsonify({'status': 'OK', 'message': 'Duplicate ignored'}), 200
        
        # Process message in database transaction
        conversation_id = None
        try:
            with db_transaction():
                # Find or create conversation
                conversation = Conversation.query.filter_by(
                    customer_phone=customer_phone
                ).first()
                
                if not conversation:
                    logger.info("Creating new conversation", customer_phone=customer_phone)
                    conversation = Conversation(customer_phone=customer_phone)
                    db.session.add(conversation)
                    db.session.flush()  # Get ID without committing
                
                conversation_id = conversation.id
                
                # Create incoming message record
                incoming_message = Message(
                    conversation_id=conversation.id,
                    whatsapp_message_id=message_id,
                    message_type='incoming',
                    content=content
                )
                db.session.add(incoming_message)
                
                logger.info(
                    "Message saved to database",
                    conversation_id=conversation_id,
                    message_id=message_id
                )
        
        except IntegrityError as e:
            logger.error("Database integrity error", error=str(e))
            return jsonify({'error': 'Conflict', 'message': 'Message already exists'}), 409
        
        except SQLAlchemyError as e:
            logger.error("Database transaction failed", error=str(e), exc_info=True)
            return jsonify({'error': 'Internal Server Error', 'message': 'Database error'}), 500
        
        # Dispatch background task only after successful database commit
        if conversation_id:
            try:
                task_result = process_and_reply_task.delay(
                    customer_phone=customer_phone,
                    message=content,
                    conversation_id=str(conversation_id),
                    correlation_id=g.correlation_id
                )
                
                logger.info(
                    "Background task dispatched",
                    conversation_id=conversation_id,
                    task_id=task_result.id
                )
                
            except Exception as e:
                logger.error("Failed to dispatch background task", error=str(e))
                # Don't return error - message is already saved
                # The task dispatch failure is not critical for webhook response
        
        return jsonify({'status': 'OK', 'message': 'Message processed'}), 200
        
    except ValueError as e:
        logger.warning("Validation error", error=str(e))
        return jsonify({'error': 'Bad Request', 'message': str(e)}), 400
        
    except Exception as e:
        logger.error("Unexpected error processing webhook", error=str(e), exc_info=True)
        return jsonify({'error': 'Internal Server Error', 'message': 'Processing failed'}), 500

# Health check endpoint
@webhook_bp.route('/webhook/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring."""
    health_status = {
        'status': 'healthy',
        'timestamp': time.time(),
        'service': 'whatsapp_gateway',
        'version': '1.0.0'
    }
    
    # Check database connectivity
    try:
        db.session.execute(sa.text('SELECT 1'))
        health_status['database'] = 'connected'
    except Exception as e:
        health_status['database'] = 'disconnected'
        health_status['database_error'] = str(e)
        health_status['status'] = 'unhealthy'
    
    # Check Redis connectivity
    try:
        redis_client.ping()
        health_status['redis'] = 'connected'
    except Exception as e:
        health_status['redis'] = 'disconnected'
        health_status['redis_error'] = str(e)
        health_status['status'] = 'degraded'
    
    status_code = 200 if health_status['status'] == 'healthy' else 503
    return jsonify(health_status), status_code

# Error handlers
@webhook_bp.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit exceeded."""
    logger.warning("Rate limit exceeded", limit=str(e.description))
    return jsonify({
        'error': 'Too Many Requests',
        'message': 'Rate limit exceeded',
        'retry_after': e.retry_after
    }), 429

@webhook_bp.errorhandler(500)
def internal_error_handler(e):
    """Handle internal server errors."""
    logger.error("Internal server error", error=str(e), exc_info=True)
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred'
    }), 500