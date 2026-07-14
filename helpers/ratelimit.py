"""
Redis sorted-set sliding-window rate limiter.

Falls back to in-memory deques when Redis is unavailable so the bot stays
functional even without a Redis server.

Usage:
    count = await sw_count("flood:chat:user", window=10)
    if count >= limit:
        await sw_reset("flood:chat:user")
        # take action
"""
from __future__ import annotations
import time
from collections import defaultdict, deque

from cache import get_redis

# In-memory fallback store {key: deque of float timestamps}
_mem: dict[str, deque] = defaultdict(deque)


async def sw_count(key: str, window: int, *, record: bool = True) -> int:
    """
    Return the number of events recorded in the last `window` seconds.
    If `record` is True (default) this call itself is counted as an event.
    """
    now = time.time()
    r = await get_redis()

    if r is not None:
        # Redis sorted set — score = unix timestamp, member = unique nano key
        member = f"{now:.9f}"
        cutoff = now - window
        pipe = r.pipeline()
        if record:
            pipe.zadd(key, {member: now})
        pipe.zremrangebyscore(key, "-inf", cutoff)
        pipe.zcard(key)
        pipe.expire(key, window + 10)
        results = await pipe.execute()
        return int(results[2])   # zcard result
    else:
        dq = _mem[key]
        if record:
            dq.append(now)
        while dq and now - dq[0] > window:
            dq.popleft()
        return len(dq)


async def sw_count_text(key: str, text: str, window: int) -> int:
    """
    Count how many times *exactly `text`* has been seen under `key` within
    `window` seconds, recording this occurrence in the process.
    Uses a composite key so different texts get independent counters.
    """
    import hashlib
    h = hashlib.sha1(text.encode()).hexdigest()[:12]
    return await sw_count(f"{key}:{h}", window)


async def sw_reset(key: str) -> None:
    """Clear all recorded events for `key` (and any sub-keys via pattern)."""
    r = await get_redis()
    if r is not None:
        # Delete the key itself; sub-keys (text hashes) share the prefix
        await r.delete(key)
        # Also clean up any text-hash sub-keys
        try:
            sub_keys = await r.keys(f"{key}:*")
            if sub_keys:
                await r.delete(*sub_keys)
        except Exception:
            pass
    else:
        # Remove from in-memory fallback
        _mem.pop(key, None)
        to_remove = [k for k in list(_mem) if k.startswith(f"{key}:")]
        for k in to_remove:
            _mem.pop(k, None)
