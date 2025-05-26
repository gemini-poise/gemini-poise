"""add initial default config

Revision ID: 6b16d5da7d2b
Revises: adb84de9e76b
Create Date: 2025-05-20 03:20:49.678841

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app.models.models import Config, User

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '6b16d5da7d2b'
down_revision: Union[str, None] = 'adb84de9e76b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    bind = op.get_bind()
    session = Session(bind=bind)

    default_user_id = 1
    default_user = session.query(User).filter_by(id=default_user_id).first()
    if not default_user:
        logger.warning(f"Default user ID {default_user_id} not found for config initialization! Skipping insertion of default config items.")
        session.close()
        return

    default_configs = [
        {"key": "target_api_url", "value": "https://generativelanguage.googleapis.com/v1beta"},
        {"key": "key_validation_interval_seconds", "value": "3600"},
        {"key": "key_validation_max_failed_count", "value": "3"},
        {"key": "key_validation_timeout_seconds", "value": "10"},
        {"key": "key_validation_model_name", "value": "gemini-1.5-flash"},
    ]

    for config_data in default_configs:
        existing_config = session.query(Config).filter_by(key=config_data["key"]).first()
        if not existing_config:
            session.execute(
                sa.insert(Config).values(
                    key=config_data["key"],
                    value=config_data["value"],
                    updated_by_user_id=default_user_id
                )
            )
            logger.info(f"Default config key '{config_data['key']}' added.")
        else:
            logger.info(f"Default config key '{config_data['key']}' already exists.")

    session.commit()
    session.close()


def downgrade() -> None:
    """Downgrade schema."""

    bind = op.get_bind()
    session = Session(bind=bind)

    config_keys_to_delete = [
        "target_api_url",
        "key_validation_interval_seconds",
        "key_validation_max_failed_count",
        "key_validation_timeout_seconds",
    ]

    for key in config_keys_to_delete:
        deleted_count = session.query(Config).filter(Config.key == key).delete()
        if deleted_count > 0:
            logger.info(f"Default config key '{key}' deleted.")
        else:
            logger.info(f"Default config key '{key}' not found during downgrade.")

    session.commit()
    session.close()
