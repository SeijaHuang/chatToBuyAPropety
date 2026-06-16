"""Low-level Redis connection management — connect, close, ping, raw get/setex."""

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import settings

logger = structlog.get_logger()


class RedisClient:
    """Manages the async Redis connection pool and exposes atomic get/setex operations.

    All Redis errors are caught and logged at WARNING level; callers receive None or
    a silent no-op so that Redis failures never propagate to the HTTP response layer.
    """

    def __init__(self) -> None:
        self._redis: Redis | None = None

    async def connect_async(self) -> None:
        """Open the Redis connection pool and verify connectivity with a PING.

        Raises:
            RedisError: If the initial PING fails (startup should abort).
        """
        self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
        await self._redis.get("__connect_check__")
        logger.info("redis_connected", url=settings.redis_url)

    async def close_async(self) -> None:
        """Close all pooled Redis connections."""
        if self._redis is not None:
            await self._redis.aclose()
            logger.info("redis_disconnected")

    async def ping_async(self) -> bool:
        """Return True if Redis responds to PING; used by the /health endpoint.

        Returns:
            True on success, False on any connection or command error.
        """
        if self._redis is None:
            return False
        try:
            await self._redis.get("__health_check__")
            return True
        except RedisError:
            return False

    async def get_async(self, key: str) -> str | None:
        """Return the string value stored at key, or None on miss or error.

        Args:
            key: Redis key to fetch.

        Returns:
            Stored string value, or None when the key is absent or a Redis error occurs.

        Raises:
            RuntimeError: If called before connect_async().
        """
        if self._redis is None:
            raise RuntimeError("RedisClient.connect_async() must be called before use.")
        try:
            raw: object = await self._redis.get(key)
            return str(raw) if isinstance(raw, str) else None
        except RedisError as exc:
            logger.warning("redis_get_failed", key=key, error=str(exc))
            return None

    async def setex_async(self, key: str, ttl: int, value: str) -> None:
        """Set key to value with an expiry of ttl seconds.

        Errors are logged at WARNING level and swallowed — callers must not rely
        on this call succeeding in order to maintain correctness.

        Args:
            key: Redis key to write.
            ttl: Expiry duration in seconds.
            value: String value to store.

        Raises:
            RuntimeError: If called before connect_async().
        """
        if self._redis is None:
            raise RuntimeError("RedisClient.connect_async() must be called before use.")
        try:
            await self._redis.setex(key, ttl, value)
        except RedisError as exc:
            logger.warning("redis_setex_failed", key=key, error=str(exc))


redis_client: RedisClient = RedisClient()