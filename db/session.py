"""
Фабрика асинхронных сессий SQLAlchemy для FastAPI и бота.
DATABASE_URL читается из переменной окружения.
"""
import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Фолбэк на SQLite для обратной совместимости с ботом (пока не переключим)
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "sqlite+aiosqlite:////root/ai-assistant/db/app.db",
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """FastAPI dependency — выдаёт сессию и закрывает после запроса."""
    async with AsyncSessionLocal() as session:
        yield session
