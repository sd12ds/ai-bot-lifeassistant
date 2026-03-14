"""
Фабрики тестовых объектов для coaching-моделей.
Используют factory_boy для генерации тестовых данных.
Так как SQLAlchemy async не интегрируется с factory_boy напрямую,
фабрики создают объекты моделей без сохранения в БД.
"""
from __future__ import annotations

import factory
from datetime import datetime, date, timedelta

from db.models import (
    Goal, Habit, HabitLog, GoalMilestone, GoalCheckin,
    CoachingInsight, CoachingRecommendation,
    UserCoachingProfile, CoachingMemory,
)

# Идентификатор тестового пользователя по умолчанию
DEFAULT_USER_ID = 123456789


class GoalFactory(factory.Factory):
    """Фабрика для создания тестовых целей."""

    class Meta:
        model = Goal

    user_id = DEFAULT_USER_ID
    title = factory.Sequence(lambda n: f"Тестовая цель #{n}")
    description = "Описание тестовой цели"
    area = factory.Iterator(["health", "career", "finance", "personal"])
    status = "active"
    progress_pct = factory.Iterator([0, 20, 50, 75])
    priority = "medium"
    is_frozen = False
    frozen_reason = None
    why_statement = "Потому что это важно для меня"
    first_step = "Сделать первый шаг"
    coaching_notes = None
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class HabitFactory(factory.Factory):
    """Фабрика для создания тестовых привычек."""

    class Meta:
        model = Habit

    user_id = DEFAULT_USER_ID
    title = factory.Sequence(lambda n: f"Тестовая привычка #{n}")
    description = "Описание тестовой привычки"
    area = factory.Iterator(["health", "productivity", "mindset", "sport"])
    frequency = "daily"
    target_count = 1
    color = "#5B8CFF"
    is_active = True
    current_streak = 0
    longest_streak = 0
    total_completions = 0
    difficulty = "medium"
    best_time = "morning"
    created_at = factory.LazyFunction(datetime.utcnow)


class HabitLogFactory(factory.Factory):
    """Фабрика для записей о выполнении привычки."""

    class Meta:
        model = HabitLog

    habit_id = 1
    user_id = DEFAULT_USER_ID
    logged_at = factory.LazyFunction(datetime.utcnow)
    value = 1
    notes = ""


class GoalMilestoneFactory(factory.Factory):
    """Фабрика для этапов цели."""

    class Meta:
        model = GoalMilestone

    goal_id = 1
    user_id = DEFAULT_USER_ID
    title = factory.Sequence(lambda n: f"Этап #{n}")
    description = "Описание этапа"
    status = "pending"
    sort_order = 0
    completed_at = None
    created_at = factory.LazyFunction(datetime.utcnow)


class GoalCheckinFactory(factory.Factory):
    """Фабрика для check-in прогресса по цели."""

    class Meta:
        model = GoalCheckin

    goal_id = 1
    user_id = DEFAULT_USER_ID
    progress_pct = 50
    energy_level = 4
    notes = "Всё идёт хорошо"
    blockers = None
    wins = "Выполнил план"
    created_at = factory.LazyFunction(datetime.utcnow)


class CoachingInsightFactory(factory.Factory):
    """Фабрика для coaching-инсайтов."""

    class Meta:
        model = CoachingInsight

    user_id = DEFAULT_USER_ID
    insight_type = factory.Iterator(["risk", "pattern", "achievement"])
    severity = factory.Iterator(["info", "low", "medium", "high"])
    title = factory.Sequence(lambda n: f"Инсайт #{n}")
    body = "Тело инсайта"
    source_modules = ["coaching"]
    is_read = False
    is_actioned = False
    valid_until = None
    created_at = factory.LazyFunction(datetime.utcnow)


class CoachingRecommendationFactory(factory.Factory):
    """Фабрика для рекомендаций коуча."""

    class Meta:
        model = CoachingRecommendation

    user_id = DEFAULT_USER_ID
    rec_type = "schedule_fix"
    title = factory.Sequence(lambda n: f"Рекомендация #{n}")
    body = "Текст рекомендации"
    priority = 3
    acted_on = False
    dismissed = False
    expires_at = None
    created_at = factory.LazyFunction(datetime.utcnow)


class UserCoachingProfileFactory(factory.Factory):
    """Фабрика для профиля пользователя в коучинге."""

    class Meta:
        model = UserCoachingProfile

    user_id = DEFAULT_USER_ID
    coach_tone = "friendly"
    coaching_mode = "standard"
    preferred_checkin_time = "20:00"
    preferred_review_day = "sunday"
    morning_brief_enabled = True
    evening_reflection_enabled = True
    max_daily_nudges = 3
    onboarding_completed = False
    focus_areas = ["health", "career"]
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class CoachingMemoryFactory(factory.Factory):
    """Фабрика для долгосрочной памяти коуча."""

    class Meta:
        model = CoachingMemory

    user_id = DEFAULT_USER_ID
    memory_type = "preference"
    key = factory.Sequence(lambda n: f"memory_key_{n}")
    value = "значение"
    confidence = 0.8
    evidence_count = 1
    is_explicit = False
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)
