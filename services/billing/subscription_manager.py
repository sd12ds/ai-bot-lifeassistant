"""
SubscriptionManager - CRUD подписок, lifecycle transitions.
"""
from __future__ import annotations
import uuid, logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Subscription, Plan, BillingEvent

logger = logging.getLogger(__name__)


async def create_trial(session: AsyncSession, workspace_id: str, plan_id: str) -> Subscription:
    """Создает trial-подписку для workspace."""
    now = datetime.now(timezone.utc)
    sub = Subscription(
        id=str(uuid.uuid4()), workspace_id=workspace_id, plan_id=plan_id,
        status="trial", period_start=now, period_end=now + timedelta(days=14),
        trial_end=now + timedelta(days=14),
    )
    session.add(sub)
    # Событие биллинга
    session.add(BillingEvent(id=str(uuid.uuid4()), workspace_id=workspace_id, event_type="subscription.created", subscription_id=sub.id, details={"plan_id": plan_id, "status": "trial"}))
    await session.flush()
    logger.info("Trial created: ws=%s plan=%s", workspace_id, plan_id)
    return sub


async def get_subscription(session: AsyncSession, workspace_id: str) -> Subscription | None:
    """Получает активную подписку workspace."""
    stmt = select(Subscription).where(Subscription.workspace_id == workspace_id).order_by(Subscription.period_start.desc()).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def check_subscription_status(session: AsyncSession, workspace_id: str) -> str:
    """Проверяет статус подписки. Возвращает статус или 'none'."""
    sub = await get_subscription(session, workspace_id)
    if not sub:
        return "none"
    # Проверяем истечение trial
    now = datetime.now(timezone.utc)
    if sub.status == "trial" and sub.trial_end and sub.trial_end < now:
        sub.status = "suspended"
        await session.flush()
        return "suspended"
    return sub.status


async def upgrade_plan(session: AsyncSession, workspace_id: str, new_plan_id: str, actor_id: int | None = None) -> Subscription | None:
    """Смена плана подписки."""
    sub = await get_subscription(session, workspace_id)
    if not sub:
        return None
    old_plan = sub.plan_id
    sub.plan_id = new_plan_id
    sub.status = "active"
    session.add(BillingEvent(id=str(uuid.uuid4()), workspace_id=workspace_id, event_type="subscription.upgraded", subscription_id=sub.id, actor_id=actor_id, details={"old_plan": old_plan, "new_plan": new_plan_id}))
    await session.flush()
    return sub


async def cancel_subscription(session: AsyncSession, workspace_id: str, actor_id: int | None = None) -> Subscription | None:
    """Отмена подписки."""
    sub = await get_subscription(session, workspace_id)
    if not sub:
        return None
    sub.status = "canceled"
    sub.canceled_at = datetime.now(timezone.utc)
    session.add(BillingEvent(id=str(uuid.uuid4()), workspace_id=workspace_id, event_type="subscription.canceled", subscription_id=sub.id, actor_id=actor_id))
    await session.flush()
    return sub
