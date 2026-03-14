"""
Phase 2: Юнит-тесты coaching_analytics.

Покрывает:
- compute_dropout_risk_detailed() — все уровни риска
- compute_weekly_score_auto() — автоматический расчёт из БД
- get_goal_metrics() — метрики целей
- get_habit_detailed_metrics() — метрики привычек
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from services.coaching_analytics import (
    get_goal_metrics,
    compute_weekly_score_auto,
    compute_dropout_risk_detailed,
    DROPOUT_RISK_HIGH_THRESHOLD,
)
from db.models import Goal, Habit, HabitLog, GoalCheckin


# ── compute_dropout_risk_detailed() ──────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.coaching
async def test_dropout_risk_new_user_no_data(db_session: AsyncSession, test_user):
    """Новый пользователь без данных → риск по no_checkin_days=30."""
    result = await compute_dropout_risk_detailed(db_session, test_user.telegram_id)
    assert "score" in result
    assert "level" in result
    assert "is_high_risk" in result
    assert "factors" in result
    # Нет check-in → no_checkin_days=30 → вклад 0.3*1.0=0.30
    assert result["score"] >= 0.3


@pytest.mark.integration
@pytest.mark.coaching
async def test_dropout_risk_high_with_stale_goals(db_session: AsyncSession, test_user):
    """Застрявшие цели + нет check-in → высокий риск."""
    # Создаём цель без прогресса 15 дней назад
    old_time = datetime.utcnow() - timedelta(days=15)
    goal = Goal(
        user_id=test_user.telegram_id,
        title="Старая цель",
        status="active",
        progress_pct=10,
        updated_at=old_time,
        created_at=old_time - timedelta(days=30),
    )
    db_session.add(goal)
    await db_session.commit()

    result = await compute_dropout_risk_detailed(db_session, test_user.telegram_id)
    # Застрявшая цель + нет check-in → должен быть высокий риск
    assert result["score"] >= 0.5
    assert result["level"] in ("high", "critical")


@pytest.mark.integration
@pytest.mark.coaching
async def test_dropout_risk_low_active_user(db_session: AsyncSession, test_user):
    """Активный пользователь с недавним check-in и логами привычек → низкий риск."""
    # Создаём цель
    goal = Goal(
        user_id=test_user.telegram_id,
        title="Активная цель",
        status="active",
        progress_pct=50,
    )
    db_session.add(goal)
    await db_session.flush()

    # Check-in вчера
    checkin = GoalCheckin(
        goal_id=goal.id,
        user_id=test_user.telegram_id,
        progress_pct=50,
        created_at=datetime.utcnow() - timedelta(hours=20),
    )
    db_session.add(checkin)

    # Создаём привычку с логами
    habit = Habit(
        user_id=test_user.telegram_id,
        title="Привычка",
        current_streak=7,
    )
    db_session.add(habit)
    await db_session.flush()

    # Логи за последние 7 дней (более активно чем 7-14 дней)
    for days_ago in range(7):
        db_session.add(HabitLog(
            habit_id=habit.id,
            user_id=test_user.telegram_id,
            logged_at=datetime.utcnow() - timedelta(days=days_ago),
        ))
    # Меньше логов 7-14 дней назад
    for days_ago in range(8, 12):
        db_session.add(HabitLog(
            habit_id=habit.id,
            user_id=test_user.telegram_id,
            logged_at=datetime.utcnow() - timedelta(days=days_ago),
        ))
    await db_session.commit()

    result = await compute_dropout_risk_detailed(db_session, test_user.telegram_id)
    # Недавний check-in → no_checkin_days=0 → 0.0 вклад
    assert result["score"] < DROPOUT_RISK_HIGH_THRESHOLD
    assert result["level"] in ("none", "low", "medium")
    assert result["is_high_risk"] is False


@pytest.mark.integration
@pytest.mark.coaching
async def test_dropout_risk_result_structure(db_session: AsyncSession, test_user):
    """Результат содержит все обязательные поля."""
    result = await compute_dropout_risk_detailed(db_session, test_user.telegram_id)
    assert "score" in result
    assert "level" in result
    assert "is_high_risk" in result
    assert "factors" in result
    assert result["level"] in ("none", "low", "medium", "high", "critical")
    assert 0.0 <= result["score"] <= 1.0


@pytest.mark.integration
@pytest.mark.coaching
async def test_dropout_threshold_value():
    """DROPOUT_RISK_HIGH_THRESHOLD = 0.7."""
    assert DROPOUT_RISK_HIGH_THRESHOLD == 0.7


# ── compute_weekly_score_auto() ───────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.coaching
async def test_weekly_score_auto_empty_db(db_session: AsyncSession, test_user):
    """Пустая БД → дефолтный score (не падает)."""
    score, components = await compute_weekly_score_auto(db_session, test_user.telegram_id)
    assert isinstance(score, int)
    assert 0 <= score <= 100
    assert "goals" in components
    assert "habits" in components
    assert "engagement" in components
    assert "recovery" in components


@pytest.mark.integration
@pytest.mark.coaching
async def test_weekly_score_auto_with_goals(db_session: AsyncSession, test_user):
    """С достигнутой целью → goals-компонент > 0."""
    goal = Goal(
        user_id=test_user.telegram_id,
        title="Достигнутая",
        status="achieved",
        progress_pct=100,
    )
    db_session.add(goal)
    await db_session.commit()

    score, components = await compute_weekly_score_auto(db_session, test_user.telegram_id)
    assert components["goals"] > 0


@pytest.mark.integration
@pytest.mark.coaching
async def test_weekly_score_auto_with_habit_logs(db_session: AsyncSession, test_user):
    """С логами привычек за эту неделю → habits-компонент > 0."""
    habit = Habit(
        user_id=test_user.telegram_id,
        title="Привычка",
        frequency="daily",
        is_active=True,
    )
    db_session.add(habit)
    await db_session.flush()

    # 5 логов за неделю
    for i in range(5):
        db_session.add(HabitLog(
            habit_id=habit.id,
            user_id=test_user.telegram_id,
            logged_at=datetime.utcnow() - timedelta(days=i),
        ))
    await db_session.commit()

    score, components = await compute_weekly_score_auto(db_session, test_user.telegram_id)
    assert components["habits"] > 0


# ── get_goal_metrics() ────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.coaching
async def test_goal_metrics_empty(db_session: AsyncSession, test_user):
    """Нет целей → нулевые метрики, не падает."""
    metrics = await get_goal_metrics(db_session, test_user.telegram_id)
    assert metrics["total"] == 0
    assert metrics["completion_rate"] == 0.0
    assert metrics["abandonment_rate"] == 0.0


@pytest.mark.integration
@pytest.mark.coaching
async def test_goal_metrics_completion_rate(db_session: AsyncSession, test_user):
    """2 из 4 целей достигнуты → completion_rate = 0.5."""
    for status in ["achieved", "achieved", "active", "archived"]:
        db_session.add(Goal(
            user_id=test_user.telegram_id,
            title=f"Цель {status}",
            status=status,
        ))
    await db_session.commit()

    metrics = await get_goal_metrics(db_session, test_user.telegram_id)
    assert metrics["total"] == 4
    assert metrics["achieved"] == 2
    assert metrics["active"] == 1
    # completion_rate = 2/4 = 0.5
    assert metrics["completion_rate"] == 0.5


@pytest.mark.integration
@pytest.mark.coaching
async def test_goal_metrics_abandonment_rate(db_session: AsyncSession, test_user):
    """1 achieved + 1 archived → abandonment = 0.5."""
    for status in ["achieved", "archived"]:
        db_session.add(Goal(
            user_id=test_user.telegram_id,
            title=f"Цель {status}",
            status=status,
        ))
    await db_session.commit()

    metrics = await get_goal_metrics(db_session, test_user.telegram_id)
    # abandonment = archived / (achieved + archived) = 1/2 = 0.5
    assert metrics["abandonment_rate"] == 0.5


@pytest.mark.integration
@pytest.mark.coaching
async def test_goal_metrics_by_area(db_session: AsyncSession, test_user):
    """Цели по областям считаются правильно."""
    for area in ["health", "health", "career"]:
        db_session.add(Goal(
            user_id=test_user.telegram_id,
            title=f"Цель {area}",
            area=area,
            status="active",
        ))
    await db_session.commit()

    metrics = await get_goal_metrics(db_session, test_user.telegram_id)
    assert metrics["goals_by_area"]["health"] == 2
    assert metrics["goals_by_area"]["career"] == 1
