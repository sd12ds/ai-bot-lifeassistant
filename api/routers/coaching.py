"""
Coaching API Router — /api/coaching/*

Реализует §14 архитектурного документа: Pydantic DTOs, 40+ endpoints,
агрегирующий dashboard endpoint (<500ms).

Группы endpoints:
  /coaching/dashboard           — агрегирующий (1 запрос при открытии Mini App)
  /coaching/state               — текущее состояние пользователя
  /coaching/goals/*             — CRUD + действия с целями
  /coaching/milestones/*        — этапы целей
  /coaching/habits/*            — CRUD + трекинг привычек
  /coaching/checkins/*          — check-in прогресса
  /coaching/reviews/*           — weekly/monthly review
  /coaching/insights/*          — AI-инсайты
  /coaching/recommendations/*   — рекомендации
  /coaching/profile             — настройки коуча
  /coaching/onboarding/*        — онбординг
  /coaching/analytics/*         — метрики и аналитика
  /coaching/prompts             — sample prompts для UI
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from db.models import User, CoachingOrchestrationAction
from db.session import get_session
import db.coaching_storage as cs
from services.coaching_cross_module import (
    run_cross_module_analysis,
    execute_orchestration_action,
)
from services.coaching_personalization import (
    get_adaptation_context,
    reset_personalization as reset_personalization_svc,
    analyze_behavioral_patterns,
    update_memory_from_behavior,
)
from services.coaching_engine import (
    compute_user_state,
    compute_risk_scores,
    compute_weekly_score,
    update_daily_snapshot,
)

router = APIRouter(prefix="/coaching", tags=["coaching"])


# ══════════════════════════════════════════════════════════════════════════════
# PYDANTIC DTOs
# ══════════════════════════════════════════════════════════════════════════════

# ── Goals ─────────────────────────────────────────────────────────────────────

class GoalCreateDto(BaseModel):
    """Создание новой цели."""
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    area: Optional[str] = None          # health|finance|career|personal|relationships
    target_date: Optional[date] = None
    why_statement: Optional[str] = None
    first_step: Optional[str] = None
    priority: int = Field(default=2, ge=1, le=5)


class GoalUpdateDto(BaseModel):
    """Обновление цели (все поля опциональны)."""
    title: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    area: Optional[str] = None
    target_date: Optional[date] = None
    why_statement: Optional[str] = None
    first_step: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    progress_pct: Optional[int] = Field(None, ge=0, le=100)
    status: Optional[str] = None
    coaching_notes: Optional[str] = None


class GoalOut(BaseModel):
    """Ответ с данными цели."""
    id: int
    title: str
    description: Optional[str]
    area: Optional[str]
    status: str
    priority: int
    progress_pct: int
    target_date: Optional[date]
    why_statement: Optional[str]
    first_step: Optional[str]
    is_frozen: bool
    frozen_reason: Optional[str]
    coaching_notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Milestones ─────────────────────────────────────────────────────────────────

class MilestoneCreateDto(BaseModel):
    """Создание этапа цели."""
    title: str = Field(..., min_length=2, max_length=200)
    goal_id: int
    due_date: Optional[date] = None
    description: Optional[str] = None
    order_index: int = 0


class MilestoneOut(BaseModel):
    id: int
    goal_id: int
    title: str
    status: str
    due_date: Optional[date]
    description: Optional[str]
    order_index: int
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Habits ─────────────────────────────────────────────────────────────────────

class HabitCreateDto(BaseModel):
    """Создание привычки."""
    title: str = Field(..., min_length=2, max_length=200)
    area: Optional[str] = None          # health|sport|mindset|productivity
    frequency: str = "daily"            # daily|weekly|custom
    target_count: int = Field(default=1, ge=1)
    cue: Optional[str] = None           # триггер (после кофе, перед сном...)
    reward: Optional[str] = None
    best_time: Optional[str] = None
    goal_id: Optional[int] = None


class HabitUpdateDto(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=200)
    area: Optional[str] = None
    cue: Optional[str] = None
    reward: Optional[str] = None
    best_time: Optional[str] = None
    is_active: Optional[bool] = None


class HabitOut(BaseModel):
    id: int
    title: str
    area: Optional[str]
    frequency: str
    target_count: int
    cue: Optional[str]
    reward: Optional[str]
    best_time: Optional[str]
    is_active: bool
    current_streak: int
    longest_streak: int
    total_completions: int
    last_logged_at: Optional[datetime]
    goal_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Check-in ──────────────────────────────────────────────────────────────────

class CheckInCreateDto(BaseModel):
    """Создание check-in."""
    energy_level: int = Field(..., ge=1, le=5)
    mood: Optional[str] = None          # great|good|ok|tired|bad
    notes: Optional[str] = None
    blockers: Optional[str] = None
    wins: Optional[str] = None
    goal_id: Optional[int] = None
    progress_pct: Optional[int] = Field(None, ge=0, le=100)


class CheckInOut(BaseModel):
    id: int
    goal_id: Optional[int]
    energy_level: int
    mood: Optional[str]
    notes: Optional[str]
    blockers: Optional[str]
    wins: Optional[str]
    progress_pct: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Reviews ───────────────────────────────────────────────────────────────────

class ReviewOut(BaseModel):
    id: int
    goal_id: Optional[int]
    review_type: str
    summary: Optional[str]
    highlights: Optional[list]
    blockers: Optional[list]
    next_actions: Optional[list]
    ai_assessment: Optional[str]
    score: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Profile ───────────────────────────────────────────────────────────────────

class CoachingProfileUpdateDto(BaseModel):
    """Обновление настроек коуча."""
    coach_tone: Optional[str] = None            # strict|friendly|motivational|soft
    coaching_mode: Optional[str] = None         # soft|standard|active
    preferred_checkin_time: Optional[str] = None  # "20:00"
    preferred_review_day: Optional[str] = None
    morning_brief_enabled: Optional[bool] = None
    evening_reflection_enabled: Optional[bool] = None
    max_daily_nudges: Optional[int] = Field(None, ge=1, le=10)


class CoachingProfileOut(BaseModel):
    user_id: int
    coach_tone: str
    coaching_mode: str
    preferred_checkin_time: Optional[str]
    preferred_review_day: str
    morning_brief_enabled: bool
    evening_reflection_enabled: bool
    max_daily_nudges: int

    class Config:
        from_attributes = True


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardOut(BaseModel):
    """Агрегированный ответ для главного экрана Mini App."""
    state: str                              # momentum|stable|overload|recovery|risk
    state_score: int
    habits_today: list[dict]                # привычки + выполнено ли
    goals_active: list[dict]                # топ-3 активных цели
    top_insight: Optional[dict]             # один AI-инсайт
    recommendations: list[dict]            # до 2
    weekly_score: int
    nudge_pending: Optional[dict]          # pending proactive
    prompt_suggestions: list[str]          # 3-5 sample prompts
    risks: dict                             # dropout/overload/goal_failure/habit_death


# ── Onboarding ────────────────────────────────────────────────────────────────

class OnboardingStepDto(BaseModel):
    step: str       # intro|goals|habits|profile|done


class OnboardingOut(BaseModel):
    current_step: Optional[str]
    steps_completed: list
    first_goal_created: bool
    first_habit_created: bool
    first_checkin_done: bool
    bot_onboarding_done: bool

    class Config:
        from_attributes = True


# ── Analytics ─────────────────────────────────────────────────────────────────

class WeeklyAnalyticsOut(BaseModel):
    weekly_score: int
    goals_progress: list[dict]
    habits_completion_rate: float
    checkins_this_week: int
    dropout_risk: float
    state: str


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _goal_to_dict(g) -> dict:
    """Компактный dict цели для dashboard."""
    return {
        "id": g.id,
        "title": g.title,
        "progress_pct": g.progress_pct,
        "area": g.area,
        "target_date": g.target_date.isoformat() if g.target_date else None,
        "is_frozen": g.is_frozen,
        "status": g.status,
    }


def _habit_to_dict(h) -> dict:
    """Компактный dict привычки для dashboard."""
    return {
        "id": h.id,
        "title": h.title,
        "current_streak": h.current_streak,
        "longest_streak": h.longest_streak,
        "area": h.area,
    }


_SAMPLE_PROMPTS = {
    "default": [
        "Как дела с моими целями?",
        "Разбей мою главную цель на этапы",
        "Что мне стоит сделать прямо сейчас?",
        "Оцени мой прогресс за последнюю неделю",
        "Мне нужна мотивация",
    ],
    "momentum": [
        "Я на подъёме — что можно добавить?",
        "Покажи мои лучшие результаты",
        "Поставим новую цель?",
    ],
    "overload": [
        "Помоги разгрузить мой список задач",
        "Что можно заморозить?",
        "Расставь приоритеты за меня",
    ],
    "recovery": [
        "Мне сложно — с чего начать?",
        "Один маленький шаг прямо сейчас",
        "Не могу войти в ритм — что делать?",
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD — агрегирующий endpoint (§14.3)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DashboardOut:
    """
    Агрегирующий endpoint для главного экрана Mini App.

    Выполняет все запросы параллельно через asyncio.gather().
    Цель: latency <500ms.
    """
    user_id = current_user.id

    # Параллельные запросы для минимальной latency
    (
        goals,
        habits,
        insights,
        recs,
        state_data,
        risks,
        weekly_score,
    ) = await asyncio.gather(
        cs.get_goals(db, user_id, status="active"),
        cs.get_habits(db, user_id, is_active=True),
        cs.get_active_insights(db, user_id, limit=1),
        cs.get_active_recommendations(db, user_id, limit=2),
        compute_user_state(db, user_id),
        compute_risk_scores(db, user_id),
        compute_weekly_score(db, user_id),
        return_exceptions=False,
    )

    state = state_data["state"]
    state_score = state_data["score"]

    # Топ-3 цели
    goals_active = [_goal_to_dict(g) for g in goals[:3]]

    # Привычки сегодня
    habits_today = [_habit_to_dict(h) for h in habits]

    # Инсайт
    top_insight = None
    if insights:
        i = insights[0]
        top_insight = {
            "id": i.id,
            "insight_type": i.insight_type,
            "severity": i.severity,
            "title": getattr(i, 'title', ''),
            "body": getattr(i, 'body', ''),
        }

    # Рекомендации
    recs_out = []
    for r in recs:
        recs_out.append({
            "id": r.id,
            "rec_type": r.rec_type,
            "title": r.title,
            "body": getattr(r, 'body', ''),
            "action_type": r.action_type,
        })

    # Sample prompts по состоянию
    prompts = _SAMPLE_PROMPTS.get(state, _SAMPLE_PROMPTS["default"])

    return DashboardOut(
        state=state,
        state_score=state_score,
        habits_today=habits_today,
        goals_active=goals_active,
        top_insight=top_insight,
        recommendations=recs_out,
        weekly_score=weekly_score,
        nudge_pending=None,  # TODO: pendng nudge из scheduler
        prompt_suggestions=prompts[:5],
        risks=risks,
    )


# ══════════════════════════════════════════════════════════════════════════════
# STATE
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/state")
async def get_state(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Текущее whole-user state + risk scores."""
    user_id = current_user.id
    state_data, risks = await asyncio.gather(
        compute_user_state(db, user_id),
        compute_risk_scores(db, user_id),
    )
    return {**state_data, "risks": risks}


