import logging
import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger("llm_qa")

_redis_client = None


async def get_redis_client():
    """Get or create the Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info("Redis client created")
    return _redis_client


async def close_redis():
    """Close the Redis connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connection closed")


async def cache_get(key: str):
    """Get a value from Redis cache."""
    client = await get_redis_client()
    try:
        value = await client.get(key)
        logger.debug("Cache GET: %s -> %s", key, value)
        return value
    except Exception as exc:
        logger.error("Cache GET error: %s", exc)
        return None


async def cache_set(key: str, value: str, expire_seconds: int = 3600):
    """Set a value in Redis cache with expiration."""
    client = await get_redis_client()
    try:
        await client.set(key, value, ex=expire_seconds)
        logger.debug("Cache SET: %s (expires in %d seconds)", key, expire_seconds)
    except Exception as exc:
        logger.error("Cache SET error: %s", exc)


async def cache_delete(key: str):
    """Delete a value from Redis cache."""
    client = await get_redis_client()
    try:
        await client.delete(key)
        logger.debug("Cache DELETE: %s", key)
    except Exception as exc:
        logger.error("Cache DELETE error: %s", exc)
