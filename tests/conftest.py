"""
Общие фикстуры pytest для тестирования FastAPI.
Создаёт тестовую БД в памяти и подменяет зависимости приложения.
"""
import hashlib
import hmac
import json
import time
import urllib.parse
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# ── Патч: добавляем поддержку JSONB в SQLite-компилятор ──────────────────────
# PostgreSQL JSONB не поддерживается SQLite. Переопределяем visit_JSONB,
# чтобы он использовал то же поведение, что и visit_JSON.
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
SQLiteTypeCompiler.visit_JSONB = SQLiteTypeCompiler.visit_JSON  # type: ignore[attr-defined]

from db.models import Base
from db.session import get_session
from api.main import app
from api.deps import get_current_user
from db.models import User

# ── Тестовая БД в памяти ──────────────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Создаёт и мигрирует тестовую SQLite-БД."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Предоставляет сессию тестовой БД."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


# ── Тестовый пользователь ─────────────────────────────────────────────────────

TEST_USER_ID = 123456789

@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """Создаёт тестового пользователя в БД."""
    user = User(
        telegram_id=TEST_USER_ID,
        mode="personal",
        timezone="Europe/Moscow",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ── HTTP-клиент с обходом авторизации ────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession, test_user: User) -> AsyncGenerator[AsyncClient, None]:
    """
    HTTP-клиент с переопределёнными зависимостями:
    - БД → тестовая in-memory сессия
    - Авторизация → всегда возвращает test_user
    """
    # Подменяем зависимость get_session
    async def override_get_session():
        yield db_session

    # Подменяем авторизацию — всегда test_user
    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    # Убираем переопределения после теста
    app.dependency_overrides.clear()


# ── Генератор валидного initData ──────────────────────────────────────────────

def make_init_data(bot_token: str = "test_token", user_id: int = TEST_USER_ID) -> str:
    """Генерирует валидный Telegram initData для тестов авторизации."""
    user_data = json.dumps({"id": user_id, "first_name": "Тест", "username": "testuser"})
    auth_date = str(int(time.time()))
    params = {
        "auth_date": auth_date,
        "user": user_data,
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    hash_ = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    params["hash"] = hash_
    return urllib.parse.urlencode(params)
