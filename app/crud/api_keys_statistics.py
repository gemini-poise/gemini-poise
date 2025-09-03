import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from ..models import models
from .api_keys_query import get_key_statistics

logger = logging.getLogger(__name__)


def record_key_survival_statistics(db: Session):
    """
    记录当前密钥存活统计数据。
    """
    try:
        # 获取当前密钥统计
        stats = get_key_statistics(db)

        # 创建新的统计记录
        new_statistics = models.KeySurvivalStatistics(
            active_keys=stats.active_keys,
            exhausted_keys=stats.exhausted_keys,
            error_keys=stats.error_keys,
            total_keys=stats.total_keys
        )

        db.add(new_statistics)
        db.commit()
        db.refresh(new_statistics)

        logger.info(f"Recorded key survival statistics: active={stats.active_keys}, exhausted={stats.exhausted_keys}, error={stats.error_keys}, total={stats.total_keys}")
        return new_statistics
    except Exception as e:
        logger.error(f"Failed to record key survival statistics: {e}")
        db.rollback()
        return None


def get_key_survival_statistics(
    db: Session,
    limit: int = 30,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
):
    """
    获取密钥存活统计数据，支持时间范围过滤。
    """
    try:
        query = db.query(models.KeySurvivalStatistics)

        if start_time:
            query = query.filter(models.KeySurvivalStatistics.timestamp >= start_time)
        if end_time:
            query = query.filter(models.KeySurvivalStatistics.timestamp <= end_time)

        statistics = (query.order_by(models.KeySurvivalStatistics.timestamp.desc())
                      # .limit(limit)
                      .all())

        # 返回时间正序排列
        return list(reversed(statistics))
    except Exception as e:
        logger.error(f"Failed to get key survival statistics: {e}")
        return []
