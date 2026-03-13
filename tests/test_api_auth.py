"""
pytest-тесты авторизации: X-Init-Data header, HMAC-SHA256 верификация.
"""
import hashlib
import hmac
import json
import os
import time
import urllib.parse
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from db.models import Base
from db.session import get_session
from api.main import app
from api.deps import get_current_user

# Используем тестовый токен, совпадающий с make_init_data
TEST_BOT_TOKEN = "test_token"

# ── Вспомогательная фикстура клиента БЕЗ переопределения auth ────────────────

@pytest_asyncio.fixture
async def raw_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    HTTP-клиент с подменой только БД-сессии.
    Авторизация работает через настоящий get_current_user (HMAC-проверка).
    """
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_session, None)


# ── Вспомогательная функция генерации initData ────────────────────────────────

def build_init_data(
    user_id: int = 111111,
    bot_token: str = TEST_BOT_TOKEN,
    auth_date: int | None = None,
    add_hash: bool = True,
    corrupt_hash: bool = False,
) -> str:
    """Собирает валидный (или нарочно сломанный) Telegram initData."""
    if auth_date is None:
        auth_date = int(time.time())

    user_json = json.dumps({"id": user_id, "first_name": "Test", "username": "testuser"})
    params = {
        "auth_date": str(auth_date),
        "user": user_json,
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    correct_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if add_hash:
        params["hash"] = "badhash0000000000" if corrupt_hash else correct_hash

    return urllib.parse.urlencode(params)


# ── Тесты ─────────────────────────────────────────────────────────────────────

class TestAuthMiddleware:
    async def test_missing_header_returns_401(self, raw_client: AsyncClient):
        """Запрос без X-Init-Data → 401/422."""
        r = await raw_client.get("/api/tasks/")
        # FastAPI может вернуть 422 (missing required header) или 401
        assert r.status_code in (401, 422)

    async def test_invalid_signature_returns_401(self, raw_client: AsyncClient, monkeypatch):
        """Неверная подпись → 401 Invalid signature."""
        monkeypatch.setattr("api.deps.BOT_TOKEN", TEST_BOT_TOKEN)
        bad_init_data = build_init_data(corrupt_hash=True)
        r = await raw_client.get(
            "/api/tasks/",
            headers={"X-Init-Data": bad_init_data},
        )
        assert r.status_code == 401
        assert "signature" in r.json().get("detail", "").lower() or r.status_code == 401

    async def test_missing_hash_returns_401(self, raw_client: AsyncClient, monkeypatch):
        """initData без поля hash → 401 Missing hash."""
        monkeypatch.setattr("api.deps.BOT_TOKEN", TEST_BOT_TOKEN)
        no_hash_data = build_init_data(add_hash=False)
        r = await raw_client.get(
            "/api/tasks/",
            headers={"X-Init-Data": no_hash_data},
        )
        assert r.status_code == 401

    async def test_expired_init_data_returns_401(self, raw_client: AsyncClient, monkeypatch):
        """initData с auth_date > 1 часа назад → 401 expired."""
        monkeypatch.setattr("api.deps.BOT_TOKEN", TEST_BOT_TOKEN)
        old_date = int(time.time()) - 7200  # 2 часа назад
        expired_data = build_init_data(auth_date=old_date)
        r = await raw_client.get(
            "/api/tasks/",
            headers={"X-Init-Data": expired_data},
        )
        assert r.status_code == 401

    async def test_valid_init_data_creates_user(self, raw_client: AsyncClient, monkeypatch, db_session):
        """Валидный initData создаёт пользователя в БД и возвращает 200."""
        monkeypatch.setattr("api.deps.BOT_TOKEN", TEST_BOT_TOKEN)
        valid_data = build_init_data(user_id=777777)
        r = await raw_client.get(
            "/api/tasks/",
            headers={"X-Init-Data": valid_data},
        )
        assert r.status_code == 200

        # Проверяем что пользователь появился в БД
        from sqlalchemy import select
        from db.models import User
        result = await db_session.execute(select(User).where(User.telegram_id == 777777))
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.telegram_id == 777777

    async def test_valid_init_data_reuses_existing_user(self, raw_client: AsyncClient, monkeypatch, db_session):
        """Повторный запрос с тем же initData не создаёт дубль пользователя."""
        monkeypatch.setattr("api.deps.BOT_TOKEN", TEST_BOT_TOKEN)
        valid_data = build_init_data(user_id=888888)

        # Два запроса с одними данными
        await raw_client.get("/api/tasks/", headers={"X-Init-Data": valid_data})
        await raw_client.get("/api/tasks/", headers={"X-Init-Data": valid_data})

        from sqlalchemy import select, func
        from db.models import User
        result = await db_session.execute(
            select(func.count()).where(User.telegram_id == 888888)
        )
        count = result.scalar()
        assert count == 1  # Только один пользователь

    async def test_wrong_token_returns_401(self, raw_client: AsyncClient, monkeypatch):
        """initData подписан другим токеном → 401."""
        monkeypatch.setattr("api.deps.BOT_TOKEN", "correct_token")
        # Подписываем с другим токеном
        wrong_data = build_init_data(bot_token="wrong_token")
        r = await raw_client.get(
            "/api/tasks/",
            headers={"X-Init-Data": wrong_data},
        )
        assert r.status_code == 401

    async def test_tasks_isolated_per_user(self, raw_client: AsyncClient, monkeypatch):
        """Пользователь видит только свои задачи."""
        monkeypatch.setattr("api.deps.BOT_TOKEN", TEST_BOT_TOKEN)

        user_a_data = build_init_data(user_id=100001)
        user_b_data = build_init_data(user_id=100002)

        # Пользователь A создаёт задачу
        r = await raw_client.post(
            "/api/tasks/",
            json={"title": "Задача пользователя A"},
            headers={"X-Init-Data": user_a_data},
        )
        assert r.status_code == 201

        # Пользователь B видит пустой список
        r = await raw_client.get(
            "/api/tasks/",
            headers={"X-Init-Data": user_b_data},
        )
        assert r.status_code == 200
        assert r.json() == []
