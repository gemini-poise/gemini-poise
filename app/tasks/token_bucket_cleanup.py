"""
Token Bucket 清理定时任务
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..utils.token_bucket import token_bucket_manager
from ..utils.token_bucket_config import TokenBucketConfig

logger = logging.getLogger(__name__)


def cleanup_token_buckets_task():
    """清理过期的 token bucket 定时任务"""
    try:
        logger.info("Starting token bucket cleanup task")
        token_bucket_manager.cleanup_expired_buckets()
        logger.info("Token bucket cleanup task completed successfully")
    except Exception as e:
        logger.error(f"Token bucket cleanup task failed: {e}")


def setup_token_bucket_scheduler():
    """设置 token bucket 相关的定时任务"""
    scheduler = BackgroundScheduler()
    
    try:
        # 获取数据库会话来读取配置
        db = next(get_db())
        
        # 获取清理间隔配置
        cleanup_interval = TokenBucketConfig.get_config(db, "cleanup_interval", 300)
        
        # 添加清理任务
        scheduler.add_job(
            func=cleanup_token_buckets_task,
            trigger="interval",
            seconds=cleanup_interval,
            id="token_bucket_cleanup",
            name="Token Bucket Cleanup",
            replace_existing=True
        )
        
        logger.info(f"Token bucket cleanup task scheduled to run every {cleanup_interval} seconds")
        
        # 启动调度器
        scheduler.start()
        logger.info("Token bucket scheduler started successfully")
        
        return scheduler
        
    except Exception as e:
        logger.error(f"Failed to setup token bucket scheduler: {e}")
        return None


def shutdown_token_bucket_scheduler(scheduler):
    """关闭 token bucket 调度器"""
    if scheduler:
        try:
            scheduler.shutdown()
            logger.info("Token bucket scheduler shutdown successfully")
        except Exception as e:
            logger.error(f"Failed to shutdown token bucket scheduler: {e}")