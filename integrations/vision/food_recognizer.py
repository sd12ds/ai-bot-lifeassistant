"""
Распознавание еды на фото через GPT-4o Vision API.
Отправляет base64-картинку + промпт → получает структурированный JSON
с продуктами, граммовкой и КБЖУ.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime
from typing import Any

from openai import AsyncOpenAI

from config import OPENAI_API_KEY, DEFAULT_TZ

logger = logging.getLogger(__name__)

# Клиент OpenAI (async)
_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Модели для распознавания (основная + fallback)
_PRIMARY_MODEL = "gpt-4o"
_FALLBACK_MODEL = "gpt-4o-mini"

# Системный промпт для анализа фото еды
_VISION_SYSTEM_PROMPT = """Ты — эксперт-диетолог и нутрициолог. Проанализируй фото еды и определи:
1. Все продукты/блюда на фото
2. Оцени вес каждого продукта в граммах (визуально)
3. Рассчитай КБЖУ для оценённого веса
4. Определи тип приёма пищи по текущему времени

ПРАВИЛА:
- Будь реалистичен в оценке веса (используй размер тарелки как ориентир)
- Если блюдо составное (суп, салат) — разложи на основные ингредиенты
- Калории, белки, жиры, углеводы — на ФАКТИЧЕСКИЙ вес порции, не на 100г
- Названия продуктов — на русском языке

