"""
Хендлеры меню задач (ReplyKeyboard):
- Вход в раздел «Задачи» из главного меню
- Быстрые действия: «📋 Список», «📅 Сегодня», «📆 Завтра», «🗓 На неделю», «∅ Без срока», «➕ Добавить», «⬅️ Назад»

Примечание: здесь мы не реализуем полный FSM добавления задачи.
Кнопка «➕ Добавить» подсказывает формат, дальше текст попадёт в общий text_handler
и будет обработан агентом/инструментами (ReminderAgent + tools).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from db import storage
from bot.keyboards.main_kb import main_menu_kb
from bot.keyboards.tasks_kb import tasks_menu_kb

logger = logging.getLogger(__name__)
router = Router()


def _tz(user_db: dict | None) -> ZoneInfo:
    """Возвращает таймзону пользователя из БД, по умолчанию Europe/Moscow."""
    tz = (user_db or {}).get("timezone") or "Europe/Moscow"
    return ZoneInfo(tz)


def _iso_range_today(tz: ZoneInfo) -> tuple[str, str]:
    """Возвращает границы сегодняшнего дня в ISO 8601 с TZ."""
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _iso_range_tomorrow(tz: ZoneInfo) -> tuple[str, str]:
    """Возвращает границы завтрашнего дня в ISO 8601 с TZ."""
    now = datetime.now(tz)
    start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _iso_range_week(tz: ZoneInfo) -> tuple[str, str]:
    """Возвращает диапазон на 7 суток от начала сегодняшнего дня."""
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return start.isoformat(), end.isoformat()


def _format_task_line(t: dict, tz: ZoneInfo) -> str:
    """Одна строка задачи для отдельного сообщения с кнопками.
    Пример: «⬜ [6] 🔸 Позвонить Ивану | до 08.03 09:30 (через 9ч 26м)».
    """
    from datetime import datetime as _dt
    status = "✅" if t.get("is_done") else "⬜"
    pr = {1: "🔺", 3: "🔹"}.get(int(t.get("priority", 2) or 2), "🔸")
    due_tail = ""
    if t.get("due_datetime"):
        try:
            dt = _dt.fromisoformat(t["due_datetime"])
            if dt.tzinfo is None:
                # Нет TZ в строке — считаем локальным временем пользователя
                dt = dt.replace(tzinfo=tz)
            dt = dt.astimezone(tz)
            now = _dt.now(tz)
            delta = dt - now
            sign = 1 if delta.total_seconds() >= 0 else -1
            sec = int(abs(delta.total_seconds()))
            d, sec = divmod(sec, 86400)
            h, sec = divmod(sec, 3600)
            m, _ = divmod(sec, 60)
            parts = []
            if d:
                parts.append(f"{d}д")
            if h:
                parts.append(f"{h}ч")
            if m or not parts:
                parts.append(f"{m}м")
            when = dt.strftime('%d.%m %H:%M')
            if sign > 0:
                due_tail = f" | до {when} (через {' '.join(parts)})"
            else:
                due_tail = f" | ⛔ просрочено {' '.join(parts)}"
        except Exception:
            due_tail = f" | до {t['due_datetime']}"
    desc = f" — {t['description']}" if t.get("description") else ""
    return f"{status} [{t['id']}] {pr} {t['title']}{due_tail}{desc}"


def _task_kb(task_id: int) -> InlineKeyboardMarkup:
    """Инлайн-кнопки под конкретной задачей: Выполнено / Перенести / Изменить."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="✅ Выполнено",
                callback_data=f"task_done_list:single:{task_id}",
            ),
            InlineKeyboardButton(
                text="⏱ Перенести",
                callback_data=f"postpone:single:{task_id}:choose",
            ),
            InlineKeyboardButton(
                text="✏️ Изменить",
                callback_data=f"edit:single:{task_id}",
            ),
        ]]
    )


@router.message(F.text == "Задачи")
async def enter_tasks_menu(message: Message):
    """Вход в раздел задач: показываем меню управления задачами."""
    await message.answer("Раздел «Задачи». Выберите действие:", reply_markup=tasks_menu_kb())


@router.message(F.text == "📋 Список")
async def list_all_tasks(message: Message, user_db: dict | None = None):
    """Показывает все невыполненные задачи пользователя."""
    user_id = (user_db or {}).get("telegram_id") or message.from_user.id
    tz = _tz(user_db)
    tasks = await storage.list_tasks(user_id=user_id, include_done=False)
    if not tasks:
        await message.answer("Список задач пуст. Нажми «➕ Добавить», чтобы создать первую задачу.")
        return
    await message.answer(f"Все задачи ({len(tasks)}):")
    for t in tasks[:50]:
        await message.answer(_format_task_line(t, tz), reply_markup=_task_kb(int(t["id"])))


