import logging
import json
import time
from typing import Optional, List
import redis

from ..core.config import settings

logger = logging.getLogger(__name__)

# Redis客户端用于缓存活跃API keys
_redis_client = None

# 缓存配置
ACTIVE_KEYS_CACHE_KEY = "active_api_keys_cache"
ACTIVE_KEYS_CACHE_TTL = 300  # 5分钟缓存
ACTIVE_KEYS_LAST_UPDATE_KEY = "active_api_keys_last_update"


def get_redis_client():
    """获取Redis客户端实例"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )
    return _redis_client


def get_cached_active_api_key_ids() -> Optional[List[int]]:
    """
    从Redis缓存获取活跃API key IDs列表
    
    Returns:
        Optional[List[int]]: 活跃API key IDs列表，如果缓存不存在或过期则返回None
    """
    try:
        redis_client = get_redis_client()
        
        # 检查缓存是否存在
        cached_data = redis_client.get(ACTIVE_KEYS_CACHE_KEY)
        if not cached_data:
            logger.debug("No cached active API keys found")
            return None
        
        # 检查缓存是否过期
        last_update = redis_client.get(ACTIVE_KEYS_LAST_UPDATE_KEY)
        if last_update:
            last_update_time = float(last_update)
            if time.time() - last_update_time > ACTIVE_KEYS_CACHE_TTL:
                logger.debug("Cached active API keys expired")
                return None
        
        # 解析缓存数据
        key_ids = json.loads(cached_data)
        logger.debug(f"🎯 [CACHE] Retrieved {len(key_ids)} active API key IDs from cache")
        return key_ids
        
    except Exception as e:
        logger.warning(f"⚠️ [CACHE] Failed to get cached active API keys: {e}")
        return None


def cache_active_api_key_ids(key_ids: List[int]):
    """
    将活跃API key IDs列表缓存到Redis
    
    Args:
        key_ids: 活跃API key IDs列表
    """
    try:
        redis_client = get_redis_client()
        
        # 缓存数据
        cached_data = json.dumps(key_ids)
        redis_client.setex(ACTIVE_KEYS_CACHE_KEY, ACTIVE_KEYS_CACHE_TTL * 2, cached_data)  # 设置更长的TTL防止意外过期
        
        # 记录更新时间
        redis_client.setex(ACTIVE_KEYS_LAST_UPDATE_KEY, ACTIVE_KEYS_CACHE_TTL * 2, str(time.time()))
        
        logger.info(f"💾 [CACHE] Cached {len(key_ids)} active API key IDs to Redis")
        
    except Exception as e:
        logger.error(f"❌ [CACHE] Failed to cache active API keys: {e}")


def invalidate_active_api_keys_cache():
    """
    使活跃API keys缓存失效
    """
    try:
        redis_client = get_redis_client()
        redis_client.delete(ACTIVE_KEYS_CACHE_KEY, ACTIVE_KEYS_LAST_UPDATE_KEY)
        logger.info("🗑️ [CACHE] Invalidated active API keys cache")
    except Exception as e:
        logger.error(f"❌ [CACHE] Failed to invalidate active API keys cache: {e}")