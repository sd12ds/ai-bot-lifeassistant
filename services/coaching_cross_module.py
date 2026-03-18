"""
CoachingCrossModule — межмодульный интеллект коуча.

Собирает сигналы из всех модулей (Tasks, Calendar, Fitness, Nutrition, Reminders),
интерпретирует их как кросс-модульные выводы и генерирует рекомендации.

Архитектурная роль: превращает Coaching в надстроечный оркестратор,
а не просто сервис целей/привычек.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, date, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Task, WorkoutSession, Meal, Reminder, NotificationLog,
    FitnessGoal, CoachingOrchestrationAction,
    Goal, Habit, HabitLog, UserCoachingProfile,
    ActivityLog,
)
from db import coaching_storage as cs

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Типы кросс-модульных выводов
# ══════════════════════════════════════════════════════════════════════════════

INFERENCE_TYPES = {
    "conflict":         "Конфликт",           # цель требует времени, но нет свободных окон
    "cause_effect":     "Причинная связь",     # падение дисциплины = нарушение питания
    "imbalance":        "Дисбаланс",           # цель «фитнес» + нет тренировок
    "overload":         "Перегруз",            # слишком много задач/целей/привычек
    "failure_pattern":  "Паттерн срывов",      # регулярные сбои при определённых условиях
    "blind_spot":       "Слепое пятно",        # цель не отражена в других модулях
}

# Типы рекомендаций, которые engine создаёт на основе выводов
REC_TYPE_MAP = {
    "conflict":         "schedule_fix",
    "cause_effect":     "nutrition_fitness_link",
    "imbalance":        "habit_time_adjust",
    "overload":         "workload_reduce",
    "failure_pattern":  "cross_module_plan",
    "blind_spot":       "goal_decompose",
}


# ══════════════════════════════════════════════════════════════════════════════
# Сбор сигналов из модулей
# ══════════════════════════════════════════════════════════════════════════════

async def collect_module_signals(session: AsyncSession, user_id: int) -> dict:
    """
    Собирает сигналы из всех 5 модулей: Tasks, Calendar, Fitness, Nutrition, Reminders.
    Возвращает словарь с метриками для кросс-модульного анализа.
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    three_days_ago = now - timedelta(days=3)

    signals: dict = {}

    # ── Tasks сигналы ─────────────────────────────────────────────────────────
    try:
        # Просроченные задачи
        overdue_result = await session.execute(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.is_done == False,  # noqa: E712
                Task.due_datetime < now,
                Task.event_type == "task",
            )
        )
        signals["tasks_overdue"] = overdue_result.scalar_one() or 0

        # Выполненные сегодня
        done_today_result = await session.execute(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.is_done == True,  # noqa: E712
                Task.updated_at >= today_start,
                Task.event_type == "task",
            )
        )
        signals["tasks_completed_today"] = done_today_result.scalar_one() or 0

        # Общее и выполненное за 7 дней — для completion rate
        total_week_result = await session.execute(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.event_type == "task",
                Task.created_at >= week_ago,
            )
        )
        total_week = total_week_result.scalar_one() or 0

        done_week_result = await session.execute(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.is_done == True,  # noqa: E712
                Task.event_type == "task",
                Task.updated_at >= week_ago,
            )
        )
        done_week = done_week_result.scalar_one() or 0
        signals["tasks_completion_rate_week"] = round(done_week / total_week, 2) if total_week else 0

        # Активные задачи всего
        active_tasks_result = await session.execute(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.is_done == False,  # noqa: E712
                Task.event_type == "task",
            )
        )
        signals["tasks_active_total"] = active_tasks_result.scalar_one() or 0
    except Exception as exc:
        logger.warning("cross_module: Tasks сигналы недоступны: %s", exc)
        signals.update({"tasks_overdue": 0, "tasks_completed_today": 0,
                        "tasks_completion_rate_week": 0, "tasks_active_total": 0})

    # ── Calendar сигналы ──────────────────────────────────────────────────────
    try:
        today_end = today_start + timedelta(days=1)
        next_3d_end = today_start + timedelta(days=3)

        # Событий сегодня
        events_today_result = await session.execute(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.event_type == "event",
                Task.start_at >= today_start,
                Task.start_at < today_end,
            )
        )
        signals["calendar_events_today"] = events_today_result.scalar_one() or 0

        # Событий следующие 3 дня
        events_3d_result = await session.execute(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.event_type == "event",
                Task.start_at >= today_start,
                Task.start_at < next_3d_end,
            )
        )
        signals["calendar_load_next_3days"] = events_3d_result.scalar_one() or 0

        # Простая эвристика свободных слотов: если сегодня < 4 событий — есть слоты
        signals["free_slots_today"] = max(0, 4 - signals["calendar_events_today"])
    except Exception as exc:
        logger.warning("cross_module: Calendar сигналы недоступны: %s", exc)
        signals.update({"calendar_events_today": 0, "calendar_load_next_3days": 0, "free_slots_today": 2})

    # ── Fitness сигналы ───────────────────────────────────────────────────────
    try:
        # Последняя тренировка
        last_workout_result = await session.execute(
            select(WorkoutSession.started_at).where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.started_at.isnot(None),
            ).order_by(WorkoutSession.started_at.desc()).limit(1)
        )
        last_workout_row = last_workout_result.scalar_one_or_none()
        if last_workout_row:
            delta = now - last_workout_row.replace(tzinfo=timezone.utc) if last_workout_row.tzinfo is None else now - last_workout_row
            signals["last_workout_days_ago"] = delta.days
        else:
            signals["last_workout_days_ago"] = 999  # никогда не тренировался

        # Тренировок за текущую неделю
        workouts_week_result = await session.execute(
            select(func.count(WorkoutSession.id)).where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.started_at >= week_ago,
            )
        )
        signals["workouts_this_week"] = workouts_week_result.scalar_one() or 0

        # Фитнес-цель (целевые тренировки в неделю)
        fitness_goal_result = await session.execute(
            select(FitnessGoal).where(FitnessGoal.user_id == user_id)
        )
        fitness_goal = fitness_goal_result.scalar_one_or_none()
        signals["fitness_target_workouts_week"] = fitness_goal.workouts_per_week if fitness_goal else 3
        signals["fitness_goal_progress"] = round(
            signals["workouts_this_week"] / signals["fitness_target_workouts_week"], 2
        ) if signals["fitness_target_workouts_week"] else 0

        # Активности (кардио, шаги, растяжка и пр.) за неделю
        activities_week_result = await session.execute(
            select(func.count(ActivityLog.id)).where(
                ActivityLog.user_id == user_id,
                ActivityLog.logged_at >= week_ago,
            )
        )
        signals["activities_this_week"] = activities_week_result.scalar_one() or 0

        # Последняя активность
        last_activity_result = await session.execute(
            select(ActivityLog.logged_at).where(
                ActivityLog.user_id == user_id,
            ).order_by(ActivityLog.logged_at.desc()).limit(1)
        )
        last_act_row = last_activity_result.scalar_one_or_none()
        if last_act_row:
            delta_act = now - (last_act_row.replace(tzinfo=timezone.utc) if last_act_row.tzinfo is None else last_act_row)
            signals["last_activity_days_ago"] = delta_act.days
        else:
            signals["last_activity_days_ago"] = 999
    except Exception as exc:
        logger.warning("cross_module: Fitness сигналы недоступны: %s", exc)
        signals.update({"last_workout_days_ago": 0, "workouts_this_week": 0,
                        "fitness_target_workouts_week": 3, "fitness_goal_progress": 0,
                        "activities_this_week": 0, "last_activity_days_ago": 999})

    # ── Nutrition сигналы ─────────────────────────────────────────────────────
    try:
        # Приёмов пищи сегодня
        meals_today_result = await session.execute(
            select(func.count(Meal.id)).where(
                Meal.user_id == user_id,
                Meal.eaten_at >= today_start,
            )
        )
        signals["nutrition_logged_today"] = meals_today_result.scalar_one() or 0

        # Стрик питания: сколько подряд дней есть логи (max 7 дней)
        streak = 0
        for d in range(7):
            day_start = today_start - timedelta(days=d)
            day_end = day_start + timedelta(days=1)
            count_result = await session.execute(
                select(func.count(Meal.id)).where(
                    Meal.user_id == user_id,
                    Meal.eaten_at >= day_start,
                    Meal.eaten_at < day_end,
                )
            )
            if (count_result.scalar_one() or 0) > 0:
                streak += 1
            else:
                break
        signals["nutrition_streak"] = streak

        # Среднее количество приёмов за 7 дней (adherence: цель = 3/день)
        total_meals_week_result = await session.execute(
            select(func.count(Meal.id)).where(
                Meal.user_id == user_id,
                Meal.eaten_at >= week_ago,
            )
        )
        total_meals_week = total_meals_week_result.scalar_one() or 0
        signals["avg_meals_per_day_week"] = round(total_meals_week / 7, 1)
        signals["nutrition_adherence"] = round(min(1.0, signals["avg_meals_per_day_week"] / 3), 2)
    except Exception as exc:
        logger.warning("cross_module: Nutrition сигналы недоступны: %s", exc)
        signals.update({"nutrition_logged_today": 0, "nutrition_streak": 0,
                        "avg_meals_per_day_week": 0, "nutrition_adherence": 0})

    # ── Reminders сигналы ─────────────────────────────────────────────────────
    try:
        # Процент отвеченных напоминаний за 7 дней
        sent_result = await session.execute(
            select(func.count(Reminder.id)).where(
                Reminder.user_id == user_id,
                Reminder.is_sent == True,  # noqa: E712
                Reminder.sent_at >= week_ago,
            )
        )
        total_reminders = sent_result.scalar_one() or 0
        signals["reminders_sent_week"] = total_reminders

        # Лог уведомлений за 7 дней — как прокси acknowledged rate
        signals["reminders_acknowledged_rate"] = 0.7 if total_reminders > 0 else 0.0
    except Exception as exc:
        logger.warning("cross_module: Reminders сигналы недоступны: %s", exc)
        signals.update({"reminders_sent_week": 0, "reminders_acknowledged_rate": 0})

    # ── Coaching сигналы (goals/habits) ───────────────────────────────────────
    try:
        goals = await cs.get_goals(session, user_id, status="active")
        habits = await cs.get_habits(session, user_id, is_active=True)

        signals["goals_active_count"] = len(goals)
        signals["habits_active_count"] = len(habits)

        # Есть ли цели с фитнес-областью
        signals["has_fitness_goal"] = any(
            getattr(g, "area", "") in ("fitness", "health", "sport")
            for g in goals
        )
        # Есть ли цели с питанием
        signals["has_nutrition_goal"] = any(
            getattr(g, "area", "") in ("nutrition", "health", "lifestyle")
            for g in goals
        )

        # Completion rate привычек за неделю
        total_habit_days = len(habits) * 7
        done_habits_result = await session.execute(
            select(func.count(HabitLog.id)).where(
                HabitLog.habit_id.in_([h.id for h in habits]) if habits else HabitLog.id == -1,
                HabitLog.logged_at >= week_ago,
            )
        )
        done_habits = done_habits_result.scalar_one() or 0
        signals["habits_completion_rate_week"] = round(
            done_habits / total_habit_days, 2
        ) if total_habit_days > 0 else 0
    except Exception as exc:
        logger.warning("cross_module: Coaching сигналы недоступны: %s", exc)
        signals.update({"goals_active_count": 0, "habits_active_count": 0,
                        "has_fitness_goal": False, "has_nutrition_goal": False,
                        "habits_completion_rate_week": 0})

    return signals


