#!/usr/bin/env python3
"""
令牌桶测试脚本
用于演示和测试令牌桶的工作状态
"""

import sys
import time
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.utils.token_bucket import token_bucket_manager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('token_bucket_test.log')
    ]
)

logger = logging.getLogger(__name__)


def test_single_api_key():
    """测试单个API key的令牌消耗"""
    print("\n" + "="*60)
    print("🧪 测试单个API key的令牌消耗")
    print("="*60)
    
    api_key_id = 1001
    
    # 重置令牌桶
    token_bucket_manager.reset_bucket(api_key_id)
    print(f"🔄 重置API key {api_key_id}的令牌桶")
    
    # 获取初始状态
    status = token_bucket_manager.get_bucket_status(api_key_id)
    print(f"📊 初始状态: {status}")
    
    # 连续消耗令牌
    print(f"\n🔥 开始连续消耗令牌...")
    for i in range(15):  # 尝试消耗15个令牌（超过默认容量10）
        success = token_bucket_manager.consume_token(api_key_id, 1)
        available = token_bucket_manager.get_available_tokens(api_key_id)
        print(f"第{i+1}次消耗: {'✅成功' if success else '❌失败'}, 剩余令牌: {available:.2f}")
        
        if not success:
            print(f"⚠️ 令牌不足，停止消耗")
            break
        
        time.sleep(0.1)  # 短暂等待
    
    # 等待令牌补充
    print(f"\n⏳ 等待3秒让令牌自动补充...")
    time.sleep(3)
    
    # 检查补充后的状态
    available = token_bucket_manager.get_available_tokens(api_key_id)
    print(f"📈 补充后可用令牌: {available:.2f}")
    
    # 再次尝试消耗
    success = token_bucket_manager.consume_token(api_key_id, 1)
    print(f"🔄 补充后消耗结果: {'✅成功' if success else '❌失败'}")


def test_batch_operations():
    """测试批量操作"""
    print("\n" + "="*60)
    print("🧪 测试批量操作")
    print("="*60)
    
    api_key_ids = [2001, 2002, 2003, 2004, 2005]
    
    # 重置所有令牌桶
    print(f"🔄 重置{len(api_key_ids)}个API key的令牌桶")
    for api_key_id in api_key_ids:
        token_bucket_manager.reset_bucket(api_key_id)
    
    # 消耗部分API key的令牌
    print(f"\n🔥 消耗部分API key的令牌...")
    for i, api_key_id in enumerate(api_key_ids[:3]):  # 只消耗前3个
        tokens_to_consume = (i + 1) * 3  # 消耗3, 6, 9个令牌
        for _ in range(tokens_to_consume):
            token_bucket_manager.consume_token(api_key_id, 1)
        print(f"API key {api_key_id}: 消耗了{tokens_to_consume}个令牌")
    
    # 批量检查可用性
    print(f"\n🔍 批量检查可用性...")
    available_keys = token_bucket_manager.get_available_api_keys(api_key_ids, required_tokens=2)
    print(f"📊 需要2个令牌时，可用的API keys: {available_keys}")
    
    available_keys = token_bucket_manager.get_available_api_keys(api_key_ids, required_tokens=5)
    print(f"📊 需要5个令牌时，可用的API keys: {available_keys}")
    
    # 显示所有API key的状态
    print(f"\n📊 所有API key的详细状态:")
    for api_key_id in api_key_ids:
        status = token_bucket_manager.get_bucket_status(api_key_id)
        print(f"  API key {api_key_id}: {status['status']}, "
              f"{status.get('tokens', 0):.2f}/{status.get('capacity', 0)} tokens, "
              f"利用率: {status.get('utilization_percent', 0)}%")


def test_rate_limiting():
    """测试速率限制效果"""
    print("\n" + "="*60)
    print("🧪 测试速率限制效果")
    print("="*60)
    
    api_key_id = 3001
    
    # 配置一个小容量的桶
    token_bucket_manager.configure_bucket(api_key_id, capacity=3, refill_rate=1.0)  # 3个令牌，每秒补充1个
    print(f"⚙️ 配置API key {api_key_id}: 容量=3, 补充速率=1.0/秒")
    
    # 重置桶
    token_bucket_manager.reset_bucket(api_key_id)
    
    # 快速消耗所有令牌
    print(f"\n🚀 快速消耗所有令牌...")
    for i in range(5):
        success = token_bucket_manager.consume_token(api_key_id, 1)
        available = token_bucket_manager.get_available_tokens(api_key_id)
        print(f"第{i+1}次: {'✅' if success else '❌'}, 剩余: {available:.2f}")
    
    # 等待并观察令牌补充
    print(f"\n⏳ 观察令牌补充过程...")
    for i in range(6):
        available = token_bucket_manager.get_available_tokens(api_key_id)
        print(f"第{i}秒: 可用令牌 {available:.2f}")
        time.sleep(1)
    
    # 测试补充后的消耗
    print(f"\n🔄 测试补充后的消耗...")
    for i in range(3):
        success = token_bucket_manager.consume_token(api_key_id, 1)
        available = token_bucket_manager.get_available_tokens(api_key_id)
        print(f"消耗{i+1}: {'✅' if success else '❌'}, 剩余: {available:.2f}")


def test_cleanup():
    """测试清理功能"""
    print("\n" + "="*60)
    print("🧪 测试清理功能")
    print("="*60)
    
    # 创建一些测试桶
    test_keys = [4001, 4002, 4003]
    print(f"🔧 创建测试令牌桶...")
    for api_key_id in test_keys:
        token_bucket_manager.consume_token(api_key_id, 1)  # 触发桶创建
    
    print(f"📊 清理前状态:")
    for api_key_id in test_keys:
        status = token_bucket_manager.get_bucket_status(api_key_id)
        print(f"  API key {api_key_id}: {status.get('status', 'unknown')}")
    
    # 执行清理
    print(f"\n🧹 执行清理操作...")
    deleted_count = token_bucket_manager.cleanup_expired_buckets()
    print(f"🗑️ 清理了 {deleted_count} 个过期桶")


def main():
    """主测试函数"""
    print("🚀 令牌桶测试开始")
    print(f"📝 日志将保存到: token_bucket_test.log")
    
    try:
        # 检查令牌桶管理器状态
        print(f"\n🔧 令牌桶管理器信息:")
        print(f"  类型: {type(token_bucket_manager).__name__}")
        print(f"  默认容量: {token_bucket_manager.default_capacity}")
        print(f"  默认补充速率: {token_bucket_manager.default_refill_rate}")
        print(f"  Lua脚本支持: {'✅' if hasattr(token_bucket_manager, '_lua_script') and token_bucket_manager._lua_script else '❌'}")
        
        # 运行各项测试
        test_single_api_key()
        test_batch_operations()
        test_rate_limiting()
        test_cleanup()
        
        print("\n" + "="*60)
        print("✅ 所有测试完成！")
        print("📝 查看 token_bucket_test.log 文件获取详细日志")
        print("="*60)
        
    except Exception as e:
        print(f"\n💥 测试过程中出现错误: {e}")
        logger.error(f"Test failed: {e}", exc_info=True)


if __name__ == "__main__":
    main()