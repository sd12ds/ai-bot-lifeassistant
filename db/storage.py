"""
Хранилище пользовательских данных через SQLAlchemy 2.x async.
Все функции сохраняют прежние сигнатуры — бот работает без изменений.
БД: PostgreSQL через SQLAlchemy async (asyncpg).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, and_, or_, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import DATABASE_URL
from db.models import (
    User, Task, Calendar, Reminder, NotificationLog,
    CrmContact, CrmDeal,
)
from db.session import AsyncSessionLocal
from db.recurrence import generate_occurrence_dicts


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _user_to_dict(u: User) -> dict:
    """Конвертирует ORM-объект User в словарь (обратная совместимость с ботом)."""
    return {
        "telegram_id": u.telegram_id,
        "mode": u.mode,
        "timezone": u.timezone,
        "notification_offset_min": u.notification_offset_min,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def _task_to_dict(t: Task) -> dict:
    """Конвертирует ORM-объект Task в словарь (обратная совместимость с ботом)."""
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
        "recurrence_rule": t.recurrence_rule,
        "parent_task_id": t.parent_task_id,
        "event_type": t.event_type,
        "calendar_id": t.calendar_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


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


def _contact_to_dict(c: CrmContact) -> dict:
    return {
        "id": c.id, "user_id": c.user_id, "name": c.name,
        "phone": c.phone, "email": c.email, "notes": c.notes,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _deal_to_dict(d: CrmDeal) -> dict:
    return {
        "id": d.id, "user_id": d.user_id, "contact_id": d.contact_id,
        "title": d.title, "amount": d.amount, "status": d.status,
        "notes": d.notes,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


# ── Инициализация ─────────────────────────────────────────────────────────────

async def ensure_tables() -> None:
    """No-op: схема управляется через Alembic (PostgreSQL)."""
    pass


# ── Пользователи ──────────────────────────────────────────────────────────────

async def get_or_create_user(
    telegram_id: int,
    mode: str = "personal",
    timezone: str = "Europe/Moscow",
) -> dict:
    """Возвращает пользователя из БД, создаёт если не существует."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(telegram_id=telegram_id, mode=mode, timezone=timezone)
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return _user_to_dict(user)


async def get_user(telegram_id: int) -> dict | None:
    """Возвращает пользователя по telegram_id или None."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        return _user_to_dict(user) if user else None


async def update_user_settings(
    telegram_id: int,
    timezone: Optional[str] = None,
    mode: Optional[str] = None,
    notification_offset_min: Optional[int] = None,
) -> bool:
    """Обновляет настройки пользователя."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            return False
        if timezone is not None:
            user.timezone = timezone
        if mode is not None:
            user.mode = mode
        if notification_offset_min is not None:
            user.notification_offset_min = notification_offset_min
        await db.commit()
        return True


# ── Задачи ────────────────────────────────────────────────────────────────────

