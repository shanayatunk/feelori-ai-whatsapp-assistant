# ai_conversation_engine/src/utils/rate_limiter.py

import time
import hashlib
import logging
import asyncio
from functools import wraps
from typing import Optional, Callable, Any, Dict
from quart import request, jsonify, current_app
import redis.asyncio as redis
from redis.exceptions import RedisError, NoScriptError

logger = logging.getLogger(__name__)

class RateLimiterError(Exception):
    """Custom exception for critical rate limiter errors."""
    pass

# Lua script for atomic sliding window rate limiting.
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
    A Redis-based rate limiter with fallback to in-memory storage.
    Compatible with both Quart decorators and direct usage.
    """
    
    def __init__(
        self, 
        max_requests: int, 
        time_window: int = None,  # For compatibility with ai_processor.py
        window_seconds: int = None,  # For compatibility with routes
        fail_open: bool = True,
        redis_client: Optional[redis.Redis] = None
    ):
        """
        Args:
            max_requests: Maximum number of requests allowed in the window.
            time_window: Time window in seconds (for ai_processor.py compatibility).
            window_seconds: Time window in seconds (for routes compatibility).
            fail_open: If True, allow requests when Redis is unavailable.
            redis_client: Optional Redis client to use.
        """
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        
        # Handle both parameter names for backward compatibility
        if time_window is not None and window_seconds is not None:
            raise ValueError("Cannot specify both time_window and window_seconds")
        
        window = time_window or window_seconds or 60
        if window <= 0:
            raise ValueError("time window must be positive")
            
        self.max_requests = max_requests
        self.time_window = window  # For ai_processor.py compatibility
        self.window_seconds = window  # For routes compatibility
        self.fail_open = fail_open
        self._redis_client = redis_client
        self._script_sha: Optional[str] = None
        
        # In-memory fallback storage
        self._memory_storage: Dict[str, list] = {}
        self._cleanup_interval = 60  # Clean memory every minute
        self._last_cleanup = time.time()

    async def allow_request(self, identifier: str) -> bool:
        """
        Check if a request should be allowed for the given identifier.
        This method is used by ai_processor.py
        
        Args:
            identifier: Unique identifier for rate limiting (e.g., user_id)
            
        Returns:
            True if request is allowed, False otherwise
        """
        return await self.is_allowed(identifier)

    async def is_allowed(self, identifier: str) -> bool:
        """
        Checks if a request is allowed using Redis or memory fallback.
        
        Args:
            identifier: Unique identifier for rate limiting
            
        Returns:
            True if allowed, False if rate limited
        """
        if not identifier:
            logger.warning("Rate limit check called with empty identifier")
            return self.fail_open

        # Try Redis first if available
        if self._redis_client:
            try:
                return await self._redis_is_allowed(identifier)
            except Exception as e:
                logger.warning(f"Redis rate limiting failed, using memory fallback: {e}")
        
        # Fallback to memory-based rate limiting
        return await self._memory_is_allowed(identifier)

    @property
    def redis_client(self) -> Optional[redis.Redis]:
        """Gets the Redis client, trying app context if not set."""
        if self._redis_client:
            return self._redis_client
        
        # Try to get from current app context (for Quart decorator usage)
        try:
            if hasattr(current_app, 'conversation_manager'):
                return getattr(current_app.conversation_manager, '_redis_client', None)
        except RuntimeError:
            # No app context available
            pass
        
        return None

    async def _load_script(self, client: redis.Redis) -> Optional[str]:
        """Loads the Lua script into Redis and caches its SHA hash."""
        if self._script_sha:
            return self._script_sha
        
        try:
            self._script_sha = await client.script_load(LUA_SCRIPT)
            logger.debug("Loaded rate limiter Lua script successfully")
            return self._script_sha
        except RedisError as e:
            logger.error(f"Failed to load Redis Lua script: {e}")
            return None

    async def _redis_is_allowed(self, identifier: str) -> bool:
        """Check rate limit using Redis."""
        client = self.redis_client
        if not client:
            raise Exception("Redis client not available")

        try:
            script_sha = await self._load_script(client)
            if not script_sha:
                raise Exception("Lua script not available")

            current_time = time.time()
            unique_id = f"{current_time:.6f}:{id(object())}"
            
            # Hash the identifier for security
            safe_key = hashlib.sha256(identifier.encode()).hexdigest()[:16]
            
            # Atomically execute the script
            result = await client.evalsha(
                script_sha, 1, f"rate_limit:{safe_key}",
                self.max_requests, self.window_seconds, current_time, unique_id
            )
            
            return result == 1

        except NoScriptError:
            # The script was flushed from Redis cache, reload it.
            logger.warning("Lua script not found in Redis, reloading")
            self._script_sha = None
            return await self._redis_is_allowed(identifier)
                
        except RedisError as e:
            logger.error(f"Redis error during rate limiting: {e}")
            if self.fail_open:
                return True
            raise RateLimiterError("Rate limiter Redis error occurred")

    async def _memory_is_allowed(self, identifier: str) -> bool:
        """Check rate limit using in-memory storage."""
        current_time = time.time()
        
        # Cleanup old entries periodically
        if current_time - self._last_cleanup > self._cleanup_interval:
            await self._cleanup_memory()
            self._last_cleanup = current_time
        
        # Hash identifier for consistency
        safe_key = hashlib.sha256(identifier.encode()).hexdigest()[:16]
        
        # Get or create request list for this identifier
        if safe_key not in self._memory_storage:
            self._memory_storage[safe_key] = []
        
        request_times = self._memory_storage[safe_key]
        
        # Remove requests outside the time window
        cutoff_time = current_time - self.window_seconds
        request_times[:] = [t for t in request_times if t > cutoff_time]
        
        # Check if we can allow this request
        if len(request_times) < self.max_requests:
            request_times.append(current_time)
            return True
        
        return False

    async def _cleanup_memory(self) -> None:
        """Clean up expired entries from memory storage."""
        current_time = time.time()
        cutoff_time = current_time - self.window_seconds
        
        keys_to_remove = []
        for key, request_times in self._memory_storage.items():
            # Remove old requests
            request_times[:] = [t for t in request_times if t > cutoff_time]
            
            # If no recent requests, remove the key entirely
            if not request_times:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._memory_storage[key]
        
        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} expired rate limit entries")

    def get_rate_limit_key(self) -> str:
        """
        Generates a secure composite rate limit key for Quart requests.
        This method is used when the rate limiter is used as a decorator.
        """
        try:
            data = request.get_json(silent=True) or {}
            conv_id = data.get('conv_id', '')
            
            api_key = request.headers.get('X-API-Key', '')
            user_agent = request.headers.get('User-Agent', '')
            remote_addr = getattr(request, 'remote_addr', 'unknown')
            
            # Create composite identifier with all available data
            raw_identifier = f"{conv_id}:{api_key}:{remote_addr}:{user_agent}"
            
            # Always hash the identifier for security
            identifier_hash = hashlib.sha256(raw_identifier.encode()).hexdigest()[:16]
            
            return f"rl:{identifier_hash}"
            
        except Exception:
            # Failsafe: create a minimal but secure fallback key
            try:
                remote_addr = getattr(request, 'remote_addr', 'unknown')
                fallback_data = f"fallback:{remote_addr}:{time.time()}"
                fallback_hash = hashlib.sha256(fallback_data.encode()).hexdigest()[:16]
                return f"rl:{fallback_hash}"
            except Exception:
                # Ultimate fallback
                return f"rl:emergency:{int(time.time())}"

    def limit(self, identifier_func: Optional[Callable[[], str]] = None):
        """Decorator to apply rate limiting to a Quart route."""
        def decorator(f: Callable) -> Callable:
            @wraps(f)
            async def decorated_function(*args: Any, **kwargs: Any):
                try:
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
                except Exception as e:
                    logger.error(f"Rate limiter decorator error: {e}")
                    # Continue with request if rate limiter fails
                    return await f(*args, **kwargs)
                    
            return decorated_function
        return decorator

    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            'max_requests': self.max_requests,
            'time_window': self.time_window,
            'memory_entries': len(self._memory_storage),
            'redis_available': self.redis_client is not None,
            'fail_open': self.fail_open
        }

    async def reset(self, identifier: str) -> bool:
        """
        Reset rate limit for a specific identifier.
        
        Args:
            identifier: Identifier to reset
            
        Returns:
            True if reset successful
        """
        try:
            # Reset in Redis if available
            if self.redis_client:
                safe_key = hashlib.sha256(identifier.encode()).hexdigest()[:16]
                redis_key = f"rate_limit:{safe_key}"
                await self.redis_client.delete(redis_key)
            
            # Reset in memory storage
            safe_key = hashlib.sha256(identifier.encode()).hexdigest()[:16]
            if safe_key in self._memory_storage:
                del self._memory_storage[safe_key]
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset rate limit for {identifier}: {e}")
            return False

    async def close(self) -> None:
        """Clean up resources."""
        try:
            # Clear memory storage
            self._memory_storage.clear()
            
            # Redis client cleanup is handled by the client itself
            logger.debug("Rate limiter cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Error during rate limiter cleanup: {e}")

    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            # Only clear memory storage in destructor
            if hasattr(self, '_memory_storage'):
                self._memory_storage.clear()
        except Exception:
            pass