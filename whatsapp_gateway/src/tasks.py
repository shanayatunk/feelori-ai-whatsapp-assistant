# whatsapp_gateway/src/tasks.py (Production-Ready Version with Fixed Event Loop Handling)

import os
import logging
import time
from typing import Optional, Dict, Any
from uuid import UUID
import hashlib
import json

import httpx
import asyncio
from functools import wraps
from celery import Celery
from celery.exceptions import Retry, MaxRetriesExceededError
from redis.exceptions import RedisError

# --- CORRECTED CONFIGURATION ---
# Import the central settings object
from shared.config import settings

# Structured logging with correlation support
import structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger(__name__).bind(
    service="whatsapp_gateway",
    version="1.0.0"
)

# --- CONFIGURATION ---
AI_SERVICE_URL = settings.AI_SERVICE_URL
# Timeout configurations
AI_SERVICE_TIMEOUT = settings.AI_SERVICE_TIMEOUT
TASK_DUPLICATE_TTL = 300  # 5 minutes
MAX_MESSAGE_LENGTH = settings.MAX_MESSAGE_LENGTH

# Validate required configuration
if not AI_SERVICE_URL:
    raise ValueError("AI_SERVICE_URL environment variable is required")

# --- CELERY APP INITIALIZATION ---
celery_app = Celery(
    'whatsapp_gateway_tasks',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    # Serialization
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    
    # Timezone
    timezone='UTC',
    enable_utc=True,
    
    # Connection and reliability
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    
    # Task execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # Important for long-running tasks
    
    # Results
    result_expires=3600,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Error handling
    task_soft_time_limit=120,  # Soft limit before SIGTERM
    task_time_limit=150,      # Hard limit before SIGKILL
)

class TaskError(Exception):
    """Base exception for non-retryable task-related errors."""
    pass

class AIServiceError(Exception):
    """Exception for AI service errors that should be retried."""
    pass

class WhatsAppServiceError(TaskError):
    """Exception for WhatsApp service errors that should not be retried."""
    pass

def validate_task_inputs(customer_phone: str, message: str, conversation_id: str, correlation_id: str) -> None:
    """Validate task input parameters."""
    if not customer_phone or not isinstance(customer_phone, str):
        raise ValueError("Invalid customer_phone parameter")
    
    if not message or not isinstance(message, str):
        raise ValueError("Invalid message parameter")
        
    if len(message) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH}")
    
    if not conversation_id:
        raise ValueError("conversation_id is required")
        
    try:
        UUID(conversation_id)
    except ValueError:
        raise ValueError(f"Invalid conversation_id format: {conversation_id}")
    
    if not correlation_id:
        raise ValueError("correlation_id is required")

def generate_task_key(conversation_id: str, message: str) -> str:
    """Generate a unique key for task deduplication."""
    message_hash = hashlib.sha256(message.encode()).hexdigest()[:16]
    return f"task:{conversation_id}:{message_hash}"

def run_in_new_loop(coro):
    """
    Runs a coroutine safely in a managed asyncio event loop.
    This is essential for calling async code from a synchronous context like Celery.
    """
    return asyncio.run(coro)

def check_and_set_task_lock(redis_client, task_key: str) -> bool:
    """
    Atomically check and set task lock to prevent duplicate processing.
    Returns True if lock was acquired, False if already exists.
    """
    try:
        # Use SET NX EX for atomic operation
        result = redis_client.set(task_key, "processing", nx=True, ex=TASK_DUPLICATE_TTL)
        return result is not None
    except RedisError as e:
        logger.warning("Redis error during task lock check", error=str(e))
        # Fail open - allow processing if Redis is unavailable
        return True

def cleanup_task_lock(redis_client, task_key: str) -> None:
    """Clean up task lock."""
    try:
        redis_client.delete(task_key)
    except RedisError as e:
        logger.warning("Failed to cleanup task lock", task_key=task_key, error=str(e))

@celery_app.task(
    name='process_and_reply_task',
    bind=True,
    autoretry_for=(httpx.RequestError, httpx.TimeoutException, AIServiceError),
    retry_backoff=2,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5
)
def process_and_reply_task(
    self,
    customer_phone: str,
    message: str,
    conversation_id: str,
    correlation_id: str,
    platform: str = 'whatsapp',
    source_language: str = 'en'
) -> Dict[str, Any]:
    """
    Process incoming message with AI service and send reply via WhatsApp.
    """
    start_time = time.time()
    
    # Bind context for structured logging
    structlog.contextvars.bind_contextvars(
        correlation_id=correlation_id,
        task_id=self.request.id,
        conversation_id=conversation_id,
        customer_phone=customer_phone[:6] + "****"  # Mask for privacy
    )
    
    task_logger = logger.bind(
        retry_count=self.request.retries,
        max_retries=self.max_retries
    )
    
    task_logger.info("Starting message processing task")
    
    try:
        # Import the correct WhatsApp service class and redis client
        from src.services.whatsapp_service_sync import WhatsAppService
        from shared.cache import redis_client
    except ImportError as e:
        task_logger.error("Failed to import required services", error=str(e))
        raise TaskError(f"Service import failed: {e}")
    
    try:
        validate_task_inputs(customer_phone, message, conversation_id, correlation_id)
    except ValueError as e:
        task_logger.error("Invalid task inputs", error=str(e))
        # Do not retry on validation errors
        raise TaskError(f"Input validation failed: {e}")
    
    task_key = generate_task_key(conversation_id, message)
    
    if not check_and_set_task_lock(redis_client, task_key):
        task_logger.info("Duplicate task detected, skipping processing", task_key=task_key)
        return {
            'status': 'skipped',
            'reason': 'duplicate_task',
            'processing_time': time.time() - start_time
        }
    
    try:
        ai_response = call_ai_service(
            conversation_id, message, platform, source_language, 
            correlation_id, task_logger
        )
        
        # Send the WhatsApp message using the imported service class
        send_whatsapp_message(customer_phone, ai_response, task_logger, WhatsAppService)
        
        duration = time.time() - start_time
        task_logger.info(
            "Task completed successfully",
            processing_time=round(duration, 2)
        )
        
        return {
            'status': 'success',
            'processing_time': duration,
        }
        
    except (TaskError, WhatsAppServiceError) as exc:
        # Non-retryable errors
        task_logger.error(
            "Task failed permanently (non-retryable)",
            error=str(exc),
            error_type=type(exc).__name__
        )
        raise # Celery will mark the task as FAILED
    except Exception as exc:
        # This block will catch retryable errors defined in `autoretry_for`
        # and any other unexpected exceptions.
        task_logger.error(
            "Task failed, will be retried if applicable",
            error=str(exc),
            error_type=type(exc).__name__,
            exc_info=True
        )
        # Re-raise the exception. Celery's `autoretry_for` will catch it
        # and schedule a retry. Other exceptions will cause a task failure.
        raise
        
    finally:
        cleanup_task_lock(redis_client, task_key)

