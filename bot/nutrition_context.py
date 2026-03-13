"""
Хранилище сессий питания (Nutrition Session Context).

Хранит черновики приёмов пищи (MealDraft) и последний сохранённый meal
для каждого пользователя. Позволяет nutrition agent'у видеть контекст
между фото и текстовыми сообщениями.

In-memory хранилище с TTL 30 минут. В Этапе B → Redis / БД.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from config import DEFAULT_TZ

logger = logging.getLogger(__name__)

# TTL контекста сессии — 30 минут неактивности
_SESSION_TTL = timedelta(minutes=30)

# Названия типов приёма пищи (для форматирования)
_MEAL_TYPE_RU = {
    "breakfast": "🌅 Завтрак",
    "lunch": "🍽 Обед",
    "dinner": "🌙 Ужин",
    "snack": "🍎 Перекус",
}


@dataclass
class MealDraft:
    """Черновик приёма пищи — хранится до подтверждения пользователем."""
    draft_id: str                       # Уникальный id (uuid hex[:8])
    items: list[dict]                   # [{name, amount_g, calories, protein_g, fat_g, carbs_g, confidence, source}]
    meal_type: str                      # breakfast | lunch | dinner | snack
    source_type: str                    # photo | text | mixed
    photo_file_id: str | None = None    # Telegram file_id фото еды
    vision_result: dict | None = None   # Сырой результат Vision API
    caption: str | None = None          # Подпись пользователя к фото
    status: str = "draft"               # draft | awaiting_confirmation | confirmed | saved | discarded
    total: dict = field(default_factory=dict)   # {calories, protein_g, fat_g, carbs_g}
    message_id: int | None = None       # ID сообщения с карточкой (для обновления)
    created_at: datetime = field(default_factory=lambda: datetime.now(DEFAULT_TZ))
    updated_at: datetime = field(default_factory=lambda: datetime.now(DEFAULT_TZ))

    def recalc_total(self) -> None:
        """Пересчитывает суммарные КБЖУ по items."""
        self.total = {
            "calories": round(sum(i.get("calories", 0) for i in self.items), 1),
            "protein_g": round(sum(i.get("protein_g", 0) for i in self.items), 1),
            "fat_g": round(sum(i.get("fat_g", 0) for i in self.items), 1),
            "carbs_g": round(sum(i.get("carbs_g", 0) for i in self.items), 1),
        }
        self.updated_at = datetime.now(DEFAULT_TZ)


@dataclass
class NutritionSessionContext:
    """Контекст сессии питания для одного пользователя."""
    user_id: int
    # Текущий черновик приёма пищи
    draft: MealDraft | None = None
    # Последний сохранённый meal (для ответов на «записал?»)
    last_saved_meal: dict | None = None
    # Время последнего взаимодействия
    last_activity: datetime = field(default_factory=lambda: datetime.now(DEFAULT_TZ))
    # Источник последнего входа
    last_source: str = ""  # "photo" | "text" | "voice"


# ── In-memory хранилище контекстов ──────────────────────────────────────────
_contexts: dict[int, NutritionSessionContext] = {}
# Lock per user для предотвращения race conditions
_locks: dict[int, asyncio.Lock] = {}


def _get_lock(user_id: int) -> asyncio.Lock:
    """Возвращает asyncio Lock для конкретного пользователя."""
    if user_id not in _locks:
        _locks[user_id] = asyncio.Lock()
    return _locks[user_id]


def get_context(user_id: int) -> NutritionSessionContext | None:
    """Получить контекст сессии питания пользователя (или None если нет / истёк)."""
    ctx = _contexts.get(user_id)
    if ctx is None:
        return None
    # Проверяем TTL
    if datetime.now(DEFAULT_TZ) - ctx.last_activity > _SESSION_TTL:
        # Сессия истекла — удаляем
        _contexts.pop(user_id, None)
        logger.debug("Nutrition context для user=%s истёк (TTL)", user_id)
        return None
    return ctx


def get_or_create_context(user_id: int) -> NutritionSessionContext:
    """Получить существующий контекст или создать новый."""
    ctx = get_context(user_id)
    if ctx is None:
        ctx = NutritionSessionContext(user_id=user_id)
        _contexts[user_id] = ctx
    return ctx


def set_context(user_id: int, ctx: NutritionSessionContext) -> None:
    """Сохранить / обновить контекст пользователя."""
    ctx.last_activity = datetime.now(DEFAULT_TZ)
    _contexts[user_id] = ctx


def clear_context(user_id: int) -> None:
    """Полностью очистить контекст пользователя."""
    _contexts.pop(user_id, None)


def clear_draft(user_id: int) -> None:
    """Очистить только draft, оставив last_saved_meal."""
    ctx = _contexts.get(user_id)
    if ctx:
        ctx.draft = None
        ctx.last_activity = datetime.now(DEFAULT_TZ)


def create_draft(
    user_id: int,
    items: list[dict],
    meal_type: str,
    source_type: str = "text",
    photo_file_id: str | None = None,
    vision_result: dict | None = None,
    caption: str | None = None,
) -> MealDraft:
    """Создать новый MealDraft и сохранить в контексте пользователя."""
    ctx = get_or_create_context(user_id)
    draft = MealDraft(
        draft_id=uuid.uuid4().hex[:8],
        items=items,
        meal_type=meal_type,
        source_type=source_type,
        photo_file_id=photo_file_id,
        vision_result=vision_result,
        caption=caption,
        status="awaiting_confirmation",
    )
    # Пересчитываем итоги
    draft.recalc_total()
    ctx.draft = draft
    ctx.last_source = source_type
    ctx.last_activity = datetime.now(DEFAULT_TZ)
    _contexts[user_id] = ctx
    logger.info(
        "Создан draft %s для user=%s: %d items, %s ккал",
        draft.draft_id, user_id, len(items), draft.total.get("calories", 0),
    )
    return draft


def cleanup_expired() -> int:
    """Удалить все просроченные контексты. Возвращает количество удалённых."""
    now = datetime.now(DEFAULT_TZ)
    expired = [
        uid for uid, ctx in _contexts.items()
        if now - ctx.last_activity > _SESSION_TTL
    ]
    for uid in expired:
        _contexts.pop(uid, None)
    if expired:
        logger.debug("Очищено %d просроченных nutrition context'ов", len(expired))
    return len(expired)


# ── Форматирование контекста для agent ──────────────────────────────────────

def format_context_for_agent(ctx: NutritionSessionContext) -> str:
    """Форматирует контекст сессии для инъекции в HumanMessage перед отправкой agent'у."""
    lines: list[str] = ["[NUTRITION_CONTEXT]"]

    if ctx.draft and ctx.draft.status in ("draft", "awaiting_confirmation"):
        # Есть активный черновик
        draft = ctx.draft
        mt_label = _MEAL_TYPE_RU.get(draft.meal_type, draft.meal_type)
        source_label = {
            "photo": "фото",
            "text": "текст",
            "mixed": "фото + подпись",
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

        total = draft.total
        lines.append("")
        lines.append(
            f"Итого: {total.get('calories', 0)} ккал · "
            f"Б {total.get('protein_g', 0)}г · "
            f"Ж {total.get('fat_g', 0)}г · "
            f"У {total.get('carbs_g', 0)}г"
        )

        if draft.caption:
            lines.append(f'\nПодпись пользователя: "{draft.caption}"')

    elif ctx.last_saved_meal:
        # Нет draft, но есть последний сохранённый meal
        meal = ctx.last_saved_meal
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
        lines.append(
            f"Последний сохранённый приём: {mt_label}{eaten_time}"
        )
        lines.append(f"  {items_str} — {total_cal} ккал")
    else:
        # Ничего нет — не добавляем контекст
        return ""

    lines.append("[/NUTRITION_CONTEXT]")
    return "\n".join(lines)


def format_draft_card(draft: MealDraft) -> str:
    """Форматирует карточку draft для отправки пользователю в Telegram."""
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

        # Маркер уверенности: 🔸 — уверен, 🔹 — сомневается
        marker = "🔹" if conf in ("low", "medium") else "🔸"
        uncertain = " (??)" if conf == "low" else ""

        lines.append(f"{marker} {name} — {grams}г{uncertain}")
        lines.append(f"   {cal} ккал · Б {p} · Ж {f_val} · У {c}\n")

    # Итого
    total = draft.total
    lines.append("─────────────────")
    lines.append(
        f"📊 Итого: {total.get('calories', 0)} ккал · "
        f"Б {total.get('protein_g', 0)} · "
        f"Ж {total.get('fat_g', 0)} · "
        f"У {total.get('carbs_g', 0)}"
    )

    return "\n".join(lines)
