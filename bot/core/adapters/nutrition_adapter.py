"""
NutritionAdapter — реализация DomainAdapter для модуля питания.

Содержит MealDraft (наследник BaseDraft) и NutritionFollowupProvider.
Оборачивает текущую логику из bot/nutrition_context.py и services/nutrition_followup.py.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from config import DEFAULT_TZ
from bot.core.base_draft import BaseDraft, DraftStatus
from bot.core.session_context import SessionContext

logger = logging.getLogger(__name__)

# Названия типов приёма пищи (для форматирования)
_MEAL_TYPE_RU = {
    "breakfast": "🌅 Завтрак",
    "lunch": "🍽 Обед",
    "dinner": "🌙 Ужин",
    "snack": "🍎 Перекус",
}


# ── MealDraft — доменный наследник BaseDraft ─────────────────────────────────

@dataclass
class MealDraft(BaseDraft):
    """Черновик приёма пищи — расширение BaseDraft для nutrition."""
    # Nutrition-специфичные поля хранятся в meta и отдельных атрибутах
    meal_type: str = "snack"                    # breakfast | lunch | dinner | snack
    photo_file_id: str | None = None            # Telegram file_id фото еды
    vision_result: dict | None = None           # Сырой результат Vision API
    caption: str | None = None                  # Подпись пользователя к фото
    total_calories: float = 0
    total_protein: float = 0
    total_fat: float = 0
    total_carbs: float = 0
    message_id: int | None = None               # ID сообщения с карточкой

    def __post_init__(self):
        """Устанавливаем домен при создании."""
        self.domain = "nutrition"

    def recalc(self) -> None:
        """Пересчитывает суммарные КБЖУ по items."""
        self.total_calories = round(sum(i.get("calories", 0) for i in self.items), 1)
        self.total_protein = round(sum(i.get("protein_g", 0) for i in self.items), 1)
        self.total_fat = round(sum(i.get("fat_g", 0) for i in self.items), 1)
        self.total_carbs = round(sum(i.get("carbs_g", 0) for i in self.items), 1)
        self.updated_at = datetime.now(DEFAULT_TZ)

    @property
    def total(self) -> dict:
        """Совместимость со старым кодом, который обращается к draft.total."""
        return {
            "calories": self.total_calories,
            "protein_g": self.total_protein,
            "fat_g": self.total_fat,
            "carbs_g": self.total_carbs,
        }


# ── NutritionAdapter ─────────────────────────────────────────────────────────

class NutritionAdapter:
    """Доменный адаптер питания — реализует DomainAdapter protocol."""

    @property
    def domain(self) -> str:
        return "nutrition"

    def create_draft(
        self,
        user_id: int,
        items: list[dict],
        meal_type: str = "snack",
        source_type: str = "text",
        photo_file_id: str | None = None,
        vision_result: dict | None = None,
        caption: str | None = None,
        **kwargs: Any,
    ) -> MealDraft:
        """Создать MealDraft с пересчётом КБЖУ."""
        draft = MealDraft(
            draft_id=uuid.uuid4().hex[:8],
            items=items,
            status=DraftStatus.AWAITING_CONFIRMATION,
            source_type=source_type,
            meal_type=meal_type,
            photo_file_id=photo_file_id,
            vision_result=vision_result,
            caption=caption,
        )
        draft.recalc()
        logger.info(
            "NutritionAdapter: создан draft %s для user=%s: %d items, %.0f ккал",
            draft.draft_id, user_id, len(items), draft.total_calories,
        )
        return draft

    def format_draft_card(self, draft: BaseDraft) -> str:
        """Форматирует карточку MealDraft для Telegram."""
        if not isinstance(draft, MealDraft):
            return "⚠️ Некорректный тип draft"

        mt_label = _MEAL_TYPE_RU.get(draft.meal_type, draft.meal_type)
        now_str = datetime.now(DEFAULT_TZ).strftime("%H:%M")

        lines = [f"{mt_label} · {now_str}\n"]

        for item in draft.items:
            name = item.get("name", "?")
            grams = item.get("amount_g", 0)
            cal = item.get("calories", 0)
            p = item.get("protein_g", 0)
            f_val = item.get("fat_g", 0)
            c = item.get("carbs_g", 0)
            conf = item.get("confidence", "high")

            # Маркер уверенности
            marker = "🔹" if conf in ("low", "medium") else "🔸"
            uncertain = " (??)" if conf == "low" else ""

            lines.append(f"{marker} {name} — {grams}г{uncertain}")
            lines.append(f"   {cal} ккал · Б {p} · Ж {f_val} · У {c}\n")

        # Итого
        lines.append("─────────────────")
        lines.append(
            f"📊 Итого: {draft.total_calories} ккал · "
            f"Б {draft.total_protein} · "
            f"Ж {draft.total_fat} · "
            f"У {draft.total_carbs}"
        )
        return "\n".join(lines)

    def format_context_for_agent(self, ctx: SessionContext) -> str:
        """Форматирует контекст для инъекции в промпт nutrition agent."""
        lines: list[str] = ["[NUTRITION_CONTEXT]"]
        draft = ctx.draft

        if draft and isinstance(draft, MealDraft) and draft.status in (
            DraftStatus.DRAFT, DraftStatus.AWAITING_CONFIRMATION,
            "draft", "awaiting_confirmation",
        ):
            mt_label = _MEAL_TYPE_RU.get(draft.meal_type, draft.meal_type)
            source_label = {
                "photo": "фото", "text": "текст", "mixed": "фото + подпись",
                "clone": "клонирование",
            }.get(draft.source_type, draft.source_type)

            lines.append("Статус: есть несохранённый черновик")
            lines.append("")
            lines.append(f"Черновик приёма пищи (draft_id: {draft.draft_id}):")
            lines.append(f"Тип: {mt_label}")
            lines.append(f"Статус: {draft.status}")
            lines.append(f"Источник: {source_label}")
            lines.append("")
            lines.append("Продукты:")

            for i, item in enumerate(draft.items, 1):
                name = item.get("name", "?")
                grams = item.get("amount_g", 0)
                cal = item.get("calories", 0)
                conf = item.get("confidence", "medium")
                src = item.get("source", "unknown")
                lines.append(
                    f"{i}. {name} — {grams}г ({cal} ккал) "
                    f"[источник: {src}, уверенность: {conf}]"
                )

            lines.append("")
            lines.append(
                f"Итого: {draft.total_calories} ккал · "
                f"Б {draft.total_protein}г · "
                f"Ж {draft.total_fat}г · "
                f"У {draft.total_carbs}г"
            )

            if draft.caption:
                lines.append(f'\nПодпись пользователя: "{draft.caption}"')

        elif ctx.last_saved_entity:
            meal = ctx.last_saved_entity
            mt_label = _MEAL_TYPE_RU.get(meal.get("meal_type", ""), "")
            eaten_time = ""
            if meal.get("eaten_at"):
                try:
                    t = datetime.fromisoformat(meal["eaten_at"])
                    eaten_time = f" в {t.strftime('%H:%M')}"
                except (ValueError, TypeError):
                    pass
            items_str = ", ".join(
                f"{it['name']} {it['amount_g']}г"
                for it in meal.get("items", [])
            )
            total_cal = meal.get("total_calories", 0)
            lines.append("Статус: нет активного черновика")
            lines.append(f"Последний сохранённый приём: {mt_label}{eaten_time}")
            lines.append(f"  {items_str} — {total_cal} ккал")
        else:
            return ""

        lines.append("[/NUTRITION_CONTEXT]")
        return "\n".join(lines)

    async def save_draft(self, user_id: int, draft: BaseDraft) -> dict:
        """Сохранить MealDraft в БД через nutrition_storage."""
        from db import nutrition_storage as ns
        if not isinstance(draft, MealDraft):
            raise TypeError("Expected MealDraft")

        eaten_at = datetime.now(DEFAULT_TZ)
        result = await ns.add_meal(
            user_id=user_id,
            meal_type=draft.meal_type,
            eaten_at=eaten_at,
            items=draft.items,
            notes=f"source:{draft.source_type}",
        )
        return result

    async def generate_followup(self, user_id: int) -> list[str]:
        """Сгенерировать follow-up через services/nutrition_followup."""
        from services.nutrition_followup import generate_followup
        return await generate_followup(user_id)


# ── NutritionFollowupProvider для универсального followup_engine ─────────────

class NutritionFollowupProvider:
    """Провайдер follow-up подсказок для nutrition (обёртка над services)."""

    async def generate(self, user_id: int, **kwargs: Any) -> list[str]:
        """Делегирует в services/nutrition_followup."""
        from services.nutrition_followup import generate_followup
        return await generate_followup(user_id)
