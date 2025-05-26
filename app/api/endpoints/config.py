from typing import List

from fastapi import APIRouter, HTTPException, status

from ... import crud
from ...core.scheduler_config import scheduler, logger
from ...tasks.key_validation import validate_api_key_task
from ...core.database import SessionLocal

from ...core.security import user_dependency, db_dependency

from ...schemas.schemas import (
    ConfigItem,
    ConfigCreateRequest,
    ConfigUpdateRequest,
    ConfigBulkSaveRequest,
)


router = APIRouter(prefix="/config", tags=["Config"])


def _reschedule_key_validation_task(interval_value: str, source: str):
    """
    Helper function to reschedule the API Key validation task.
    """
    try:
        new_interval_seconds = int(interval_value)
        if new_interval_seconds <= 0:
            logger.warning(
                f"Invalid new task interval '{interval_value}' from {source}, using default 300 seconds."
            )
            new_interval_seconds = 300

        if scheduler.get_job("key_validation_task"):
            scheduler.reschedule_job(
                "key_validation_task", trigger="interval", seconds=new_interval_seconds
            )
            logger.info(
                f"API Key validation task rescheduled to {new_interval_seconds} seconds via {source}."
            )
        else:
            scheduler.add_job(
                validate_api_key_task,
                "interval",
                seconds=new_interval_seconds,
                id="key_validation_task",
                replace_existing=True,
                args=[SessionLocal],
            )
            logger.info(
                f"API Key validation task added to scheduler (interval: {new_interval_seconds} seconds) via {source}."
            )

    except ValueError:
        logger.error(
            f"Invalid value for key_validation_interval_seconds from {source}: {interval_value}. Must be an integer."
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interval value from {source}. Must be an integer.",
        )
    except Exception as e:
        logger.error(
            f"Error rescheduling API Key validation task from {source}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to reschedule task from {source}."
        )


@router.get("/", response_model=List[ConfigItem])
async def get_all_config(db: db_dependency, current_user: user_dependency):
    """
    获取所有配置项。需要登录。
    """
    _ = current_user
    config_items = crud.config.get_all_config(db)
    return [ConfigItem.model_validate(item) for item in config_items]


@router.get("/{key}", response_model=ConfigItem)
async def get_config_by_key(key: str, db: db_dependency, current_user: user_dependency):
    """
    根据 Key 获取单个配置项。需要登录。
    """
    # 只有登录用户才能执行此操作
    _ = current_user
    config_item = crud.config.get_config_by_key(db, key)
    if config_item is None:
        raise HTTPException(status_code=404, detail=f"Config key '{key}' not found")
    return ConfigItem.model_validate(config_item)


@router.post("/", response_model=ConfigItem, status_code=status.HTTP_201_CREATED)
async def create_config_item(
    config_item: ConfigCreateRequest, db: db_dependency, current_user: user_dependency
):
    """
    创建一个新的配置项。需要登录。
    """
    # 只有登录用户才能执行此操作
    existing_config = crud.config.get_config_by_key(db, config_item.key)
    if existing_config:
        raise HTTPException(
            status_code=400, detail=f"Config key '{config_item.key}' already exists"
        )

    created_config = crud.config.create_config_item(db, config_item, current_user.id)
    db.commit()
    db.refresh(created_config)
    return ConfigItem.model_validate(created_config)


@router.put("/{key}", response_model=ConfigItem)
async def update_config_by_key(
    key: str,
    config_update: ConfigUpdateRequest,
    db: db_dependency,
    current_user: user_dependency,
):
    """
    根据 Key 更新配置值。需要登录。
    """
    # 只有登录用户才能执行此操作
    updated = crud.config.update_config_value(
        db, key, config_update.value, current_user.id
    )
    db.commit()
    if not updated:
        raise HTTPException(status_code=404, detail=f"Config key '{key}' not found")

    if key == "key_validation_interval_seconds":
        _reschedule_key_validation_task(config_update.value, "update_config_by_key")

    updated_config = crud.config.get_config_by_key(db, key)
    return ConfigItem.model_validate(updated_config)


@router.delete("/{key}")
async def delete_config_by_key(
    key: str, db: db_dependency, current_user: user_dependency
):
    """
    根据 Key 删除配置项。需要登录。
    """
    # 只有登录用户才能执行此操作
    _ = current_user
    deleted = crud.config.delete_config_key(db, key)
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Config key '{key}' not found")
    return {"detail": f"Config key '{key}' deleted"}


@router.post("/bulk-save", status_code=status.HTTP_200_OK)
async def bulk_save_config(
    request_data: ConfigBulkSaveRequest,
    db: db_dependency,
    current_user: user_dependency,
):
    """
    批量保存配置项。如果 Key 存在则更新，否则添加。需要登录。
    """
    crud.config.bulk_save_config_items(db, request_data.items, current_user.id)
    db.commit()

    for item in request_data.items:
        if item.key == "key_validation_interval_seconds":
            _reschedule_key_validation_task(item.value, "bulk_save")
            break

    return {"detail": f"Successfully processed {len(request_data.items)} config items."}
