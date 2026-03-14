"""
Общие фикстуры pytest для тестирования FastAPI.
Создаёт тестовую БД в памяти и подменяет зависимости приложения.
"""
import hashlib
import hmac
import json
import time
import urllib.parse
from datetime import datetime, timedelta
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


# ── Coaching Personas — специализированные фикстуры для coaching-тестов ───────

@pytest_asyncio.fixture(scope="function")
async def persona_disciplined(db_session: AsyncSession, test_user: User) -> dict:
    """
    Персона «Дисциплинированный»:
    - 3 активных цели с прогрессом
    - 3 привычки с хорошими стриками (7-14 дней)
    - последний check-in 1 день назад
    Ожидаемое состояние: momentum или stable.
    """
    from db.models import Goal, Habit, HabitLog, GoalCheckin
    from tests.factories import GoalFactory, HabitFactory

    # Создаём цели
    goals = []
    for i, area in enumerate(["health", "career", "finance"]):
        goal = GoalFactory.build(
            user_id=test_user.telegram_id,
            title=f"Цель {area}",
            area=area,
            progress_pct=60 + i * 10,
            status="active",
        )
        db_session.add(goal)
        goals.append(goal)
    await db_session.flush()

    # Создаём привычки с хорошими стриками
    habits = []
    for i in range(3):
        habit = HabitFactory.build(
            user_id=test_user.telegram_id,
            title=f"Привычка {i}",
            current_streak=7 + i * 2,
            longest_streak=14,
            total_completions=30,
        )
        db_session.add(habit)
        habits.append(habit)
    await db_session.flush()

    # Логируем привычки за последние 7 дней
    for habit in habits:
        for days_ago in range(7):
            log = HabitLog(
                habit_id=habit.id,
                user_id=test_user.telegram_id,
                logged_at=datetime.utcnow() - timedelta(days=days_ago),
                value=1,
            )
            db_session.add(log)

    # Check-in вчера
    checkin = GoalCheckin(
        goal_id=goals[0].id,
        user_id=test_user.telegram_id,
        progress_pct=65,
        energy_level=4,
        notes="Всё идёт хорошо",
        created_at=datetime.utcnow() - timedelta(days=1),
    )
    db_session.add(checkin)
    await db_session.commit()

    return {
        "user": test_user,
        "goals": goals,
        "habits": habits,
        "expected_state": "momentum",
    }


@pytest_asyncio.fixture(scope="function")
async def persona_dropout(db_session: AsyncSession, test_user: User) -> dict:
    """
    Персона «Риск дропаута»:
    - 2 цели без прогресса 10+ дней
    - привычки с нулевым стриком, нет логов 7 дней
    - нет check-in 14+ дней
    Ожидаемое состояние: risk.
    """
    from db.models import Goal, Habit
    from tests.factories import GoalFactory, HabitFactory

    # Цели без прогресса (обновлены 15 дней назад)
    old_time = datetime.utcnow() - timedelta(days=15)
    goals = []
    for i in range(2):
        goal = GoalFactory.build(
            user_id=test_user.telegram_id,
            title=f"Застрявшая цель {i}",
            status="active",
            progress_pct=10,
            updated_at=old_time,
            created_at=old_time - timedelta(days=30),
        )
        db_session.add(goal)
        goals.append(goal)
    await db_session.flush()

    # Привычки с нулевым стриком
    habits = []
    for i in range(2):
        habit = HabitFactory.build(
            user_id=test_user.telegram_id,
            title=f"Заброшенная привычка {i}",
            current_streak=0,
            longest_streak=5,
            total_completions=5,
            last_logged_at=datetime.utcnow() - timedelta(days=10),
        )
        db_session.add(habit)
        habits.append(habit)
    await db_session.commit()

    return {
        "user": test_user,
        "goals": goals,
        "habits": habits,
        "expected_state": "risk",
    }


@pytest_asyncio.fixture(scope="function")
async def persona_new_user(db_session: AsyncSession, test_user: User) -> dict:
    """
    Персона «Новый пользователь»:
    - нет целей, нет привычек, нет check-in
    - только что зарегистрировался
    Ожидаемое состояние: stable (нет негативных сигналов).
    """
    return {
        "user": test_user,
        "goals": [],
        "habits": [],
        "expected_state": "stable",
    }