Ответь СТРОГО в JSON формате (без markdown, без ```):
{
  "meal_type": "breakfast|lunch|dinner|snack",
  "items": [
    {
      "name": "Название продукта",
      "amount_g": 150,
      "calories": 165,
      "protein_g": 31.0,
      "fat_g": 3.6,
      "carbs_g": 0.0
    }
  ],
  "total": {
    "calories": 425,
    "protein_g": 36.4,
    "fat_g": 4.2,
    "carbs_g": 57.0
  }
}"""


def _guess_meal_type() -> str:
    """Определяет тип приёма пищи по текущему времени."""
    hour = datetime.now(DEFAULT_TZ).hour
    if 5 <= hour < 11:
        return "breakfast"
    elif 11 <= hour < 15:
        return "lunch"
    elif 15 <= hour < 18:
        return "snack"
    else:
        return "dinner"


def _extract_json(text: str) -> str:
    """Извлекает JSON из текста, убирая markdown-обёртки и мусор.

    Обрабатывает случаи:
    - Чистый JSON
    - ```json ... ```
    - ``` ... ```
    - Текст до/после JSON
    """
    stripped = text.strip()

    # Убираем markdown code-block обёртки
    # Паттерн: ```json\n{...}\n``` или ```\n{...}\n```
    md_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', stripped, re.DOTALL)
    if md_match:
        stripped = md_match.group(1).strip()

    # Ищем JSON-объект по фигурным скобкам (может быть мусор до/после)
    brace_match = re.search(r'\{.*\}', stripped, re.DOTALL)
    if brace_match:
        return brace_match.group(0)

    return stripped


async def _call_vision(
    model: str,
    photo_base64: str,
    time_hint: str,
    caption: str | None = None,
) -> dict[str, Any]:
    """Вызов Vision API с указанной моделью.

    Args:
        model: название модели OpenAI
        photo_base64: base64-строка изображения
        time_hint: подсказка с текущим временем и типом приёма пищи
        caption: подпись пользователя к фото (если есть)
    """
    # Базовый текст запроса
    user_text = "Проанализируй эту еду. Определи продукты, вес и КБЖУ."

    # Если пользователь добавил подпись — включаем её в запрос
    if caption:
        user_text += (
            f"\n\nПользователь описал: «{caption}»\n"
            "Учти эту информацию: если указаны продукты или граммовка — "
            "они имеют ПРИОРИТЕТ над визуальной оценкой."
        )

    response = await _client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": _VISION_SYSTEM_PROMPT + time_hint,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_text,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{photo_base64}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ],
        max_tokens=1500,
        temperature=0.2,
    )
    return response


async def recognize_food_photo(
    photo_base64: str,
    caption: str | None = None,
) -> dict[str, Any]:
    """
    Анализирует фото еды через GPT-4o Vision.

    Args:
        photo_base64: base64-строка изображения (без префикса data:image/...)
        caption: подпись пользователя к фото (если есть) —
                 используется для уточнения продуктов и граммовки

    Returns:
        dict с ключами: meal_type, items, total
        В случае ошибки: {"error": "описание"}
    """
    # Текущее время для определения типа приёма пищи
    now = datetime.now(DEFAULT_TZ)
    time_hint = f"\nСейчас {now.strftime('%H:%M')} ({_guess_meal_type()})."

    if caption:
        logger.info("Vision: распознаём фото с подписью: «%s»", caption[:100])

    # Пробуем основную модель, при ошибке или отказе — fallback
    raw_text = None
    for model in [_PRIMARY_MODEL, _FALLBACK_MODEL]:
        try:
            response = await _call_vision(model, photo_base64, time_hint, caption)
            content = response.choices[0].message.content
            # Проверяем наличие поля refusal (OpenAI API)
            refusal = getattr(response.choices[0].message, "refusal", None)
            if refusal:
                logger.warning("Vision API (%s) отказ (refusal): %s", model, refusal)
                continue  # Пробуем следующую модель

            if not content:
                logger.warning("Vision API (%s) пустой ответ", model)
                continue  # Пробуем следующую модель

            text = content.strip()
            logger.info("Vision API (%s) ответ: %s", model, text[:300])

            # Проверяем что ответ содержит JSON (фигурные скобки), а не отказ
            if "{" not in text:
                logger.warning("Vision API (%s) вернул не-JSON (вероятно отказ): %s", model, text[:200])
                continue  # Пробуем следующую модель

            raw_text = text
            break  # Успешно — выходим из цикла
        except Exception as e:
            logger.warning("Vision API (%s) ошибка: %s", model, e)
            continue  # Пробуем следующую модель

    if not raw_text:
        return {"error": "Не удалось распознать еду на фото. Убедитесь, что на фото видна еда, и попробуйте ещё раз."}

    # Парсим JSON (с устойчивостью к markdown-обёрткам)
    try:
        json_text = _extract_json(raw_text)
        result = json.loads(json_text)
    except json.JSONDecodeError as e:
        logger.error("Ошибка парсинга JSON от Vision API: %s\nRaw: %s", e, raw_text[:500])
        return {"error": f"Не удалось распарсить ответ AI: {e}"}

    # Валидируем структуру
    if "items" not in result or not isinstance(result["items"], list):
        return {"error": "AI вернул некорректный формат", "raw": raw_text}

    # Пересчитываем total если отсутствует
    if "total" not in result:
        result["total"] = {
            "calories": round(sum(i.get("calories", 0) for i in result["items"]), 1),
            "protein_g": round(sum(i.get("protein_g", 0) for i in result["items"]), 1),
            "fat_g": round(sum(i.get("fat_g", 0) for i in result["items"]), 1),
            "carbs_g": round(sum(i.get("carbs_g", 0) for i in result["items"]), 1),
        }

    # Подставляем meal_type если отсутствует
    if "meal_type" not in result:
        result["meal_type"] = _guess_meal_type()

    return result


async def recognize_food_from_file(
    file_path: str,
    caption: str | None = None,
) -> dict[str, Any]:
    """Удобная обёртка: читает файл, конвертирует в base64 и распознаёт.

    Args:
        file_path: путь к файлу изображения
        caption: подпись пользователя (если есть)
    """
    with open(file_path, "rb") as f:
        photo_bytes = f.read()
    photo_b64 = base64.b64encode(photo_bytes).decode("utf-8")
    return await recognize_food_photo(photo_b64, caption=caption)
