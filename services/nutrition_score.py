"""
Daily Nutrition Score — оценка дня по питанию (0–100).

6 компонентов с весами:
1. Калории (25%) — попадание в ±10% от цели
2. Белок (25%) — >= 90% цели
3. Баланс БЖУ (15%) — жиры и углеводы в пределах цели
4. Вода (15%) — >= 80% цели
5. Регулярность (10%) — количество приёмов пищи
6. Тайминг (10%) — правильное время приёмов
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from config import DEFAULT_TZ
from db import nutrition_storage as ns

logger = logging.getLogger(__name__)

# Веса компонентов score
_WEIGHTS = {
    "calories": 0.25,
    "protein": 0.25,
    "balance": 0.15,
    "water": 0.15,
    "regularity": 0.10,
    "timing": 0.10,
}


def _score_calories(eaten: float, goal: float) -> tuple[int, str]:
    """Оценка по калориям: ±10% от цели = 100, дальше линейное снижение."""
    if goal <= 0:
        return 50, "цель не задана"
    ratio = eaten / goal
    # Идеальный диапазон: 0.9 - 1.1
    if 0.9 <= ratio <= 1.1:
        score = 100
    elif ratio < 0.9:
        # Недобор: 0.5 → 50, 0.0 → 0
        score = max(0, int(ratio / 0.9 * 100))
    else:
        # Перебор: 1.2 → 80, 1.5 → 50, 2.0 → 0
        score = max(0, int((2.0 - ratio) / 0.9 * 100))
    detail = f"{int(eaten)} / {int(goal)} ккал"
    return min(score, 100), detail


def _score_protein(eaten: float, goal: float) -> tuple[int, str]:
    """Оценка по белку: >= 90% цели = 100."""
    if goal <= 0:
        return 50, "цель не задана"
    ratio = eaten / goal
    if ratio >= 0.9:
        score = 100
    else:
        # Линейное снижение: 0.5 → 56, 0.0 → 0
        score = int(ratio / 0.9 * 100)
    detail = f"{int(eaten)} / {int(goal)}г"
    return min(max(score, 0), 100), detail


def _score_balance(totals: dict, goals: dict) -> tuple[int, str]:
    """Оценка баланса БЖУ: жиры и углеводы в пределах ±20% от цели."""
    fat_goal = goals.get("fat_g") or 0
    carbs_goal = goals.get("carbs_g") or 0
    if fat_goal <= 0 and carbs_goal <= 0:
        return 50, "цели не заданы"

    scores = []
    parts = []

    # Жиры
    if fat_goal > 0:
        fat_ratio = totals.get("fat_g", 0) / fat_goal
        if 0.8 <= fat_ratio <= 1.2:
            scores.append(100)
        else:
            scores.append(max(0, int(100 - abs(fat_ratio - 1.0) * 150)))
        parts.append(f"Ж {int(totals.get('fat_g', 0))}/{int(fat_goal)}")

    # Углеводы
    if carbs_goal > 0:
        carbs_ratio = totals.get("carbs_g", 0) / carbs_goal
        if 0.8 <= carbs_ratio <= 1.2:
            scores.append(100)
        else:
            scores.append(max(0, int(100 - abs(carbs_ratio - 1.0) * 150)))
        parts.append(f"У {int(totals.get('carbs_g', 0))}/{int(carbs_goal)}")

    avg = sum(scores) // len(scores) if scores else 50
    return min(avg, 100), ", ".join(parts) or "—"


def _score_water(water_ml: int, goal_ml: int) -> tuple[int, str]:
    """Оценка по воде: >= 80% цели = 100."""
    if goal_ml <= 0:
        return 50, "цель не задана"
    ratio = water_ml / goal_ml
    if ratio >= 0.8:
        score = 100
    else:
        score = int(ratio / 0.8 * 100)
    detail = f"{water_ml} / {goal_ml} мл"
    return min(max(score, 0), 100), detail


def _score_regularity(meals: list) -> tuple[int, str]:
    """Оценка регулярности: >= 3 приёмов = 100."""
    count = len(meals)
    if count >= 3:
        score = 100
    elif count == 2:
        score = 70
    elif count == 1:
        score = 30
    else:
        score = 0
    detail = f"{count} приём(ов) пищи"
    return score, detail


def _score_timing(meals: list) -> tuple[int, str]:
    """Оценка тайминга: есть завтрак до 11, обед до 15, ужин до 21."""
    # Определяем какие типы приёмов были вовремя
    checks = 0
    passed = 0
    meal_types_seen = set()

    for m in meals:
        mt = m.get("meal_type", "")
        eaten_at = m.get("eaten_at")
        meal_types_seen.add(mt)

        if eaten_at:
            try:
                # Парсим время
                if isinstance(eaten_at, str):
                    t = datetime.fromisoformat(eaten_at)
                else:
                    t = eaten_at
                hour = t.hour
            except (ValueError, AttributeError):
                continue

            if mt == "breakfast":
                checks += 1
                if hour <= 11:
                    passed += 1
            elif mt == "lunch":
                checks += 1
                if 11 <= hour <= 15:
                    passed += 1
            elif mt == "dinner":
                checks += 1
                if 18 <= hour <= 22:
                    passed += 1

    if checks == 0:
        return 50, "мало данных"

    score = int(passed / checks * 100)
    detail = f"{passed}/{checks} вовремя"
    return min(score, 100), detail


async def calculate_daily_score(
    user_id: int,
    target_date: date | None = None,
) -> dict[str, Any]:
    """
    Считает дневной score питания 0–100.

    Returns:
        dict с ключами: total, breakdown, emoji, date
    """
    if target_date is None:
        target_date = date.today()

    # Получаем сводку за день
    summary = await ns.get_nutrition_summary(user_id, target_date)
    goals = summary.get("goals") or {}
    totals = summary.get("totals", {})
    water_ml = summary.get("water_ml", 0)
    meals = summary.get("meals", [])

    # Если нет целей — не можем нормально оценить
    if not goals or not goals.get("calories"):
        return {
            "total": 0,
            "breakdown": {},
            "emoji": "⚪",
            "date": str(target_date),
            "message": "Установи цели по КБЖУ для получения оценки",
        }

    # Считаем каждый компонент
    cal_score, cal_detail = _score_calories(totals.get("calories", 0), goals.get("calories", 0))
    prot_score, prot_detail = _score_protein(totals.get("protein_g", 0), goals.get("protein_g", 0))
    bal_score, bal_detail = _score_balance(totals, goals)
    water_score, water_detail = _score_water(water_ml, goals.get("water_ml", 0))
    reg_score, reg_detail = _score_regularity(meals)
    timing_score, timing_detail = _score_timing(meals)

    # Взвешенная сумма
    total = int(
        cal_score * _WEIGHTS["calories"]
        + prot_score * _WEIGHTS["protein"]
        + bal_score * _WEIGHTS["balance"]
        + water_score * _WEIGHTS["water"]
        + reg_score * _WEIGHTS["regularity"]
        + timing_score * _WEIGHTS["timing"]
    )

    # Эмодзи по уровню
    if total >= 80:
        emoji = "🟢"
    elif total >= 60:
        emoji = "🟡"
    else:
        emoji = "🔴"

    return {
        "total": total,
        "emoji": emoji,
        "date": str(target_date),
        "breakdown": {
            "calories": {"score": cal_score, "weight": "25%", "detail": cal_detail},
            "protein": {"score": prot_score, "weight": "25%", "detail": prot_detail},
            "balance": {"score": bal_score, "weight": "15%", "detail": bal_detail},
            "water": {"score": water_score, "weight": "15%", "detail": water_detail},
            "regularity": {"score": reg_score, "weight": "10%", "detail": reg_detail},
            "timing": {"score": timing_score, "weight": "10%", "detail": timing_detail},
        },
    }


def format_score_card(result: dict) -> str:
    """Форматирует score в читабельную карточку для Telegram."""
    if result.get("message"):
        return f"⚪ {result['message']}"

    total = result["total"]
    emoji = result["emoji"]
    bd = result["breakdown"]

    lines = [f"{emoji} Оценка за {result['date']}: **{total}/100**\n"]
    for key, label in [
        ("calories", "🔥 Калории"),
        ("protein", "🥩 Белок"),
        ("balance", "⚖️ Баланс БЖУ"),
        ("water", "💧 Вода"),
        ("regularity", "🕐 Регулярность"),
        ("timing", "⏰ Тайминг"),
    ]:
        if key in bd:
            s = bd[key]
            bar = "█" * (s["score"] // 10) + "░" * (10 - s["score"] // 10)
            lines.append(f"  {label}: {bar} {s['score']} · {s['detail']}")

    return "\n".join(lines)
