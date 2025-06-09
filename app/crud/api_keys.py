import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple

from sqlalchemy import select, func, insert, and_, case
from sqlalchemy.orm import Session

from ..models import models
from ..schemas import schemas
from ..utils.token_bucket import token_bucket_manager

logger = logging.getLogger(__name__)


def get_api_key(db: Session, api_key_id: int):
    """
    根据 ID 获取单个 API Key。
    """
    return db.query(models.ApiKey).filter(models.ApiKey.id == api_key_id).first()


def get_api_key_by_value(db: Session, key_value: str):
    """
    根据 Key 值获取单个 API Key。
    """
    return db.query(models.ApiKey).filter(models.ApiKey.key_value == key_value).first()


def get_api_keys(db: Session, skip: int = 0, limit: int = 100):
    """
    获取 API Key 列表。
    """
    return db.query(models.ApiKey).offset(skip).limit(limit).all()


def create_api_key(db: Session, api_key: schemas.ApiKeyCreate):
    """
    创建一个新的 API Key。如果 Key 存在则不做处理，返回 None。
    """
    logger.info(f"Attempting to create single API key: {api_key.key_value}.")

    # ！！！先查询 Key 是否已存在！！！
    existing_key = get_api_key_by_value(db, api_key.key_value)
    if existing_key:
        logger.warning(
            f"API Key '{api_key.key_value}' already exists, skipping creation."
        )
        return None

    db_api_key = models.ApiKey(**api_key.model_dump())
    db.add(db_api_key)
    logger.info(f"API Key '{api_key.key_value}' added to session.")
    return db_api_key


def update_api_key(db: Session, api_key_id: int, api_key_update: schemas.ApiKeyUpdate):
    """
    更新 API Key 信息。
    """
    db_api_key = get_api_key(db, api_key_id)
    if db_api_key:
        update_data = api_key_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_api_key, key, value)
        db.add(db_api_key)
        db.commit()
        db.refresh(db_api_key)
    return db_api_key


def delete_api_key(db: Session, api_key_id: int):
    """
    删除 API Key。
    """
    db_api_key = get_api_key(db, api_key_id)
    if db_api_key:
        db.delete(db_api_key)
        db.commit()
    return db_api_key


def bulk_delete_api_keys(db: Session, api_key_ids: List[int]) -> int:
    """
    批量删除 API Key。
    返回删除的 Key 数量。
    """
    if not api_key_ids:
        return 0

    # 使用 in 操作符删除指定 ID 的记录
    delete_count = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.id.in_(api_key_ids))
        .delete(synchronize_session=False)
    )
    db.commit()
    logger.info(f"Bulk deleted {delete_count} API keys with IDs: {api_key_ids}")
    return delete_count


def delete_api_call_logs_by_api_key_ids(db: Session, api_key_ids: List[int]) -> int:
    """
    根据 API Key ID 批量删除 API 调用日志。
    返回删除的日志数量。
    """
    if not api_key_ids:
        return 0

    delete_count = (
        db.query(models.ApiCallLog)
        .filter(models.ApiCallLog.api_key_id.in_(api_key_ids))
        .delete(synchronize_session=False)
    )
    db.commit()
    logger.info(f"Bulk deleted {delete_count} API call logs for API Key IDs: {api_key_ids}")
    return delete_count


