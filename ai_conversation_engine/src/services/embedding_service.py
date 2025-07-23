# ai_conversation_engine/src/services/embedding_service.py

import httpx
import logging
from typing import List, Optional
from src.config import Settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, http_client: httpx.AsyncClient, settings: Settings):
        self.http_client = http_client
        self.settings = settings
        self.api_url = f"https://api.gemini.google.com/v1/embedding?key={self.settings.GEMINI_API_KEY}"
        self.dimension = self.settings.EMBEDDING_DIMENSION  # ✅ Configurable dimension

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generates an embedding for a single text input.

        Args:
            text: The input text to embed.

        Returns:
            Optional[List[float]]: The embedding vector or None if failed.
        """
        headers = {"Content-Type": "application/json"}
        data = {"text": text}
        try:
            response = await self.http_client.post(self.api_url, headers=headers, json=data)
            response.raise_for_status()
            embedding = response.json().get('embedding', [])
            if len(embedding) != self.dimension:
                logger.error(f"Unexpected embedding dimension: {len(embedding)}")
                return None
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding for text: {e}")
            return None

    async def generate_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generates embeddings for a batch of texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors or None for failed embeddings.
        """
        tasks = [self.generate_embedding(text) for text in texts]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculates cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector.
            embedding2: Second embedding vector.

        Returns:
            float: Cosine similarity score.
        """
        if not embedding1 or not embedding2:
            return 0.0
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        norm1 = sum(a * a for a in embedding1) ** 0.5
        norm2 = sum(b * b for b in embedding2) ** 0.5
        return dot_product / (norm1 * norm2) if norm1 and norm2 else 0.0