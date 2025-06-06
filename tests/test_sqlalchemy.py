import logging
import pytest
from sqlalchemy import text
from app.core import get_db, Base, engine, settings
from sqlalchemy import Column, Integer, String


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SQLAlchemyTestTable(Base):
    __tablename__ = "test_sqlalchemy_table"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)

    def __repr__(self):
        return f"<SQLAlchemyTestTable(id={self.id}, name='{self.name}')>"


@pytest.fixture(scope="module", autouse=True)
def setup_sqlalchemy_test_db():
    if not settings.DATABASE_URL:
        pytest.skip("DATABASE_URL is not set in config. Skipping SQLAlchemy tests.")

    Base.metadata.create_all(bind=engine)

    yield

    Base.metadata.drop_all(bind=engine)

def test_sqlalchemy_connection():
    with next(get_db()) as db:
        result = db.execute(text("SELECT 1")).fetchone()
        assert result is not None and result[0] == 1, "SQLAlchemy connection failed"
        logger.info("SQLAlchemy connection successful.")

def test_sqlalchemy_insert_and_select():
    with next(get_db()) as db:
        new_entry = SQLAlchemyTestTable(name="Test Entry")
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)
        logger.info(f"Inserted: {new_entry}")

        retrieved_entry = db.query(SQLAlchemyTestTable).filter_by(name="Test Entry").first()
        assert retrieved_entry is not None, "Failed to retrieve inserted data"
        assert retrieved_entry.name == "Test Entry", "Retrieved data mismatch"
        logger.info(f"Retrieved: {retrieved_entry}")

        db.delete(retrieved_entry)
        db.commit()