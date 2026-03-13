"""
Smart Merge Engine — слияние данных Vision API и текста пользователя.

Два основных метода:
1. merge_vision_and_caption() — объединяет результат распознавания фото с подписью
2. apply_user_correction() — применяет текстовые правки к черновику приёма пищи

Оба используют LLM (gpt-4o-mini) для понимания свободного текста.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

# LLM-клиент для merge-операций (быстрая модель)
_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
_MERGE_MODEL = "gpt-4o-mini"


# ── Промпт для слияния vision + caption ──────────────────────────────────────

_MERGE_PROMPT = """Ты получил результат распознавания фото еды (vision) и текстовую подпись пользователя (caption).
Объедини их в один список продуктов.

ПРАВИЛА ПРИОРИТЕТА:
1. Если пользователь указал граммовку текстом — она ВАЖНЕЕ, чем оценка vision
2. Если пользователь назвал продукт, которого нет в vision — добавь его (рассчитай КБЖУ сам)
3. Если vision нашёл продукт, а пользователь его не упомянул — оставь из vision
4. Если продукты совпадают по смыслу — объедини в один (merge), приоритет у пользователя
5. КБЖУ считай на ФАКТИЧЕСКИЙ вес (amount_g), НЕ на 100г

Для каждого item укажи:
- confidence: "high" если совпадает с текстом пользователя, "medium" если только из vision, "low" если сомневаешься
- source: "caption" если из текста, "vision" если из распознавания, "merged" если объединён

Ответь СТРОГО JSON-массивом (без markdown, без ```):
[{"name": "...", "amount_g": N, "calories": N, "protein_g": N, "fat_g": N, "carbs_g": N, "confidence": "high|medium|low", "source": "caption|vision|merged"}]"""


# ── Промпт для применения пользовательской корректировки ─────────────────────

_CORRECTION_PROMPT = """У пользователя есть черновик приёма пищи (items). Он написал сообщение для корректировки.
Определи, что он хочет, и примени изменение.

ВОЗМОЖНЫЕ ДЕЙСТВИЯ:
- update_item: изменить граммовку или КБЖУ продукта (пересчитай КБЖУ пропорционально)
- remove_item: убрать продукт из списка
- add_item: добавить новый продукт (рассчитай КБЖУ)
- change_meal_type: изменить тип приёма пищи
- confirm: пользователь подтверждает ("да", "ок", "сохрани", "верно")
- discard: пользователь отменяет ("нет", "отмена", "не надо")
- unknown: непонятно что хочет пользователь

КБЖУ ВСЕГДА считай на фактический вес (amount_g), НЕ на 100г.
При изменении граммовки — ПЕРЕСЧИТАЙ КБЖУ пропорционально.

Ответь СТРОГО JSON (без markdown, без ```):
{
  "action": "update_item|remove_item|add_item|change_meal_type|confirm|discard|unknown",
  "updated_items": [...],
  "meal_type": "breakfast|lunch|dinner|snack",
  "explanation": "краткое описание что изменилось"
}

updated_items — ПОЛНЫЙ обновлённый список всех продуктов (с теми же полями: name, amount_g, calories, protein_g, fat_g, carbs_g, confidence, source).
Если action = confirm, discard или unknown — updated_items = [] (пустой массив)."""


def _extract_json_from_text(text: str) -> str:
    """Извлекает JSON из текста, убирая markdown-обёртки."""
    import re
    stripped = text.strip()
    # Убираем markdown code-block
    md_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', stripped, re.DOTALL)
    if md_match:
        stripped = md_match.group(1).strip()
    return stripped


async def merge_vision_and_caption(
    vision_items: list[dict],
    caption: str | None,
    user_text: str | None = None,
) -> list[dict]:
    """
    Слияние данных vision и подписи/текста пользователя через LLM.

    Args:
        vision_items: результат Vision API (список продуктов)
        caption: подпись к фото от пользователя
        user_text: дополнительный текст (если есть)

    Returns:
        Объединённый список продуктов с confidence и source
    """
    # Если caption пустой — просто добавляем confidence к vision items
    if not caption and not user_text:
        for item in vision_items:
            item.setdefault("confidence", "medium")
            item.setdefault("source", "vision")
        return vision_items

    # Формируем запрос к LLM
    combined_text = caption or ""
    if user_text:
        combined_text += f"\nДополнительно: {user_text}"

    user_message = (
        f"Vision распознал:\n{json.dumps(vision_items, ensure_ascii=False, indent=2)}\n\n"
        f"Подпись пользователя: «{combined_text}»"
    )

    try:
        response = await _client.chat.completions.create(
            model=_MERGE_MODEL,
            messages=[
                {"role": "system", "content": _MERGE_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
            max_tokens=2000,
        )

        raw = response.choices[0].message.content.strip()
        json_text = _extract_json_from_text(raw)
        merged = json.loads(json_text)

        if not isinstance(merged, list):
            logger.warning("Merge вернул не массив: %s", raw[:200])
            # Фолбэк — возвращаем vision items с дефолтными метками
            for item in vision_items:
                item.setdefault("confidence", "medium")
                item.setdefault("source", "vision")
            return vision_items

        logger.info("Merge: %d vision items + caption → %d merged items", len(vision_items), len(merged))
        return merged

    except Exception as e:
        logger.error("Ошибка merge vision+caption: %s", e, exc_info=True)
        # Фолбэк — возвращаем vision items
        for item in vision_items:
            item.setdefault("confidence", "medium")
            item.setdefault("source", "vision")
        return vision_items


async def apply_user_correction(
    draft_items: list[dict],
    user_text: str,
    current_meal_type: str = "snack",
) -> dict[str, Any]:
    """
    Применяет текстовую правку пользователя к черновику приёма пищи.

    Args:
        draft_items: текущий список продуктов в draft
        user_text: сообщение пользователя (корректировка)
        current_meal_type: текущий тип приёма пищи

    Returns:
        dict с ключами:
        - action: тип действия
        - updated_items: обновлённый список продуктов
        - meal_type: новый тип (если изменился)
        - explanation: описание изменений
    """
    user_message = (
        f"Текущий черновик (тип: {current_meal_type}):\n"
        f"{json.dumps(draft_items, ensure_ascii=False, indent=2)}\n\n"
        f"Сообщение пользователя: «{user_text}»"
    )

    try:
        response = await _client.chat.completions.create(
            model=_MERGE_MODEL,
            messages=[
                {"role": "system", "content": _CORRECTION_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
            max_tokens=2000,
        )

        raw = response.choices[0].message.content.strip()
        json_text = _extract_json_from_text(raw)
        result = json.loads(json_text)

        if not isinstance(result, dict):
            logger.warning("Correction вернул не dict: %s", raw[:200])
            return {
                "action": "unknown",
                "updated_items": [],
                "meal_type": current_meal_type,
                "explanation": "Не удалось распознать команду",
            }

        # Подставляем дефолты
        result.setdefault("action", "unknown")
        result.setdefault("updated_items", [])
        result.setdefault("meal_type", current_meal_type)
        result.setdefault("explanation", "")

        logger.info("Correction: action=%s, explanation=%s", result["action"], result["explanation"])
        return result

    except Exception as e:
        logger.error("Ошибка apply_user_correction: %s", e, exc_info=True)
        return {
            "action": "unknown",
            "updated_items": [],
            "meal_type": current_meal_type,
            "explanation": f"Ошибка обработки: {e}",
        }
