# ai_conversation_engine/src/routes/conversation.py

import logging
import uuid
import time
import asyncio
import structlog
from functools import wraps

from quart import Blueprint, request, jsonify, current_app
from pydantic import BaseModel, Field, ValidationError

# --- Local Imports ---
from src.auth import require_api_key
from shared.config import settings
from shared.exceptions import CircuitBreakerOpenError
from src.utils.rate_limiter import RateLimiter
from src.services.sanitizer import InputSanitizer

# --- Observability ---
from opentelemetry import trace
from prometheus_client import Counter, Histogram

# --- Setup ---
logger = structlog.get_logger(__name__)
conversation_bp = Blueprint('conversation', __name__, url_prefix='/ai/v1')
tracer = trace.get_tracer(__name__)

# --- Metrics ---
API_ERRORS = Counter('api_errors_total', 'Total API errors by type and endpoint', ['endpoint', 'error_type'])
REQUEST_DURATION = Histogram('request_duration_seconds', 'Request duration by endpoint', ['endpoint'])
USER_SATISFACTION = Counter('user_satisfaction_ratings_total', 'User satisfaction ratings', ['rating'])

# --- Custom Exceptions ---
class ServiceUnavailableError(Exception):
    """Raised when a critical service is unavailable."""
    pass

# --- Pydantic Models ---
class MessageRequest(BaseModel):
    conv_id: str = Field(..., min_length=8, max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')
    message: str = Field(..., min_length=1, max_length=4096)
    platform: str = Field(default="web", min_length=2, max_length=50)
    lang: str = Field(default="en", min_length=2, max_length=5)
    user_id: str | None = None

class FeedbackRequest(BaseModel):
    conv_id: str = Field(..., min_length=8, max_length=100)
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(None, max_length=1024)

class APIResponse(BaseModel):
    response: str | dict
    status: str = "success"
    timestamp: int = Field(default_factory=lambda: int(time.time()))

class ErrorResponse(BaseModel):
    error: str
    message: str
    timestamp: int = Field(default_factory=lambda: int(time.time()))

# --- Rate Limiter ---
rate_limiter = RateLimiter(
    max_requests=settings.RATE_LIMIT_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW
)

# --- API Endpoints ---
@conversation_bp.route('/session/init', methods=['POST'])
@require_api_key
async def init_session():
    """Initializes a secure session."""
    with tracer.start_as_current_span("init_session"), REQUEST_DURATION.labels('init_session').time():
        try:
            conv_id = str(uuid.uuid4())
            response_data = {"conv_id": conv_id, "status": "initialized"}
            return jsonify(response_data), 200
        except Exception:
            logger.error("Failed to initialize session", exc_info=True)
            API_ERRORS.labels(endpoint='init_session', error_type='internal_error').inc()
            error_resp = ErrorResponse(error="service_unavailable", message="Could not initialize session.")
            return jsonify(error_resp.model_dump()), 503

@conversation_bp.route('/process', methods=['POST'])
@require_api_key
@rate_limiter.limit()
async def process_conversation():
    """Main endpoint to process a user's message."""
    with tracer.start_as_current_span("process_conversation"), REQUEST_DURATION.labels('process').time():
        try:
            json_data = await request.get_json()
            validated_data = MessageRequest.model_validate(json_data)

            sanitized_message = InputSanitizer.sanitize(validated_data.message, strict_mode=True)
            if not sanitized_message:
                raise ValidationError.from_exception_data("Message is empty after sanitization.", [])

            ai_processor = current_app.ai_processor
            result = await ai_processor.process_message(
                message=sanitized_message,
                conv_id=validated_data.conv_id,
                platform=validated_data.platform,
                lang=validated_data.lang,
                user_id=validated_data.user_id
            )

            if result.error:
                # Log the specific error returned by the processor
                logger.warning(
                    "AI processor returned an error", 
                    error_type=result.error, 
                    response_message=result.response,
                    conv_id=validated_data.conv_id
                )
                
                # If the processor already determined the service is unavailable, respond with 503
                if result.error == "service_unavailable":
                    error_resp = ErrorResponse(error="service_unavailable", message=result.response)
                    return jsonify(error_resp.model_dump()), 503
                
                # For any other processor error, treat it as an internal server error
                error_resp = ErrorResponse(error="internal_server_error", message=result.response)
                return jsonify(error_resp.model_dump()), 500

            api_response = APIResponse(response=result.response)
            return jsonify(api_response.model_dump()), 200

        except ValidationError as e:
            API_ERRORS.labels(endpoint='process', error_type='validation_error').inc()
            error_resp = ErrorResponse(error="bad_request", message=str(e))
            return jsonify(error_resp.model_dump()), 400
        except CircuitBreakerOpenError as e:
            API_ERRORS.labels(endpoint='process', error_type='circuit_breaker').inc()
            error_resp = ErrorResponse(error="service_unavailable", message=str(e))
            return jsonify(error_resp.model_dump()), 503
        except Exception:
            API_ERRORS.labels(endpoint='process', error_type='internal_error').inc()
            logger.error("Unexpected error in /process", exc_info=True)
            error_resp = ErrorResponse(error="internal_server_error", message="An unexpected error occurred.")
            return jsonify(error_resp.model_dump()), 500

@conversation_bp.route('/feedback', methods=['POST'])
@require_api_key
async def submit_feedback():
    """Endpoint to collect user satisfaction feedback."""
    with tracer.start_as_current_span("submit_feedback"), REQUEST_DURATION.labels('feedback').time():
        try:
            validated_data = FeedbackRequest.model_validate(await request.get_json())

            USER_SATISFACTION.labels(rating=str(validated_data.rating)).inc()

            _ = InputSanitizer.sanitize(validated_data.comment) if validated_data.comment else None

            logger.info(
                "User feedback received",
                extra={"conv_id": validated_data.conv_id, "rating": validated_data.rating}
            )

            return jsonify({"status": "success", "message": "Thank you for your feedback!"}), 200

        except ValidationError as e:
            API_ERRORS.labels(endpoint='feedback', error_type='validation_error').inc()
            error_resp = ErrorResponse(error="bad_request", message=str(e))
            return jsonify(error_resp.model_dump()), 400
        except Exception:
            API_ERRORS.labels(endpoint='feedback', error_type='internal_error').inc()
            logger.error("Error processing feedback", exc_info=True)
            error_resp = ErrorResponse(error="internal_server_error", message="Could not process feedback.")
            return jsonify(error_resp.model_dump()), 500

@conversation_bp.route('/health', methods=['GET'])
async def health_check():
    """Enhanced health check for all critical application components."""
    with tracer.start_as_current_span("health_check"), REQUEST_DURATION.labels('health').time():
        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    current_app.ai_processor.health_check(),
                    current_app.conversation_manager.health_check(),
                    return_exceptions=True
                ),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            return jsonify({"status": "unhealthy", "message": "Health check timed out."}), 503

        processor_health, conversation_health = results

        health_status = {
            "status": "healthy",
            "timestamp": int(time.time()),
            "dependencies": {
                "ai_processor": processor_health if isinstance(processor_health, dict) else {"status": "unhealthy", "error": str(processor_health)},
                "conversation_manager": conversation_health if isinstance(conversation_health, dict) else {"status": "unhealthy", "error": str(conversation_health)},
            }
        }

        if any(dep.get("status") == "unhealthy" for dep in health_status["dependencies"].values()):
            health_status["status"] = "unhealthy"
            return jsonify(health_status), 503

        return jsonify(health_status), 200