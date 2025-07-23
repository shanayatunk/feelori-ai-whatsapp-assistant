# ai_conversation_engine/src/routes/conversation.py

import logging
import uuid
from quart import Blueprint, request, jsonify, current_app, abort
from pydantic import BaseModel, Field, ValidationError
from src.auth import require_api_key
from src.services.rate_limiter import RateLimiter
from src.config import settings
from src.exceptions import InvalidInputError, RateLimitExceededError, CircuitBreakerOpenError
from opentelemetry import trace
from prometheus_client import Counter

logger = logging.getLogger(__name__)
conversation_bp = Blueprint('conversation', __name__, url_prefix='/ai/v1')
tracer = trace.get_tracer(__name__)
USER_SATISFACTION = Counter('user_satisfaction', 'User satisfaction ratings', ['rating'])

class MessageRequest(BaseModel):
    """
    Pydantic model for validating conversation request payloads.
    """
    conv_id: str = Field(..., regex=r'^[a-zA-Z0-9]{8,100}$')
    message: str = Field(..., min_length=1, max_length=4096)
    platform: str = Field(default="web", regex=r'^[a-zA-Z0-9]{1,50}$')
    lang: str = Field(default="en", regex=r'^[a-z]{2}$')
    csrf_token: str = Field(..., min_length=32)

rate_limiter = RateLimiter(
    max_requests=settings.RATE_LIMIT_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW
)

def verify_csrf_token(token: str, conv_id: str) -> bool:
    """
    Verifies CSRF token against stored session token.

    Args:
        token: The provided CSRF token.
        conv_id: The conversation ID.

    Returns:
        bool: True if valid, False otherwise.
    """
    client = current_app.conversation_manager.redis_client
    if client:
        stored_token = client.get(f"csrf:{conv_id}")
        return stored_token == token
    return False

@conversation_bp.route('/generate_csrf', methods=['GET'])
@require_api_key
async def generate_csrf():
    """
    Generates a CSRF token for a conversation.
    
    Returns:
        JSON response with the CSRF token or error message.
    """
    with tracer.start_as_current_span("generate_csrf"):
        conv_id = request.args.get('conv_id')
        if not conv_id or not bool(re.match(r'^[a-zA-Z0-9]{8,100}$', conv_id)):
            return jsonify({"error": "Invalid conversation ID"}), 400
        token = str(uuid.uuid4())
        client = current_app.conversation_manager.redis_client
        if client:
            client.setex(f"csrf:{conv_id}", settings.CONVERSATION_TTL_SECONDS, token)
        return jsonify({"csrf_token": token})

@conversation_bp.route('/process', methods=['POST'])
@require_api_key
@rate_limiter.limit()
async def process_conversation():
    """
    Main endpoint to process a user's message asynchronously.
    
    Returns:
        JSON response with the AI response or error message.
    """
    with tracer.start_as_current_span("process_conversation") as span:
        ai_processor = current_app.ai_processor
        try:
            data = await request.get_json()
            if not data:
                raise InvalidInputError("Invalid or missing JSON payload")
            
            try:
                validated_data = MessageRequest(**data)
            except ValidationError:
                raise InvalidInputError("Invalid input data provided.")

            span.set_attribute("conv_id", validated_data.conv_id)
            if not verify_csrf_token(validated_data.csrf_token, validated_data.conv_id):
                logger.warning(f"Invalid CSRF token for conv_id {validated_data.conv_id}")
                return jsonify({"error": "Invalid CSRF token"}), 403

            response_text = await ai_processor.process_message(
                message=validated_data.message,
                conv_id=validated_data.conv_id,
                platform=validated_data.platform,
                lang=validated_data.lang
            )
            
            return jsonify({"response": response_text})

        except InvalidInputError as e:
            span.record_exception(e)
            return jsonify({"error": str(e)}), 400
        except RateLimitExceededError as e:
            span.record_exception(e)
            response = jsonify({"error": str(e)})
            response.headers["Retry-After"] = str(e.retry_after)
            return response, 429
        except CircuitBreakerOpenError:
            span.record_exception(CircuitBreakerOpenError())
            return jsonify({"error": "Service temporarily unavailable. Please try again later."}), 503
        except Exception as e:
            span.record_exception(e)
            logger.error(f"Unexpected error processing conversation: {e}", exc_info=True)
            return jsonify({"error": "An internal server error occurred."}), 500

@conversation_bp.route('/health', methods=['GET'])
async def health_check():
    """
    Enhanced health check including Redis and circuit breaker status.
    
    Returns:
        JSON response with health status of components.
    """
    with tracer.start_as_current_span("health_check"):
        status = {"status": "healthy", "components": {}}
        ai_processor = current_app.ai_processor
        conversation_manager = current_app.conversation_manager
        
        # Check HTTP client
        status["components"]["http_client"] = not ai_processor.http_client.is_closed if ai_processor.http_client else False
        
        # Check Redis
        redis_ok = False
        if conversation_manager.redis_client:
            try:
                conversation_manager.redis_client.ping()
                redis_ok = True
            except redis.RedisError:
                pass
        status["components"]["redis"] = redis_ok
        
        # Check circuit breakers
        status["components"]["llm_circuit_breaker"] = ai_processor.llm_circuit_breaker.state.value
        status["components"]["ecommerce_circuit_breaker"] = ai_processor.ecommerce_circuit_breaker.state.value
        
        if not all(status["components"].values()) or any(s == "OPEN" for s in status["components"].values()):
            status["status"] = "unhealthy"
        
        return jsonify(status), 200 if status["status"] == "healthy" else 503

@conversation_bp.route('/feedback', methods=['POST'])
@require_api_key
async def submit_feedback():
    """
    Endpoint to collect user satisfaction feedback.
    
    Returns:
        JSON response indicating success or error.
    """
    with tracer.start_as_current_span("submit_feedback"):
        try:
            data = await request.get_json()
            if not data or 'rating' not in data or 'conv_id' not in data:
                raise InvalidInputError("Missing rating or conversation ID")
            
            rating = data['rating']
            conv_id = data['conv_id']
            if not isinstance(rating, int) or rating < 1 or rating > 5:
                raise InvalidInputError("Rating must be an integer between 1 and 5")
            if not bool(re.match(r'^[a-zA-Z0-9]{8,100}$', conv_id)):
                raise InvalidInputError("Invalid conversation ID")
            
            USER_SATISFACTION.labels(rating=str(rating)).inc()
            logger.info("Received user feedback", conv_id=conv_id, rating=rating)
            return jsonify({"status": "success"})

        except InvalidInputError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error(f"Error processing feedback: {e}", exc_info=True)
            return jsonify({"error": "An internal server error occurred."}), 500