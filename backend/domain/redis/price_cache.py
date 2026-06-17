"""Redis-backed Domain API price cache — suburb median price with 24-hour TTL."""

import json

import structlog

from domain.redis.client import redis_client

logger = structlog.get_logger()

_PRICE_PREFIX: str = "price:"
_PRICE_TTL: int = 86400  # 24 hours — fixed, non-sliding (PRD §25.2)


class RedisPriceCache:
    """Caches Domain API suburb median prices in Redis.

    Key format: price:{suburb}:{property_type}:{min_bedrooms}
    TTL is fixed at 24 hours and does not slide on cache hits.
    Cache misses and Redis errors both return None — the caller falls through
    to the Domain API without any error propagation.
    """

    def _key(self, suburb: str, property_type: str, min_bedrooms: int) -> str:
        """Build the canonical Redis key for a suburb/type/beds combination."""
        slug: str = suburb.lower().replace(" ", "_")
        return f"{_PRICE_PREFIX}{slug}:{property_type}:{min_bedrooms}"

    async def get_async(self, suburb: str, property_type: str, min_bedrooms: int) -> int | None:
        """Return the cached median price, or None on cache miss.

        Args:
            suburb: Suburb name (normalised to lowercase with underscores).
            property_type: Property type string (e.g. "house").
            min_bedrooms: Minimum bedroom count.

        Returns:
            Cached median price in AUD, or None when absent or expired.
        """
        raw: str | None = await redis_client.get_async(
            self._key(suburb, property_type, min_bedrooms)
        )
        if raw is None:
            return None
        return int(json.loads(raw)["median_price"])

    async def set_async(
        self, suburb: str, property_type: str, min_bedrooms: int, median_price: int
    ) -> None:
        """Cache a median price with a fixed 24-hour TTL.

        Args:
            suburb: Suburb name.
            property_type: Property type string.
            min_bedrooms: Minimum bedroom count.
            median_price: Median price in AUD to cache.
        """
        value: str = json.dumps({"median_price": median_price})
        await redis_client.setex_async(
            self._key(suburb, property_type, min_bedrooms),
            _PRICE_TTL,
            value,
        )


price_cache: RedisPriceCache = RedisPriceCache()
