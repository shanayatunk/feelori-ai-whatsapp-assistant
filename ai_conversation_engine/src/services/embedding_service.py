# ai_conversation_engine/src/services/embedding_service.py
import httpx
import logging
import asyncio
from typing import List, Optional, Union
from dataclasses import dataclass
from src.config import settings

logger = logging.getLogger(__name__)

@dataclass
class EmbeddingResult:
    """Result wrapper for embedding operations"""
    embedding: Optional[List[float]]
    success: bool
    error: Optional[str] = None

class EmbeddingService:
    """Service for generating text embeddings using Google's Gemini API"""

    def __init__(self, http_client: httpx.AsyncClient, app_settings: "Settings"):
        if not app_settings.GEMINI_API_KEY:
            raise ValueError("API key configuration missing for EmbeddingService")

        self.http_client = http_client
        self.settings = app_settings
        self.api_key = self.settings.GEMINI_API_KEY # Store securely
        self.api_url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.EMBEDDING_MODEL}:embedContent"
        )
        self.dimension = self.settings.EMBEDDING_DIMENSION
        self._request_headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key # Correct header for API Key
        }

        # Rate limiting and retry configuration
        self.max_retries = self.settings.EMBEDDING_MAX_RETRIES
        self.retry_delay = self.settings.EMBEDDING_RETRY_DELAY
        self.request_timeout = self.settings.EMBEDDING_TIMEOUT

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generates an embedding for a single text input with retry logic.

        Args:
            text: Input text to generate embedding for

        Returns:
            List of floats representing the embedding, or None if failed
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding generation")
            return None

        # Truncate text if too long (Gemini has token limits)
        max_length = getattr(self.settings, 'MAX_TEXT_LENGTH', 8192)
        if len(text) > max_length:
            text = text[:max_length]
            logger.warning(f"Text truncated to {max_length} characters")

        data = {
            "model": f"models/{self.settings.EMBEDDING_MODEL}",
            "content": {"parts": [{"text": text}]}
        }

        for attempt in range(self.max_retries):
            try:
                response = await self.http_client.post(
                    self.api_url,
                    headers=self._request_headers,
                    json=data,
                    timeout=self.request_timeout
                )
                response.raise_for_status()

                result = response.json()
                embedding = result.get('embedding', {}).get('values', [])

                if not embedding:
                    logger.error("Empty embedding returned from API")
                    return None
                
                if len(embedding) != self.dimension:
                    logger.error(f"Unexpected embedding dimension: {len(embedding)}, expected: {self.dimension}")
                    return None

                return embedding
            except httpx.TimeoutException:
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Too Many Requests
                    logger.warning(f"Rate limited, attempt {attempt + 1}/{self.max_retries}")
                    if attempt < self.max_retries - 1:
                        # Respect 'Retry-After' header if available
                        retry_after = int(e.response.headers.get("Retry-After", self.retry_delay * (2 ** attempt)))
                        await asyncio.sleep(retry_after)
                else:
                    logger.error(f"HTTP error {e.response.status_code} calling embedding API", exc_info=False)
                    break # Non-retriable error
            except Exception:
                logger.error(f"Unexpected error on attempt {attempt + 1}", exc_info=True)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
        
        logger.error(f"Failed to generate embedding after {self.max_retries} attempts")
        return None

    async def generate_embeddings_batch(
        self, texts: List[str], batch_size: Optional[int] = None, return_results: bool = False
    ) -> Union[List[Optional[List[float]]], List[EmbeddingResult]]:
        """
        Generates embeddings for a batch of texts with proper error handling and batching.

        Args:
            texts: List of texts to generate embeddings for
            batch_size: Number of texts to process concurrently (default from settings)
            return_results: If True, returns EmbeddingResult objects with error info

        Returns:
            List of embeddings or EmbeddingResult objects
        """
        if not texts:
            return []

        batch_size = batch_size or self.settings.EMBEDDING_BATCH_SIZE
        results = []

        # Process in batches to avoid overwhelming the API
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_tasks = [self._generate_embedding_with_result(text) for text in batch]

            try:
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for result in batch_results:
                    if isinstance(result, Exception):
                        error_result = EmbeddingResult(embedding=None, success=False, error=str(result))
                        results.append(error_result if return_results else None)
                    else:
                        results.append(result if return_results else result.embedding)
            
            except Exception as e:
                logger.error(f"Batch processing failed: {e}")
                # Add failed results for the entire batch
                for _ in batch:
                    error_result = EmbeddingResult(embedding=None, success=False, error=str(e))
                    results.append(error_result if return_results else None)

            # Add delay between batches to respect rate limits
            if i + batch_size < len(texts):
                await asyncio.sleep(0.1) 
        
        return results

    async def _generate_embedding_with_result(self, text: str) -> EmbeddingResult:
        """Helper method that returns EmbeddingResult instead of raw embedding"""
        try:
            embedding = await self.generate_embedding(text)
            return EmbeddingResult(
                embedding=embedding,
                success=embedding is not None,
                error=None if embedding else "Failed to generate embedding"
            )
        except Exception as e:
            return EmbeddingResult(embedding=None, success=False, error=str(e))

    def calculate_similarity(
        self, embedding1: List[float], embedding2: List[float]
    ) -> float:
        """
        Calculates cosine similarity between two embeddings with validation.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score between 0 and 1
        """
        if not embedding1 or not embedding2:
            logger.warning("One or both embeddings are empty for similarity calculation")
            return 0.0

        if len(embedding1) != len(embedding2):
            logger.error(
                f"Embedding dimension mismatch: {len(embedding1)} vs {len(embedding2)}"
            )
            return 0.0
        
        try:
            # Use more efficient numpy-style calculation if available
            dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
            norm1 = sum(a * a for a in embedding1) ** 0.5
            norm2 = sum(b * b for b in embedding2) ** 0.5

            if norm1 == 0.0 or norm2 == 0.0: # Use 0.0 for float comparison
                logger.warning("Zero norm detected in embedding, similarity is 0")
                return 0.0

            similarity = dot_product / (norm1 * norm2)
            
            # Clamp to valid range due to floating point precision
            return max(0.0, min(1.0, similarity))
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0

    def calculate_similarity_batch(
        self, query_embedding: List[float], embeddings: List[List[float]]
    ) -> List[float]:
        """
        Calculates cosine similarity between a query embedding and multiple embeddings.

        Args:
            query_embedding: Query embedding vector
            embeddings: List of embedding vectors to compare against

        Returns:
            List of similarity scores
        """
        return [
            self.calculate_similarity(query_embedding, emb) for emb in embeddings
        ]

    async def health_check(self) -> dict:
        """
        Performs a health check by generating a test embedding.

        Returns:
            A dictionary with the health status.
        """
        try:
            test_embedding = await self.generate_embedding("health_check")
            if test_embedding is not None:
                return {"status": "healthy"}
            else:
                return {"status": "unhealthy", "error": "Failed to generate test embedding"}
        except Exception as e:
            logger.error(f"EmbeddingService health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}