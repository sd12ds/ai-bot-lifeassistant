"""
Coaching API — роуты для привычек (Habits).

Группы endpoints:
  GET/POST /habits                    — список + создание
  GET      /habits/templates          — библиотека шаблонов
  GET/PUT  /habits/{id}               — CRUD одной привычки
  POST     /habits/{id}/log           — залогировать выполнение
  POST     /habits/{id}/miss          — отметить пропуск
  POST     /habits/{id}/pause|resume  — пауза / возобновление
  GET      /habits/{id}/analytics     — статистика привычки
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from db.models import User
from db.session import get_session
import db.coaching_storage as cs

from .coaching_schemas import (
    HabitCreateDto,
    HabitUpdateDto,
    HabitOut,
)

# Отдельный роутер без prefix — prefix задаётся в coaching.py через include_router
router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# HABITS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/habits", response_model=List[HabitOut])
async def list_habits(
    is_active: Optional[bool] = Query(None),
    goal_id: Optional[int] = Query(None),   # фильтр по привязанной цели
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await cs.get_habits(db, current_user.telegram_id, is_active=is_active, goal_id=goal_id)


@router.post("/habits", response_model=HabitOut, status_code=201)
async def create_habit(
    body: HabitCreateDto,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from db.models import Habit
    # Создаём привычку напрямую — у модели нет хелпера в coaching_storage
    h = Habit(user_id=current_user.telegram_id, **body.model_dump(exclude_none=True))
    db.add(h)
    await db.flush()
    await db.refresh(h)
    await db.commit()
    return h


@router.get("/habits/templates")
async def get_habit_templates(
    area: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list:
    """Библиотека готовых шаблонов привычек."""
    return await cs.get_habit_templates(db, area=area)


@router.get("/habits/{habit_id}", response_model=HabitOut)
async def get_habit(
    habit_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select
    from db.models import Habit
    # Запрос привычки с проверкой принадлежности пользователю
    r = await db.execute(select(Habit).where(Habit.id == habit_id, Habit.user_id == current_user.telegram_id))
    h = r.scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="Habit not found")
    return h


@router.put("/habits/{habit_id}", response_model=HabitOut)
async def update_habit(
    habit_id: int,
    body: HabitUpdateDto,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import update as sql_update, select
    from db.models import Habit
    await db.execute(
        sql_update(Habit)
        .where(Habit.id == habit_id, Habit.user_id == current_user.telegram_id)
        .values(**body.model_dump(exclude_none=True))
    )
    await db.commit()
    r = await db.execute(select(Habit).where(Habit.id == habit_id))
    return r.scalar_one()


@router.post("/habits/{habit_id}/log")
async def log_habit(
    habit_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Залогировать выполнение привычки."""
    habit = await cs.increment_habit_streak(db, habit_id, current_user.telegram_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    from db.models import HabitLog
    # Сохраняем запись в журнале привычки
    db.add(HabitLog(habit_id=habit_id, user_id=current_user.telegram_id))
    await db.commit()
    return {"streak": habit.current_streak, "is_record": habit.current_streak == habit.longest_streak}


@router.post("/habits/{habit_id}/miss")
async def miss_habit(
    habit_id: int,
    reason: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Отметить пропуск привычки."""
    habit = await cs.reset_habit_streak(db, habit_id, current_user.telegram_id, reason=reason or "пропуск")
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    await db.commit()
    return {"streak_reset": True, "previous_streak": habit.current_streak}


@router.post("/habits/{habit_id}/pause")
async def pause_habit(
    habit_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    from sqlalchemy import update as sql_update
    from db.models import Habit
    # Деактивируем привычку (пауза = is_active=False)
    await db.execute(
        sql_update(Habit).where(Habit.id == habit_id, Habit.user_id == current_user.telegram_id).values(is_active=False)
    )
    await db.commit()
    return {"paused": True}


@router.post("/habits/{habit_id}/resume")
async def resume_habit(
    habit_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    from sqlalchemy import update as sql_update
    from db.models import Habit
    # Возобновляем привычку (is_active=True)
    await db.execute(
        sql_update(Habit).where(Habit.id == habit_id, Habit.user_id == current_user.telegram_id).values(is_active=True)
    )
    await db.commit()
    return {"resumed": True}


@router.get("/habits/{habit_id}/analytics")
async def habit_analytics(
    habit_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Статистика привычки: streak history, completion rate, best/worst days."""
    from sqlalchemy import select
    from db.models import Habit, HabitLog
    r = await db.execute(select(Habit).where(Habit.id == habit_id, Habit.user_id == current_user.telegram_id))
    h = r.scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="Habit not found")
    # Последние 30 логов привычки
    logs_r = await db.execute(
        select(HabitLog).where(HabitLog.habit_id == habit_id)
        .order_by(HabitLog.logged_at.desc()).limit(30)
    )
    logs = logs_r.scalars().all()
    return {
        "habit_id": habit_id,
        "title": h.title,
        "current_streak": h.current_streak,
        "longest_streak": h.longest_streak,
        "total_completions": h.total_completions,
        "last_30_days": len(logs),
        "last_logged_at": h.last_logged_at.isoformat() if h.last_logged_at else None,
    }
