"""
Token Bucket 管理 API 端点
"""

import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_user
from ...models.models import User
from ...crud.api_keys import (
    get_api_key_with_token_bucket,
    get_api_key_with_fallback,
    configure_api_key_token_bucket,
    reset_api_key_token_bucket,
    get_api_key_token_info,
    batch_configure_token_buckets,
    cleanup_token_buckets,
    get_active_api_keys
)
from ...utils.token_bucket_config import TokenBucketConfig, validate_token_bucket_config
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


class TokenBucketConfigModel(BaseModel):
    """Token Bucket 配置模型"""
    default_capacity: int = Field(default=10, ge=1, le=1000, description="默认令牌桶容量")
    default_refill_rate: float = Field(default=1.0, ge=0.1, le=100.0, description="默认令牌补充速率（每秒）")
    high_priority_capacity: int = Field(default=20, ge=1, le=1000, description="高优先级令牌桶容量")
    high_priority_refill_rate: float = Field(default=2.0, ge=0.1, le=100.0, description="高优先级令牌补充速率（每秒）")
    low_priority_capacity: int = Field(default=5, ge=1, le=1000, description="低优先级令牌桶容量")
    low_priority_refill_rate: float = Field(default=0.5, ge=0.1, le=100.0, description="低优先级令牌补充速率（每秒）")
    bucket_ttl: int = Field(default=3600, ge=60, le=86400, description="令牌桶TTL（秒）")
    enable_token_bucket: bool = Field(default=True, description="是否启用Token Bucket")
    fallback_to_random: bool = Field(default=True, description="是否回退到随机选择")
    cleanup_interval: int = Field(default=300, ge=60, le=3600, description="清理间隔（秒）")


class ApiKeyTokenBucketConfig(BaseModel):
    """单个 API Key 的 Token Bucket 配置"""
    capacity: int = Field(ge=1, le=1000, description="令牌桶容量")
    refill_rate: float = Field(ge=0.1, le=100.0, description="令牌补充速率（每秒）")


class BatchTokenBucketConfig(BaseModel):
    """批量 Token Bucket 配置"""
    capacity: int = Field(ge=1, le=1000, description="令牌桶容量")
    refill_rate: float = Field(ge=0.1, le=100.0, description="令牌补充速率（每秒）")


class TokenBucketStatus(BaseModel):
    """Token Bucket 状态"""
    api_key_id: int
    capacity: int
    tokens: float
    refill_rate: float
    last_refill: float


@router.get("/config", response_model=Dict[str, Any])
async def get_token_bucket_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取 Token Bucket 配置"""
    try:
        config = TokenBucketConfig.get_all_config(db)
        return {
            "success": True,
            "data": config,
            "message": "获取配置成功"
        }
    except Exception as e:
        logger.error(f"Failed to get token bucket config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取配置失败"
        )


@router.put("/config")
async def update_token_bucket_config(
    config: TokenBucketConfigModel,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新 Token Bucket 配置"""
    try:
        # 验证配置
        config_dict = config.model_dump()
        errors = validate_token_bucket_config(config_dict)
        
        if errors:
            return {
                "success": False,
                "errors": errors,
                "message": "配置验证失败"
            }
        
        # 更新配置
        for key, value in config_dict.items():
            TokenBucketConfig.set_config(db, key, value, current_user.id)
        
        return {
            "success": True,
            "message": "配置更新成功"
        }
        
    except Exception as e:
        logger.error(f"Failed to update token bucket config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新配置失败"
        )