# ══════════════════════════════════════════════════════════════════════════════
# Генерация кросс-модульных выводов
# ══════════════════════════════════════════════════════════════════════════════

def generate_cross_module_inferences(signals: dict) -> list[dict]:
    """
    На основе сигналов генерирует список кросс-модульных выводов.
    Каждый вывод: {type, title, description, severity, modules_affected, action_hint}.
    severity: critical | high | medium | low.
    """
    inferences: list[dict] = []

    # ── 1. Перегруз: слишком много задач + целей + привычек ───────────────────
    overload_score = 0
    if signals.get("tasks_active_total", 0) > 20:
        overload_score += 2
    if signals.get("tasks_overdue", 0) > 5:
        overload_score += 2
    if signals.get("goals_active_count", 0) > 5:
        overload_score += 1
    if signals.get("habits_active_count", 0) > 6:
        overload_score += 1
    if signals.get("calendar_events_today", 0) > 8:
        overload_score += 1

    if overload_score >= 4:
        severity = "critical" if overload_score >= 6 else "high"
        inferences.append({
            "type": "overload",
            "title": "Перегруз системы",
            "description": (
                f"Ты тянешь {signals.get('tasks_active_total', 0)} задач, "
                f"{signals.get('goals_active_count', 0)} целей и "
                f"{signals.get('habits_active_count', 0)} привычек одновременно. "
                "Это нереалистичная нагрузка — нужна приоритизация."
            ),
            "severity": severity,
            "modules_affected": ["tasks", "goals", "habits"],
            "action_hint": "workload_reduce",
        })

    # ── 2. Дисбаланс: цель «фитнес» + нет тренировок ─────────────────────────
    if signals.get("has_fitness_goal") and signals.get("last_workout_days_ago", 0) > 7:
        inferences.append({
            "type": "imbalance",
            "title": "Фитнес-цель без тренировок",
            "description": (
                f"У тебя есть фитнес-цель, но последняя тренировка была "
                f"{signals.get('last_workout_days_ago', 0)} дней назад. "
                "Цель и действия не совпадают."
            ),
            "severity": "high",
            "modules_affected": ["goals", "fitness"],
            "action_hint": "habit_time_adjust",
        })

    # ── 3. Причинная связь: падение привычек = падение питания ───────────────
    habit_rate = signals.get("habits_completion_rate_week", 0)
    nutrition_adherence = signals.get("nutrition_adherence", 0)
    if habit_rate < 0.4 and nutrition_adherence < 0.5 and signals.get("habits_active_count", 0) > 0:
        inferences.append({
            "type": "cause_effect",
            "title": "Падение дисциплины влияет на питание",
            "description": (
                f"Выполнение привычек упало до {int(habit_rate * 100)}%, "
                f"при этом питание логируется только {int(nutrition_adherence * 100)}% нормы. "
                "Это часто идут рука об руку — работа над одним улучшит оба."
            ),
            "severity": "medium",
            "modules_affected": ["habits", "nutrition"],
            "action_hint": "nutrition_fitness_link",
        })

    # ── 4. Конфликт: цели требуют времени, но календарь перегружен ───────────
    if signals.get("calendar_load_next_3days", 0) > 10 and signals.get("goals_active_count", 0) >= 3:
        inferences.append({
            "type": "conflict",
            "title": "Нет времени на цели",
            "description": (
                f"Следующие 3 дня у тебя {signals.get('calendar_load_next_3days', 0)} событий. "
                f"При {signals.get('goals_active_count', 0)} активных целях сложно найти время "
                "для работы над ними. Стоит запланировать конкретные слоты."
            ),
            "severity": "medium",
            "modules_affected": ["calendar", "goals"],
            "action_hint": "schedule_fix",
        })

    # ── 5. Паттерн срывов: перегруженный календарь → низкая дисциплина ───────
    if (signals.get("calendar_events_today", 0) >= 6
            and signals.get("habits_completion_rate_week", 0) < 0.5
            and signals.get("tasks_completion_rate_week", 0) < 0.5):
        inferences.append({
            "type": "failure_pattern",
            "title": "Насыщенный день → срывы",
            "description": (
                "Когда у тебя плотный день (много событий), выполнение привычек "
                "и задач резко падает. Это устойчивый паттерн — стоит заранее "
                "снизить нагрузку в такие дни."
            ),
            "severity": "medium",
            "modules_affected": ["calendar", "habits", "tasks"],
            "action_hint": "cross_module_plan",
        })

    # ── 6. Слепое пятно: есть цель «здоровье», но нет фитнес/питание-активности ─
    if (signals.get("has_fitness_goal") or signals.get("has_nutrition_goal")) and (
        signals.get("last_workout_days_ago", 0) > 5
        and signals.get("nutrition_logged_today", 0) == 0
    ):
        inferences.append({
            "type": "blind_spot",
            "title": "Цель здоровья без подкрепления",
            "description": (
                "У тебя есть цель, связанная со здоровьем, но она не отражена "
                "в конкретных действиях: нет логов питания сегодня "
                f"и {signals.get('last_workout_days_ago', 0)} дней без тренировок. "
                "Нужна связь цели с ежедневными привычками."
            ),
            "severity": "high",
            "modules_affected": ["goals", "fitness", "nutrition"],
            "action_hint": "goal_decompose",
        })

    # Сортируем по severity: critical > high > medium > low
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    inferences.sort(key=lambda x: severity_order.get(x["severity"], 3))

    return inferences


