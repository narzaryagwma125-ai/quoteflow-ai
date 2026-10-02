"""In-memory sliding-window rate limiter.

For a single-process deployment this is sufficient. For multi-instance
deployments swap the storage backend (e.g. Redis) — the interface stays the same.

Keys never include secrets; they are audit-safe (ip + action prefix).
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from app.core.errors import too_many_requests


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        """Record a hit. Returns True if allowed, False if over limit."""
        now = time.monotonic()
        async with self._lock:
            bucket = self._buckets[key]
            while bucket and now - bucket[0] > window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    async def remaining(self, key: str, limit: int, window_seconds: int) -> int:
        now = time.monotonic()
        bucket = self._buckets[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        return max(0, limit - len(bucket))


limiter = InMemoryRateLimiter()


def client_ip_key(request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def enforce(client_ip: str, action: str, limit: int, window_seconds: int) -> None:
    key = f"{action}:{client_ip}"
    allowed = await limiter.hit(key, limit, window_seconds)
    if not allowed:
        raise too_many_requests()
