# ai_conversation_engine/src/routes/knowledge.py

import logging
from quart import Blueprint, jsonify, request
from src.utils.rate_limiter import RateLimiter
from src.config import settings

logger = logging.getLogger(__name__)
knowledge_bp = Blueprint('knowledge', __name__, url_prefix='/ai/v1')

# Rate limiter for deprecated endpoint (lower limits)
rate_limiter = RateLimiter(
    max_requests=settings.RATE_LIMIT_REQUESTS // 4,  # Much lower limit for deprecated endpoint
    window_seconds=settings.RATE_LIMIT_WINDOW
)

@knowledge_bp.route('/knowledge', methods=['GET', 'POST', 'PUT', 'DELETE'])
@knowledge_bp.route('/knowledge/', methods=['GET', 'POST', 'PUT', 'DELETE'])
@knowledge_bp.route('/knowledge/<path:u_path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@rate_limiter.limit()
async def knowledge_routes(u_path: str = ""):
    """
    Handles all requests to the deprecated /knowledge endpoint.
    This functionality has been migrated to the core conversation processing.
    
    Args:
        u_path: The path component after /knowledge/
        
    Returns:
        JSON response with deprecation notice and migration guidance
    """
    # Log deprecated endpoint usage for monitoring
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', 'Unknown')
    
    logger.warning(
        f"Deprecated /knowledge endpoint accessed: path='{u_path}', "
        f"method={request.method}, ip={client_ip}, user_agent={user_agent}"
    )
    
    response_data = {
        "error": "endpoint_deprecated",
        "message": "The /knowledge endpoint is deprecated and no longer available.",
        "migration": {
            "new_endpoint": "/ai/v1/process",
            "description": "Knowledge base interactions are now handled through the main conversation endpoint.",
            "documentation": "https://docs.example.com/api/v1/migration-guide"
        },
        "deprecated_since": "2024-01-15",
        "removal_date": "2024-06-01"
    }
    
    # Add CORS headers for web clients
    response = jsonify(response_data)
    response.status_code = 410  # Gone - resource permanently unavailable
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    
    return response

@knowledge_bp.route('/knowledge', methods=['OPTIONS'])
@knowledge_bp.route('/knowledge/', methods=['OPTIONS'])
@knowledge_bp.route('/knowledge/<path:u_path>', methods=['OPTIONS'])
async def knowledge_options(u_path: str = ""):
    """Handle CORS preflight requests for deprecated endpoint."""
    response = jsonify({})
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Max-Age'] = '3600'
    return response