# whatsapp_gateway/src/models.py

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

db = SQLAlchemy()

class BaseModel(db.Model):
    """Base model with common fields for all models."""
    __abstract__ = True
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

class WhatsAppMessage(BaseModel):
    """Model to store WhatsApp messages."""
    __tablename__ = 'whatsapp_messages'
    
    # WhatsApp identifiers
    whatsapp_message_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone_number = db.Column(db.String(20), nullable=False, index=True)
    phone_number_id = db.Column(db.String(255), nullable=False)
    
    # Message content
    message_type = db.Column(db.String(50), nullable=False)  # text, image, audio, etc.
    message_content = db.Column(db.Text)
    message_metadata = db.Column(JSONB)  # Store additional message data
    
    # Message direction and status
    direction = db.Column(db.String(10), nullable=False)  # inbound, outbound
    status = db.Column(db.String(20), default='received')  # received, processed, sent, failed
    
    # Processing information
    conversation_id = db.Column(db.String(255), index=True)
    ai_response = db.Column(db.Text)
    processing_duration = db.Column(db.Float)  # Processing time in seconds
    error_message = db.Column(db.Text)
    
    # Indexes for better query performance
    __table_args__ = (
        db.Index('idx_phone_created', 'phone_number', 'created_at'),
        db.Index('idx_conversation_created', 'conversation_id', 'created_at'),
        db.Index('idx_status_created', 'status', 'created_at'),
    )
    
    def __repr__(self):
        return f'<WhatsAppMessage {self.whatsapp_message_id} from {self.phone_number}>'
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': str(self.id),
            'whatsapp_message_id': self.whatsapp_message_id,
            'phone_number': self.phone_number,
            'phone_number_id': self.phone_number_id,
            'message_type': self.message_type,
            'message_content': self.message_content,
            'message_metadata': self.message_metadata,
            'direction': self.direction,
            'status': self.status,
            'conversation_id': self.conversation_id,
            'ai_response': self.ai_response,
            'processing_duration': self.processing_duration,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class WebhookEvent(BaseModel):
    """Model to store webhook events for auditing."""
    __tablename__ = 'webhook_events'
    
    # Event identification
    event_type = db.Column(db.String(100), nullable=False)
    event_source = db.Column(db.String(50), default='whatsapp')
    
    # Request information
    request_headers = db.Column(JSONB)
    request_body = db.Column(JSONB)
    request_signature = db.Column(db.String(255))
    
    # Processing information
    processing_status = db.Column(db.String(20), default='pending')  # pending, processed, failed
    processing_duration = db.Column(db.Float)
    error_message = db.Column(db.Text)
    
    # Response information
    response_status_code = db.Column(db.Integer)
    response_body = db.Column(JSONB)
    
    __table_args__ = (
        db.Index('idx_event_type_created', 'event_type', 'created_at'),
        db.Index('idx_processing_status', 'processing_status'),
    )
    
    def __repr__(self):
        return f'<WebhookEvent {self.event_type} - {self.processing_status}>'
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': str(self.id),
            'event_type': self.event_type,
            'event_source': self.event_source,
            'processing_status': self.processing_status,
            'processing_duration': self.processing_duration,
            'error_message': self.error_message,
            'response_status_code': self.response_status_code,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class ConversationSession(BaseModel):
    """Model to track conversation sessions."""
    __tablename__ = 'conversation_sessions'
    
    # Session identification
    session_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone_number = db.Column(db.String(20), nullable=False, index=True)
    
    # Session state
    status = db.Column(db.String(20), default='active')  # active, ended, expired
    last_activity = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Conversation context
    context_data = db.Column(JSONB)  # Store conversation context
    message_count = db.Column(db.Integer, default=0)
    
    # Session metadata
    user_agent = db.Column(db.String(255))
    ip_address = db.Column(db.String(45))  # IPv6 compatible
    
    __table_args__ = (
        db.Index('idx_phone_last_activity', 'phone_number', 'last_activity'),
        db.Index('idx_status_last_activity', 'status', 'last_activity'),
    )
    
    def __repr__(self):
        return f'<ConversationSession {self.session_id} for {self.phone_number}>'
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': str(self.id),
            'session_id': self.session_id,
            'phone_number': self.phone_number,
            'status': self.status,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'context_data': self.context_data,
            'message_count': self.message_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class MessageTemplate(BaseModel):
    """Model to store message templates."""
    __tablename__ = 'message_templates'
    
    # Template identification
    template_name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    template_type = db.Column(db.String(50), nullable=False)  # greeting, error, help, etc.
    
    # Template content
    template_content = db.Column(db.Text, nullable=False)
    template_variables = db.Column(JSONB)  # Variables that can be substituted
    
    # Template configuration
    is_active = db.Column(db.Boolean, default=True)
    language_code = db.Column(db.String(10), default='en')
    
    def __repr__(self):
        return f'<MessageTemplate {self.template_name}>'
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': str(self.id),
            'template_name': self.template_name,
            'template_type': self.template_type,
            'template_content': self.template_content,
            'template_variables': self.template_variables,
            'is_active': self.is_active,
            'language_code': self.language_code,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }