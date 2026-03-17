"""
Coaching API — роуты для целей (Goals) и этапов (Milestones).

Группы endpoints:
  GET/POST /goals             — список + создание
  GET/PUT/DELETE /goals/{id}  — CRUD одной цели
  POST /goals/{id}/freeze|resume|restart|achieve — действия над целью
  GET  /goals/{id}/analytics  — аналитика по цели
  GET/POST /milestones        — этапы цели
  POST /milestones/{id}/complete
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
    GoalCreateDto,
    GoalUpdateDto,
    GoalOut,
    MilestoneCreateDto,
    MilestoneOut,
)

# Отдельный роутер без prefix — prefix задаётся в coaching.py через include_router
router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# GOALS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/goals", response_model=List[GoalOut])
async def list_goals(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Список целей с фильтром по статусу (active|achieved|archived|all)."""
    return await cs.get_goals(db, current_user.telegram_id, status=status)


@router.post("/goals", response_model=GoalOut, status_code=201)
async def create_goal(
    body: GoalCreateDto,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Создать новую цель."""
    goal = await cs.create_goal(db, current_user.telegram_id, **body.model_dump(exclude_none=True))
    await db.commit()
    return goal


@router.get("/goals/{goal_id}", response_model=GoalOut)
async def get_goal(
    goal_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    goal = await cs.get_goal(db, goal_id, current_user.telegram_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.put("/goals/{goal_id}", response_model=GoalOut)
async def update_goal(
    goal_id: int,
    body: GoalUpdateDto,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    goal = await cs.update_goal(db, goal_id, current_user.telegram_id, **body.model_dump(exclude_none=True))
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    await db.commit()
    return goal


@router.delete("/goals/{goal_id}", status_code=204)
async def delete_goal(
    goal_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import delete as sql_delete
    from db.models import Goal
    # Удаляем цель пользователя по id и user_id (защита от чужих данных)
    await db.execute(
        sql_delete(Goal).where(Goal.id == goal_id, Goal.user_id == current_user.telegram_id)
    )
    await db.commit()


@router.post("/goals/{goal_id}/freeze", response_model=GoalOut)
async def freeze_goal(
    goal_id: int,
    reason: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Заморозить цель."""
    goal = await cs.update_goal(db, goal_id, current_user.telegram_id, is_frozen=True, frozen_reason=reason)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    await db.commit()
    return goal


@router.post("/goals/{goal_id}/resume", response_model=GoalOut)
async def resume_goal(
    goal_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Возобновить замороженную цель."""
    goal = await cs.update_goal(db, goal_id, current_user.telegram_id, is_frozen=False, frozen_reason=None)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    await db.commit()
    return goal


@router.post("/goals/{goal_id}/restart", response_model=GoalOut)
async def restart_goal(
    goal_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Сбросить прогресс и перезапустить цель."""
    goal = await cs.update_goal(db, goal_id, current_user.telegram_id,
                                status="active", progress_pct=0, is_frozen=False)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    await db.commit()
    return goal


@router.post("/goals/{goal_id}/achieve", response_model=GoalOut)
async def achieve_goal(
    goal_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Отметить цель как достигнутую."""
    goal = await cs.update_goal(db, goal_id, current_user.telegram_id,
                                status="achieved", progress_pct=100)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    await db.commit()
    return goal


@router.get("/goals/{goal_id}/analytics")
async def goal_analytics(
    goal_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Аналитика по цели: checkins история, прогресс, stuck-дни."""
    goal = await cs.get_goal(db, goal_id, current_user.telegram_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    milestones = await cs.get_milestones(db, goal_id, current_user.telegram_id)

    # Прямой запрос check-in для конкретной цели
    from sqlalchemy import select as _sel3
    from db.models import GoalCheckin as _GC3
    _r3 = await db.execute(
        _sel3(_GC3).where(_GC3.goal_id == goal_id, _GC3.user_id == current_user.telegram_id)
        .order_by(_GC3.created_at.desc()).limit(10)
    )
    goal_checkins = list(_r3.scalars().all())
    done_ms = [m for m in milestones if m.status == "done"]
    return {
        "goal_id": goal_id,
        "title": goal.title,
        "progress_pct": goal.progress_pct,
        "milestones_total": len(milestones),
        "milestones_done": len(done_ms),
        "checkins_count": len(goal_checkins),
        "last_checkin": goal_checkins[0].created_at.isoformat() if goal_checkins else None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# MILESTONES
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/milestones", response_model=List[MilestoneOut])
async def list_milestones(
    goal_id: int = Query(...),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await cs.get_milestones(db, goal_id, current_user.telegram_id)


@router.post("/milestones", response_model=MilestoneOut, status_code=201)
async def create_milestone(
    body: MilestoneCreateDto,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Извлекаем goal_id из body — cs.create_milestone(session, goal_id, user_id, **kwargs)
    _ms_data = body.model_dump(exclude_none=True)
    _ms_goal_id = _ms_data.pop("goal_id", 0)
    # Переименовываем order_index -> sort_order (поле модели GoalMilestone)
    if "order_index" in _ms_data:
        _ms_data["sort_order"] = _ms_data.pop("order_index")
    m = await cs.create_milestone(db, _ms_goal_id, current_user.telegram_id, **_ms_data)
    await db.commit()
    return m


@router.post("/milestones/{milestone_id}/complete", response_model=MilestoneOut)
async def complete_milestone(
    milestone_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    m = await cs.complete_milestone(db, milestone_id, current_user.telegram_id)
    if not m:
        raise HTTPException(status_code=404, detail="Milestone not found")
    await db.commit()
    return m
