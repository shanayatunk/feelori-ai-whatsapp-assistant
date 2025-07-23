# src/services/whatsapp_service_sync.py

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
import structlog

from .whatsapp_service import async_whatsapp_service, WhatsAppError

logger = structlog.get_logger(__name__)

class WhatsAppService:
    """
    A synchronous wrapper for the AsyncWhatsAppService.
    
    This class provides a synchronous interface for sending messages, correctly
    managing the async event loop in a separate thread to avoid blocking.
    """
    def __init__(self):
        self.async_service = async_whatsapp_service
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        
        self._executor = ThreadPoolExecutor(max_workers=1)

        # Run the event loop in a separate thread
        self._executor.submit(self._loop.run_forever)

        logger.info("Sync WhatsApp Service initialized with a dedicated event loop.")

    def _run_async(self, coro):
        """Submits a coroutine to the running event loop and waits for the result."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def send_message(self, to: str, message: str) -> Optional[str]:
        """
        Sends a WhatsApp message synchronously.

        Returns:
            The message ID if successful, otherwise None.
        """
        log = logger.bind(recipient=to)
        try:
            log.info("Dispatching synchronous send_message to event loop.")
            message_id = self._run_async(self.async_service.send_message(to, message))
            return message_id
        except WhatsAppError as e:
            log.error("Failed to send WhatsApp message (sync wrapper)", error=str(e))
            return None
        except Exception as e:
            log.error("An unexpected error occurred in the sync wrapper", error=str(e))
            return None

    def shutdown(self):
        """Gracefully shuts down the event loop and thread pool."""
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._executor.shutdown(wait=True)
        logger.info("Sync WhatsApp Service event loop has been shut down.")

# Instantiate a reusable synchronous service
whatsapp_service = WhatsAppService()

# Ensure cleanup on application exit
import atexit
atexit.register(whatsapp_service.shutdown)