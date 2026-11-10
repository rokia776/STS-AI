import asyncpg
import logging

from app.core.config import settings

logger = logging.getLogger("llm_qa")

_pool = None


async def get_pool():
    """Get or create the database connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=5,
            max_size=10,
        )
        logger.info("Database connection pool created")
    return _pool


async def close_pool():
    """Close the database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed")


async def get_connection():
    """Get a database connection from the pool."""
    pool = await get_pool()
    return await pool.acquire()


async def release_connection(connection):
    """Release a database connection back to the pool."""
    if connection:
        await _pool.release(connection)