def bulk_add_api_keys(db: Session, key_values: List[str]) -> int:
    """
    批量添加 API Key。如果 Key 存在则跳过，不存在则插入。
    返回新插入的 Key 数量。
    """
    logger.info(f"Attempting to bulk add {len(key_values)} API keys.")

    if not key_values:
        logger.info("No key values provided for bulk add.")
        return 0

    existing_keys_query = db.execute(select(models.ApiKey.key_value)).scalars().all()
    existing_keys = set(existing_keys_query)

    keys_to_add = []
    for key_value in key_values:
        cleaned_key = key_value.strip()
        if cleaned_key and cleaned_key not in existing_keys:
            keys_to_add.append(cleaned_key)
            existing_keys.add(cleaned_key)

    if not keys_to_add:
        logger.info("All provided keys already exist or are empty after cleaning.")
        return 0

    insert_data = [{"key_value": key, "status": "active"} for key in keys_to_add]

    db.execute(insert(models.ApiKey), insert_data)

    logger.info(f"Bulk added {len(keys_to_add)} new API keys.")
    return len(keys_to_add)


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
            case((models.ApiKey.status == "active", 0), else_=1), models.ApiKey.id.asc()
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
    valid_keys = db.query(models.ApiKey).filter(
        (models.ApiKey.status == "active") | (models.ApiKey.status == "exhausted")
    ).count()
    invalid_keys = db.query(models.ApiKey).filter(models.ApiKey.status == "error").count()

    statistics = schemas.KeyStatistics(
        total_keys=total_keys,
        valid_keys=valid_keys,
        invalid_keys=invalid_keys,
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


# --- 用于代理逻辑的函数 ---


def get_active_api_keys(db: Session):
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


# --- Token Bucket 相关函数 ---

def get_api_key_with_token_bucket(db: Session, required_tokens: int = 1) -> Optional[models.ApiKey]:
    """
    使用 token bucket 算法获取可用的 API Key。
    优先选择令牌充足的 key，实现智能负载均衡。
    
    Args:
        db: 数据库会话
        required_tokens: 所需令牌数量，默认为1
        
    Returns:
        Optional[models.ApiKey]: 可用的 API Key，如果没有则返回 None
    """
    logger.info(f"Attempting to get API key using token bucket algorithm, required tokens: {required_tokens}")
    
    active_keys = get_active_api_keys(db)
    if not active_keys:
        logger.warning("No active API keys found")
        return None
    
    active_key_ids = [key.id for key in active_keys]
    
    available_key_ids = token_bucket_manager.get_available_api_keys(active_key_ids, required_tokens)
    
    if not available_key_ids:
        logger.warning("No API keys have sufficient tokens available")
        return None
    
    selected_key_id = _select_best_api_key(available_key_ids)
    
    if token_bucket_manager.consume_token(selected_key_id, required_tokens):
        selected_key = next((key for key in active_keys if key.id == selected_key_id), None)
        if selected_key:
            logger.info(f"Successfully selected API key {selected_key_id} using token bucket")
            return selected_key
    
    logger.warning(f"Failed to consume tokens for selected API key {selected_key_id}")
    return None


def _select_best_api_key(available_key_ids: List[int]) -> int:
    """
    从可用的 API key 中选择最佳的一个。
    当前实现使用加权随机选择，令牌越多权重越高。
    
    Args:
        available_key_ids: 可用的 API key ID 列表
        
    Returns:
        int: 选中的 API key ID
    """
    if len(available_key_ids) == 1:
        return available_key_ids[0]
    
    key_weights = []
    for key_id in available_key_ids:
        tokens = token_bucket_manager.get_available_tokens(key_id)
        key_weights.append(max(tokens, 0.1))
    
    total_weight = sum(key_weights)
    if total_weight <= 0:
        return random.choice(available_key_ids)
    
    random_value = random.uniform(0, total_weight)
    cumulative_weight = 0
    
    for i, weight in enumerate(key_weights):
        cumulative_weight += weight
        if random_value <= cumulative_weight:
            return available_key_ids[i]
    
    return available_key_ids[-1]


def get_active_api_key_with_token_bucket(db: Session) -> Optional[models.ApiKey]:
    """
    使用 token bucket 算法获取一个可用的活跃 API Key。
    这是类似于 get_random_active_api_key_from_db 的主要入口方法。
    如果 token bucket 方法失败，会自动回退到随机选择。
    
    Args:
        db: 数据库会话
        
    Returns:
        Optional[models.ApiKey]: 可用的 API Key，如果没有则返回 None
    """
    logger.info("Attempting to get active API key using token bucket algorithm.")
    
    try:
        api_key = get_api_key_with_token_bucket(db, required_tokens=1)
        if api_key:
            logger.info(f"Successfully retrieved API key {api_key.id} using token bucket")
            return api_key
        
        logger.info("Token bucket method failed, falling back to random selection")
        
        fallback_key = get_random_active_api_key_from_db(db)
        if fallback_key:
            logger.info(f"Fallback: retrieved API key {fallback_key.id} using random selection")
        else:
            logger.warning("No active API keys available")
        
        return fallback_key
        
    except Exception as e:
        logger.error(f"Error in token bucket API key selection: {e}")
        return get_random_active_api_key_from_db(db)


def get_api_key_with_fallback(db: Session, required_tokens: int = 1, use_token_bucket: bool = True) -> Optional[models.ApiKey]:
    """
    获取 API Key 的高级入口函数，支持 token bucket 和传统随机选择的回退机制。
    
    Args:
        db: 数据库会话
        required_tokens: 所需令牌数量
        use_token_bucket: 是否使用 token bucket 算法
        
    Returns:
        Optional[models.ApiKey]: 可用的 API Key
    """
    if use_token_bucket:
        api_key = get_api_key_with_token_bucket(db, required_tokens)
        if api_key:
            return api_key
        
        logger.info("Token bucket method failed, falling back to random selection")
    
    return get_random_active_api_key_from_db(db)


def configure_api_key_token_bucket(api_key_id: int, capacity: int = None, refill_rate: float = None):
    """
    配置指定 API Key 的 token bucket 参数。
    
    Args:
        api_key_id: API Key ID
        capacity: 令牌桶容量
        refill_rate: 令牌补充速率（每秒）
    """
    token_bucket_manager.configure_bucket(api_key_id, capacity, refill_rate)
    logger.info(f"Configured token bucket for API key {api_key_id}")


def reset_api_key_token_bucket(api_key_id: int):
    """
    重置指定 API Key 的 token bucket（填满令牌）。
    
    Args:
        api_key_id: API Key ID
    """
    token_bucket_manager.reset_bucket(api_key_id)
    logger.info(f"Reset token bucket for API key {api_key_id}")


def get_api_key_token_info(api_key_id: int) -> dict:
    """
    获取指定 API Key 的 token bucket 信息。
    
    Args:
        api_key_id: API Key ID
        
    Returns:
        dict: Token bucket 信息
    """
    return token_bucket_manager.get_bucket_info(api_key_id)


def batch_configure_token_buckets(db: Session, capacity: int = 10, refill_rate: float = 1.0):
    """
    批量配置所有活跃 API Key 的 token bucket。
    
    Args:
        db: 数据库会话
        capacity: 令牌桶容量
        refill_rate: 令牌补充速率（每秒）
    """
    active_keys = get_active_api_keys(db)
    configured_count = 0
    
    for api_key in active_keys:
        try:
            token_bucket_manager.configure_bucket(api_key.id, capacity, refill_rate)
            configured_count += 1
        except Exception as e:
            logger.error(f"Failed to configure token bucket for API key {api_key.id}: {e}")
    
    logger.info(f"Batch configured token buckets for {configured_count} API keys")
    return configured_count


def cleanup_token_buckets():
    """
    清理过期的 token bucket 数据。
    """
    try:
        token_bucket_manager.cleanup_expired_buckets()
        logger.info("Token bucket cleanup completed")
    except Exception as e:
        logger.error(f"Token bucket cleanup failed: {e}")
