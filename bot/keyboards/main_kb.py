"""
Главное меню бота (ReplyKeyboard).
Mini App доступен через стандартную синюю кнопку Telegram (Menu Button).
"""
from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру главного меню."""
    rows: list[list[KeyboardButton]] = [
        # Ряд: «Задачи», «🎯 Коучинг»
        [
            KeyboardButton(text="Задачи"),
            KeyboardButton(text="🎯 Коучинг"),
        ],
        # Ряд: «⚙️ Настройки», «Помощь»
        [
            KeyboardButton(text="⚙️ Настройки"),
            KeyboardButton(text="Помощь"),
        ],
    ]

    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
