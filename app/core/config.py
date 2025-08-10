from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database Configuration
    DATABASE_TYPE: str
    DATABASE_URL: str
    DB_USERNAME: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    POOL_SIZE: Optional[int] = 20  # Increased from 10
    MAX_OVERFLOW: Optional[int] = 50  # Decreased from 100 for better resource management
    POOL_TIMEOUT: Optional[int] = 30
    POOL_RECYCLE: Optional[int] = 3600  # Recycle connections every hour
    POOL_PRE_PING: Optional[bool] = True  # Validate connections before use
    
    # Redis Configuration
    REDIS_URL: str
    REDIS_PASSWORD: Optional[str] = None
    REDIS_MAX_CONNECTIONS: Optional[int] = 50  # Redis connection pool size
    
    # Security Configuration
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    
    # API Configuration
    GEMINI_PURE_PROXY_PREFIX: str = "/v1beta"
    OPENAI_PROXY_PREFIX: str = "/v1"
    
    # Performance Configuration
    MAX_REQUEST_SIZE: Optional[int] = 10 * 1024 * 1024  # 10MB max request size
    REQUEST_TIMEOUT: Optional[int] = 60  # Default request timeout
    
    # Logging Configuration
    LOG_LEVEL: Optional[str] = "INFO"
    LOG_ROTATION: Optional[bool] = True
    LOG_MAX_SIZE: Optional[str] = "100MB"
    LOG_BACKUP_COUNT: Optional[int] = 5

    class Config:
        env_file = ".env"


load_dotenv()
settings = Settings()
