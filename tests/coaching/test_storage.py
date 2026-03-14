"""
Phase 2: Тесты coaching_storage — CRUD операции.

Покрывает:
- Goals: create, get, update, delete, freeze/unfreeze, get_stuck_goals
- Habits: create, get, increment_streak, reset_streak, habits_at_risk
- Checkins: create, get_recent
- Insights: create, get_active, mark_read
- Profile: get_or_create, update
- Memory: upsert, get, clear
- Recommendations: create, get_active, dismiss
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

import db.coaching_storage as cs
from db.models import Goal, Habit, HabitLog, GoalCheckin


# ══════════════════════════════════════════════════════════════════════════════
# GOALS STORAGE
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.coaching
async def test_create_goal(db_session: AsyncSession, test_user):
    """create_goal() создаёт цель и возвращает объект с id."""
    goal = await cs.create_goal(
        db_session, test_user.telegram_id,
        title="Пробежать 5 км", area="health"
    )
    assert goal.id is not None
    assert goal.title == "Пробежать 5 км"
    assert goal.user_id == test_user.telegram_id
    assert goal.status == "active"


@pytest.mark.integration
@pytest.mark.coaching
async def test_get_goals_by_status(db_session: AsyncSession, test_user):
    """get_goals(status='active') возвращает только активные."""
    await cs.create_goal(db_session, test_user.telegram_id, title="Активная", status="active")
    g2 = await cs.create_goal(db_session, test_user.telegram_id, title="Достигнутая")
    await cs.update_goal(db_session, g2.id, test_user.telegram_id, status="achieved")

    active = await cs.get_goals(db_session, test_user.telegram_id, status="active")
    assert len(active) == 1
    assert active[0].title == "Активная"


@pytest.mark.integration
@pytest.mark.coaching
async def test_get_goal_by_id(db_session: AsyncSession, test_user):
    """get_goal() возвращает конкретную цель по id."""
    created = await cs.create_goal(db_session, test_user.telegram_id, title="Конкретная")
    fetched = await cs.get_goal(db_session, created.id, test_user.telegram_id)
    assert fetched is not None
    assert fetched.id == created.id


@pytest.mark.integration
@pytest.mark.coaching
async def test_get_goal_wrong_user(db_session: AsyncSession, test_user):
    """get_goal() с чужим user_id → None."""
    goal = await cs.create_goal(db_session, test_user.telegram_id, title="Моя цель")
    result = await cs.get_goal(db_session, goal.id, user_id=999999)
    assert result is None


@pytest.mark.integration
@pytest.mark.coaching
async def test_update_goal_progress(db_session: AsyncSession, test_user):
    """update_goal() обновляет progress_pct."""
    goal = await cs.create_goal(db_session, test_user.telegram_id, title="Цель")
    updated = await cs.update_goal(db_session, goal.id, test_user.telegram_id, progress_pct=75)
    assert updated.progress_pct == 75


@pytest.mark.integration
@pytest.mark.coaching
async def test_update_goal_freeze(db_session: AsyncSession, test_user):
    """update_goal() с is_frozen=True замораживает цель."""
    goal = await cs.create_goal(db_session, test_user.telegram_id, title="Цель")
    frozen = await cs.update_goal(
        db_session, goal.id, test_user.telegram_id,
        is_frozen=True, frozen_reason="Нет времени"
    )
    assert frozen.is_frozen is True
    assert frozen.frozen_reason == "Нет времени"


@pytest.mark.integration
@pytest.mark.coaching
async def test_get_stuck_goals(db_session: AsyncSession, test_user):
    """get_stuck_goals() находит цели без прогресса 7+ дней."""
    old_time = datetime.utcnow() - timedelta(days=10)
    # Старая незамороженная активная цель
    old_goal = Goal(
        user_id=test_user.telegram_id,
        title="Застрявшая",
        status="active",
        is_frozen=False,
        updated_at=old_time,
        created_at=old_time - timedelta(days=20),
    )
    db_session.add(old_goal)
    # Свежая цель — last_coaching_at сейчас, не должна попасть в stuck
    from datetime import datetime as _dt
    new_goal = Goal(
        user_id=test_user.telegram_id,
        title="Свежая",
        status="active",
        is_frozen=False,
        last_coaching_at=_dt.utcnow(),
    )
    db_session.add(new_goal)
    await db_session.commit()

    stuck = await cs.get_stuck_goals(db_session, test_user.telegram_id, days_without_progress=7)
    stuck_ids = [g.id for g in stuck]
    assert old_goal.id in stuck_ids
    assert new_goal.id not in stuck_ids


# ══════════════════════════════════════════════════════════════════════════════
# HABITS STORAGE
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.coaching
async def test_get_habits_active_only(db_session: AsyncSession, test_user):
    """get_habits(is_active=True) возвращает только активные привычки."""
    h1 = Habit(user_id=test_user.telegram_id, title="Активная", is_active=True)
    h2 = Habit(user_id=test_user.telegram_id, title="Неактивная", is_active=False)
    db_session.add_all([h1, h2])
    await db_session.commit()

    active = await cs.get_habits(db_session, test_user.telegram_id, is_active=True)
    assert len(active) == 1
    assert active[0].title == "Активная"


@pytest.mark.integration
@pytest.mark.coaching
async def test_increment_habit_streak(db_session: AsyncSession, test_user):
    """increment_habit_streak() увеличивает стрик и total_completions."""
    habit = Habit(
        user_id=test_user.telegram_id,
        title="Привычка",
        current_streak=5,
        longest_streak=5,
        total_completions=10,
    )
    db_session.add(habit)
    await db_session.commit()

    updated = await cs.increment_habit_streak(db_session, habit.id, test_user.telegram_id)
    assert updated.current_streak == 6
    assert updated.total_completions == 11
    assert updated.longest_streak == 6  # новый рекорд


@pytest.mark.integration
@pytest.mark.coaching
async def test_increment_streak_updates_longest(db_session: AsyncSession, test_user):
    """longest_streak обновляется только когда текущий его превышает."""
    habit = Habit(
        user_id=test_user.telegram_id,
        title="Привычка",
        current_streak=3,
        longest_streak=10,  # рекорд выше
    )
    db_session.add(habit)
    await db_session.commit()

    updated = await cs.increment_habit_streak(db_session, habit.id, test_user.telegram_id)
    assert updated.current_streak == 4
    assert updated.longest_streak == 10  # рекорд НЕ изменился


@pytest.mark.integration
@pytest.mark.coaching
async def test_reset_habit_streak(db_session: AsyncSession, test_user):
    """reset_habit_streak() обнуляет текущий стрик."""
    habit = Habit(
        user_id=test_user.telegram_id,
        title="Привычка",
        current_streak=7,
    )
    db_session.add(habit)
    await db_session.commit()

    updated = await cs.reset_habit_streak(
        db_session, habit.id, test_user.telegram_id, reason="пропуск"
    )
    assert updated.current_streak == 0


@pytest.mark.integration
@pytest.mark.coaching
async def test_increment_streak_nonexistent(db_session: AsyncSession, test_user):
    """increment_habit_streak() несуществующей привычки → None."""
    result = await cs.increment_habit_streak(db_session, habit_id=99999, user_id=test_user.telegram_id)
    assert result is None


@pytest.mark.integration
@pytest.mark.coaching
async def test_get_habits_at_risk(db_session: AsyncSession, test_user):
    """get_habits_at_risk() находит привычки без лога 3+ дней."""
    # Привычка без лога 5 дней (current_streak > 0 — требование get_habits_at_risk)
    risky = Habit(
        user_id=test_user.telegram_id,
        title="Рискованная",
        is_active=True,
        current_streak=3,
        last_logged_at=datetime.utcnow() - timedelta(days=5),
    )
    # Привычка с логом вчера
    safe = Habit(
        user_id=test_user.telegram_id,
        title="Безопасная",
        is_active=True,
        last_logged_at=datetime.utcnow() - timedelta(hours=20),
    )
    db_session.add_all([risky, safe])
    await db_session.commit()

    at_risk = await cs.get_habits_at_risk(db_session, test_user.telegram_id, days_no_log=3)
    at_risk_ids = [h.id for h in at_risk]
    assert risky.id in at_risk_ids
    assert safe.id not in at_risk_ids


# ══════════════════════════════════════════════════════════════════════════════
# CHECKINS STORAGE
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.coaching
async def test_create_goal_checkin(db_session: AsyncSession, test_user):
    """create_goal_checkin() создаёт check-in."""
    goal = await cs.create_goal(db_session, test_user.telegram_id, title="Цель")
    checkin = await cs.create_goal_checkin(
        db_session, goal.id, test_user.telegram_id,
        progress_pct=60,
        energy_level=4,
        notes="Хорошо идёт",
    )
    assert checkin.id is not None
    assert checkin.progress_pct == 60
    assert checkin.energy_level == 4


@pytest.mark.integration
@pytest.mark.coaching
async def test_get_recent_checkins(db_session: AsyncSession, test_user):
    """get_recent_goal_checkins() возвращает последние check-in'ы."""
    goal = await cs.create_goal(db_session, test_user.telegram_id, title="Цель")
    for i in range(5):
        await cs.create_goal_checkin(
            db_session, goal.id, test_user.telegram_id,
            progress_pct=i * 20
        )

    recent = await cs.get_recent_goal_checkins(db_session, goal.id, test_user.telegram_id, limit=3)
    assert len(recent) == 3


