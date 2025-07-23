# ai_conversation_engine/src/services/knowledge_retriever.py

import asyncio
import logging
from typing import List, Dict
from src.services.embedding_service import EmbeddingService
from src.config import settings  # ✅ Added import

logger = logging.getLogger(__name__)

class KnowledgeRetriever:
    def __init__(self, http_client, settings):
        """
        Initializes the knowledge retriever with dynamic document loading.
        """
        self.embedding_service = EmbeddingService(http_client, settings)
        self.docs = [
            {"chunk_text": "Our return policy allows returns within 30 days."},
            {"chunk_text": "Free shipping on orders above ₹1000."},
            {"chunk_text": "Refunds are processed within 7 business days."}
        ]
        self.embeddings = None
        
    async def initialize(self) -> None:
        """
        Initializes embeddings asynchronously.
        """
        if self.embeddings is None:
            self.embeddings = await self._generate_embeddings()

    async def _generate_embeddings(self) -> List[List[float]]:
        """Generates embeddings for all documents asynchronously."""
        texts = [doc["chunk_text"] for doc in self.docs]
        embeddings = await self.embedding_service.generate_embeddings_batch(texts)
        return [emb for emb in embeddings if emb is not None]

    async def search(self, query: str, limit: int = 1) -> List[Dict[str, str]]:
        """
        Searches for documents matching the query using embedding similarity.

        Args:
            query: The search query.
            limit: Maximum number of results to return.

        Returns:
            List of matching documents.
        """
        query_embedding = await self.embedding_service.generate_embedding(query)
        if not query_embedding:
            logger.warning(f"Failed to generate embedding for query: {query}")
            return []

        results = []
        for i, doc_embedding in enumerate(self.embeddings):
            similarity = self.embedding_service.calculate_similarity(query_embedding, doc_embedding)
            if similarity > settings.SIMILARITY_THRESHOLD:  # ✅ Use config
                results.append({"index": i, "similarity": similarity})
        
        results.sort(key=lambda x: x[1], reverse=True)
        return [self.docs[r["index"]] for r in results[:limit]]