def call_ai_service(
    conversation_id: str, 
    message: str, 
    platform: str, 
    source_language: str,
    correlation_id: str,
    task_logger
) -> str:
    """
    Call the AI service to process the message.
    """
    ai_endpoint = f"{AI_SERVICE_URL.rstrip('/')}/ai/v1/process"
    
    payload = {
        "conv_id": conversation_id,
        "message": message,
        "platform": platform,
        "lang": source_language
    }
    
    headers = {
        'X-Correlation-ID': correlation_id,
        'X-API-Key': settings.INTERNAL_API_KEY.get_secret_value(),
        'Content-Type': 'application/json',
        'User-Agent': 'WhatsApp-Gateway/1.0.0'
    }
    
    task_logger.debug("Calling AI service", endpoint=ai_endpoint)
    
    try:
        with httpx.Client(timeout=httpx.Timeout(AI_SERVICE_TIMEOUT)) as client:
            response = client.post(ai_endpoint, json=payload, headers=headers)
            response.raise_for_status()
        
        ai_response_data = response.json()
        ai_text_reply = ai_response_data.get('response')
        
        if not ai_text_reply:
            raise TaskError("Empty response from AI service")
            
        task_logger.debug("AI service response received successfully")
        return ai_text_reply
        
    except httpx.HTTPStatusError as e:
        error_detail = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        task_logger.error("AI service HTTP error", detail=error_detail)
        
        # Retry on server errors (5xx)
        if 500 <= e.response.status_code < 600:
            raise AIServiceError(f"AI service server error: {error_detail}")
        else:
            # Do not retry on client errors (4xx)
            raise TaskError(f"AI service client error: {error_detail}")
            
    except (httpx.RequestError, httpx.TimeoutException) as e:
        task_logger.error("AI service connection error", error=str(e))
        raise AIServiceError(f"AI service connection failed: {e}")
        
    except (json.JSONDecodeError, KeyError) as e:
        task_logger.error("AI service response parsing error", error=str(e))
        raise TaskError(f"Invalid AI service response: {e}")

def send_whatsapp_message(customer_phone: str, message_content: str, task_logger, whatsapp_service_class) -> None:
    """
    Sends a message using the synchronous wrapper for the WhatsApp service.
    This version correctly manages its own asyncio event loop to prevent errors
    during Celery retries.
    """
    try:
        task_logger.info("Dispatching synchronous send_message to a new event loop.", recipient=customer_phone)

        def send_sync() -> Optional[str]:
            """Wrapper function to instantiate and call the sync service."""
            service = whatsapp_service_class()
            # This is a synchronous call
            return service.send_message(customer_phone, message_content)

        # Use asyncio.to_thread to run the blocking sync function in a separate thread,
        # managed by a new event loop created by run_in_new_loop.
        # This prevents the "Event loop is closed" error on Celery retries.
        message_id = run_in_new_loop(asyncio.to_thread(send_sync))

        if not message_id:
            raise WhatsAppServiceError("WhatsApp service returned None, indicating a failure to send.")

        task_logger.info(
            "Successfully dispatched message to WhatsApp service",
            recipient=customer_phone,
            message_id=message_id
        )
        
    except WhatsAppServiceError as e:
        # Re-raise known, non-retryable WhatsApp errors
        task_logger.error("A known WhatsApp service error occurred.", error=str(e))
        raise
    except Exception as e:
        # Catch any other unexpected errors during the process
        task_logger.error(
            "An unexpected error occurred while trying to send WhatsApp message",
            error=str(e),
            exc_info=True
        )
        # Wrap the unexpected error in our non-retryable error type
        raise WhatsAppServiceError(f"Unexpected error during WhatsApp sending: {e}")

# Health check task for monitoring
@celery_app.task(name='health_check_task')
def health_check_task() -> Dict[str, Any]:
    """Health check task for monitoring worker status."""
    return {'status': 'healthy', 'timestamp': time.time()}