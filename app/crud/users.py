import logging

from sqlalchemy.orm import Session

from ..core.security import get_password_hash
from ..models import models
from ..schemas import schemas

logger = logging.getLogger(__name__)


def get_user_by_username(db: Session, username: str):
    """根据用户名获取用户。"""
    logger.info(f"Attempting to get user by username: {username}")
    user = db.query(models.User).filter(models.User.username == username).first()
    logger.info(f"Result for user '{username}': {user}")
    return user


def create_user(db: Session, user: schemas.UserCreate):
    """创建一个新用户。"""
    logger.info(f"--- Attempting to create user: {user.username} ---")
    hashed_password = get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    logger.info(f"--- User {user.username} added and committed to DB ---")
    db.refresh(db_user)
    logger.info(f"--- User {user.username} refreshed, ID: {db_user.id} ---")
    return db_user


def get_user(db: Session, user_id: int):
    """根据用户 ID 获取用户。"""
    logger.info(f"Attempting to get user by ID: {user_id}")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    logger.info(f"Result for user ID '{user_id}': {user}")
    return user


def update_user_password(db: Session, user_id: int, new_hashed_password: str):
    """更新用户密码。"""
    logger.info(f"Attempting to update password for user ID: {user_id}")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.hashed_password = new_hashed_password
        db.commit()
        db.refresh(user)
        logger.info(f"Password updated successfully for user ID: {user_id}")
        return user
    else:
        logger.warning(f"User with ID {user_id} not found")
        return None
