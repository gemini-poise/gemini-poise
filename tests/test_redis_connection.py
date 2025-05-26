import logging
import pytest

from app.core import settings, init_redis, close_redis, get_redis_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

"""
pytest tests/test_redis_connection.py --log-cli-level=INFO --log-cli-format="%(asctime)s - %(levelname)s - %(message)s"
"""
@pytest.mark.asyncio
async def test_redis_connection():
    logger.info("Starting Redis connection test...")
    try:
        if not settings.REDIS_URL:
            pytest.skip("REDIS_URL is not set, skipping Redis connection test.")
        
        await init_redis()
        if get_redis_client is None:
            pytest.skip("Redis client could not be initialized, skipping Redis connection test.")
        logger.info("Redis client initialized for test.")

        async for client in get_redis_client():
            assert client is not None
            logger.info("Successfully obtained Redis client.")
            await client.set("test_key", "test_value")
            value = await client.get("test_key")
            assert value == "test_value"
            logger.info(f"Redis test_key set and retrieved successfully: {value}")
            await client.delete("test_key")
            logger.info("Redis test_key deleted.")

    except Exception as e:
        logger.error(f"Redis connection test failed: {e}", exc_info=True)
        pytest.fail(f"Redis connection test failed: {e}")
    finally:
        await close_redis()
        logger.info("Redis client closed after test.")