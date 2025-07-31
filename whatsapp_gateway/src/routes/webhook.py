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
from src.models.conversation import Conversation, Message, MessageType
from src.tasks import process_and_reply_task
from shared.cache import redis_client

import bleach
import structlog

# --- Setup & Configuration ---

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

# REFINEMENT: Custom exception for specific handling
class NonTextMessageError(ValueError):
    """Custom exception for non-text message types."""
    pass

def read_secret_from_file(file_path: Optional[str]) -> Optional[str]:
    if not file_path:
        return None
    try:
        with open(file_path, 'r') as f:
            return f.read().strip()
    except (IOError, FileNotFoundError):
        return None

# --- Constants & Settings ---
WHATSAPP_VERIFY_TOKEN = read_secret_from_file(os.getenv('WHATSAPP_VERIFY_TOKEN_FILE'))
WEBHOOK_SECRET = read_secret_from_file(os.getenv('WHATSAPP_WEBHOOK_SECRET_FILE'))
REDIS_PASSWORD = read_secret_from_file(os.getenv('REDIS_PASSWORD_FILE'))
WEBHOOK_TIMEOUT = int(os.getenv('WEBHOOK_TIMEOUT', '300'))
STRICT_REDIS_DEDUP = os.getenv('STRICT_REDIS_DEDUP', 'false').lower() == 'true'

if REDIS_PASSWORD:
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@redis:6379/0"
else:
    REDIS_URL = "redis://redis:6379/0"

if not WEBHOOK_SECRET:
    raise ValueError("WEBHOOK_SECRET must be configured for security")
if not WHATSAPP_VERIFY_TOKEN:
    raise ValueError("WHATSAPP_VERIFY_TOKEN must be configured")

webhook_bp = Blueprint('webhook', __name__)

# --- Rate Limiter ---
def get_rate_limit_key() -> str:
    correlation_id = getattr(g, 'correlation_id', 'unknown')
    try:
        data = request.get_json(force=False, silent=True) or {}
        phone = (data.get('entry', [{}])[0]
                    .get('changes', [{}])[0]
                    .get('value', {})
                    .get('messages', [{}])[0]
                    .get('from'))
        if phone:
            return f"phone:{InputValidator.validate_phone_number(phone)}:{correlation_id}"
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return f"ip:{get_remote_address()}:{correlation_id}"

limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["100 per minute", "1000 per hour"],
    storage_uri=REDIS_URL,
    storage_options={"socket_connect_timeout": 5}
)


# --- Input Validation ---
class InputValidator:
    PHONE_PATTERN = re.compile(r'^\+?[1-9]\d{8,14}$')
    MESSAGE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_.-=]{1,255}$')
    MAX_MESSAGE_LENGTH = 4096

    @staticmethod
    def validate_phone_number(phone: str) -> str:
        """Validate and normalize phone number format."""
        if not phone:
            raise ValueError("Phone number is required")
        
        phone = phone.strip()
        # vvv ADD THIS BLOCK vvv
        if not phone.startswith('+'):
            phone = f"+{phone}"
        # ^^^ END BLOCK ^^^
            
        if not InputValidator.PHONE_PATTERN.match(phone):
            raise ValueError(f"Invalid phone number format for Conversation: {phone}")
        return phone

    @staticmethod
    def validate_message_id(message_id: str) -> str:
        if not message_id or not InputValidator.MESSAGE_ID_PATTERN.match(message_id):
            raise ValueError("Invalid message ID format")
        return message_id

    @staticmethod
    def sanitize_message_content(content: str) -> str:
        if not content:
            raise ValueError("Message content is required")
        content = bleach.clean(content, tags=[], strip=True, strip_comments=True)
        content = html.escape(content).strip()
        if not content:
            raise ValueError("Message content is empty after sanitization")
        return content[:InputValidator.MAX_MESSAGE_LENGTH]


# --- Security & Verification (REFINED) ---

