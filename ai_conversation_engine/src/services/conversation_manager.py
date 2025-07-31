# ai_conversation_engine/src/services/conversation_manager.py

import redis.asyncio as redis
import json
import logging
import time
import asyncio
from typing import List, Dict, Optional, Any
from collections import OrderedDict
from contextlib import asynccontextmanager
from shared.config import Settings

logger = logging.getLogger(__name__)

class ConversationManager:
    """
    Manages conversation history and caching with a primary Redis backend
    and a secondary in-memory fallback cache for high availability.
    """
    def __init__(self, settings: Settings):
        self.settings = settings
        self._redis_client: Optional[redis.Redis] = None
        self.fallback_storage: OrderedDict[str, Tuple[str, float]] = OrderedDict()
        self._lock = asyncio.Lock()

        # Configuration for caching and history
        self.max_fallback_entries = 1000
        self.history_ttl_seconds = self.settings.CONVERSATION_TTL_SECONDS
        self.max_history_length = 20

        # Background task for periodic cleanup
        self._cleanup_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """
        Initializes the Redis connection pool and starts background tasks.
        This should be called once when the application starts.
        """
        try:
            pool = redis.ConnectionPool.from_url(
                self.settings.REDIS_URL,
                max_connections=50,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            self._redis_client = redis.Redis(connection_pool=pool)
            await self._redis_client.ping()
            logger.info("Redis connection pool established and health check passed.")
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {e}. Manager will operate in fallback mode.")
            self._redis_client = None

        # Start the periodic cleanup task for the fallback cache
        self._cleanup_task = asyncio.create_task(self._start_periodic_cleanup())
        logger.info("Started periodic cleanup task for fallback storage.")

    async def close(self):
        """Closes connections and cleans up resources gracefully."""
        # Stop the background cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                logger.info("Fallback storage cleanup task successfully cancelled.")

        # Close Redis client
        if self._redis_client:
            try:
                await self._redis_client.close()
                logger.info("Redis connection pool closed.")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
        
        # Clear in-memory storage
        async with self._lock:
            self.fallback_storage.clear()

    async def _is_redis_available(self) -> bool:
        """Checks if the Redis client is connected and healthy."""
        if not self._redis_client:
            return False
        try:
            await self._redis_client.ping()
            return True
        except (redis.RedisError, asyncio.TimeoutError):
            logger.warning("Redis health check failed. Switching to fallback storage.")
            return False

    async def get_history(self, conversation_id: str) -> List[Dict]:
        """
        Retrieves conversation history, trying Redis first and then the
        in-memory fallback cache.
        """
        if not conversation_id:
            return []

        key = f"history:{conversation_id}"
        
        # 1. Try to get from Redis
        if await self._is_redis_available():
            try:
                data = await self._redis_client.get(key)
                if data:
                    history = json.loads(data)
                    return self._validate_and_trim_history(history)
            except (redis.RedisError, json.JSONDecodeError) as e:
                logger.warning(f"Redis GET error for key '{key}': {e}. Falling back.")
        
        # 2. Fallback to local storage
        async with self._lock:
            cached_item = self.fallback_storage.get(key)
            if cached_item:
                data, timestamp = cached_item
                if time.time() - timestamp < self.history_ttl_seconds:
                    try:
                        history = json.loads(data)
                        return self._validate_and_trim_history(history)
                    except json.JSONDecodeError:
                        del self.fallback_storage[key] # Remove corrupted data
                else:
                    del self.fallback_storage[key] # Remove expired data
        return []
    async def health_check(self) -> dict:
        """
        Checks the health of the ConversationManager by checking its
        dependency on Redis.
        """
        is_redis_ok = await self._is_redis_available()
        
        # If Redis is down, the service still works in fallback mode,
        # so we'll call the status "degraded" instead of "unhealthy".
        status = "healthy" if is_redis_ok else "degraded"
        
        return {
            "status": status,
            "details": {
                "redis_connected": is_redis_ok
            }
        }

    async def save_history(self, conversation_id: str, history: List[Dict]) -> bool:
        """
        Saves conversation history, trying Redis first and then the
        in-memory fallback cache.
        """
        if not conversation_id or not isinstance(history, list):
            logger.warning("Invalid input for save_history.", conv_id=conversation_id)
            return False

        key = f"history:{conversation_id}"
        validated_history = self._validate_and_trim_history(history, add_timestamp=True)
        
        try:
            serialized_value = json.dumps(validated_history, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize history for key '{key}': {e}")
            return False
        
        # 1. Try to save to Redis
        if await self._is_redis_available():
            try:
                await self._redis_client.setex(key, self.history_ttl_seconds, serialized_value)
                return True
            except redis.RedisError as e:
                logger.warning(f"Redis SET error for key '{key}': {e}. Falling back.")

        # 2. Fallback to local storage
        async with self._lock:
            self.fallback_storage[key] = (serialized_value, time.time())
            self.fallback_storage.move_to_end(key) # Mark as recently used for LRU
        return True

    def _validate_and_trim_history(self, history: List[Dict], add_timestamp: bool = False) -> List[Dict]:
        """Validates the format of history entries and trims to max length."""
        if not isinstance(history, list):
            return []
            
        valid_history = []
        for entry in history:
            if isinstance(entry, dict) and 'role' in entry and 'content' in entry:
                if add_timestamp and 'timestamp' not in entry:
                    entry['timestamp'] = time.time()
                valid_history.append(entry)
        
        return valid_history[-self.max_history_length:]

    async def _cleanup_fallback_storage(self) -> None:
        """Periodically cleans expired items and enforces size limits on the fallback cache."""
        async with self._lock:
            now = time.time()
            # Remove expired items
            expired_keys = [
                key for key, (_, timestamp) in self.fallback_storage.items()
                if now - timestamp > self.history_ttl_seconds
            ]
            for key in expired_keys:
                del self.fallback_storage[key]
            
            # Enforce max size using LRU (Least Recently Used) eviction
            while len(self.fallback_storage) > self.max_fallback_entries:
                oldest_key, _ = self.fallback_storage.popitem(last=False)
                logger.warning(f"Evicted oldest entry from fallback storage: {oldest_key}")

    async def _start_periodic_cleanup(self, interval_seconds: int = 300):
        """A background task that runs cleanup periodically."""
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                logger.info("Running periodic cleanup of fallback storage...")
                await self._cleanup_fallback_storage()
            except asyncio.CancelledError:
                logger.info("Periodic cleanup task is stopping.")
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup task: {e}")