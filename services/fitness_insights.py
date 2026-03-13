"""
Сервис аналитики и советов для фитнес-модуля.

Связка с питанием, определение перетренированности, плато,
еженедельная сводка. По аналогии с nutrition_insights.py.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from db import fitness_storage as fs
from db import nutrition_storage as ns

logger = logging.getLogger(__name__)


async def post_workout_tips(user_id: int, session_data: dict) -> list[str]:
    """
    Советы после завершения тренировки.
    Связка с питанием: остаток белка, калорий.
    """
    tips: list[str] = []

    try:
        # Получаем данные о питании за сегодня
        nutrition = await ns.get_nutrition_summary(user_id, date.today())
        goals = nutrition.get("goals")
        totals = nutrition.get("totals", {})

        # Сожжённые калории за тренировку (оценка)
        calories_burned = session_data.get("calories_burned") or 0
        volume = session_data.get("total_volume_kg") or 0

        if goals:
            # Остаток белка
            protein_eaten = totals.get("protein_g", 0)
            protein_goal = goals.get("protein_g", 120)
            protein_left = protein_goal - protein_eaten
            if protein_left > 20:
                tips.append(
                    f"🥩 Тебе нужно ещё {round(protein_left)}г белка сегодня "
                    f"({round(protein_eaten)}/{protein_goal}г)"
                )

            # Остаток калорий (с учётом сожжённых)
            cal_eaten = totals.get("calories", 0)
            cal_goal = goals.get("calories", 2000)
            # Добавляем сожжённые к бюджету
            effective_budget = cal_goal + calories_burned - cal_eaten
            if effective_budget > 300:
                tips.append(
                    f"🔥 Можешь съесть ещё ~{round(effective_budget)} ккал "
                    f"(+{round(calories_burned)} сожжено на тренировке)"
                )
        else:
            # Нет целей по питанию — общий совет
            if volume > 0:
                # Рекомендуем белок по объёму тренировки
                suggested_protein = round(volume * 0.003 + 25)  # грубая оценка
                tips.append(
                    f"💪 Хорошая тренировка! Не забудь съесть {suggested_protein}г белка для восстановления"
                )

        # Совет по воде
        water = nutrition.get("water_ml", 0)
        if water < 1500:
            tips.append("💧 Не забудь попить воды — после тренировки это особенно важно")

    except Exception as e:
        logger.warning(f"Ошибка получения nutrition данных для tips: {e}")
        # Общий совет без привязки к питанию
        tips.append("💪 Отличная тренировка! Не забудь про белок и воду для восстановления")

    return tips


async def weekly_fitness_summary(user_id: int) -> dict:
    """
    Еженедельная фитнес-сводка.
    Тренировки/цель, объём, рекорды, streak, сравнение с прошлой неделей.
    """
    # Текущая неделя
    stats = await fs.get_workout_stats(user_id, days=7)
    # Прошлая неделя — сравнение
    stats_prev = await fs.get_workout_stats(user_id, days=14)

    # Фитнес-цель
    goal = await fs.get_fitness_goal(user_id)
    workouts_goal = goal.get("workouts_per_week", 3) if goal else 3

    # Рекорды за неделю
    records = await fs.get_personal_records(user_id)
    # Фильтруем рекорды за последнюю неделю
    week_ago = date.today() - timedelta(days=7)
    recent_records = [
        r for r in records
        if r.get("achieved_at") and r["achieved_at"][:10] >= str(week_ago)
    ]

    # Подсчёт изменений
    current_sessions = stats.get("total_sessions", 0)
    # Из stats за 14 дней вычитаем текущую неделю
    prev_sessions = stats_prev.get("total_sessions", 0) - current_sessions
    current_volume = stats.get("total_volume_kg", 0)
    prev_volume = stats_prev.get("total_volume_kg", 0) - current_volume

    return {
        "sessions": current_sessions,
        "sessions_goal": workouts_goal,
        "sessions_prev": prev_sessions,
        "volume_kg": round(current_volume),
        "volume_prev_kg": round(prev_volume),
        "volume_change_pct": round((current_volume - prev_volume) / prev_volume * 100) if prev_volume > 0 else 0,
        "time_min": round(stats.get("total_time_min", 0)),
        "calories": round(stats.get("total_calories", 0)),
        "streak": stats.get("current_streak_days", 0),
        "new_records": len(recent_records),
        "records": recent_records[:5],
        "top_exercises": stats.get("top_exercises", [])[:3],
    }


async def check_overtraining(user_id: int) -> str | None:
    """
    Проверка на перетренированность.
    >6 тренировок за неделю → предупреждение.
    """
    stats = await fs.get_workout_stats(user_id, days=7)
    sessions = stats.get("total_sessions", 0)

    if sessions >= 7:
        return (
            "⚠️ Ты тренировался каждый день на этой неделе! "
            "Отдых важен для восстановления и роста мышц. "
            "Запланируй хотя бы 1 день отдыха."
        )
    elif sessions >= 6:
        return (
            "💡 6 тренировок на этой неделе — отлично, но не забывай про отдых. "
            "Мышцы растут во время восстановления."
        )
    return None


async def detect_plateau(user_id: int, exercise_id: int) -> str | None:
    """
    Обнаружение плато — вес по упражнению не растёт 3+ недели.
    """
    progress = await fs.get_exercise_progress(user_id, exercise_id, days=28)

    if len(progress) < 3:
        return None  # недостаточно данных

    # Берём максимальные веса за последние тренировки
    weights = [p["max_weight"] for p in progress if p["max_weight"] > 0]
    if len(weights) < 3:
        return None

    # Проверяем: если последние 3 тренировки — вес одинаковый или снижается
    recent = weights[-3:]
    if recent[-1] <= recent[0] and all(w == recent[0] for w in recent):
        return (
            f"📊 Похоже на плато: рабочий вес {recent[0]} кг не менялся "
            f"последние {len(recent)} тренировки. "
            "Попробуй: изменить кол-во повторов, добавить дроп-сеты, "
            "сменить вариацию упражнения или увеличить калорийность."
        )

    return None
