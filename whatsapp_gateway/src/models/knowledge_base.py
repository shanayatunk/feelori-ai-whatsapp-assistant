# src/models/knowledge_base.py

import logging
from typing import Any, Dict, List, Optional

import numpy as np
from pgvector.sqlalchemy import Vector
from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import JSONB, UUID  # <-- ADDED UUID IMPORT

from . import db
from .base import BaseModel, DocumentType

logger = logging.getLogger(__name__)


class Document(BaseModel):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    document_type = db.Column(db.Enum(DocumentType), nullable=False, index=True)
    category = db.Column(db.String(100), index=True)
    source_url = db.Column(db.String(512))
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    chunks = db.relationship('DocumentChunk', backref='document', lazy='dynamic', cascade='all, delete-orphan')

    __table_args__ = (
        Index('idx_document_type_category_active', 'document_type', 'category', 'is_active'),
    )

    def to_dict(self) -> Dict[str, Any]:
        try:
            return {
                'id': self.id,
                'title': self.title,
                'document_type': self.document_type.value,
                'category': self.category,
                'source_url': self.source_url,
                'created_at': self.created_at.isoformat(),
                'updated_at': self.updated_at.isoformat(),
                'is_active': self.is_active,
            }
        except (AttributeError, TypeError) as e:
            logger.error(f"Serialization error for Document {self.id}: {e}")
            raise ValueError(f"Error serializing Document: {str(e)}")

    def __repr__(self) -> str:
        return f"<Document {self.id}: {self.title}>"


class DocumentChunk(BaseModel):
    __tablename__ = 'document_chunks'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    chunk_text = db.Column(db.Text, nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)

    embedding = db.Column(Vector(768))

    __table_args__ = (
        Index('idx_chunk_document_index', 'document_id', 'chunk_index', unique=True),
        Index('idx_chunk_embedding', 'embedding', postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}),
    )

    def set_embedding(self, embedding_vector: List[float]) -> None:
        if not isinstance(embedding_vector, list) or not all(isinstance(i, float) for i in embedding_vector):
            raise ValueError("Embedding must be a list of floats.")
        self.embedding = np.array(embedding_vector)

    def get_embedding(self) -> Optional[List[float]]:
        if self.embedding is None:
            return None
        return self.embedding.tolist()

    def __repr__(self) -> str:
        return f"<DocumentChunk {self.id} for Document {self.document_id}>"


class ConversationContext(BaseModel):
    __tablename__ = 'conversation_contexts'

    id = db.Column(db.Integer, primary_key=True)
    # --- THIS LINE IS NOW CORRECTED ---
    conversation_id = db.Column(UUID(as_uuid=True), db.ForeignKey('conversations.id'), nullable=False, index=True)
    context_data = db.Column(JSONB)

    def __repr__(self) -> str:
        return f"<ConversationContext for Conversation {self.conversation_id}>"


class IntentPattern(BaseModel):
    __tablename__ = 'intent_patterns'

    id = db.Column(db.Integer, primary_key=True)
    pattern = db.Column(db.String(255), nullable=False)
    intent = db.Column(db.String(100), nullable=False, index=True)
    confidence = db.Column(db.Float)

    def __repr__(self) -> str:
        return f"<IntentPattern '{self.pattern}' -> '{self.intent}'>"