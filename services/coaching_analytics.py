"""
CoachingAnalytics — детальные метрики и аналитика коучинг-модуля.

Источник: §22 документа coaching-architecture.md.

Предоставляет:
- Метрики целей: completion rate, среднее время достижения, abandonment rate, этапы
- Метрики привычек: 7-дневный rolling consistency, лучший/худший день, паттерны времени
- Метрики вовлечённости: частота check-in, nudge response rate, сессии/неделя
- Weekly score (автоматический расчёт из DB)
- Dropout risk (полная формула §22.2)
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Goal, GoalMilestone, GoalCheckin, GoalReview,
    Habit, HabitLog, HabitStreak,
    CoachingSession, CoachingNudgeLog,
)
from db import coaching_storage as cs

logger = logging.getLogger(__name__)

# Порог риска дропаута — выше этого значения → reactivation-сценарий
DROPOUT_RISK_HIGH_THRESHOLD = 0.7


# ══════════════════════════════════════════════════════════════════════════════
# Метрики целей (§22.1)
# ══════════════════════════════════════════════════════════════════════════════

async def get_goal_metrics(session: AsyncSession, user_id: int, days: int = 30) -> dict:
    """
    Метрики по целям за последние N дней.
    Возвращает: completion_rate, avg_days_to_achieve, abandonment_rate,
                milestone_completion_rate, goals_by_area.
    """
    now = datetime.utcnow()
    since = now - timedelta(days=days)

    # Все цели пользователя
    all_goals_result = await session.execute(
        select(Goal).where(Goal.user_id == user_id)
    )
    all_goals = list(all_goals_result.scalars().all())

    if not all_goals:
        return {
            "completion_rate": 0.0,
            "avg_days_to_achieve": None,
            "abandonment_rate": 0.0,
            "milestone_completion_rate": 0.0,
            "goals_by_area": {},
            "total": 0,
            "active": 0,
            "achieved": 0,
            "archived": 0,
        }

    total = len(all_goals)
    achieved = [g for g in all_goals if g.status == "achieved"]
    active = [g for g in all_goals if g.status == "active"]
    archived = [g for g in all_goals if g.status == "archived"]

    # Completion rate: достигнутые / (достигнутые + архивированные + активные)
    completion_rate = len(achieved) / total if total else 0.0

    # Среднее время достижения (дней от created_at до updated_at у achieved)
    times_to_achieve = []
    for g in achieved:
        if g.created_at and g.updated_at:
            delta = g.updated_at - g.created_at
            times_to_achieve.append(delta.days)
    avg_days_to_achieve = (
        round(sum(times_to_achieve) / len(times_to_achieve), 1)
        if times_to_achieve else None
    )

    # Abandonment rate: архивированные без достижения / всего созданных (не active)
    total_closed = len(achieved) + len(archived)
    abandonment_rate = len(archived) / total_closed if total_closed > 0 else 0.0

    # Milestone completion rate
    milestones_result = await session.execute(
        select(GoalMilestone).where(
            GoalMilestone.goal_id.in_([g.id for g in all_goals])
        )
    )
    all_milestones = list(milestones_result.scalars().all())
    done_milestones = [m for m in all_milestones if m.status == "done"]
    milestone_completion_rate = (
        len(done_milestones) / len(all_milestones) if all_milestones else 0.0
    )

    # Распределение по областям
    goals_by_area: dict = {}
    for g in all_goals:
        area = g.area or "other"
        goals_by_area[area] = goals_by_area.get(area, 0) + 1

    return {
        "completion_rate": round(completion_rate, 2),
        "avg_days_to_achieve": avg_days_to_achieve,
        "abandonment_rate": round(abandonment_rate, 2),
        "milestone_completion_rate": round(milestone_completion_rate, 2),
        "goals_by_area": goals_by_area,
        "total": total,
        "active": len(active),
        "achieved": len(achieved),
        "archived": len(archived),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Метрики привычек (§22.1)
# ══════════════════════════════════════════════════════════════════════════════

async def get_habit_detailed_metrics(
    session: AsyncSession, user_id: int, days: int = 30
) -> list[dict]:
    """
    Детальные метрики для каждой активной привычки:
    - consistency_score: 7-дневный rolling (число выполненных из последних 7 дней)
    - best_day_of_week: день с наибольшим числом выполнений (0=пн, 6=вс)
    - worst_day_of_week: день с наименьшим числом выполнений
    - morning_ratio: доля выполнений до 12:00
    - completion_rate: за последние N дней
    """
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    week_ago = now - timedelta(days=7)

    habits = await cs.get_habits(session, user_id, is_active=True)
    result = []

    for h in habits:
        # Логи за период
        logs_result = await session.execute(
            select(HabitLog).where(
                HabitLog.habit_id == h.id,
                HabitLog.logged_at >= since,
            ).order_by(HabitLog.logged_at)
        )
        logs = list(logs_result.scalars().all())

        # Completion rate за период
        completion_rate = len(logs) / days if days > 0 else 0.0

        # 7-дневный rolling consistency (0-7)
        recent_logs = [l for l in logs if l.logged_at >= week_ago]
        consistency_score = len(recent_logs)  # 0-7

        # Паттерны по дням недели
        day_counts: Counter = Counter()
        hour_counts: Counter = Counter()
        for log in logs:
            if log.logged_at:
                day_counts[log.logged_at.weekday()] += 1
                hour_counts[log.logged_at.hour] += 1

        best_day = day_counts.most_common(1)[0][0] if day_counts else None
        worst_day = day_counts.most_common()[-1][0] if day_counts else None

        # Временной паттерн: утро (5-12), день (12-18), вечер (18-23)
        morning = sum(v for k, v in hour_counts.items() if 5 <= k < 12)
        afternoon = sum(v for k, v in hour_counts.items() if 12 <= k < 18)
        evening = sum(v for k, v in hour_counts.items() if 18 <= k < 23)
        total_with_time = morning + afternoon + evening

        days_map = {0: "пн", 1: "вт", 2: "ср", 3: "чт", 4: "пт", 5: "сб", 6: "вс"}

        result.append({
            "habit_id": h.id,
            "title": h.title,
            "area": h.area,
            "current_streak": h.current_streak,
            "longest_streak": h.longest_streak,
            "total_completions": h.total_completions,
            "completion_rate": round(min(1.0, completion_rate), 2),
            "consistency_score": consistency_score,
            "best_day": days_map.get(best_day) if best_day is not None else None,
            "worst_day": days_map.get(worst_day) if worst_day is not None else None,
            "time_pattern": {
                "morning_ratio": round(morning / total_with_time, 2) if total_with_time else 0,
                "afternoon_ratio": round(afternoon / total_with_time, 2) if total_with_time else 0,
                "evening_ratio": round(evening / total_with_time, 2) if total_with_time else 0,
            },
        })

    return result


# ══════════════════════════════════════════════════════════════════════════════
# Метрики вовлечённости (§22.1)
# ══════════════════════════════════════════════════════════════════════════════

async def get_engagement_metrics(
    session: AsyncSession, user_id: int, days: int = 30
) -> dict:
    """
    Метрики вовлечённости пользователя в систему за последние N дней:
    - checkin_frequency: check-ins/неделю
    - nudge_response_rate: доля nudges с реакцией
    - sessions_per_week: сессий с коучем в неделю
    - feature_usage: использование функций (goals/habits/checkins/reviews)
    """
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    weeks = max(1, days / 7)

    # Check-in частота
    checkins_result = await session.execute(
        select(func.count(GoalCheckin.id)).where(
            GoalCheckin.user_id == user_id,
            GoalCheckin.created_at >= since,
        )
    )
    total_checkins = checkins_result.scalar_one() or 0
    checkin_frequency = round(total_checkins / weeks, 1)

    # Nudge response rate
    total_nudges_result = await session.execute(
        select(func.count(CoachingNudgeLog.id)).where(
            CoachingNudgeLog.user_id == user_id,
            CoachingNudgeLog.sent_at >= since,
        )
    )
    total_nudges = total_nudges_result.scalar_one() or 0

    responded_nudges_result = await session.execute(
        select(func.count(CoachingNudgeLog.id)).where(
            CoachingNudgeLog.user_id == user_id,
            CoachingNudgeLog.sent_at >= since,
            CoachingNudgeLog.acted_on == True,  # noqa
        )
    )
    responded_nudges = responded_nudges_result.scalar_one() or 0
    nudge_response_rate = round(responded_nudges / total_nudges, 2) if total_nudges else 0.0

    # Coaching sessions per week
    sessions_result = await session.execute(
        select(func.count(CoachingSession.id)).where(
            CoachingSession.user_id == user_id,
            CoachingSession.created_at >= since,
        )
    )
    total_sessions = sessions_result.scalar_one() or 0
    sessions_per_week = round(total_sessions / weeks, 1)

    # Feature usage
    reviews_result = await session.execute(
        select(func.count(GoalReview.id)).where(
            GoalReview.user_id == user_id,
            GoalReview.created_at >= since,
        )
    )
    total_reviews = reviews_result.scalar_one() or 0

    goals_created_result = await session.execute(
        select(func.count(Goal.id)).where(
            Goal.user_id == user_id,
            Goal.created_at >= since,
        )
    )
    goals_created = goals_created_result.scalar_one() or 0

    habits_logged_result = await session.execute(
        select(func.count(HabitLog.id)).where(
            HabitLog.user_id == user_id,
            HabitLog.logged_at >= since,
        )
    )
    habits_logged = habits_logged_result.scalar_one() or 0

    return {
        "checkin_frequency_per_week": checkin_frequency,
        "nudge_response_rate": nudge_response_rate,
        "nudges_sent": total_nudges,
        "sessions_per_week": sessions_per_week,
        "total_sessions": total_sessions,
        "feature_usage": {
            "goals_created": goals_created,
            "habits_logged": habits_logged,
            "checkins_done": total_checkins,
            "reviews_done": total_reviews,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# Стрик-аналитика
# ══════════════════════════════════════════════════════════════════════════════

async def get_streak_analytics(session: AsyncSession, user_id: int) -> dict:
    """
    Обзорная аналитика стриков: лучшие привычки, рекорды, at-risk.
    """
    habits = await cs.get_habits(session, user_id, is_active=True)
    at_risk = await cs.get_habits_at_risk(session, user_id, days_no_log=2)
    at_risk_ids = {h.id for h in at_risk}

    # Топ-3 по текущему стрику
    sorted_by_streak = sorted(habits, key=lambda h: h.current_streak, reverse=True)
    top_streaks = [
        {
            "habit_id": h.id,
            "title": h.title,
            "current_streak": h.current_streak,
            "longest_streak": h.longest_streak,
            "at_risk": h.id in at_risk_ids,
        }
        for h in sorted_by_streak[:5]
    ]

    # Глобальный рекорд стрика
    global_record = max((h.longest_streak for h in habits), default=0)
    current_max = max((h.current_streak for h in habits), default=0)

    return {
        "total_active_habits": len(habits),
        "at_risk_count": len(at_risk),
        "global_record_streak": global_record,
        "current_max_streak": current_max,
        "top_streaks": top_streaks,
        "at_risk_habits": [
            {"habit_id": h.id, "title": h.title, "current_streak": h.current_streak}
            for h in at_risk
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# Weekly score — автоматический расчёт из DB (§22.3)
# ══════════════════════════════════════════════════════════════════════════════

async def compute_weekly_score_auto(session: AsyncSession, user_id: int) -> tuple[int, dict]:
    """
    Вычисляет weekly score 0-100 из БД без ручных параметров.
    Формула §22.3: Goals 30% + Habits 40% + Engagement 20% + Recovery 10%

    Возвращает (score: int, breakdown: dict) — детализацию по компонентам.
    """
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    # ── Goals progress (30%) ─────────────────────────────────────────────────
    active_goals = await cs.get_goals(session, user_id, status="active")
    if active_goals:
        avg_progress = sum(g.progress_pct for g in active_goals) / len(active_goals) / 100
    else:
        avg_progress = 0.5  # нет целей — нейтральный скор
    goals_score = round(avg_progress * 30, 1)

    # ── Habits completion rate (40%) ─────────────────────────────────────────
    habits = await cs.get_habits(session, user_id, is_active=True)
    habit_score = 0.0
    if habits:
        total_expected = len(habits) * 7  # 1 выполнение/привычка/день = 7 за неделю
        done_result = await session.execute(
            select(func.count(HabitLog.id)).where(
                HabitLog.habit_id.in_([h.id for h in habits]),
                HabitLog.logged_at >= week_ago,
            )
        )
        done_count = done_result.scalar_one() or 0
        habits_completion = min(1.0, done_count / total_expected)
        habit_score = round(habits_completion * 40, 1)
    else:
        habit_score = 20.0  # нет привычек — половина балла

    # ── Engagement (20%): check-ins 15% + review 5% ──────────────────────────
    checkins_result = await session.execute(
        select(func.count(GoalCheckin.id)).where(
            GoalCheckin.user_id == user_id,
            GoalCheckin.created_at >= week_ago,
        )
    )
    checkins_done = checkins_result.scalar_one() or 0
    # Цель: 3 check-in в неделю = полный балл
    checkin_score = round(min(1.0, checkins_done / 3) * 15, 1)

    reviews_result = await session.execute(
        select(func.count(GoalReview.id)).where(
            GoalReview.user_id == user_id,
            GoalReview.created_at >= week_ago,
        )
    )
    review_done = (reviews_result.scalar_one() or 0) > 0
    review_score = 5.0 if review_done else 0.0
    engagement_score = round(checkin_score + review_score, 1)

    # ── Recovery (10%): возврат стриков после срыва ──────────────────────────
    # Считаем привычки у которых streak > 0 но были срывы на этой неделе
    recovery_score = 0.0
    for h in habits:
        if h.current_streak > 0:
            # Есть ли записи типа "miss" за последнюю неделю — значит был срыв и возврат
            miss_result = await session.execute(
                select(func.count(HabitLog.id)).where(
                    HabitLog.habit_id == h.id,
                    HabitLog.logged_at >= week_ago,
                    HabitLog.status == "missed",
                )
            )
            if (miss_result.scalar_one() or 0) > 0:
                recovery_score += 5.0
                if recovery_score >= 10.0:
                    break
    recovery_score = min(10.0, recovery_score)

    total = int(goals_score + habit_score + engagement_score + recovery_score)
    total = min(100, max(0, total))

    breakdown = {
        "goals": goals_score,
        "habits": habit_score,
        "engagement": engagement_score,
        "recovery": recovery_score,
        "checkins_this_week": checkins_done,
        "review_done": review_done,
    }

    return total, breakdown


# ══════════════════════════════════════════════════════════════════════════════
# Dropout risk — полная формула (§22.2)
# ══════════════════════════════════════════════════════════════════════════════

async def compute_dropout_risk_detailed(session: AsyncSession, user_id: int) -> dict:
    """
    Dropout risk по полной формуле §22.2 с детализацией факторов.
    Возвращает score, level, is_high_risk, factors, reactivation_needed.
    """
    now = datetime.utcnow()

    # no_checkin_days — дней с последнего check-in
    last_checkin_result = await session.execute(
        select(func.max(GoalCheckin.created_at)).where(GoalCheckin.user_id == user_id)
    )
    last_checkin = last_checkin_result.scalar_one_or_none()
    no_checkin_days = (now - last_checkin).days if last_checkin else 30

    # habit_completion_drop — падение за 7 vs 14 дней
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    habits = await cs.get_habits(session, user_id, is_active=True)
    habit_completion_drop = 0.0
    if habits:
        habit_ids = [h.id for h in habits]
        recent_result = await session.execute(
            select(func.count(HabitLog.id)).where(
                HabitLog.habit_id.in_(habit_ids),
                HabitLog.logged_at >= week_ago,
            )
        )
        previous_result = await session.execute(
            select(func.count(HabitLog.id)).where(
                HabitLog.habit_id.in_(habit_ids),
                HabitLog.logged_at >= two_weeks_ago,
                HabitLog.logged_at < week_ago,
            )
        )
        recent_count = recent_result.scalar_one() or 0
        previous_count = previous_result.scalar_one() or 0
        if previous_count > 0:
            habit_completion_drop = max(0.0, (previous_count - recent_count) / previous_count)

    # goal_progress_stale — доля целей без прогресса 7+ дней
    stuck_goals = await cs.get_stuck_goals(session, user_id, days_without_progress=7)
    active_goals = await cs.get_goals(session, user_id, status="active")
    goal_progress_stale = len(stuck_goals) / len(active_goals) if active_goals else 0.0

    # task_overdue_spike — нормализованный спайк просроченных задач
    snapshot = await cs.get_latest_snapshot(session, user_id)
    task_overdue_spike = min(1.0, (snapshot.tasks_overdue / 10)) if snapshot else 0.0

    # Итоговая формула
    score = (
        min(1.0, no_checkin_days / 10) * 0.30
        + habit_completion_drop * 0.25
        + goal_progress_stale * 0.25
        + task_overdue_spike * 0.20
    )
    score = round(min(1.0, score), 3)

    # Уровень риска
    if score >= DROPOUT_RISK_HIGH_THRESHOLD:
        level = "critical"
    elif score >= 0.5:
        level = "high"
    elif score >= 0.3:
        level = "medium"
    elif score >= 0.1:
        level = "low"
    else:
        level = "none"

    return {
        "score": score,
        "level": level,
        "is_high_risk": score >= DROPOUT_RISK_HIGH_THRESHOLD,
        "reactivation_needed": score >= DROPOUT_RISK_HIGH_THRESHOLD,
        "factors": {
            "no_checkin_days": no_checkin_days,
            "habit_completion_drop": round(habit_completion_drop, 2),
            "goal_progress_stale": round(goal_progress_stale, 2),
            "task_overdue_spike": round(task_overdue_spike, 2),
        },
        "recommendations": _get_dropout_recommendations(score, no_checkin_days, habit_completion_drop),
    }


def _get_dropout_recommendations(
    score: float,
    no_checkin_days: int,
    habit_drop: float,
) -> list[str]:
    """Формирует конкретные советы по снижению риска дропаута."""
    recs = []
    if no_checkin_days >= 5:
        recs.append("Сделай быстрый check-in — это займёт 30 секунд")
    if no_checkin_days >= 10:
        recs.append("Выбери одну цель и сделай один маленький шаг прямо сейчас")
    if habit_drop > 0.3:
        recs.append("Вернись к одной ключевой привычке — не нужно восстанавливать все сразу")
    if score >= DROPOUT_RISK_HIGH_THRESHOLD:
        recs.append("Расскажи мне что мешает — я подстрою план под твою текущую ситуацию")
    return recs
