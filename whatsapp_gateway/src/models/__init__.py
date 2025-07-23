from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import all models to ensure they're registered
from .conversation import Conversation, Message
from .knowledge_base import Document, DocumentChunk, ConversationContext, IntentPattern
from .order import Order