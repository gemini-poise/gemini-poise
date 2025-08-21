"""
API Keys CRUD 操作模块

这个文件已经被重构，按职责拆分为多个子模块：
- api_keys_basic.py: 基础CRUD操作
- api_keys_cache.py: 缓存管理
- api_keys_query.py: 查询和统计功能
- api_keys_proxy.py: 代理逻辑相关
- api_keys_token_bucket.py: Token Bucket相关功能
- api_keys_statistics.py: 统计记录功能

为了保持向后兼容性，所有原有的函数都通过导入的方式在这里重新暴露。
"""

# 从各个子模块导入所有函数，保持向后兼容性

# 基础CRUD操作
from .api_keys_basic import (
    get_api_key,
    get_api_key_by_value,
    get_api_keys,
    create_api_key,
    update_api_key,
    delete_api_key,
    bulk_delete_api_keys,
    bulk_add_api_keys,
    delete_api_call_logs_by_api_key_ids,
)

# 缓存管理
from .api_keys_cache import (
    get_redis_client,
    get_cached_active_api_key_ids,
    cache_active_api_key_ids,
    invalidate_active_api_keys_cache,
    ACTIVE_KEYS_CACHE_TTL,
)

# 查询和统计功能
from .api_keys_query import (
    get_api_keys_paginated,
    get_key_statistics,
    get_api_call_statistics,
    get_api_call_logs_by_minute,
)

# 代理逻辑相关
from .api_keys_proxy import (
    get_active_api_keys,
    get_random_active_api_key,
    get_random_active_api_key_from_db,
    increment_api_key_failure_count,
    update_api_key_usage,
)

# Token Bucket相关功能
from .api_keys_token_bucket import (
    get_active_api_key_ids_optimized,
    smart_sample_api_keys,
    get_api_key_with_token_bucket,
    get_active_api_key_with_token_bucket,
    get_api_key_with_fallback,
    configure_api_key_token_bucket,
    reset_api_key_token_bucket,
    get_api_key_token_info,
    batch_configure_token_buckets,
    cleanup_token_buckets,
)

# 统计记录功能
from .api_keys_statistics import (
    record_key_survival_statistics,
    get_key_survival_statistics,
)

# 导出所有函数，确保向后兼容性
__all__ = [
    # 基础CRUD操作
    "get_api_key",
    "get_api_key_by_value", 
    "get_api_keys",
    "create_api_key",
    "update_api_key",
    "delete_api_key",
    "bulk_delete_api_keys",
    "bulk_add_api_keys",
    "delete_api_call_logs_by_api_key_ids",
    
    # 缓存管理
    "get_redis_client",
    "get_cached_active_api_key_ids",
    "cache_active_api_key_ids",
    "invalidate_active_api_keys_cache",
    "ACTIVE_KEYS_CACHE_TTL",
    
    # 查询和统计功能
    "get_api_keys_paginated",
    "get_key_statistics",
    "get_api_call_statistics",
    "get_api_call_logs_by_minute",
    
    # 代理逻辑相关
    "get_active_api_keys",
    "get_random_active_api_key",
    "get_random_active_api_key_from_db",
    "increment_api_key_failure_count",
    "update_api_key_usage",
    
    # Token Bucket相关功能
    "get_active_api_key_ids_optimized",
    "smart_sample_api_keys",
    "get_api_key_with_token_bucket",
    "get_active_api_key_with_token_bucket",
    "get_api_key_with_fallback",
    "configure_api_key_token_bucket",
    "reset_api_key_token_bucket",
    "get_api_key_token_info",
    "batch_configure_token_buckets",
    "cleanup_token_buckets",
    
    # 统计记录功能
    "record_key_survival_statistics",
    "get_key_survival_statistics",
]
