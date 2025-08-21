import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple

from sqlalchemy import select, func, and_, case
from sqlalchemy.orm import Session

from ..models import models
from ..schemas import schemas

logger = logging.getLogger(__name__)


def get_api_keys_paginated(
    db: Session,
    page: int,
    page_size: int,
    search_key: Optional[str] = None,
    min_failed_count: Optional[int] = None,
    status: Optional[str] = None,
) -> Tuple[list[models.ApiKey], int]:
    """
    获取分页后的 API Key 列表和总数。
    """
    logger.info(
        f"Attempting to get API keys for page {page} with size {page_size}, filters: search_key={search_key}, min_failed_count={min_failed_count}, status={status}"
    )

    skip = (page - 1) * page_size
    limit = page_size

    query = select(models.ApiKey)

    filters = []
    if search_key:
        filters.append(models.ApiKey.key_value.ilike(f"%{search_key}%"))
    if min_failed_count is not None:
        filters.append(models.ApiKey.failed_count >= min_failed_count)
    if status:
        filters.append(models.ApiKey.status == status)

    if filters:
        query = query.where(and_(*filters))

    total_query = select(func.count()).select_from(query.subquery())
    total = db.execute(total_query).scalar_one()
    logger.info(f"Calculated total active API keys (with filters): {total}")

    paginated_query = (
        query.order_by(
            case(
                (models.ApiKey.status == "active", 0),
                (models.ApiKey.status == "exhausted", 1),
                (models.ApiKey.status == "error", 2),
                else_=3
            ),
            models.ApiKey.id.asc()
        )
        .offset(skip)
        .limit(limit)
    )
    items = db.execute(paginated_query).scalars().all()
    logger.info(f"Retrieved {len(items)} API keys for page {page} (with filters).")

    return list(items), total


def get_key_statistics(db: Session) -> schemas.KeyStatistics:
    """
    获取 API Key 统计数据（总数、有效、无效）。
    """
    logger.info("Attempting to get API key statistics.")

    total_keys = db.query(models.ApiKey).count()
    active_keys = db.query(models.ApiKey).filter(models.ApiKey.status == "active").count()
    exhausted_keys = db.query(models.ApiKey).filter(models.ApiKey.status == "exhausted").count()
    error_keys = db.query(models.ApiKey).filter(models.ApiKey.status == "error").count()

    statistics = schemas.KeyStatistics(
        total_keys=total_keys,
        active_keys=active_keys,
        exhausted_keys=exhausted_keys,
        error_keys=error_keys,
    )
    logger.info(f"Retrieved API key statistics: {statistics.model_dump_json()}")
    return statistics


def get_api_call_statistics(db: Session) -> schemas.ApiCallStatistics:
    """
    获取 API 调用统计数据。
    """
    logger.info("Attempting to get API call statistics.")
    now = datetime.now(timezone.utc)

    # Calls in the last 1 minute
    one_minute_ago = now - timedelta(minutes=1)
    calls_last_1_minute = (
        db.query(func.sum(models.ApiCallLog.call_count))
        .filter(models.ApiCallLog.timestamp >= one_minute_ago)
        .scalar()
        or 0
    )

    # Calls in the last 1 hour
    one_hour_ago = now - timedelta(hours=1)
    calls_last_1_hour = (
        db.query(func.sum(models.ApiCallLog.call_count))
        .filter(models.ApiCallLog.timestamp >= one_hour_ago)
        .scalar()
        or 0
    )

    # Calls in the last 24 hours
    twenty_four_hours_ago = now - timedelta(hours=24)
    calls_last_24_hours = (
        db.query(func.sum(models.ApiCallLog.call_count))
        .filter(models.ApiCallLog.timestamp >= twenty_four_hours_ago)
        .scalar()
        or 0
    )

    # Monthly usage (current month)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_usage = (
        db.query(func.sum(models.ApiCallLog.call_count))
        .filter(models.ApiCallLog.timestamp >= start_of_month)
        .scalar()
        or 0
    )

    statistics = schemas.ApiCallStatistics(
        calls_last_1_minute=calls_last_1_minute,
        calls_last_1_hour=calls_last_1_hour,
        calls_last_24_hours=calls_last_24_hours,
        monthly_usage=monthly_usage,
    )
    logger.info(f"Retrieved API call statistics: {statistics.model_dump_json()}")
    return statistics


def get_api_call_logs_by_minute(db: Session, hours_ago: int = 24) -> List[schemas.ApiCallLogEntry]:
    """
    获取按分钟统计的 API 调用日志。
    """
    logger.info(f"Attempting to get API call logs for the last {hours_ago} hours.")
    end_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start_time = end_time - timedelta(hours=hours_ago)

    results = db.query(
        models.ApiCallLog.api_key_id,
        models.ApiKey.key_value,
        models.ApiCallLog.timestamp,
        models.ApiCallLog.call_count
    ).join(
        models.ApiKey, models.ApiCallLog.api_key_id == models.ApiKey.id
    ).filter(
        models.ApiCallLog.timestamp >= start_time,
        models.ApiCallLog.timestamp <= end_time
    ).order_by(
        models.ApiCallLog.api_key_id,
        models.ApiCallLog.timestamp
    ).all()

    logs = [
        schemas.ApiCallLogEntry(
            api_key_id=r.api_key_id,
            key_value= f"{r.key_value[:8]}...",
            timestamp=r.timestamp,
            call_count=r.call_count
        )
        for r in results
    ]
    logger.info(f"Retrieved {len(logs)} API call log entries.")
    return logs