"""
Coaching API — роуты для dashboard, state, check-ins, reviews, profile, onboarding.

Группы endpoints:
  GET /dashboard             — агрегирующий endpoint для Mini App
  GET /state                 — текущее состояние пользователя
  POST/GET /checkins/*       — создание, история, today, by-date, calendar, patch
  GET /reviews               — список + latest
  GET/PUT /profile           — профиль коуча
  GET/POST /onboarding/*     — онбординг
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from db.models import User
from db.session import get_session
import db.coaching_storage as cs
from services.coaching_analytics import DROPOUT_RISK_HIGH_THRESHOLD
from services.coaching_engine import (
    compute_user_state,
    compute_risk_scores,
    compute_weekly_score,
)

from .coaching_schemas import (
    CheckInCreateDto,
    CheckInPatchDto,
    CheckInOut,
    ReviewOut,
    CoachingProfileUpdateDto,
    CoachingProfileOut,
    DashboardOut,
    OnboardingStepDto,
    OnboardingOut,
    _goal_to_dict,
    _habit_to_dict,
    SAMPLE_PROMPTS,
)

# Отдельный роутер без prefix — prefix задаётся в coaching.py через include_router
router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD — агрегирующий endpoint (§14.3)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DashboardOut:
    """
    Агрегирующий endpoint для главного экрана Mini App.

    Выполняет все запросы последовательно (asyncpg не поддерживает параллельные
    запросы на одном AsyncSession). Цель: latency <500ms.
    """
    user_id = current_user.telegram_id

    # asyncpg не поддерживает параллельные запросы на одном AsyncSession —
    # выполняем последовательно, чтобы избежать InterfaceError
    goals       = await cs.get_goals(db, user_id, status="active")
    habits      = await cs.get_habits(db, user_id, is_active=True)
    insights    = await cs.get_active_insights(db, user_id, limit=1)
    recs        = await cs.get_active_recommendations(db, user_id, limit=2)
    state_data  = await compute_user_state(db, user_id)
    risks       = await compute_risk_scores(db, user_id)
    weekly_score = await compute_weekly_score(db, user_id)

    state = state_data["state"]
    state_score = state_data["score"]

    # Топ-3 цели
    goals_active = [_goal_to_dict(g) for g in goals[:3]]

    # Привычки сегодня
    habits_today = [_habit_to_dict(h) for h in habits]

    # Инсайт
    top_insight = None
    if insights:
        i = insights[0]
        top_insight = {
            "id": i.id,
            "insight_type": i.insight_type,
            "severity": i.severity,
            "title": getattr(i, 'title', ''),
            "body": getattr(i, 'body', ''),
        }

    # Рекомендации
    recs_out = []
    for r in recs:
        recs_out.append({
            "id": r.id,
            "rec_type": r.rec_type,
            "title": r.title,
            "body": getattr(r, 'body', ''),
            "action_type": r.action_type,
        })

    # Sample prompts по состоянию пользователя
    prompts = SAMPLE_PROMPTS.get(state, SAMPLE_PROMPTS["default"])

    # Уровень риска дропаута для UI
    dropout_score = risks.get("dropout", 0.0)
    if dropout_score >= DROPOUT_RISK_HIGH_THRESHOLD:
        dropout_level = "critical"
    elif dropout_score >= 0.5:
        dropout_level = "high"
    elif dropout_score >= 0.3:
        dropout_level = "medium"
    elif dropout_score >= 0.1:
        dropout_level = "low"
    else:
        dropout_level = "none"

    return DashboardOut(
        state=state,
        state_score=state_score,
        habits_today=habits_today,
        goals_active=goals_active,
        top_insight=top_insight,
        recommendations=recs_out,
        weekly_score=weekly_score,
        nudge_pending=None,
        prompt_suggestions=prompts[:5],
        risks=risks,
        dropout_risk_level=dropout_level,
    )


# ══════════════════════════════════════════════════════════════════════════════
# STATE
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/state")
async def get_state(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Текущее whole-user state + risk scores."""
    user_id = current_user.telegram_id
    # asyncpg: последовательно — один AsyncSession, один conn
    state_data = await compute_user_state(db, user_id)
    risks      = await compute_risk_scores(db, user_id)
    return {**state_data, "risks": risks}


