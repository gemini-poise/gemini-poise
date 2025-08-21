import logging
import random
from typing import Optional, List

from sqlalchemy.orm import Session

from ..models import models
from ..utils.token_bucket import token_bucket_manager
from .api_keys_cache import get_cached_active_api_key_ids, cache_active_api_key_ids, invalidate_active_api_keys_cache
from .api_keys_proxy import get_active_api_keys
from .api_keys_basic import get_api_key

logger = logging.getLogger(__name__)

# 采样配置
INITIAL_SAMPLE_SIZE = 200  # 初始采样大小
MAX_SAMPLE_SIZE = 1000     # 最大采样大小
SAMPLE_EXPANSION_FACTOR = 2  # 采样扩展倍数


def get_active_api_key_ids_optimized(db: Session) -> List[int]:
    """
    优化版本：获取活跃API key IDs，优先使用缓存
    
    Args:
        db: 数据库会话
        
    Returns:
        List[int]: 活跃API key IDs列表
    """
    # 尝试从缓存获取
    cached_ids = get_cached_active_api_key_ids()
    if cached_ids is not None:
        logger.debug(f"🎯 [CACHE] Using cached active API key IDs: {len(cached_ids)} keys")
        return cached_ids
    
    # 缓存未命中，从数据库查询
    logger.info("🔍 [DB] Cache miss, querying active API keys from database")
    active_keys = get_active_api_keys(db)
    key_ids = [key.id for key in active_keys]
    
    # 更新缓存
    cache_active_api_key_ids(key_ids)
    
    logger.info(f"📊 [DB] Retrieved {len(key_ids)} active API key IDs from database and cached")
    return key_ids


def smart_sample_api_keys(key_ids: List[int], sample_size: int) -> List[int]:
    """
    智能采样API keys
    
    Args:
        key_ids: 所有可用的API key IDs
        sample_size: 采样大小
        
    Returns:
        List[int]: 采样后的API key IDs
    """
    if len(key_ids) <= sample_size:
        return key_ids
    
    # 随机采样
    sampled_ids = random.sample(key_ids, sample_size)
    logger.debug(f"🎲 [SAMPLE] Sampled {len(sampled_ids)} keys from {len(key_ids)} total keys")
    return sampled_ids


def get_api_key_with_token_bucket(db: Session, required_tokens: int = 1) -> Optional[models.ApiKey]:
    """
    使用 token bucket 算法获取可用的 API Key（优化版本）。
    优先选择令牌充足的 key，实现智能负载均衡和采样优化。
    
    Args:
        db: 数据库会话
        required_tokens: 所需令牌数量，默认为1
        
    Returns:
        Optional[models.ApiKey]: 可用的 API Key，如果没有则返回 None
    """
    logger.info(f"🚀 [OPTIMIZED] Attempting to get API key using optimized token bucket algorithm, required tokens: {required_tokens}")
    
    # 使用优化的方法获取活跃API key IDs（优先使用缓存）
    active_key_ids = get_active_api_key_ids_optimized(db)
    if not active_key_ids:
        logger.warning("❌ [OPTIMIZED] No active API keys found")
        return None
    
    logger.info(f"📊 [OPTIMIZED] Found {len(active_key_ids)} active API keys (from cache or database)")
    
    # 智能采样策略：渐进式扩展
    current_sample_size = INITIAL_SAMPLE_SIZE
    max_attempts = 3
    
    for attempt in range(max_attempts):
        # 采样API keys
        sampled_key_ids = smart_sample_api_keys(active_key_ids, current_sample_size)
        logger.info(f"🎲 [OPTIMIZED] Attempt {attempt + 1}: Sampling {len(sampled_key_ids)} keys from {len(active_key_ids)} total")
        
        # 批量检查token可用性
        available_key_ids = token_bucket_manager.get_available_api_keys(sampled_key_ids, required_tokens)
        
        if available_key_ids:
            logger.info(f"✅ [OPTIMIZED] Found {len(available_key_ids)} available keys in sample")
            
            # 选择最佳API key
            selected_key_id = _select_best_api_key(available_key_ids)
            
            # 尝试消耗token
            if token_bucket_manager.consume_token(selected_key_id, required_tokens):
                # 只查询选中的API key，避免查询所有keys
                selected_key = get_api_key(db, selected_key_id)
                if selected_key and selected_key.status == "active":
                    logger.info(f"🎯 [OPTIMIZED] Successfully selected API key {selected_key_id} using optimized token bucket (attempt {attempt + 1})")
                    return selected_key
                else:
                    logger.warning(f"⚠️ [OPTIMIZED] Selected API key {selected_key_id} is no longer active, invalidating cache")
                    # API key状态已变化，使缓存失效
                    invalidate_active_api_keys_cache()
                    break
            else:
                logger.warning(f"❌ [OPTIMIZED] Failed to consume tokens for selected API key {selected_key_id}")
        else:
            logger.warning(f"⚠️ [OPTIMIZED] No available keys in sample of {len(sampled_key_ids)} keys")
        
        # 扩展采样大小，但不超过总数和最大限制
        if current_sample_size < len(active_key_ids) and current_sample_size < MAX_SAMPLE_SIZE:
            current_sample_size = min(current_sample_size * SAMPLE_EXPANSION_FACTOR, len(active_key_ids), MAX_SAMPLE_SIZE)
            logger.info(f"📈 [OPTIMIZED] Expanding sample size to {current_sample_size} for next attempt")
        else:
            logger.warning(f"🔄 [OPTIMIZED] Reached maximum sample size, no more expansion possible")
            break
    
    logger.warning(f"❌ [OPTIMIZED] Failed to find available API key after {max_attempts} attempts")
    return None


def _select_best_api_key(available_key_ids: List[int]) -> int:
    """
    从可用的 API key 中选择最佳的一个。
    优化版本：使用批量获取令牌信息，减少Redis查询次数。
    
    Args:
        available_key_ids: 可用的 API key ID 列表
        
    Returns:
        int: 选中的 API key ID
    """
    if len(available_key_ids) == 1:
        return available_key_ids[0]
    
    # 批量获取所有key的令牌信息
    tokens_map = token_bucket_manager.get_available_tokens_batch(available_key_ids)
    
    key_weights = []
    for key_id in available_key_ids:
        tokens = tokens_map.get(key_id, 0.0)
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
    from .api_keys_proxy import get_random_active_api_key_from_db
    
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
    from .api_keys_proxy import get_random_active_api_key_from_db
    
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