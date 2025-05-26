"""add initial admin user

Revision ID: adb84de9e76b
Revises: 1d431efc41e8
Create Date: 2025-05-20 03:19:23.090049

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.models.models import User

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = 'adb84de9e76b'
down_revision: Union[str, None] = '1d431efc41e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    session = Session(bind=bind)

    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    hashed_password = pwd_context.hash("password123")

    # 检查用户是否已存在
    existing_user = session.query(User).filter_by(username="admin").first()
    if not existing_user:
        session.execute(
            sa.insert(User).values(
                username="admin",
                hashed_password=hashed_password,
                is_active=True
            )
        )
        session.commit()
        logger.info("Initial admin user 'admin' added.")
    else:
        logger.info("Initial admin user 'admin' already exists.")

    session.close()
    pass


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    session = Session(bind=bind)
    session.execute(
        sa.delete(User).where(User.username == "admin")
    )
    session.commit()
    session.close()
    pass