@router.message(F.text == "📅 Сегодня")
async def list_today(message: Message, user_db: dict | None = None):
    """Показывает задачи с дедлайном сегодня (без задач без дедлайна)."""
    user_id = (user_db or {}).get("telegram_id") or message.from_user.id
    tz = _tz(user_db)
    date_from, date_to = _iso_range_today(tz)
    logger.info("Сегодня user=%s tz=%s range=%s..%s", user_id, tz, date_from, date_to)
    tasks = await storage.list_tasks_by_period(user_id=user_id, date_from=date_from, date_to=date_to, include_done=False)
    # Фильтруем только задачи с конкретным дедлайном (без "OR due IS NULL")
    tasks = [t for t in tasks if t.get("due_datetime")]
    logger.info("Сегодня user=%s найдено=%d задач", user_id, len(tasks))
    if not tasks:
        await message.answer("На сегодня задач нет.")
        return
    await message.answer(f"Сегодня ({len(tasks)}):")
    for t in tasks[:50]:
        await message.answer(_format_task_line(t, tz), reply_markup=_task_kb(int(t["id"])))


@router.message(F.text == "📆 Завтра")
async def list_tomorrow(message: Message, user_db: dict | None = None):
    """Показывает задачи на завтрашний день."""
    user_id = (user_db or {}).get("telegram_id") or message.from_user.id
    tz = _tz(user_db)
    date_from, date_to = _iso_range_tomorrow(tz)
    tasks = await storage.list_tasks_by_period(user_id=user_id, date_from=date_from, date_to=date_to, include_done=False)
    # Только задачи с явным дедлайном
    tasks = [t for t in tasks if t.get("due_datetime")]
    if not tasks:
        await message.answer("На завтра задач нет.")
        return
    await message.answer(f"Завтра ({len(tasks)}):")
    for t in tasks[:50]:
        await message.answer(_format_task_line(t, tz), reply_markup=_task_kb(int(t["id"])))


@router.message(F.text == "🗓 На неделю")
async def list_week(message: Message, user_db: dict | None = None):
    """Показывает задачи на ближайшие 7 дней (только с дедлайном)."""
    user_id = (user_db or {}).get("telegram_id") or message.from_user.id
    tz = _tz(user_db)
    date_from, date_to = _iso_range_week(tz)
    tasks = await storage.list_tasks_by_period(user_id=user_id, date_from=date_from, date_to=date_to, include_done=False)
    # Только задачи с явным дедлайном (задачи без срока — в разделе «∅ Без срока»)
    tasks = [t for t in tasks if t.get("due_datetime")]
    if not tasks:
        await message.answer("На неделю задач нет.")
        return
    await message.answer(f"На неделе ({len(tasks)}):")
    for t in tasks[:50]:
        await message.answer(_format_task_line(t, tz), reply_markup=_task_kb(int(t["id"])))


@router.message(F.text == "∅ Без срока")
async def list_no_due(message: Message, user_db: dict | None = None):
    """Показывает невыполненные задачи без дедлайна."""
    user_id = (user_db or {}).get("telegram_id") or message.from_user.id
    tz = _tz(user_db)
    tasks = await storage.list_tasks_no_due(user_id=user_id, include_done=False)
    if not tasks:
        await message.answer("Задач без срока нет.")
        return
    await message.answer(f"Без срока ({len(tasks)}):")
    for t in tasks[:50]:
        await message.answer(_format_task_line(t, tz), reply_markup=_task_kb(int(t["id"])))


@router.message(F.text == "➕ Добавить")
async def add_hint(message: Message):
    """Подсказка по добавлению: дальше текст пойдёт в общий обработчик и разберётся агентом."""
    await message.answer("""Пришлите задачу в свободной форме, например:
• Подготовить отчёт до завтра 15:00
• Купить билеты сегодня в 20:00
Можно добавить описание после двоеточия: 'Встреча с Анной: обсудить контракт'""")


@router.message(F.text == "⬅️ Назад")
async def back_to_main(message: Message):
    """Возврат в главное меню бота."""
    await message.answer("Главное меню:", reply_markup=main_menu_kb())
