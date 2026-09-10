"""Alembic migration environment for AURORA.

Pulls the database URL from app settings (env vars / .env) rather than
alembic.ini, so migrations always target the same database the API uses --
no need to keep a URL in two places.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.config import get_settings
from app.database import Base
from app import models  # noqa: F401 - register all ORM tables on Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)

target_metadata = Base.metadata

# PostGIS creates its own bookkeeping tables (spatial_ref_sys, and the
# topology/tiger extras if those extensions are ever enabled). They aren't
# part of our ORM models, so without this filter autogenerate treats them as
# tables we "removed" and tries to drop them on every revision.
_POSTGIS_SYSTEM_TABLES = {"spatial_ref_sys", "layer", "topology"}


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in _POSTGIS_SYSTEM_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (emits SQL only)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