async def add_task(
    user_id: int,
    title: str,
    description: str = "",
    due_datetime: Optional[str] = None,
    priority: int = 2,
    remind_at: Optional[str] = None,
    start_at: Optional[str] = None,
    end_at: Optional[str] = None,
    is_all_day: bool = False,
    event_type: str = "task",
    calendar_id: Optional[int] = None,
    recurrence_rule: Optional[str] = None,
) -> int:
    """Создаёт задачу или событие и возвращает id.

    Если передан start_at — создаётся событие (event_type='event').
    Если передан due_datetime — задача с дедлайном (event_type='task').
    """
    async with AsyncSessionLocal() as db:
        # Парсим ISO-строки в datetime если переданы
        due_dt = _parse_iso(due_datetime)
        remind_dt = _parse_iso(remind_at)
        start_dt = _parse_iso(start_at)
        end_dt = _parse_iso(end_at)
        task = Task(
            user_id=user_id,
            title=title,
            description=description,
            due_datetime=due_dt,
            start_at=start_dt,
            end_at=end_dt,
            is_all_day=is_all_day,
            event_type=event_type,
            calendar_id=calendar_id,
            remind_at=remind_dt,
            priority=priority,
            recurrence_rule=recurrence_rule,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        # Если задана recurrence_rule — генерируем экземпляры на 30 дней
        if recurrence_rule:
            from db.storage import _task_to_dict
            template = _task_to_dict(task)
            occ_dicts = generate_occurrence_dicts(template, horizon_days=30)
            for occ in occ_dicts:
                occ_task = Task(
                    user_id=occ["user_id"],
                    title=occ["title"],
                    description=occ.get("description", ""),
                    event_type=occ.get("event_type", "task"),
                    priority=occ.get("priority", 2),
                    calendar_id=occ.get("calendar_id"),
                    is_all_day=occ.get("is_all_day", False),
                    parent_task_id=occ["parent_task_id"],
                    due_datetime=_parse_iso(occ.get("due_datetime")),
                    start_at=_parse_iso(occ.get("start_at")),
                    end_at=_parse_iso(occ.get("end_at")),
                    updated_at=datetime.now(timezone.utc),
                )
                db.add(occ_task)
            await db.commit()
        return task.id


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


async def list_tasks(user_id: int, include_done: bool = False) -> list[dict]:
    """Возвращает все задачи пользователя (шаблоны повторений скрыты)."""
    async with AsyncSessionLocal() as db:
        q = select(Task).where(Task.user_id == user_id)
        if not include_done:
            q = q.where(Task.is_done == False)
        # Скрываем шаблоны повторяющихся задач (recurrence_rule без parent_task_id)
        q = q.where(or_(Task.recurrence_rule.is_(None), Task.parent_task_id.isnot(None)))
        q = q.order_by(Task.due_datetime.nullslast(), Task.priority, Task.id)
        result = await db.execute(q)
        return [_task_to_dict(t) for t in result.scalars().all()]


async def list_tasks_by_period(
    user_id: int,
    date_from: str,
    date_to: str,
    include_done: bool = False,
) -> list[dict]:
    """Возвращает задачи И события в диапазоне [date_from, date_to).

    Задачи фильтруются по due_datetime, события — по start_at.
    """
    async with AsyncSessionLocal() as db:
        dt_from = _parse_iso(date_from)
        dt_to = _parse_iso(date_to)
        # PostgreSQL нативно работает с TIMESTAMPTZ — не нужно strip tzinfo
        # Ищем по due_datetime ИЛИ start_at в диапазоне
        q = select(Task).where(
            Task.user_id == user_id,
            or_(
                and_(Task.due_datetime.isnot(None), Task.due_datetime >= dt_from, Task.due_datetime < dt_to),
                and_(Task.start_at.isnot(None), Task.start_at >= dt_from, Task.start_at < dt_to),
            ),
        )
        if not include_done:
            q = q.where(Task.is_done == False)
        q = q.order_by(
            func.coalesce(Task.start_at, Task.due_datetime).asc(),
            Task.priority, Task.id,
        )
        result = await db.execute(q)
        return [_task_to_dict(t) for t in result.scalars().all()]


async def list_tasks_no_due(user_id: int, include_done: bool = False) -> list[dict]:
    """Возвращает задачи без дедлайна."""
    async with AsyncSessionLocal() as db:
        q = select(Task).where(
            Task.user_id == user_id,
            Task.due_datetime.is_(None),
        )
        if not include_done:
            q = q.where(Task.is_done == False)
        q = q.order_by(Task.priority, Task.id)
        result = await db.execute(q)
        return [_task_to_dict(t) for t in result.scalars().all()]


async def list_calendar_items(
    user_id: int,
    date_from: str,
    date_to: str,
    include_done: bool = False,
) -> list[dict]:
    """Возвращает ВСЕ записи (задачи + события) в диапазоне дат для календаря.

    Задачи фильтруются по due_datetime, события — по start_at.
    Результат отсортирован по времени.
    """
    async with AsyncSessionLocal() as db:
        dt_from = _parse_iso(date_from)
        dt_to = _parse_iso(date_to)
        # PostgreSQL нативно работает с TIMESTAMPTZ
        # Задачи по due_datetime ИЛИ события по start_at в диапазоне
        q = select(Task).where(
            Task.user_id == user_id,
            or_(
                and_(Task.due_datetime.isnot(None), Task.due_datetime >= dt_from, Task.due_datetime < dt_to),
                and_(Task.start_at.isnot(None), Task.start_at >= dt_from, Task.start_at < dt_to),
            ),
        )
        if not include_done:
            q = q.where(Task.is_done == False)
        # Сортируем по самому раннему времени (start_at или due_datetime)
        q = q.order_by(
            func.coalesce(Task.start_at, Task.due_datetime).asc(),
            Task.priority,
            Task.id,
        )
        result = await db.execute(q)
        return [_task_to_dict(t) for t in result.scalars().all()]


async def get_task(task_id: int, user_id: int) -> dict | None:
    """Возвращает задачу по id и user_id."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
        t = result.scalar_one_or_none()
        return _task_to_dict(t) if t else None


async def complete_task(task_id: int, user_id: int) -> bool:
    """Помечает задачу выполненной."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return False
        task.is_done = True
        task.status = "done"
        await db.commit()
        return True


async def delete_task(task_id: int, user_id: int) -> bool:
    """Удаляет задачу и отменяет связанные pending-напоминания."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return False
        await db.delete(task)
        await db.commit()
    # Отменяем pending-напоминания для удалённой задачи
    try:
        from db.reminders import cancel_pending_reminders_for_task
        await cancel_pending_reminders_for_task(user_id, task_id)
    except Exception:
        pass  # Не блокируем удаление если reminders недоступны
    return True


async def update_task_due(task_id: int, user_id: int, due_datetime: Optional[str]) -> bool:
    """Обновляет дедлайн задачи."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return False
        task.due_datetime = _parse_iso(due_datetime)
        await db.commit()
        return True


async def update_task_text(
    task_id: int, user_id: int, title: str, description: str = ""
) -> bool:
    """Обновляет заголовок и описание задачи."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return False
        task.title = title
        task.description = description
        await db.commit()
        return True


async def update_task_fields(task_id: int, user_id: int, **fields) -> bool:
    """Обновляет произвольные поля задачи/события.

    Поля с ISO-датами (due_datetime, start_at, end_at, remind_at)
    автоматически парсятся из строк.
    """
    # Список полей, которые содержат ISO-даты
    _iso_fields = {"due_datetime", "start_at", "end_at", "remind_at"}
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return False
        for key, value in fields.items():
            if not hasattr(task, key):
                continue
            # Парсим ISO-строки в datetime
            if key in _iso_fields and isinstance(value, str):
                value = _parse_iso(value)
            setattr(task, key, value)
        task.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return True


# ── Напоминания ───────────────────────────────────────────────────────────────

async def add_reminder(
    user_id: int,
    entity_type: str,
    entity_id: int,
    remind_at: str,
) -> int:
    """Создаёт напоминание и возвращает его id."""
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


async def get_pending_reminders(cutoff: str) -> list[dict]:
    """Возвращает неотправленные напоминания с remind_at <= cutoff."""
    async with AsyncSessionLocal() as db:
        cutoff_dt = _parse_iso(cutoff)
        result = await db.execute(
            select(Reminder).where(
                Reminder.is_sent == False,
                Reminder.remind_at <= cutoff_dt,
            ).order_by(Reminder.remind_at)
        )
        return [_reminder_to_dict(r) for r in result.scalars().all()]


async def mark_reminder_sent(
    reminder_id: int,
    telegram_message_id: Optional[int] = None,
) -> None:
    """Помечает напоминание как отправленное."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Reminder).where(Reminder.id == reminder_id)
        )
        reminder = result.scalar_one_or_none()
        if reminder:
            reminder.is_sent = True
            reminder.sent_at = datetime.now(timezone.utc)
            reminder.telegram_message_id = telegram_message_id
            await db.commit()


