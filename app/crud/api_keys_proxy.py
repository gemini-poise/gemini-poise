import logging
import random
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..models import models

logger = logging.getLogger(__name__)


def get_active_api_keys(db: Session):
    """获取所有活跃的API keys"""
    return db.query(models.ApiKey).filter(models.ApiKey.status == "active").all()


def get_random_active_api_key(db: Session) -> Optional[models.ApiKey]:
    """
    获取一个随机的可用 API Key。
    如果没有任何可用 Key，返回 None。
    """
    active_keys = get_active_api_keys(db)
    if not active_keys:
        return None
    return random.choice(active_keys)


def get_random_active_api_key_from_db(db: Session) -> Optional[models.ApiKey]:
    """
    获取一个随机的可用 API Key (从数据库层面随机选择)。
    如果没有任何可用 Key，返回 None。
    """
    logger.info("Attempting to get a random active API key from the database.")

    dialect_name = db.connection().dialect.name
    if dialect_name == "mysql":
        random_func = func.rand()
    else:
        random_func = func.random()

    stmt = (
        select(models.ApiKey)
        .filter(models.ApiKey.status == "active")
        .order_by(random_func)
        .limit(1)
    )

    result = db.execute(stmt).scalar_one_or_none()

    if result:
        logger.info(
            f"Successfully retrieved random active API key with ID: {result.id}"
        )
    else:
        logger.warning("No active API keys found in the database.")

    return result


def increment_api_key_failure_count(
    db: Session, api_key_id: int, max_failed_count: int = 3
):
    """增加API key的失败计数"""
    api_key = db.query(models.ApiKey).filter(models.ApiKey.id == api_key_id).first()

    if not api_key:
        logger.error(f"API key with ID {api_key_id} not found for failure increment.")
        return

    api_key.failed_count += 1
    logger.warning(
        f"Incremented failure count for key ID {api_key_id} to {api_key.failed_count}"
    )

    if api_key.failed_count >= max_failed_count:
        api_key.is_active = False
        logger.error(
            f"API key ID {api_key_id} deactivated due to exceeding max failed count ({max_failed_count})."
        )

    db.commit()
    db.refresh(api_key)


def update_api_key_usage(db: Session, api_key_id: int, success: bool, status_override: Optional[str] = None):
    """
    更新 API Key 的使用次数、失败次数和最后使用时间。
    """
    from .api_keys_basic import get_api_key
    
    db_api_key = get_api_key(db, api_key_id)
    if db_api_key:
        db_api_key.last_used_at = datetime.now(timezone.utc)
        if status_override:
            db_api_key.status = status_override
            if status_override == "exhausted" or status_override == "error":
                db_api_key.failed_count += 1
        elif success:
            db_api_key.usage_count += 1
            db_api_key.failed_count = 0
        else:
            db_api_key.failed_count += 1
        db.add(db_api_key)