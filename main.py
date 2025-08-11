import logging
import os
from fastapi import FastAPI
from contextlib import asynccontextmanager

# 配置全局日志格式
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/app.log', encoding='utf-8')
    ] if os.path.exists('logs') else [logging.StreamHandler()]
)

# 设置第三方库的日志级别，避免过多噪音
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING if log_level != "DEBUG" else logging.INFO)
logging.getLogger("redis").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

from app.api.api import api_router
from app.core.database import init_redis, close_redis, optimize_sqlite
from app.api.endpoints.proxies import pure_proxy_router, gemini_openai_proxy, gemini_claude_proxy

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
app.include_router(gemini_claude_proxy.router)
app.include_router(pure_proxy_router)


@app.get("/")
async def read_root():
    return {"message": "Welcome to Gemini Poise AI Proxy Tool"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "gemini-poise"}
