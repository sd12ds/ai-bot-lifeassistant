"""
Общие команды бота: /start, /help, /mode, /voice_on, /voice_off.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from db.storage import set_user_mode
from config import BUSINESS_MODE_USERS

# Главное меню (ReplyKeyboard) — первая кнопка «Задачи»
from bot.keyboards.main_kb import main_menu_kb

router = Router()


@router.message(Command("start"))
async def start_handler(message: Message, user_db: dict | None = None):
    """Приветствие и показ главного меню с первой кнопкой «Задачи»."""
    mode = user_db.get("mode", "personal") if user_db else "personal"
    mode_str = "🏢 Бизнес" if mode == "business" else "👤 Личный"
    text = (
        "Привет! Я мультиагентный ассистент.\n\n"
        f"Текущий режим: {mode_str}\n\n"
        "Нажмите «Задачи», чтобы управлять списком дел. Остальные разделы появятся позже.\n"
        "/help — помощь"
    )
    # Показываем ReplyKeyboard главного меню
    await message.answer(text, reply_markup=main_menu_kb())


@router.message(Command("help"))
async def help_handler(message: Message):
    """Краткая справка по командам."""
    await message.answer(
        "Примеры запросов:\n\n"
        "📅 Календарь:\n"
        "— создай встречу завтра в 15:00 с названием Планёрка\n"
        "— что у меня в календаре завтра?\n"
        "— перенеси встречу Планёрка на пятницу в 18:00\n\n"
        "✅ Задачи:\n"
        "— добавь задачу написать отчёт до пятницы\n"
        "— покажи мои задачи\n"
        "— выполнил задачу 3\n\n"
        "🏢 Бизнес (режим /mode business):\n"
        "— добавь контакт Иван Иванов, телефон +79001234567\n"
        "— покажи мои сделки\n"
        "— новая сделка: проект сайт на 150000 руб\n\n"
        "💬 Просто общайся — я помню контекст разговора!"
    )


@router.message(Command("mode"))
async def mode_handler(message: Message, user_db: dict | None = None):
    """Переключение режима работы: /mode personal или /mode business."""
    if not message.text:
        return

    # Парсим аргумент команды
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2 or parts[1] not in ("personal", "business"):
        await message.answer(
            "Укажи режим:\n/mode personal — личный\n/mode business — бизнес"
        )
        return

    new_mode = parts[1]
    user_id = message.from_user.id

    # Проверяем доступ к бизнес-режиму (если задан whitelist)
    if new_mode == "business" and BUSINESS_MODE_USERS and user_id not in BUSINESS_MODE_USERS:
        await message.answer("Бизнес-режим недоступен для вашего аккаунта.")
        return

    await set_user_mode(user_id, new_mode)
    icon = "🏢" if new_mode == "business" else "👤"
    label = "Бизнес" if new_mode == "business" else "Личный"
    await message.answer(f"{icon} Режим переключён: {label}")


@router.message(Command("voice_on"))
async def voice_on_handler(message: Message):
    """Включает голосовые ответы."""
    # Используем глобальный config — изменяем на лету
    import config
    config.VOICE_REPLY_MODE = "always"
    await message.answer("🔊 Отвечаю голосом.")


@router.message(Command("voice_off"))
async def voice_off_handler(message: Message):
    """Отключает голосовые ответы."""
    import config
    config.VOICE_REPLY_MODE = "never"
    await message.answer("🔇 Отвечаю текстом.")