def _verify_hmac_signature(request_obj) -> bool:
    """Verifies the HMAC-SHA256 signature of the request."""
    signature = request_obj.headers.get('X-Hub-Signature-256')
    if not signature:
        logger.warning("Missing X-Hub-Signature-256 header")
        return False

    body = request_obj.get_data()
    expected_signature = 'sha256=' + hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        logger.warning("Webhook HMAC signature verification failed: Signatures do not match.")
        return False
    return True

def _is_valid_timestamp(payload: Dict[str, Any]) -> bool:
    """Validates the payload timestamp to prevent replay attacks."""
    try:
        change_value = payload.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {})
        
        timestamp = None
        if 'messages' in change_value:
            timestamp = int(change_value['messages'][0]['timestamp'])
        elif 'statuses' in change_value:
            timestamp = int(change_value['statuses'][0]['timestamp'])
        else:
            logger.info("Unhandled payload type, skipping timestamp check.", payload_keys=list(change_value.keys()))
            return True

        if abs(time.time() - timestamp) > WEBHOOK_TIMEOUT:
            logger.warning("Stale webhook timestamp detected (potential replay attack).",
                           timestamp_age=abs(time.time() - timestamp))
            return False
        return True
    except (KeyError, IndexError, TypeError, ValueError):
        logger.warning("Could not extract timestamp from webhook payload.")
        return False

def verify_webhook_signature(request_obj) -> bool:
    """
    REFINEMENT: Decoupled function that performs both HMAC and timestamp validation.
    """
    if not _verify_hmac_signature(request_obj):
        return False
    
    try:
        payload = request_obj.get_json()
        if not _is_valid_timestamp(payload):
            return False
    except json.JSONDecodeError:
        logger.warning("Could not verify timestamp because payload is not valid JSON.")
        return False
        
    return True


# --- Core Logic ---

def is_duplicate_webhook(message_id: str, phone: str) -> bool:
    """REFINEMENT: Check for duplicates with better logging and optional fail-fast."""
    try:
        key = f"webhook_seen:{message_id}:{phone}"
        logger.debug("Deduplication key used", redis_key=key) # Added for debuggability
        
        result = redis_client.set(key, "1", nx=True, ex=300)
        return result is None # True if the key already existed
    except RedisError as e:
        logger.warning("Redis error during duplicate check", error=str(e), correlation_id=g.get('correlation_id'))
        if STRICT_REDIS_DEDUP:
            raise RuntimeError("Redis unavailable - cannot perform deduplication") from e
        return False

def extract_message_data(payload: Dict[str, Any]) -> Tuple[str, str, str]:
    """REFINEMENT: Now raises a specific error for non-text messages."""
    try:
        value = payload['entry'][0]['changes'][0]['value']
        message = value['messages'][0]
        
        message_type = message.get('type')
        if message_type != 'text':
            raise NonTextMessageError(f"Non-text message received: {message_type}")

        customer_phone = InputValidator.validate_phone_number(message['from'])
        message_id = InputValidator.validate_message_id(message['id'])
        content = InputValidator.sanitize_message_content(message['text']['body'])
        
        return customer_phone, message_id, content
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"Invalid text message structure: {e}") from e

@contextmanager
def db_transaction():
    try:
        yield db.session
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    finally:
        db.session.close()


# --- Request Handlers & Blueprint ---

@webhook_bp.before_request
def before_webhook_request():
    g.correlation_id = str(uuid.uuid4())
    g.start_time = time.time()
    structlog.contextvars.bind_contextvars(
        correlation_id=g.correlation_id,
        method=request.method,
        path=request.path
    )

@webhook_bp.after_request
def after_webhook_request(response):
    duration = time.time() - getattr(g, 'start_time', time.time())
    logger.info("Request completed", status_code=response.status_code, duration_ms=round(duration * 1000, 2))
    response.headers['X-Correlation-ID'] = getattr(g, 'correlation_id', 'unknown')
    return response

