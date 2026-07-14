"""
Redis-backed async cache layer.

• Lazy-connects to Redis on first use.
• Gracefully falls back to no-op when REDIS_URL is unset or Redis is
  unreachable — the bot keeps working, just without the speedup.
• JSON-serialises values so any Python primitive or list/dict is storable.
• All public helpers are async-safe and importable from any handler.
"""
from __future__ import annotations
import json
import logging
from typing import Any

import redis.asyncio as aioredis
from config import REDIS_URL

log = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None
_available: bool | None = None   # None = untested

# ── TTL constants (seconds) ────────────────────────────────────────────────────
SETTINGS_TTL = 300   # group settings  (captcha, antispam, limits …)
WARN_TTL     = 60    # warn lists      — mutate often, keep fresh
LIST_TTL     = 120   # blacklists, notes index
BLOCK_TTL    = 600   # user/group block flags — rare writes


async def _client() -> aioredis.Redis | None:
    """Return a live Redis client, or None if unavailable."""
    global _redis, _available
    if _available is False:
        return None
    if _redis is not None:
        return _redis
    if not REDIS_URL:
        _available = False
        log.warning("REDIS_URL not set — Redis cache disabled.")
        return None
    try:
        _redis = aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,
        )
        await _redis.ping()
        _available = True
        log.info("Redis ✅ connected — caching active.")
    except Exception as exc:
        log.warning("Redis ❌ unavailable (%s) — falling back to direct DB.", exc)
        _redis = None
        _available = False
    return _redis


async def cget(key: str) -> Any | None:
    """Get a cached value. Returns None on miss or when cache is offline."""
    r = await _client()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception:
        return None


async def cset(key: str, value: Any, ttl: int) -> None:
    """Store a value with a TTL. Silently no-ops on failure."""
    r = await _client()
    if r is None:
        return
    try:
        await r.setex(key, ttl, json.dumps(value))
    except Exception:
        pass


async def cdel(*keys: str) -> None:
    """Delete one or more cache keys. Silently no-ops on failure."""
    r = await _client()
    if r is None:
        return
    try:
        await r.delete(*[k for k in keys if k])
    except Exception:
        pass


async def get_redis() -> aioredis.Redis | None:
    """Expose raw Redis client — used by the rate-limit sliding window."""
    return await _client()
