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

# 缓存统计配置
CACHE_STATS_KEY = "api_keys_cache_stats"
CACHE_STATS_TTL = 86400 * 7  # 7天统计数据
CACHE_STATS_RESET_KEY = "api_keys_cache_stats_reset"


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


def get_cached_active_api_key_ids(record_stats: bool = True) -> Optional[List[int]]:
    """
    从Redis缓存获取活跃API key IDs列表
    
    Args:
        record_stats: 是否记录缓存统计，默认为True
    
    Returns:
        Optional[List[int]]: 活跃API key IDs列表，如果缓存不存在或过期则返回None
    """
    try:
        redis_client = get_redis_client()
        
        # 检查缓存是否存在
        cached_data = redis_client.get(ACTIVE_KEYS_CACHE_KEY)
        if not cached_data:
            logger.debug("No cached active API keys found")
            if record_stats:
                record_cache_access(hit=False)
            return None
        
        # 检查缓存是否过期
        last_update = redis_client.get(ACTIVE_KEYS_LAST_UPDATE_KEY)
        if last_update:
            last_update_time = float(last_update)
            if time.time() - last_update_time > ACTIVE_KEYS_CACHE_TTL:
                logger.debug("Cached active API keys expired")
                if record_stats:
                    record_cache_access(hit=False)
                return None
        
        # 解析缓存数据
        key_ids = json.loads(cached_data)
        logger.debug(f"🎯 [CACHE] Retrieved {len(key_ids)} active API key IDs from cache")
        if record_stats:
            record_cache_access(hit=True)
        return key_ids
        
    except Exception as e:
        logger.warning(f"⚠️ [CACHE] Failed to get cached active API keys: {e}")
        if record_stats:
            record_cache_access(hit=False)
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


def record_cache_access(hit: bool):
    """
    记录缓存访问统计
    
    Args:
        hit: 是否命中缓存
    """
    try:
        redis_client = get_redis_client()
        
        # 使用 Redis pipeline 和原子操作来更新统计
        with redis_client.pipeline() as pipe:
            while True:
                try:
                    # 监视键以确保原子性
                    pipe.watch(CACHE_STATS_KEY)
                    
                    # 获取当前统计数据
                    stats_data = pipe.get(CACHE_STATS_KEY)
                    if stats_data:
                        stats = json.loads(stats_data)
                    else:
                        stats = {
                            "total_requests": 0,
                            "cache_hits": 0,
                            "cache_misses": 0,
                            "start_time": time.time(),
                            "last_reset_time": None
                        }
                    
                    # 更新统计
                    stats["total_requests"] += 1
                    if hit:
                        stats["cache_hits"] += 1
                    else:
                        stats["cache_misses"] += 1
                    
                    # 开始事务
                    pipe.multi()
                    pipe.setex(CACHE_STATS_KEY, CACHE_STATS_TTL, json.dumps(stats))
                    pipe.execute()
                    break
                    
                except redis.WatchError:
                    # 如果键被其他客户端修改，重试
                    continue
        
    except Exception as e:
        logger.warning(f"⚠️ [CACHE] Failed to record cache access: {e}")


def get_cache_statistics():
    """
    获取缓存统计数据
    
    Returns:
        dict: 包含缓存统计信息的字典
    """
    try:
        redis_client = get_redis_client()
        
        stats_data = redis_client.get(CACHE_STATS_KEY)
        if not stats_data:
            return {
                "total_requests": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "hit_rate": 0.0,
                "start_time": None,
                "last_reset_time": None,
                "duration_hours": 0.0
            }
        
        stats = json.loads(stats_data)
        
        # 计算命中率
        total = stats.get("total_requests", 0)
        hits = stats.get("cache_hits", 0)
        hit_rate = (hits / total * 100) if total > 0 else 0.0
        
        # 计算运行时长
        start_time = stats.get("start_time", time.time())
        duration_hours = (time.time() - start_time) / 3600
        
        return {
            "total_requests": total,
            "cache_hits": hits,
            "cache_misses": stats.get("cache_misses", 0),
            "hit_rate": round(hit_rate, 2),
            "start_time": start_time,
            "last_reset_time": stats.get("last_reset_time"),
            "duration_hours": round(duration_hours, 2)
        }
        
    except Exception as e:
        logger.error(f"❌ [CACHE] Failed to get cache statistics: {e}")
        return {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "hit_rate": 0.0,
            "start_time": None,
            "last_reset_time": None,
            "duration_hours": 0.0
        }


def reset_cache_statistics():
    """
    重置缓存统计数据
    """
    try:
        redis_client = get_redis_client()
        
        reset_stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "start_time": time.time(),
            "last_reset_time": time.time()
        }
        
        redis_client.setex(CACHE_STATS_KEY, CACHE_STATS_TTL, json.dumps(reset_stats))
        logger.info("🔄 [CACHE] Reset cache statistics")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ [CACHE] Failed to reset cache statistics: {e}")
        return False