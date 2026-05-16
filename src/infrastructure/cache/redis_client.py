from __future__ import annotations

import asyncio
import time
from typing import Any

from src.infrastructure.config.settings import get_settings

# ── In-memory fallback (dev mode, no Redis required) ─────────────────────────

class _InMemoryRedis:
    """Minimal Redis-compatible in-memory store for development.

    Supports only the operations used in this project: get / setex / delete.
    TTL is enforced on read.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float]] = {}  # key → (value, expires_at)
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> bytes | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value.encode()

    async def setex(self, key: str, ttl_seconds: int, value: Any) -> None:
        async with self._lock:
            self._store[key] = (str(value), time.time() + ttl_seconds)

    async def delete(self, *keys: str) -> int:
        async with self._lock:
            count = 0
            for key in keys:
                if self._store.pop(key, None) is not None:
                    count += 1
            return count

    async def aclose(self) -> None:
        async with self._lock:
            self._store.clear()


# ── Real Redis (production) ───────────────────────────────────────────────────

_client: Any = None


async def get_redis() -> Any:
    """Return a Redis-compatible client.

    Uses real Redis when REDIS_URL is set to a non-empty value that starts
    with 'redis://'. Falls back to the in-memory store otherwise.
    """
    global _client
    if _client is not None:
        return _client

    settings = get_settings()
    url = settings.redis_url.strip()

    if url and url.startswith("redis://"):
        try:
            import redis.asyncio as aioredis
            _client = await aioredis.from_url(url)
            return _client
        except Exception:
            pass

    # Dev fallback
    _client = _InMemoryRedis()
    return _client


async def close_redis() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None
