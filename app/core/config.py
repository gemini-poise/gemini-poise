from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# , SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_TYPE: str
    DATABASE_URL: str
    REDIS_URL: str
    REDIS_PASSWORD: Optional[str] = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    GEMINI_PURE_PROXY_PREFIX: str = "/v1beta"
    OPENAI_PROXY_PREFIX: str = "/v1"

    # model_config = SettingsConfigDict(env_file=".env")


load_dotenv()
settings = Settings()