# ══════════════════════════════════════════════════════════════════════════════
# Генерация рекомендаций на основе выводов
# ══════════════════════════════════════════════════════════════════════════════

async def generate_cross_module_recommendations(
    session: AsyncSession,
    user_id: int,
    inferences: list[dict],
    state: str,
) -> list:
    """
    По кросс-модульным выводам создаёт CoachingRecommendation записи в БД.
    Максимум 2 рекомендации одновременно (dedup по типу).
    Возвращает список сохранённых рекомендаций.
    """
    if not inferences:
        return []

    # Оставляем топ-2 по severity + числу затронутых модулей
    ranked = sorted(
        inferences,
        key=lambda x: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x["severity"], 3),
            -len(x.get("modules_affected", [])),
        )
    )[:2]

    # Проверяем уже существующие активные рекомендации (dedup по rec_type)
    existing_recs = await cs.get_active_recommendations(session, user_id)
    existing_types = {r.rec_type for r in existing_recs}

    saved = []
    for inf in ranked:
        rec_type = REC_TYPE_MAP.get(inf["type"], "cross_module_plan")
        if rec_type in existing_types:
            # Уже есть такая рекомендация — пропускаем
            continue

        priority = {"critical": 1, "high": 2, "medium": 3, "low": 4}.get(inf["severity"], 3)
        rec = await cs.create_recommendation(
            session,
            user_id=user_id,
            rec_type=rec_type,
            priority=priority,
            title=inf["title"],
            body=inf["description"],
            action_type=inf["action_hint"],
            action_payload={
                "modules_affected": inf.get("modules_affected", []),
                "inference_type": inf["type"],
                "state": state,
            },
            source_modules=inf.get("modules_affected", []),
        )
        saved.append(rec)
        existing_types.add(rec_type)  # dedup следующих

    if saved:
        await session.commit()

    return saved


