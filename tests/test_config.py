import logging
import pytest
from app.core import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_config_settings_loading():
    """
    测试配置设置是否正确加载。
    """
    assert isinstance(settings.REDIS_URL, str)
    assert settings.REDIS_URL != ""

    assert isinstance(settings.REDIS_PASSWORD, (str, type(None)))
    logging.info(settings.REDIS_URL)