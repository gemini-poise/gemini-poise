import re
from typing import List, Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ... import crud, schemas
from ...core.security import user_dependency, db_dependency
from ...schemas.schemas import (
    ApiKey,
    ApiKeyCreate,
    ApiKeyUpdate,
    ApiKeyBulkAddRequest,
    ApiKeyAddListRequest,
    ApiKeyBulkAddResponse,
    ApiKeyPaginationParams,
    PaginatedApiKeyResponse,
    ApiCallStatistics,
    ApiKeyBulkCheckRequest,
    ApiKeyBulkCheckResponse,
    ApiKeyCheckResult,
    ApiCallLogResponse,
    KeyStatistics,
    KeySurvivalStatisticsResponse,
)
from ...tasks.key_validation import check_keys_validity

router = APIRouter(prefix="/api_keys", tags=["API Keys"])


@router.get("/paginated", response_model=PaginatedApiKeyResponse)
async def list_api_keys_paginated(
    pagination_params: Annotated[ApiKeyPaginationParams, Depends()],
    db: db_dependency,
    current_user: user_dependency,
):
    """
    获取分页后的 API Key 列表。需要登录。
    """
    # 只有登录用户才能执行此操作

    items, total = crud.api_keys.get_api_keys_paginated(
        db,
        page=pagination_params.page,
        page_size=pagination_params.page_size,
        search_key=pagination_params.search_key,
        min_failed_count=pagination_params.min_failed_count,
        status=pagination_params.status,
    )

    paginated_items = [schemas.ApiKey.model_validate(item) for item in items]

    return PaginatedApiKeyResponse(total=total, items=paginated_items)


@router.post("/", response_model=ApiKey)
async def create_api_key(
    api_key: ApiKeyCreate, db: db_dependency, current_user: user_dependency
):
    """
    创建一个新的 API Key。需要登录。
    """
    # 只有登录用户才能执行此操作
    # current_user 包含了当前用户对象，你可以在这里根据用户角色等进行权限检查
    # 例如：if not current_user.is_admin: raise HTTPException(...)
    created_key = crud.api_keys.create_api_key(db=db, api_key=api_key)
    if created_key is None:
        existing_key = crud.api_keys.get_api_key_by_value(db, api_key.key_value)
        return existing_key

    db.commit()
    db.refresh(created_key)
    return created_key


@router.get("/", response_model=List[ApiKey])
async def list_api_keys(
    db: db_dependency, current_user: user_dependency, skip: int = 0, limit: int = 100
):
    """
    获取 API Key 列表。需要登录。
    """
    # 只有登录用户才能执行此操作
    _ = current_user
    api_keys = crud.api_keys.get_api_keys(db, skip=skip, limit=limit)
    return api_keys


@router.get("/{api_key_id}", response_model=ApiKey)
async def get_api_key(
    api_key_id: int, db: db_dependency, current_user: user_dependency
):
    """
    根据 ID 获取单个 API Key。需要登录。
    """
    # 只有登录用户才能执行此操作
    _ = current_user
    db_api_key = crud.api_keys.get_api_key(db, api_key_id=api_key_id)
    if db_api_key is None:
        raise HTTPException(status_code=404, detail="API Key not found")
    return db_api_key


@router.put("/{api_key_id}", response_model=ApiKey)
async def update_api_key(
    api_key_id: int,
    api_key_update: ApiKeyUpdate,
    db: db_dependency,
    current_user: user_dependency,
):
    """
    更新 API Key 信息。需要登录。
    """
    # 只有登录用户才能执行此操作
    _ = current_user
    db_api_key = crud.api_keys.update_api_key(
        db, api_key_id=api_key_id, api_key_update=api_key_update
    )
    if db_api_key is None:
        raise HTTPException(status_code=404, detail="API Key not found")
    return db_api_key


@router.delete("/bulk-delete", status_code=status.HTTP_200_OK)
async def bulk_delete_api_keys(
    api_key_ids: List[int], db: db_dependency, current_user: user_dependency
):
    """
    批量删除 API Key。需要登录。
    """
    # 只有登录用户才能执行此操作
    _ = current_user

    deleted_count = crud.api_keys.bulk_delete_api_keys(db, api_key_ids)
    crud.api_keys.delete_api_call_logs_by_api_key_ids(db, api_key_ids)

    return {"detail": f"Successfully deleted {deleted_count} API Key(s)"}


@router.delete("/{api_key_id}")
async def delete_api_key(
    api_key_id: int, db: db_dependency, current_user: user_dependency
):
    """
    删除 API Key。需要登录。
    """
    # 只有登录用户才能执行此操作
    _ = current_user
    db_api_key = crud.api_keys.delete_api_key(db, api_key_id=api_key_id)
    if db_api_key is None:
        raise HTTPException(status_code=404, detail="API Key not found")
    crud.api_keys.delete_api_call_logs_by_api_key_ids(db, [api_key_id])
    return {"detail": "API Key deleted"}


