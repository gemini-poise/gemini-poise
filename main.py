from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.api.api import api_router
from app.core.database import init_redis, close_redis, SessionLocal
from app.crud import config as crud_config
from app.tasks.key_validation import validate_api_key_task
from app.api.endpoints.proxies import pure_proxy_router, gemini_openai_proxy

from app.core.scheduler_config import (
    scheduler,
    logger,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle event handler.
    Executes startup logic when the application starts and shutdown logic when the application stops.
    """
    logger.info("Application startup...")
    await init_redis()
    db = SessionLocal()
    try:
        logger.info("Database session created for startup config.")
        # crud_config.initialize_config(db)
        # logger.info("Config initialized (or already exists).")

        # --- Read task interval configuration from the database ---
        interval_seconds_key = "key_validation_interval_seconds"
        interval_seconds_str = crud_config.get_config_value(db, interval_seconds_key)

        task_interval_seconds = 300
        if interval_seconds_str:
            try:
                task_interval_seconds = int(interval_seconds_str)
                if task_interval_seconds <= 0:
                    logger.warning(
                        f"Invalid task interval '{interval_seconds_str}' from config, using default 1 hour."
                    )
                    task_interval_seconds = 300
            except ValueError:
                logger.warning(
                    f"Invalid task interval format '{interval_seconds_str}' from config, using default 1 hour."
                )
                task_interval_seconds = 300

        logger.info(
            f"API Key validation task interval set to {task_interval_seconds} seconds."
        )
        # --- End reading configuration ---

        # --- Start scheduler and add task ---
        logger.info("Starting scheduler...")
        scheduler.start()

        # Add scheduled task: execute validate_api_key_task every task_interval_seconds seconds
        scheduler.add_job(
            validate_api_key_task,
            "interval",
            seconds=task_interval_seconds,
            id="key_validation_task",
            replace_existing=True,
            args=[SessionLocal],
        )
        logger.info(
            f"API Key validation task added to scheduler (interval: {task_interval_seconds} seconds)."
        )
        # --- End scheduler setup ---

    except Exception as e:
        logger.error(f"Error during startup user creation: {e}", exc_info=True)
        db.rollback()
        raise

    finally:
        db.close()
        logger.info("Database session closed.")

    logger.info("Startup complete. Application ready.")
    yield

    logger.info("Application shutting down...")
    logger.info("Shutting down scheduler...")
    scheduler.shutdown()
    await close_redis()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Gemini Poise AI Proxy Tool",
    description="A tool to manage and proxy AI API keys.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api")
app.include_router(gemini_openai_proxy)
app.include_router(pure_proxy_router)


@app.get("/")
async def read_root():
    return {"message": "Welcome to Gemini Poise AI Proxy Tool"}
