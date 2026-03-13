from __future__ import annotations
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def postpone_kb(scope: str, task_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора переноса дедлайна на фиксированные интервалы."""
    options = [
        ("+30 мин", 30),
        ("+1 ч", 60),
        ("+3 ч", 180),
        ("+1 д", 1440),
        ("+1 нед", 10080),
    ]
    rows = []
    row = []
    for i, (label, minutes) in enumerate(options, 1):
        row.append(InlineKeyboardButton(text=label, callback_data=f"postpone:{scope}:{task_id}:{minutes}"))
        if i % 3 == 0:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="Отмена", callback_data=f"postpone:{scope}:{task_id}:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