# ══════════════════════════════════════════════════════════════════════════════
# INSIGHTS STORAGE
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.coaching
async def test_create_and_get_insight(db_session: AsyncSession, test_user):
    """create_insight() + get_active_insights() — базовый цикл."""
    await cs.create_insight(
        db_session, test_user.telegram_id,
        insight_type="risk",
        severity="high",
        title="Риск дропаута",
        body="Нет активности 7 дней",
    )

    insights = await cs.get_active_insights(db_session, test_user.telegram_id)
    assert len(insights) == 1
    assert insights[0].title == "Риск дропаута"
    assert insights[0].is_read is False


@pytest.mark.integration
@pytest.mark.coaching
async def test_mark_insight_read(db_session: AsyncSession, test_user):
    """mark_insight_read() помечает инсайт прочитанным."""
    await cs.create_insight(
        db_session, test_user.telegram_id,
        insight_type="achievement",
        severity="info",
        title="Стрик 7 дней",
    )
    insights = await cs.get_active_insights(db_session, test_user.telegram_id)
    insight_id = insights[0].id

    await cs.mark_insight_read(db_session, insight_id, test_user.telegram_id)
    await db_session.commit()  # Expire session cache после UPDATE

    # get_active_insights возвращает все инсайты (не фильтрует по is_read)
    # Проверяем, что is_read обновился для конкретного инсайта
    from sqlalchemy import select as _select
    from db.models import CoachingInsight as _CI
    result = await db_session.execute(_select(_CI).where(_CI.id == insight_id))
    updated = result.scalar_one()
    assert updated.is_read is True


