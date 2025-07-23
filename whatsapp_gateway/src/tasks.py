# whatsapp_gateway/src/tasks.py (Production-Ready Version with Simplified Retry)

import os
import logging
import time
from typing import Optional, Dict, Any
from uuid import UUID
import hashlib
import json

import httpx
from celery import Celery
from celery.exceptions import Retry, MaxRetriesExceededError
from redis.exceptions import RedisError

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
AI_SERVICE_URL = os.getenv('AI_SERVICE_URL')
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')

# Timeout configurations
AI_SERVICE_TIMEOUT = int(os.getenv('AI_SERVICE_TIMEOUT', '90'))
TASK_DUPLICATE_TTL = int(os.getenv('TASK_DUPLICATE_TTL', '300'))  # 5 minutes
MAX_MESSAGE_LENGTH = int(os.getenv('MAX_MESSAGE_LENGTH', '4096'))

# Validate required configuration
if not AI_SERVICE_URL:
    raise ValueError("AI_SERVICE_URL environment variable is required")

# --- CELERY APP INITIALIZATION ---
celery_app = Celery(
    'whatsapp_gateway_tasks',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
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
    retry_backoff=True,
    retry_backoff_max=300,  # Max 5 minutes
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
        from src.services.whatsapp_service_sync import WhatsAppService
        from src.services.cache import redis_client
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
        
        send_whatsapp_message(customer_phone, ai_response, task_logger)
        
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
    ai_endpoint = f"{AI_SERVICE_URL.rstrip('/')}/ai/process"
    
    payload = {
        "conv_id": conversation_id,
        "message": message,
        "platform": platform,
        "lang": source_language
    }
    
    headers = {
        'X-Correlation-ID': correlation_id,
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
        
    except (ValueError, KeyError) as e:
        task_logger.error("AI service response parsing error", error=str(e))
        raise TaskError(f"Invalid AI service response: {e}")

def send_whatsapp_message(customer_phone: str, message: str, task_logger) -> None:
    """
    Send message via WhatsApp service.
    """
    from src.services.whatsapp_service_sync import WhatsAppService
    try:
        whatsapp_service = WhatsAppService()
        success = whatsapp_service.send_message(customer_phone, message)
        
        if not success:
            raise WhatsAppServiceError("WhatsApp service returned failure on send")
            
        task_logger.info("WhatsApp message sent successfully")
        
    except Exception as e:
        task_logger.error("Failed to send WhatsApp message", error=str(e))
        raise WhatsAppServiceError(f"WhatsApp sending failed: {e}")

# Health check task for monitoring
@celery_app.task(name='health_check_task')
def health_check_task() -> Dict[str, Any]:
    """Health check task for monitoring worker status."""
    return {'status': 'healthy', 'timestamp': time.time()}