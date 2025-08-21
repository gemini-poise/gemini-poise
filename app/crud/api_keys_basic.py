import logging
from typing import List
from sqlalchemy import select, insert
from sqlalchemy.orm import Session

from ..models import models
from ..schemas import schemas

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
    from .api_keys_cache import invalidate_active_api_keys_cache
    
    db_api_key = get_api_key(db, api_key_id)
    if db_api_key:
        # 检查是否更新了状态字段
        update_data = api_key_update.model_dump(exclude_unset=True)
        status_changed = 'status' in update_data and update_data['status'] != db_api_key.status
        
        for key, value in update_data.items():
            setattr(db_api_key, key, value)
        db.add(db_api_key)
        db.commit()
        db.refresh(db_api_key)
        
        # 如果状态发生变化，使缓存失效
        if status_changed:
            logger.info(f"🔄 [CACHE] API key {api_key_id} status changed, invalidating cache")
            invalidate_active_api_keys_cache()
            
    return db_api_key


def delete_api_key(db: Session, api_key_id: int):
    """
    删除 API Key。
    """
    from .api_keys_cache import invalidate_active_api_keys_cache
    
    db_api_key = get_api_key(db, api_key_id)
    if db_api_key:
        db.delete(db_api_key)
        db.commit()
        # 删除API key后使缓存失效
        logger.info(f"🗑️ [CACHE] API key {api_key_id} deleted, invalidating cache")
        invalidate_active_api_keys_cache()
    return db_api_key


def bulk_delete_api_keys(db: Session, api_key_ids: List[int]) -> int:
    """
    批量删除 API Key。
    返回删除的 Key 数量。
    """
    from .api_keys_cache import invalidate_active_api_keys_cache
    
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
    
    # 批量删除后使缓存失效
    if delete_count > 0:
        logger.info(f"🗑️ [CACHE] Bulk deleted {delete_count} API keys, invalidating cache")
        invalidate_active_api_keys_cache()
    
    return delete_count


def bulk_add_api_keys(db: Session, key_values: List[str]) -> int:
    """
    批量添加 API Key。如果 Key 存在则跳过，不存在则插入。
    返回新插入的 Key 数量。
    """
    from .api_keys_cache import invalidate_active_api_keys_cache
    
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
    
    # 批量添加后使缓存失效
    if len(keys_to_add) > 0:
        logger.info(f"➕ [CACHE] Bulk added {len(keys_to_add)} API keys, invalidating cache")
        invalidate_active_api_keys_cache()
    
    return len(keys_to_add)


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