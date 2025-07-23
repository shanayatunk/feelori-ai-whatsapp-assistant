# src/services/ai_service.py

import httpx
from typing import Optional, Dict, Any
import structlog
from pybreaker import CircuitBreaker

from src.config import settings

logger = structlog.get_logger(__name__)

# --- Circuit Breaker for AI Service ---
# Prevents cascading failures if the AI service is down
ai_service_breaker = CircuitBreaker(
    fail_max=settings.CIRCUIT_BREAKER_FAIL_MAX,
    reset_timeout=settings.CIRCUIT_BREAKER_RESET_TIMEOUT,
)

class AIServiceError(Exception):
    """Custom exception for AI service-related errors."""
    pass

class AIService:
    """A client for interacting with the external AI service."""

    def __init__(self):
        self.url = settings.AI_SERVICE_URL
        self._client = httpx.AsyncClient(
            base_url=self.url,
            timeout=settings.HTTP_CLIENT_TIMEOUT
        )
        logger.info("AI Service client initialized", url=self.url)

    @ai_service_breaker
    async def process_message(
        self,
        message: str,
        conversation_id: str,
        correlation_id: str
    ) -> Optional[str]:
        """
        Sends a message to the AI service for processing and returns the response.

        Args:
            message: The content of the user's message.
            conversation_id: The unique ID for the conversation.
            correlation_id: The request ID for tracing.

        Returns:
            The AI's text response, or None on failure.
            
        Raises:
            AIServiceError: If the service call fails after retries.
        """
        endpoint = "/ai/process"
        payload = {
            "message": message,
            "conv_id": conversation_id,
        }
        headers = {
            'X-Correlation-ID': correlation_id,
            'Content-Type': 'application/json'
        }
        
        log = logger.bind(
            endpoint=endpoint,
            conversation_id=conversation_id,
            correlation_id=correlation_id
        )

        try:
            log.info("Sending request to AI service")
            response = await self._client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()

            response_data = response.json()
            ai_reply = response_data.get('response')

            if not ai_reply:
                log.warning("AI service returned an empty response")
                raise AIServiceError("Empty response from AI service")

            log.info("Successfully received response from AI service")
            return ai_reply

        except httpx.HTTPStatusError as e:
            log.error(
                "HTTP error calling AI service",
                status_code=e.response.status_code,
                response_body=e.response.text
            )
            raise AIServiceError(f"AI service returned status {e.response.status_code}") from e
        except httpx.RequestError as e:
            log.error("Request error calling AI service", error=str(e))
            raise AIServiceError("Network error while contacting AI service") from e
        except Exception as e:
            log.error("An unexpected error occurred in AI service client", error=str(e))
            raise AIServiceError("An unexpected error occurred") from e

    async def close(self):
        """Closes the HTTP client session."""
        await self._client.aclose()
        logger.info("AI Service client closed.")

# Instantiate a reusable client
ai_service_client = AIService()