# ai_conversation_engine/src/services/rate_limiter.py

import time
import hashlib
from functools import wraps
from quart import request, jsonify, current_app
import redis

class RateLimiter:
    """
    A Redis-based rate limiter for Quart applications.
    """
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def get_rate_limit_key(self) -> str:
        """
        Generates a composite rate limit key using conv_id and API key hash.
        """
        try:
            data = request.get_json()
            conv_id = data.get('conv_id') if data else None
            api_key = request.headers.get('X-API-Key', '')
            api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:8]
            return f"{conv_id}:{api_key_hash}" if conv_id else request.remote_addr
        except Exception:
            return request.remote_addr

    async def is_allowed(self, identifier: str) -> bool:
        """
        Checks if a request from the identifier is allowed using optimized Redis pipeline.

        Args:
            identifier: Unique identifier for the user (e.g., conv_id:api_key_hash).

        Returns:
            bool: True if allowed, False if rate limit exceeded.
        """
        key = f"rate_limit:{identifier}"
        client = current_app.conversation_manager.redis_client
        if not client:
            return True

        current_time = time.time()
        pipeline = client.pipeline()
        pipeline.zremrangebyscore(key, 0, current_time - self.window_seconds)
        pipeline.zadd(key, {str(current_time): current_time})
        pipeline.zcard(key)
        pipeline.expire(key, self.window_seconds)
        results = pipeline.execute()  # ✅ Single execute call
        count = results[2]

        return count <= self.max_requests

    def limit(self, identifier_func=None):
        """Decorator to apply rate limiting to a Quart route."""
        def decorator(f):
            @wraps(f)
            async def decorated_function(*args, **kwargs):
                identifier = self.get_rate_limit_key() if identifier_func is None else identifier_func()
                if not await self.is_allowed(identifier):  # ✅ Async method
                    response = jsonify({
                        "error": "Rate limit exceeded. Please try again later."
                    })
                    response.headers["Retry-After"] = str(self.window_seconds)
                    return response, 429
                return await f(*args, **kwargs)
            return decorated_function
        return decorator