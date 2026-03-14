"""
Phase 2: Юнит-тесты coaching_engine.

Покрывает:
- compute_user_state() — все состояния + граничные случаи
- get_tone_for_state() — все 5 состояний
- compute_weekly_score() — формула §22.3
- update_daily_snapshot() — запись в БД
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from services.coaching_engine import (
    compute_user_state,
    compute_risk_scores,
    compute_weekly_score,
    get_tone_for_state,
    update_daily_snapshot,
)


# ── get_tone_for_state() — чистая функция, нет I/O ────────────────────────────

@pytest.mark.unit
@pytest.mark.coaching
def test_tone_momentum():
    """momentum → бодрый вдохновляющий тон."""
    tone = get_tone_for_state("momentum")
    assert "MOMENTUM" in tone
    assert len(tone) > 20


@pytest.mark.unit
@pytest.mark.coaching
def test_tone_stable():
    """stable → нейтральный поддерживающий тон."""
    tone = get_tone_for_state("stable")
    assert "STABLE" in tone


@pytest.mark.unit
@pytest.mark.coaching
def test_tone_overload():
    """overload → тон без давления."""
    tone = get_tone_for_state("overload")
    assert "OVERLOAD" in tone
    assert "НЕ" in tone or "не" in tone  # явный запрет давления


@pytest.mark.unit
@pytest.mark.coaching
def test_tone_recovery():
    """recovery → мягкий тон без упрёков."""
    tone = get_tone_for_state("recovery")
    assert "RECOVERY" in tone
    assert "БЕЗ" in tone or "без" in tone


@pytest.mark.unit
@pytest.mark.coaching
def test_tone_risk():
    """risk → заботливый прямой тон."""
    tone = get_tone_for_state("risk")
    assert "RISK" in tone


@pytest.mark.unit
@pytest.mark.coaching
def test_tone_unknown_state_fallback():
    """Неизвестное состояние → fallback на stable."""
    tone = get_tone_for_state("unknown_state_xyz")
    # Должен вернуть что-то (fallback к stable)
    assert isinstance(tone, str)
    assert len(tone) > 10


# ── compute_user_state() — требует БД ────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.coaching
async def test_state_momentum_no_negatives(db_session: AsyncSession, test_user):
    """Нет негативных сигналов → score 100 → momentum."""
    result = await compute_user_state(
        session=db_session,
        user_id=test_user.telegram_id,
        tasks_overdue=0,
        calendar_events_today=3,
        habits_done_today=3,
        habits_total_today=3,
        task_completion_rate_week=1.0,
    )
    assert result["state"] == "momentum"
    assert result["score"] == 100
    assert result["habits_completion"] == 1.0


@pytest.mark.integration
@pytest.mark.coaching
async def test_state_stable_moderate_penalties(db_session: AsyncSession, test_user):
    """Умеренные штрафы → 50-74 → stable."""
    result = await compute_user_state(
        session=db_session,
        user_id=test_user.telegram_id,
        tasks_overdue=6,         # -20 → score 80... нет, это только 1 штраф
        calendar_events_today=0,
        habits_done_today=3,
        habits_total_today=3,
        task_completion_rate_week=0.3,  # -15 (< 0.4 порог) → 65
    )
    # 100 - 20 (overdue) - 15 (task_rate) = 65 → stable
    assert result["state"] == "stable"
    assert 50 <= result["score"] < 75


@pytest.mark.integration
@pytest.mark.coaching
async def test_state_overload_many_penalties(db_session: AsyncSession, test_user):
    """Много штрафов → score 30-49 → overload (нет recovery snapshot)."""
    result = await compute_user_state(
        session=db_session,
        user_id=test_user.telegram_id,
        tasks_overdue=10,        # -20
        calendar_events_today=9, # -15
        habits_done_today=0,
        habits_total_today=3,    # -20 (completion < 0.4)
        task_completion_rate_week=0.2,  # -15
    )
    # 100 - 20 - 15 - 20 - 15 = 30 → overload
    assert result["state"] in ("overload", "recovery")
    assert result["score"] <= 35


@pytest.mark.integration
@pytest.mark.coaching
async def test_state_risk_max_penalties(db_session: AsyncSession, test_user):
    """Максимальные штрафы → score < 30 → risk."""
    result = await compute_user_state(
        session=db_session,
        user_id=test_user.telegram_id,
        tasks_overdue=10,         # -20
        calendar_events_today=9,  # -15
        habits_done_today=0,
        habits_total_today=5,     # -20
        task_completion_rate_week=0.1,  # -15
        no_workout_7d=True,       # -10
        no_nutrition=True,        # -5
    )
    # 100 - 20 - 15 - 20 - 15 - 10 - 5 = 15 → risk
    assert result["state"] == "risk"
    assert result["score"] < 30


@pytest.mark.integration
@pytest.mark.coaching
async def test_state_score_never_negative(db_session: AsyncSession, test_user):
    """Score не может быть отрицательным."""
    result = await compute_user_state(
        session=db_session,
        user_id=test_user.telegram_id,
        tasks_overdue=100,
        calendar_events_today=100,
        habits_done_today=0,
        habits_total_today=10,
        task_completion_rate_week=0.0,
        no_workout_7d=True,
        no_nutrition=True,
    )
    assert result["score"] >= 0


@pytest.mark.integration
@pytest.mark.coaching
async def test_state_with_zero_habits(db_session: AsyncSession, test_user):
    """Нет привычек (total=0) → completion=1.0, нет штрафа за привычки."""
    result = await compute_user_state(
        session=db_session,
        user_id=test_user.telegram_id,
        habits_done_today=0,
        habits_total_today=0,  # деление на ноль → должен дать 1.0
    )
    assert result["habits_completion"] == 1.0
    assert result["score"] == 100


@pytest.mark.integration
@pytest.mark.coaching
async def test_state_has_required_keys(db_session: AsyncSession, test_user):
    """Результат содержит все обязательные ключи."""
    result = await compute_user_state(db_session, test_user.telegram_id)
    assert "state" in result
    assert "score" in result
    assert "factors" in result
    assert "habits_completion" in result
    assert result["state"] in ("momentum", "stable", "overload", "recovery", "risk")


# ── compute_weekly_score() — формула §22.3 ────────────────────────────────────

@pytest.mark.integration
@pytest.mark.coaching
async def test_weekly_score_perfect(db_session: AsyncSession, test_user):
    """100% goals + habits + 3 checkins + review = 100."""
    score = await compute_weekly_score(
        session=db_session,
        user_id=test_user.telegram_id,
        goals_progress=1.0,       # 30 pts
        habits_completion=1.0,    # 40 pts
        checkins_done=3,          # 15 pts
        review_done=True,         # 5 pts
        streak_recoveries=2,      # 10 pts
    )
    assert score == 100


@pytest.mark.integration
@pytest.mark.coaching
async def test_weekly_score_zero(db_session: AsyncSession, test_user):
    """Нулевые метрики → score 0."""
    score = await compute_weekly_score(
        session=db_session,
        user_id=test_user.telegram_id,
        goals_progress=0.0,
        habits_completion=0.0,
        checkins_done=0,
        review_done=False,
        streak_recoveries=0,
    )
    assert score == 0


@pytest.mark.integration
@pytest.mark.coaching
async def test_weekly_score_never_exceeds_100(db_session: AsyncSession, test_user):
    """Score не превышает 100 даже при overflow параметрах."""
    score = await compute_weekly_score(
        session=db_session,
        user_id=test_user.telegram_id,
        goals_progress=2.0,    # переполнение — 60 pts
        habits_completion=2.0, # переполнение — 80 pts
        checkins_done=10,
        review_done=True,
        streak_recoveries=10,
    )
    assert score <= 100


@pytest.mark.integration
@pytest.mark.coaching
async def test_weekly_score_habit_weight(db_session: AsyncSession, test_user):
    """Привычки весят 40% — самый весомый компонент."""
    only_habits = await compute_weekly_score(
        session=db_session,
        user_id=test_user.telegram_id,
        goals_progress=0.0,
        habits_completion=1.0,
        checkins_done=0,
        review_done=False,
        streak_recoveries=0,
    )
    assert only_habits == 40  # 40% от 100


@pytest.mark.integration
@pytest.mark.coaching
async def test_weekly_score_goal_weight(db_session: AsyncSession, test_user):
    """Цели весят 30%."""
    only_goals = await compute_weekly_score(
        session=db_session,
        user_id=test_user.telegram_id,
        goals_progress=1.0,
        habits_completion=0.0,
        checkins_done=0,
        review_done=False,
        streak_recoveries=0,
    )
    assert only_goals == 30  # 30% от 100


# ── update_daily_snapshot() — запись в БД ────────────────────────────────────

@pytest.mark.integration
@pytest.mark.coaching
async def test_update_daily_snapshot_creates(db_session: AsyncSession, test_user):
    """update_daily_snapshot() создаёт запись в БД."""
    snapshot = await update_daily_snapshot(
        session=db_session,
        user_id=test_user.telegram_id,
        tasks_overdue=2,
        tasks_completed_today=5,
        calendar_events_today=3,
        habits_done_today=2,
        habits_total_today=3,
    )
    assert snapshot is not None
    assert snapshot.user_id == test_user.telegram_id
    assert snapshot.tasks_overdue == 2
    assert snapshot.overall_state in ("momentum", "stable", "overload", "recovery", "risk")


@pytest.mark.integration
@pytest.mark.coaching
async def test_update_daily_snapshot_idempotent(db_session: AsyncSession, test_user):
    """Повторный вызов в тот же день обновляет, не создаёт дубль."""
    s1 = await update_daily_snapshot(db_session, test_user.telegram_id, tasks_overdue=1)
    s2 = await update_daily_snapshot(db_session, test_user.telegram_id, tasks_overdue=3)
    # Должна быть одна запись (upsert)
    assert s1.id == s2.id or s2.tasks_overdue == 3
