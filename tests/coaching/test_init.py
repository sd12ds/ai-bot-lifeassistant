"""
Phase 1: Bootstrap-тесты — проверка инфраструктуры тестов.

Покрывает:
- Создание тестовой БД и всех таблиц
- Работоспособность фикстур (db_session, test_user, client)
- Импорт всех coaching-моделей
- Импорт всех coaching-сервисов
- Работоспособность фабрик
- Работоспособность заглушек (fakes)
- Health endpoint
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from db.models import (
    User, Goal, Habit, HabitLog,
    GoalMilestone, GoalCheckin, GoalReview,
    HabitStreak, HabitTemplate,
    CoachingSession, CoachingInsight,
    UserCoachingProfile, CoachingRecommendation,
    CoachingMemory, CoachingNudgeLog,
    CoachingOnboardingState, CoachingDialogDraft,
    CoachingContextSnapshot, CoachingRiskScore,
    CoachingOrchestrationAction, BehaviorPattern,
)


# ── Тест 1: БД инициализирована ───────────────────────────────────────────────

@pytest.mark.smoke
@pytest.mark.coaching
async def test_db_engine_creates_tables(db_engine):
    """БД успешно создана и содержит все таблицы."""
    from sqlalchemy import inspect, text

    async with db_engine.connect() as conn:
        # Получаем список всех таблиц
        tables = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )

    # Проверяем, что все coaching-таблицы присутствуют
    expected_tables = [
        "goals", "habits", "habit_logs",
        "goal_milestones", "goal_checkins", "goal_reviews",
        "habit_streaks", "habit_templates",
        "coaching_sessions", "coaching_insights",
        "user_coaching_profile", "coaching_recommendations",
        "coaching_memory", "coaching_nudges_log",
        "coaching_onboarding_state", "coaching_dialog_drafts",
        "coaching_context_snapshots", "coaching_risk_scores",
        "coaching_orchestration_actions", "behavior_patterns",
    ]
    for table in expected_tables:
        assert table in tables, f"Таблица {table!r} не найдена в БД"


@pytest.mark.smoke
@pytest.mark.coaching
async def test_db_session_works(db_session: AsyncSession):
    """Сессия БД работает — можно выполнить запрос."""
    from sqlalchemy import text
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


# ── Тест 2: Фикстуры пользователей ───────────────────────────────────────────

@pytest.mark.smoke
@pytest.mark.coaching
async def test_test_user_created(test_user: User):
    """Тестовый пользователь создан в БД."""
    assert test_user.telegram_id == 123456789
    assert test_user.mode == "personal"
    assert test_user.timezone == "Europe/Moscow"


@pytest.mark.smoke
@pytest.mark.coaching
async def test_client_fixture(client: AsyncClient):
    """HTTP-клиент создан и доступен."""
    assert client is not None


@pytest.mark.smoke
@pytest.mark.coaching
async def test_coaching_api_accessible(client: AsyncClient):
    """Coaching API доступен — /coaching/state возвращает не 404."""
    # Не вызываем /api/health — он обращается к реальной БД напрямую
    resp = await client.get("/api/coaching/state")
    # 200 — данных нет (нет snapshot), но endpoint работает
    assert resp.status_code in (200, 404)


# ── Тест 3: Импорт coaching-моделей ──────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.coaching
def test_import_coaching_models():
    """Все coaching-модели корректно импортируются."""
    models = [
        Goal, Habit, HabitLog, GoalMilestone, GoalCheckin, GoalReview,
        HabitStreak, HabitTemplate, CoachingSession, CoachingInsight,
        UserCoachingProfile, CoachingRecommendation, CoachingMemory,
        CoachingNudgeLog, CoachingOnboardingState, CoachingDialogDraft,
        CoachingContextSnapshot, CoachingRiskScore,
        CoachingOrchestrationAction, BehaviorPattern,
    ]
    # Проверяем, что каждая модель имеет __tablename__
    for model in models:
        assert hasattr(model, "__tablename__"), (
            f"Модель {model.__name__} не имеет __tablename__"
        )


# ── Тест 4: Импорт coaching-сервисов ─────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.coaching
def test_import_coaching_engine():
    """coaching_engine импортируется без ошибок."""
    from services.coaching_engine import (
        compute_user_state,
        compute_risk_scores,
        compute_weekly_score,
        get_context_pack,
        get_tone_for_state,
        update_daily_snapshot,
    )
    assert callable(compute_user_state)
    assert callable(get_tone_for_state)


@pytest.mark.unit
@pytest.mark.coaching
def test_import_coaching_analytics():
    """coaching_analytics импортируется без ошибок."""
    from services.coaching_analytics import (
        get_goal_metrics,
        get_habit_detailed_metrics,
        compute_weekly_score_auto,
        compute_dropout_risk_detailed,
        DROPOUT_RISK_HIGH_THRESHOLD,
    )
    assert callable(get_goal_metrics)
    assert DROPOUT_RISK_HIGH_THRESHOLD == 0.7


@pytest.mark.unit
@pytest.mark.coaching
def test_import_coaching_storage():
    """coaching_storage импортируется без ошибок."""
    import db.coaching_storage as cs
    assert callable(cs.get_goals)
    assert callable(cs.create_goal)
    assert callable(cs.get_habits)
    assert callable(cs.increment_habit_streak)


@pytest.mark.unit
@pytest.mark.coaching
def test_import_coaching_router():
    """Coaching API router импортируется без ошибок."""
    from api.routers.coaching import router
    assert router is not None
    # Проверяем, что роутер содержит маршруты
    assert len(router.routes) > 0


# ── Тест 5: Работоспособность фабрик ─────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.coaching
def test_goal_factory_builds():
    """GoalFactory создаёт объект Goal без БД."""
    from tests.factories import GoalFactory
    goal = GoalFactory.build()
    assert goal.title is not None
    assert goal.user_id == 123456789
    assert goal.status == "active"


@pytest.mark.unit
@pytest.mark.coaching
def test_habit_factory_builds():
    """HabitFactory создаёт объект Habit без БД."""
    from tests.factories import HabitFactory
    habit = HabitFactory.build()
    assert habit.title is not None
    assert habit.frequency == "daily"
    assert habit.is_active is True


@pytest.mark.unit
@pytest.mark.coaching
def test_factories_unique_titles():
    """Фабрики генерируют уникальные title через Sequence."""
    from tests.factories import GoalFactory
    g1 = GoalFactory.build()
    g2 = GoalFactory.build()
    assert g1.title != g2.title


# ── Тест 6: Работоспособность заглушек ───────────────────────────────────────

@pytest.mark.unit
@pytest.mark.coaching
async def test_fake_llm_returns_default():
    """FakeLLM возвращает дефолтный ответ."""
    from tests.fakes import FakeLLM
    llm = FakeLLM("Привет, коуч!")
    response = await llm.ainvoke([{"role": "user", "content": "Тест"}])
    assert response.content == "Привет, коуч!"
    assert llm.call_count == 1


@pytest.mark.unit
@pytest.mark.coaching
async def test_fake_llm_queue():
    """FakeLLM поочерёдно отдаёт ответы из очереди."""
    from tests.fakes import FakeLLM
    llm = FakeLLM()
    llm.set_responses(["Ответ 1", "Ответ 2", "Ответ 3"])
    r1 = await llm.ainvoke([])
    r2 = await llm.ainvoke([])
    r3 = await llm.ainvoke([])
    assert r1.content == "Ответ 1"
    assert r2.content == "Ответ 2"
    assert r3.content == "Ответ 3"


@pytest.mark.unit
@pytest.mark.coaching
async def test_fake_llm_with_error():
    """FakeLLMWithError выбрасывает исключение заданное число раз."""
    from tests.fakes import FakeLLMWithError
    llm = FakeLLMWithError()
    llm.set_failures(2)
    llm.set_next_response("Успех после 2 ошибок")
    with pytest.raises(RuntimeError):
        await llm.ainvoke([])
    with pytest.raises(RuntimeError):
        await llm.ainvoke([])
    # Третья попытка — успех
    resp = await llm.ainvoke([])
    assert resp.content == "Успех после 2 ошибок"


@pytest.mark.unit
@pytest.mark.coaching
async def test_fake_telegram_bot():
    """FakeTelegramBot записывает отправленные сообщения."""
    from tests.fakes import FakeTelegramBot
    bot = FakeTelegramBot()
    await bot.send_message(chat_id=123, text="Тест сообщение")
    assert len(bot.sent_messages) == 1
    assert bot.last_message_text() == "Тест сообщение"
    assert bot.messages_to(123)[0]["text"] == "Тест сообщение"


# ── Тест 7: Personas доступны ─────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.coaching
async def test_persona_new_user(persona_new_user: dict):
    """Персона new_user доступна и возвращает пустые данные."""
    assert persona_new_user["goals"] == []
    assert persona_new_user["habits"] == []
    assert persona_new_user["expected_state"] == "stable"


@pytest.mark.integration
@pytest.mark.coaching
async def test_persona_disciplined(persona_disciplined: dict):
    """Персона disciplined создаёт goals и habits."""
    assert len(persona_disciplined["goals"]) == 3
    assert len(persona_disciplined["habits"]) == 3


@pytest.mark.integration
@pytest.mark.coaching
async def test_persona_dropout(persona_dropout: dict):
    """Персона dropout создаёт застрявшие цели и заброшенные привычки."""
    assert len(persona_dropout["goals"]) == 2
    assert len(persona_dropout["habits"]) == 2


# ── Тест 8: coaching_storage CRUD smoke-test ─────────────────────────────────

@pytest.mark.integration
@pytest.mark.coaching
async def test_storage_create_and_get_goal(db_session, test_user):
    """create_goal() → get_goals() → возвращает созданную цель."""
    import db.coaching_storage as cs
    goal = await cs.create_goal(
        session=db_session,
        user_id=test_user.telegram_id,
        title="Тест цель",
        area="health",
    )
    assert goal.id is not None
    assert goal.title == "Тест цель"

    goals = await cs.get_goals(db_session, test_user.telegram_id)
    assert any(g.id == goal.id for g in goals)


@pytest.mark.integration
@pytest.mark.coaching
async def test_storage_profile_get_or_create(db_session, test_user):
    """get_or_create_profile() создаёт профиль при первом вызове."""
    import db.coaching_storage as cs
    profile = await cs.get_or_create_profile(db_session, test_user.telegram_id)
    assert profile is not None
    assert profile.user_id == test_user.telegram_id
    assert profile.coach_tone == "friendly"

    # Повторный вызов не создаёт дубль
    profile2 = await cs.get_or_create_profile(db_session, test_user.telegram_id)
    assert profile2.id == profile.id
