"""
Обработчик фото еды — v3 (album-aware, draft-based).
Поддержка альбомов: несколько фото → один объединённый draft.
Одиночное фото → отдельный draft.
Редактирование через текст (agent), не через FSM.
"""
from __future__ import annotations

import asyncio
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

# ── Буфер для сбора альбомов ──────────────────────────────────────────────────
# media_group_id → список сообщений (фото) в альбоме
_album_buffer: dict[str, list[Message]] = {}
# media_group_id → asyncio.Task (таймер ожидания остальных фото)
_album_tasks: dict[str, asyncio.Task] = {}
# Время ожидания остальных фото альбома (сек)
_ALBUM_COLLECT_DELAY = 1.5


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


async def _download_photo_b64(message: Message, bot: Bot) -> str:
    """Скачивает фото из сообщения и возвращает base64-строку."""
    photo = message.photo[-1]  # самое большое разрешение
    file = await bot.get_file(photo.file_id)
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = Path(tmpdir) / "food.jpg"
        await bot.download_file(file.file_path, destination=img_path)
        with open(img_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")


async def _recognize_and_merge(photo_b64: str, caption: str | None) -> list[dict]:
    """Распознаёт фото через Vision API и мержит с caption если есть."""
    result = await recognize_food_photo(photo_b64, caption=caption)

    if "error" in result or not result.get("items"):
        return []

    vision_items = result["items"]
    if caption:
        # Мержим с подписью к фото
        merged = await merge_vision_and_caption(vision_items, caption)
        logger.info("Photo+caption merge: %d → %d items", len(vision_items), len(merged))
        return merged

    # Без caption — добавляем дефолтные метки
    for item in vision_items:
        item.setdefault("confidence", "medium")
        item.setdefault("source", "vision")
    return vision_items


# ── Обработчик фото ──────────────────────────────────────────────────────────

@router.message(F.photo)
async def photo_handler(message: Message, user_db: dict | None = None, bot: Bot = None):
    """Обрабатывает фото. Альбомы (media_group) собираются и обрабатываются вместе."""
    media_group_id = message.media_group_id

    if media_group_id:
        # ── Альбом: собираем все фото, ждём пока придут все ──
        if media_group_id not in _album_buffer:
            _album_buffer[media_group_id] = []
        _album_buffer[media_group_id].append(message)

        # Отменяем предыдущий таймер, ставим новый (debounce)
        old_task = _album_tasks.get(media_group_id)
        if old_task and not old_task.done():
            old_task.cancel()

        _album_tasks[media_group_id] = asyncio.create_task(
            _process_album(media_group_id, message.from_user.id, bot)
        )
        return

    # ── Одиночное фото — обрабатываем сразу ──
    await _process_single_photo(message, bot)


async def _process_album(media_group_id: str, user_id: int, bot: Bot):
    """Ждёт пока соберутся все фото альбома, затем создаёт один draft."""
    # Ждём остальные фото (Telegram присылает их с небольшой задержкой)
    await asyncio.sleep(_ALBUM_COLLECT_DELAY)

    messages = _album_buffer.pop(media_group_id, [])
    _album_tasks.pop(media_group_id, None)

    if not messages:
        return

    count = len(messages)
    logger.info("Альбом %s: получено %d фото от user=%s", media_group_id, count, user_id)

    # Один индикатор обработки для всего альбома
    processing_msg = await messages[0].answer(f"🔍 Анализирую {count} фото еды...")

    try:
        # Параллельно распознаём все фото
        tasks = []
        for msg in messages:
            photo_b64 = await _download_photo_b64(msg, bot)
            caption = msg.caption.strip() if msg.caption else None
            tasks.append(_recognize_and_merge(photo_b64, caption))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Собираем все items в один список
        all_items: list[dict] = []
        errors = 0
        for r in results:
            if isinstance(r, Exception):
                logger.error("Ошибка распознавания фото в альбоме: %s", r)
                errors += 1
            elif r:
                all_items.extend(r)

        if not all_items:
            await processing_msg.edit_text(
                "❌ Не удалось распознать еду на фото. Попробуй сфотографировать ближе."
            )
            return

        # Определяем meal_type по времени суток
        meal_type = _guess_meal_type()

        # Создаём ОДИН draft со всеми продуктами из всех фото
        draft = create_draft(
            user_id=user_id,
            items=all_items,
            meal_type=meal_type,
            source="photo",
        )

        card = format_draft_card(draft)
        status = f"📸 Распознано {count} фото"
        if errors:
            status += f" ({errors} с ошибкой)"
        hint = "\n💬 Напиши правку текстом (например: «сыра 30г» или «убери хлеб»)"

        await processing_msg.edit_text(
            f"{status}\n\n📋 Черновик приёма пищи:\n\n{card}{hint}",
            reply_markup=_quick_actions_keyboard(),
        )

    except Exception as e:
        logger.error("Ошибка обработки альбома %s: %s", media_group_id, e, exc_info=True)
        try:
            await processing_msg.edit_text("❌ Произошла ошибка при анализе фото.")
        except Exception:
            pass


async def _process_single_photo(message: Message, bot: Bot):
    """Обрабатывает одиночное фото (не альбом)."""
    user_id = message.from_user.id

    await bot.send_chat_action(message.chat.id, "typing")
    processing_msg = await message.answer("🔍 Анализирую фото еды...")

    try:
        caption = message.caption.strip() if message.caption else None
        photo_b64 = await _download_photo_b64(message, bot)
        items = await _recognize_and_merge(photo_b64, caption)

        if not items:
            await processing_msg.edit_text(
                "❌ Не удалось распознать еду на фото. Попробуй сфотографировать ближе."
            )
            return

        # Проверяем: если уже есть draft от фото — дополняем его
        ctx = get_context(user_id)
        if ctx and ctx.draft and ctx.draft.source_type == "photo":
            # Append: добавляем новые items к существующему draft
            ctx.draft.items.extend(items)
            ctx.draft.recalc()
            ctx.draft.version += 1
            logger.info(
                "Photo append: draft %s user=%s, теперь %d items",
                ctx.draft.draft_id, user_id, len(ctx.draft.items),
            )
            card = format_draft_card(ctx.draft)
            hint = "\n💬 Напиши правку текстом (например: «сыра 30г» или «убери хлеб»)"
            await processing_msg.edit_text(
                f"➕ Добавлено к черновику (v{ctx.draft.version}):\n\n📋 Черновик приёма пищи:\n\n{card}{hint}",
                reply_markup=_quick_actions_keyboard(),
            )
            return

        # Новый draft
        meal_type = _guess_meal_type()
        draft = create_draft(
            user_id=user_id,
            items=items,
            meal_type=meal_type,
            source="photo",
        )

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


def _guess_meal_type() -> str:
    """Определяет тип приёма пищи по текущему времени суток."""
    hour = datetime.now(DEFAULT_TZ).hour
    if 5 <= hour < 11:
        return "breakfast"
    elif 11 <= hour < 16:
        return "lunch"
    elif 16 <= hour < 22:
        return "dinner"
    return "snack"


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
            notes=f"source:{draft.source_type}",
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
