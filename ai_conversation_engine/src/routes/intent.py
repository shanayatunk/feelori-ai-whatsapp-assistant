# ai_conversation_engine/src/routes/intent.py

import logging
import re
from typing import Optional, Dict, Any

from quart import Blueprint, request, jsonify, current_app
from pydantic import BaseModel, Field, ValidationError, validator

from src.auth import require_api_key
from src.services.rate_limiter import RateLimiter
from src.config import settings

logger = logging.getLogger(__name__)
intent_bp = Blueprint('intent', __name__, url_prefix='/ai/v1')

# --- Constants ---

MAX_MESSAGE_LENGTH = 4096
MIN_MESSAGE_LENGTH = 1
INTENT_RATE_LIMIT_MULTIPLIER = getattr(settings, 'INTENT_RATE_LIMIT_MULTIPLIER', 2)

# --- Pydantic Models ---

class IntentRequest(BaseModel):
    """Request model for intent analysis."""
    message: str = Field(
        ..., 
        min_length=MIN_MESSAGE_LENGTH, 
        max_length=MAX_MESSAGE_LENGTH,
        description="The message to analyze for intent"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional context information for better intent analysis"
    )

    @validator('message')
    def sanitize_message(cls, v):
        """Sanitize message input to prevent potential security issues."""
        if not v or not v.strip():
            raise ValueError("Message cannot be empty or whitespace only")
        
        # Remove potentially dangerous HTML/script tags
        v = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', v, flags=re.IGNORECASE)
        v = re.sub(r'<[^>]+>', '', v)  # Remove all HTML tags
        
        # Limit consecutive whitespace
        v = re.sub(r'\s+', ' ', v.strip())
        
        return v

    @validator('context')
    def validate_context(cls, v):
        """Validate context data."""
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError("Context must be a dictionary")
            
            # Limit context size to prevent abuse
            if len(str(v)) > 1024:  # 1KB limit for context
                raise ValueError("Context data too large")
                
        return v

class IntentResponse(BaseModel):
    """Response model for intent analysis."""
    intent: str = Field(..., description="The identified intent")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Extracted entities from the message")
    processing_time_ms: Optional[float] = Field(default=None, description="Processing time in milliseconds")

# --- Rate Limiter ---

rate_limiter = RateLimiter(
    max_requests=settings.RATE_LIMIT_REQUESTS * INTENT_RATE_LIMIT_MULTIPLIER,
    window_seconds=settings.RATE_LIMIT_WINDOW
)

# --- Helper Functions ---

def log_request_info(endpoint: str, success: bool, processing_time: float = None):
    """Log request information for monitoring and debugging."""
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', 'Unknown')
    
    log_data = {
        'endpoint': endpoint,
        'method': request.method,
        'client_ip': client_ip,
        'user_agent': user_agent,
        'success': success
    }
    
    if processing_time is not None:
        log_data['processing_time_ms'] = processing_time
    
    if success:
        logger.info(f"Intent analysis request completed: {log_data}")
    else:
        logger.error(f"Intent analysis request failed: {log_data}")

# --- Endpoints ---

@intent_bp.route('/intent/analyze', methods=['POST'])
@rate_limiter.limit()  # Apply rate limiting before auth for better security
@require_api_key
async def analyze_message_intent():
    """
    Analyzes the intent of a user message using AI models.
    
    This endpoint accepts a message and optional context, then uses the application's
    intent analyzer to determine the user's intent, confidence level, and extract
    relevant entities.
    
    Returns:
        JSON response containing intent, confidence score, and extracted entities
        
    Raises:
        400: Validation error in request data
        429: Rate limit exceeded
        500: Internal server error during processing
    """
    import time
    start_time = time.time()
    
    try:
        # Get and validate request data
        json_data = await request.get_json()
        if not json_data:
            log_request_info('/intent/analyze', False)
            return jsonify({
                "error": "invalid_request", 
                "message": "Request body must contain valid JSON data"
            }), 400
            
        # Validate request using Pydantic model
        try:
            data = IntentRequest.model_validate(json_data)
        except ValidationError as ve:
            log_request_info('/intent/analyze', False)
            return jsonify({
                "error": "validation_error", 
                "message": "Invalid request data",
                "details": ve.errors()
            }), 400
        
        # Check if intent analyzer is available
        if not hasattr(current_app, 'intent_analyzer') or current_app.intent_analyzer is None:
            logger.error("Intent analyzer not initialized in application")
            log_request_info('/intent/analyze', False)
            return jsonify({
                "error": "service_unavailable", 
                "message": "Intent analysis service is currently unavailable"
            }), 503
        
        # Perform intent analysis
        intent_analyzer = current_app.intent_analyzer
        intent_result = await intent_analyzer.analyze(data.message, data.context)
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Format and return the response
        response_data = IntentResponse(
            intent=intent_result.intent.value,
            confidence=intent_result.confidence,
            entities=intent_result.entities,
            processing_time_ms=round(processing_time, 2)
        )
        
        log_request_info('/intent/analyze', True, processing_time)
        return jsonify(response_data.model_dump()), 200

    except ValidationError as ve:
        log_request_info('/intent/analyze', False)
        return jsonify({
            "error": "validation_error", 
            "message": "Request validation failed",
            "details": ve.errors()
        }), 400
        
    except AttributeError as ae:
        logger.error(f"Intent analyzer method missing: {ae}", exc_info=True)
        log_request_info('/intent/analyze', False)
        return jsonify({
            "error": "service_error", 
            "message": "Intent analysis service configuration error"
        }), 500
        
    except Exception as e:
        logger.error(f"Intent analysis failed: {e}", exc_info=True)
        log_request_info('/intent/analyze', False)
        return jsonify({
            "error": "internal_server_error", 
            "message": "An unexpected error occurred during intent analysis"
        }), 500

@intent_bp.route('/intent/health', methods=['GET'])
async def health_check():
    """
    Health check endpoint for the intent analysis service.
    
    Returns:
        JSON response indicating service health status
    """
    try:
        # Check if intent analyzer is properly initialized
        analyzer_available = (
            hasattr(current_app, 'intent_analyzer') and 
            current_app.intent_analyzer is not None
        )
        
        status = "healthy" if analyzer_available else "unhealthy"
        status_code = 200 if analyzer_available else 503
        
        response_data = {
            "status": status,
            "service": "intent_analysis",
            "analyzer_available": analyzer_available,
            "timestamp": time.time()
        }
        
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return jsonify({
            "status": "unhealthy",
            "service": "intent_analysis", 
            "error": str(e),
            "timestamp": time.time()
        }), 500