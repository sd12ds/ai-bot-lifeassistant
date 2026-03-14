"""
Coaching Engine — вычислительное ядро коучинга.

Реализует:
- compute_user_state() — скоринговый алгоритм §16
- compute_risk_scores() — формулы рисков §22.2
- update_daily_snapshot() — ежедневный снимок контекста
- get_context_pack() — пакет контекста для системного промпта агента

Принципы: только вычисления, никакого UI/LLM. Детерминировано.
"""
from __future__ import annotations

import logging
from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from db import coaching_storage as cs
from db.models import (
    Goal, Habit, HabitLog, CoachingMemory,
    CoachingContextSnapshot,
)

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Скоринговый алгоритм (§16 — Whole-User State Model)
# ══════════════════════════════════════════════════════════════════════════════

async def compute_user_state(
    session: AsyncSession,
    user_id: int,
    tasks_overdue: int = 0,
    calendar_events_today: int = 0,
    habits_done_today: int = 0,
    habits_total_today: int = 0,
    task_completion_rate_week: float = 1.0,  # 0.0-1.0
    no_workout_7d: bool = False,
    no_nutrition: bool = False,
) -> dict:
    """
    Вычисляет состояние пользователя по скоринговому алгоритму §16.

    Возвращает:
        {
            "state": "momentum" | "stable" | "overload" | "recovery" | "risk",
            "score": 0-100,
            "factors": dict с деталями
        }
    """
    score = 100  # начальный балл
    factors = {}

    # ── Штрафы за негативные сигналы ──────────────────────────────────────
    if tasks_overdue > 5:
        score -= 20
        factors["tasks_overdue"] = f"-20 (просрочено: {tasks_overdue})"

    if calendar_events_today > 8:
        score -= 15
        factors["calendar_overload"] = f"-15 (событий сегодня: {calendar_events_today})"

    habits_completion = (habits_done_today / habits_total_today) if habits_total_today > 0 else 1.0
    if habits_completion < 0.4:
        score -= 20
        factors["habits_low"] = f"-20 (выполнено: {habits_completion:.0%})"

    if task_completion_rate_week < 0.4:
        score -= 15
        factors["task_rate_low"] = f"-15 (скорость задач за неделю: {task_completion_rate_week:.0%})"

    if no_workout_7d:
        score -= 10
        factors["no_workout"] = "-10 (нет тренировок 7 дней)"

    if no_nutrition:
        score -= 5
        factors["no_nutrition"] = "-5 (нет логов питания)"

    score = max(0, min(100, score))

    # ── Определение состояния по итоговому скору ──────────────────────────
    # Если пользователь возвращается после долгого перерыва — recovery
    snapshot = await cs.get_latest_snapshot(session, user_id)
    in_recovery = False
    if snapshot and snapshot.overall_state in ("risk", "recovery"):
        in_recovery = True

    if score >= 75:
        state = "momentum"
    elif score >= 50:
        state = "stable"
    elif score >= 30:
        # Различаем overload (перегруз) и recovery (восстановление)
        state = "recovery" if in_recovery else "overload"
    else:
        state = "risk"

    return {
        "state": state,
        "score": score,
        "factors": factors,
        "habits_completion": habits_completion,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Формулы рисков (§22.2)
# ══════════════════════════════════════════════════════════════════════════════

async def compute_risk_scores(
    session: AsyncSession,
    user_id: int,
) -> dict[str, float]:
    """
    Вычисляет 4 вида рисков по формулам §22.2.

    Возвращает: {"dropout": 0.0-1.0, "overload": ..., "goal_failure": ..., "habit_death": ...}
    Threshold для HIGH RISK: > 0.7
    """
    now = datetime.utcnow()
    risks = {}

    # ── 1. Dropout risk: no_checkin_days×0.3 + habit_drop×0.25 + goal_stale×0.25 + task_spike×0.2 ──
    # no_checkin_days — дней с последнего check-in
    from db.models import GoalCheckin
    last_checkin_result = await session.execute(
        select(func.max(GoalCheckin.created_at)).where(GoalCheckin.user_id == user_id)
    )
    last_checkin = last_checkin_result.scalar_one_or_none()
    if last_checkin:
        no_checkin_days = (now - last_checkin).days
    else:
        no_checkin_days = 30  # никогда не делал check-in

    # habit_completion_drop — насколько упала выполняемость привычек (7 vs 14 дней)
    habit_completion_drop = await _compute_habit_completion_drop(session, user_id)

    # goal_progress_stale — доля целей без прогресса 7+ дней
    stuck_goals = await cs.get_stuck_goals(session, user_id, days_without_progress=7)
    active_goals_result = await session.execute(
        select(func.count(Goal.id)).where(Goal.user_id == user_id, Goal.status == "active")
    )
    active_goals_count = active_goals_result.scalar_one() or 1
    goal_progress_stale = len(stuck_goals) / active_goals_count

    # task_overdue_spike — нормализованный спайк просроченных задач (заглушка, полный сбор в Фазе 9)
    snapshot = await cs.get_latest_snapshot(session, user_id)
    task_overdue_spike = min(1.0, (snapshot.tasks_overdue / 10) if snapshot else 0.0)

    dropout = (
        min(1.0, no_checkin_days / 10) * 0.30
        + habit_completion_drop * 0.25
        + goal_progress_stale * 0.25
        + task_overdue_spike * 0.20
    )
    risks["dropout"] = round(min(1.0, dropout), 3)

    # ── 2. Overload risk ──────────────────────────────────────────────────
    tasks_overdue = snapshot.tasks_overdue if snapshot else 0
    calendar_load = snapshot.calendar_events_today if snapshot else 0
    active_goals = active_goals_count
    overload = (
        min(1.0, tasks_overdue / 10) * 0.35
        + min(1.0, calendar_load / 10) * 0.25
        + min(1.0, active_goals / 8) * 0.20
        + habit_completion_drop * 0.20
    )
    risks["overload"] = round(min(1.0, overload), 3)

    # ── 3. Goal failure risk ──────────────────────────────────────────────
    risks["goal_failure"] = round(min(1.0, goal_progress_stale * 1.2), 3)

    # ── 4. Habit death risk ───────────────────────────────────────────────
    at_risk_habits = await cs.get_habits_at_risk(session, user_id, days_no_log=3)
    active_habits_result = await session.execute(
        select(func.count(Habit.id)).where(Habit.user_id == user_id, Habit.is_active == True)  # noqa
    )
    active_habits = active_habits_result.scalar_one() or 1
    risks["habit_death"] = round(min(1.0, len(at_risk_habits) / active_habits), 3)

    # Сохраняем оценки рисков в БД
    for risk_type, score in risks.items():
        await cs.upsert_risk_score(
            session, user_id, risk_type, score,
            factors={"computed_at": now.isoformat()}
        )

    return risks


async def _compute_habit_completion_drop(
    session: AsyncSession, user_id: int
) -> float:
    """Вспомогательный: насколько упала выполняемость привычек последние 7 vs 14 дней."""
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    # Логи за последние 7 дней
    result7 = await session.execute(
        select(func.count(HabitLog.id)).where(
            HabitLog.user_id == user_id,
            HabitLog.logged_at >= week_ago,
        )
    )
    logs_7 = result7.scalar_one() or 0

    # Логи за предыдущие 7 дней (7-14 дней назад)
    result14 = await session.execute(
        select(func.count(HabitLog.id)).where(
            HabitLog.user_id == user_id,
            HabitLog.logged_at >= two_weeks_ago,
            HabitLog.logged_at < week_ago,
        )
    )
    logs_14 = result14.scalar_one() or 0

    if logs_14 == 0:
        return 0.0  # нет данных — не считаем риском

    # Насколько упало: (предыдущие - текущие) / предыдущие
    drop = max(0.0, (logs_14 - logs_7) / logs_14)
    return round(min(1.0, drop), 3)


# ══════════════════════════════════════════════════════════════════════════════
# Еженедельный скор пользователя (§22.3)
# ══════════════════════════════════════════════════════════════════════════════

async def compute_weekly_score(
    session: AsyncSession,
    user_id: int,
    goals_progress: float = -1.0,     # -1 означает "автовычисление из DB"
    habits_completion: float = -1.0,  # -1 означает "автовычисление из DB"
    checkins_done: int = -1,          # -1 означает "автовычисление из DB"
    review_done: bool = False,
    streak_recoveries: int = 0,
) -> int:
    """
    Weekly score 0-100 по формуле §22.3:
    Goals 30% + Habits 40% + Engagement 20% + Recovery 10%.

    При вызове без параметров (только session + user_id) автоматически
    запрашивает все данные из DB через coaching_analytics.
    """
    # Если параметры не переданы — используем auto-расчёт из DB
    if goals_progress < 0 and habits_completion < 0 and checkins_done < 0:
        try:
            from services.coaching_analytics import compute_weekly_score_auto
            score, _ = await compute_weekly_score_auto(session, user_id)
            return score
        except Exception:
            pass
        # Fallback к дефолтным значениям
        goals_progress = 0.5
        habits_completion = 0.5
        checkins_done = 0

    goals_score = goals_progress * 30
    habits_score = habits_completion * 40

    # Engagement: check-ins (max 3/неделя = полный балл) + review
    checkin_score = min(1.0, checkins_done / 3) * 15
    review_score = 5.0 if review_done else 0.0
    engagement_score = checkin_score + review_score

    # Recovery: возврат после срывов
    recovery_score = min(10.0, streak_recoveries * 5)

    total = int(goals_score + habits_score + engagement_score + recovery_score)
    return min(100, max(0, total))


# ══════════════════════════════════════════════════════════════════════════════
# Ежедневный снимок контекста (§5.2)
# ══════════════════════════════════════════════════════════════════════════════

async def update_daily_snapshot(
    session: AsyncSession,
    user_id: int,
    tasks_overdue: int = 0,
    tasks_completed_today: int = 0,
    calendar_events_today: int = 0,
    free_slots_today: int = 0,
    habits_done_today: int = 0,
    habits_total_today: int = 0,
) -> CoachingContextSnapshot:
    """
    Обновляет (или создаёт) ежедневный снимок контекста пользователя.
    Вычисляет state и score, сохраняет в coaching_context_snapshots.
    """
    # Вычисляем состояние
    state_data = await compute_user_state(
        session=session,
        user_id=user_id,
        tasks_overdue=tasks_overdue,
        calendar_events_today=calendar_events_today,
        habits_done_today=habits_done_today,
        habits_total_today=habits_total_today,
        task_completion_rate_week=1.0,  # будет уточнено в Phase 9
    )

    # Считаем зависшие цели и стрики под угрозой
    stuck_goals = await cs.get_stuck_goals(session, user_id, days_without_progress=7)
    at_risk_habits = await cs.get_habits_at_risk(session, user_id, days_no_log=3)

    snapshot = await cs.upsert_snapshot(
        session=session,
        user_id=user_id,
        snapshot_date=date.today(),
        tasks_overdue=tasks_overdue,
        tasks_completed_today=tasks_completed_today,
        calendar_events_today=calendar_events_today,
        free_slots_today=free_slots_today,
        habits_done_today=habits_done_today,
        habits_total_today=habits_total_today,
        stuck_goals=len(stuck_goals),
        streak_at_risk=len(at_risk_habits),
        overall_state=state_data["state"],
        score=state_data["score"],
    )

    logger.info(
        "Snapshot updated: user=%s state=%s score=%s",
        user_id, state_data["state"], state_data["score"]
    )
    return snapshot


# ══════════════════════════════════════════════════════════════════════════════
# Context Pack для системного промпта агента (§6.5)
# ══════════════════════════════════════════════════════════════════════════════

async def get_context_pack(
    session: AsyncSession,
    user_id: int,
) -> dict:
    """
    Формирует обязательный context pack для системного промпта агента §6.5:
    - active_goals_summary (топ-5 активных целей)
    - habits_summary (активные привычки + стрики)
    - user_state (текущее состояние из snapshot)
    - top_recommendations (до 3)
    - top_memory (топ-5 по confidence)
    - pending_milestones (незавершённые этапы)
    """
    # ── Состояние (с graceful degradation) ─────────────────────────────────
    state = "stable"
    score = 75
    try:
        snapshot = await cs.get_latest_snapshot(session, user_id)
        state = snapshot.overall_state if snapshot else "stable"
        score = snapshot.score if snapshot else 75
    except Exception as exc:
        logger.warning("get_context_pack: snapshot недоступен: %s", exc)
        snapshot = None

    # ── Цели (с graceful degradation) ────────────────────────────────────
    goals_summary = []
    try:
        goals = await cs.get_goals(session, user_id, status="active")
        for g in goals[:5]:
            summary = f"• {g.title} ({g.area or '—'}) — {g.progress_pct}%"
            if g.is_frozen:
                summary += " [заморожена]"
            goals_summary.append(summary)
    except Exception as exc:
        logger.warning("get_context_pack: цели недоступны: %s", exc)
        goals = []

    # ── Привычки (с graceful degradation) ───────────────────────────────
    habits_summary = []
    try:
        habits = await cs.get_habits(session, user_id, is_active=True)
        for h in habits[:8]:
            habits_summary.append(
                f"• {h.title} — стрик: {h.current_streak} дн. / рекорд: {h.longest_streak}"
            )
    except Exception as exc:
        logger.warning("get_context_pack: привычки недоступны: %s", exc)

    # ── Рекомендации (с graceful degradation) ────────────────────────────
    recs_summary = []
    try:
        recs = await cs.get_active_recommendations(session, user_id, limit=3)
        recs_summary = [f"• [{r.rec_type}] {r.title}" for r in recs]
    except Exception as exc:
        logger.warning("get_context_pack: рекомендации недоступны: %s", exc)

    # ── Память (с graceful degradation) ──────────────────────────────────
    memory_summary = []
    try:
        memories = await cs.get_memory(session, user_id, top_n=5)
        memory_summary = [f"• {m.key}: {m.value} (confidence={m.confidence:.1f})" for m in memories]
    except Exception as exc:
        logger.warning("get_context_pack: память недоступна: %s", exc)

    # Кросс-модульный вывод (Phase 9) — lazy import для избежания circular dependency
    cross_module_top = None
    try:
        from services.coaching_cross_module import (
            collect_module_signals,
            generate_cross_module_inferences,
        )
        signals = await collect_module_signals(session, user_id)
        inferences = generate_cross_module_inferences(signals)
        if inferences:
            top = inferences[0]
            cross_module_top = f"[{top['type']}] {top['title']}: {top['description']}"
    except Exception:
        pass  # cross-module анализ — некритичный, не ломаем context pack

    return {
        "state": state,
        "score": score,
        "goals_summary": goals_summary,
        "habits_summary": habits_summary,
        "recommendations": recs_summary,
        "memory": memory_summary,
        "stuck_goals_count": snapshot.stuck_goals if snapshot else 0,
        "streak_at_risk_count": snapshot.streak_at_risk if snapshot else 0,
        # Персонализированный тон (Phase 8)
        "tone_instruction": await _get_tone_instruction_safe(session, user_id, state),
        # Топовый кросс-модульный вывод (Phase 9)
        "cross_module_top": cross_module_top,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Адаптация тона коуча под состояние пользователя (§6.2, §16)
# ══════════════════════════════════════════════════════════════════════════════


async def _get_tone_instruction_safe(session, user_id: int, state: str) -> str | None:
    """Безопасно получает персонализированную инструкцию тона (с fallback)."""
    try:
        from services.coaching_personalization import get_adaptation_context
        ctx = await get_adaptation_context(session, user_id, state)
        return ctx.get("tone_instruction")
    except Exception:
        return None


def get_tone_for_state(state: str) -> str:
    """
    Возвращает описание тона/стиля коуча под текущее состояние.
    Используется в системном промпте агента.
    """
    tones = {
        "momentum": (
            "Пользователь в состоянии MOMENTUM — высокая энергия, всё идёт хорошо. "
            "Будь бодрым и вдохновляющим. Предлагай новые вызовы и амбициозные шаги. "
            "Отмечай достижения с энтузиазмом."
        ),
        "stable": (
            "Пользователь в состоянии STABLE — всё нормально, устойчивый ритм. "
            "Нейтральный и поддерживающий тон. Помогай поддерживать текущий курс."
        ),
        "overload": (
            "Пользователь в состоянии OVERLOAD — перегрузка, много задач. "
            "НЕ давай дополнительного давления. Помогай разгрузиться, расставить приоритеты. "
            "Предлагай отказаться от лишнего."
        ),
        "recovery": (
            "Пользователь в состоянии RECOVERY — возвращается после паузы или срыва. "
            "Мягкий тон, БЕЗ упрёков. Предлагай маленький конкретный шаг. "
            "«Пропуск не обнуляет прогресс — главное вернуться.»"
        ),
        "risk": (
            "Пользователь в состоянии RISK — высокий риск dropout. "
            "Заботливый, прямой, без осуждения. Reactivation-сценарий. "
            "Одно простое действие прямо сейчас."
        ),
    }
    return tones.get(state, tones["stable"])
