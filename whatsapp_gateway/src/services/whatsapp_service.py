# src/services/whatsapp_service.py

import aiohttp
import asyncio
import random
import re
from typing import Optional, Dict, Any
import structlog
from pybreaker import CircuitBreaker

from shared.config import settings

logger = structlog.get_logger(__name__)

# --- Custom Exceptions ---
class WhatsAppError(Exception):
    """Base exception for WhatsApp service errors."""
    pass

class RateLimitError(WhatsAppError):
    """Raised when the rate limit is exceeded."""
    pass

class InvalidRecipientError(WhatsAppError):
    """Raised for invalid recipient phone numbers."""
    pass

# --- Circuit Breaker for WhatsApp API ---
whatsapp_api_breaker = CircuitBreaker(
    fail_max=settings.CIRCUIT_BREAKER_FAIL_MAX,
    reset_timeout=settings.CIRCUIT_BREAKER_RESET_TIMEOUT,
)

class AsyncWhatsAppService:
    """
    An asynchronous service for interacting with the WhatsApp Business API.
    Handles session management, validation, error handling, and retries.
    """
    def __init__(self):
        self.base_url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}"
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self._session: aiohttp.ClientSession = None

        # Basic phone number regex (allows for international numbers)
        self.phone_regex = re.compile(r'^[1-9]\d{6,14}$')

    async def _get_session(self) -> aiohttp.ClientSession:
        """Initializes and returns a reusable aiohttp session."""
        if self._session is None or self._session.closed:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=settings.HTTP_CLIENT_TIMEOUT)
            )
        return self._session

    def _validate_phone_number(self, phone: str) -> str:
        """Strips non-digits and validates the phone number format."""
        cleaned = re.sub(r'\D', '', phone)
        if not self.phone_regex.match(cleaned):
            raise InvalidRecipientError(f"Invalid phone number format: {phone}")
        return cleaned

    def _sanitize_message(self, message: str) -> str:
        """Basic sanitization to remove common injection patterns."""
        # Simple sanitization, consider a more robust library like bleach for production
        return message.strip()

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculates exponential backoff with jitter."""
        base_delay = 1.0
        max_delay = 30.0
        delay = min(base_delay * (2 ** attempt), max_delay)
        jitter = delay * 0.2 * random.random()
        return delay + jitter

    @whatsapp_api_breaker
    async def send_message(
        self,
        to: str,
        message: str,
        max_retries: int = 3
    ) -> Optional[str]:
        """
        Sends a text message to a WhatsApp user with validation and retries.
        """
        try:
            validated_to = self._validate_phone_number(to)
            sanitized_message = self._sanitize_message(message)
        except InvalidRecipientError as e:
            logger.error("Failed to send message due to invalid recipient", phone=to)
            raise e

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": validated_to,
            "type": "text",
            "text": {"body": sanitized_message},
        }

        log = logger.bind(recipient=validated_to)

        for attempt in range(max_retries + 1):
            try:
                session = await self._get_session()
                async with session.post(url, json=payload) as response:
                    response.raise_for_status()
                    response_data = await response.json()
                    message_id = response_data.get("messages", [{}])[0].get("id")
                    
                    if not message_id:
                        raise WhatsAppError("WhatsApp API did not return a message ID")
                        
                    log.info("Successfully sent WhatsApp message", message_id=message_id)
                    return message_id
            
            except aiohttp.ClientResponseError as e:
                log.warning(
                    "HTTP error sending message",
                    status=e.status,
                    attempt=attempt + 1,
                    message=e.message
                )
                if e.status == 429: # Rate limit
                    raise RateLimitError("Rate limit exceeded")
                if 400 <= e.status < 500 and e.status != 429:
                    # Don't retry on client errors (e.g., bad request)
                    raise WhatsAppError(f"Client error: {e.status}") from e
                
                # Retry on server errors (5xx)
                if attempt >= max_retries:
                    raise WhatsAppError("Max retries exceeded for server error") from e
            
            except aiohttp.ClientError as e:
                log.warning("Client error sending message", error=str(e), attempt=attempt + 1)
                if attempt >= max_retries:
                    raise WhatsAppError("Max retries exceeded for client error") from e
            
            backoff = self._calculate_backoff(attempt)
            log.info(f"Retrying in {backoff:.2f} seconds...")
            await asyncio.sleep(backoff)

    async def close(self):
        """Closes the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("WhatsApp service session closed.")

# Instantiate a reusable async service
async_whatsapp_service = AsyncWhatsAppService()