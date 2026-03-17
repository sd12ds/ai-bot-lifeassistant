"""
Coaching API — Pydantic DTOs и вспомогательные функции.

Импортируются во все sub-router модули: coaching_routes_goals,
coaching_routes_habits, coaching_routes_checkins, coaching_routes_analytics.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════════════════════
# Goals
# ══════════════════════════════════════════════════════════════════════════════

class GoalCreateDto(BaseModel):
    """Создание новой цели."""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    area: Optional[str] = None          # health|finance|career|personal|relationships
    target_date: Optional[date] = None
    why_statement: Optional[str] = None
    first_step: Optional[str] = None
    priority: Optional[str] = None   # не передаём — DB использует default=medium


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
    priority: Optional[str] = None  # Приоритет: high|medium|low
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


# ══════════════════════════════════════════════════════════════════════════════
# Milestones
# ══════════════════════════════════════════════════════════════════════════════

class MilestoneCreateDto(BaseModel):
    """Создание этапа цели."""
    title: str = Field(..., min_length=1, max_length=200)
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
    sort_order: int = 0  # Порядок сортировки этапа (в модели sort_order)
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════════════════════════
# Habits
# ══════════════════════════════════════════════════════════════════════════════

class HabitCreateDto(BaseModel):
    """Создание привычки."""
    title: str = Field(..., min_length=1, max_length=200)
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


# ══════════════════════════════════════════════════════════════════════════════
# Check-in
# ══════════════════════════════════════════════════════════════════════════════

class CheckInCreateDto(BaseModel):
    """Создание чекина (один временной слот дня)."""
    energy_level: Optional[int] = Field(None, ge=1, le=5)  # обязателен для morning/midday
    mood: Optional[str] = None              # great|good|ok|tired|bad
    notes: Optional[str] = None             # рефлексия / ответ на «как прошёл день»
    blockers: Optional[str] = None          # что мешало
    wins: Optional[str] = None              # победы дня
    goal_id: Optional[int] = None
    progress_pct: Optional[int] = Field(None, ge=0, le=100)
    time_slot: str = "manual"               # morning|midday|evening|manual
    check_date: Optional[date] = None         # дата чекина (date-объект), если не указана — сегодня


class CheckInPatchDto(BaseModel):
    """Обновление существующего чекина."""
    energy_level: Optional[int] = Field(None, ge=1, le=5)
    mood: Optional[str] = None
    notes: Optional[str] = None
    blockers: Optional[str] = None
    wins: Optional[str] = None
    progress_pct: Optional[int] = Field(None, ge=0, le=100)


class CheckInOut(BaseModel):
    id: int
    goal_id: Optional[int] = None
    energy_level: Optional[int] = None
    mood: Optional[str] = None
    notes: Optional[str] = None
    blockers: Optional[str] = None
    wins: Optional[str] = None
    progress_pct: Optional[int] = None
    time_slot: str = "manual"
    check_date: Optional[date] = None         # дата чекина (date-объект)
    created_at: datetime

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════════════════════════
# Reviews
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# Profile
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# Dashboard
# ══════════════════════════════════════════════════════════════════════════════

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
    dropout_risk_level: str = "none"        # none|low|medium|high|critical


# ══════════════════════════════════════════════════════════════════════════════
# Onboarding
# ══════════════════════════════════════════════════════════════════════════════

class OnboardingStepDto(BaseModel):
    step: str       # intro|goals|habits|profile|done


class OnboardingOut(BaseModel):
    current_step: Optional[Any] = None  # В БД хранится как int (номер шага)
    steps_completed: Optional[list] = None  # nullable JSONB
    first_goal_created: bool
    first_habit_created: bool
    first_checkin_done: bool
    bot_onboarding_done: bool

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════════════════════════
# Analytics
# ══════════════════════════════════════════════════════════════════════════════

class WeeklyAnalyticsOut(BaseModel):
    weekly_score: int
    weekly_score_breakdown: dict = {}       # {goals, habits, engagement, recovery}
    goals_progress: list[dict]
    habits_completion_rate: float
    checkins_this_week: int
    dropout_risk: float
    dropout_risk_level: str = "none"
    state: str


# ══════════════════════════════════════════════════════════════════════════════
# Helpers — компактные dict-представления для dashboard
# ══════════════════════════════════════════════════════════════════════════════

def _goal_to_dict(g) -> dict:
    """Компактный dict цели для dashboard и аналитики."""
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
    """Компактный dict привычки для dashboard и аналитики."""
    return {
        "id": h.id,
        "title": h.title,
        "current_streak": h.current_streak,
        "longest_streak": h.longest_streak,
        "area": h.area,
        "today_done": (h.last_logged_at is not None and h.last_logged_at.date() == __import__("datetime").date.today()),
    }


# Sample prompts по состоянию пользователя (используются в dashboard + prompts endpoint)
SAMPLE_PROMPTS = {
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
