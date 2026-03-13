"""
Follow-up Suggestions — подсказки после сохранения приёма пищи.

Генерирует 1-2 коротких совета на основе текущего прогресса за день.
Правила (rule-based, без LLM):
- Остаток белка ниже нормы
- Мало воды
- Калории на исходе / с запасом
- Поздний старт (первый приём после 12:00)
"""
from __future__ import annotations

import logging
from datetime import date, time
from typing import Any

from db import nutrition_storage as ns

logger = logging.getLogger(__name__)

# Максимум подсказок за раз
_MAX_TIPS = 2


async def generate_followup(
    user_id: int,
    target_date: date | None = None,
) -> list[str]:
    """
    Возвращает список строк-подсказок (0-2 шт.) после сохранения приёма.
    """
    if target_date is None:
        target_date = date.today()

    summary = await ns.get_nutrition_summary(user_id, target_date)
    goals = summary.get("goals") or {}
    totals = summary.get("totals", {})
    water_ml = summary.get("water_ml", 0)
    meals = summary.get("meals", [])

    # Если нет целей — нечего советовать
    if not goals or not goals.get("calories"):
        return []

    tips: list[str] = []

    # 1. Остаток белка
    protein_eaten = totals.get("protein_g", 0)
    protein_goal = goals.get("protein_g", 0)
    if protein_goal > 0:
        protein_left = protein_goal - protein_eaten
        protein_pct = protein_eaten / protein_goal
        if protein_pct < 0.5 and len(meals) >= 2:
            # Съедено меньше половины белка при >= 2 приёмах
            tips.append(f"🥩 Белка осталось набрать {int(protein_left)}г — добавь белковый продукт в следующий приём")
        elif protein_pct < 0.75 and len(meals) >= 3:
            tips.append(f"🥩 До нормы белка ещё {int(protein_left)}г — творог, яйца или курица помогут")

    # 2. Мало воды
    water_goal = goals.get("water_ml", 0)
    if water_goal > 0:
        water_pct = water_ml / water_goal
        if water_pct < 0.3 and len(meals) >= 2:
            tips.append(f"💧 Выпито всего {water_ml} мл из {water_goal} — не забывай пить воду")
        elif water_pct < 0.5 and len(meals) >= 3:
            tips.append(f"💧 Воды меньше половины нормы ({water_ml}/{water_goal} мл)")

    # 3. Калории — перебор или запас
    cal_eaten = totals.get("calories", 0)
    cal_goal = goals.get("calories", 0)
    if cal_goal > 0:
        cal_left = cal_goal - cal_eaten
        cal_pct = cal_eaten / cal_goal
        if cal_pct > 1.1:
            # Перебор
            over = int(cal_eaten - cal_goal)
            tips.append(f"⚠️ Калории превышены на {over} ккал — на оставшиеся приёмы выбирай лёгкие продукты")
        elif 0.85 <= cal_pct <= 1.0 and len(meals) < 3:
            # Почти норма, но ещё не все приёмы — осторожнее
            tips.append(f"🔥 Осталось всего {int(cal_left)} ккал — планируй лёгкий следующий приём")

    # 4. Поздний старт
    if len(meals) == 1 and meals[0].get("eaten_at"):
        eaten_at = meals[0]["eaten_at"]
        try:
            from datetime import datetime
            if isinstance(eaten_at, str):
                t = datetime.fromisoformat(eaten_at)
            else:
                t = eaten_at
            if t.hour >= 12:
                tips.append("⏰ Первый приём после 12:00 — старайся завтракать раньше для лучшего метаболизма")
        except (ValueError, AttributeError):
            pass

    # Ограничиваем количество
    return tips[:_MAX_TIPS]


def format_followup(tips: list[str]) -> str:
    """Форматирует подсказки в строку для Telegram."""
    if not tips:
        return ""
    return "\n".join(["", "💡 **Совет:**"] + tips)