# ══════════════════════════════════════════════════════════════════════════════
# GOALS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/goals", response_model=List[GoalOut])
async def list_goals(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Список целей с фильтром по статусу (active|achieved|archived|all)."""
    return await cs.get_goals(db, current_user.id, status=status)


@router.post("/goals", response_model=GoalOut, status_code=201)
async def create_goal(
    body: GoalCreateDto,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Создать новую цель."""
    goal = await cs.create_goal(db, current_user.id, **body.model_dump(exclude_none=True))
    await db.commit()
    return goal


@router.get("/goals/{goal_id}", response_model=GoalOut)
async def get_goal(
    goal_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    goal = await cs.get_goal(db, goal_id, current_user.id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.put("/goals/{goal_id}", response_model=GoalOut)
async def update_goal(
    goal_id: int,
    body: GoalUpdateDto,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    goal = await cs.update_goal(db, goal_id, current_user.id, **body.model_dump(exclude_none=True))
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    await db.commit()
    return goal


@router.delete("/goals/{goal_id}", status_code=204)
async def delete_goal(
    goal_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import delete as sql_delete
    from db.models import Goal
    await db.execute(
        sql_delete(Goal).where(Goal.id == goal_id, Goal.user_id == current_user.id)
    )
    await db.commit()


@router.post("/goals/{goal_id}/freeze", response_model=GoalOut)
async def freeze_goal(
    goal_id: int,
    reason: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Заморозить цель."""
    goal = await cs.update_goal(db, goal_id, current_user.id, is_frozen=True, frozen_reason=reason)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    await db.commit()
    return goal


@router.post("/goals/{goal_id}/resume", response_model=GoalOut)
async def resume_goal(
    goal_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Возобновить замороженную цель."""
    goal = await cs.update_goal(db, goal_id, current_user.id, is_frozen=False, frozen_reason=None)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    await db.commit()
    return goal


@router.post("/goals/{goal_id}/restart", response_model=GoalOut)
async def restart_goal(
    goal_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Сбросить прогресс и перезапустить цель."""
    goal = await cs.update_goal(db, goal_id, current_user.id,
                                status="active", progress_pct=0, is_frozen=False)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    await db.commit()
    return goal


@router.post("/goals/{goal_id}/achieve", response_model=GoalOut)
async def achieve_goal(
    goal_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Отметить цель как достигнутую."""
    goal = await cs.update_goal(db, goal_id, current_user.id,
                                status="achieved", progress_pct=100)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    await db.commit()
    return goal


@router.get("/goals/{goal_id}/analytics")
async def goal_analytics(
    goal_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Аналитика по цели: checkins история, прогресс, stuck-дни."""
    goal = await cs.get_goal(db, goal_id, current_user.id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    milestones = await cs.get_milestones(db, goal_id, current_user.id)
    checkins = await cs.get_recent_goal_checkins(db, current_user.id, limit=10)
    goal_checkins = [c for c in checkins if getattr(c, 'goal_id', None) == goal_id]
    done_ms = [m for m in milestones if m.status == "done"]
    return {
        "goal_id": goal_id,
        "title": goal.title,
        "progress_pct": goal.progress_pct,
        "milestones_total": len(milestones),
        "milestones_done": len(done_ms),
        "checkins_count": len(goal_checkins),
        "last_checkin": goal_checkins[0].created_at.isoformat() if goal_checkins else None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# MILESTONES
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/milestones", response_model=List[MilestoneOut])
async def list_milestones(
    goal_id: int = Query(...),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await cs.get_milestones(db, goal_id, current_user.id)


@router.post("/milestones", response_model=MilestoneOut, status_code=201)
async def create_milestone(
    body: MilestoneCreateDto,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    m = await cs.create_milestone(db, current_user.id, **body.model_dump(exclude_none=True))
    await db.commit()
    return m


@router.post("/milestones/{milestone_id}/complete", response_model=MilestoneOut)
async def complete_milestone(
    milestone_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    m = await cs.complete_milestone(db, milestone_id, current_user.id)
    if not m:
        raise HTTPException(status_code=404, detail="Milestone not found")
    await db.commit()
    return m


# ══════════════════════════════════════════════════════════════════════════════
# HABITS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/habits", response_model=List[HabitOut])
async def list_habits(
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await cs.get_habits(db, current_user.id, is_active=is_active)


@router.post("/habits", response_model=HabitOut, status_code=201)
async def create_habit(
    body: HabitCreateDto,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from db.models import Habit
    h = Habit(user_id=current_user.id, **body.model_dump(exclude_none=True))
    db.add(h)
    await db.flush()
    await db.refresh(h)
    await db.commit()
    return h


@router.get("/habits/templates")
async def get_habit_templates(
    area: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list:
    """Библиотека готовых шаблонов привычек."""
    return await cs.get_habit_templates(db, area=area)


@router.get("/habits/{habit_id}", response_model=HabitOut)
async def get_habit(
    habit_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select
    from db.models import Habit
    r = await db.execute(select(Habit).where(Habit.id == habit_id, Habit.user_id == current_user.id))
    h = r.scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="Habit not found")
    return h


@router.put("/habits/{habit_id}", response_model=HabitOut)
async def update_habit(
    habit_id: int,
    body: HabitUpdateDto,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import update as sql_update, select
    from db.models import Habit
    await db.execute(
        sql_update(Habit)
        .where(Habit.id == habit_id, Habit.user_id == current_user.id)
        .values(**body.model_dump(exclude_none=True))
    )
    await db.commit()
    r = await db.execute(select(Habit).where(Habit.id == habit_id))
    return r.scalar_one()


@router.post("/habits/{habit_id}/log")
async def log_habit(
    habit_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Залогировать выполнение привычки."""
    habit = await cs.increment_habit_streak(db, habit_id, current_user.id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    from db.models import HabitLog
    db.add(HabitLog(habit_id=habit_id, user_id=current_user.id))
    await db.commit()
    return {"streak": habit.current_streak, "is_record": habit.current_streak == habit.longest_streak}


@router.post("/habits/{habit_id}/miss")
async def miss_habit(
    habit_id: int,
    reason: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Отметить пропуск привычки."""
    habit = await cs.reset_habit_streak(db, habit_id, current_user.id, reason=reason or "пропуск")
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    await db.commit()
    return {"streak_reset": True, "previous_streak": habit.current_streak}


@router.post("/habits/{habit_id}/pause")
async def pause_habit(
    habit_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    from sqlalchemy import update as sql_update
    from db.models import Habit
    await db.execute(
        sql_update(Habit).where(Habit.id == habit_id, Habit.user_id == current_user.id).values(is_active=False)
    )
    await db.commit()
    return {"paused": True}


@router.post("/habits/{habit_id}/resume")
async def resume_habit(
    habit_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    from sqlalchemy import update as sql_update
    from db.models import Habit
    await db.execute(
        sql_update(Habit).where(Habit.id == habit_id, Habit.user_id == current_user.id).values(is_active=True)
    )
    await db.commit()
    return {"resumed": True}


@router.get("/habits/{habit_id}/analytics")
async def habit_analytics(
    habit_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Статистика привычки: streak history, completion rate, best/worst days."""
    from sqlalchemy import select
    from db.models import Habit, HabitLog
    r = await db.execute(select(Habit).where(Habit.id == habit_id, Habit.user_id == current_user.id))
    h = r.scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="Habit not found")
    logs_r = await db.execute(
        select(HabitLog).where(HabitLog.habit_id == habit_id)
        .order_by(HabitLog.logged_at.desc()).limit(30)
    )
    logs = logs_r.scalars().all()
    return {
        "habit_id": habit_id,
        "title": h.title,
        "current_streak": h.current_streak,
        "longest_streak": h.longest_streak,
        "total_completions": h.total_completions,
        "last_30_days": len(logs),
        "last_logged_at": h.last_logged_at.isoformat() if h.last_logged_at else None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CHECK-INS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/checkins", response_model=CheckInOut, status_code=201)
async def create_checkin(
    body: CheckInCreateDto,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Создать новый check-in."""
    checkin = await cs.create_goal_checkin(db, current_user.id, **body.model_dump(exclude_none=True))
    await db.commit()
    return checkin


@router.get("/checkins/today")
async def get_today_checkin(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Проверить, был ли check-in сегодня."""
    from datetime import timezone
    checkins = await cs.get_recent_goal_checkins(db, current_user.id, limit=1)
    if checkins:
        c = checkins[0]
        today = datetime.now(timezone.utc).date()
        if c.created_at.date() == today:
            return {"done": True, "checkin_id": c.id, "energy_level": c.energy_level}
    return {"done": False}


@router.get("/checkins/history", response_model=List[CheckInOut])
async def get_checkin_history(
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await cs.get_recent_goal_checkins(db, current_user.id, limit=limit)


# ══════════════════════════════════════════════════════════════════════════════
# REVIEWS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/reviews", response_model=List[ReviewOut])
async def list_reviews(
    goal_id: Optional[int] = Query(None),
    limit: int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select
    from db.models import GoalReview
    q = select(GoalReview).where(GoalReview.user_id == current_user.id)
    if goal_id:
        q = q.where(GoalReview.goal_id == goal_id)
    q = q.order_by(GoalReview.created_at.desc()).limit(limit)
    r = await db.execute(q)
    return r.scalars().all()


@router.get("/reviews/latest", response_model=Optional[ReviewOut])
async def get_latest_review(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await cs.get_latest_review(db, current_user.id)


# ══════════════════════════════════════════════════════════════════════════════
# INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/insights")
async def list_insights(
    limit: int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list:
    insights = await cs.get_active_insights(db, current_user.id, limit=limit)
    return [
        {
            "id": i.id,
            "insight_type": i.insight_type,
            "severity": i.severity,
            "title": getattr(i, 'title', ''),
            "body": getattr(i, 'body', ''),
            "is_read": i.is_read,
            "created_at": i.created_at.isoformat(),
        }
        for i in insights
    ]


@router.post("/insights/{insight_id}/read")
async def mark_insight_read(
    insight_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    await cs.mark_insight_read(db, insight_id, current_user.id)
    await db.commit()
    return {"read": True}


# ══════════════════════════════════════════════════════════════════════════════
# RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/recommendations")
async def list_recommendations(
    limit: int = Query(default=5, le=20),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list:
    recs = await cs.get_active_recommendations(db, current_user.id, limit=limit)
    return [
        {
            "id": r.id,
            "rec_type": r.rec_type,
            "priority": r.priority,
            "title": r.title,
            "body": getattr(r, 'body', ''),
            "action_type": r.action_type,
            "action_payload": r.action_payload,
        }
        for r in recs
    ]


@router.post("/recommendations/{rec_id}/dismiss")
async def dismiss_recommendation(
    rec_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    await cs.dismiss_recommendation(db, rec_id, current_user.id)
    await db.commit()
    return {"dismissed": True}


# ══════════════════════════════════════════════════════════════════════════════
# PROFILE
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/profile", response_model=CoachingProfileOut)
async def get_profile(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await cs.get_or_create_profile(db, current_user.id)


@router.put("/profile", response_model=CoachingProfileOut)
async def update_profile(
    body: CoachingProfileUpdateDto,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    profile = await cs.update_profile(db, current_user.id, **body.model_dump(exclude_none=True))
    await db.commit()
    return profile


# ══════════════════════════════════════════════════════════════════════════════
# ONBOARDING
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/onboarding", response_model=OnboardingOut)
async def get_onboarding_state(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await cs.get_or_create_onboarding(db, current_user.id)


@router.post("/onboarding/step")
async def advance_onboarding(
    body: OnboardingStepDto,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    state = await cs.advance_onboarding_step(db, current_user.id, body.step)
    await db.commit()
    return {"step": body.step, "done": state.bot_onboarding_done}


@router.post("/onboarding/complete")
async def complete_onboarding(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    from sqlalchemy import update as sql_update
    from db.models import CoachingOnboardingState
    await db.execute(
        sql_update(CoachingOnboardingState)
        .where(CoachingOnboardingState.user_id == current_user.id)
        .values(bot_onboarding_done=True)
    )
    await db.commit()
    return {"completed": True}


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/analytics/weekly", response_model=WeeklyAnalyticsOut)
async def weekly_analytics(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Сводная аналитика за текущую неделю."""
    user_id = current_user.id
    goals, state_data, risks, weekly_score, checkins = await asyncio.gather(
        cs.get_goals(db, user_id, status="active"),
        compute_user_state(db, user_id),
        compute_risk_scores(db, user_id),
        compute_weekly_score(db, user_id),
        cs.get_recent_goal_checkins(db, user_id, limit=7),
    )
    habits = await cs.get_habits(db, user_id, is_active=True)
    completion_rate = (
        sum(h.current_streak > 0 for h in habits) / len(habits)
        if habits else 0.0
    )
    return WeeklyAnalyticsOut(
        weekly_score=weekly_score,
        goals_progress=[_goal_to_dict(g) for g in goals],
        habits_completion_rate=round(completion_rate, 2),
        checkins_this_week=len(checkins),
        dropout_risk=risks.get("dropout", 0.0),
        state=state_data["state"],
    )


@router.get("/analytics/habits")
async def habits_analytics(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Аналитика по всем привычкам: completion rate, streaks."""
    habits = await cs.get_habits(db, current_user.id, is_active=True)
    at_risk = await cs.get_habits_at_risk(db, current_user.id, days_no_log=3)
    return {
        "total_habits": len(habits),
        "at_risk_count": len(at_risk),
        "avg_streak": round(sum(h.current_streak for h in habits) / len(habits), 1) if habits else 0,
        "habits": [_habit_to_dict(h) for h in habits],
    }


@router.get("/analytics/goals")
async def goals_analytics(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Аналитика по целям: прогресс, stuck, achieved."""
    user_id = current_user.id
    active = await cs.get_goals(db, user_id, status="active")
    achieved = await cs.get_goals(db, user_id, status="achieved")
    stuck = await cs.get_stuck_goals(db, user_id, days_no_progress=7)
    return {
        "active_count": len(active),
        "achieved_count": len(achieved),
        "stuck_count": len(stuck),
        "avg_progress": round(sum(g.progress_pct for g in active) / len(active), 1) if active else 0,
        "goals": [_goal_to_dict(g) for g in active],
    }


# ══════════════════════════════════════════════════════════════════════════════
# PROMPTS (sample prompts для UI)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/prompts")
async def get_prompts(
    context: Optional[str] = Query(None),  # onboarding|dashboard|goal|habit|review
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[str]:
    """
    Sample prompts для CoachPromptBubble и каруселей в UI.
    Контекстно-зависимые по параметру context.
    """
    state_data = await compute_user_state(db, current_user.id)
    state = state_data["state"]

    context_prompts = {
        "onboarding": [
            "Расскажи как ты работаешь",
            "Помоги поставить первую цель",
            "Покажи примеры привычек",
        ],
        "goal": [
            "Разбей эту цель на этапы",
            "Что мне сделать сегодня для этой цели?",
            "Оцени реалистичность дедлайна",
            "Найди связь этой цели с моими привычками",
        ],
        "habit": [
            "Как усилить эту привычку?",
            "Почему я срываюсь?",
            "Свяжи эту привычку с целью",
        ],
        "review": [
            "Оцени мою неделю",
            "Что у меня получилось?",
            "Что стоит изменить на следующей неделе?",
        ],
        "empty": [
            "С чего начать?",
            "Поставим первую цель",
            "Создадим привычку",
            "Расскажи о себе чтобы я мог помочь",
        ],
    }

    if context and context in context_prompts:
        return context_prompts[context]

    return _SAMPLE_PROMPTS.get(state, _SAMPLE_PROMPTS["default"])


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/memory")
async def get_memory(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list:
    memories = await cs.get_memory(db, current_user.id, top_n=20)
    return [
        {
            "key": m.key,
            "value": m.value,
            "confidence": m.confidence,
            "is_explicit": m.is_explicit,
        }
        for m in memories
    ]


@router.delete("/memory")
async def clear_memory(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Сбросить coaching-память (reversible learning)."""
    count = await cs.clear_memory(db, current_user.id)
    await db.commit()
    return {"cleared": count}


# ══════════════════════════════════════════════════════════════════════════════
# PERSONALIZATION
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/profile/personalization")
async def get_personalization_profile(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Возвращает поведенческий профиль адаптации коуча:
    тон общения, выявленные паттерны, области фокуса, лучшее время для работы.
    """
    state_data = await compute_user_state(db, current_user.id)
    state = state_data["state"]
    profile = state_data.get("profile")
    coach_tone = profile.coach_tone if profile else "motivational"

    # Получаем полный контекст адаптации
    adaptation = await get_adaptation_context(db, current_user.id, state)

    return {
        "tone": coach_tone,
        "tone_instruction": adaptation.get("tone_instruction"),
        "best_time": adaptation.get("best_time"),
        "active_patterns": adaptation.get("active_patterns", []),
        "focus_areas": adaptation.get("focus_areas", []),
        "has_explicit_corrections": adaptation.get("has_corrections", False),
    }


@router.post("/profile/reset", status_code=status.HTTP_200_OK)
async def reset_personalization_endpoint(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Сбрасывает всю персонализацию коуча: coaching_memory и behavior_patterns.
    Профиль, цели и привычки НЕ затрагиваются.
    """
    await reset_personalization_svc(db, current_user.id)
    await db.commit()
    return {
        "ok": True,
        "message": "Персонализация сброшена. Коуч начнёт адаптироваться заново.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATION ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/orchestration/pending")
async def get_pending_orchestration_actions(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list:
    """
    Список orchestration-действий, ожидающих подтверждения пользователя.
    Коуч предлагает создать задачу/событие/напоминание — пользователь подтверждает здесь.
    """
    actions = await cs.get_pending_actions(db, current_user.id)
    return [
        {
            "id": a.id,
            "action_type": a.action_type,
            "target_module": a.target_module,
            "payload": a.payload,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in actions
    ]


@router.post("/orchestration/{action_id}/confirm")
async def confirm_orchestration_action(
    action_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Подтвердить и выполнить orchestration-действие.
    Создаёт задачу/событие/напоминание в соответствующем модуле.
    """
    # Находим действие
    from sqlalchemy import select as sa_select
    result = await db.execute(
        sa_select(CoachingOrchestrationAction).where(
            CoachingOrchestrationAction.id == action_id,
            CoachingOrchestrationAction.user_id == current_user.id,
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Действие не найдено")
    if action.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Действие уже в статусе: {action.status}")

    # Сначала помечаем как подтверждённое
    await cs.confirm_orchestration_action(db, action_id, current_user.id)

    # Выполняем действие
    success, message = await execute_orchestration_action(db, action)
    await db.commit()

    return {"ok": success, "message": message, "action_id": action_id}


@router.post("/orchestration/{action_id}/reject")
async def reject_orchestration_action(
    action_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Отклонить orchestration-действие — оно не будет выполнено.
    """
    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(CoachingOrchestrationAction)
        .where(
            CoachingOrchestrationAction.id == action_id,
            CoachingOrchestrationAction.user_id == current_user.id,
        )
        .values(status="rejected")
    )
    await db.commit()
    return {"ok": True, "message": "Действие отклонено", "action_id": action_id}


# ══════════════════════════════════════════════════════════════════════════════
# CROSS-MODULE ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/cross-module/analyze")
async def trigger_cross_module_analysis(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Запустить кросс-модульный анализ вручную.
    Собирает сигналы из всех модулей, генерирует выводы и сохраняет рекомендации.
    Возвращает найденные проблемы и число сохранённых рекомендаций.
    """
    state_data = await compute_user_state(db, current_user.id)
    state = state_data["state"]

    result = await run_cross_module_analysis(db, current_user.id, state)
    await db.commit()

    return {
        "state": state,
        "inferences_found": len(result.get("inferences", [])),
        "recommendations_saved": result.get("saved_recommendations", 0),
        "top_inference": result.get("top_inference"),
        "signals_summary": {
            "tasks_overdue": result["signals"].get("tasks_overdue", 0),
            "calendar_events_today": result["signals"].get("calendar_events_today", 0),
            "last_workout_days_ago": result["signals"].get("last_workout_days_ago", 0),
            "habits_completion_rate": result["signals"].get("habits_completion_rate_week", 0),
        },
    }
