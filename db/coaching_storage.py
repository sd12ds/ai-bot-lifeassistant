"""
Coaching Storage — CRUD-слой для всех coaching-сущностей.
Используется coaching_engine, coaching_proactive и API-роутером.

Принципы (Clean Architecture §3):
- Только async SQLAlchemy, никакой бизнес-логики.
- Каждый метод принимает AsyncSession и возвращает ORM-объект или None/list.
- Агрегирующие методы помечены отдельным комментарием.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Optional, List, Any

from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Goal, Habit,
    GoalMilestone, GoalCheckin, GoalReview,
    HabitStreak, HabitTemplate,
    CoachingSession, CoachingInsight,
    UserCoachingProfile, CoachingRecommendation,
    CoachingMemory, BehaviorPattern,
    CoachingNudgeLog, CoachingOnboardingState,
    CoachingDialogDraft, CoachingContextSnapshot,
    CoachingRiskScore, CoachingOrchestrationAction,
)


# ══════════════════════════════════════════════════════════════════════════════
# Goals (расширенные coaching-операции)
# ══════════════════════════════════════════════════════════════════════════════

async def get_goals(
    session: AsyncSession,
    user_id: int,
    status: Optional[str] = None,
    area: Optional[str] = None,
) -> List[Goal]:
    """Получить список целей пользователя с опциональной фильтрацией."""
    q = select(Goal).where(Goal.user_id == user_id)
    if status:
        q = q.where(Goal.status == status)
    if area:
        q = q.where(Goal.area == area)
    q = q.order_by(Goal.priority.desc(), Goal.created_at.desc())
    result = await session.execute(q)
    return list(result.scalars().all())


async def get_goal(session: AsyncSession, goal_id: int, user_id: int) -> Optional[Goal]:
    """Получить цель по id (с проверкой владельца)."""
    result = await session.execute(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_goal(session: AsyncSession, user_id: int, **kwargs) -> Goal:
    """Создать новую цель пользователя."""
    goal = Goal(user_id=user_id, **kwargs)
    session.add(goal)
    await session.flush()
    await session.refresh(goal)
    return goal


async def update_goal(
    session: AsyncSession, goal_id: int, user_id: int, **kwargs
) -> Optional[Goal]:
    """Обновить поля цели. Возвращает обновлённый объект или None."""
    await session.execute(
        update(Goal)
        .where(Goal.id == goal_id, Goal.user_id == user_id)
        .values(**kwargs)
    )
    return await get_goal(session, goal_id, user_id)


async def get_stuck_goals(
    session: AsyncSession, user_id: int, days_without_progress: int = 7
) -> List[Goal]:
    """Агрегат: цели без check-in дольше N дней (для proactive-логики)."""
    threshold = datetime.utcnow() - timedelta(days=days_without_progress)
    result = await session.execute(
        select(Goal).where(
            Goal.user_id == user_id,
            Goal.status == "active",
            Goal.is_frozen == False,  # noqa: E712
            or_(
                Goal.last_coaching_at == None,  # noqa: E711
                Goal.last_coaching_at < threshold,
            ),
        )
    )
    return list(result.scalars().all())


# ══════════════════════════════════════════════════════════════════════════════
# GoalMilestone
# ══════════════════════════════════════════════════════════════════════════════

async def get_milestones(
    session: AsyncSession, goal_id: int, user_id: int
) -> List[GoalMilestone]:
    """Получить этапы цели, отсортированные по порядку."""
    result = await session.execute(
        select(GoalMilestone)
        .where(GoalMilestone.goal_id == goal_id, GoalMilestone.user_id == user_id)
        .order_by(GoalMilestone.sort_order, GoalMilestone.created_at)
    )
    return list(result.scalars().all())


async def create_milestone(
    session: AsyncSession, goal_id: int, user_id: int, **kwargs
) -> GoalMilestone:
    """Создать этап цели."""
    milestone = GoalMilestone(goal_id=goal_id, user_id=user_id, **kwargs)
    session.add(milestone)
    await session.flush()
    await session.refresh(milestone)
    return milestone


async def complete_milestone(
    session: AsyncSession, milestone_id: int, user_id: int
) -> Optional[GoalMilestone]:
    """Отметить этап как выполненный."""
    await session.execute(
        update(GoalMilestone)
        .where(GoalMilestone.id == milestone_id, GoalMilestone.user_id == user_id)
        .values(status="done", completed_at=datetime.utcnow())
    )
    result = await session.execute(
        select(GoalMilestone).where(GoalMilestone.id == milestone_id)
    )
    return result.scalar_one_or_none()


# ══════════════════════════════════════════════════════════════════════════════
# GoalCheckin
# ══════════════════════════════════════════════════════════════════════════════

async def create_goal_checkin(
    session: AsyncSession, goal_id: int, user_id: int, **kwargs
) -> GoalCheckin:
    """Создать check-in по цели."""
    checkin = GoalCheckin(goal_id=goal_id, user_id=user_id, **kwargs)
    session.add(checkin)
    await session.flush()
    await session.refresh(checkin)
    # Обновляем last_coaching_at у цели
    await session.execute(
        update(Goal)
        .where(Goal.id == goal_id)
        .values(last_coaching_at=datetime.utcnow())
    )
    return checkin


async def get_recent_goal_checkins(
    session: AsyncSession, goal_id: int, user_id: int, limit: int = 5
) -> List[GoalCheckin]:
    """Получить последние N check-ins по цели."""
    result = await session.execute(
        select(GoalCheckin)
        .where(GoalCheckin.goal_id == goal_id, GoalCheckin.user_id == user_id)
        .order_by(GoalCheckin.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ══════════════════════════════════════════════════════════════════════════════
# GoalReview
# ══════════════════════════════════════════════════════════════════════════════

async def create_goal_review(
    session: AsyncSession, goal_id: int, user_id: int, **kwargs
) -> GoalReview:
    """Создать review по цели (weekly или monthly)."""
    review = GoalReview(goal_id=goal_id, user_id=user_id, **kwargs)
    session.add(review)
    await session.flush()
    await session.refresh(review)
    return review


async def get_latest_review(
    session: AsyncSession, user_id: int, review_type: str = "weekly"
) -> Optional[GoalReview]:
    """Получить последний review пользователя заданного типа."""
    result = await session.execute(
        select(GoalReview)
        .where(GoalReview.user_id == user_id, GoalReview.review_type == review_type)
        .order_by(GoalReview.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# ══════════════════════════════════════════════════════════════════════════════
# Habits (расширенные coaching-операции)
# ══════════════════════════════════════════════════════════════════════════════

async def get_habits(
    session: AsyncSession,
    user_id: int,
    is_active: Optional[bool] = True,
    goal_id: Optional[int] = None,
) -> List[Habit]:
    """Получить привычки пользователя."""
    q = select(Habit).where(Habit.user_id == user_id)
    if is_active is not None:
        q = q.where(Habit.is_active == is_active)
    if goal_id is not None:
        q = q.where(Habit.goal_id == goal_id)
    result = await session.execute(q)
    return list(result.scalars().all())


async def get_habits_at_risk(
    session: AsyncSession, user_id: int, days_no_log: int = 3
) -> List[Habit]:
    """Агрегат: привычки, где стрик под угрозой (нет лога N дней)."""
    threshold = datetime.utcnow() - timedelta(days=days_no_log)
    result = await session.execute(
        select(Habit).where(
            Habit.user_id == user_id,
            Habit.is_active == True,  # noqa: E712
            Habit.current_streak > 0,
            or_(
                Habit.last_logged_at == None,  # noqa: E711
                Habit.last_logged_at < threshold,
            ),
        )
    )
    return list(result.scalars().all())


async def increment_habit_streak(
    session: AsyncSession, habit_id: int, user_id: int
) -> Optional[Habit]:
    """Инкрементировать стрик привычки после логирования."""
    result = await session.execute(
        select(Habit).where(Habit.id == habit_id, Habit.user_id == user_id)
    )
    habit = result.scalar_one_or_none()
    if not habit:
        return None
    habit.current_streak += 1
    habit.total_completions += 1
    habit.last_logged_at = datetime.utcnow()
    if habit.current_streak > habit.longest_streak:
        habit.longest_streak = habit.current_streak
    await session.flush()
    return habit


async def reset_habit_streak(
    session: AsyncSession, habit_id: int, user_id: int, reason: str = ""
) -> Optional[Habit]:
    """Сбросить стрик привычки при пропуске."""
    result = await session.execute(
        select(Habit).where(Habit.id == habit_id, Habit.user_id == user_id)
    )
    habit = result.scalar_one_or_none()
    if not habit:
        return None
    habit.current_streak = 0
    await session.flush()
    # Сохраняем историю стрика если был
    if habit.current_streak > 0:
        streak = HabitStreak(
            habit_id=habit_id,
            user_id=user_id,
            start_date=date.today() - timedelta(days=habit.current_streak),
            end_date=date.today(),
            length=habit.current_streak,
            break_reason=reason,
            is_current=False,
        )
        session.add(streak)
    return habit


# ══════════════════════════════════════════════════════════════════════════════
# HabitTemplate
# ══════════════════════════════════════════════════════════════════════════════

async def get_habit_templates(
    session: AsyncSession,
    area: Optional[str] = None,
    difficulty: Optional[str] = None,
    limit: int = 20,
) -> List[HabitTemplate]:
    """Получить библиотеку шаблонов привычек с фильтрацией."""
    q = select(HabitTemplate)
    if area:
        q = q.where(HabitTemplate.area == area)
    if difficulty:
        q = q.where(HabitTemplate.difficulty == difficulty)
    q = q.order_by(HabitTemplate.use_count.desc()).limit(limit)
    result = await session.execute(q)
    return list(result.scalars().all())


# ══════════════════════════════════════════════════════════════════════════════
# CoachingSession
# ══════════════════════════════════════════════════════════════════════════════

async def create_coaching_session(
    session: AsyncSession, user_id: int, **kwargs
) -> CoachingSession:
    """Создать запись о coaching-сессии."""
    cs = CoachingSession(user_id=user_id, **kwargs)
    session.add(cs)
    await session.flush()
    await session.refresh(cs)
    return cs


async def get_recent_sessions(
    session: AsyncSession, user_id: int, limit: int = 10
) -> List[CoachingSession]:
    """Получить последние N coaching-сессий пользователя."""
    result = await session.execute(
        select(CoachingSession)
        .where(CoachingSession.user_id == user_id)
        .order_by(CoachingSession.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_sessions_this_week(session: AsyncSession, user_id: int) -> int:
    """Агрегат: количество coaching-сессий за последние 7 дней."""
    threshold = datetime.utcnow() - timedelta(days=7)
    result = await session.execute(
        select(func.count(CoachingSession.id)).where(
            CoachingSession.user_id == user_id,
            CoachingSession.created_at >= threshold,
        )
    )
    return result.scalar_one() or 0


# ══════════════════════════════════════════════════════════════════════════════
# CoachingInsight
# ══════════════════════════════════════════════════════════════════════════════

async def create_insight(
    session: AsyncSession, user_id: int, **kwargs
) -> CoachingInsight:
    """Создать AI-инсайт для пользователя."""
    insight = CoachingInsight(user_id=user_id, **kwargs)
    session.add(insight)
    await session.flush()
    await session.refresh(insight)
    return insight


async def get_active_insights(
    session: AsyncSession,
    user_id: int,
    severity: Optional[str] = None,
    limit: int = 10,
) -> List[CoachingInsight]:
    """Получить актуальные нечитанные инсайты пользователя."""
    q = select(CoachingInsight).where(
        CoachingInsight.user_id == user_id,
        or_(
            CoachingInsight.valid_until == None,  # noqa: E711
            CoachingInsight.valid_until >= datetime.utcnow(),
        ),
    )
    if severity:
        q = q.where(CoachingInsight.severity == severity)
    q = q.order_by(CoachingInsight.created_at.desc()).limit(limit)
    result = await session.execute(q)
    return list(result.scalars().all())


async def mark_insight_read(
    session: AsyncSession, insight_id: int, user_id: int
) -> None:
    """Пометить инсайт как прочитанный."""
    await session.execute(
        update(CoachingInsight)
        .where(CoachingInsight.id == insight_id, CoachingInsight.user_id == user_id)
        .values(is_read=True)
    )


# ══════════════════════════════════════════════════════════════════════════════
# UserCoachingProfile
# ══════════════════════════════════════════════════════════════════════════════

async def get_or_create_profile(
    session: AsyncSession, user_id: int
) -> UserCoachingProfile:
    """Получить или создать профиль коуча пользователя."""
    result = await session.execute(
        select(UserCoachingProfile).where(UserCoachingProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = UserCoachingProfile(user_id=user_id)
        session.add(profile)
        await session.flush()
        await session.refresh(profile)
    return profile


async def update_profile(
    session: AsyncSession, user_id: int, **kwargs
) -> UserCoachingProfile:
    """Обновить настройки профиля коуча."""
    await session.execute(
        update(UserCoachingProfile)
        .where(UserCoachingProfile.user_id == user_id)
        .values(**kwargs)
    )
    return await get_or_create_profile(session, user_id)


# ══════════════════════════════════════════════════════════════════════════════
# CoachingRecommendation
# ══════════════════════════════════════════════════════════════════════════════

async def create_recommendation(
    session: AsyncSession, user_id: int, **kwargs
) -> CoachingRecommendation:
    """Добавить рекомендацию в очередь пользователя."""
    rec = CoachingRecommendation(user_id=user_id, **kwargs)
    session.add(rec)
    await session.flush()
    await session.refresh(rec)
    return rec


async def get_active_recommendations(
    session: AsyncSession, user_id: int, limit: int = 5
) -> List[CoachingRecommendation]:
    """Получить актуальные (не выполненные и не отклонённые) рекомендации."""
    result = await session.execute(
        select(CoachingRecommendation)
        .where(
            CoachingRecommendation.user_id == user_id,
            CoachingRecommendation.acted_on == False,  # noqa: E712
            CoachingRecommendation.dismissed == False,  # noqa: E712
            or_(
                CoachingRecommendation.expires_at == None,  # noqa: E711
                CoachingRecommendation.expires_at >= datetime.utcnow(),
            ),
        )
        .order_by(CoachingRecommendation.priority, CoachingRecommendation.created_at)
        .limit(limit)
    )
    return list(result.scalars().all())


async def dismiss_recommendation(
    session: AsyncSession, rec_id: int, user_id: int
) -> None:
    """Отклонить рекомендацию."""
    await session.execute(
        update(CoachingRecommendation)
        .where(
            CoachingRecommendation.id == rec_id,
            CoachingRecommendation.user_id == user_id,
        )
        .values(dismissed=True)
    )


# ══════════════════════════════════════════════════════════════════════════════
# CoachingMemory
# ══════════════════════════════════════════════════════════════════════════════

async def get_memory(
    session: AsyncSession, user_id: int, key: Optional[str] = None, top_n: int = 5
) -> List[CoachingMemory]:
    """
    Получить записи долгосрочной памяти коуча.
    Если key задан — конкретную запись, иначе top-N по confidence.
    """
    q = select(CoachingMemory).where(CoachingMemory.user_id == user_id)
    if key:
        q = q.where(CoachingMemory.key == key)
    else:
        q = q.order_by(CoachingMemory.confidence.desc()).limit(top_n)
    result = await session.execute(q)
    return list(result.scalars().all())


async def upsert_memory(
    session: AsyncSession,
    user_id: int,
    key: str,
    value: str,
    memory_type: str = "pattern",
    confidence: float = 0.5,
    is_explicit: bool = False,
) -> CoachingMemory:
    """
    Создать или обновить запись памяти.
    Если is_explicit=True — это явная коррекция пользователя (confidence=1.0).
    """
    result = await session.execute(
        select(CoachingMemory).where(
            CoachingMemory.user_id == user_id,
            CoachingMemory.key == key,
        )
    )
    memory = result.scalar_one_or_none()
    if memory:
        # Обновляем confidence усреднением, если не явная коррекция
        if is_explicit:
            memory.confidence = 1.0
            memory.is_explicit = True
        else:
            memory.confidence = min(1.0, (memory.confidence + confidence) / 2)
            memory.evidence_count += 1
        memory.value = value
    else:
        final_confidence = 1.0 if is_explicit else confidence
        memory = CoachingMemory(
            user_id=user_id,
            key=key,
            value=value,
            memory_type=memory_type,
            confidence=final_confidence,
            is_explicit=is_explicit,
        )
        session.add(memory)
    await session.flush()
    await session.refresh(memory)
    return memory


async def clear_memory(session: AsyncSession, user_id: int) -> int:
    """Сбросить всю память коуча пользователя (reversible learning)."""
    result = await session.execute(
        delete(CoachingMemory).where(CoachingMemory.user_id == user_id)
    )
    return result.rowcount


# ══════════════════════════════════════════════════════════════════════════════
# BehaviorPattern
# ══════════════════════════════════════════════════════════════════════════════

async def get_behavior_patterns(
    session: AsyncSession, user_id: int
) -> List[BehaviorPattern]:
    """Получить поведенческие паттерны пользователя."""
    result = await session.execute(
        select(BehaviorPattern)
        .where(BehaviorPattern.user_id == user_id)
        .order_by(BehaviorPattern.last_observed_at.desc())
    )
    return list(result.scalars().all())


async def upsert_behavior_pattern(
    session: AsyncSession, user_id: int, pattern_type: str, **kwargs
) -> BehaviorPattern:
    """Создать или обновить поведенческий паттерн."""
    result = await session.execute(
        select(BehaviorPattern).where(
            BehaviorPattern.user_id == user_id,
            BehaviorPattern.pattern_type == pattern_type,
        )
    )
    pattern = result.scalar_one_or_none()
    if pattern:
        for k, v in kwargs.items():
            setattr(pattern, k, v)
        pattern.last_observed_at = datetime.utcnow()
    else:
        pattern = BehaviorPattern(user_id=user_id, pattern_type=pattern_type, **kwargs)
        session.add(pattern)
    await session.flush()
    await session.refresh(pattern)
    return pattern


# ══════════════════════════════════════════════════════════════════════════════
# CoachingNudgeLog (антиспам)
# ══════════════════════════════════════════════════════════════════════════════

async def log_nudge_sent(
    session: AsyncSession, user_id: int, nudge_type: str, channel: str = "telegram"
) -> CoachingNudgeLog:
    """Зафиксировать отправку proactive-сообщения."""
    log = CoachingNudgeLog(user_id=user_id, nudge_type=nudge_type, channel=channel)
    session.add(log)
    await session.flush()
    await session.refresh(log)
    return log


async def check_antispam(
    session: AsyncSession,
    user_id: int,
    nudge_type: str,
    cooldown_hours_same_type: int = 48,
    cooldown_hours_any: int = 4,
    max_per_day: int = 3,
) -> bool:
    """
    Агрегат: проверка антиспам-правил перед отправкой nudge.
    Возвращает True если отправка разрешена, False — заблокировано.
    Правила §5.3: cooldown 48ч для типа, 4ч между любыми, макс 3/день.
    """
    now = datetime.utcnow()

    # Проверка: тот же nudge_type за 48ч
    cutoff_same = now - timedelta(hours=cooldown_hours_same_type)
    res = await session.execute(
        select(func.count(CoachingNudgeLog.id)).where(
            CoachingNudgeLog.user_id == user_id,
            CoachingNudgeLog.nudge_type == nudge_type,
            CoachingNudgeLog.sent_at >= cutoff_same,
        )
    )
    if (res.scalar_one() or 0) > 0:
        return False  # тип уже отправлялся в окне cooldown

    # Проверка: любой nudge за последние 4ч
    cutoff_any = now - timedelta(hours=cooldown_hours_any)
    res = await session.execute(
        select(func.count(CoachingNudgeLog.id)).where(
            CoachingNudgeLog.user_id == user_id,
            CoachingNudgeLog.sent_at >= cutoff_any,
        )
    )
    if (res.scalar_one() or 0) > 0:
        return False  # слишком частая отправка

    # Проверка: макс N в день
    cutoff_day = now - timedelta(hours=24)
    res = await session.execute(
        select(func.count(CoachingNudgeLog.id)).where(
            CoachingNudgeLog.user_id == user_id,
            CoachingNudgeLog.sent_at >= cutoff_day,
        )
    )
    if (res.scalar_one() or 0) >= max_per_day:
        return False  # дневной лимит исчерпан

    return True  # всё ок, можно отправлять


async def update_nudge_response(
    session: AsyncSession,
    nudge_id: int,
    user_id: int,
    acted_on: bool = False,
    dismissed: bool = False,
    response_type: Optional[str] = None,
) -> None:
    """Обновить реакцию пользователя на nudge."""
    await session.execute(
        update(CoachingNudgeLog)
        .where(CoachingNudgeLog.id == nudge_id, CoachingNudgeLog.user_id == user_id)
        .values(opened=True, acted_on=acted_on, dismissed=dismissed, response_type=response_type)
    )


# ══════════════════════════════════════════════════════════════════════════════
# CoachingOnboardingState
# ══════════════════════════════════════════════════════════════════════════════

async def get_or_create_onboarding(
    session: AsyncSession, user_id: int
) -> CoachingOnboardingState:
    """Получить или создать состояние онбординга пользователя."""
    result = await session.execute(
        select(CoachingOnboardingState).where(
            CoachingOnboardingState.user_id == user_id
        )
    )
    state = result.scalar_one_or_none()
    if not state:
        state = CoachingOnboardingState(user_id=user_id)
        session.add(state)
        await session.flush()
        await session.refresh(state)
    return state


async def advance_onboarding_step(
    session: AsyncSession, user_id: int, step_name: str
) -> CoachingOnboardingState:
    """Продвинуть онбординг на следующий шаг."""
    state = await get_or_create_onboarding(session, user_id)
    completed = list(state.steps_completed or [])
    if step_name not in completed:
        completed.append(step_name)
    state.steps_completed = completed
    state.current_step = len(completed)
    await session.flush()
    return state


# ══════════════════════════════════════════════════════════════════════════════
# CoachingDialogDraft
# ══════════════════════════════════════════════════════════════════════════════

async def get_active_draft(
    session: AsyncSession, user_id: int, draft_type: Optional[str] = None
) -> Optional[CoachingDialogDraft]:
    """Получить активный (не истёкший) черновик диалога."""
    q = select(CoachingDialogDraft).where(
        CoachingDialogDraft.user_id == user_id,
        or_(
            CoachingDialogDraft.expires_at == None,  # noqa: E711
            CoachingDialogDraft.expires_at >= datetime.utcnow(),
        ),
    )
    if draft_type:
        q = q.where(CoachingDialogDraft.draft_type == draft_type)
    q = q.order_by(CoachingDialogDraft.updated_at.desc()).limit(1)
    result = await session.execute(q)
    return result.scalar_one_or_none()


async def upsert_draft(
    session: AsyncSession,
    user_id: int,
    draft_type: str,
    payload: dict,
    step: int,
    expires_hours: int = 24,
) -> CoachingDialogDraft:
    """Создать или обновить черновик многошагового диалога."""
    draft = await get_active_draft(session, user_id, draft_type)
    expires = datetime.utcnow() + timedelta(hours=expires_hours)
    if draft:
        draft.payload = payload
        draft.step = step
        draft.expires_at = expires
    else:
        draft = CoachingDialogDraft(
            user_id=user_id,
            draft_type=draft_type,
            payload=payload,
            step=step,
            expires_at=expires,
        )
        session.add(draft)
    await session.flush()
    await session.refresh(draft)
    return draft


async def delete_draft(
    session: AsyncSession, user_id: int, draft_type: str
) -> None:
    """Удалить черновик диалога после завершения flow."""
    await session.execute(
        delete(CoachingDialogDraft).where(
            CoachingDialogDraft.user_id == user_id,
            CoachingDialogDraft.draft_type == draft_type,
        )
    )


# ══════════════════════════════════════════════════════════════════════════════
# CoachingContextSnapshot
# ══════════════════════════════════════════════════════════════════════════════

async def get_latest_snapshot(
    session: AsyncSession, user_id: int
) -> Optional[CoachingContextSnapshot]:
    """Получить последний снимок контекста пользователя."""
    result = await session.execute(
        select(CoachingContextSnapshot)
        .where(CoachingContextSnapshot.user_id == user_id)
        .order_by(CoachingContextSnapshot.snapshot_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def upsert_snapshot(
    session: AsyncSession, user_id: int, snapshot_date: date, **kwargs
) -> CoachingContextSnapshot:
    """Создать или обновить снимок контекста на дату."""
    result = await session.execute(
        select(CoachingContextSnapshot).where(
            CoachingContextSnapshot.user_id == user_id,
            CoachingContextSnapshot.snapshot_date == snapshot_date,
        )
    )
    snapshot = result.scalar_one_or_none()
    if snapshot:
        for k, v in kwargs.items():
            setattr(snapshot, k, v)
    else:
        snapshot = CoachingContextSnapshot(
            user_id=user_id, snapshot_date=snapshot_date, **kwargs
        )
        session.add(snapshot)
    await session.flush()
    await session.refresh(snapshot)
    return snapshot


# ══════════════════════════════════════════════════════════════════════════════
# CoachingRiskScore
# ══════════════════════════════════════════════════════════════════════════════

async def upsert_risk_score(
    session: AsyncSession,
    user_id: int,
    risk_type: str,
    score: float,
    factors: Optional[dict] = None,
) -> CoachingRiskScore:
    """Создать или обновить оценку риска пользователя."""
    result = await session.execute(
        select(CoachingRiskScore).where(
            CoachingRiskScore.user_id == user_id,
            CoachingRiskScore.risk_type == risk_type,
        )
    )
    risk = result.scalar_one_or_none()
    if risk:
        risk.score = score
        risk.factors = factors
        risk.assessed_at = datetime.utcnow()
    else:
        risk = CoachingRiskScore(
            user_id=user_id, risk_type=risk_type, score=score, factors=factors
        )
        session.add(risk)
    await session.flush()
    await session.refresh(risk)
    return risk


async def get_risk_scores(
    session: AsyncSession, user_id: int
) -> List[CoachingRiskScore]:
    """Получить все оценки рисков пользователя."""
    result = await session.execute(
        select(CoachingRiskScore)
        .where(CoachingRiskScore.user_id == user_id)
        .order_by(CoachingRiskScore.score.desc())
    )
    return list(result.scalars().all())


# ══════════════════════════════════════════════════════════════════════════════
# CoachingOrchestrationAction
# ══════════════════════════════════════════════════════════════════════════════

async def create_orchestration_action(
    session: AsyncSession, user_id: int, **kwargs
) -> CoachingOrchestrationAction:
    """Создать orchestration-действие (ожидает подтверждения пользователя)."""
    action = CoachingOrchestrationAction(user_id=user_id, **kwargs)
    session.add(action)
    await session.flush()
    await session.refresh(action)
    return action


async def confirm_orchestration_action(
    session: AsyncSession, action_id: int, user_id: int
) -> Optional[CoachingOrchestrationAction]:
    """Подтвердить orchestration-действие пользователем."""
    await session.execute(
        update(CoachingOrchestrationAction)
        .where(
            CoachingOrchestrationAction.id == action_id,
            CoachingOrchestrationAction.user_id == user_id,
        )
        .values(status="confirmed", confirmed_at=datetime.utcnow())
    )
    result = await session.execute(
        select(CoachingOrchestrationAction).where(
            CoachingOrchestrationAction.id == action_id
        )
    )
    return result.scalar_one_or_none()


async def mark_action_executed(
    session: AsyncSession, action_id: int
) -> None:
    """Пометить orchestration-действие как выполненное."""
    await session.execute(
        update(CoachingOrchestrationAction)
        .where(CoachingOrchestrationAction.id == action_id)
        .values(status="executed", executed_at=datetime.utcnow())
    )


async def get_pending_actions(
    session: AsyncSession, user_id: int
) -> List[CoachingOrchestrationAction]:
    """Получить все pending-действия (ожидающие подтверждения)."""
    result = await session.execute(
        select(CoachingOrchestrationAction).where(
            CoachingOrchestrationAction.user_id == user_id,
            CoachingOrchestrationAction.status == "pending",
        )
    )
    return list(result.scalars().all())
