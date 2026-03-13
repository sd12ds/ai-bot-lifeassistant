"""
Модуль напоминаний — тонкая обёртка над db/storage.py.
Сохраняет прежний API для обратной совместимости (scheduler, handlers, tools).
Вся логика работает через SQLAlchemy async — PostgreSQL или SQLite.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update

from db.models import User, Task, Reminder
from db.session import AsyncSessionLocal


# ── Утилиты ───────────────────────────────────────────────────────────────────

async def ensure_schema() -> None:
    """No-op: схема управляется через Alembic."""
    pass


# ── Настройки пользователя ───────────────────────────────────────────────────

async def get_user_settings(telegram_id: int) -> dict:
    """Возвращает timezone и notification_offset_min пользователя."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            # Дефолты если пользователь ещё не создан
            return {"timezone": "Europe/Moscow", "notification_offset_min": 15}
        return {
            "timezone": user.timezone or "Europe/Moscow",
            "notification_offset_min": user.notification_offset_min or 15,
        }


async def set_user_timezone(telegram_id: int, tz: str) -> None:
    """Обновляет часовой пояс пользователя. Создаёт запись если нет."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user:
            # Обновляем существующего пользователя
            user.timezone = tz
        else:
            # Создаём нового пользователя с указанным TZ
            db.add(User(telegram_id=telegram_id, mode="personal", timezone=tz))
        await db.commit()


async def set_user_notification_offset(telegram_id: int, minutes: int) -> None:
    """Обновляет смещение напоминаний в минутах."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user:
            # Обновляем существующего пользователя
            user.notification_offset_min = int(minutes)
        else:
            # Создаём нового пользователя с указанным offset
            db.add(User(
                telegram_id=telegram_id,
                mode="personal",
                timezone="Europe/Moscow",
                notification_offset_min=int(minutes),
            ))
        await db.commit()


# ── Задачи (для scheduler) ───────────────────────────────────────────────────

async def get_task(task_id: int, user_id: int) -> Optional[dict]:
    """Возвращает задачу по id и user_id, либо None."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
        t = result.scalar_one_or_none()
        if not t:
            return None
        return {
            "id": t.id,
            "user_id": t.user_id,
            "title": t.title,
            "description": t.description or "",
            "due_datetime": t.due_datetime.isoformat() if t.due_datetime else None,
            "start_at": t.start_at.isoformat() if t.start_at else None,
            "end_at": t.end_at.isoformat() if t.end_at else None,
            "is_done": 1 if t.is_done else 0,
            "status": t.status,
            "priority": t.priority,
            "tags": t.tags or [],
            "remind_at": t.remind_at.isoformat() if t.remind_at else None,
            "event_type": t.event_type,
        }


# ── Напоминания ───────────────────────────────────────────────────────────────

async def add_reminder(
    user_id: int,
    entity_type: str,
    entity_id: int,
    remind_at: str,
) -> int:
    """Создаёт запись в reminders. remind_at — ISO 8601."""
    async with AsyncSessionLocal() as db:
        remind_dt = _parse_iso(remind_at)
        if not remind_dt:
            raise ValueError(f"Некорректная дата remind_at: {remind_at}")
        reminder = Reminder(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            remind_at=remind_dt,
        )
        db.add(reminder)
        await db.commit()
        await db.refresh(reminder)
        return reminder.id


async def get_pending_reminders(now_iso: str, limit: int = 200) -> list[dict]:
    """Все is_sent=0 напоминания с remind_at <= now_iso."""
    async with AsyncSessionLocal() as db:
        cutoff_dt = _parse_iso(now_iso)
        result = await db.execute(
            select(Reminder).where(
                Reminder.is_sent == False,
                Reminder.remind_at <= cutoff_dt,
            ).order_by(Reminder.remind_at).limit(limit)
        )
        return [_reminder_to_dict(r) for r in result.scalars().all()]


async def mark_reminder_sent(
    reminder_id: int,
    telegram_message_id: int | None = None,
) -> None:
    """Отмечает напоминание как отправленное."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Reminder).where(Reminder.id == reminder_id)
        )
        reminder = result.scalar_one_or_none()
        if reminder:
            # Помечаем отправленным
            reminder.is_sent = True
            reminder.sent_at = datetime.now(timezone.utc)
            if telegram_message_id is not None:
                reminder.telegram_message_id = telegram_message_id
            await db.commit()


# ── Управление напоминаниями для задач ────────────────────────────────────────

async def cancel_pending_reminders_for_task(user_id: int, task_id: int) -> int:
    """Отменяет (помечает отправленными) все pending-напоминания задачи."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Reminder).where(
                Reminder.user_id == user_id,
                Reminder.entity_type == "task",
                Reminder.entity_id == task_id,
                Reminder.is_sent == False,
            )
        )
        reminders = result.scalars().all()
        count = 0
        for r in reminders:
            # Помечаем как отправленное (отмена)
            r.is_sent = True
            r.sent_at = datetime.now(timezone.utc)
            count += 1
        if count:
            await db.commit()
        return count


async def schedule_reminder_for_task(user_id: int, task_id: int, due_iso: str) -> None:
    """Создаёт напоминание для задачи на момент (due - offset).
    Если время уже прошло — ставит на сейчас.
    """
    try:
        us = await get_user_settings(user_id)
        offset_min = int(us.get("notification_offset_min", 15))
        due_dt = datetime.fromisoformat(due_iso)
        # Вычисляем время напоминания: due - offset
        remind_dt = due_dt - timedelta(minutes=offset_min)
        remind_dt_utc = (
            remind_dt.astimezone(timezone.utc)
            if remind_dt.tzinfo
            else remind_dt.replace(tzinfo=timezone.utc)
        )
        now_utc = datetime.now(timezone.utc)
        # Если время уже прошло — ставим на сейчас
        safe_remind_at = remind_dt_utc if remind_dt_utc > now_utc else now_utc
        await add_reminder(
            user_id=user_id,
            entity_type="task",
            entity_id=task_id,
            remind_at=safe_remind_at.isoformat(),
        )
    except Exception:
        pass


# ── Утилиты ───────────────────────────────────────────────────────────────────

def _parse_iso(val: Optional[str]) -> Optional[datetime]:
    """Парсит ISO-строку в timezone-aware datetime."""
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _reminder_to_dict(r: Reminder) -> dict:
    """Конвертирует ORM-объект Reminder в словарь."""
    return {
        "id": r.id,
        "user_id": r.user_id,
        "entity_type": r.entity_type,
        "entity_id": r.entity_id,
        "remind_at": r.remind_at.isoformat() if r.remind_at else None,
        "is_sent": 1 if r.is_sent else 0,
        "sent_at": r.sent_at.isoformat() if r.sent_at else None,
        "telegram_message_id": r.telegram_message_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
