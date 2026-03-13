"""
Парсер текста программы тренировок через LLM.
Принимает произвольный текст → возвращает структурированный JSON.
"""
from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

from config import OPENAI_API_KEY, OPENAI_AGENT_MODEL

logger = logging.getLogger(__name__)

# Клиент OpenAI для парсинга
_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Системный промпт для парсинга программы тренировок
_PARSE_PROMPT = """\
Ты — парсер программы тренировок. Пользователь присылает текст с описанием программы.
Твоя задача — извлечь структурированные данные.

ПРАВИЛА:
1. Определи количество тренировочных дней
2. Для каждого дня определи:
   - day_number (1, 2, 3, ...)
   - day_name — краткое название по основным мышечным группам (например: "Ноги + трицепс", "Спина + грудь")
   - exercises — список упражнений В ТОМ ЖЕ ПОРЯДКЕ как в тексте
3. Для каждого упражнения:
   - name — полное название упражнения (как в тексте, максимально точно)
   - sets — количество подходов (если не указано → 3)
   - reps — количество повторений (если не указано → 12 для верха, 10 для ног, 15 для пресса)
   - muscle_group — основная мышечная группа (legs, back, chest, shoulders, biceps, triceps, core, glutes, forearms)
   - equipment — оборудование (штанга, гантели, тренажёр, кроссовер, гравитрон, смит, без оборудования)
4. Для программы определи:
   - name — название программы (краткое, по сплиту)
   - goal_type — цель (gain_muscle, lose_fat, strength, general)

ВЕРНИ ТОЛЬКО JSON без markdown-обёртки:
{
  "name": "...",
  "goal_type": "...",
  "days": [
    {
      "day_number": 1,
      "day_name": "...",
      "exercises": [
        {"name": "...", "sets": 3, "reps": 12, "muscle_group": "...", "equipment": "..."},
        ...
      ]
    },
    ...
  ]
}
"""


async def parse_program_text(text: str) -> dict:
    """
    Парсит текст программы тренировок через LLM.
    Возвращает структурированный dict с днями и упражнениями.
    Raises ValueError при ошибке парсинга.
    """
    logger.info("Парсинг программы тренировок, длина текста: %d", len(text))

    response = await _client.chat.completions.create(
        model=OPENAI_AGENT_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": _PARSE_PROMPT},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("Ошибка парсинга JSON от LLM: %s\nRaw: %s", e, raw[:500])
        raise ValueError(f"LLM вернул невалидный JSON: {e}")

    # Валидация структуры
    if "days" not in data or not isinstance(data["days"], list):
        raise ValueError("LLM не вернул массив days")

    for day in data["days"]:
        if "exercises" not in day or not isinstance(day["exercises"], list):
            raise ValueError(f"День {day.get('day_number', '?')} не содержит exercises")
        if len(day["exercises"]) == 0:
            raise ValueError(f"День {day.get('day_number', '?')} содержит 0 упражнений")

    total_exercises = sum(len(d["exercises"]) for d in data["days"])
    logger.info(
        "Программа распознана: %s, %d дней, %d упражнений",
        data.get("name", "?"), len(data["days"]), total_exercises,
    )

    return data