# ══════════════════════════════════════════════════════════════════════════════
# CHECK-INS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/checkins", response_model=CheckInOut, status_code=201)
async def create_checkin(
    body: CheckInCreateDto,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Создать новый чекин (привязан к дате и временному слоту)."""
    from datetime import date as _date_t
    data = body.model_dump(exclude_none=True)
    # Определяем check_date: из запроса или сегодня (Pydantic уже парсит str -> date)
    check_date_raw = data.pop("check_date", None)
    if isinstance(check_date_raw, _date_t):
        check_date_val = check_date_raw          # уже date-объект (Pydantic v2 coercion)
    elif isinstance(check_date_raw, str):
        try:
            check_date_val = _date_t.fromisoformat(check_date_raw)
        except ValueError:
            check_date_val = _date_t.today()
    else:
        check_date_val = _date_t.today()
    data["check_date"] = check_date_val

    goal_id_val = data.pop("goal_id", None)
    checkin = await cs.create_goal_checkin(db, goal_id_val, current_user.telegram_id, **data)
    await db.commit()
    return checkin


@router.get("/checkins/today")
async def get_today_checkin(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Проверить, был ли check-in сегодня."""
    from datetime import timezone
    # Прямой запрос последнего check-in пользователя (не требует goal_id)
    from sqlalchemy import select as _sel
    from db.models import GoalCheckin as _GC
    _r = await db.execute(
        _sel(_GC).where(_GC.user_id == current_user.telegram_id)
        .order_by(_GC.created_at.desc()).limit(1)
    )
    checkins = list(_r.scalars().all())
    if checkins:
        c = checkins[0]
        today = datetime.now(timezone.utc).date()
        if c.created_at.date() == today:
            return {"done": True, "checkin_id": c.id, "energy_level": c.energy_level}
    return {"done": False}


@router.get("/checkins/history", response_model=List[CheckInOut])
async def get_checkin_history(
    limit: int = Query(default=20, le=100),
    goal_id: Optional[int] = Query(default=None, description="Фильтр по цели"),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Запрос чекинов пользователя с опциональным фильтром по goal_id
    from sqlalchemy import select as _sel2
    from db.models import GoalCheckin as _GC2
    q = _sel2(_GC2).where(_GC2.user_id == current_user.telegram_id)
    if goal_id is not None:
        q = q.where(_GC2.goal_id == goal_id)  # фильтр по конкретной цели
    _r2 = await db.execute(q.order_by(_GC2.created_at.desc()).limit(limit))
    return list(_r2.scalars().all())


@router.get("/checkins/by-date")
async def get_checkin_by_date(
    date: str = Query(..., description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Вернуть все слоты чекина за указанный день. Ключи: morning, midday, evening, manual."""
    from datetime import date as _date_t
    from sqlalchemy import select as _sel_bd
    from db.models import GoalCheckin as _GC_bd
    try:
        check_date = _date_t.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты. Ожидается YYYY-MM-DD")

    _r = await db.execute(
        _sel_bd(_GC_bd)
        .where(_GC_bd.user_id == current_user.telegram_id, _GC_bd.check_date == check_date)
        .order_by(_GC_bd.created_at.asc())
    )
    checkins = list(_r.scalars().all())
    # Группируем слоты дня в словарь {slot: CheckInOut}
    result: dict = {}
    for c in checkins:
        slot = c.time_slot or "manual"
        result[slot] = CheckInOut.model_validate(c)
    return result


@router.get("/checkins/calendar")
async def get_checkin_calendar(
    days: int = Query(default=14, ge=1, le=60),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Вернуть даты с чекинами за последние N дней. Формат: {YYYY-MM-DD: [slot,...]}."""
    from datetime import date as _date_t, timedelta
    from sqlalchemy import select as _sel_cal
    from db.models import GoalCheckin as _GC_cal
    since = _date_t.today() - timedelta(days=days)
    _r = await db.execute(
        _sel_cal(_GC_cal)
        .where(
            _GC_cal.user_id == current_user.telegram_id,
            _GC_cal.check_date >= since,
        )
        .order_by(_GC_cal.check_date.asc())
    )
    checkins = list(_r.scalars().all())
    # Строим календарь {дата: [слот1, слот2...]}
    calendar: dict = {}
    for c in checkins:
        if c.check_date:
            key = c.check_date.isoformat()
            slot = c.time_slot or "manual"
            if key not in calendar:
                calendar[key] = []
            if slot not in calendar[key]:
                calendar[key].append(slot)
    return calendar


@router.patch("/checkins/{checkin_id}", response_model=CheckInOut)
async def update_checkin(
    checkin_id: int,
    body: CheckInPatchDto,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Обновить существующий чекин (energy, mood, notes, blockers, wins)."""
    from sqlalchemy import select as _sel_p
    from db.models import GoalCheckin as _GC_p
    _r = await db.execute(
        _sel_p(_GC_p).where(
            _GC_p.id == checkin_id,
            _GC_p.user_id == current_user.telegram_id,
        )
    )
    checkin = _r.scalar_one_or_none()
    if not checkin:
        raise HTTPException(status_code=404, detail="Чекин не найден")
    data = body.model_dump(exclude_none=True)
    # Применяем обновлённые поля к объекту
    for k, v in data.items():
        setattr(checkin, k, v)
    await db.commit()
    await db.refresh(checkin)
    return checkin


# ══════════════════════════════════════════════════════════════════════════════
# REVIEWS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/reviews", response_model=List[ReviewOut])
async def list_reviews(
    goal_id: Optional[int] = Query(None),
    limit: int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select
    from db.models import GoalReview
    q = select(GoalReview).where(GoalReview.user_id == current_user.telegram_id)
    if goal_id:
        q = q.where(GoalReview.goal_id == goal_id)
    q = q.order_by(GoalReview.created_at.desc()).limit(limit)
    r = await db.execute(q)
    return r.scalars().all()


@router.get("/reviews/latest", response_model=Optional[ReviewOut])
async def get_latest_review(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await cs.get_latest_review(db, current_user.telegram_id)


# ══════════════════════════════════════════════════════════════════════════════
# PROFILE
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/profile", response_model=CoachingProfileOut)
async def get_profile(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await cs.get_or_create_profile(db, current_user.telegram_id)


@router.put("/profile", response_model=CoachingProfileOut)
async def update_profile(
    body: CoachingProfileUpdateDto,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    profile = await cs.update_profile(db, current_user.telegram_id, **body.model_dump(exclude_none=True))
    await db.commit()
    return profile


# ══════════════════════════════════════════════════════════════════════════════
# ONBOARDING
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/onboarding", response_model=OnboardingOut)
async def get_onboarding_state(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await cs.get_or_create_onboarding(db, current_user.telegram_id)


@router.post("/onboarding/step")
async def advance_onboarding(
    body: OnboardingStepDto,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    state = await cs.advance_onboarding_step(db, current_user.telegram_id, body.step)
    await db.commit()
    return {"step": body.step, "done": state.bot_onboarding_done}


@router.post("/onboarding/complete")
async def complete_onboarding(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    from sqlalchemy import update as sql_update
    from db.models import CoachingOnboardingState
    # Помечаем онбординг как завершённый
    await db.execute(
        sql_update(CoachingOnboardingState)
        .where(CoachingOnboardingState.user_id == current_user.telegram_id)
        .values(bot_onboarding_done=True)
    )
    await db.commit()
    return {"completed": True}
