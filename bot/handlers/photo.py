"""
Обработчик фото еды — v2 (draft-based).
Фото + caption → Vision API → merge engine → MealDraft → карточка + Quick Actions.
Редактирование через текст (agent), не через FSM.
"""
from __future__ import annotations

import base64
import logging
import tempfile
from datetime import datetime
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import DEFAULT_TZ
from db import nutrition_storage as ns
from integrations.vision.food_recognizer import recognize_food_photo
from services.nutrition_merge import merge_vision_and_caption
from bot.nutrition_context import (
    create_draft, get_context, clear_draft,
    format_draft_card,
)

router = Router()
logger = logging.getLogger(__name__)

# Названия типов приёма пищи
_MEAL_TYPE_RU = {
    "breakfast": "🌅 Завтрак",
    "lunch": "🍽 Обед",
    "dinner": "🌙 Ужин",
    "snack": "🍎 Перекус",
}


def _quick_actions_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура Quick Actions: сохранить / отменить.
    Редактирование — через текстовое сообщение в чат (обрабатывает agent).
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Сохранить", callback_data="draft_save"),
            InlineKeyboardButton(text="🗑 Отменить", callback_data="draft_cancel"),
        ],
        [
            InlineKeyboardButton(text="✏️ Напиши правку в чат", callback_data="draft_edit_hint"),
        ],
    ])


# ── Обработчик фото ──────────────────────────────────────────────────────────

@router.message(F.photo)
async def photo_handler(message: Message, user_db: dict | None = None, bot: Bot = None):
    """Обрабатывает фото: скачивает → Vision API → merge с caption → создаёт draft."""
    user_id = message.from_user.id

    # Индикатор обработки
    await bot.send_chat_action(message.chat.id, "typing")
    processing_msg = await message.answer("🔍 Анализирую фото еды...")

    try:
        # Читаем caption (подпись к фото)
        caption = message.caption.strip() if message.caption else None

        # Скачиваем фото (берём самое большое разрешение — последний элемент)
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)

        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "food.jpg"
            await bot.download_file(file.file_path, destination=img_path)

            # Конвертируем в base64
            with open(img_path, "rb") as f:
                photo_b64 = base64.b64encode(f.read()).decode("utf-8")

        # Распознаём через Vision API (с caption если есть)
        result = await recognize_food_photo(photo_b64, caption=caption)

        # Проверяем на ошибку
        if "error" in result:
            await processing_msg.edit_text(f"❌ {result['error']}")
            return

        if not result.get("items"):
            await processing_msg.edit_text(
                "❌ Не удалось распознать еду на фото. Попробуй сфотографировать ближе."
            )
            return

        # Если есть caption — прогоняем через merge engine для слияния
        vision_items = result["items"]
        if caption:
            merged_items = await merge_vision_and_caption(vision_items, caption)
            logger.info("Photo+caption merge: %d → %d items", len(vision_items), len(merged_items))
        else:
            # Без caption — просто добавляем дефолтные метки
            merged_items = vision_items
            for item in merged_items:
                item.setdefault("confidence", "medium")
                item.setdefault("source", "vision")

        # Создаём MealDraft в контексте сессии
        meal_type = result.get("meal_type", "snack")
        draft = create_draft(
            user_id=user_id,
            items=merged_items,
            meal_type=meal_type,
            source="photo",
        )

        # Формируем карточку и отправляем с Quick Actions
        card = format_draft_card(draft)
        hint = "\n💬 Напиши правку текстом (например: «сыра 30г» или «убери хлеб»)"
        await processing_msg.edit_text(
            f"📋 Черновик приёма пищи:\n\n{card}{hint}",
            reply_markup=_quick_actions_keyboard(),
        )

    except Exception as e:
        logger.error("Ошибка обработки фото: %s", e, exc_info=True)
        try:
            await processing_msg.edit_text("❌ Произошла ошибка при анализе фото.")
        except Exception:
            pass


# ── Callback: Сохранить draft ────────────────────────────────────────────────

@router.callback_query(F.data == "draft_save")
async def on_draft_save(cb: CallbackQuery):
    """Сохраняет текущий draft в БД."""
    user_id = cb.from_user.id
    ctx = get_context(user_id)

    if not ctx or not ctx.draft:
        await cb.answer("⏰ Черновик не найден или устарел.", show_alert=True)
        return

    draft = ctx.draft
    try:
        # Сохраняем приём пищи через nutrition_storage
        meal = await ns.add_meal(
            user_id=user_id,
            meal_type=draft.meal_type,
            eaten_at=datetime.now(DEFAULT_TZ),
            items=draft.items,
            notes=f"source:{draft.source}",
        )

        total_cal = meal["total_calories"]

        # Очищаем draft после сохранения
        clear_draft(user_id)

        await cb.answer(f"✅ Сохранено! {total_cal} ккал")

        # Обновляем сообщение — убираем кнопки, показываем результат
        mt_label = _MEAL_TYPE_RU.get(draft.meal_type, draft.meal_type)
        lines = [f"✅ {mt_label} сохранён\n"]
        for item in meal.get("items", []):
            lines.append(f"  🔸 {item['name']} — {item['amount_g']}г ({item['calories']} ккал)")
        lines.append(
            f"\n📊 Итого: {total_cal} ккал "
            f"· Б {meal['total_protein']} · Ж {meal['total_fat']} · У {meal['total_carbs']}"
        )
        await cb.message.edit_text("\n".join(lines))

    except Exception as e:
        logger.error("Ошибка сохранения draft: %s", e, exc_info=True)
        await cb.answer("❌ Ошибка при сохранении", show_alert=True)


# ── Callback: Отменить draft ─────────────────────────────────────────────────

@router.callback_query(F.data == "draft_cancel")
async def on_draft_cancel(cb: CallbackQuery):
    """Отменяет текущий draft."""
    user_id = cb.from_user.id
    clear_draft(user_id)

    await cb.answer("🗑 Отменено")
    try:
        await cb.message.edit_text("🗑 Приём пищи отменён.")
    except Exception:
        pass


# ── Callback: Подсказка про текстовое редактирование ──────────────────────────

@router.callback_query(F.data == "draft_edit_hint")
async def on_draft_edit_hint(cb: CallbackQuery):
    """Показывает подсказку — как редактировать через текст."""
    await cb.answer(
        "Просто напиши в чат что изменить:\n"
        "• «сыра 30г» — изменить граммовку\n"
        "• «убери хлеб» — удалить продукт\n"
        "• «добавь кофе» — добавить продукт\n"
        "• «да» или «ок» — сохранить",
        show_alert=True,
    )
