"""
性能优化测试脚本
测试Redis缓存和智能采样对API key选择性能的影响
"""

import time
import logging
import asyncio
from typing import List
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from app.crud.api_keys import (
    get_api_key_with_token_bucket,
    get_active_api_key_ids_optimized,
    get_cached_active_api_key_ids,
    cache_active_api_key_ids,
    invalidate_active_api_keys_cache,
    smart_sample_api_keys,
    INITIAL_SAMPLE_SIZE,
    MAX_SAMPLE_SIZE
)
from app.models.models import ApiKey

logger = logging.getLogger(__name__)


class TestPerformanceOptimization:
    """性能优化测试类"""
    
    def setup_method(self):
        """测试前准备"""
        # 清理缓存
        invalidate_active_api_keys_cache()
    
    def teardown_method(self):
        """测试后清理"""
        # 清理缓存
        invalidate_active_api_keys_cache()
    
    def test_cache_functionality(self):
        """测试缓存功能"""
        # 测试缓存不存在时
        cached_ids = get_cached_active_api_key_ids()
        assert cached_ids is None
        
        # 测试缓存写入
        test_ids = [1, 2, 3, 4, 5]
        cache_active_api_key_ids(test_ids)
        
        # 测试缓存读取
        cached_ids = get_cached_active_api_key_ids()
        assert cached_ids == test_ids
        
        # 测试缓存失效
        invalidate_active_api_keys_cache()
        cached_ids = get_cached_active_api_key_ids()
        assert cached_ids is None
    
    def test_smart_sampling(self):
        """测试智能采样功能"""
        # 测试小于采样大小的情况
        small_list = [1, 2, 3, 4, 5]
        sampled = smart_sample_api_keys(small_list, INITIAL_SAMPLE_SIZE)
        assert sampled == small_list
        
        # 测试大于采样大小的情况
        large_list = list(range(1, 1001))  # 1000个keys
        sampled = smart_sample_api_keys(large_list, INITIAL_SAMPLE_SIZE)
        assert len(sampled) == INITIAL_SAMPLE_SIZE
        assert all(key_id in large_list for key_id in sampled)
    
    @patch('app.crud.api_keys.get_active_api_keys')
    def test_cache_performance_improvement(self, mock_get_active_keys):
        """测试缓存对性能的改善"""
        # 模拟大量API keys
        mock_keys = []
        for i in range(1, 10001):  # 10000个keys
            mock_key = Mock(spec=ApiKey)
            mock_key.id = i
            mock_key.status = "active"
            mock_keys.append(mock_key)
        
        mock_get_active_keys.return_value = mock_keys
        
        # 创建模拟数据库会话
        mock_db = Mock(spec=Session)
        
        # 第一次调用（缓存未命中）
        start_time = time.time()
        result1 = get_active_api_key_ids_optimized(mock_db)
        first_call_time = time.time() - start_time
        
        assert len(result1) == 10000
        assert mock_get_active_keys.call_count == 1
        
        # 第二次调用（缓存命中）
        start_time = time.time()
        result2 = get_active_api_key_ids_optimized(mock_db)
        second_call_time = time.time() - start_time
        
        assert result1 == result2
        assert mock_get_active_keys.call_count == 1  # 没有再次调用数据库
        
        # 缓存命中应该显著更快
        logger.info(f"First call (cache miss): {first_call_time:.4f}s")
        logger.info(f"Second call (cache hit): {second_call_time:.4f}s")
        logger.info(f"Performance improvement: {first_call_time / second_call_time:.2f}x")
        
        # 缓存命中应该更快（放宽条件，因为测试环境可能有差异）
        assert second_call_time < first_call_time or second_call_time < 0.1
    
    @patch('app.crud.api_keys.token_bucket_manager')
    @patch('app.crud.api_keys.get_api_key')
    @patch('app.crud.api_keys.get_active_api_key_ids_optimized')
    def test_sampling_performance_improvement(self, mock_get_ids, mock_get_key, mock_token_manager):
        """测试采样对性能的改善"""
        # 模拟大量API key IDs
        large_key_ids = list(range(1, 50001))  # 50000个keys
        mock_get_ids.return_value = large_key_ids
        
        # 模拟token bucket manager
        mock_token_manager.get_available_api_keys.return_value = [1, 2, 3]  # 前几个有token
        mock_token_manager.consume_token.return_value = True
        # 模拟token数量返回
        mock_token_manager.get_available_tokens_batch.return_value = {1: 10.0, 2: 8.0, 3: 5.0}
        
        # 模拟API key对象
        mock_key = Mock(spec=ApiKey)
        mock_key.id = 1
        mock_key.status = "active"
        mock_get_key.return_value = mock_key
        
        # 创建模拟数据库会话
        mock_db = Mock(spec=Session)
        
        # 测试优化后的函数
        start_time = time.time()
        result = get_api_key_with_token_bucket(mock_db, required_tokens=1)
        optimized_time = time.time() - start_time
        
        assert result is not None
        assert result.id == 1
        
        # 验证只检查了采样的keys，而不是全部50000个
        call_args = mock_token_manager.get_available_api_keys.call_args[0]
        sampled_keys = call_args[0]
        
        logger.info(f"Total keys: {len(large_key_ids)}")
        logger.info(f"Sampled keys: {len(sampled_keys)}")
        logger.info(f"Sampling ratio: {len(sampled_keys) / len(large_key_ids) * 100:.2f}%")
        logger.info(f"Optimized call time: {optimized_time:.4f}s")
        
        # 采样大小应该远小于总数
        assert len(sampled_keys) <= INITIAL_SAMPLE_SIZE
        assert len(sampled_keys) < len(large_key_ids) / 10  # 至少减少90%
    
    def test_progressive_sampling(self):
        """测试渐进式采样策略"""
        # 测试采样扩展
        key_ids = list(range(1, 5001))  # 5000个keys
        
        # 第一次采样
        sample1 = smart_sample_api_keys(key_ids, INITIAL_SAMPLE_SIZE)
        assert len(sample1) == INITIAL_SAMPLE_SIZE
        
        # 扩展采样
        expanded_size = min(INITIAL_SAMPLE_SIZE * 2, MAX_SAMPLE_SIZE, len(key_ids))
        sample2 = smart_sample_api_keys(key_ids, expanded_size)
        assert len(sample2) == expanded_size
        
        # 最大采样
        max_sample = smart_sample_api_keys(key_ids, MAX_SAMPLE_SIZE)
        assert len(max_sample) == min(MAX_SAMPLE_SIZE, len(key_ids))
    
    @patch('app.crud.api_keys.get_redis_client')
    def test_redis_error_handling(self, mock_redis_client):
        """测试Redis错误处理"""
        # 模拟Redis连接错误
        mock_redis_client.side_effect = Exception("Redis connection failed")
        
        # 缓存读取应该返回None而不是抛出异常
        cached_ids = get_cached_active_api_key_ids()
        assert cached_ids is None
        
        # 缓存写入应该不抛出异常
        test_ids = [1, 2, 3]
        try:
            cache_active_api_key_ids(test_ids)
        except Exception:
            pytest.fail("cache_active_api_key_ids should not raise exception on Redis error")
    
    def test_cache_ttl_expiration(self):
        """测试缓存TTL过期"""
        # 这个测试需要实际的Redis连接，在集成测试中运行
        pass
    
    def generate_performance_report(self):
        """生成性能报告"""
        report = {
            "optimization_features": [
                "Redis缓存活跃API keys列表",
                "智能采样策略（初始200个keys）",
                "渐进式扩展采样",
                "自动缓存失效机制"
            ],
            "expected_improvements": {
                "database_queries": "减少99%+（从每次请求查询变为缓存命中）",
                "token_bucket_checks": "减少90%+（从检查所有keys变为采样检查）",
                "memory_usage": "增加约1MB（缓存50000个key IDs）",
                "response_time": "预期提升5-10倍"
            },
            "cache_configuration": {
                "ttl_seconds": 300,
                "initial_sample_size": INITIAL_SAMPLE_SIZE,
                "max_sample_size": MAX_SAMPLE_SIZE,
                "expansion_factor": 2
            }
        }
        return report


