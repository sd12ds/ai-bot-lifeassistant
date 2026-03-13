"""
Обработчик фото еды.
Фото → GPT-4o Vision → карточка приёма пищи → inline-кнопки (сохранить/редактировать/отменить).
"""
from __future__ import annotations

import asyncio
import base64
import logging
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.states import EditMealStates
from config import DEFAULT_TZ
from db import nutrition_storage as ns
from integrations.vision.food_recognizer import recognize_food_photo

router = Router()
logger = logging.getLogger(__name__)

# ── Временное хранилище распознанных данных ───────────────────────────────────
# {temp_id: {"user_id": int, "result": dict, "created_at": datetime}}
_pending_meals: dict[str, dict[str, Any]] = {}

# Названия типов приёма пищи
_MEAL_TYPE_RU = {
    "breakfast": "🌅 Завтрак",
    "lunch": "🍽 Обед",
    "dinner": "🌙 Ужин",
    "snack": "🍎 Перекус",
}


def _format_meal_card(result: dict) -> str:
    """Форматирует карточку приёма пищи для отправки в Telegram."""
    meal_type = result.get("meal_type", "snack")
    mt_label = _MEAL_TYPE_RU.get(meal_type, meal_type)
    now_str = datetime.now(DEFAULT_TZ).strftime("%H:%M")

    lines = [f"{mt_label} · {now_str}\n"]

    for item in result.get("items", []):
        name = item.get("name", "?")
        grams = item.get("amount_g", 0)
        cal = item.get("calories", 0)
        p = item.get("protein_g", 0)
        f = item.get("fat_g", 0)
        c = item.get("carbs_g", 0)
        lines.append(f"🔸 {name} — {grams}г")
        lines.append(f"   {cal} ккал · Б {p} · Ж {f} · У {c}\n")

    # Итого
    total = result.get("total", {})
    lines.append("─────────────────")
    lines.append(
        f"📊 Итого: {total.get('calories', 0)} ккал · "
        f"Б {total.get('protein_g', 0)} · "
        f"Ж {total.get('fat_g', 0)} · "
        f"У {total.get('carbs_g', 0)}"
    )

    return "\n".join(lines)


