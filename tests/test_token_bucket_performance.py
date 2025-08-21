#!/usr/bin/env python3
"""
Token Bucket 性能测试脚本
用于测试优化后的token bucket性能改进
"""

import time
import asyncio
import logging
from typing import List
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.token_bucket import OptimizedTokenBucketManager
from app.core.config import settings
import redis

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_redis_client():
    """创建测试用的Redis客户端"""
    try:
        client = redis.from_url(
            settings.REDIS_URL,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )
        # 测试连接
        client.ping()
        logger.info("✅ Redis连接成功")
        return client
    except Exception as e:
        logger.error(f"❌ Redis连接失败: {e}")
        return None


def setup_test_data(manager: OptimizedTokenBucketManager, num_keys: int = 1000):
    """设置测试数据"""
    logger.info(f"🔧 设置 {num_keys} 个测试API keys的token bucket数据")
    
    # 为测试keys创建一些token bucket数据
    for i in range(1, num_keys + 1):
        try:
            # 模拟不同的令牌状态
            if i % 3 == 0:
                # 1/3的key令牌较少
                manager.configure_bucket(i, capacity=20, refill_rate=1.0)
                manager.consume_token(i, 15)  # 消耗一些令牌
            elif i % 3 == 1:
                # 1/3的key令牌充足
                manager.configure_bucket(i, capacity=20, refill_rate=1.0)
            else:
                # 1/3的key令牌耗尽
                manager.configure_bucket(i, capacity=20, refill_rate=1.0)
                manager.consume_token(i, 20)  # 消耗所有令牌
        except Exception as e:
            logger.warning(f"设置测试数据失败 key {i}: {e}")
    
    logger.info("✅ 测试数据设置完成")


def test_batch_performance(manager: OptimizedTokenBucketManager, test_keys: List[int], iterations: int = 10):
    """测试批量操作性能"""
    logger.info(f"🚀 开始性能测试: {len(test_keys)} keys, {iterations} 次迭代")
    
    total_time = 0
    successful_iterations = 0
    
    for i in range(iterations):
        try:
            start_time = time.time()
            
            # 批量获取可用的API keys
            available_keys = manager.get_available_api_keys(test_keys, required_tokens=1)
            
            # 如果有可用的keys，选择一个最佳的
            if available_keys:
                from app.crud.api_keys import _select_best_api_key
                selected_key = _select_best_api_key(available_keys)
                
                # 消耗令牌
                success = manager.consume_token(selected_key, 1)
                
                end_time = time.time()
                iteration_time = end_time - start_time
                total_time += iteration_time
                successful_iterations += 1
                
                logger.info(f"迭代 {i+1}: {iteration_time:.3f}s, 可用keys: {len(available_keys)}, 选中key: {selected_key}, 消耗成功: {success}")
            else:
                logger.warning(f"迭代 {i+1}: 没有可用的API keys")
                
        except Exception as e:
            logger.error(f"迭代 {i+1} 失败: {e}")
    
    if successful_iterations > 0:
        avg_time = total_time / successful_iterations
        logger.info(f"📊 性能测试结果:")
        logger.info(f"   总迭代次数: {iterations}")
        logger.info(f"   成功次数: {successful_iterations}")
        logger.info(f"   总耗时: {total_time:.3f}s")
        logger.info(f"   平均耗时: {avg_time:.3f}s")
        logger.info(f"   QPS: {1/avg_time:.2f}")
        return avg_time
    else:
        logger.error("❌ 所有测试迭代都失败了")
        return None


def test_cache_effectiveness(manager: OptimizedTokenBucketManager, test_keys: List[int]):
    """测试缓存效果"""
    logger.info("🎯 测试缓存效果")
    
    # 第一次查询（无缓存）
    start_time = time.time()
    tokens_map1 = manager.get_available_tokens_batch(test_keys)
    first_query_time = time.time() - start_time
    
    # 第二次查询（有缓存）
    start_time = time.time()
    tokens_map2 = manager.get_available_tokens_batch(test_keys)
    second_query_time = time.time() - start_time
    
    logger.info(f"第一次查询耗时: {first_query_time:.3f}s")
    logger.info(f"第二次查询耗时: {second_query_time:.3f}s")
    logger.info(f"缓存加速比: {first_query_time/second_query_time:.2f}x")
    
    return first_query_time, second_query_time


def main():
    """主函数"""
    logger.info("🚀 开始Token Bucket性能测试")
    
    # 创建Redis客户端
    redis_client = create_test_redis_client()
    if not redis_client:
        logger.error("无法连接Redis，测试终止")
        return
    
    # 创建优化的token bucket管理器
    manager = OptimizedTokenBucketManager(redis_client)
    
    # 测试不同规模的key数量
    test_scenarios = [
        {"num_keys": 100, "name": "小规模测试"},
        {"num_keys": 1000, "name": "中等规模测试"},
        {"num_keys": 5000, "name": "大规模测试"},
    ]
    
    for scenario in test_scenarios:
        num_keys = scenario["num_keys"]
        name = scenario["name"]
        
        logger.info(f"\n{'='*50}")
        logger.info(f"📋 {name} ({num_keys} keys)")
        logger.info(f"{'='*50}")
        
        # 设置测试数据
        setup_test_data(manager, num_keys)
        
        # 准备测试key列表
        test_keys = list(range(1, num_keys + 1))
        
        # 测试批量性能
        avg_time = test_batch_performance(manager, test_keys, iterations=5)
        
        # 测试缓存效果
        if num_keys <= 1000:  # 只在较小规模时测试缓存
            test_cache_effectiveness(manager, test_keys[:100])
        
        logger.info(f"✅ {name} 完成\n")
    
    logger.info("🎉 所有性能测试完成")


if __name__ == "__main__":
    main()
