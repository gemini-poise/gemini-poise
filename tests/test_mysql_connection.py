import logging
import pytest
from sqlalchemy import text
from app.core import get_db, settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture(scope="module", autouse=True)
def setup_database_url():
    if not settings.DATABASE_URL:
        pytest.skip("DATABASE_URL is not set in config. Skipping MySQL tests.")

def test_mysql_version_and_database():
    with next(get_db()) as db:
        version_query = text("SELECT VERSION();")
        version_result = db.execute(version_query).fetchone()
        assert version_result is not None, "Failed to get MySQL version"
        logger.info(f"MySQL Version: {version_result[0]}")

        database_query = text("SELECT DATABASE();")
        database_result = db.execute(database_query).fetchone()
        assert database_result is not None, "Failed to get current database"
        logger.info(f"Current Database: {database_result[0]}")