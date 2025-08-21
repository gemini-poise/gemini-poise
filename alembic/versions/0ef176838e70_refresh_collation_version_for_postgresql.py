"""refresh_collation_version_for_postgresql

Revision ID: 0ef176838e70
Revises: 2e8df17f89b6
Create Date: 2025-08-21 13:23:13.642962

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0ef176838e70'
down_revision: Union[str, None] = '2e8df17f89b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 检查是否为PostgreSQL数据库
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        try:
            # 刷新数据库排序规则版本以解决版本不匹配警告
            op.execute("ALTER DATABASE gemini_poise REFRESH COLLATION VERSION;")
            print("Successfully refreshed PostgreSQL collation version for database 'gemini_poise'")
        except Exception as e:
            # 如果执行失败，记录警告但不中断迁移
            print(f"Warning: Failed to refresh collation version: {e}")
            print("This is not critical and the database will continue to work normally.")


def downgrade() -> None:
    """Downgrade schema."""
    # 排序规则版本刷新是一次性操作，不需要回滚
    pass
