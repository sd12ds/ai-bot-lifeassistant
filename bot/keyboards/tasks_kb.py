"""
Меню управления задачами (ReplyKeyboard) при проваливании в раздел «Задачи».
"""
from __future__ import annotations

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def tasks_menu_kb() -> ReplyKeyboardMarkup:
    """Клавиатура действий над задачами.
    Включает быстрые действия и кнопку «Назад» в главное меню.
    """
    row1 = [KeyboardButton(text="📋 Список"), KeyboardButton(text="➕ Добавить")]
    row2 = [
        KeyboardButton(text="📅 Сегодня"),
        KeyboardButton(text="📆 Завтра"),
        KeyboardButton(text="🗓 На неделю"),
    ]
    row3 = [KeyboardButton(text="∅ Без срока"), KeyboardButton(text="⬅️ Назад")]
    return ReplyKeyboardMarkup(keyboard=[row1, row2, row3], resize_keyboard=True)
