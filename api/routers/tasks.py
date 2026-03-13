"""
CRUD роутер для задач (/api/tasks).
Все операции изолированы по user_id текущего пользователя.
Поддерживаются фильтры: period (today|week|all|nodate) и status (todo|done|all).
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from db.models import Task, User, Reminder
from db.session import get_session

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _sync_reminder(
    db: AsyncSession,
    user_id: int,
    task_id: int,
    remind_at: Optional[datetime],
) -> None:
    """Синхронизирует запись в reminders с Task.remind_at.

    Если remind_at задан — upsert записи.
    Если remind_at = None — удаляем неотправленный reminder.
    """
    result = await db.execute(
        select(Reminder).where(
            Reminder.user_id == user_id,
            Reminder.entity_type == "task",
            Reminder.entity_id == task_id,
            Reminder.is_sent == False,  # не трогаем уже отправленные
        )
    )
    existing = result.scalar_one_or_none()

    if remind_at is None:
        # Удаляем если есть
        if existing:
            await db.delete(existing)
    else:
        if existing:
            # Обновляем время
            existing.remind_at = remind_at
        else:
            # Создаём новый
            db.add(Reminder(
                user_id=user_id,
                entity_type="task",
                entity_id=task_id,
                remind_at=remind_at,
            ))


# ── Pydantic-схемы ────────────────────────────────────────────────────────────

class TaskOut(BaseModel):
    """Схема ответа — данные задачи."""
    id: int
    title: str
    description: str
    event_type: str
    status: str
    priority: int
    tags: list
    due_datetime: Optional[datetime]
    start_at: Optional[datetime]
    end_at: Optional[datetime]
    is_all_day: bool
    remind_at: Optional[datetime]
    recurrence_rule: Optional[str]
    parent_task_id: Optional[int]
    is_done: bool
    calendar_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    """Схема создания задачи."""
    title: str
    description: str = ""
    priority: int = 2
    tags: list = []
    due_datetime: Optional[datetime] = None
    start_at: Optional[datetime] = None   # начало интервала
    end_at: Optional[datetime] = None     # конец интервала
    remind_at: Optional[datetime] = None


class TaskPatch(BaseModel):
    """Схема частичного обновления задачи."""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    tags: Optional[list] = None
    is_done: Optional[bool] = None
    due_datetime: Optional[datetime] = None
    start_at: Optional[datetime] = None   # начало интервала
    end_at: Optional[datetime] = None     # конец интервала
    remind_at: Optional[datetime] = None


# ── Эндпоинты ─────────────────────────────────────────────────────────────────

@router.get("", response_model=List[TaskOut])
async def list_tasks(
    period: str = Query("all", description="Фильтр по периоду: all | today | week | nodate"),
    task_status: str = Query("all", alias="status", description="Фильтр по статусу: all | todo | done"),
    view: str = Query("list", description="Режим отображения: list | calendar"),
    date_from: Optional[str] = Query(None, description="Начало диапазона ISO (для view=calendar)"),
    date_to: Optional[str] = Query(None, description="Конец диапазона ISO (для view=calendar)"),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Возвращает задачи пользователя.

    view=list (по умолчанию): фильтр по period + status (прежнее поведение).
    view=calendar: возвращает ВСЕ записи (задачи + события) в диапазоне date_from..date_to.
    """
    # Берём таймзону пользователя для корректного определения «сегодня»
    user_tz = ZoneInfo(current_user.timezone or "Europe/Moscow")
    now_local = datetime.now(user_tz)

    # ── Calendar view: записи в произвольном диапазоне ──
    if view == "calendar":
        # Дефолтный диапазон — текущая неделя (tz-aware для корректного сравнения с timestamptz)
        if date_from:
            dt_from = datetime.fromisoformat(date_from)
            if dt_from.tzinfo is None:
                dt_from = dt_from.replace(tzinfo=timezone.utc)
        else:
            dt_from = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        if date_to:
            dt_to = datetime.fromisoformat(date_to)
            if dt_to.tzinfo is None:
                dt_to = dt_to.replace(tzinfo=timezone.utc)
        else:
            dt_to = dt_from + timedelta(days=7)


        # Фильтр: due_datetime ИЛИ start_at попадает в диапазон
        time_cond = or_(
            and_(Task.due_datetime.isnot(None), Task.due_datetime >= dt_from, Task.due_datetime < dt_to),
            and_(Task.start_at.isnot(None), Task.start_at >= dt_from, Task.start_at < dt_to),
        )
        conditions = [Task.user_id == current_user.telegram_id, time_cond]
        if task_status == "todo":
            conditions.append(Task.is_done == False)
        elif task_status == "done":
            conditions.append(Task.is_done == True)

        stmt = (
            select(Task)
            .where(and_(*conditions))
            .order_by(func.coalesce(Task.start_at, Task.due_datetime).asc(), Task.priority, Task.id)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    # ── List view: прежнее поведение ──
    conditions = [
        Task.user_id == current_user.telegram_id,
        # Скрываем шаблоны повторяющихся задач (показываем только экземпляры)
        or_(Task.recurrence_rule.is_(None), Task.parent_task_id.isnot(None)),
    ]

    # Фильтр по статусу (is_done)
    if task_status == "todo":
        conditions.append(Task.is_done == False)
    elif task_status == "done":
        conditions.append(Task.is_done == True)

    # Фильтр по периоду дедлайна.
    # SQLite хранит datetime как naive TEXT (локальное время) —
    # границы тоже делаем naive для корректного TEXT-сравнения.
    if period == "today":
        start = now_local.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        end = start + timedelta(days=1)
        # Фильтруем по due_datetime ИЛИ start_at
        conditions.append(or_(
            and_(Task.due_datetime.isnot(None), Task.due_datetime >= start, Task.due_datetime < end),
            and_(Task.start_at.isnot(None), Task.start_at >= start, Task.start_at < end),
        ))
    elif period == "week":
        start = now_local.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        end = start + timedelta(days=7)
        # Фильтруем по due_datetime ИЛИ start_at
        conditions.append(or_(
            and_(Task.due_datetime.isnot(None), Task.due_datetime >= start, Task.due_datetime < end),
            and_(Task.start_at.isnot(None), Task.start_at >= start, Task.start_at < end),
        ))
    elif period == "nodate":
        conditions.append(and_(Task.due_datetime.is_(None), Task.start_at.is_(None)))

    stmt = (
        select(Task)
        .where(and_(*conditions))
        .order_by(Task.is_done.asc(), Task.priority.asc(), Task.due_datetime.asc().nullslast())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Создаёт новую задачу для текущего пользователя."""
    now = datetime.now(timezone.utc)
    task = Task(
        user_id=current_user.telegram_id,
        title=body.title,
        description=body.description,
        priority=body.priority,
        tags=body.tags,
        due_datetime=body.due_datetime,
        start_at=body.start_at,
        end_at=body.end_at,
        remind_at=body.remind_at,
        updated_at=now,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    # Синхронизируем reminder если задан индивидуальный remind_at
    if body.remind_at is not None:
        await _sync_reminder(db, current_user.telegram_id, task.id, body.remind_at)
        await db.commit()
    return task


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Возвращает задачу по ID (только своя)."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == current_user.telegram_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskOut)
async def patch_task(
    task_id: int,
    body: TaskPatch,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Частично обновляет задачу (только своя)."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == current_user.telegram_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Применяем только переданные поля
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(task, field, value)

    # Синхронизируем статус: if is_done=True → status='done'
    if body.is_done is True and task.status not in ("done", "cancelled"):
        task.status = "done"
    elif body.is_done is False and task.status == "done":
        task.status = "todo"

    task.updated_at = datetime.now(timezone.utc)
    # Синхронизируем reminder если поле remind_at передано явно
    if "remind_at" in body.model_dump(exclude_unset=True):
        await _sync_reminder(db, current_user.telegram_id, task_id, body.remind_at)
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Удаляет задачу (только своя)."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == current_user.telegram_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.commit()