@router.post(
    "/bulk-add", response_model=ApiKeyBulkAddResponse, status_code=status.HTTP_200_OK
)
async def bulk_add_api_keys(
    request_data: ApiKeyBulkAddRequest, db: db_dependency, current_user: user_dependency
):
    """
    批量添加 API Key。支持逗号或换行符分隔。如果 Key 存在则跳过。需要登录。
    """
    # 只有登录用户才能执行此操作
    _ = current_user

    key_values = re.split(r"[,\n]+", request_data.keys_string)
    key_values = [key.strip() for key in key_values if key.strip()]

    total_processed = len(key_values)
    total_added = crud.api_keys.bulk_add_api_keys(db, key_values)
    db.commit()

    return ApiKeyBulkAddResponse(
        total_processed=total_processed, total_added=total_added
    )


@router.post(
    "/bulk-check",
    response_model=ApiKeyBulkCheckResponse,
    status_code=status.HTTP_200_OK,
)
async def bulk_check_api_keys(
    request_data: ApiKeyBulkCheckRequest,
    db: db_dependency,
    current_user: user_dependency,
):
    """
    批量检测 API Key 的有效性。需要登录。
    """
    _ = current_user

    # 调用 key_validation 模块中的函数进行实际检测
    check_results = check_keys_validity(db, request_data.key_ids)
    
    # 提交数据库更改
    db.commit()

    # 将检测结果转换为 ApiKeyCheckResult 列表
    results = [ApiKeyCheckResult(**res) for res in check_results]

    return ApiKeyBulkCheckResponse(results=results)


@router.post(
    "/check/{api_key_id}",
    response_model=ApiKeyCheckResult,
    status_code=status.HTTP_200_OK,
)
async def check_single_api_key(
    api_key_id: int, db: db_dependency, current_user: user_dependency
):
    """
    检测单个 API Key 的有效性。需要登录。
    """
    _ = current_user

    # 调用 key_validation 模块中的函数进行实际检测
    check_results = check_keys_validity(db, [api_key_id])
    
    # 提交数据库更改
    db.commit()

    if not check_results:
        raise HTTPException(
            status_code=404, detail="API Key not found or check failed."
        )

    return ApiKeyCheckResult(**check_results[0])


@router.get("/statistics/keys", response_model=KeyStatistics)
async def get_key_statistics_endpoint(db: db_dependency, current_user: user_dependency):
    """
    获取 API Key 统计数据（总数、有效、无效）。需要登录。
    """
    _ = current_user
    statistics = crud.api_keys.get_key_statistics(db)
    return statistics


@router.get("/statistics/calls", response_model=ApiCallStatistics)
async def get_api_call_statistics(db: db_dependency, current_user: user_dependency):
    """
    获取 API 调用统计数据。需要登录。
    """
    _ = current_user
    statistics = crud.api_keys.get_api_call_statistics(db)
    return statistics


@router.get("/statistics/calls_by_minute", response_model=ApiCallLogResponse)
async def get_api_call_logs_by_minute_endpoint(
    db: db_dependency, current_user: user_dependency, hours_ago: int = 24
):
    """
    获取按分钟统计的 API 调用日志。需要登录。
    """
    _ = current_user
    logs = crud.api_keys.get_api_call_logs_by_minute(db, hours_ago)
    return ApiCallLogResponse(logs=logs)


@router.post(
    "/add-list", response_model=ApiKeyBulkAddResponse, status_code=status.HTTP_200_OK
)
async def add_api_keys_from_list(
    request_data: ApiKeyAddListRequest, db: db_dependency, current_user: user_dependency
):
    """
    批量添加 API Key (列表)。接收 Key 字符串列表。如果 Key 存在则跳过。需要登录。
    """
    # 只有登录用户才能执行此操作
    _ = current_user
    key_values = request_data.keys
    total_processed = len(key_values)
    total_added = crud.api_keys.bulk_add_api_keys(db, key_values)
    db.commit()

    return ApiKeyBulkAddResponse(
        total_processed=total_processed, total_added=total_added
    )


@router.get("/statistics/survival", response_model=KeySurvivalStatisticsResponse)
async def get_key_survival_statistics(db: db_dependency, current_user: user_dependency):
    """
    获取最近60次密钥存活统计数据。需要登录。
    """
    _ = current_user
    statistics = crud.api_keys.get_key_survival_statistics(db, limit=60)
    return KeySurvivalStatisticsResponse(statistics=statistics)