@pytest.mark.integration
@pytest.mark.coaching
async def test_get_active_insights_empty(db_session: AsyncSession, test_user):
    """Нет инсайтов → пустой список, не падает."""
    insights = await cs.get_active_insights(db_session, test_user.telegram_id)
    assert insights == []


# ══════════════════════════════════════════════════════════════════════════════
# PROFILE STORAGE
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.coaching
async def test_profile_get_or_create_twice(db_session: AsyncSession, test_user):
    """get_or_create_profile() идемпотентен — не создаёт дубль."""
    p1 = await cs.get_or_create_profile(db_session, test_user.telegram_id)
    p2 = await cs.get_or_create_profile(db_session, test_user.telegram_id)
    assert p1.id == p2.id


@pytest.mark.integration
@pytest.mark.coaching
async def test_profile_default_values(db_session: AsyncSession, test_user):
    """Профиль создаётся с корректными дефолтами."""
    profile = await cs.get_or_create_profile(db_session, test_user.telegram_id)
    assert profile.coach_tone == "friendly"
    assert profile.coaching_mode == "standard"
    assert profile.max_daily_nudges == 3


@pytest.mark.integration
@pytest.mark.coaching
async def test_profile_update(db_session: AsyncSession, test_user):
    """update_profile() сохраняет изменения."""
    await cs.get_or_create_profile(db_session, test_user.telegram_id)
    updated = await cs.update_profile(
        db_session, test_user.telegram_id,
        coach_tone="strict",
        max_daily_nudges=5,
    )
    assert updated.coach_tone == "strict"
    assert updated.max_daily_nudges == 5


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY STORAGE
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.coaching
async def test_upsert_and_get_memory(db_session: AsyncSession, test_user):
    """upsert_memory() + get_memory() — сохранение и чтение памяти."""
    await cs.upsert_memory(
        db_session, test_user.telegram_id,
        memory_type="preference",
        key="morning_person",
        value="да",
        confidence=0.9,
    )

    memories = await cs.get_memory(db_session, test_user.telegram_id)
    assert len(memories) >= 1
    keys = [m.key for m in memories]
    assert "morning_person" in keys


