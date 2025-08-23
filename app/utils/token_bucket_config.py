import logging
from typing import Dict, Any, Optional
from ..crud.config import get_config_by_key, update_config_value
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class TokenBucketConfig:
    """Token Bucket 配置管理器"""
    
    # 默认配置
    DEFAULT_CONFIG = {
        "default_capacity": 10,
        "default_refill_rate": 1.0,
        "high_priority_capacity": 20,
        "high_priority_refill_rate": 2.0,
        "low_priority_capacity": 5,
        "low_priority_refill_rate": 0.5,
        "bucket_ttl": 3600,
        "enable_token_bucket": True,
        "fallback_to_random": True,
        "cleanup_interval": 300,  # 5分钟（保持兼容性）
        # 新增动态过期配置
        "enable_lazy_cleanup": True,  # 启用懒删除
        "enable_lru_eviction": True,  # 启用LRU淘汰
        "max_buckets": 1000,  # 最大bucket数量
        "high_freq_ttl": 3600,  # 高频使用TTL（1小时）
        "medium_freq_ttl": 1800,  # 中频使用TTL（30分钟）
        "low_freq_ttl": 300,  # 低频使用TTL（5分钟）
        "high_freq_threshold": 100,  # 高频使用阈值
        "medium_freq_threshold": 10,  # 中频使用阈值
    }
    
    CONFIG_PREFIX = "token_bucket_"
    
    @classmethod
    def get_config(cls, db: Session, key: str, default_value: Any = None) -> Any:
        """
        从数据库获取配置值
        
        Args:
            db: 数据库会话
            key: 配置键名
            default_value: 默认值
            
        Returns:
            配置值
        """
        config_key = f"{cls.CONFIG_PREFIX}{key}"
        config = get_config_by_key(db, config_key)
        
        if config:
            try:
                # 尝试转换为适当的类型
                value = config.value
                if isinstance(default_value, bool):
                    return value.lower() in ('true', '1', 'yes', 'on')
                elif isinstance(default_value, int):
                    return int(value)
                elif isinstance(default_value, float):
                    return float(value)
                else:
                    return value
            except (ValueError, AttributeError) as e:
                logger.warning(f"Failed to parse config value for {config_key}: {e}")
                return default_value or cls.DEFAULT_CONFIG.get(key)
        
        return default_value or cls.DEFAULT_CONFIG.get(key)
    
    @classmethod
    def set_config(cls, db: Session, key: str, value: Any, user_id: int):
        """
        设置配置值到数据库
        
        Args:
            db: 数据库会话
            key: 配置键名
            value: 配置值
            user_id: 更新用户ID
        """
        config_key = f"{cls.CONFIG_PREFIX}{key}"
        str_value = str(value)
        
        try:
            update_config_value(db, config_key, str_value, user_id)
            logger.info(f"Updated token bucket config: {config_key} = {str_value}")
        except Exception as e:
            logger.error(f"Failed to update config {config_key}: {e}")
            raise
    
    @classmethod
    def get_all_config(cls, db: Session) -> Dict[str, Any]:
        """获取所有 token bucket 配置"""
        config = {}
        for key, default_value in cls.DEFAULT_CONFIG.items():
            config[key] = cls.get_config(db, key, default_value)
        return config
    
    @classmethod
    def init_default_config(cls, db: Session, user_id: int):
        """初始化默认配置到数据库"""
        for key, value in cls.DEFAULT_CONFIG.items():
            try:
                cls.set_config(db, key, value, user_id)
            except Exception as e:
                logger.error(f"Failed to init config {key}: {e}")
        
        logger.info("Token bucket default configuration initialized")
    
    @classmethod
    def get_bucket_params_for_key(cls, db: Session, api_key_id: int, 
                                 priority: str = "normal") -> Dict[str, Any]:
        """
        根据优先级获取 API Key 的 token bucket 参数
        
        Args:
            db: 数据库会话
            api_key_id: API Key ID
            priority: 优先级 ("high", "normal", "low")
            
        Returns:
            Dict: 包含 capacity 和 refill_rate 的字典
        """
        if priority == "high":
            capacity = cls.get_config(db, "high_priority_capacity")
            refill_rate = cls.get_config(db, "high_priority_refill_rate")
        elif priority == "low":
            capacity = cls.get_config(db, "low_priority_capacity")
            refill_rate = cls.get_config(db, "low_priority_refill_rate")
        else:  # normal
            capacity = cls.get_config(db, "default_capacity")
            refill_rate = cls.get_config(db, "default_refill_rate")
        
        return {
            "capacity": capacity,
            "refill_rate": refill_rate
        }
    
    @classmethod
    def is_token_bucket_enabled(cls, db: Session) -> bool:
        """检查是否启用 token bucket"""
        return cls.get_config(db, "enable_token_bucket", True)
    
    @classmethod
    def should_fallback_to_random(cls, db: Session) -> bool:
        """检查是否应该回退到随机选择"""
        return cls.get_config(db, "fallback_to_random", True)
    
    @classmethod
    def is_lazy_cleanup_enabled(cls, db: Session) -> bool:
        """检查是否启用懒删除"""
        return cls.get_config(db, "enable_lazy_cleanup", True)
    
    @classmethod
    def is_lru_eviction_enabled(cls, db: Session) -> bool:
        """检查是否启用LRU淘汰"""
        return cls.get_config(db, "enable_lru_eviction", True)
    
    @classmethod
    def get_max_buckets(cls, db: Session) -> int:
        """获取最大bucket数量"""
        return cls.get_config(db, "max_buckets", 1000)
    
    @classmethod
    def calculate_dynamic_ttl(cls, db: Session, usage_frequency: int) -> int:
        """
        根据使用频率计算动态TTL
        
        Args:
            db: 数据库会话
            usage_frequency: 使用频率（单位时间内访问次数）
            
        Returns:
            TTL秒数
        """
        high_threshold = cls.get_config(db, "high_freq_threshold", 100)
        medium_threshold = cls.get_config(db, "medium_freq_threshold", 10)
        
        if usage_frequency >= high_threshold:
            return cls.get_config(db, "high_freq_ttl", 3600)
        elif usage_frequency >= medium_threshold:
            return cls.get_config(db, "medium_freq_ttl", 1800)
        else:
            return cls.get_config(db, "low_freq_ttl", 300)
    
    @classmethod
    def get_cleanup_strategy_config(cls, db: Session) -> Dict[str, Any]:
        """获取清理策略配置"""
        return {
            "enable_lazy_cleanup": cls.is_lazy_cleanup_enabled(db),
            "enable_lru_eviction": cls.is_lru_eviction_enabled(db),
            "max_buckets": cls.get_max_buckets(db),
            "cleanup_interval": cls.get_config(db, "cleanup_interval", 300),
            "high_freq_threshold": cls.get_config(db, "high_freq_threshold", 100),
            "medium_freq_threshold": cls.get_config(db, "medium_freq_threshold", 10),
            "high_freq_ttl": cls.get_config(db, "high_freq_ttl", 3600),
            "medium_freq_ttl": cls.get_config(db, "medium_freq_ttl", 1800),
            "low_freq_ttl": cls.get_config(db, "low_freq_ttl", 300),
        }


