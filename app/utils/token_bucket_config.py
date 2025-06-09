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
        "cleanup_interval": 300,  # 5分钟
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
    
    return errors