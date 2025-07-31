# src/services/whatsapp_service_sync.py

import asyncio
import threading
from typing import Optional
import structlog

from .whatsapp_service import async_whatsapp_service, WhatsAppError

logger = structlog.get_logger(__name__)

class WhatsAppService:
    """
    A synchronous wrapper for the AsyncWhatsAppService.
    
    This class provides a synchronous interface that correctly handles calling
    async functions in Celery workers where event loops may be closed or reused.
    """
    def __init__(self):
        self.async_service = async_whatsapp_service
        logger.info("Sync WhatsApp Service initialized.")

    def send_message(self, to: str, message: str) -> Optional[str]:
        """
        Sends a WhatsApp message synchronously by running the async version
        in a new event loop. This approach avoids conflicts with Celery's
        event loop management.
        """
        log = logger.bind(recipient=to)
        
        try:
            log.info("Dispatching synchronous send_message to a new event loop.")
            
            # Always create a new event loop for each operation
            # This avoids issues with closed or conflicting loops in Celery
            def run_async_task():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(
                        self.async_service.send_message(to, message)
                    )
                finally:
                    # Clean up the loop properly
                    try:
                        # Cancel any remaining tasks
                        pending = asyncio.all_tasks(loop)
                        for task in pending:
                            task.cancel()
                        
                        # Give tasks a chance to clean up
                        if pending:
                            loop.run_until_complete(
                                asyncio.gather(*pending, return_exceptions=True)
                            )
                    except Exception as cleanup_error:
                        log.warning("Error during loop cleanup", error=str(cleanup_error))
                    finally:
                        loop.close()
            
            # Run in a separate thread to completely isolate from Celery's event loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_async_task)
                message_id = future.result(timeout=30)  # 30 second timeout
                
            log.info("Successfully sent WhatsApp message", message_id=message_id)
            return message_id
            
        except WhatsAppError as e:
            log.error("Failed to send WhatsApp message (sync wrapper)", error=str(e))
            return None
        except concurrent.futures.TimeoutError:
            log.error("WhatsApp message sending timed out")
            return None
        except Exception as e:
            log.error("An unexpected error occurred in the sync wrapper", error=str(e), exc_info=True)
            return None

    def shutdown(self):
        """
        A shutdown method for compatibility. The new implementation doesn't
        maintain persistent loops, but we can still close the underlying
        async client's session if needed.
        """
        try:
            # Create a temporary loop just for cleanup
            def cleanup_async_service():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.async_service.close())
                finally:
                    loop.close()
            
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(cleanup_async_service)
                future.result(timeout=10)
                
            logger.info("Sync WhatsApp Service has been shut down.")
        except Exception as e:
            logger.error("Error during sync shutdown", error=str(e))


# Alternative simpler implementation using asyncio.run (Python 3.7+)
class SimpleWhatsAppService:
    """
    A simpler synchronous wrapper that uses asyncio.run().
    This is cleaner but may have different behavior in some environments.
    """
    def __init__(self):
        self.async_service = async_whatsapp_service
        logger.info("Simple Sync WhatsApp Service initialized.")

    def send_message(self, to: str, message: str) -> Optional[str]:
        """
        Sends a WhatsApp message using asyncio.run() which creates
        a new event loop each time.
        """
        log = logger.bind(recipient=to)
        
        try:
            log.info("Dispatching synchronous send_message using asyncio.run.")
            
            # Use asyncio.run which handles loop creation and cleanup
            message_id = asyncio.run(self.async_service.send_message(to, message))
            
            log.info("Successfully sent WhatsApp message", message_id=message_id)
            return message_id
            
        except WhatsAppError as e:
            log.error("Failed to send WhatsApp message (simple sync wrapper)", error=str(e))
            return None
        except Exception as e:
            log.error("An unexpected error occurred in the simple sync wrapper", error=str(e), exc_info=True)
            return None

    def shutdown(self):
        """Cleanup method."""
        try:
            asyncio.run(self.async_service.close())
            logger.info("Simple Sync WhatsApp Service has been shut down.")
        except Exception as e:
            logger.error("Error during simple sync shutdown", error=str(e))


# Use the thread-based implementation for better Celery compatibility
whatsapp_service = WhatsAppService()

# Alternative: Use the simpler implementation if the above doesn't work
# whatsapp_service = SimpleWhatsAppService()

# Ensure cleanup on application exit
import atexit
atexit.register(whatsapp_service.shutdown)