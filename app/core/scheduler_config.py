import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

jobstores = {
    'default': RedisJobStore(
        host=settings.REDIS_URL.split('://')[1].split(':')[0],
        port=int(settings.REDIS_URL.split('://')[1].split(':')[1].split('/')[0]),
        password=settings.REDIS_PASSWORD,
        db=int(settings.REDIS_URL.split('/')[-1]) if '/' in settings.REDIS_URL else 0
    )
}

scheduler = AsyncIOScheduler(jobstores=jobstores)
