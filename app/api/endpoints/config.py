from typing import List, Optional

from fastapi import APIRouter, HTTPException, status

from ... import crud
from ...core.scheduler_config import scheduler, logger
from ...tasks.key_validation import (
    validate_active_api_keys_task,
    validate_exhausted_api_keys_task,
    validate_error_api_keys_task,
)
from ...core.database import SessionLocal

from ...core.security import user_dependency, db_dependency

from ...schemas.schemas import (
    ConfigItem,
    ConfigCreateRequest,
    ConfigUpdateRequest,
    ConfigBulkSaveRequest,
)


router = APIRouter(prefix="/config", tags=["Config"])


def _reschedule_task(
    task_id: str, task_func, interval_value: Optional[str], default_interval: int, source: str
):
    """
    Helper function to reschedule a specific API Key validation task.
    """
    try:
        new_interval_seconds = default_interval
        if interval_value is not None:
            try:
                parsed_interval = int(interval_value)
                if parsed_interval > 0:
                    new_interval_seconds = parsed_interval
                else:
                    logger.warning(
                        f"Invalid interval '{interval_value}' for task '{task_id}' from {source}, using default {default_interval} seconds."
                    )
            except ValueError:
                logger.warning(
                    f"Invalid interval format '{interval_value}' for task '{task_id}' from {source}, using default {default_interval} seconds."
                )

        if new_interval_seconds > 0:
            if scheduler.get_job(task_id):
                scheduler.reschedule_job(
                    task_id, trigger="interval", seconds=new_interval_seconds
                )
                logger.info(
                    f"Task '{task_id}' rescheduled to {new_interval_seconds} seconds via {source}."
                )
            else:
                scheduler.add_job(
                    task_func,
                    "interval",
                    seconds=new_interval_seconds,
                    id=task_id,
                    replace_existing=True,
                )
                logger.info(
                    f"Task '{task_id}' added to scheduler (interval: {new_interval_seconds} seconds) via {source}."
                )
        else:
            if scheduler.get_job(task_id):
                scheduler.remove_job(task_id)
                logger.info(f"Task '{task_id}' removed from scheduler as interval is 0.")

    except Exception as e:
        logger.error(
            f"Error rescheduling task '{task_id}' from {source}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to reschedule task '{task_id}' from {source}."
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
    # 验证并发数量配置
    if config_item.key == "key_validation_concurrent_count":
        try:
            concurrent_count = int(config_item.value)
            if concurrent_count < 1:
                raise HTTPException(
                    status_code=400, 
                    detail="Key validation concurrent count must be at least 1"
                )
            elif concurrent_count > 10:
                raise HTTPException(
                    status_code=400, 
                    detail="Key validation concurrent count cannot exceed 10"
                )
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail="Key validation concurrent count must be a valid integer"
            )
    
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
    # 验证并发数量配置
    if key == "key_validation_concurrent_count":
        try:
            concurrent_count = int(config_update.value)
            if concurrent_count < 1:
                raise HTTPException(
                    status_code=400, 
                    detail="Key validation concurrent count must be at least 1"
                )
            elif concurrent_count > 10:
                raise HTTPException(
                    status_code=400, 
                    detail="Key validation concurrent count cannot exceed 10"
                )
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail="Key validation concurrent count must be a valid integer"
            )
    
    # 只有登录用户才能执行此操作
    updated = crud.config.update_config_value(
        db, key, config_update.value, current_user.id
    )
    db.commit()
    if not updated:
        raise HTTPException(status_code=404, detail=f"Config key '{key}' not found")

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
    # 验证并发数量配置
    for item in request_data.items:
        if item.key == "key_validation_concurrent_count":
            try:
                concurrent_count = int(item.value)
                if concurrent_count < 1:
                    raise HTTPException(
                        status_code=400, 
                        detail="Key validation concurrent count must be at least 1"
                    )
                elif concurrent_count > 10:
                    raise HTTPException(
                        status_code=400, 
                        detail="Key validation concurrent count cannot exceed 10"
                    )
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail="Key validation concurrent count must be a valid integer"
                )
    
    crud.config.bulk_save_config_items(db, request_data.items, current_user.id)
    db.commit()

    all_configs = {item.key: item.value for item in crud.config.get_all_config(db)}

    active_interval = int(all_configs.get("key_validation_active_interval_seconds", 300))
    exhausted_interval = all_configs.get("key_validation_exhausted_interval_seconds")
    error_interval = all_configs.get("key_validation_error_interval_seconds")

    _reschedule_task(
        "key_validation_active_task",
        validate_active_api_keys_task,
        str(active_interval),
        300,
        "bulk_save",
    )

    _reschedule_task(
        "key_validation_exhausted_task",
        validate_exhausted_api_keys_task,
        exhausted_interval,
        active_interval,
        "bulk_save",
    )

    _reschedule_task(
        "key_validation_error_task",
        validate_error_api_keys_task,
        error_interval,
        0,
        "bulk_save",
    )

    return {"detail": f"Successfully processed {len(request_data.items)} config items."}
