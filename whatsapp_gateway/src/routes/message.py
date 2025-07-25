# whatsapp_gateway/src/routes/message.py

import logging
import re
import time
from typing import Optional, Dict, Any, Tuple
from flask import Blueprint, request, jsonify, g
from sqlalchemy import func, desc, text
from sqlalchemy.orm import selectinload
from marshmallow import Schema, fields, validate, ValidationError, post_load
from uuid import UUID
import sqlalchemy as sa
from contextlib import contextmanager

from src.models.conversation import Conversation, db, Message
from src.services.whatsapp_service_sync import WhatsAppService

import structlog
logger = structlog.get_logger(__name__).bind(
    service="whatsapp_gateway",
    version="1.0.0"
)

# --- Configuration Constants ---
class Config:
    # Message settings
    MAX_MESSAGE_LENGTH = 4096
    MIN_MESSAGE_LENGTH = 1
    
    # Pagination settings
    MAX_PER_PAGE = 100
    DEFAULT_PER_PAGE = 25
    MAX_MESSAGES_LIMIT = 100
    DEFAULT_MESSAGES_LIMIT = 50
    
    # Duplication detection window (5 minutes)
    IDEMPOTENCY_WINDOW_SECONDS = 300
    
    # Phone validation
    PHONE_REGEX = re.compile(r'^\+[1-9]\d{1,14}$')

# --- Blueprint and Service Initialization ---
message_bp = Blueprint('message', __name__)
whatsapp_service = WhatsAppService()

# --- Enhanced Error Handling ---
class MessageAPIError(Exception):
    """Custom exception for API errors."""
    def __init__(self, message: str, status_code: int = 400, details: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)

def handle_api_error(error: MessageAPIError) -> Tuple[Dict[str, Any], int]:
    """Handle API errors consistently."""
    response = {'error': error.message}
    if error.details:
        response['details'] = error.details
    return response, error.status_code

def build_error_response(
    message: str, 
    status_code: int = 400, 
    details: Optional[Dict[str, Any]] = None
) -> Tuple[Dict[str, Any], int]:
    """Build consistent error response."""
    response = {'error': message}
    if details:
        response['details'] = details
    return response, status_code

# --- Database Transaction Management ---
@contextmanager
def db_transaction():
    """Enhanced context manager for database transactions."""
    session = db.session
    try:
        yield session
        session.commit()
        logger.debug("Database transaction committed successfully")
    except Exception as e:
        session.rollback()
        logger.error("Database transaction rolled back", error=str(e))
        raise
    finally:
        db.session.close()

