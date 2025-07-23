# ai_conversation_engine/src/auth.py

import os
import secrets
from functools import wraps
from quart import request, jsonify

from src.config import settings

def validate_api_key(provided_key: str) -> bool:
    """✅ FIX: Constant-time comparison to prevent timing attacks."""
    expected_key = settings.INTERNAL_API_KEY
    if not expected_key or not provided_key:
        return False
    return secrets.compare_digest(provided_key, expected_key)

def require_api_key(f):
    """Decorator to protect routes with a simple API key."""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        if not settings.INTERNAL_API_KEY:
            return jsonify({"error": "Service is not configured for authentication."}), 500

        provided_key = request.headers.get('X-API-Key')
        if not validate_api_key(provided_key):
            return jsonify({"error": "Unauthorized: Invalid or missing API Key."}), 401
        
        return await f(*args, **kwargs)
    return decorated_function