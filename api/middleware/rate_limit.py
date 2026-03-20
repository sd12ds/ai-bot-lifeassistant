"""
In-memory rate limiter для API endpoints.
"""
from __future__ import annotations
import time, logging
from collections import defaultdict
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# In-memory storage: {key: [(timestamp, ...),]}
_buckets: dict[str, list[float]] = defaultdict(list)


def rate_limit(max_requests: int = 10, window_seconds: int = 60):
    """FastAPI dependency factory для rate limiting."""
    async def limiter(request: Request):
        # Ключ: IP + user_id (если есть)
        ip = request.client.host if request.client else "unknown"
        key = f"{ip}:{request.url.path}"
        now = time.time()
        # Очищаем устаревшие записи
        _buckets[key] = [t for t in _buckets[key] if now - t < window_seconds]
        if len(_buckets[key]) >= max_requests:
            logger.warning("Rate limit exceeded: %s (%d/%d)", key, len(_buckets[key]), max_requests)
            raise HTTPException(429, "Too many requests. Try again later.")
        _buckets[key].append(now)
    return limiter
