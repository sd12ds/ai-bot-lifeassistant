"""
BillingGuard - FastAPI middleware для проверки подписки.
"""
from __future__ import annotations
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_session
from services.auth.permission_checker import get_workspace_context
from services.billing.subscription_manager import check_subscription_status


async def require_active_subscription(
    ctx=Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """FastAPI dependency: проверяет что подписка active/trial."""
    status = await check_subscription_status(session, ctx["workspace_id"])
    if status not in ("active", "trial"):
        raise HTTPException(402, f"Subscription required. Current status: {status}")
    return ctx