def _main_keyboard(temp_id: str) -> InlineKeyboardMarkup:
    """Клавиатура: сохранить / редактировать / отменить."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Сохранить", callback_data=f"meal_save:{temp_id}"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"meal_edit_start:{temp_id}"),
        ],
        [
            InlineKeyboardButton(text="🗑 Отменить", callback_data=f"meal_cancel:{temp_id}"),
        ],
    ])


def _edit_keyboard(temp_id: str, items: list[dict]) -> InlineKeyboardMarkup:
    """Клавиатура редактирования: кнопка для каждого продукта + готово."""
    rows = []
    for idx, item in enumerate(items):
        name = item.get("name", "?")[:20]  # Обрезаем длинные названия
        grams = item.get("amount_g", 0)
        rows.append([
            InlineKeyboardButton(
                text=f"📝 {name} ({grams}г)",
                callback_data=f"meal_edit_item:{temp_id}:{idx}",
            ),
            InlineKeyboardButton(
                text="❌",
                callback_data=f"meal_edit_del:{temp_id}:{idx}",
            ),
        ])
    # Кнопки внизу: готово (вернуться к карточке)
    rows.append([
        InlineKeyboardButton(text="✅ Готово", callback_data=f"meal_edit_done:{temp_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Обработчик фото ──────────────────────────────────────────────────────────

@router.message(F.photo)
async def photo_handler(message: Message, user_db: dict | None = None, bot: Bot = None):
    """Обрабатывает фото: скачивает → Vision API → показывает карточку."""
    # Индикатор обработки
    await bot.send_chat_action(message.chat.id, "typing")

    processing_msg = await message.answer("🔍 Анализирую фото еды...")

    try:
        # Скачиваем фото (берём самое большое разрешение — последний элемент)
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)

        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "food.jpg"
            await bot.download_file(file.file_path, destination=img_path)

            # Конвертируем в base64
            with open(img_path, "rb") as f:
                photo_b64 = base64.b64encode(f.read()).decode("utf-8")

        # Распознаём через Vision API
        result = await recognize_food_photo(photo_b64)

        # Проверяем на ошибку
        if "error" in result:
            await processing_msg.edit_text(f"❌ {result['error']}")
            return

        if not result.get("items"):
            await processing_msg.edit_text("❌ Не удалось распознать еду на фото. Попробуй сфотографировать ближе.")
            return

        # Сохраняем во временное хранилище
        temp_id = uuid.uuid4().hex[:8]
        _pending_meals[temp_id] = {
            "user_id": message.from_user.id,
            "result": result,
            "created_at": datetime.now(DEFAULT_TZ),
        }

        # Формируем и отправляем карточку
        card_text = _format_meal_card(result)
        await processing_msg.edit_text(
            card_text,
            reply_markup=_main_keyboard(temp_id),
        )

    except Exception as e:
        logger.error("Ошибка обработки фото: %s", e, exc_info=True)
        try:
            await processing_msg.edit_text("❌ Произошла ошибка при анализе фото.")
        except Exception:
            pass


# ── Callback: Сохранить ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("meal_save:"))
async def on_meal_save(cb: CallbackQuery):
    """Сохраняет распознанный приём пищи в БД."""
    temp_id = cb.data.split(":", 1)[1]
    pending = _pending_meals.pop(temp_id, None)

    if not pending:
        await cb.answer("⏰ Данные устарели, сфотографируй ещё раз.", show_alert=True)
        return

    result = pending["result"]
    user_id = pending["user_id"]

    try:
        # Сохраняем приём пищи
        meal = await ns.add_meal(
            user_id=user_id,
            meal_type=result.get("meal_type", "snack"),
            eaten_at=datetime.now(DEFAULT_TZ),
            items=result["items"],
        )

        total_cal = meal["total_calories"]
        await cb.answer(f"✅ Сохранено! {total_cal} ккал")

        # Обновляем сообщение — убираем кнопки, добавляем статус
        card_text = _format_meal_card(result)
        await cb.message.edit_text(f"{card_text}\n\n✅ Сохранено ({total_cal} ккал)")

    except Exception as e:
        logger.error("Ошибка сохранения meal: %s", e, exc_info=True)
        await cb.answer("❌ Ошибка при сохранении", show_alert=True)
        # Возвращаем в хранилище чтобы можно было повторить
        _pending_meals[temp_id] = pending


# ── Callback: Отменить ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("meal_cancel:"))
async def on_meal_cancel(cb: CallbackQuery):
    """Отменяет распознанный приём пищи."""
    temp_id = cb.data.split(":", 1)[1]
    _pending_meals.pop(temp_id, None)

    await cb.answer("🗑 Отменено")
    try:
        await cb.message.edit_text("🗑 Приём пищи отменён.")
    except Exception:
        pass


# ── Callback: Начать редактирование ───────────────────────────────────────────

@router.callback_query(F.data.startswith("meal_edit_start:"))
async def on_meal_edit_start(cb: CallbackQuery):
    """Показывает кнопки редактирования для каждого продукта."""
    temp_id = cb.data.split(":", 1)[1]
    pending = _pending_meals.get(temp_id)

    if not pending:
        await cb.answer("⏰ Данные устарели.", show_alert=True)
        return

    items = pending["result"].get("items", [])
    await cb.answer()
    await cb.message.edit_reply_markup(
        reply_markup=_edit_keyboard(temp_id, items),
    )


# ── Callback: Удалить продукт ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("meal_edit_del:"))
async def on_meal_edit_del(cb: CallbackQuery):
    """Удаляет продукт из распознанного списка."""
    parts = cb.data.split(":", 2)
    temp_id, idx = parts[1], int(parts[2])
    pending = _pending_meals.get(temp_id)

    if not pending:
        await cb.answer("⏰ Данные устарели.", show_alert=True)
        return

    items = pending["result"].get("items", [])
    if 0 <= idx < len(items):
        removed = items.pop(idx)
        # Пересчитываем total
        _recalc_total(pending["result"])
        await cb.answer(f"❌ {removed['name']} удалён")
    else:
        await cb.answer("Продукт не найден", show_alert=True)
        return

    # Обновляем карточку + кнопки редактирования
    card_text = _format_meal_card(pending["result"])
    await cb.message.edit_text(
        card_text,
        reply_markup=_edit_keyboard(temp_id, items),
    )


# ── Callback: Изменить граммовку продукта ──────────────────────────────────────

@router.callback_query(F.data.startswith("meal_edit_item:"))
async def on_meal_edit_item(cb: CallbackQuery, state: FSMContext):
    """Запрашивает новую граммовку для продукта (FSM)."""
    parts = cb.data.split(":", 2)
    temp_id, idx = parts[1], int(parts[2])
    pending = _pending_meals.get(temp_id)

    if not pending:
        await cb.answer("⏰ Данные устарели.", show_alert=True)
        return

    items = pending["result"].get("items", [])
    if idx >= len(items):
        await cb.answer("Продукт не найден", show_alert=True)
        return

    item_name = items[idx]["name"]
    current_g = items[idx]["amount_g"]

    # Запоминаем контекст в FSM
    await state.set_state(EditMealStates.waiting_for_grams)
    await state.update_data(temp_id=temp_id, item_idx=idx, msg_id=cb.message.message_id)

    await cb.answer()
    await cb.message.answer(
        f"📝 Введи новую граммовку для «{item_name}» (сейчас {current_g}г):"
    )


# ── FSM: Получение новой граммовки ────────────────────────────────────────────

@router.message(EditMealStates.waiting_for_grams)
async def on_grams_input(message: Message, state: FSMContext, bot: Bot = None):
    """Обрабатывает ввод новой граммовки."""
    data = await state.get_data()
    temp_id = data.get("temp_id")
    idx = data.get("item_idx")
    orig_msg_id = data.get("msg_id")

    await state.clear()

    # Парсим число
    try:
        new_grams = float(message.text.strip().replace(",", "."))
        if new_grams <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("❌ Введи число граммов (например: 200).")
        return

    pending = _pending_meals.get(temp_id)
    if not pending:
        await message.answer("⏰ Данные устарели, сфотографируй ещё раз.")
        return

    items = pending["result"].get("items", [])
    if idx >= len(items):
        await message.answer("❌ Продукт не найден.")
        return

    old_item = items[idx]
    old_grams = old_item["amount_g"]

    # Пересчитываем КБЖУ пропорционально новой граммовке
    if old_grams > 0:
        ratio = new_grams / old_grams
        old_item["amount_g"] = new_grams
        old_item["calories"] = round(old_item["calories"] * ratio, 1)
        old_item["protein_g"] = round(old_item["protein_g"] * ratio, 1)
        old_item["fat_g"] = round(old_item["fat_g"] * ratio, 1)
        old_item["carbs_g"] = round(old_item["carbs_g"] * ratio, 1)
    else:
        old_item["amount_g"] = new_grams

    # Пересчитываем total
    _recalc_total(pending["result"])

    await message.answer(f"✅ {old_item['name']} → {new_grams}г")

    # Обновляем карточку в оригинальном сообщении
    try:
        card_text = _format_meal_card(pending["result"])
        await bot.edit_message_text(
            text=card_text,
            chat_id=message.chat.id,
            message_id=orig_msg_id,
            reply_markup=_edit_keyboard(temp_id, items),
        )
    except Exception:
        pass  # Если не удалось обновить — не критично


# ── Callback: Завершить редактирование ─────────────────────────────────────────

@router.callback_query(F.data.startswith("meal_edit_done:"))
async def on_meal_edit_done(cb: CallbackQuery):
    """Завершает редактирование — возвращает главные кнопки."""
    temp_id = cb.data.split(":", 1)[1]
    pending = _pending_meals.get(temp_id)

    if not pending:
        await cb.answer("⏰ Данные устарели.", show_alert=True)
        return

    # Обновляем карточку с главными кнопками
    card_text = _format_meal_card(pending["result"])
    await cb.answer("✅ Редактирование завершено")
    await cb.message.edit_text(
        card_text,
        reply_markup=_main_keyboard(temp_id),
    )


# ── Утилиты ──────────────────────────────────────────────────────────────────

def _recalc_total(result: dict) -> None:
    """Пересчитывает итоговые значения КБЖУ по items."""
    items = result.get("items", [])
    result["total"] = {
        "calories": round(sum(i.get("calories", 0) for i in items), 1),
        "protein_g": round(sum(i.get("protein_g", 0) for i in items), 1),
        "fat_g": round(sum(i.get("fat_g", 0) for i in items), 1),
        "carbs_g": round(sum(i.get("carbs_g", 0) for i in items), 1),
    }
