"""update inactive api_keys to exhausted on startup

Revision ID: 49ae181f3372
Revises: 47c2f4eaa5ea
Create Date: 2025-06-06 19:26:49.125464

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '49ae181f3372'
down_revision: Union[str, None] = '47c2f4eaa5ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("UPDATE api_keys SET status = 'exhausted' WHERE status = 'inactive';")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE api_keys SET status = 'inactive' WHERE status = 'exhausted';")
