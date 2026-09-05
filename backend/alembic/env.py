import asyncio

from alembic import context
from pomogator.config import get_settings
from pomogator.infrastructure.db import models  # noqa: F401
from pomogator.infrastructure.db.base import Base
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_sync(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_online():
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with engine.connect() as connection:
        await connection.run_sync(run_sync)
    await engine.dispose()


def run_offline():
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    asyncio.run(run_online())
