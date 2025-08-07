import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

# 配置全局日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

from app.api.api import api_router
from app.core.database import init_redis, close_redis, optimize_sqlite
from app.api.endpoints.proxies import pure_proxy_router, gemini_openai_proxy

from app.core.scheduler_config import (
    scheduler,
    logger,
    initialize_scheduler,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle event handler.
    Executes startup logic when the application starts and shutdown logic when the application stops.
    """
    logger.info("Application startup...")
    # 优化SQLite配置
    optimize_sqlite()
    await init_redis()
    
    try:
        logger.info("Initializing scheduler tasks...")
        initialize_scheduler()
        
        logger.info("Starting scheduler...")
        scheduler.start()
        
    except Exception as e:
        logger.error(f"Error during application startup: {e}", exc_info=True)
        raise

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
