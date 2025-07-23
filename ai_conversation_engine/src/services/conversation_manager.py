# ai_conversation_engine/src/services/conversation_manager.py

import redis
import json
import logging
import time
import asyncio  # ✅ Added import
from typing import List, Dict, Optional, Any, Tuple
from collections import OrderedDict

from src.config import Settings

logger = logging.getLogger(__name__)

class ConversationManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._redis_client: Optional[redis.Redis] = None
        self._connection_pool: Optional[redis.ConnectionPool] = None
        self.fallback_storage: OrderedDict[str, Tuple[str, float]] = OrderedDict()
        self._lock = asyncio.Lock()  # ✅ Added lock
        self.max_fallback_entries = 1000
        self.history_ttl = self.settings.CONVERSATION_TTL_SECONDS
        self.max_history_length = 20

    @property
    def redis_client(self) -> Optional[redis.Redis]:
        if self._redis_client is None and self._connection_pool is None:
            try:
                self._connection_pool = redis.ConnectionPool(
                    host=self.settings.REDIS_HOST,
                    port=self.settings.REDIS_PORT,
                    password=self.settings.REDIS_PASSWORD,
                    ssl=self.settings.REDIS_SSL,
                    ssl_cert_reqs=None if not self.settings.REDIS_SSL else 'required',
                    decode_responses=True,
                    max_connections=50  # ✅ Added connection pooling config
                )
                self._redis_client = redis.Redis(connection_pool=self._connection_pool)
                logger.info("Redis connection established.")
            except redis.RedisError as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self._redis_client = None
        return self._redis_client

    def close(self) -> None:
        """Closes the Redis connection pool to release resources."""
        if self._connection_pool:
            logger.info("Closing Redis connection pool.")
            self._connection_pool.disconnect()
            self._redis_client = None
            self._connection_pool = None

    async def get_cache(self, key: str) -> Optional[Any]:
        client = self.redis_client
        if client:
            try:
                data = client.get(key)
                return json.loads(data) if data else None
            except redis.RedisError as e:
                logger.error(f"Redis GET error for key '{key}': {e}. Using fallback.")
        
        async with self._lock:  # ✅ Thread-safe access
            cached_item = self.fallback_storage.get(key)
            if cached_item:
                data, timestamp = cached_item
                if time.time() - timestamp < self.history_ttl:
                    return json.loads(data) if data else None
                else:
                    del self.fallback_storage[key]
        return None

    async def set_cache(self, key: str, value: Any, ttl_seconds: int) -> None:
        client = self.redis_client
        serialized_value = json.dumps(value)
        
        if client:
            try:
                client.setex(key, ttl_seconds, serialized_value)
                return
            except redis.RedisError as e:
                logger.error(f"Redis SET error for key '{key}': {e}. Using fallback.")
        
        async with self._lock:  # ✅ Thread-safe access
            if len(self.fallback_storage) >= self.max_fallback_entries * 0.9:
                logger.warning(f"Fallback storage approaching capacity: {len(self.fallback_storage)} entries")
            self.fallback_storage[key] = (serialized_value, time.time())
            await self._cleanup_fallback_storage()

    async def get_history(self, conversation_id: str) -> List[Dict]:
        return await self.get_cache(f"history:{conversation_id}") or []

    async def save_history(self, conversation_id: str, history: List[Dict]) -> None:
        if len(history) > self.max_history_length:
            history = history[-self.max_history_length:]
        await self.set_cache(f"history:{conversation_id}", history, ttl_seconds=self.history_ttl)

    async def _cleanup_fallback_storage(self) -> None:
        async with self._lock:  # ✅ Thread-safe cleanup
            now = time.time()
            expired_keys = [key for key, (_, timestamp) in self.fallback_storage.items() if now - timestamp > self.history_ttl]
            for key in expired_keys:
                try:
                    del self.fallback_storage[key]
                except KeyError:
                    pass
        
            while len(self.fallback_storage) > self.max_fallback_entries:
                logger.warning(f"Removing oldest entry from fallback storage to prevent memory leak")
                self.fallback_storage.popitem(last=False)