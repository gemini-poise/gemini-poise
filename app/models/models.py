from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    TIMESTAMP,
    func,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from ..core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key_value = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default="active", nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    last_used_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)


class Config(Base):
    __tablename__ = "config"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_by_user = relationship("User", uselist=False)


class ApiCallLog(Base):
    __tablename__ = "api_call_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=False)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    call_count = Column(Integer, default=0)

    api_key = relationship("ApiKey", uselist=False)