async def log_notification(
    reminder_id: int, user_id: int, message_text: str
) -> None:
    """Сохраняет запись в лог уведомлений."""
    async with AsyncSessionLocal() as db:
        log = NotificationLog(
            reminder_id=reminder_id,
            user_id=user_id,
            message_text=message_text,
        )
        db.add(log)
        await db.commit()


async def delete_reminders_for_task(task_id: int) -> None:
    """Удаляет все напоминания для задачи (при переносе)."""
    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(Reminder).where(
                Reminder.entity_type == "task",
                Reminder.entity_id == task_id,
                Reminder.is_sent == False,
            )
        )
        await db.commit()


# ── Повторяющиеся задачи: регенерация ─────────────────────────────────────────


async def create_occurrence_reminders(
    template_id: int, user_id: int, offset_seconds: int
) -> int:
    """Создаёт/обновляет напоминания для экземпляров повторяющейся задачи.

    offset_seconds — сколько секунд ДО дедлайна/начала нужно отправить напоминание.
    Вызывается после создания шаблонного напоминания в reminder_tools.
    """
    async with AsyncSessionLocal() as db:
        # Выбираем все экземпляры шаблона
        children = await db.execute(
            select(Task).where(
                Task.parent_task_id == template_id,
                Task.user_id == user_id,
            )
        )
        now_utc = datetime.now(timezone.utc)
        count = 0
        for child in children.scalars().all():
            # Якорное время экземпляра: start_at (событие) или due_datetime (задача)
            anchor = child.start_at or child.due_datetime
            if not anchor:
                continue
            # Вычисляем время напоминания
            occ_remind_dt = anchor - timedelta(seconds=offset_seconds)
            if occ_remind_dt.tzinfo is None:
                occ_remind_dt = occ_remind_dt.replace(tzinfo=timezone.utc)
            else:
                occ_remind_dt = occ_remind_dt.astimezone(timezone.utc)
            # Пропускаем прошедшие напоминания
            if occ_remind_dt <= now_utc:
                continue
            # Синхронизируем task.remind_at
            child.remind_at = occ_remind_dt
            # Upsert записи в reminders (не трогаем уже отправленные)
            existing = await db.execute(
                select(Reminder).where(
                    Reminder.user_id == user_id,
                    Reminder.entity_type == "task",
                    Reminder.entity_id == child.id,
                    Reminder.is_sent == False,
                )
            )
            rem = existing.scalar_one_or_none()
            if rem:
                rem.remind_at = occ_remind_dt  # обновляем если уже есть
            else:
                db.add(Reminder(
                    user_id=user_id,
                    entity_type="task",
                    entity_id=child.id,
                    remind_at=occ_remind_dt,
                ))
            count += 1
        if count:
            await db.commit()
        return count


