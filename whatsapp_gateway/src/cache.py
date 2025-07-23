# src/services/cache.py

import redis
import structlog
from src.config import settings

logger = structlog.get_logger(__name__)

class RedisManager:
    """
    A robust Redis connection manager that handles connection pooling
    and graceful degradation if Redis is unavailable.
    """
    def __init__(self):
        self._pool: redis.ConnectionPool = None
        self._client: redis.Redis = None
        self._is_available: bool = False
        self._connect()

    def _connect(self):
        """Attempts to establish a connection to Redis."""
        try:
            if not self._pool:
                self._pool = redis.ConnectionPool(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    decode_responses=True # Decode responses to UTF-8
                )
            
            self._client = redis.Redis(connection_pool=self._pool)
            self._client.ping()
            self._is_available = True
            logger.info("Successfully connected to Redis", host=settings.REDIS_HOST)
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            self._is_available = False
            logger.error("Redis is unavailable. Service will run in degraded mode.", error=str(e))
        except Exception as e:
            self._is_available = False
            logger.error("An unexpected error occurred during Redis connection.", error=str(e))

    def get_client(self) -> Optional[redis.Redis]:
        """
        Returns the Redis client if available, otherwise returns None.
        Attempts to reconnect if the connection was previously lost.
        """
        if not self._is_available:
            logger.warning("Attempting to reconnect to Redis...")
            self._connect()
        
        return self._client if self._is_available else None

    @property
    def is_available(self) -> bool:
        """Returns the current availability status of Redis."""
        # Perform a quick check to see if the connection is still alive
        if self._client:
            try:
                self._client.ping()
                self._is_available = True
            except redis.exceptions.ConnectionError:
                self._is_available = False
                logger.warning("Lost connection to Redis.")
        return self._is_available

    def close(self):
        """Closes the Redis connection pool."""
        if self._pool:
            self._pool.disconnect()
            logger.info("Redis connection pool disconnected.")

# Instantiate a single manager for the application
redis_manager = RedisManager()

# Provide a direct reference to the client for convenience
redis_client = redis_manager.get_client()