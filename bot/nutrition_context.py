"""
Хранилище сессий питания (Nutrition Session Context).

РЕФАКТОРИНГ: теперь это тонкий адаптер поверх bot/core/.
Все публичные функции сохраняют обратную совместимость —
импорты из других модулей (tools, handlers, supervisor) работают без изменений.

Внутри делегирует в:
- bot.core.session_context — универсальное хранилище сессий
- bot.core.adapters.nutrition_adapter — MealDraft, NutritionAdapter
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from config import DEFAULT_TZ

# ── Импорты из core (вся логика теперь там) ──────────────────────────────────
from bot.core.session_context import (
    SessionContext,
    get_context as _core_get_context,
    get_or_create_context as _core_get_or_create,
    set_draft as _core_set_draft,
    clear_draft as _core_clear_draft,
    clear_context as _core_clear_context,
    cleanup_expired as _core_cleanup_expired,
)
from bot.core.adapters.nutrition_adapter import (
    MealDraft,
    NutritionAdapter,
)

logger = logging.getLogger(__name__)

# Синглтон адаптера
_adapter = NutritionAdapter()

# ── Совместимость: NutritionSessionContext → SessionContext ───────────────────
# Старый код использовал NutritionSessionContext.
# Теперь это алиас для SessionContext с доп. свойствами.

NutritionSessionContext = SessionContext


# ── Публичные функции (обратная совместимость) ───────────────────────────────

def get_context(user_id: int) -> SessionContext | None:
    """Получить контекст сессии питания пользователя (или None если нет / истёк)."""
    return _core_get_context(user_id)


def get_or_create_context(user_id: int) -> SessionContext:
    """Получить существующий контекст или создать новый."""
    return _core_get_or_create(user_id, domain="nutrition")


def set_context(user_id: int, ctx: SessionContext) -> None:
    """Сохранить / обновить контекст пользователя."""
    ctx.last_activity = datetime.now(DEFAULT_TZ)
    # Core хранилище обновляется автоматически (тот же объект по ссылке)


def clear_context(user_id: int) -> None:
    """Полностью очистить контекст пользователя."""
    _core_clear_context(user_id)


def clear_draft(user_id: int) -> None:
    """Очистить только draft, оставив last_saved_meal."""
    _core_clear_draft(user_id)


def create_draft(
    user_id: int,
    items: list[dict],
    meal_type: str = "snack",
    source: str = "text",
    source_type: str = "",
    photo_file_id: str | None = None,
    vision_result: dict | None = None,
    caption: str | None = None,
) -> MealDraft:
    """Создать новый MealDraft и сохранить в контексте пользователя."""
    # Совместимость: параметр назывался и source и source_type
    src = source_type or source

    draft = _adapter.create_draft(
        user_id=user_id,
        items=items,
        meal_type=meal_type,
        source_type=src,
        photo_file_id=photo_file_id,
        vision_result=vision_result,
        caption=caption,
    )

    # Сохраняем в core session context
    ctx = _core_set_draft(user_id, draft)
    ctx.last_source = src
    ctx.active_domain = "nutrition"

    return draft


def cleanup_expired() -> int:
    """Удалить все просроченные контексты."""
    return _core_cleanup_expired()


# ── Форматирование ───────────────────────────────────────────────────────────

def format_context_for_agent(ctx_or_user_id) -> str:
    """Форматирует контекст сессии для инъекции в HumanMessage перед отправкой agent'у.
    
    Инжектирует:
    - [DRAFT] контекст если есть активный черновик
    - [LAST_SAVED] контекст если нет draft, но есть недавно сохранённый приём (< 10 мин)
    
    Принимает SessionContext или user_id (int) для обратной совместимости.
    """
    if isinstance(ctx_or_user_id, int):
        # Вызвано из supervisor с user_id
        ctx = _core_get_context(ctx_or_user_id)
        if ctx is None:
            return ""
    else:
        ctx = ctx_or_user_id

    # Если есть активный draft — используем стандартный формат
    draft_ctx = _adapter.format_context_for_agent(ctx)
    if draft_ctx:
        return draft_ctx

    # Если нет draft, но есть last_saved_entity — инжектируем контекст
    if ctx.last_saved_entity and ctx.active_domain == "nutrition":
        # Проверяем давность — только < 10 мин
        elapsed = datetime.now(DEFAULT_TZ) - ctx.last_activity
        if elapsed.total_seconds() < 600:  # 10 минут
            entity = ctx.last_saved_entity
            items_lines = []
            for item in entity.get("items", []):
                items_lines.append(
                    f"  - {item.get('name', '?')} {item.get('amount_g', 0)}г "
                    f"({item.get('calories', 0)} ккал)"
                )
            items_str = "\n".join(items_lines) if items_lines else "  (нет продуктов)"
            mt = entity.get("meal_type", "?")
            meal_id = entity.get("id", "?")
            total_cal = entity.get("total_calories", 0)
            return (
                f"[LAST_SAVED] Последний сохранённый приём (ID: {meal_id}, {mt}, {total_cal} ккал):\n"
                f"{items_str}\n"
                f"Если пользователь хочет изменить/поменять что-то — вызови meal_reload_last."
            )

    return ""


def format_draft_card(draft: MealDraft) -> str:
    """Форматирует карточку draft для отправки пользователю в Telegram."""
    return _adapter.format_draft_card(draft)
