import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from app.core.config import settings
from app.core.database import SessionLocal
from app.crud import config as crud_config
from app.tasks.key_validation import (
    validate_active_api_keys_task,
    validate_exhausted_api_keys_task,
    validate_error_api_keys_task,
)

logger = logging.getLogger(__name__)

jobstores = {
    "default": RedisJobStore(
        host=settings.REDIS_URL.split("://")[1].split(":")[0],
        port=int(settings.REDIS_URL.split("://")[1].split(":")[1].split("/")[0]),
        password=settings.REDIS_PASSWORD,
        db=int(settings.REDIS_URL.split("/")[-1]) if "/" in settings.REDIS_URL else 0,
    )
}

scheduler = AsyncIOScheduler(jobstores=jobstores)


def initialize_scheduler():
    """
    Initializes and adds scheduled tasks based on configuration from the database.
    """
    with SessionLocal() as db:
        active_interval = crud_config.get_config_value(
            db, "key_validation_active_interval_seconds"
        )
        exhausted_interval = crud_config.get_config_value(
            db, "key_validation_exhausted_interval_seconds"
        )
        error_interval = crud_config.get_config_value(
            db, "key_validation_error_interval_seconds"
        )

        # Default to 300 seconds (5 minutes) for active keys if not configured
        active_interval_seconds = int(active_interval) if active_interval else 300
        if active_interval_seconds <= 0:
            active_interval_seconds = 300
            logger.warning(
                f"Invalid active key validation interval '{active_interval}', using default 300 seconds."
            )

        # Default to active interval for exhausted keys if not configured
        exhausted_interval_seconds = (
            int(exhausted_interval) if exhausted_interval else active_interval_seconds
        )
        if exhausted_interval_seconds <= 0:
            exhausted_interval_seconds = active_interval_seconds
            logger.warning(
                f"Invalid exhausted key validation interval '{exhausted_interval}', using active interval {active_interval_seconds} seconds."
            )

        # Default to 0 (no refresh) for error keys if not configured
        error_interval_seconds = int(error_interval) if error_interval else 0
        if error_interval_seconds < 0:
            error_interval_seconds = 0
            logger.warning(
                f"Invalid error key validation interval '{error_interval}', using default 0 seconds (no refresh)."
            )

        # Add/reschedule active key validation task
        scheduler.add_job(
            validate_active_api_keys_task,
            "interval",
            seconds=active_interval_seconds,
            id="key_validation_active_task",
            replace_existing=True,
            max_instances=1,
            coalesce=False,
            misfire_grace_time=0,
        )
        logger.info(
            f"Scheduled 'active' API Key validation task with interval: {active_interval_seconds} seconds."
        )

        # Add/reschedule exhausted key validation task
        if exhausted_interval_seconds > 0:
            scheduler.add_job(
                validate_exhausted_api_keys_task,
                "interval",
                seconds=exhausted_interval_seconds,
                id="key_validation_exhausted_task",
                replace_existing=True,
                max_instances=1,
                coalesce=False,
                misfire_grace_time=0,
            )
            logger.info(
                f"Scheduled 'exhausted' API Key validation task with interval: {exhausted_interval_seconds} seconds."
            )
        else:
            if scheduler.get_job("key_validation_exhausted_task"):
                scheduler.remove_job("key_validation_exhausted_task")
                logger.info("Removed 'exhausted' API Key validation task.")

        # Add/reschedule error key validation task
        if error_interval_seconds > 0:
            scheduler.add_job(
                validate_error_api_keys_task,
                "interval",
                seconds=error_interval_seconds,
                id="key_validation_error_task",
                replace_existing=True,
                max_instances=1,
                coalesce=False,
                misfire_grace_time=0,
            )
            logger.info(
                f"Scheduled 'error' API Key validation task with interval: {error_interval_seconds} seconds."
            )
        else:
            # If interval is 0, ensure the task is not scheduled or is removed
            if scheduler.get_job("key_validation_error_task"):
                scheduler.remove_job("key_validation_error_task")
                logger.info("Removed 'error' API Key validation task as interval is 0.")
            else:
                logger.info("Skipping 'error' API Key validation task as interval is 0.")

    logger.info("Scheduler initialization complete.")
