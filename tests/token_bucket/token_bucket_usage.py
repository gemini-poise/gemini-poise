"""
Token Bucket 使用示例

这个脚本展示了如何使用新的 token bucket 功能来管理 API key 的使用频率。
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.database import get_db
from app.crud.api_keys import (
    get_api_key_with_token_bucket,
    get_api_key_with_fallback,
    configure_api_key_token_bucket,
    reset_api_key_token_bucket,
    get_api_key_token_info,
    batch_configure_token_buckets,
    get_active_api_keys
)
from app.utils.token_bucket_config import TokenBucketConfig
import time


def demo_basic_usage():
    """演示基本的 token bucket 使用"""
    print("=== Token Bucket 基本使用演示 ===")
    
    db = next(get_db())
    
    # 1. 获取活跃的 API keys
    active_keys = get_active_api_keys(db)
    if not active_keys:
        print("没有找到活跃的 API keys")
        return
    
    print(f"找到 {len(active_keys)} 个活跃的 API keys")
    
    # 2. 配置 token bucket
    print("\n配置 token bucket...")
    for api_key in active_keys[:3]:  # 只配置前3个
        configure_api_key_token_bucket(
            api_key.id, 
            capacity=5,  # 容量为5
            refill_rate=1.0  # 每秒补充1个令牌
        )
        print(f"已配置 API key {api_key.id}")
    
    # 3. 使用 token bucket 获取 API key
    print("\n使用 token bucket 获取 API key...")
    for i in range(10):
        api_key = get_api_key_with_token_bucket(db, required_tokens=1)
        if api_key:
            print(f"第 {i+1} 次: 获取到 API key {api_key.id}")
            # 查看令牌信息
            token_info = get_api_key_token_info(api_key.id)
            print(f"  剩余令牌: {token_info.get('tokens', 0):.2f}")
        else:
            print(f"第 {i+1} 次: 没有可用的 API key")
        
        time.sleep(0.5)  # 等待0.5秒


def demo_fallback_mechanism():
    """演示回退机制"""
    print("\n=== 回退机制演示 ===")
    
    db = next(get_db())
    
    # 使用带回退的方法
    print("使用带回退机制的 API key 获取...")
    for i in range(5):
        api_key = get_api_key_with_fallback(
            db, 
            required_tokens=1, 
            use_token_bucket=True
        )
        if api_key:
            print(f"获取到 API key {api_key.id}")
        else:
            print("没有可用的 API key")


def demo_configuration_management():
    """演示配置管理"""
    print("\n=== 配置管理演示 ===")
    
    db = next(get_db())
    
    # 获取当前配置
    config = TokenBucketConfig.get_all_config(db)
    print("当前 Token Bucket 配置:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    
    # 批量配置所有 API keys
    print("\n批量配置所有 API keys...")
    configured_count = batch_configure_token_buckets(
        db, 
        capacity=10, 
        refill_rate=2.0
    )
    print(f"已配置 {configured_count} 个 API keys")


def demo_priority_based_configuration():
    """演示基于优先级的配置"""
    print("\n=== 优先级配置演示 ===")
    
    db = next(get_db())
    active_keys = get_active_api_keys(db)
    
    if len(active_keys) >= 3:
        # 配置不同优先级的 API keys
        high_priority_params = TokenBucketConfig.get_bucket_params_for_key(
            db, active_keys[0].id, "high"
        )
        normal_priority_params = TokenBucketConfig.get_bucket_params_for_key(
            db, active_keys[1].id, "normal"
        )
        low_priority_params = TokenBucketConfig.get_bucket_params_for_key(
            db, active_keys[2].id, "low"
        )
        
        print("配置不同优先级的 API keys:")
        print(f"高优先级 (API key {active_keys[0].id}): {high_priority_params}")
        print(f"普通优先级 (API key {active_keys[1].id}): {normal_priority_params}")
        print(f"低优先级 (API key {active_keys[2].id}): {low_priority_params}")
        
        # 应用配置
        configure_api_key_token_bucket(
            active_keys[0].id, 
            **high_priority_params
        )
        configure_api_key_token_bucket(
            active_keys[1].id, 
            **normal_priority_params
        )
        configure_api_key_token_bucket(
            active_keys[2].id, 
            **low_priority_params
        )
        
        print("配置已应用")


def demo_token_info_monitoring():
    """演示令牌信息监控"""
    print("\n=== 令牌信息监控演示 ===")
    
    db = next(get_db())
    active_keys = get_active_api_keys(db)
    
    if active_keys:
        print("API Key 令牌状态:")
        for api_key in active_keys[:5]:  # 只显示前5个
            token_info = get_api_key_token_info(api_key.id)
            print(f"API key {api_key.id}:")
            print(f"  容量: {token_info.get('capacity', 0)}")
            print(f"  当前令牌: {token_info.get('tokens', 0):.2f}")
            print(f"  补充速率: {token_info.get('refill_rate', 0)}/秒")
            print(f"  上次补充: {token_info.get('last_refill', 0)}")


def demo_reset_functionality():
    """演示重置功能"""
    print("\n=== 重置功能演示 ===")
    
    db = next(get_db())
    active_keys = get_active_api_keys(db)
    
    if active_keys:
        api_key = active_keys[0]
        
        print(f"重置前 API key {api_key.id} 的令牌信息:")
        token_info = get_api_key_token_info(api_key.id)
        print(f"  当前令牌: {token_info.get('tokens', 0):.2f}")
        
        # 消耗一些令牌
        print("消耗一些令牌...")
        for _ in range(3):
            get_api_key_with_token_bucket(db, required_tokens=1)
        
        print("消耗后的令牌信息:")
        token_info = get_api_key_token_info(api_key.id)
        print(f"  当前令牌: {token_info.get('tokens', 0):.2f}")
        
        # 重置令牌桶
        print("重置令牌桶...")
        reset_api_key_token_bucket(api_key.id)
        
        print("重置后的令牌信息:")
        token_info = get_api_key_token_info(api_key.id)
        print(f"  当前令牌: {token_info.get('tokens', 0):.2f}")


def main():
    """主函数"""
    print("Token Bucket 功能演示")
    print("=" * 50)
    
    try:
        demo_basic_usage()
        demo_fallback_mechanism()
        demo_configuration_management()
        demo_priority_based_configuration()
        demo_token_info_monitoring()
        demo_reset_functionality()
        
        print("\n演示完成!")
        
    except Exception as e:
        print(f"演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()