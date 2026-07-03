import logging
from redis.asyncio import Redis, ConnectionPool

from app.config import settings

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None
_redis: Redis | None = None


async def get_redis() -> Redis:
    global _redis, _pool
    if _redis is None:
        _pool = ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)
        _redis = Redis(connection_pool=_pool)
    return _redis


async def init_redis():
    try:
        r = await get_redis()
        await r.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.warning("Redis unavailable — rate limiter will fail open: %s", e)


async def close_redis():
    global _redis, _pool
    if _redis:
        await _redis.aclose()
        _redis = None
    if _pool:
        await _pool.disconnect()
        _pool = None
