"""
FastAPI роутер для Billing / Subscription / Usage.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from api.deps import get_current_user
from db.session import get_session
from db.models import Plan, Subscription
from sqlalchemy import select
from services.auth.permission_checker import get_workspace_context
from services.auth.rbac import Permission, has_permission
from services.billing import subscription_manager, usage_tracker, quota_checker

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans")
async def list_plans(session: AsyncSession = Depends(get_session)):
    """Доступные тарифные планы."""
    stmt = select(Plan).where(Plan.is_active == True).order_by(Plan.price_monthly)
    result = await session.execute(stmt)
    plans = result.scalars().all()
    return [{"id": p.id, "name": p.name, "features": p.features, "quotas": p.quotas,
             "price_monthly": p.price_monthly, "price_yearly": p.price_yearly} for p in plans]


@router.get("/subscription")
async def get_subscription(ctx=Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    """Текущая подписка workspace."""
    sub = await subscription_manager.get_subscription(session, ctx["workspace_id"])
    if not sub:
        return {"status": "none", "workspace_id": ctx["workspace_id"]}
    return {"id": sub.id, "status": sub.status, "plan_id": sub.plan_id,
            "period_start": sub.period_start.isoformat() if sub.period_start else None,
            "period_end": sub.period_end.isoformat() if sub.period_end else None,
            "trial_end": sub.trial_end.isoformat() if sub.trial_end else None}


@router.get("/usage")
async def get_usage(ctx=Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    """Usage summary за текущий период."""
    summary = await usage_tracker.get_usage_summary(session, ctx["workspace_id"])
    return {"workspace_id": ctx["workspace_id"], "metrics": summary}


class SubscribeRequest(BaseModel):
    plan_id: str

@router.post("/subscribe")
async def subscribe(data: SubscribeRequest, ctx=Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    """Оформить подписку (trial)."""
    if not has_permission(ctx["role"], Permission.BILLING_SUBSCRIBE):
        raise HTTPException(403, "Permission denied")
    existing = await subscription_manager.get_subscription(session, ctx["workspace_id"])
    if existing and existing.status in ("active", "trial"):
        raise HTTPException(409, "Already subscribed")
    sub = await subscription_manager.create_trial(session, ctx["workspace_id"], data.plan_id)
    await session.commit()
    return {"id": sub.id, "status": sub.status}


@router.post("/upgrade")
async def upgrade(data: SubscribeRequest, ctx=Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    """Сменить план."""
    if not has_permission(ctx["role"], Permission.BILLING_SUBSCRIBE):
        raise HTTPException(403, "Permission denied")
    sub = await subscription_manager.upgrade_plan(session, ctx["workspace_id"], data.plan_id, ctx["user_id"])
    if not sub:
        raise HTTPException(404, "No subscription found")
    await session.commit()
    return {"id": sub.id, "status": sub.status, "plan_id": sub.plan_id}


@router.post("/cancel")
async def cancel(ctx=Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    """Отменить подписку."""
    if not has_permission(ctx["role"], Permission.BILLING_SUBSCRIBE):
        raise HTTPException(403, "Permission denied")
    sub = await subscription_manager.cancel_subscription(session, ctx["workspace_id"], ctx["user_id"])
    if not sub:
        raise HTTPException(404, "No subscription found")
    await session.commit()
    return {"id": sub.id, "status": "canceled"}


@router.get("/invoices")
async def list_invoices(ctx=Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    """История платежей (заглушка Phase 3)."""
    return {"items": [], "total": 0, "message": "Invoices coming soon"}