# 配置验证函数
def validate_token_bucket_config(config: Dict[str, Any]) -> Dict[str, str]:
    """
    验证 token bucket 配置
    
    Args:
        config: 配置字典
        
    Returns:
        Dict[str, str]: 验证错误信息，键为配置项名，值为错误信息
    """
    errors = {}
    
    # 验证容量配置
    for capacity_key in ["default_capacity", "high_priority_capacity", "low_priority_capacity"]:
        if capacity_key in config:
            try:
                capacity = int(config[capacity_key])
                if capacity <= 0:
                    errors[capacity_key] = "容量必须大于0"
                elif capacity > 1000:
                    errors[capacity_key] = "容量不能超过1000"
            except (ValueError, TypeError):
                errors[capacity_key] = "容量必须是有效的整数"
    
    # 验证补充速率配置
    for rate_key in ["default_refill_rate", "high_priority_refill_rate", "low_priority_refill_rate"]:
        if rate_key in config:
            try:
                rate = float(config[rate_key])
                if rate <= 0:
                    errors[rate_key] = "补充速率必须大于0"
                elif rate > 100:
                    errors[rate_key] = "补充速率不能超过100"
            except (ValueError, TypeError):
                errors[rate_key] = "补充速率必须是有效的数字"
    
    # 验证TTL配置
    if "bucket_ttl" in config:
        try:
            ttl = int(config["bucket_ttl"])
            if ttl < 60:
                errors["bucket_ttl"] = "TTL不能小于60秒"
            elif ttl > 86400:
                errors["bucket_ttl"] = "TTL不能超过24小时"
        except (ValueError, TypeError):
            errors["bucket_ttl"] = "TTL必须是有效的整数"
    
    # 验证清理间隔
    if "cleanup_interval" in config:
        try:
            interval = int(config["cleanup_interval"])
            if interval < 60:
                errors["cleanup_interval"] = "清理间隔不能小于60秒"
            elif interval > 3600:
                errors["cleanup_interval"] = "清理间隔不能超过1小时"
        except (ValueError, TypeError):
            errors["cleanup_interval"] = "清理间隔必须是有效的整数"
    
    # 验证最大bucket数量
    if "max_buckets" in config:
        try:
            max_buckets = int(config["max_buckets"])
            if max_buckets < 10:
                errors["max_buckets"] = "最大bucket数量不能小于10"
            elif max_buckets > 10000:
                errors["max_buckets"] = "最大bucket数量不能超过10000"
        except (ValueError, TypeError):
            errors["max_buckets"] = "最大bucket数量必须是有效的整数"
    
    # 验证频率阈值
    for threshold_key in ["high_freq_threshold", "medium_freq_threshold"]:
        if threshold_key in config:
            try:
                threshold = int(config[threshold_key])
                if threshold < 1:
                    errors[threshold_key] = "频率阈值必须大于0"
                elif threshold > 10000:
                    errors[threshold_key] = "频率阈值不能超过10000"
            except (ValueError, TypeError):
                errors[threshold_key] = "频率阈值必须是有效的整数"
    
    # 验证动态TTL配置
    for ttl_key in ["high_freq_ttl", "medium_freq_ttl", "low_freq_ttl"]:
        if ttl_key in config:
            try:
                ttl = int(config[ttl_key])
                if ttl < 60:
                    errors[ttl_key] = f"{ttl_key} 不能小于60秒"
                elif ttl > 86400:
                    errors[ttl_key] = f"{ttl_key} 不能超过24小时"
            except (ValueError, TypeError):
                errors[ttl_key] = f"{ttl_key} 必须是有效的整数"
    
    return errors