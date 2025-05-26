import logging
from typing import Optional, List

from sqlalchemy import insert, update, select
from sqlalchemy.orm import Session

from ..models import models
from ..schemas import schemas

logger = logging.getLogger(__name__)


def get_config_value(db: Session, key: str) -> Optional[str]:
    """根据 Key 获取配置值。"""
    logger.info(f"Attempting to get config value for key: {key}")
    result = db.execute(
        select(models.Config.value).where(models.Config.key == key)
    ).scalar_one_or_none()
    logger.info(f"Result for config key '{key}': {result}")
    return result


def get_all_config(db: Session) -> list[models.Config]:
    """获取所有配置项。"""
    logger.info("Attempting to get all config items.")
    result = db.execute(select(models.Config)).scalars().all()
    logger.info(f"Found {len(result)} config items.")
    return list(result)


def get_config_by_key(db: Session, key: str) -> Optional[models.Config]:
    """根据 Key 获取单个配置项模型。"""
    logger.info(f"Attempting to get config item for key: {key}")
    result = db.execute(
        select(models.Config).where(models.Config.key == key)
    ).scalar_one_or_none()
    logger.info(f"Result for config item '{key}': {result}")
    return result


def create_config_item(
    db: Session, config_item: schemas.ConfigCreateRequest, user_id: int
) -> models.Config:
    """创建一个新的配置项。"""
    logger.info(
        f"Attempting to create config item with key: {config_item.key} by user ID {user_id}."
    )
    db_config = models.Config(
        key=config_item.key, value=config_item.value, updated_by_user_id=user_id
    )
    db.add(db_config)
    logger.info(
        f"Config key '{config_item.key}' added to session by user ID {user_id}."
    )
    return db_config


def update_config_value(db: Session, key: str, value: str, user_id: int) -> bool:
    """根据 Key 更新配置值。"""
    logger.info(f"Attempting to update config key: {key} by user ID {user_id}.")
    existing_config = get_config_by_key(db, key)

    if existing_config:
        db.execute(
            update(models.Config)
            .where(models.Config.key == key)
            .values(value=value, updated_by_user_id=user_id)
        )
        logger.info(f"Config key '{key}' updated in session by user ID {user_id}.")
        return True
    else:
        logger.warning(f"Attempted to update non-existent config key '{key}'.")
        return False


def bulk_save_config_items(
    db: Session, config_items: List[schemas.ConfigBulkSaveRequestItem], user_id: int
):
    """
    批量保存配置项。如果 Key 存在则更新，否则添加。
    """
    logger.info(
        f"Attempting to bulk save {len(config_items)} config items by user ID {user_id}."
    )

    # 获取所有现有配置项的 Key
    existing_keys = {item.key for item in get_all_config(db)}  # 使用集合提高查找效率

    items_to_create = []
    items_to_update = []

    for item in config_items:
        if item.key in existing_keys:
            items_to_update.append(item)
        else:
            items_to_create.append(item)

    if items_to_create:
        insert_data = [
            {"key": item.key, "value": item.value, "updated_by_user_id": user_id}
            for item in items_to_create
        ]
        db.execute(insert(models.Config), insert_data)
        logger.info(f"Bulk created {len(items_to_create)} config items.")

    if items_to_update:
        for item in items_to_update:
            db.execute(
                update(models.Config)
                .where(models.Config.key == item.key)
                .values(value=item.value, updated_by_user_id=user_id)
            )
        logger.info(f"Bulk updated {len(items_to_update)} config items.")


def delete_config_key(db: Session, key: str) -> int:
    """根据 Key 删除配置项。"""
    logger.info(f"Attempting to delete config key: {key}.")
    deleted_count = db.query(models.Config).filter(models.Config.key == key).delete()
    logger.info(f"Deleted {deleted_count} rows for config key '{key}'.")
    return deleted_count


# 初始化配置
# def initialize_config(db: Session):
#     """
#     初始化配置。如果在数据库中没有找到某个关键配置项，则创建一个默认值。
#     注意：初始化时需要一个默认用户 ID，例如第一个管理员用户 ID
#     """
#     logger.info("Attempting to initialize default config items.")
#     # 假设第一个用户 (ID=1) 是管理员用于初始化
#     default_user_id = 1
#     # 检查默认用户是否存在
#     from . import users as crud_users
#     default_user = crud_users.get_user(db, default_user_id)
#     if not default_user:
#         logger.error(f"Default user ID {default_user_id} not found for config initialization! Skipping initialization.")
#         return
#
#     # 定义需要初始化的默认配置项 (Key 和默认 Value)
#     default_configs_to_initialize = {
#         "target_api_url": "https://generativelanguage.googleapis.com/v1beta",
#         "key_validation_interval_seconds": "3600",
#         "key_validation_max_failed_count": "3",
#         "key_validation_timeout_seconds": "10.0",
#     }
#
#     # 遍历需要初始化的配置项
#     for key, default_value in default_configs_to_initialize.items():
#         existing_value = get_config_value(db, key)
#
#         if existing_value is None:
#             create_config_item(db, schemas.ConfigCreateRequest(key=key, value=default_value), default_user_id)
#             logger.info(
#                 f"Default config key '{key}' created with value '{default_value}' by user ID {default_user_id}.")
#
#     db.commit()
#     logger.info("Default config initialization finished.")
