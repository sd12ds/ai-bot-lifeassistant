"""
CRUD роутер для календарей (/api/calendars).
Операции изолированы по user_id текущего пользователя.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from db.models import Calendar, User
from db.session import get_session

router = APIRouter(prefix="/calendars", tags=["calendars"])


# ── Pydantic-схемы ────────────────────────────────────────────────────────────

class CalendarOut(BaseModel):
    """Схема ответа — данные календаря."""
    id: int
    name: str
    color: str
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CalendarCreate(BaseModel):
    """Схема создания календаря."""
    name: str
    color: str = "#5B8CFF"


class CalendarPatch(BaseModel):
    """Схема обновления календаря."""
    name: Optional[str] = None
    color: Optional[str] = None


# ── Эндпоинты ─────────────────────────────────────────────────────────────────

@router.get("", response_model=List[CalendarOut])
async def list_calendars(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Возвращает все календари пользователя."""
    result = await db.execute(
        select(Calendar)
        .where(Calendar.user_id == current_user.telegram_id)
        .order_by(Calendar.is_default.desc(), Calendar.name)
    )
    return result.scalars().all()


@router.post("", response_model=CalendarOut, status_code=status.HTTP_201_CREATED)
async def create_calendar(
    body: CalendarCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Создаёт новый календарь."""
    cal = Calendar(
        user_id=current_user.telegram_id,
        name=body.name,
        color=body.color,
    )
    db.add(cal)
    await db.commit()
    await db.refresh(cal)
    return cal


@router.patch("/{calendar_id}", response_model=CalendarOut)
async def patch_calendar(
    calendar_id: int,
    body: CalendarPatch,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Частично обновляет календарь (только свой)."""
    result = await db.execute(
        select(Calendar).where(
            Calendar.id == calendar_id,
            Calendar.user_id == current_user.telegram_id,
        )
    )
    cal = result.scalar_one_or_none()
    if not cal:
        raise HTTPException(status_code=404, detail="Calendar not found")
    # Применяем только переданные поля
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(cal, field, value)
    await db.commit()
    await db.refresh(cal)
    return cal


@router.delete("/{calendar_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_calendar(
    calendar_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Удаляет календарь (только свой, нельзя дефолтный)."""
    result = await db.execute(
        select(Calendar).where(
            Calendar.id == calendar_id,
            Calendar.user_id == current_user.telegram_id,
        )
    )
    cal = result.scalar_one_or_none()
    if not cal:
        raise HTTPException(status_code=404, detail="Calendar not found")
    if cal.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default calendar")
    await db.delete(cal)
    await db.commit()