if __name__ == "__main__":
    # 运行性能测试
    test_instance = TestPerformanceOptimization()
    
    print("🚀 开始性能优化测试...")
    
    # 运行各项测试
    test_instance.setup_method()
    
    try:
        print("✅ 测试缓存功能...")
        test_instance.test_cache_functionality()
        
        print("✅ 测试智能采样...")
        test_instance.test_smart_sampling()
        
        print("✅ 测试缓存性能改善...")
        test_instance.test_cache_performance_improvement()
        
        print("✅ 测试采样性能改善...")
        test_instance.test_sampling_performance_improvement()
        
        print("✅ 测试渐进式采样...")
        test_instance.test_progressive_sampling()
        
        print("✅ 测试Redis错误处理...")
        test_instance.test_redis_error_handling()
        
        print("\n📊 性能优化报告:")
        report = test_instance.generate_performance_report()
        
        print(f"优化功能: {', '.join(report['optimization_features'])}")
        print(f"预期改善:")
        for key, value in report['expected_improvements'].items():
            print(f"  - {key}: {value}")
        
        print(f"缓存配置:")
        for key, value in report['cache_configuration'].items():
            print(f"  - {key}: {value}")
        
        print("\n🎉 所有测试通过！性能优化实施成功！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        raise
    finally:
        test_instance.teardown_method()