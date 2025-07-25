# src/services/whatsapp_service_sync.py

import asyncio
from typing import Optional
import structlog

from .whatsapp_service import async_whatsapp_service, WhatsAppError

logger = structlog.get_logger(__name__)

class WhatsAppService:
    """
    A synchronous wrapper for the AsyncWhatsAppService.
    
    This class provides a synchronous interface that correctly handles calling
    async functions without creating a conflicting, long-running event loop.
    """
    def __init__(self):
        self.async_service = async_whatsapp_service
        logger.info("Sync WhatsApp Service initialized.")

    def send_message(self, to: str, message: str) -> Optional[str]:
        """
        Sends a WhatsApp message synchronously by running the async version
        in a new, temporary event loop.

        Returns:
            The message ID if successful, otherwise None.
        """
        log = logger.bind(recipient=to)
        try:
            log.info("Dispatching synchronous send_message to a new event loop.")
            # asyncio.run() creates a new event loop, runs the task, and closes it.
            # This prevents conflict with the main Hypercorn event loop.
            message_id = asyncio.run(self.async_service.send_message(to, message))
            return message_id
        except WhatsAppError as e:
            log.error("Failed to send WhatsApp message (sync wrapper)", error=str(e))
            return None
        except Exception as e:
            # This can happen if Hypercorn's loop is already running, which is fine.
            # We are simply wrapping the async call.
            log.error("An unexpected error occurred in the sync wrapper", error=str(e))
            return None

    def shutdown(self):
        """
        A shutdown method for compatibility. In this new version,
        there's no persistent loop to close, but we can close the underlying
        async client's session.
        """
        try:
            asyncio.run(self.async_service.close())
            logger.info("Sync WhatsApp Service underlying async client has been shut down.")
        except Exception as e:
            logger.error("Error during sync shutdown", error=str(e))


# Instantiate a reusable synchronous service
whatsapp_service = WhatsAppService()

# Ensure cleanup on application exit
import atexit
atexit.register(whatsapp_service.shutdown)