@router.post("/api-keys/{api_key_id}/configure")
async def configure_api_key_bucket(
    api_key_id: int,
    config: ApiKeyTokenBucketConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """配置单个 API Key 的 Token Bucket"""
    try:
        configure_api_key_token_bucket(
            api_key_id,
            capacity=config.capacity,
            refill_rate=config.refill_rate
        )
        
        return {
            "success": True,
            "message": f"API Key {api_key_id} 的 Token Bucket 配置成功"
        }
        
    except Exception as e:
        logger.error(f"Failed to configure token bucket for API key {api_key_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="配置失败"
        )


@router.post("/api-keys/{api_key_id}/reset")
async def reset_api_key_bucket(
    api_key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """重置单个 API Key 的 Token Bucket"""
    try:
        reset_api_key_token_bucket(api_key_id)
        
        return {
            "success": True,
            "message": f"API Key {api_key_id} 的 Token Bucket 重置成功"
        }
        
    except Exception as e:
        logger.error(f"Failed to reset token bucket for API key {api_key_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="重置失败"
        )


@router.get("/api-keys/{api_key_id}/status", response_model=TokenBucketStatus)
async def get_api_key_bucket_status(
    api_key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取单个 API Key 的 Token Bucket 状态"""
    try:
        token_info = get_api_key_token_info(api_key_id)
        
        if not token_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token Bucket 信息不存在"
            )
        
        return TokenBucketStatus(
            api_key_id=api_key_id,
            **token_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get token bucket status for API key {api_key_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取状态失败"
        )


@router.get("/api-keys/status", response_model=List[TokenBucketStatus])
async def get_all_api_keys_bucket_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有活跃 API Key 的 Token Bucket 状态"""
    try:
        active_keys = get_active_api_keys(db)
        statuses = []
        
        for api_key in active_keys:
            try:
                token_info = get_api_key_token_info(api_key.id)
                if token_info:
                    statuses.append(TokenBucketStatus(
                        api_key_id=api_key.id,
                        **token_info
                    ))
            except Exception as e:
                logger.warning(f"Failed to get token info for API key {api_key.id}: {e}")
                continue
        
        return statuses
        
    except Exception as e:
        logger.error(f"Failed to get all token bucket statuses: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取状态失败"
        )


@router.post("/batch-configure")
async def batch_configure_buckets(
    config: BatchTokenBucketConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量配置所有活跃 API Key 的 Token Bucket"""
    try:
        configured_count = batch_configure_token_buckets(
            db,
            capacity=config.capacity,
            refill_rate=config.refill_rate
        )
        
        return {
            "success": True,
            "configured_count": configured_count,
            "message": f"成功配置 {configured_count} 个 API Key 的 Token Bucket"
        }
        
    except Exception as e:
        logger.error(f"Failed to batch configure token buckets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="批量配置失败"
        )


@router.post("/cleanup")
async def cleanup_expired_buckets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """清理过期的 Token Bucket"""
    try:
        cleanup_token_buckets()
        
        return {
            "success": True,
            "message": "Token Bucket 清理完成"
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup token buckets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="清理失败"
        )


@router.post("/test-selection")
async def test_token_bucket_selection(
    required_tokens: int = 1,
    use_token_bucket: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """测试 Token Bucket API Key 选择"""
    try:
        if use_token_bucket:
            api_key = get_api_key_with_token_bucket(db, required_tokens)
        else:
            api_key = get_api_key_with_fallback(db, required_tokens, use_token_bucket=False)
        
        if api_key:
            # 获取令牌信息
            token_info = get_api_key_token_info(api_key.id)
            
            return {
                "success": True,
                "selected_api_key_id": api_key.id,
                "key_value_preview": f"{api_key.key_value[:8]}...",
                "token_info": token_info,
                "message": "API Key 选择成功"
            }
        else:
            return {
                "success": False,
                "message": "没有可用的 API Key"
            }
            
    except Exception as e:
        logger.error(f"Failed to test token bucket selection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="测试失败"
        )


@router.get("/statistics")
async def get_token_bucket_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取 Token Bucket 统计信息"""
    try:
        active_keys = get_active_api_keys(db)
        total_keys = len(active_keys)
        
        total_capacity = 0
        total_tokens = 0
        configured_keys = 0
        
        for api_key in active_keys:
            try:
                token_info = get_api_key_token_info(api_key.id)
                if token_info:
                    configured_keys += 1
                    total_capacity += token_info.get('capacity', 0)
                    total_tokens += token_info.get('tokens', 0)
            except Exception:
                continue
        
        avg_capacity = total_capacity / configured_keys if configured_keys > 0 else 0
        avg_tokens = total_tokens / configured_keys if configured_keys > 0 else 0
        utilization_rate = (total_capacity - total_tokens) / total_capacity if total_capacity > 0 else 0
        
        return {
            "success": True,
            "data": {
                "total_api_keys": total_keys,
                "configured_keys": configured_keys,
                "total_capacity": total_capacity,
                "total_available_tokens": total_tokens,
                "average_capacity": round(avg_capacity, 2),
                "average_available_tokens": round(avg_tokens, 2),
                "utilization_rate": round(utilization_rate * 100, 2)  # 百分比
            },
            "message": "统计信息获取成功"
        }
        
    except Exception as e:
        logger.error(f"Failed to get token bucket statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取统计信息失败"
        )