async def regenerate_occurrences(
    template_id: int, user_id: int, horizon_days: int = 30
) -> int:
    """Догенерирует экземпляры для шаблона на горизонт.

    Возвращает количество созданных экземпляров.
    """
    async with AsyncSessionLocal() as db:
        # Загружаем шаблон
        result = await db.execute(
            select(Task).where(Task.id == template_id, Task.user_id == user_id)
        )
        template = result.scalar_one_or_none()
        if not template or not template.recurrence_rule:
            return 0
        # Получаем существующие экземпляры — их даты
        children = await db.execute(
            select(Task).where(Task.parent_task_id == template_id)
        )
        existing_dates = set()
        for c in children.scalars().all():
            ref = c.start_at or c.due_datetime
            if ref:
                existing_dates.add(ref.strftime("%Y-%m-%d %H:%M"))
        # Генерируем новые экземпляры
        tmpl_dict = _task_to_dict(template)
        occ_dicts = generate_occurrence_dicts(tmpl_dict, horizon_days, existing_dates)
        count = 0
        for occ in occ_dicts:
            occ_task = Task(
                user_id=occ["user_id"],
                title=occ["title"],
                description=occ.get("description", ""),
                event_type=occ.get("event_type", "task"),
                priority=occ.get("priority", 2),
                calendar_id=occ.get("calendar_id"),
                is_all_day=occ.get("is_all_day", False),
                parent_task_id=occ["parent_task_id"],
                due_datetime=_parse_iso(occ.get("due_datetime")),
                start_at=_parse_iso(occ.get("start_at")),
                end_at=_parse_iso(occ.get("end_at")),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(occ_task)
            count += 1
        if count:
            await db.commit()
            # Создаём напоминания для экземпляров на основе offset шаблона.
            # Ищем offset двумя способами: task.remind_at или запись в reminders.
            anchor_tmpl = template.start_at or template.due_datetime
            if anchor_tmpl:
                offset_sec = 0
                # Способ 1: remind_at на самом шаблоне
                if template.remind_at:
                    offset_sec = int(
                        (anchor_tmpl - template.remind_at).total_seconds()
                    )
                # Способ 2: запись в reminders (fallback — remind_at может быть NULL)
                if offset_sec <= 0:
                    tmpl_rem = await db.execute(
                        select(Reminder).where(
                            Reminder.entity_type == "task",
                            Reminder.entity_id == template_id,
                            Reminder.user_id == user_id,
                        ).order_by(Reminder.id.desc()).limit(1)
                    )
                    rem_row = tmpl_rem.scalar_one_or_none()
                    if rem_row and rem_row.remind_at:
                        offset_sec = int(
                            (anchor_tmpl - rem_row.remind_at).total_seconds()
                        )
                # Способ 3: дефолт из user_settings (notification_offset_min)
                if offset_sec <= 0:
                    try:
                        from db import reminders as rdb
                        us = await rdb.get_user_settings(user_id)
                        offset_sec = int(us.get("notification_offset_min", 15)) * 60
                    except Exception:
                        offset_sec = 15 * 60  # 15 мин по умолчанию

                if offset_sec > 0:
                    await create_occurrence_reminders(
                        template_id=template_id,
                        user_id=user_id,
                        offset_seconds=offset_sec,
                    )
        return count


async def skip_occurrence(task_id: int, user_id: int) -> bool:
    """Пропускает (удаляет) экземпляр повторяющейся задачи."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Task).where(
                Task.id == task_id,
                Task.user_id == user_id,
                Task.parent_task_id.isnot(None),  # Только экземпляры
            )
        )
        task = result.scalar_one_or_none()
        if not task:
            return False
        await db.delete(task)
        await db.commit()
        return True


async def get_all_recurring_templates() -> list[dict]:
    """Возвращает все шаблоны (для cron-регенерации)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Task).where(
                Task.recurrence_rule.isnot(None),
                Task.parent_task_id.is_(None),
            )
        )
        return [_task_to_dict(t) for t in result.scalars().all()]


