import os
import sys
from dotenv import load_dotenv

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv()

from app.core.config import settings
from app.core.database import Base, engine

from app.models import models # 确保这行存在且没有注释

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None # 保留这行，它是模板的一部分

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # --- 添加调试打印 ---
    print("--- Running migrations in OFFLINE mode ---")
    # --- 调试打印结束 ---

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine

    try: # 添加 try-except 块，捕获连接或配置时的错误
        with connectable.connect() as connection:
            print("--- Database connection successful ---")
            context.configure(
                connection=connection,
                target_metadata=Base.metadata,
                # compare_type=True
            )
            print(f"Base.metadata.tables keys (after configure): {Base.metadata.tables.keys()}")
            with context.begin_transaction():
                context.run_migrations()
        print("--- Online migrations finished ---")
    except Exception as e:
        print(f"--- Error during online migration setup or execution: {e} ---")
        # 重新抛出异常，以便在终端看到详细错误
        raise


# --- 添加调试打印 ---
print("--- Reached end of env.py script, deciding mode ---")
print(f"context.is_offline_mode(): {context.is_offline_mode()}")
# --- 调试打印结束 ---

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

# --- 添加调试打印 ---
print("--- env.py script finished ---")
# --- 调试打印结束 ---
