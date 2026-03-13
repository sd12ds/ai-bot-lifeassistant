"""
Сервис контекстных советов по питанию.

Анализирует дневные/недельные данные и генерирует короткие рекомендации.
Данные берутся из nutrition_storage — новых таблиц не требуется.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from db import nutrition_storage as ns

logger = logging.getLogger(__name__)


async def generate_daily_tips(user_id: int, current_hour: int = 14) -> list[str]:
    """
    Советы на текущий момент дня.

    Логика:
      - Если калории < 30% цели после 14:00 → «Ты почти ничего не ел сегодня»
      - Если белок < 50% цели после 18:00 → «Сегодня мало белка»
      - Если жиры > 85% цели → «Держи жиры пониже остаток дня»
      - Если вода < 50% цели после 16:00 → «Не забудь попить воды»

    Возвращает список строк (1–3 совета, максимум).
    """
    tips: list[str] = []

    # Получаем сводку за сегодня и цели
    summary = await ns.get_nutrition_summary(user_id, date.today())
    goals = summary.get("goals")
    totals = summary.get("totals", {})
    water_ml = summary.get("water_ml", 0)

    # Если целей нет — не можем анализировать
    if not goals:
        return tips

    # Если нет приёмов пищи — специальное сообщение
    if not summary.get("meals") and current_hour >= 12:
        tips.append("📝 Ты ещё ничего не записал сегодня — не забудь логировать приёмы пищи")
        return tips

    goal_cal = goals.get("calories") or 2000
    goal_prot = goals.get("protein_g") or 120
    goal_fat = goals.get("fat_g") or 65
    goal_water = goals.get("water_ml") or 2000

    eaten_cal = totals.get("calories", 0)
    eaten_prot = totals.get("protein_g", 0)
    eaten_fat = totals.get("fat_g", 0)

    # Процент выполнения
    cal_pct = eaten_cal / goal_cal if goal_cal else 1
    prot_pct = eaten_prot / goal_prot if goal_prot else 1
    fat_pct = eaten_fat / goal_fat if goal_fat else 0
    water_pct = water_ml / goal_water if goal_water else 1

    # Правила генерации советов (порядок — по приоритету)

    # 1. Мало калорий после обеда
    if current_hour >= 14 and cal_pct < 0.3:
        tips.append(
            f"⚡ Сегодня съедено всего {int(eaten_cal)} из {goal_cal} ккал — "
            f"не забудь нормально поесть"
        )

    # 2. Мало белка к вечеру
    if current_hour >= 18 and prot_pct < 0.5:
        remaining = goal_prot - int(eaten_prot)
        tips.append(
            f"🥩 Сегодня мало белка — осталось {remaining}г до цели. "
            f"Добавь творог или курицу на ужин"
        )

    # 3. Жиры близки к лимиту
    if fat_pct > 0.85:
        tips.append(
            f"⚠️ Жиры сегодня уже {int(fat_pct * 100)}% от нормы — "
            f"держи ужин полегче"
        )

    # 4. Мало воды
    if current_hour >= 16 and water_pct < 0.5:
        remaining = goal_water - water_ml
        tips.append(
            f"💧 Выпил только {water_ml} мл воды — "
            f"не забудь попить ещё {remaining} мл"
        )

    # 5. Всё хорошо — позитивный совет (только если нет предупреждений)
    if not tips and current_hour >= 18 and cal_pct >= 0.7 and prot_pct >= 0.7:
        tips.append("✅ Отличный день по питанию — так держать!")

    # Ограничиваем количество советов
    return tips[:3]


async def generate_weekly_tips(user_id: int) -> list[str]:
    """
    Советы по недельной статистике.

    Логика:
      - Средний дефицит/профицит за 7 дней
      - Стрик выполнения целей
      - Самый слабый макронутриент за неделю

    Возвращает список строк (1–3 совета).
    """
    tips: list[str] = []
    goals = await ns.get_goals(user_id)
    if not goals:
        return tips

    goal_cal = goals.get("calories") or 2000
    goal_prot = goals.get("protein_g") or 120
    goal_fat = goals.get("fat_g") or 65
    goal_carbs = goals.get("carbs_g") or 250
    goal_type = goals.get("goal_type", "maintain")

    # Собираем данные за 7 дней
    today = date.today()
    daily_data: list[dict] = []
    for i in range(7):
        d = today - timedelta(days=i)
        summary = await ns.get_nutrition_summary(user_id, d)
        daily_data.append(summary)

    # Дни с логами (хотя бы один приём пищи)
    active_days = [d for d in daily_data if d.get("meals")]
    if not active_days:
        return tips

    days_count = len(active_days)

    # Средние значения
    avg_cal = sum(d["totals"]["calories"] for d in active_days) / days_count
    avg_prot = sum(d["totals"]["protein_g"] for d in active_days) / days_count
    avg_fat = sum(d["totals"]["fat_g"] for d in active_days) / days_count

    # 1. Средний дефицит/профицит
    diff = avg_cal - goal_cal
    if goal_type == "lose" and diff < 0:
        tips.append(
            f"🔥 За 7 дней средний дефицит {abs(int(diff))} ккал — "
            f"отличный темп для похудения!"
        )
    elif goal_type == "gain" and diff > 0:
        tips.append(
            f"💪 За 7 дней средний профицит {int(diff)} ккал — "
            f"хороший набор!"
        )
    elif abs(diff) > 300:
        direction = "выше" if diff > 0 else "ниже"
        tips.append(
            f"📊 Среднее потребление за неделю: {int(avg_cal)} ккал "
            f"({direction} цели на {abs(int(diff))} ккал)"
        )

    # 2. Стрик — дни подряд в цели по калориям (±10%)
    streak = 0
    for d in daily_data:
        if not d.get("meals"):
            break
        cal = d["totals"]["calories"]
        if abs(cal - goal_cal) / goal_cal <= 0.10:
            streak += 1
        else:
            break
    if streak >= 3:
        tips.append(f"🏆 {streak} дней подряд в цели по калориям — так держать!")

    # 3. Самый слабый макронутриент
    prot_pct = avg_prot / goal_prot if goal_prot else 1
    fat_pct = avg_fat / goal_fat if goal_fat else 1
    weakest = min(
        [("белок", prot_pct, "творог, курицу, яйца"),
         ("жиры", fat_pct, "орехи, авокадо, рыбу")],
        key=lambda x: x[1],
    )
    if weakest[1] < 0.7:
        tips.append(
            f"📉 За неделю в среднем мало {weakest[0]} ({int(weakest[1]*100)}% от нормы). "
            f"Попробуй добавить {weakest[2]}"
        )

    return tips[:3]


async def generate_evening_summary(user_id: int) -> Optional[str]:
    """
    Формирует итоговое сообщение за день (для вечерней отправки).

    Формат:
    📊 Итоги дня
    ✅ Калории: 1820 / 2000 — отлично
    ⚠️ Белок: 75 / 120г — добавь на ужин творог
    💧 Вода: 1200 / 2000 мл
    """
    summary = await ns.get_nutrition_summary(user_id, date.today())
    goals = summary.get("goals")
    totals = summary.get("totals", {})
    water_ml = summary.get("water_ml", 0)

    # Если нет целей или нет приёмов — не отправляем
    if not goals or not summary.get("meals"):
        return None

    goal_cal = goals.get("calories") or 2000
    goal_prot = goals.get("protein_g") or 120
    goal_fat = goals.get("fat_g") or 65
    goal_carbs = goals.get("carbs_g") or 250
    goal_water = goals.get("water_ml") or 2000

    eaten_cal = totals.get("calories", 0)
    eaten_prot = totals.get("protein_g", 0)
    eaten_fat = totals.get("fat_g", 0)
    eaten_carbs = totals.get("carbs_g", 0)

    lines = ["📊 Итоги дня"]

    # Вспомогательная функция для статуса
    def _status(eaten: float, goal: float) -> str:
        pct = eaten / goal if goal else 0
        if pct >= 0.9 and pct <= 1.1:
            return "✅"      # в норме
        elif pct < 0.7:
            return "⚠️"     # мало
        elif pct > 1.15:
            return "🔴"     # перебор
        return "👌"          # близко к цели

    lines.append(f"{_status(eaten_cal, goal_cal)} Калории: {int(eaten_cal)} / {goal_cal} ккал")
    lines.append(f"{_status(eaten_prot, goal_prot)} Белок: {int(eaten_prot)} / {goal_prot}г")
    lines.append(f"{_status(eaten_fat, goal_fat)} Жиры: {int(eaten_fat)} / {goal_fat}г")
    lines.append(f"{_status(eaten_carbs, goal_carbs)} Углеводы: {int(eaten_carbs)} / {goal_carbs}г")
    lines.append(f"{_status(water_ml, goal_water)} Вода: {water_ml} / {goal_water} мл")

    return "\n".join(lines)
