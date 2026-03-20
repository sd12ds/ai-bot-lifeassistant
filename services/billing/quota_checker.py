"""
QuotaChecker - проверка лимитов перед запуском задач.
"""
from __future__ import annotations
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import UsageLedger, QuotaPolicy, Subscription

logger = logging.getLogger(__name__)


async def check_quota(session: AsyncSession, workspace_id: str, metric_type: str, required_amount: float = 1.0) -> dict:
    """Проверяет квоту. Возвращает {allowed, remaining, limit, consumed, enforcement}."""
    # Получаем подписку и план
    sub_stmt = select(Subscription).where(Subscription.workspace_id == workspace_id).order_by(Subscription.period_start.desc()).limit(1)
    sub = (await session.execute(sub_stmt)).scalar_one_or_none()
    if not sub or sub.status not in ("active", "trial"):
        return {"allowed": False, "reason": "no_active_subscription", "remaining": 0}

    # Получаем квотную политику по плану
    policy_stmt = select(QuotaPolicy).where(QuotaPolicy.plan_id == sub.plan_id, QuotaPolicy.metric_type == metric_type)
    policy = (await session.execute(policy_stmt)).scalar_one_or_none()
    if not policy:
        return {"allowed": True, "reason": "no_quota_policy", "remaining": float("inf")}

    # Считаем текущее потребление из ledger
    ledger_stmt = select(func.coalesce(func.sum(UsageLedger.consumed), 0.0)).where(
        UsageLedger.workspace_id == workspace_id, UsageLedger.metric_type == metric_type
    )
    consumed = float((await session.execute(ledger_stmt)).scalar_one())
    remaining = policy.limit_value - consumed

    if remaining < required_amount:
        return {"allowed": False, "reason": "quota_exceeded", "remaining": remaining, "limit": policy.limit_value, "consumed": consumed, "enforcement": policy.enforcement}

    # Soft limit warning при 80%
    warning = consumed / policy.limit_value >= 0.8 if policy.limit_value > 0 else False
    return {"allowed": True, "remaining": remaining, "limit": policy.limit_value, "consumed": consumed, "warning": warning, "enforcement": policy.enforcement}


async def preflight_check(session: AsyncSession, workspace_id: str, job_spec: dict | None = None) -> dict:
    """Полная проверка перед запуском job: подписка + квоты."""
    from services.billing.subscription_manager import check_subscription_status
    status = await check_subscription_status(session, workspace_id)
    if status not in ("active", "trial"):
        return {"allowed": False, "reason": f"subscription_{status}"}
    # Проверяем основные метрики
    jobs_check = await check_quota(session, workspace_id, "job_runs")
    if not jobs_check["allowed"]:
        return jobs_check
    pages_check = await check_quota(session, workspace_id, "crawl_pages")
    warnings = [c for c in [jobs_check, pages_check] if c.get("warning")]
    return {"allowed": True, "warnings": warnings}
