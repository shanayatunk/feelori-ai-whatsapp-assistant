# src/models/conversation.py

from .base import BaseModel, ConversationStatus, MessageType, PHONE_REGEX
from . import db
from sqlalchemy import Index, text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import validates
from typing import Dict, Any
import uuid
import logging

logger = logging.getLogger(__name__)

class Conversation(BaseModel):
    __tablename__ = 'conversations'

    customer_phone = db.Column(db.String(20), nullable=False, index=True) # unique=True removed
    status = db.Column(db.Enum(ConversationStatus), nullable=False, default=ConversationStatus.ACTIVE, index=True)

    messages = db.relationship('Message', backref='conversation', lazy='dynamic', cascade="all, delete-orphan")

    __table_args__ = (
        # Optimized indexes based on common query patterns
        Index('idx_conversation_phone_status', 'customer_phone', 'status'),
        Index('idx_conversation_status_updated', 'status', 'updated_at'),
    )

    @validates('customer_phone')
    def validate_phone(self, key, phone):
        if not PHONE_REGEX.match(phone):
            raise ValueError(f"Invalid phone number format for Conversation: {phone}")
        return phone

    def __repr__(self) -> str:
        return f"<Conversation {self.id} for {self.customer_phone}>"

class Message(BaseModel):
    __tablename__ = 'messages'

    conversation_id = db.Column(UUID(as_uuid=True), db.ForeignKey('conversations.id'), nullable=False, index=True, default=uuid.uuid4)
    whatsapp_message_id = db.Column(db.String(255), unique=True, nullable=True, index=True) # Added unique constraint
    message_type = db.Column(db.Enum(MessageType), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=True, index=True) # e.g., 'sent', 'delivered', 'read'

    __table_args__ = (
        Index('idx_message_conv_created', 'conversation_id', 'created_at'),
        # Check constraint to enforce valid message types at the DB level
        CheckConstraint(
            "message_type IN ('INCOMING', 'OUTGOING', 'SYSTEM')",
            name='check_message_type'
        ),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the Message object to a dictionary."""
        try:
            return {
                'id': str(self.id),
                'conversation_id': str(self.conversation_id),
                'whatsapp_message_id': self.whatsapp_message_id,
                'message_type': self.message_type.value,
                'content': self.content,
                'status': self.status,
                'created_at': self.created_at.isoformat()
            }
        except (AttributeError, TypeError) as e:
            logger.error(f"Serialization error for Message {self.id}: {e}")
            raise ValueError(f"Error serializing Message: {str(e)}")

    def __repr__(self) -> str:
        return f"<Message {self.id} in conversation {self.conversation_id}>"