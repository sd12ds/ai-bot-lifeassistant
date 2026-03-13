"""
Клавиатуры раздела «⚙️ Настройки».
- ReplyKeyboard для входа в раздел и возврата назад
- InlineKeyboard для выбора часового пояса и оффсета напоминаний
"""
from __future__ import annotations

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

# ── Reply: меню настроек ──────────────────────────────────────────────────────

def settings_menu_kb() -> ReplyKeyboardMarkup:
    """Клавиатура раздела настроек."""
    row1 = [KeyboardButton(text="Часовой пояс"), KeyboardButton(text="Оффсет напоминаний")]
    row2 = [KeyboardButton(text="⬅️ Назад")]
    return ReplyKeyboardMarkup(keyboard=[row1, row2], resize_keyboard=True)


# ── Inline: выбор часового пояса ─────────────────────────────────────────────

# Набор популярных TZ (можно расширить по запросу)
_TZ_CHOICES: list[tuple[str, str]] = [
    ("Москва (Europe/Moscow)", "Europe/Moscow"),
    ("Киев (Europe/Kyiv)", "Europe/Kyiv"),
    ("Минск (Europe/Minsk)", "Europe/Minsk"),
    ("Тбилиси (Asia/Tbilisi)", "Asia/Tbilisi"),
    ("Алматы (Asia/Almaty)", "Asia/Almaty"),
    ("Берлин (Europe/Berlin)", "Europe/Berlin"),
    ("Лондон (Europe/London)", "Europe/London"),
    ("Нью-Йорк (America/New_York)", "America/New_York"),
    ("Лос-Анджелес (America/Los_Angeles)", "America/Los_Angeles"),
]

def tz_inline_kb() -> InlineKeyboardMarkup:
    """Клавиатура для выбора часового пояса (Inline)."""
    rows: list[list[InlineKeyboardButton]] = []
    for title, tz in _TZ_CHOICES:
        rows.append([InlineKeyboardButton(text=title, callback_data=f"tz:{tz}")])
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="tz:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Inline: выбор оффсета напоминаний ────────────────────────────────────────

_OFFSET_CHOICES = [0, 5, 10, 15, 30, 60]

def offset_inline_kb() -> InlineKeyboardMarkup:
    """Клавиатура для выбора оффсета в минутах."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for i, m in enumerate(_OFFSET_CHOICES, start=1):
        row.append(InlineKeyboardButton(text=f"{m} мин", callback_data=f"offset:{m}"))
        if i % 3 == 0:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="offset:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
