"""
Alembic environment configuration for async SQLAlchemy.

This module configures Alembic to work with async database operations.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import your models' MetaData object here
# Import Base from database module (which also imports from models)
from src.database import Base

# Import all models to ensure they're registered with Base.metadata
# Core models for all specs
from src.models import protocol_state  # noqa: F401
from src.models import discussion  # noqa: F401
from src.models import round  # noqa: F401
from src.models import participant  # noqa: F401
from src.models import submission  # noqa: F401
from src.models import approved_summary  # noqa: F401
from src.models import thought_space  # noqa: F401
from src.models import flow  # noqa: F401

# Spec 002: Input Collection - SubmissionMetadata model
from src.models import submission_metadata  # noqa: F401

# Spec 004: Clustering & Alignment models
from src.models import embedding  # noqa: F401
from src.models import cluster  # noqa: F401
from src.models import cluster_member  # noqa: F401
from src.models import alignment  # noqa: F401

# Spec 006: Question Progression models
try:
    from src.question_progression import models as question_models  # noqa: F401
except ImportError:
    pass  # Question progression models may not be available yet

target_metadata = Base.metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import settings to get database URL
try:
    from src.config import settings

    # Override sqlalchemy.url with value from settings
    config.set_main_option("sqlalchemy.url", str(settings.database_url))
except ImportError:
    # If src.config is not available yet, use environment variable
    import os

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://opendiscuss:opendiscuss_dev@localhost:5432/opendiscuss",
    )
    config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations with the provided connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode with async engine.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    configuration = config.get_section(config.config_ini_section, {})

    # Use asyncpg for PostgreSQL async operations
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (async)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
