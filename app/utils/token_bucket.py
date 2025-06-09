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
        self.default_capacity = 10  # 默认桶容量
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
    
    def consume_token(self, api_key_id: int, tokens: int = 1) -> bool:
        """
        尝试从令牌桶中消耗指定数量的令牌
        
        Args:
            api_key_id: API key ID
            tokens: 要消耗的令牌数量
            
        Returns:
            bool: 是否成功消耗令牌
        """
        try:
            bucket = self._get_bucket(api_key_id)
            bucket = self._refill_bucket(bucket)
            
            if bucket.tokens >= tokens:
                bucket.tokens -= tokens
                self._save_bucket(api_key_id, bucket)
                logger.debug(f"Consumed {tokens} tokens for API key {api_key_id}, remaining: {bucket.tokens}")
                return True
            else:
                logger.debug(f"Insufficient tokens for API key {api_key_id}, available: {bucket.tokens}, required: {tokens}")
                return False
                
        except Exception as e:
            logger.error(f"Error consuming token for API key {api_key_id}: {e}")
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
        获取有足够令牌的 API key 列表
        
        Args:
            api_key_ids: API key ID 列表
            required_tokens: 所需令牌数
            
        Returns:
            List[int]: 有足够令牌的 API key ID 列表
        """
        available_keys = []
        
        for api_key_id in api_key_ids:
            if self.get_available_tokens(api_key_id) >= required_tokens:
                available_keys.append(api_key_id)
        
        return available_keys
    
    def cleanup_expired_buckets(self):
        """清理过期的令牌桶（由 Redis TTL 自动处理，此方法用于手动清理）"""
        try:
            pattern = f"{self.bucket_prefix}*"
            keys = self.redis_client.keys(pattern)
            
            current_time = time.time()
            expired_keys = []
            
            for key in keys:
                bucket_data = self.redis_client.get(key)
                if bucket_data:
                    try:
                        data = json.loads(bucket_data)
                        bucket = TokenBucket.from_dict(data)
                        # 如果超过1小时没有使用，认为过期
                        if current_time - bucket.last_refill > 3600:
                            expired_keys.append(key)
                    except (json.JSONDecodeError, TypeError):
                        expired_keys.append(key)
            
            if expired_keys:
                self.redis_client.delete(*expired_keys)
                logger.info(f"Cleaned up {len(expired_keys)} expired token buckets")
                
        except Exception as e:
            logger.error(f"Error cleaning up expired buckets: {e}")


# 全局令牌桶管理器实例
token_bucket_manager = TokenBucketManager()