"""
Хендлеры раздела «⚙️ Настройки».
- Открытие меню настроек
- Выбор и сохранение часового пояса
- Выбор и сохранение оффсета напоминаний
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from zoneinfo import ZoneInfo

from bot.keyboards.main_kb import main_menu_kb
from bot.keyboards.settings_kb import settings_menu_kb, tz_inline_kb, offset_inline_kb
from db import reminders as rdb

router = Router()


@router.message(F.text == "⚙️ Настройки")
async def enter_settings_menu(message: Message) -> None:
    """Вход в раздел настроек (ReplyKeyboard)."""
    await rdb.ensure_schema()  # на случай первого входа — добавит недостающие колонки
    await rdb.get_user_settings(message.from_user.id)  # лениво заинициализируем запись пользователя
    await message.answer("Раздел «Настройки». Выберите параметр:", reply_markup=settings_menu_kb())


@router.message(F.text == "Часовой пояс")
async def choose_timezone(message: Message) -> None:
    """Показываем популярные TZ для быстрого выбора (InlineKeyboard)."""
    await message.answer(
        "Выберите часовой пояс из списка или отмените:",
        reply_markup=tz_inline_kb(),
    )


@router.message(F.text == "Оффсет напоминаний")
async def choose_offset(message: Message) -> None:
    """Показываем варианты смещения напоминаний в минутах."""
    await message.answer(
        "Через сколько минут до дедлайна напоминать?",
        reply_markup=offset_inline_kb(),
    )


@router.message(F.text == "⬅️ Назад")
async def back_to_main(message: Message) -> None:
    """Возврат в главное меню."""
    await message.answer("Главное меню:", reply_markup=main_menu_kb())


@router.callback_query(F.data.startswith("tz:"))
async def set_timezone(cb: CallbackQuery) -> None:
    """Обрабатываем выбор TZ из инлайн-меню."""
    _, value = cb.data.split(":", 1)
    if value == "cancel":
        await cb.answer("Отменено")
        await cb.message.delete_reply_markup()
        return
    # Валидация TZ
    try:
        ZoneInfo(value)
    except Exception:
        await cb.answer("Некорректный часовой пояс", show_alert=True)
        return
    await rdb.set_user_timezone(cb.from_user.id, value)
    await cb.answer("Сохранено")
    await cb.message.edit_text(f"Часовой пояс установлен: {value}")


@router.callback_query(F.data.startswith("offset:"))
async def set_offset(cb: CallbackQuery) -> None:
    """Обрабатываем выбор оффсета из инлайн-меню."""
    _, value = cb.data.split(":", 1)
    if value == "cancel":
        await cb.answer("Отменено")
        await cb.message.delete_reply_markup()
        return
    try:
        minutes = int(value)
    except ValueError:
        await cb.answer("Некорректное значение", show_alert=True)
        return
    await rdb.set_user_notification_offset(cb.from_user.id, minutes)
    await cb.answer("Сохранено")
    await cb.message.edit_text(f"Оффсет напоминаний: {minutes} мин")
