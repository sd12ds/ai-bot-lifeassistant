"""
Alembic env.py — асинхронный режим для SQLAlchemy 2.x + asyncpg.
DATABASE_URL читается из переменной окружения или .env файла.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Добавляем корень проекта в sys.path чтобы импортировать db.models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Загружаем .env если есть python-dotenv
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
except ImportError:
    pass

from db.models import Base  # импортируем все модели

# Конфигурация из alembic.ini
config = context.config

# Логирование
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные всех моделей — для autogenerate
target_metadata = Base.metadata

# DATABASE_URL из переменной окружения
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://aiuser:changeme@localhost:5432/aiassistant"
)
# Alembic требует sync-URL для некоторых операций — используем asyncpg через run_sync
config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_offline() -> None:
    """Оффлайн-режим — генерирует SQL без подключения к БД."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Онлайн-режим — асинхронное подключение через asyncpg."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    import asyncio
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
