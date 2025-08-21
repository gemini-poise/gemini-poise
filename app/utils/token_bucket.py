import time
import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
import redis
from ..core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """令牌桶数据结构"""
    capacity: int  # 桶容量
    tokens: float  # 当前令牌数
    refill_rate: float  # 每秒补充令牌数
    last_refill: float  # 上次补充时间戳
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TokenBucket':
        return cls(**data)


class TokenBucketManager:
    """令牌桶管理器，使用 Redis 存储状态"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        if redis_client is None:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
        else:
            self.redis_client = redis_client
        
        # 默认配置
        self.default_capacity = 20  # 默认桶容量
        self.default_refill_rate = 1.0  # 默认每秒补充1个令牌
        self.bucket_prefix = "token_bucket:api_key:"
        self.bucket_ttl = 3600  # 桶数据TTL（秒）
    
    def _get_bucket_key(self, api_key_id: int) -> str:
        """获取 Redis 中令牌桶的键名"""
        return f"{self.bucket_prefix}{api_key_id}"
    
    def _get_bucket(self, api_key_id: int) -> TokenBucket:
        """从 Redis 获取令牌桶，如果不存在则创建新的"""
        bucket_key = self._get_bucket_key(api_key_id)
        bucket_data = self.redis_client.get(bucket_key)
        
        if bucket_data:
            try:
                data = json.loads(bucket_data)
                return TokenBucket.from_dict(data)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse bucket data for key {api_key_id}: {e}")
        
        # 创建新的令牌桶
        current_time = time.time()
        return TokenBucket(
            capacity=self.default_capacity,
            tokens=self.default_capacity,  # 初始时桶是满的
            refill_rate=self.default_refill_rate,
            last_refill=current_time
        )
    
    def _save_bucket(self, api_key_id: int, bucket: TokenBucket):
        """将令牌桶保存到 Redis"""
        bucket_key = self._get_bucket_key(api_key_id)
        bucket_data = json.dumps(bucket.to_dict())
        self.redis_client.setex(bucket_key, self.bucket_ttl, bucket_data)
    
    def _refill_bucket(self, bucket: TokenBucket) -> TokenBucket:
        """补充令牌桶中的令牌"""
        current_time = time.time()
        time_passed = current_time - bucket.last_refill
        
        if time_passed > 0:
            # 计算应该补充的令牌数
            tokens_to_add = time_passed * bucket.refill_rate
            bucket.tokens = min(bucket.capacity, bucket.tokens + tokens_to_add)
            bucket.last_refill = current_time
        
        return bucket
    
    def _consume_token_lua_script(self):
        """获取Lua脚本用于原子性令牌消耗"""
        return """
        local bucket_key = KEYS[1]
        local tokens_to_consume = tonumber(ARGV[1])
        local current_time = tonumber(ARGV[2])
        local capacity = tonumber(ARGV[3])
        local refill_rate = tonumber(ARGV[4])
        local ttl = tonumber(ARGV[5])
        
        local bucket_data = redis.call('GET', bucket_key)
        local bucket
        
        if bucket_data then
            bucket = cjson.decode(bucket_data)
        else
            bucket = {
                capacity = capacity,
                tokens = capacity,
                refill_rate = refill_rate,
                last_refill = current_time
            }
        end
        
        -- 补充令牌
        local time_passed = current_time - bucket.last_refill
        if time_passed > 0 then
            local tokens_to_add = time_passed * bucket.refill_rate
            bucket.tokens = math.min(bucket.capacity, bucket.tokens + tokens_to_add)
            bucket.last_refill = current_time
        end
        
        -- 尝试消耗令牌
        local success = false
        if bucket.tokens >= tokens_to_consume then
            bucket.tokens = bucket.tokens - tokens_to_consume
            success = true
        end
        
        -- 保存桶状态
        redis.call('SETEX', bucket_key, ttl, cjson.encode(bucket))
        
        return {success and 1 or 0, bucket.tokens}
        """
    
    def consume_token(self, api_key_id: int, tokens: int = 1) -> bool:
        """
        尝试从令牌桶中消耗指定数量的令牌（优化版本，使用Lua脚本）
        
        Args:
            api_key_id: API key ID
            tokens: 要消耗的令牌数量
            
        Returns:
            bool: 是否成功消耗令牌
        """
        try:
            # 尝试使用Lua脚本进行原子操作
            if hasattr(self, '_lua_script'):
                logger.info(f"🚀 [TOKEN BUCKET] Using optimized Lua script for API key {api_key_id}")
                bucket_key = self._get_bucket_key(api_key_id)
                current_time = time.time()
                
                result = self._lua_script(
                    keys=[bucket_key],
                    args=[tokens, current_time, self.default_capacity, self.default_refill_rate, self.bucket_ttl]
                )
                
                success = bool(result[0])
                remaining_tokens = float(result[1])
                
                if success:
                    logger.info(f"✅ [TOKEN BUCKET] Successfully consumed {tokens} tokens for API key {api_key_id}, remaining: {remaining_tokens:.2f}")
                else:
                    logger.warning(f"❌ [TOKEN BUCKET] Insufficient tokens for API key {api_key_id}, available: {remaining_tokens:.2f}, required: {tokens}")
                
                return success
            else:
                # 回退到原有实现
                logger.info(f"⚠️ [TOKEN BUCKET] Using fallback implementation for API key {api_key_id}")
                bucket = self._get_bucket(api_key_id)
                bucket = self._refill_bucket(bucket)
                
                if bucket.tokens >= tokens:
                    bucket.tokens -= tokens
                    self._save_bucket(api_key_id, bucket)
                    logger.info(f"✅ [TOKEN BUCKET] Consumed {tokens} tokens for API key {api_key_id}, remaining: {bucket.tokens:.2f}")
                    return True
                else:
                    logger.warning(f"❌ [TOKEN BUCKET] Insufficient tokens for API key {api_key_id}, available: {bucket.tokens:.2f}, required: {tokens}")
                    return False
                
        except Exception as e:
            logger.error(f"💥 [TOKEN BUCKET] Error consuming token for API key {api_key_id}: {e}")
            return False
    
    def get_available_tokens(self, api_key_id: int) -> float:
        """获取指定 API key 的可用令牌数"""
        try:
            bucket = self._get_bucket(api_key_id)
            bucket = self._refill_bucket(bucket)
            self._save_bucket(api_key_id, bucket)
            return bucket.tokens
        except Exception as e:
            logger.error(f"Error getting available tokens for API key {api_key_id}: {e}")
            return 0.0
    
    def get_bucket_info(self, api_key_id: int) -> Dict[str, Any]:
        """获取令牌桶的详细信息"""
        try:
            bucket = self._get_bucket(api_key_id)
            bucket = self._refill_bucket(bucket)
            self._save_bucket(api_key_id, bucket)
            return bucket.to_dict()
        except Exception as e:
            logger.error(f"Error getting bucket info for API key {api_key_id}: {e}")
            return {}
    
    def reset_bucket(self, api_key_id: int):
        """重置令牌桶（填满令牌）"""
        try:
            bucket = self._get_bucket(api_key_id)
            bucket.tokens = bucket.capacity
            bucket.last_refill = time.time()
            self._save_bucket(api_key_id, bucket)
            logger.info(f"Reset token bucket for API key {api_key_id}")
        except Exception as e:
            logger.error(f"Error resetting bucket for API key {api_key_id}: {e}")
    
    def configure_bucket(self, api_key_id: int, capacity: int = None, refill_rate: float = None):
        """配置令牌桶参数"""
        try:
            bucket = self._get_bucket(api_key_id)
            
            if capacity is not None:
                bucket.capacity = capacity
                # 如果当前令牌数超过新容量，则调整
                bucket.tokens = min(bucket.tokens, capacity)
            
            if refill_rate is not None:
                bucket.refill_rate = refill_rate
            
            self._save_bucket(api_key_id, bucket)
            logger.info(f"Configured bucket for API key {api_key_id}: capacity={bucket.capacity}, refill_rate={bucket.refill_rate}")
            
        except Exception as e:
            logger.error(f"Error configuring bucket for API key {api_key_id}: {e}")
    
    def get_available_api_keys(self, api_key_ids: List[int], required_tokens: int = 1) -> List[int]:
        """
        获取有足够令牌的 API key 列表（优化版本，批量检查）
        
        Args:
            api_key_ids: API key ID 列表
            required_tokens: 所需令牌数
            
        Returns:
            List[int]: 有足够令牌的 API key ID 列表
        """
        if not api_key_ids:
            return []
        
        logger.info(f"🔍 [TOKEN BUCKET] Batch checking {len(api_key_ids)} API keys for {required_tokens} tokens")
        
        # 使用批量获取方法
        tokens_map = self.get_available_tokens_batch(api_key_ids)
        
        available_keys = []
        for api_key_id in api_key_ids:
            tokens = tokens_map.get(api_key_id, 0.0)
            if tokens >= required_tokens:
                available_keys.append(api_key_id)
                logger.debug(f"✅ [TOKEN BUCKET] API key {api_key_id} has {tokens:.2f} tokens (sufficient)")
            else:
                logger.debug(f"❌ [TOKEN BUCKET] API key {api_key_id} has {tokens:.2f} tokens (insufficient)")
        
        logger.info(f"📊 [TOKEN BUCKET] Batch check result: {len(available_keys)}/{len(api_key_ids)} keys have sufficient tokens")
        return available_keys
    
    def get_available_tokens_batch(self, api_key_ids: List[int]) -> Dict[int, float]:
        """
        批量获取多个 API key 的可用令牌数（优化版本，使用pipeline）
        
        Args:
            api_key_ids: API key ID 列表
            
        Returns:
            Dict[int, float]: API key ID 到可用令牌数的映射
        """
        if not api_key_ids:
            return {}
        
        logger.debug(f"🔍 [TOKEN BUCKET] Batch getting tokens for {len(api_key_ids)} API keys")
        
        tokens_map = {}
        current_time = time.time()
        
        # 批量获取所有桶的数据
        bucket_keys = [self._get_bucket_key(api_key_id) for api_key_id in api_key_ids]
        
        try:
            # 使用pipeline批量获取数据
            pipe = self.redis_client.pipeline()
            for key in bucket_keys:
                pipe.get(key)
            bucket_data_list = pipe.execute()
            
            # 处理每个桶的令牌数
            for api_key_id, bucket_data in zip(api_key_ids, bucket_data_list):
                try:
                    if bucket_data:
                        data = json.loads(bucket_data)
                        bucket = TokenBucket.from_dict(data)
                        
                        # 补充令牌
                        time_passed = current_time - bucket.last_refill
                        if time_passed > 0:
                            tokens_to_add = time_passed * bucket.refill_rate
                            bucket.tokens = min(bucket.capacity, bucket.tokens + tokens_to_add)
                        
                        tokens_map[api_key_id] = bucket.tokens
                        logger.debug(f"✅ [TOKEN BUCKET] API key {api_key_id} has {bucket.tokens:.2f} tokens")
                    else:
                        # 新桶默认是满的
                        tokens_map[api_key_id] = self.default_capacity
                        logger.debug(f"🆕 [TOKEN BUCKET] New bucket for API key {api_key_id} with {self.default_capacity} tokens")
                        
                except Exception as e:
                    logger.warning(f"⚠️ [TOKEN BUCKET] Error getting tokens for API key {api_key_id}: {e}")
                    tokens_map[api_key_id] = 0.0
            
            logger.debug(f"📊 [TOKEN BUCKET] Batch token retrieval completed for {len(tokens_map)} keys")
            return tokens_map
            
        except Exception as e:
            logger.error(f"💥 [TOKEN BUCKET] Error in batch token retrieval, falling back to individual checks: {e}")
            # 回退到逐个检查
            for api_key_id in api_key_ids:
                try:
                    tokens_map[api_key_id] = self.get_available_tokens(api_key_id)
                except Exception as individual_error:
                    logger.error(f"Error getting tokens for API key {api_key_id}: {individual_error}")
                    tokens_map[api_key_id] = 0.0
            
            return tokens_map
    
    def cleanup_expired_buckets(self):
        """清理过期的令牌桶（优化版本，使用SCAN避免阻塞）"""
        try:
            pattern = f"{self.bucket_prefix}*"
            current_time = time.time()
            total_deleted = 0
            cursor = 0
            
            while True:
                # 使用SCAN而不是KEYS，避免阻塞Redis
                cursor, keys = self.redis_client.scan(cursor, match=pattern, count=100)
                
                if keys:
                    expired_keys = []
                    
                    # 批量获取数据
                    pipe = self.redis_client.pipeline()
                    for key in keys:
                        pipe.get(key)
                    bucket_data_list = pipe.execute()
                    
                    # 检查过期
                    for key, bucket_data in zip(keys, bucket_data_list):
                        if bucket_data:
                            try:
                                data = json.loads(bucket_data)
                                bucket = TokenBucket.from_dict(data)
                                # 如果超过1小时没有使用，认为过期
                                if current_time - bucket.last_refill > 3600:
                                    expired_keys.append(key)
                            except (json.JSONDecodeError, TypeError):
                                expired_keys.append(key)
                        else:
                            # 数据已经不存在，可能是TTL过期了
                            expired_keys.append(key)
                    
                    # 批量删除过期的键
                    if expired_keys:
                        self.redis_client.delete(*expired_keys)
                        total_deleted += len(expired_keys)
                        logger.debug(f"Cleaned up {len(expired_keys)} expired buckets in this batch")
                
                if cursor == 0:
                    break
            
            if total_deleted > 0:
                logger.info(f"Cleaned up {total_deleted} expired token buckets")
            
            return total_deleted
                
        except Exception as e:
            logger.error(f"Error cleaning up expired buckets: {e}")
            return 0


class OptimizedTokenBucketManager(TokenBucketManager):
    """优化版令牌桶管理器，继承原有类并增强功能"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        super().__init__(redis_client)
        
        # 内存缓存，用于减少Redis查询
        self._token_cache = {}  # {api_key_id: (tokens, timestamp)}
        self._cache_ttl = 5  # 缓存5秒
        
        # 尝试注册Lua脚本
        try:
            self._lua_script = self.redis_client.register_script(self._consume_token_lua_script())
            logger.info("🚀 [TOKEN BUCKET] Optimized token bucket manager initialized with Lua script support and caching")
        except Exception as e:
            logger.warning(f"⚠️ [TOKEN BUCKET] Failed to register Lua script, falling back to original implementation: {e}")
            self._lua_script = None
    
    def _is_cache_valid(self, api_key_id: int) -> bool:
        """检查缓存是否有效"""
        if api_key_id not in self._token_cache:
            return False
        
        _, cached_time = self._token_cache[api_key_id]
        return time.time() - cached_time < self._cache_ttl
    
    def _get_cached_tokens(self, api_key_id: int) -> Optional[float]:
        """从缓存获取令牌数"""
        if self._is_cache_valid(api_key_id):
            tokens, _ = self._token_cache[api_key_id]
            return tokens
        return None
    
    def _cache_tokens(self, api_key_id: int, tokens: float):
        """缓存令牌数"""
        self._token_cache[api_key_id] = (tokens, time.time())
    
    def _clear_expired_cache(self):
        """清理过期的缓存项"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, cached_time) in self._token_cache.items()
            if current_time - cached_time >= self._cache_ttl
        ]
        for key in expired_keys:
            del self._token_cache[key]
    
    def get_available_tokens_batch(self, api_key_ids: List[int]) -> Dict[int, float]:
        """
        批量获取多个 API key 的可用令牌数（带缓存优化）
        """
        if not api_key_ids:
            return {}
        
        # 清理过期缓存
        self._clear_expired_cache()
        
        # 检查哪些key需要从Redis获取
        tokens_map = {}
        keys_to_fetch = []
        
        for api_key_id in api_key_ids:
            cached_tokens = self._get_cached_tokens(api_key_id)
            if cached_tokens is not None:
                tokens_map[api_key_id] = cached_tokens
                logger.debug(f"🎯 [TOKEN BUCKET] Using cached tokens for API key {api_key_id}: {cached_tokens:.2f}")
            else:
                keys_to_fetch.append(api_key_id)
        
        # 批量获取未缓存的key
        if keys_to_fetch:
            logger.debug(f"🔍 [TOKEN BUCKET] Fetching tokens from Redis for {len(keys_to_fetch)} keys")
            fresh_tokens = super().get_available_tokens_batch(keys_to_fetch)
            
            # 更新缓存和结果
            for api_key_id, tokens in fresh_tokens.items():
                self._cache_tokens(api_key_id, tokens)
                tokens_map[api_key_id] = tokens
        
        logger.debug(f"📊 [TOKEN BUCKET] Batch token retrieval completed: {len(tokens_map)} keys ({len(api_key_ids) - len(keys_to_fetch)} from cache, {len(keys_to_fetch)} from Redis)")
        return tokens_map
    
    def get_bucket_status(self, api_key_id: int) -> Dict[str, Any]:
        """获取令牌桶状态信息（用于监控）"""
        try:
            bucket_info = self.get_bucket_info(api_key_id)
            if bucket_info:
                capacity = bucket_info.get("capacity", 0)
                tokens = bucket_info.get("tokens", 0)
                utilization = round((1 - tokens / max(capacity, 1)) * 100, 2) if capacity > 0 else 0
                
                status = {
                    "api_key_id": api_key_id,
                    "capacity": capacity,
                    "tokens": round(tokens, 2),
                    "refill_rate": bucket_info.get("refill_rate", 0),
                    "utilization_percent": utilization,
                    "status": "healthy" if tokens > 0 else "depleted",
                    "last_refill": bucket_info.get("last_refill", 0)
                }
                
                logger.debug(f"📊 [TOKEN BUCKET] Status for API key {api_key_id}: {status['status']}, {tokens:.2f}/{capacity} tokens")
                return status
            else:
                return {
                    "api_key_id": api_key_id,
                    "status": "not_found"
                }
        except Exception as e:
            logger.error(f"💥 [TOKEN BUCKET] Error getting bucket status for API key {api_key_id}: {e}")
            return {"api_key_id": api_key_id, "status": "error", "error": str(e)}


# 全局令牌桶管理器实例 - 使用优化版本
token_bucket_manager = OptimizedTokenBucketManager()