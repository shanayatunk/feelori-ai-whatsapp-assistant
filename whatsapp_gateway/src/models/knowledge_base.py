# src/models/knowledge_base.py

import json
import logging
from typing import Dict, Any, List, Optional

# IMPORTANT: For production, replace this with a proper vector type from a library
# like pgvector. This is a placeholder for demonstration.
from sqlalchemy.dialects.postgresql import JSONB as VectorType

from .base import BaseModel, DocumentType
from . import db
from sqlalchemy import Index

logger = logging.getLogger(__name__)

class Document(BaseModel):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True) # Override for integer PK
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
                'is_active': self.is_active
            }
        except (AttributeError, TypeError) as e:
            logger.error(f"Serialization error for Document {self.id}: {e}")
            raise ValueError(f"Error serializing Document: {str(e)}")

class DocumentChunk(BaseModel):
    __tablename__ = 'document_chunks'
    
    id = db.Column(db.Integer, primary_key=True) # Override for integer PK
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    chunk_text = db.Column(db.Text, nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)
    
    # NOTE: Using JSONB as a placeholder. For real vector search, use a dedicated
    # vector type from a library like 'pgvector'.
    embedding = db.Column(VectorType) 
    
    __table_args__ = (
        Index('idx_chunk_document_index', 'document_id', 'chunk_index', unique=True),
        # Example of how a vector index would be created with pgvector
        # Index('idx_chunk_embedding', 'embedding', postgresql_using='ivfflat', postgresql_with={'lists': 100})
    )
    
    def set_embedding(self, embedding_vector: List[float]) -> None:
        """Sets the embedding vector."""
        if not isinstance(embedding_vector, list) or not all(isinstance(i, float) for i in embedding_vector):
            raise ValueError("Embedding must be a list of floats.")
        self.embedding = embedding_vector
    
    def get_embedding(self) -> Optional[List[float]]:
        """Gets the embedding vector."""
        return self.embedding