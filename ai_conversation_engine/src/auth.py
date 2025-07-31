# ai_conversation_engine/src/auth.py

import secrets
from functools import wraps
from quart import request, jsonify

from shared.config import settings # Import the central settings

def require_api_key(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        provided_key = request.headers.get('X-API-Key')
        if not provided_key or not validate_api_key(provided_key):
            return jsonify({'error': 'Unauthorized: Invalid or missing API key'}), 401
        return await f(*args, **kwargs)
    return decorated_function

def validate_api_key(key: str) -> bool:
    """
    Validates the provided API key against the expected key using a
    constant-time comparison to prevent timing attacks.
    """
    expected_key = settings.INTERNAL_API_KEY
    if not expected_key:
        # Fail securely if the key is not configured on the server
        return False

    # This is the corrected line
    return secrets.compare_digest(key, expected_key.get_secret_value())