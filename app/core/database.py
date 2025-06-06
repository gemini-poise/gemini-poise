import logging
from typing import AsyncGenerator

from redis import asyncio as aioredis
from redis.asyncio import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

logger = logging.getLogger(__name__)

# --- SQLAlchemy Database Setup ---
engine = create_engine(settings.DATABASE_URL,
                       pool_size=settings.POOL_SIZE,
                       max_overflow=settings.MAX_OVERFLOW,
                       pool_timeout=settings.POOL_TIMEOUT)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        logger.info('entering db context')
        yield db
    finally:
        logger.info('exiting db context') # 移动到 finally 块的开头
        logger.info('closing db session')
        db.close()


# --- Redis Setup ---
redis_client: Redis | None = None


async def init_redis():
    """Initialize Redis client."""
    global redis_client
    logger.info("Attempting to initialize Redis client...")
    redis_url = settings.REDIS_URL
    redis_password = settings.REDIS_PASSWORD
    try:
        redis_params = {"encoding": "utf-8", "decode_responses": True}
        if redis_password:
            redis_params["password"] = redis_password

        redis_client = aioredis.from_url(redis_url, **redis_params)
        await redis_client.ping()
        logger.info("Redis client initialized successfully and ping successful.")
    except Exception as e:
        redis_client = None
        logger.error(f"Failed to initialize or connect to Redis: {e}", exc_info=True)


async def close_redis():
    """Close Redis client."""
    global redis_client
    if redis_client:
        logger.info("Attempting to close Redis client...")
        await redis_client.aclose()
        logger.info("Redis client closed.")
        redis_client = None


async def get_redis_client() -> AsyncGenerator[Redis, None]:
    """Dependency to get Redis client."""
    if not redis_client:
        logger.error("Redis client requested but not initialized.")
        raise RuntimeError("Redis client not initialized")
    yield redis_client
