# src/models/base.py

import uuid
import enum
import re
from datetime import datetime
from typing import Dict, Any
import logging

from sqlalchemy import Index, text, CheckConstraint
from sqlalchemy.orm import validates
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from . import db # Assuming your __init__.py sets up the SQLAlchemy 'db' object

# --- Setup Logger ---
logger = logging.getLogger(__name__)

# --- Constants ---
PHONE_REGEX = re.compile(r'^\+[1-9]\d{1,14}$') # E.164 format

# --- Enumerations for Status Fields ---

class ConversationStatus(enum.Enum):
    ACTIVE = 'active'
    CLOSED = 'closed'
    PENDING = 'pending'
    BLOCKED = 'blocked'

class MessageType(enum.Enum):
    INCOMING = 'incoming'
    OUTGOING = 'outgoing'
    SYSTEM = 'system'

class OrderStatus(enum.Enum):
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    SHIPPED = 'shipped'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'
    RETURNED = 'returned'

class DocumentType(enum.Enum):
    FAQ = 'faq'
    POLICY = 'policy'
    GUIDE = 'guide'
    PRODUCT_INFO = 'product_info'


# --- Base Model for Common Logic ---

class BaseModel(db.Model):
    """
    An abstract base model that provides default 'created_at' and 'updated_at'
    fields, and a primary key.
    """
    __abstract__ = True

    id = db.Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        """Provides a default serialization method."""
        return {
            c.name: getattr(self, c.name) for c in self.__table__.columns
        }

    def save(self):
        """Adds and commits the current instance to the database session."""
        db.session.add(self)
        db.session.commit()

    def delete(self):
        """Deletes the current instance from the database session."""
        db.session.delete(self)
        db.session.commit()