# ── Календари ─────────────────────────────────────────────────────────────────

def _calendar_to_dict(c: Calendar) -> dict:
    """Конвертирует ORM-объект Calendar в словарь."""
    return {
        "id": c.id,
        "user_id": c.user_id,
        "name": c.name,
        "color": c.color,
        "is_default": c.is_default,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


async def create_calendar(
    user_id: int, name: str, color: str = "#5B8CFF"
) -> int:
    """Создаёт календарь и возвращает его id."""
    async with AsyncSessionLocal() as db:
        cal = Calendar(user_id=user_id, name=name, color=color)
        db.add(cal)
        await db.commit()
        await db.refresh(cal)
        return cal.id


async def list_calendars(user_id: int) -> list[dict]:
    """Возвращает все календари пользователя."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Calendar)
            .where(Calendar.user_id == user_id)
            .order_by(Calendar.is_default.desc(), Calendar.name)
        )
        return [_calendar_to_dict(c) for c in result.scalars().all()]


# ── CRM: контакты ─────────────────────────────────────────────────────────────

async def add_contact(
    user_id: int, name: str, phone: str = "",
    email: str = "", company: str = "", notes: str = "",
) -> int:
    async with AsyncSessionLocal() as db:
        contact = CrmContact(
            user_id=user_id, name=name, phone=phone,
            email=email, notes=notes,
        )
        db.add(contact)
        await db.commit()
        await db.refresh(contact)
        return contact.id


async def find_contacts(user_id: int, query: str) -> list[dict]:
    async with AsyncSessionLocal() as db:
        q = select(CrmContact).where(
            CrmContact.user_id == user_id,
            or_(
                CrmContact.name.ilike(f"%{query}%"),
                CrmContact.phone.ilike(f"%{query}%"),
                CrmContact.email.ilike(f"%{query}%"),
            )
        )
        result = await db.execute(q)
        return [_contact_to_dict(c) for c in result.scalars().all()]


async def list_contacts(user_id: int) -> list[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CrmContact).where(CrmContact.user_id == user_id).order_by(CrmContact.name)
        )
        return [_contact_to_dict(c) for c in result.scalars().all()]


# ── CRM: сделки ───────────────────────────────────────────────────────────────

async def add_deal(
    user_id: int, title: str, contact_id: Optional[int] = None,
    amount: float = 0.0, notes: str = "",
) -> int:
    async with AsyncSessionLocal() as db:
        deal = CrmDeal(
            user_id=user_id, title=title,
            contact_id=contact_id, amount=amount, notes=notes,
        )
        db.add(deal)
        await db.commit()
        await db.refresh(deal)
        return deal.id


async def list_deals(user_id: int, status: Optional[str] = None) -> list[dict]:
    async with AsyncSessionLocal() as db:
        q = select(CrmDeal).where(CrmDeal.user_id == user_id)
        if status:
            q = q.where(CrmDeal.status == status)
        result = await db.execute(q.order_by(CrmDeal.created_at.desc()))
        return [_deal_to_dict(d) for d in result.scalars().all()]


async def update_deal_status(deal_id: int, user_id: int, status: str) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CrmDeal).where(CrmDeal.id == deal_id, CrmDeal.user_id == user_id)
        )
        deal = result.scalar_one_or_none()
        if not deal:
            return False
        deal.status = status
        await db.commit()
        return True


# ── Алиасы для обратной совместимости ─────────────────────────────────────────

async def set_user_mode(telegram_id: int, mode: str) -> bool:
    """Алиас: устанавливает режим пользователя (personal/business)."""
    return await update_user_settings(telegram_id, mode=mode)


async def init_db() -> None:
    """Алиас для ensure_tables — совместимость с main.py."""
    await ensure_tables()
