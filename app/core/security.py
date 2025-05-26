import logging
import uuid
from datetime import timedelta
from typing import Annotated
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security.oauth2 import OAuth2PasswordBearer
from passlib.context import CryptContext
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import get_redis_client, get_db
from ..models import models
from ..schemas import schemas

logger = logging.getLogger(__name__)

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码是否与哈希密码匹配"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """对密码进行哈希"""
    return pwd_context.hash(password)


async def create_access_token(user_id: int, redis_client: Redis) -> str:
    """生成一个唯一的 Token 并存储到 Redis"""
    token = uuid.uuid4().hex  # 生成一个随机的 UUID 作为 Token
    # 将 token -> user_id 映射存储到 Redis，并设置过期时间
    # key 格式: auth_token:{token}
    # value: user_id
    # ex: 过期时间（秒）
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    await redis_client.set(
        f"auth_token:{token}", str(user_id), ex=int(expires_delta.total_seconds())
    )
    return token


async def get_user_id_from_token(token: str, redis_client: Redis) -> Optional[int]:
    """从 Redis 中根据 Token 获取用户 ID"""
    user_id_str = await redis_client.get(f"auth_token:{token}")
    if user_id_str:
        return int(user_id_str)
    return None


async def delete_token(token: str, redis_client: Redis) -> int:
    """从 Redis 中删除 Token"""
    return await redis_client.delete(f"auth_token:{token}")


async def refresh_token_expiration(token: str, redis_client: Redis):
    """
    刷新 Redis 中存储的 Token 的过期时间。
    """
    logger.info(
        f"Attempting to refresh expiration for token: {token[:8]}..."
    )  # 打印 Token 前几位
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # 使用 Redis 的 expire 命令设置新的过期时间
    # 如果 Token 不存在，expire 命令会返回 0
    success = await redis_client.expire(
        f"auth_token:{token}", int(expires_delta.total_seconds())
    )
    if success:
        logger.info(f"Expiration refreshed for token: {token[:8]}...")
    else:
        logger.warning(
            f"Failed to refresh expiration for token: {token[:8]}... (Token not found?)"
        )


# --- FastAPI Dependency for Authentication ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    redis: Annotated[Redis, Depends(get_redis_client)],
    db: Annotated[Session, Depends(get_db)],
) -> schemas.User:
    """
    FastAPI 依赖函数，用于验证 Token 并获取当前用户。
    如果 Token 有效，返回用户对象；否则抛出 401 异常。
    同时，刷新 Token 的过期时间。
    """
    user_id = await get_user_id_from_token(token, redis)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await refresh_token_expiration(token, redis)

    user = db.execute(
        select(models.User).where(models.User.id == user_id)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

    return schemas.User.model_validate(user)


user_dependency = Annotated[schemas.User, Depends(get_current_user)]
db_dependency = Annotated[Session, Depends(get_db)]
redis_dependency = Annotated[Redis, Depends(get_redis_client)]
