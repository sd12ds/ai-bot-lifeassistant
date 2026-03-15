"""
Inline-клавиатура для подтверждения голосового чекина.

Callback-паттерны:
  vci_save:{slot}:{date}  — сохранить чекин
  vci_edit:{slot}:{date}  — изменить данные
  vci_cancel              — отменить
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def voice_checkin_confirm_kb(slot: str, check_date: str) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения голосового чекина.

    slot       — morning | midday | evening | manual
    check_date — строка в формате YYYY-MM-DD
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            # Кнопка сохранения
            InlineKeyboardButton(
                text="✅ Сохранить",
                callback_data=f"vci_save:{slot}:{check_date}",
            ),
            # Кнопка редактирования — пользователь напишет/продиктует правки
            InlineKeyboardButton(
                text="✏️ Изменить",
                callback_data=f"vci_edit:{slot}:{check_date}",
            ),
        ],
        [
            # Отмена
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="vci_cancel",
            ),
        ],
    ])