# --- Input Validation Schemas ---
class SendMessageSchema(Schema):
    message = fields.Str(
        required=True,
        validate=[
            validate.Length(
                min=Config.MIN_MESSAGE_LENGTH,
                max=Config.MAX_MESSAGE_LENGTH,
                error="Message must be between {min} and {max} characters."
            ),
            validate.Regexp(
                r'^[\s\S]*[^\s][\s\S]*$',
                error="Message cannot be only whitespace."
            )
        ]
    )

    @post_load
    def strip_message(self, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        data['message'] = data['message'].strip()
        return data

class ConversationFiltersSchema(Schema):
    page = fields.Int(validate=validate.Range(min=1), missing=1)
    per_page = fields.Int(
        validate=validate.Range(min=1, max=Config.MAX_PER_PAGE), 
        missing=Config.DEFAULT_PER_PAGE
    )
    status = fields.Str(
        validate=validate.OneOf(['active', 'inactive', 'closed']), 
        missing=None
    )
    phone_filter = fields.Str(missing=None)

    @post_load
    def validate_phone_filter(self, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Validate phone filter at schema level."""
        if data.get('phone_filter') and not validate_phone_number(data['phone_filter']):
            raise ValidationError({'phone_filter': ['Invalid phone number format']})
        return data

class MessageFiltersSchema(Schema):
    cursor = fields.Str(missing=None)
    limit = fields.Int(
        validate=validate.Range(min=1, max=Config.MAX_MESSAGES_LIMIT), 
        missing=Config.DEFAULT_MESSAGES_LIMIT
    )
    message_type = fields.Str(
        validate=validate.OneOf(['incoming', 'outgoing']), 
        missing=None
    )

# --- Utility Functions ---
def validate_phone_number(phone: str) -> bool:
    """Validate phone number format with enhanced checking."""
    if not phone or not isinstance(phone, str):
        return False
    
    phone = phone.strip()
    return bool(Config.PHONE_REGEX.match(phone))

def truncate_message(content: Optional[str], max_length: int = 50) -> Optional[str]:
    """Safely truncate message content."""
    if not content:
        return content
    return content[:max_length] + '...' if len(content) > max_length else content

def get_request_id() -> str:
    """Get or generate request ID for tracking."""
    return request.headers.get('X-Request-ID', getattr(g, 'correlation_id', 'unknown'))

# --- Route Handlers ---
@message_bp.before_request
def before_request():
    """Set up request context."""
    g.start_time = time.time()
    g.request_id = get_request_id()

@message_bp.after_request
def after_request(response):
    """Log request completion."""
    duration_ms = round((time.time() - getattr(g, 'start_time', time.time())) * 1000, 2)
    
    logger.info(
        "Request completed",
        request_id=getattr(g, 'request_id', 'unknown'),
        method=request.method,
        endpoint=request.endpoint,
        status_code=response.status_code,
        duration_ms=duration_ms
    )
    
    response.headers['X-Request-ID'] = getattr(g, 'request_id', 'unknown')
    return response

@message_bp.route('/conversations', methods=['GET'])
def get_conversations():
    """
    Gets a paginated list of conversations with optimized queries using window functions.
    """
    logger_ctx = logger.bind(
        request_id=g.request_id,
        endpoint='get_conversations'
    )

    try:
        # Validate query parameters
        schema = ConversationFiltersSchema()
        try:
            filters = schema.load(request.args)
        except ValidationError as err:
            logger_ctx.warning("Invalid query parameters", errors=err.messages)
            return jsonify(build_error_response("Invalid query parameters", 400, err.messages)[0]), 400

        page = filters['page']
        per_page = filters['per_page']
        status_filter = filters['status']
        phone_filter = filters['phone_filter']

        # ** Optimized Query Using Window Functions **
        latest_messages_subquery = (
            db.session.query(
                Message.conversation_id,
                Message.content.label('last_content'),
                Message.message_type.label('last_type'),
                Message.created_at.label('last_timestamp'),
                func.row_number().over(
                    partition_by=Message.conversation_id,
                    order_by=Message.created_at.desc()
                ).label('rn')
            ).subquery()
        )

        latest_messages = (
            db.session.query(latest_messages_subquery)
            .filter(latest_messages_subquery.c.rn == 1)
            .subquery()
        )

        base_query = (
            db.session.query(
                Conversation,
                func.count(Message.id).label('message_count'),
                latest_messages.c.last_content,
                latest_messages.c.last_type,
                latest_messages.c.last_timestamp
            )
            .outerjoin(Message, Message.conversation_id == Conversation.id)
            .outerjoin(latest_messages, latest_messages.c.conversation_id == Conversation.id)
            .group_by(
                Conversation.id,
                latest_messages.c.last_content,
                latest_messages.c.last_type,
                latest_messages.c.last_timestamp
            )
        )

        if status_filter:
            base_query = base_query.filter(Conversation.status == status_filter)
        if phone_filter:
            base_query = base_query.filter(Conversation.customer_phone == phone_filter)

        conversations_paginated = (
            base_query
            .order_by(desc(latest_messages.c.last_timestamp))
            .paginate(page=page, per_page=per_page, error_out=False)
        )

        result = []
        for row in conversations_paginated.items:
            conv, message_count, last_content, last_type, last_timestamp = row
            result.append({
                'id': str(conv.id),
                'customer_phone': conv.customer_phone,
                'status': conv.status,
                'created_at': conv.created_at.isoformat(),
                'updated_at': conv.updated_at.isoformat(),
                'message_count': message_count or 0,
                'last_message': {
                    'content': truncate_message(last_content),
                    'type': last_type,
                    'timestamp': last_timestamp.isoformat() if last_timestamp else None
                }
            })

        response_data = {
            'conversations': result,
            'pagination': {
                'page': conversations_paginated.page,
                'per_page': conversations_paginated.per_page,
                'total': conversations_paginated.total,
                'pages': conversations_paginated.pages,
                'has_next': conversations_paginated.has_next,
                'has_prev': conversations_paginated.has_prev
            }
        }

        logger_ctx.info(
            "Conversations fetched successfully",
            total=conversations_paginated.total,
            page=page,
            filters_applied={
                'status': status_filter,
                'phone': bool(phone_filter)
            }
        )

        return jsonify(response_data), 200

    except sa.exc.SQLAlchemyError as e:
        logger_ctx.error("Database error fetching conversations", error=str(e), exc_info=True)
        return jsonify(build_error_response("Failed to fetch conversations", 500)[0]), 500
    except Exception as e:
        logger_ctx.error("Unexpected error fetching conversations", error=str(e), exc_info=True)
        return jsonify(build_error_response("Internal server error", 500)[0]), 500

@message_bp.route('/conversations/<uuid:conversation_id>/messages', methods=['GET'])
def get_conversation_messages(conversation_id: UUID):
    """
    Gets a paginated and filterable list of messages for a specific conversation.
    """
    logger_ctx = logger.bind(
        request_id=g.request_id,
        endpoint='get_conversation_messages',
        conversation_id=str(conversation_id)
    )

    try:
        schema = MessageFiltersSchema()
        try:
            filters = schema.load(request.args)
        except ValidationError as err:
            logger_ctx.warning("Invalid query parameters", errors=err.messages)
            return jsonify(build_error_response("Invalid query parameters", 400, err.messages)[0]), 400

        cursor = filters['cursor']
        limit = filters['limit']
        message_type = filters['message_type']

        conversation_exists = db.session.query(
            Conversation.query.filter_by(id=conversation_id).exists()
        ).scalar()
        
        if not conversation_exists:
            logger_ctx.warning("Conversation not found")
            return jsonify(build_error_response("Conversation not found", 404)[0]), 404

        conversation = db.session.query(Conversation).filter_by(id=conversation_id).first()
        query = Message.query.filter_by(conversation_id=conversation_id)
        if message_type:
            query = query.filter(Message.message_type == message_type)
        if cursor:
            try:
                from datetime import datetime
                cursor_time = datetime.fromisoformat(cursor.replace('Z', '+00:00'))
                query = query.filter(Message.created_at < cursor_time)
            except (ValueError, TypeError) as e:
                logger_ctx.warning("Invalid cursor format", cursor=cursor, error=str(e))
                return jsonify(build_error_response("Invalid cursor format", 400)[0]), 400

        messages = query.order_by(Message.created_at.desc()).limit(limit + 1).all()
        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        messages_list = [{
            'id': str(msg.id),
            'type': msg.message_type,
            'content': msg.content,
            'status': msg.status,
            'timestamp': msg.created_at.isoformat(),
            'whatsapp_message_id': msg.whatsapp_message_id
        } for msg in messages]

        next_cursor = messages[-1].created_at.isoformat() if has_more and messages else None
        response_data = {
            'messages': messages_list,
            'next_cursor': next_cursor,
            'has_more': has_more,
            'conversation': {
                'id': str(conversation.id),
                'customer_phone': conversation.customer_phone,
                'status': conversation.status
            }
        }

        logger_ctx.info(
            "Messages fetched successfully",
            message_count=len(messages_list),
            has_more=has_more,
            filters_applied={
                'message_type': message_type,
                'cursor': bool(cursor)
            }
        )

        return jsonify(response_data), 200

    except sa.exc.SQLAlchemyError as e:
        logger_ctx.error("Database error fetching messages", error=str(e), exc_info=True)
        return jsonify(build_error_response("Failed to fetch messages", 500)[0]), 500
    except Exception as e:
        logger_ctx.error("Unexpected error fetching messages", error=str(e), exc_info=True)
        return jsonify(build_error_response("Internal server error", 500)[0]), 500

@message_bp.route('/conversations/<uuid:conversation_id>/send', methods=['POST'])
def send_message_to_conversation(conversation_id: UUID):
    """
    Sends a message from an agent to a customer with enhanced validation and idempotency.
    """
    logger_ctx = logger.bind(
        request_id=g.request_id,
        endpoint='send_message_to_conversation',
        conversation_id=str(conversation_id)
    )

    try:
        schema = SendMessageSchema()
        try:
            validated_data = schema.load(request.get_json() or {})
        except ValidationError as err:
            logger_ctx.warning("Validation failed", errors=err.messages)
            return jsonify(build_error_response("Validation failed", 400, err.messages)[0]), 400

        message_content = validated_data['message']
        idempotency_key = request.headers.get('Idempotency-Key')
        if idempotency_key:
            existing_message = (
                Message.query
                .filter_by(conversation_id=conversation_id)
                .filter(Message.content == message_content)
                .filter(Message.message_type == 'outgoing')
                .filter(Message.created_at >= func.now() - func.interval(f'{Config.IDEMPOTENCY_WINDOW_SECONDS} seconds'))
                .first()
            )

            if existing_message:
                logger_ctx.info("Duplicate request detected, returning existing message")
                return jsonify({
                    'success': True,
                    'message_id': existing_message.whatsapp_message_id,
                    'message': {
                        'id': str(existing_message.id),
                        'type': existing_message.message_type,
                        'content': existing_message.content,
                        'status': existing_message.status,
                        'timestamp': existing_message.created_at.isoformat()
                    },
                    'duplicate': True
                }), 200

        conversation = db.session.query(Conversation).filter_by(id=conversation_id).first()
        if not conversation:
            logger_ctx.warning("Conversation not found")
            return jsonify(build_error_response("Conversation not found", 404)[0]), 404

        valid_statuses = ['active', 'open']
        if conversation.status not in valid_statuses:
            logger_ctx.warning(
                "Conversation not available for messaging", 
                status=conversation.status,
                valid_statuses=valid_statuses
            )
            return jsonify(build_error_response(
                f"Conversation status '{conversation.status}' does not allow messaging", 
                400
            )[0]), 400

        if not validate_phone_number(conversation.customer_phone):
            logger_ctx.error("Invalid phone number in conversation", phone=conversation.customer_phone)
            return jsonify(build_error_response("Invalid phone number in conversation", 500)[0]), 500

        try:
            with db_transaction() as session:
                response_message_id = whatsapp_service.send_message(
                    conversation.customer_phone,
                    message_content
                )
                if not response_message_id:
                    raise ValueError("WhatsApp service failed to return a message ID")

                outgoing_message = Message(
                    conversation_id=conversation.id,
                    whatsapp_message_id=response_message_id,
                    message_type='outgoing',
                    content=message_content,
                    status='sent'
                )
                session.add(outgoing_message)
                conversation.updated_at = func.now()
                session.flush()

                response_data = {
                    'success': True,
                    'message_id': response_message_id,
                    'message': {
                        'id': str(outgoing_message.id),
                        'type': outgoing_message.message_type,
                        'content': outgoing_message.content,
                        'status': outgoing_message.status,
                        'timestamp': outgoing_message.created_at.isoformat()
                    }
                }

            logger_ctx.info(
                "Message sent successfully",
                message_id=response_message_id,
                customer_phone=conversation.customer_phone,
                content_length=len(message_content)
            )

            return jsonify(response_data), 200

        except sa.exc.IntegrityError as e:
            logger_ctx.error("Database integrity error", error=str(e), exc_info=True)
            return jsonify(build_error_response("Message may already exist", 409)[0]), 409

    except sa.exc.SQLAlchemyError as e:
        logger_ctx.error("Database error sending message", error=str(e), exc_info=True)
        return jsonify(build_error_response("Failed to send message due to database error", 500)[0]), 500
    except ValueError as e:
        logger_ctx.warning("Invalid input or service error", error=str(e))
        return jsonify(build_error_response(str(e), 400)[0]), 400
    except Exception as e:
        logger_ctx.error("Unexpected error sending message", error=str(e), exc_info=True)
        return jsonify(build_error_response("Internal server error", 500)[0]), 500

# Error handlers
@message_bp.errorhandler(MessageAPIError)
def handle_message_api_error(error: MessageAPIError):
    """Handle custom API errors."""
    response, status_code = handle_api_error(error)
    return jsonify(response), status_code

@message_bp.errorhandler(400)
def handle_bad_request(error):
    """Handle bad request errors."""
    logger.warning("Bad request", error=str(error))
    return jsonify(build_error_response("Bad request", 400)[0]), 400

@message_bp.errorhandler(404)
def handle_not_found(error):
    """Handle not found errors."""
    logger.warning("Resource not found", error=str(error))
    return jsonify(build_error_response("Resource not found", 404)[0]), 404

@message_bp.errorhandler(500)
def handle_internal_error(error):
    """Handle internal server errors."""
    logger.error("Internal server error", error=str(error), exc_info=True)
    return jsonify(build_error_response("Internal server error", 500)[0]), 500