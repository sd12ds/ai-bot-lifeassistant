"""
Специфичные фикстуры для тестов coaching-модуля.
Переиспользует общие фикстуры из tests/conftest.py.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    User, Goal, Habit, HabitLog, GoalCheckin, GoalMilestone,
    CoachingInsight, CoachingRecommendation, UserCoachingProfile,
    CoachingContextSnapshot, CoachingMemory,
)
from tests.factories import (
    GoalFactory, HabitFactory, HabitLogFactory,
    GoalMilestoneFactory, GoalCheckinFactory,
    CoachingInsightFactory, CoachingRecommendationFactory,
    UserCoachingProfileFactory, CoachingMemoryFactory,
)


@pytest_asyncio.fixture
async def coaching_profile(db_session: AsyncSession, test_user: User) -> UserCoachingProfile:
    """Создаёт профиль коучинга для тестового пользователя."""
    profile = UserCoachingProfileFactory.build(
        user_id=test_user.telegram_id,
        onboarding_completed=True,
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    return profile


@pytest_asyncio.fixture
async def one_goal(db_session: AsyncSession, test_user: User) -> Goal:
    """Создаёт одну тестовую цель."""
    goal = GoalFactory.build(
        user_id=test_user.telegram_id,
        title="Похудеть на 5 кг",
        area="health",
        status="active",
        progress_pct=30,
    )
    db_session.add(goal)
    await db_session.commit()
    await db_session.refresh(goal)
    return goal


@pytest_asyncio.fixture
async def goals_list(db_session: AsyncSession, test_user: User) -> list[Goal]:
    """Создаёт список из 3 целей разных статусов."""
    goals = [
        GoalFactory.build(
            user_id=test_user.telegram_id,
            title="Активная цель",
            status="active",
            progress_pct=50,
        ),
        GoalFactory.build(
            user_id=test_user.telegram_id,
            title="Достигнутая цель",
            status="achieved",
            progress_pct=100,
        ),
        GoalFactory.build(
            user_id=test_user.telegram_id,
            title="Архивная цель",
            status="archived",
            progress_pct=20,
        ),
    ]
    for g in goals:
        db_session.add(g)
    await db_session.commit()
    for g in goals:
        await db_session.refresh(g)
    return goals


@pytest_asyncio.fixture
async def one_habit(db_session: AsyncSession, test_user: User) -> Habit:
    """Создаёт одну тестовую привычку."""
    habit = HabitFactory.build(
        user_id=test_user.telegram_id,
        title="Пить воду",
        area="health",
        current_streak=5,
        total_completions=10,
    )
    db_session.add(habit)
    await db_session.commit()
    await db_session.refresh(habit)
    return habit


@pytest_asyncio.fixture
async def habits_with_logs(
    db_session: AsyncSession,
    test_user: User,
) -> tuple[list[Habit], list[HabitLog]]:
    """Создаёт 2 привычки с логами за последние 7 дней."""
    habits = []
    logs = []
    for i in range(2):
        habit = HabitFactory.build(
            user_id=test_user.telegram_id,
            title=f"Привычка {i}",
            current_streak=7,
        )
        db_session.add(habit)
        habits.append(habit)
    await db_session.flush()

    # Логи за последние 7 дней для первой привычки
    for days_ago in range(7):
        log = HabitLogFactory.build(
            habit_id=habits[0].id,
            user_id=test_user.telegram_id,
            logged_at=datetime.utcnow() - timedelta(days=days_ago),
        )
        db_session.add(log)
        logs.append(log)
    await db_session.commit()

    return habits, logs


@pytest_asyncio.fixture
async def daily_snapshot(db_session: AsyncSession, test_user: User) -> CoachingContextSnapshot:
    """Создаёт ежедневный снимок контекста пользователя."""
    from db import coaching_storage as cs
    from datetime import date
    snapshot = await cs.upsert_snapshot(
        session=db_session,
        user_id=test_user.telegram_id,
        snapshot_date=date.today(),
        tasks_overdue=2,
        tasks_completed_today=5,
        calendar_events_today=3,
        free_slots_today=2,
        habits_done_today=2,
        habits_total_today=3,
        stuck_goals=0,
        streak_at_risk=0,
        overall_state="stable",
        score=70,
    )
    return snapshot


@pytest_asyncio.fixture
async def active_insights(db_session: AsyncSession, test_user: User) -> list[CoachingInsight]:
    """Создаёт 2 непрочитанных инсайта."""
    insights = [
        CoachingInsightFactory.build(
            user_id=test_user.telegram_id,
            insight_type="risk",
            severity="high",
            title="Риск дропаута",
            is_read=False,
        ),
        CoachingInsightFactory.build(
            user_id=test_user.telegram_id,
            insight_type="achievement",
            severity="info",
            title="Стрик 7 дней!",
            is_read=False,
        ),
    ]
    for i in insights:
        db_session.add(i)
    await db_session.commit()
    for i in insights:
        await db_session.refresh(i)
    return insights


@pytest_asyncio.fixture
async def active_recommendations(
    db_session: AsyncSession,
    test_user: User,
) -> list[CoachingRecommendation]:
    """Создаёт 2 активные рекомендации."""
    recs = [
        CoachingRecommendationFactory.build(
            user_id=test_user.telegram_id,
            rec_type="schedule_fix",
            title="Пересмотри расписание",
            priority=1,
        ),
        CoachingRecommendationFactory.build(
            user_id=test_user.telegram_id,
            rec_type="goal_decompose",
            title="Разбей цель на этапы",
            priority=2,
        ),
    ]
    for r in recs:
        db_session.add(r)
    await db_session.commit()
    for r in recs:
        await db_session.refresh(r)
    return recs
