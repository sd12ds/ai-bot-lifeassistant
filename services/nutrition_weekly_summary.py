"""
Weekly Nutrition Summary — LLM-powered недельный обзор.

Собирает данные за 7 дней и генерирует краткий отчёт с рекомендациями
через gpt-4o-mini.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any

from openai import AsyncOpenAI

from config import OPENAI_API_KEY
from db import nutrition_storage as ns
from services.nutrition_score import calculate_daily_score

logger = logging.getLogger(__name__)

# LLM-клиент для генерации обзора
_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
_MODEL = "gpt-4o-mini"

# Промпт для LLM — генерация недельного обзора
_SYSTEM_PROMPT = """Ты — нутрициолог-ассистент. На основе данных за неделю напиши краткий обзор на русском языке.

ФОРМАТ ОТВЕТА:
1. Общая оценка (1-2 предложения)
2. Что хорошо (1-2 пункта)
3. Что улучшить (1-2 пункта)
4. Конкретный совет на следующую неделю (1 пункт)

ПРАВИЛА:
- Пиши кратко, по делу, без воды
- Используй emoji для структуры
- Если данных мало (< 3 дней) — укажи это
- Не повторяй цифры — делай выводы
- Максимум 150 слов
"""


async def generate_weekly_summary(
    user_id: int,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Генерирует недельный обзор питания.

    Returns:
        dict: text (str), days_with_data (int), avg_score (int), period (str)
    """
    if end_date is None:
        end_date = date.today()

    start_date = end_date - timedelta(days=6)

    # Собираем данные за 7 дней
    daily_data = []
    scores = []
    days_with_data = 0

    for i in range(7):
        d = start_date + timedelta(days=i)
        summary = await ns.get_nutrition_summary(user_id, d)
        score_result = await calculate_daily_score(user_id, d)

        meals = summary.get("meals", [])
        totals = summary.get("totals", {})
        goals = summary.get("goals") or {}

        if meals:
            days_with_data += 1
            scores.append(score_result["total"])

        daily_data.append({
            "date": str(d),
            "score": score_result["total"],
            "meals_count": len(meals),
            "calories": int(totals.get("calories", 0)),
            "protein_g": int(totals.get("protein_g", 0)),
            "fat_g": int(totals.get("fat_g", 0)),
            "carbs_g": int(totals.get("carbs_g", 0)),
            "water_ml": summary.get("water_ml", 0),
            "cal_goal": int(goals.get("calories", 0)),
            "protein_goal": int(goals.get("protein_g", 0)),
        })

    avg_score = int(sum(scores) / len(scores)) if scores else 0
    period = f"{start_date} — {end_date}"

    # Если совсем нет данных — не тратим LLM
    if days_with_data == 0:
        return {
            "text": "📊 За последнюю неделю нет записей о питании. Начни логировать приёмы пищи!",
            "days_with_data": 0,
            "avg_score": 0,
            "period": period,
        }

    # Формируем запрос к LLM
    user_msg = (
        f"Данные за неделю ({period}), дней с записями: {days_with_data}/7, "
        f"средний score: {avg_score}/100.\n\n"
        f"Подневная статистика:\n{json.dumps(daily_data, ensure_ascii=False, indent=2)}"
    )

    try:
        response = await _client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
            max_tokens=400,
        )
        text = response.choices[0].message.content or "Не удалось сгенерировать обзор"
    except Exception as e:
        logger.error("Ошибка генерации weekly summary: %s", e)
        text = f"⚠️ Не удалось сгенерировать обзор: {e}"

    # Добавляем заголовок
    header = f"📊 **Итоги за неделю** ({period})\n🎯 Средний score: {avg_score}/100\n📅 Дней с данными: {days_with_data}/7\n\n"
    full_text = header + text

    return {
        "text": full_text,
        "days_with_data": days_with_data,
        "avg_score": avg_score,
        "period": period,
    }
