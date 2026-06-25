"""
Alembic environment configuration for NutriTrack.

Key design choices:
- Uses the DATABASE_URL from app.config (pydantic-settings / .env).
- Alembic's synchronous migration runner requires a non-async connection.
  asyncpg URLs (postgresql+asyncpg://...) are rewritten to psycopg2-compatible
  URLs (postgresql://...) for the synchronous connection used here.
- target_metadata is set to Base.metadata so autogenerate can diff the schema.
"""

import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import Base and all models so their metadata is populated before autogenerate runs.
# Importing models here ensures every table is registered with Base.metadata.
from app.db.models import Base  # noqa: F401 — side-effect import registers models

config = context.config

# Set up Python logging from the alembic.ini [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The metadata object Alembic diffs against when running --autogenerate.
target_metadata = Base.metadata


def _sync_database_url() -> str:
    """
    Convert an asyncpg URL to a psycopg2-compatible synchronous URL.

    Alembic's migration runner is synchronous and cannot use asyncpg directly.
    Replace the driver portion only; all other URL components remain unchanged.

    Examples:
        postgresql+asyncpg://user:pass@host:5432/db
        → postgresql+psycopg2://user:pass@host:5432/db

        postgresql+asyncpg://user:pass@host:5432/db?sslmode=require
        → postgresql+psycopg2://user:pass@host:5432/db?sslmode=require
    """
    # Import here to avoid circular import at module load.
    from app.config import settings

    url = settings.database_url
    # Replace asyncpg driver with psycopg2.  If the URL already uses psycopg2
    # (or a bare postgresql:// scheme) leave it unchanged.
    url = re.sub(r"^postgresql\+asyncpg://", "postgresql+psycopg2://", url)
    url = re.sub(r"^postgresql\+asyncio://", "postgresql+psycopg2://", url)
    return url


def run_migrations_offline() -> None:
    """
    Offline mode: emit SQL to stdout without connecting to the DB.

    Useful for generating a migration script to review or run manually.
    """
    url = _sync_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Render the CREATE/DROP for items not in metadata as part of autogenerate.
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Online mode: connect to the DB and apply migrations directly.

    This is the standard path for `alembic upgrade head`.
    """
    # Override the sqlalchemy.url from alembic.ini with the value from our config.
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _sync_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # no connection pooling in migration scripts
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # detect column type changes during autogenerate
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
