"""
简单的 Token Bucket 使用示例

这个示例展示了如何使用新的 get_active_api_key_with_token_bucket() 方法
来替代原来的 get_random_active_api_key_from_db() 方法。
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.database import get_db
from app.crud.api_keys import (
    get_active_api_key_with_token_bucket,
    get_random_active_api_key_from_db,
    batch_configure_token_buckets
)


def compare_methods():
    """比较 token bucket 方法和随机选择方法"""
    print("=== 比较 Token Bucket 和随机选择方法 ===")
    
    db = next(get_db())
    
    # 首先配置所有 API keys 的 token bucket
    print("配置所有 API keys 的 token bucket...")
    configured_count = batch_configure_token_buckets(db, capacity=5, refill_rate=1.0)
    print(f"已配置 {configured_count} 个 API keys")
    
    print("\n--- 使用 Token Bucket 方法 ---")
    for i in range(5):
        api_key = get_active_api_key_with_token_bucket(db)
        if api_key:
            print(f"第 {i+1} 次: 获取到 API key {api_key.id} (key: {api_key.key_value[:8]}...)")
        else:
            print(f"第 {i+1} 次: 没有可用的 API key")
    
    print("\n--- 使用随机选择方法 ---")
    for i in range(5):
        api_key = get_random_active_api_key_from_db(db)
        if api_key:
            print(f"第 {i+1} 次: 获取到 API key {api_key.id} (key: {api_key.key_value[:8]}...)")
        else:
            print(f"第 {i+1} 次: 没有可用的 API key")


def simple_usage_example():
    """简单使用示例"""
    print("\n=== 简单使用示例 ===")
    
    db = next(get_db())
    
    # 直接使用新方法获取 API key
    api_key = get_active_api_key_with_token_bucket(db)
    
    if api_key:
        print(f"成功获取 API key: {api_key.id}")
        print(f"Key 值预览: {api_key.key_value[:8]}...")
        print(f"状态: {api_key.status}")
        print(f"使用次数: {api_key.usage_count}")
        print(f"失败次数: {api_key.failed_count}")
    else:
        print("没有可用的 API key")


def migration_example():
    """迁移示例：如何从旧方法迁移到新方法"""
    print("\n=== 迁移示例 ===")
    
    db = next(get_db())
    
    print("旧的使用方式:")
    print("api_key = get_random_active_api_key_from_db(db)")
    
    print("\n新的使用方式:")
    print("api_key = get_active_api_key_with_token_bucket(db)")
    
    print("\n两种方法的返回值格式完全相同，可以直接替换！")
    
    # 演示两种方法返回的对象类型相同
    old_method_key = get_random_active_api_key_from_db(db)
    new_method_key = get_active_api_key_with_token_bucket(db)
    
    if old_method_key and new_method_key:
        print(f"\n旧方法返回类型: {type(old_method_key)}")
        print(f"新方法返回类型: {type(new_method_key)}")
        print("两种方法返回的都是 models.ApiKey 对象")


def main():
    """主函数"""
    print("Token Bucket 简单使用示例")
    print("=" * 50)
    
    try:
        simple_usage_example()
        compare_methods()
        migration_example()
        
        print("\n" + "=" * 50)
        print("使用建议:")
        print("1. 直接用 get_active_api_key_with_token_bucket() 替代 get_random_active_api_key_from_db()")
        print("2. 新方法会自动回退到随机选择，确保兼容性")
        print("3. Token bucket 提供更好的负载均衡和频率控制")
        print("4. 如果 Redis 不可用，会自动回退到随机选择")
        
    except Exception as e:
        print(f"示例运行出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()