# ai_conversation_engine/src/utils/cache.py

import asyncio
import time
import json
import hashlib
import logging
from typing import Any, Optional, Dict, Union, List
from dataclasses import dataclass, asdict
from enum import Enum
import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError
import pickle
import zlib

logger = logging.getLogger(__name__)

class CacheBackend(Enum):
    """Supported cache backends."""
    REDIS = "redis"
    MEMORY = "memory"

@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    data: Any
    created_at: float
    ttl: Optional[int] = None
    access_count: int = 0
    last_accessed: float = 0.0
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl
    
    def touch(self) -> None:
        """Update access metadata."""
        self.access_count += 1
        self.last_accessed = time.time()

class CacheError(Exception):
    """Custom exception for cache-related errors."""
    pass

class CacheManager:
    """
    Advanced cache manager supporting both Redis and in-memory backends
    with compression, serialization, and TTL management.
    """
    
    def __init__(
        self,
        backend: CacheBackend = CacheBackend.MEMORY,
        redis_url: Optional[str] = None,
        default_ttl: int = 3600,
        max_memory_items: int = 10000,
        compression_threshold: int = 1024,
        enable_compression: bool = True,
        key_prefix: str = "cache",
        fail_silently: bool = True
    ):
        """
        Initialize the cache manager.
        
        Args:
            backend: Cache backend to use (REDIS or MEMORY)
            redis_url: Redis connection URL (required for REDIS backend)
            default_ttl: Default TTL in seconds
            max_memory_items: Maximum items in memory cache
            compression_threshold: Compress data larger than this size (bytes)
            enable_compression: Whether to enable compression
            key_prefix: Prefix for all cache keys
            fail_silently: If True, cache failures won't raise exceptions
        """
        self.backend = backend
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.max_memory_items = max_memory_items
        self.compression_threshold = compression_threshold
        self.enable_compression = enable_compression
        self.key_prefix = key_prefix
        self.fail_silently = fail_silently
        
        # Redis client (lazy initialization)
        self._redis_client: Optional[redis.Redis] = None
        self._redis_connected = False
        
        # In-memory cache
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []  # For LRU eviction
        
        # Statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0,
            'evictions': 0
        }
        
        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 300  # 5 minutes

    async def initialize(self) -> None:
        """Initialize the cache manager."""
        if self.backend == CacheBackend.REDIS:
            await self._connect_redis()
        
        # Start background cleanup for memory cache
        if self.backend == CacheBackend.MEMORY:
            self._cleanup_task = asyncio.create_task(self._cleanup_expired())
        
        logger.info(f"Cache manager initialized with {self.backend.value} backend")

    async def _connect_redis(self) -> None:
        """Connect to Redis with retry logic."""
        if not self.redis_url:
            raise CacheError("Redis URL is required for Redis backend")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self._redis_client = redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=False,  # We handle our own serialization
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True
                )
                
                # Test connection
                await self._redis_client.ping()
                self._redis_connected = True
                logger.info("Connected to Redis successfully")
                return
                
            except (RedisError, ConnectionError) as e:
                logger.warning(f"Redis connection attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    if self.fail_silently:
                        logger.error("Failed to connect to Redis, falling back to memory cache")
                        self.backend = CacheBackend.MEMORY
                        return
                    else:
                        raise CacheError(f"Failed to connect to Redis after {max_retries} attempts")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

    def _make_key(self, key: str) -> str:
        """Create a prefixed cache key."""
        return f"{self.key_prefix}:{key}"

    def _serialize_data(self, data: Any) -> bytes:
        """Serialize data with optional compression."""
        try:
            # Use pickle for complex Python objects
            serialized = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
            
            # Compress if enabled and data is large enough
            if (self.enable_compression and 
                len(serialized) > self.compression_threshold):
                compressed = zlib.compress(serialized)
                # Only use compression if it actually reduces size
                if len(compressed) < len(serialized):
                    return b'compressed:' + compressed
            
            return b'raw:' + serialized
            
        except Exception as e:
            logger.error(f"Failed to serialize data: {e}")
            raise CacheError("Data serialization failed")

    def _deserialize_data(self, data: bytes) -> Any:
        """Deserialize data with decompression if needed."""
        try:
            if data.startswith(b'compressed:'):
                compressed_data = data[11:]  # Remove 'compressed:' prefix
                decompressed = zlib.decompress(compressed_data)
                return pickle.loads(decompressed)
            elif data.startswith(b'raw:'):
                raw_data = data[4:]  # Remove 'raw:' prefix
                return pickle.loads(raw_data)
            else:
                # Fallback for legacy data
                return pickle.loads(data)
                
        except Exception as e:
            logger.error(f"Failed to deserialize data: {e}")
            raise CacheError("Data deserialization failed")

    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        try:
            if self.backend == CacheBackend.REDIS and self._redis_connected:
                return await self._redis_get(key)
            else:
                return await self._memory_get(key)
                
        except Exception as e:
            self._stats['errors'] += 1
            if self.fail_silently:
                logger.warning(f"Cache get error for key '{key}': {e}")
                return None
            raise CacheError(f"Failed to get cache key '{key}'")

    async def _redis_get(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        cache_key = self._make_key(key)
        
        try:
            data = await self._redis_client.get(cache_key)
            if data is None:
                self._stats['misses'] += 1
                return None
            
            value = self._deserialize_data(data)
            self._stats['hits'] += 1
            return value
            
        except RedisError as e:
            logger.error(f"Redis get error: {e}")
            # Fallback to memory cache
            self._redis_connected = False
            return await self._memory_get(key)

    async def _memory_get(self, key: str) -> Optional[Any]:
        """Get value from memory cache."""
        if key not in self._memory_cache:
            self._stats['misses'] += 1
            return None
        
        entry = self._memory_cache[key]
        
        # Check expiration
        if entry.is_expired():
            del self._memory_cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            self._stats['misses'] += 1
            return None
        
        # Update access metadata
        entry.touch()
        
        # Update LRU order
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        
        self._stats['hits'] += 1
        return entry.data

    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set a value in the cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None for default)
            
        Returns:
            True if successful, False otherwise
        """
        if ttl is None:
            ttl = self.default_ttl
        
        try:
            if self.backend == CacheBackend.REDIS and self._redis_connected:
                success = await self._redis_set(key, value, ttl)
            else:
                success = await self._memory_set(key, value, ttl)
            
            if success:
                self._stats['sets'] += 1
            return success
            
        except Exception as e:
            self._stats['errors'] += 1
            if self.fail_silently:
                logger.warning(f"Cache set error for key '{key}': {e}")
                return False
            raise CacheError(f"Failed to set cache key '{key}'")

    async def _redis_set(self, key: str, value: Any, ttl: int) -> bool:
        """Set value in Redis."""
        cache_key = self._make_key(key)
        
        try:
            serialized_data = self._serialize_data(value)
            
            if ttl > 0:
                await self._redis_client.setex(cache_key, ttl, serialized_data)
            else:
                await self._redis_client.set(cache_key, serialized_data)
            
            return True
            
        except RedisError as e:
            logger.error(f"Redis set error: {e}")
            # Fallback to memory cache
            self._redis_connected = False
            return await self._memory_set(key, value, ttl)

    async def _memory_set(self, key: str, value: Any, ttl: int) -> bool:
        """Set value in memory cache."""
        # Check if cache is full and evict if necessary
        if len(self._memory_cache) >= self.max_memory_items:
            await self._evict_lru()
        
        # Create cache entry
        entry = CacheEntry(
            data=value,
            created_at=time.time(),
            ttl=ttl if ttl > 0 else None
        )
        
        # Store in cache
        self._memory_cache[key] = entry
        
        # Update access order
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        
        return True

    async def delete(self, key: str) -> bool:
        """
        Delete a key from the cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if key was deleted, False if not found
        """
        try:
            if self.backend == CacheBackend.REDIS and self._redis_connected:
                success = await self._redis_delete(key)
            else:
                success = await self._memory_delete(key)
            
            if success:
                self._stats['deletes'] += 1
            return success
            
        except Exception as e:
            self._stats['errors'] += 1
            if self.fail_silently:
                logger.warning(f"Cache delete error for key '{key}': {e}")
                return False
            raise CacheError(f"Failed to delete cache key '{key}'")

    async def _redis_delete(self, key: str) -> bool:
        """Delete key from Redis."""
        cache_key = self._make_key(key)
        
        try:
            deleted = await self._redis_client.delete(cache_key)
            return deleted > 0
            
        except RedisError as e:
            logger.error(f"Redis delete error: {e}")
            self._redis_connected = False
            return await self._memory_delete(key)

    async def _memory_delete(self, key: str) -> bool:
        """Delete key from memory cache."""
        if key in self._memory_cache:
            del self._memory_cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            return True
        return False

    async def clear(self) -> bool:
        """Clear all cache entries."""
        try:
            if self.backend == CacheBackend.REDIS and self._redis_connected:
                # Delete all keys with our prefix
                pattern = self._make_key("*")
                async for key in self._redis_client.scan_iter(match=pattern):
                    await self._redis_client.delete(key)
            
            # Always clear memory cache
            self._memory_cache.clear()
            self._access_order.clear()
            
            logger.info("Cache cleared successfully")
            return True
            
        except Exception as e:
            self._stats['errors'] += 1
            if self.fail_silently:
                logger.warning(f"Cache clear error: {e}")
                return False
            raise CacheError("Failed to clear cache")

    async def _evict_lru(self) -> None:
        """Evict least recently used items."""
        if not self._access_order:
            return
        
        # Remove 10% of items or at least 1
        items_to_evict = max(1, len(self._memory_cache) // 10)
        
        for _ in range(items_to_evict):
            if not self._access_order:
                break
            
            key = self._access_order.pop(0)  # Remove oldest
            if key in self._memory_cache:
                del self._memory_cache[key]
                self._stats['evictions'] += 1

    async def _cleanup_expired(self) -> None:
        """Background task to clean up expired entries."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                
                if self.backend == CacheBackend.MEMORY:
                    expired_keys = []
                    current_time = time.time()
                    
                    for key, entry in self._memory_cache.items():
                        if entry.is_expired():
                            expired_keys.append(key)
                    
                    for key in expired_keys:
                        await self._memory_delete(key)
                    
                    if expired_keys:
                        logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup task: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        stats = {
            **self._stats,
            'hit_rate_percent': round(hit_rate, 2),
            'total_requests': total_requests,
            'backend': self.backend.value,
            'memory_cache_size': len(self._memory_cache),
            'connected': self._redis_connected if self.backend == CacheBackend.REDIS else True
        }
        
        return stats

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on cache backend."""
        health = {
            'backend': self.backend.value,
            'healthy': True,
            'error': None
        }
        
        try:
            if self.backend == CacheBackend.REDIS:
                if self._redis_client:
                    await self._redis_client.ping()
                    health['connected'] = True
                else:
                    health['healthy'] = False
                    health['error'] = 'Redis client not initialized'
            else:
                # Memory cache is always available
                health['memory_usage'] = len(self._memory_cache)
                
        except Exception as e:
            health['healthy'] = False
            health['error'] = str(e)
        
        return health

    async def close(self) -> None:
        """Close cache manager and cleanup resources."""
        try:
            # Cancel cleanup task
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # Close Redis connection
            if self._redis_client:
                await self._redis_client.close()
            
            # Clear memory cache
            self._memory_cache.clear()
            self._access_order.clear()
            
            logger.info("Cache manager closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing cache manager: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # For sync context manager support
        pass

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Convenience functions for simple usage

_default_cache: Optional[CacheManager] = None

async def get_default_cache() -> CacheManager:
    """Get the default cache manager instance."""
    global _default_cache
    if _default_cache is None:
        _default_cache = CacheManager()
        await _default_cache.initialize()
    return _default_cache

async def cache_get(key: str) -> Optional[Any]:
    """Simple cache get using default cache manager."""
    cache = await get_default_cache()
    return await cache.get(key)

async def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """Simple cache set using default cache manager."""
    cache = await get_default_cache()
    return await cache.set(key, value, ttl)

async def cache_delete(key: str) -> bool:
    """Simple cache delete using default cache manager."""
    cache = await get_default_cache()
    return await cache.delete(key)