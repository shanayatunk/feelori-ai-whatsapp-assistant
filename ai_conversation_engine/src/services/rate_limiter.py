# ai_conversation_engine/src/services/rate_limiter.py

import time
import hashlib
import logging
from functools import wraps
from typing import Optional, Callable, Any
from quart import request, jsonify, current_app
import redis.asyncio as redis
from redis.exceptions import RedisError, NoScriptError

logger = logging.getLogger(__name__)

class RateLimiterError(Exception):
    """Custom exception for critical rate limiter errors."""
    pass

# Lua script for atomic sliding window rate limiting.
# This script ensures that checking the limit and adding a request are one atomic operation.
LUA_SCRIPT = """
-- Keys: 1 (the rate limit key)
-- ARGV: 1 (max_requests), 2 (window_seconds), 3 (current_time_float), 4 (unique_request_id)

local key = KEYS[1]
local max_requests = tonumber(ARGV[1])
local window_seconds = tonumber(ARGV[2])
local current_time = tonumber(ARGV[3])
local unique_member = ARGV[4]

-- 1. Remove requests that are outside the current time window.
local cutoff_time = current_time - window_seconds
redis.call('ZREMRANGEBYSCORE', key, 0, cutoff_time)

-- 2. Check the number of requests in the current window.
local current_count = redis.call('ZCARD', key)

if current_count < max_requests then
    -- 3. If allowed, add the new request to the sorted set.
    redis.call('ZADD', key, current_time, unique_member)
    -- 4. Set an expiry on the key to auto-clean it from Redis if it becomes inactive.
    redis.call('EXPIRE', key, window_seconds + 60)
    return 1 -- Allowed
else
    -- 5. If denied, return the current count.
    return 0 -- Denied
end
"""

class RateLimiter:
    """
    A Redis-based rate limiter for Quart applications using an atomic sliding window algorithm.
    """
    
    def __init__(self, max_requests: int, window_seconds: int, fail_open: bool = True):
        """
        Args:
            max_requests: Maximum number of requests allowed in the window.
            window_seconds: Time window in seconds.
            fail_open: If True, allow requests when Redis is unavailable.
        """
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
            
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.fail_open = fail_open
        self._script_sha: Optional[str] = None

    @property
    def _redis_client(self) -> Optional[redis.Redis]:
        """Gets the Redis client from the application context."""
        if not hasattr(current_app, 'conversation_manager'):
            return None
        return getattr(current_app.conversation_manager, '_redis_client', None)

    async def _load_script(self) -> Optional[str]:
        """Loads the Lua script into Redis and caches its SHA hash."""
        if self._script_sha:
            return self._script_sha
        
        client = self._redis_client
        if not client:
            return None
        
        try:
            self._script_sha = await client.script_load(LUA_SCRIPT)
            logger.info(f"Loaded rate limiter Lua script with SHA: {self._script_sha}")
            return self._script_sha
        except RedisError as e:
            logger.error(f"Failed to load Redis Lua script: {e}")
            return None

    def get_rate_limit_key(self) -> str:
        """
        Generates a composite rate limit key using conv_id and a hashed API key.
        Falls back to IP address if other identifiers are not available.
        """
        try:
            data = request.get_json(silent=True) or {}
            conv_id = data.get('conv_id')
            
            api_key = request.headers.get('X-API-Key', '')
            if api_key:
                api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
                if conv_id:
                    return f"rl:{conv_id}:{api_key_hash}"
                return f"rl:api:{api_key_hash}"
            
            if conv_id:
                return f"rl:conv:{conv_id}"
            return f"rl:ip:{request.remote_addr}"
            
        except Exception:
            # Failsafe for any unexpected errors during key generation
            return f"rl:ip:{getattr(request, 'remote_addr', 'unknown')}"

    async def is_allowed(self, identifier: str) -> bool:
        """
        Checks if a request is allowed using the atomic Lua script.
        """
        if not identifier:
            logger.warning("Rate limit check called with an empty identifier.")
            return self.fail_open

        client = self._redis_client
        if not client:
            logger.warning("Redis client unavailable for rate limiting.")
            return self.fail_open

        try:
            script_sha = await self._load_script()
            if not script_sha:
                logger.error("Rate limiter Lua script not loaded, cannot check.")
                return self.fail_open

            current_time = time.time()
            unique_id = f"{current_time:.6f}:{id(object())}" # High-precision, unique member
            
            # Atomically execute the script
            result = await client.evalsha(
                script_sha, 1, f"rate_limit:{identifier}",
                self.max_requests, self.window_seconds, current_time, unique_id
            )
            
            return result == 1

        except NoScriptError:
            # The script was flushed from Redis cache, reload it.
            logger.warning("Lua script not found on Redis, reloading...")
            self._script_sha = None # Force reload
            return await self.is_allowed(identifier) # Retry once
        except RedisError as e:
            logger.error(f"Redis error during rate limiting for '{identifier}': {e}")
            if self.fail_open:
                return True
            raise RateLimiterError(f"Rate limiter Redis error: {e}")

    def limit(self, identifier_func: Optional[Callable[[], str]] = None):
        """Decorator to apply rate limiting to a Quart route."""
        def decorator(f: Callable) -> Callable:
            @wraps(f)
            async def decorated_function(*args: Any, **kwargs: Any):
                identifier = identifier_func() if identifier_func else self.get_rate_limit_key()
                
                if not await self.is_allowed(identifier):
                    response = jsonify({
                        "error": "Rate limit exceeded",
                        "message": "Too many requests. Please try again later.",
                    })
                    
                    # Add informative headers
                    response.headers["Retry-After"] = str(self.window_seconds)
                    response.headers["X-RateLimit-Limit"] = str(self.max_requests)
                    response.headers["X-RateLimit-Remaining"] = "0"
                    
                    return response, 429
                
                return await f(*args, **kwargs)
            return decorated_function
        return decorator