# src/models/__init__.py

from flask_sqlalchemy import SQLAlchemy

# Create the db instance
db = SQLAlchemy()

# Import all models to ensure they're registered with SQLAlchemy
from .base import BaseModel
from .conversation import Conversation, Message
from .knowledge_base import Document, DocumentChunk, ConversationContext, IntentPattern
from .order import Order

# Make models available at package level for easier imports elsewhere
__all__ = [
    'db',
    'BaseModel',
    'Conversation',
    'Message',
    'Document',
    'DocumentChunk',
    'ConversationContext',
    'IntentPattern',
    'Order'
]