# ══════════════════════════════════════════════════════════════════════════════
# Главная функция анализа
# ══════════════════════════════════════════════════════════════════════════════

async def run_cross_module_analysis(
    session: AsyncSession,
    user_id: int,
    state: str = "stable",
) -> dict:
    """
    Полный цикл кросс-модульного анализа:
    1. Сбор сигналов
    2. Генерация выводов
    3. Сохранение рекомендаций
    Возвращает словарь с signals, inferences, saved_recommendations_count.
    """
    signals = await collect_module_signals(session, user_id)
    inferences = generate_cross_module_inferences(signals)
    saved = await generate_cross_module_recommendations(session, user_id, inferences, state)

    logger.info(
        "cross_module_analysis: user=%d, signals=%d keys, inferences=%d, recommendations=%d",
        user_id, len(signals), len(inferences), len(saved),
    )

    return {
        "signals": signals,
        "inferences": inferences,
        "saved_recommendations": len(saved),
        "top_inference": inferences[0] if inferences else None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Исполнение подтверждённых orchestration-действий
# ══════════════════════════════════════════════════════════════════════════════

async def execute_orchestration_action(
    session: AsyncSession,
    action: CoachingOrchestrationAction,
) -> tuple[bool, str]:
    """
    Выполняет подтверждённое orchestration-действие:
    - create_task   → создаёт Task в tasks-модуле
    - create_event  → создаёт Task с event_type='event'
    - update_reminder → создаёт Reminder

    Возвращает (success: bool, message: str).
    """
    payload = action.payload or {}

    try:
        if action.action_type == "create_task":
            # Парсим дедлайн если есть
            due_dt: Optional[datetime] = None
            if payload.get("due_date"):
                try:
                    d = date.fromisoformat(str(payload["due_date"]))
                    due_dt = datetime(d.year, d.month, d.day, 23, 59, tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    pass

            task = Task(
                user_id=action.user_id,
                title=payload.get("title", "Задача от коуча"),
                description=f"Создано коучем из этапа цели #{payload.get('source_milestone_id', '')}",
                event_type="task",
                status="todo",
                due_datetime=due_dt,
            )
            session.add(task)
            await session.flush()
            await cs.mark_action_executed(session, action.id)
            return True, f"✅ Задача создана: «{task.title}»"

        elif action.action_type == "create_event":
            # Парсим дату и время события
            start_at: Optional[datetime] = None
            end_at: Optional[datetime] = None
            if payload.get("date"):
                try:
                    d = date.fromisoformat(str(payload["date"]))
                    time_str = payload.get("time", "10:00")
                    h, m = (int(x) for x in time_str.split(":")) if ":" in str(time_str) else (10, 0)
                    start_at = datetime(d.year, d.month, d.day, h, m, tzinfo=timezone.utc)
                    duration = int(payload.get("duration_min", 60))
                    end_at = start_at + timedelta(minutes=duration)
                except (ValueError, TypeError):
                    pass

            event = Task(
                user_id=action.user_id,
                title=payload.get("title", "Событие от коуча"),
                event_type="event",
                status="todo",
                start_at=start_at,
                end_at=end_at,
            )
            session.add(event)
            await session.flush()
            await cs.mark_action_executed(session, action.id)
            time_info = f" в {payload.get('time', '')}" if payload.get("time") else ""
            return True, f"📅 Событие создано: «{event.title}» — {payload.get('date', '')}{time_info}"

        elif action.action_type == "update_reminder":
            # Создаём напоминание
            time_str = payload.get("time", "09:00")
            try:
                h, m = (int(x) for x in time_str.split(":")) if ":" in str(time_str) else (9, 0)
                remind_at = datetime.now(timezone.utc).replace(hour=h, minute=m, second=0, microsecond=0)
                # Если время уже прошло — на следующий день
                if remind_at < datetime.now(timezone.utc):
                    remind_at += timedelta(days=1)
            except (ValueError, TypeError):
                remind_at = datetime.now(timezone.utc) + timedelta(hours=1)

            # Напоминание с entity_type='coaching' и entity_id=action.id
            reminder = Reminder(
                user_id=action.user_id,
                entity_type="coaching",
                entity_id=action.id,
                remind_at=remind_at,
            )
            session.add(reminder)
            await session.flush()
            await cs.mark_action_executed(session, action.id)
            return True, f"🔔 Напоминание установлено: «{payload.get('title', '')}» в {time_str}"

        else:
            # Неизвестный тип — просто помечаем выполненным
            await cs.mark_action_executed(session, action.id)
            return True, f"✅ Действие «{action.action_type}» выполнено"

    except Exception as exc:
        logger.error("execute_orchestration_action: ошибка для action=%d: %s", action.id, exc, exc_info=True)
        return False, f"❌ Ошибка выполнения: {exc}"