@pytest.mark.integration
@pytest.mark.coaching
async def test_upsert_memory_updates_existing(db_session: AsyncSession, test_user):
    """upsert_memory() обновляет существующую запись по ключу."""
    await cs.upsert_memory(
        db_session, test_user.telegram_id,
        memory_type="preference", key="tone", value="мягкий", confidence=0.5
    )
    await cs.upsert_memory(
        db_session, test_user.telegram_id,
        memory_type="preference", key="tone", value="строгий", confidence=0.8
    )

    memories = await cs.get_memory(db_session, test_user.telegram_id)
    tone_memories = [m for m in memories if m.key == "tone"]
    assert len(tone_memories) == 1  # нет дублей
    assert tone_memories[0].value == "строгий"


@pytest.mark.integration
@pytest.mark.coaching
async def test_clear_memory(db_session: AsyncSession, test_user):
    """clear_memory() удаляет все записи памяти."""
    await cs.upsert_memory(
        db_session, test_user.telegram_id,
        memory_type="preference", key="k1", value="v1"
    )
    await cs.upsert_memory(
        db_session, test_user.telegram_id,
        memory_type="preference", key="k2", value="v2"
    )

    deleted = await cs.clear_memory(db_session, test_user.telegram_id)
    assert deleted >= 2

    memories = await cs.get_memory(db_session, test_user.telegram_id)
    assert memories == []


# ══════════════════════════════════════════════════════════════════════════════
# RECOMMENDATIONS STORAGE
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.coaching
async def test_create_and_get_recommendations(db_session: AsyncSession, test_user):
    """create_recommendation() + get_active_recommendations() — базовый цикл."""
    await cs.create_recommendation(
        db_session, test_user.telegram_id,
        rec_type="schedule_fix",
        title="Пересмотри расписание",
        priority=1,
    )

    recs = await cs.get_active_recommendations(db_session, test_user.telegram_id)
    assert len(recs) == 1
    assert recs[0].title == "Пересмотри расписание"
    assert recs[0].dismissed is False


@pytest.mark.integration
@pytest.mark.coaching
async def test_dismiss_recommendation(db_session: AsyncSession, test_user):
    """dismiss_recommendation() помечает рекомендацию отклонённой."""
    rec = await cs.create_recommendation(
        db_session, test_user.telegram_id,
        rec_type="goal_decompose",
        title="Разбей цель",
    )

    await cs.dismiss_recommendation(db_session, rec.id, test_user.telegram_id)

    # Отклонённая рекомендация не в активных
    active = await cs.get_active_recommendations(db_session, test_user.telegram_id)
    assert all(r.id != rec.id for r in active)
