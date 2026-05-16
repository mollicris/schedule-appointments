from __future__ import annotations

import redis.asyncio as redis

from src.infrastructure.config.settings import get_settings

_redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """Get or create the Redis client."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = await redis.from_url(settings.redis_url)
    return _redis_client


async def close_redis() -> None:
    """Close the Redis client."""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
