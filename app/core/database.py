import logging
from typing import AsyncGenerator

from redis import asyncio as aioredis
from redis.asyncio import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

logger = logging.getLogger(__name__)

# --- SQLAlchemy Database Setup ---
connect_args = {}
if settings.DATABASE_TYPE.lower() == "sqlite":
    # SQLite特定的优化参数
    connect_args = {
        "check_same_thread": False,  # 允许跨线程使用连接
        "timeout": 30,               # 连接超时时间（秒）
        "isolation_level": "IMMEDIATE"  # 事务隔离级别
    }

engine = create_engine(settings.DATABASE_URL,
                       pool_size=settings.POOL_SIZE,
                       max_overflow=settings.MAX_OVERFLOW,
                       pool_timeout=settings.POOL_TIMEOUT,
                       connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        logger.info('entering db context')
        yield db
    finally:
        logger.info('exiting db context')
        logger.info('closing db session')
        db.close()


# 优化SQLite配置
def optimize_sqlite():
    """应用SQLite特定的PRAGMA优化"""
    if settings.DATABASE_TYPE.lower() == "sqlite":
        logger.info("Applying SQLite optimizations...")
        with engine.connect() as conn:
            # 启用WAL模式，提高并发性能
            conn.execute("PRAGMA journal_mode=WAL")
            # 启用内存映射，提高读取性能（设置为30GB，根据实际内存调整）
            conn.execute("PRAGMA mmap_size=30000000000")
            # 降低同步级别，提高写入性能（可能略微降低崩溃安全性）
            conn.execute("PRAGMA synchronous=NORMAL")
            # 增加缓存大小（约20MB）
            conn.execute("PRAGMA cache_size=-20000")
            # 使用内存存储临时表和索引
            conn.execute("PRAGMA temp_store=MEMORY")
            # 设置较大的页面大小，减少I/O操作
            conn.execute("PRAGMA page_size=4096")
            # 启用自动清理
            conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
            # 设置较大的批量提交大小
            conn.execute("PRAGMA busy_timeout=5000")
        logger.info("SQLite optimizations applied successfully")


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
