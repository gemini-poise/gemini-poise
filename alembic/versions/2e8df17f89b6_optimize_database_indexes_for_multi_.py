"""optimize database indexes for multi-database support

Revision ID: 2e8df17f89b6
Revises: 09d1f06cdc66
Create Date: 2025-08-10 16:30:19.275693

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e8df17f89b6'
down_revision: Union[str, None] = '09d1f06cdc66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def get_database_type():
    """Detect the database type from the connection"""
    conn = op.get_bind()
    dialect = conn.dialect.name.lower()
    return dialect


def create_index_safely(index_name: str, table_name: str, columns: list, unique: bool = False):
    """Create index with database-specific optimizations"""
    db_type = get_database_type()
    
    if db_type == 'postgresql':
        # PostgreSQL: Use CONCURRENTLY to avoid blocking
        try:
            op.create_index(
                index_name, table_name, columns, 
                unique=unique, postgresql_concurrently=True
            )
        except Exception:
            # Fallback to regular index creation if concurrent fails
            op.create_index(index_name, table_name, columns, unique=unique)
    
    elif db_type == 'mysql':
        # MySQL: Create index normally (MySQL handles locking well)
        op.create_index(index_name, table_name, columns, unique=unique)
        
    elif db_type == 'sqlite':
        # SQLite: Create index normally
        op.create_index(index_name, table_name, columns, unique=unique)
    
    else:
        # Fallback for other databases
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    """Add composite indexes for better query performance across all supported databases"""
    db_type = get_database_type()
    
    # Index for API keys status and last_used_at for key selection optimization
    create_index_safely(
        'idx_api_keys_status_last_used',
        'api_keys',
        ['status', 'last_used_at']
    )
    
    # Index for API call logs for time-based queries
    create_index_safely(
        'idx_api_call_logs_api_key_timestamp',
        'api_call_logs',
        ['api_key_id', 'timestamp']
    )
    
    # Index for API keys failed_count for error handling
    create_index_safely(
        'idx_api_keys_failed_count',
        'api_keys',
        ['failed_count']
    )
    
    # Index for API keys usage_count for statistics
    create_index_safely(
        'idx_api_keys_usage_count',
        'api_keys',
        ['usage_count']
    )
    
    # Database-specific optimizations
    if db_type == 'postgresql':
        # PostgreSQL specific: Add partial indexes for better performance
        conn = op.get_bind()
        conn.execute(text(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_keys_active "
            "ON api_keys (id, last_used_at) WHERE status = 'active'"
        ))
        
    elif db_type == 'mysql':
        # MySQL specific: Optimize for InnoDB storage engine
        conn = op.get_bind()
        conn.execute(text(
            "ALTER TABLE api_keys ENGINE=InnoDB ROW_FORMAT=COMPRESSED"
        ))
        
    elif db_type == 'sqlite':
        # SQLite specific: Analyze tables after index creation
        conn = op.get_bind()
        conn.execute(text("ANALYZE"))
        conn.execute(text("PRAGMA optimize"))


def downgrade() -> None:
    """Remove indexes and database-specific optimizations"""
    db_type = get_database_type()
    
    # Remove database-specific optimizations first
    if db_type == 'postgresql':
        # PostgreSQL specific: Remove partial index
        conn = op.get_bind()
        conn.execute(text("DROP INDEX CONCURRENTLY IF EXISTS idx_api_keys_active"))
        
    elif db_type == 'mysql':
        # MySQL specific: Revert table optimization (optional)
        pass
        
    elif db_type == 'sqlite':
        # SQLite specific: No specific cleanup needed
        pass
    
    # Remove indexes in reverse order
    op.drop_index('idx_api_keys_usage_count', table_name='api_keys')
    op.drop_index('idx_api_keys_failed_count', table_name='api_keys')
    op.drop_index('idx_api_call_logs_api_key_timestamp', table_name='api_call_logs')
    op.drop_index('idx_api_keys_status_last_used', table_name='api_keys')