def handle_webhook_verification() -> Response:
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return Response(challenge, status=200, mimetype='text/plain')
    else:
        logger.warning("Webhook verification failed", mode=mode, token_match=(token == WHATSAPP_VERIFY_TOKEN))
        return jsonify({'error': 'Forbidden', 'message': 'Invalid verification token'}), 403


def handle_incoming_event() -> Tuple[Response, int]:
    if not verify_webhook_signature(request):
        return jsonify({'error': 'Unauthorized', 'message': 'Invalid signature'}), 401

    try:
        payload = request.get_json()
        change_value = payload['entry'][0]['changes'][0]['value']

        if 'messages' in change_value:
            customer_phone, message_id, content = extract_message_data(payload)
            if is_duplicate_webhook(message_id, customer_phone):
                logger.info("Duplicate message webhook ignored", message_id=message_id)
                return jsonify({'status': 'OK', 'message': 'Duplicate ignored'}), 200
            
            conversation_id = None
            with db_transaction():
                conversation = Conversation.query.filter_by(customer_phone=customer_phone).first()
                if not conversation:
                    conversation = Conversation(customer_phone=customer_phone)
                    db.session.add(conversation)
                    db.session.flush()
                
                conversation_id = conversation.id
                
                db.session.add(Message(
                    conversation_id=conversation_id,
                    whatsapp_message_id=message_id,
                    message_type=MessageType.INCOMING,
                    content=content
                ))
            
            # CORRECT: The task is dispatched *after* the database transaction is committed.
            if conversation_id:
                process_and_reply_task.delay(
                    customer_phone=customer_phone, message=content,
                    conversation_id=str(conversation_id),
                    correlation_id=g.correlation_id
                )
            
            return jsonify({'status': 'OK', 'message': 'Message processed'}), 200

        elif 'statuses' in change_value:
            status = change_value['statuses'][0]
            logger.info("Received message status update", status=status.get('status'), msg_id=status.get('id'))
            return jsonify({'status': 'OK', 'message': 'Status update acknowledged'}), 200

        else:
            logger.warning("Received unhandled webhook type", payload_keys=list(change_value.keys()))
            return jsonify({'status': 'OK', 'message': 'Unhandled event type received'}), 200

    except NonTextMessageError as e:
        logger.info("Ignoring non-text message", reason=str(e))
        return jsonify({'status': 'OK', 'message': 'Non-text message ignored'}), 200
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning("Validation error processing webhook", error=str(e))
        return jsonify({'error': 'Bad Request', 'message': str(e)}), 400
    except (SQLAlchemyError, IntegrityError) as e:
        logger.error("Database transaction failed", error=str(e), exc_info=True, correlation_id=g.get('correlation_id'))
        return jsonify({'error': 'Internal Server Error', 'message': 'Database error'}), 500
    except Exception as e:
        logger.error("Unexpected error processing webhook", error=str(e), exc_info=True, correlation_id=g.get('correlation_id'))
        return jsonify({'error': 'Internal Server Error', 'message': 'Processing failed'}), 500

@webhook_bp.route('/webhook', methods=['GET', 'POST'])
@limiter.limit("200 per minute")
def handle_webhook():
    return handle_webhook_verification() if request.method == 'GET' else handle_incoming_event()

# --- Health Check & Error Handlers ---
@webhook_bp.route('/health', methods=['GET'])
def health_check():
    # Renamed from /webhook/health to be more standard
    # ... health check logic ...
    return jsonify({'status': 'healthy'}), 200

@webhook_bp.errorhandler(429)
def ratelimit_handler(e):
    logger.warning("Rate limit exceeded", limit=str(e.description))
    return jsonify({'error': 'Too Many Requests', 'message': f'Rate limit exceeded: {e.description}'}), 429

@webhook_bp.errorhandler(500)
def internal_error_handler(e):
    logger.error("Internal server error", error=str(e), exc_info=True, correlation_id=g.get('correlation_id'))
    return jsonify({'error': 'Internal Server Error', 'message': 'An unexpected error occurred'}), 500