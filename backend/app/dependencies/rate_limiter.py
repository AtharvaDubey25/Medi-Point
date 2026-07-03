import logging
import time
from uuid import uuid4

from fastapi import Request, HTTPException, status

from app.redis_client import get_redis

logger = logging.getLogger(__name__)

# Sliding-window rate limiter backed by Redis sorted sets.
#
# Key format: ratelimit:{namespace}:{ip}
#
# Each entry in the sorted set stores:
#   score  - current timestamp in milliseconds
#   member - unique request identifier ("{timestamp_ms}:{uuid4()}")
#
# On each request the following steps are executed atomically inside a pipeline:
#   1. ZREMRANGEBYSCORE - remove entries older than the configured time window
#   2. ZCARD            - count the remaining entries within the window
#   3. If count >= max_requests, reject with HTTP 429
#   4. ZADD             - insert the current request (score=now_ms, member=unique_id)
#   5. EXPIRE           - set TTL = window_seconds so inactive keys auto-clean
#
# Because all state lives in Redis, this works across multiple FastAPI workers
# and horizontally scaled deployments.


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int, namespace: str):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.namespace = namespace

    async def __call__(self, request: Request):
        ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{self.namespace}:{ip}"
        now_ms = int(time.time() * 1000)
        cutoff_ms = now_ms - (self.window_seconds * 1000)

        try:
            r = await get_redis()
            pipe = r.pipeline()
            pipe.zremrangebyscore(key, "-inf", cutoff_ms)
            pipe.zcard(key)
            pipe.zadd(key, {f"{now_ms}:{uuid4()}": now_ms})
            pipe.expire(key, self.window_seconds)
            _, count, _, _ = await pipe.execute()
        except Exception as e:
            logger.error("Redis rate-limiter error, failing open: %s", e)
            return True

        if count >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Limit: {self.max_requests} per {self.window_seconds}s",
            )

        return True


login_limiter = RateLimiter(max_requests=5, window_seconds=60, namespace="login")
register_limiter = RateLimiter(max_requests=3, window_seconds=60, namespace="register")
