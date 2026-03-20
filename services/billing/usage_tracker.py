"""
UsageTracker - запись usage events, агрегация в ledger.
"""
from __future__ import annotations
import uuid, logging
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import UsageEvent, UsageLedger

logger = logging.getLogger(__name__)


async def record_usage(
    session: AsyncSession, workspace_id: str, user_id: int | None,
    metric_type: str, amount: float,
    source_type: str | None = None, source_id: str | None = None,
    provider: str | None = None, cost_meta: dict | None = None,
) -> UsageEvent:
    """Записывает атомарное событие потребления и обновляет ledger."""
    event = UsageEvent(
        id=str(uuid.uuid4()), workspace_id=workspace_id, user_id=user_id,
        metric_type=metric_type, amount=amount,
        source_type=source_type, source_id=source_id,
        provider=provider, cost_metadata=cost_meta,
    )
    session.add(event)
    # Обновляем или создаем ledger
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_end = (period_start.replace(month=period_start.month % 12 + 1) if period_start.month < 12 else period_start.replace(year=period_start.year + 1, month=1))
    ledger_stmt = select(UsageLedger).where(
        UsageLedger.workspace_id == workspace_id,
        UsageLedger.metric_type == metric_type,
        UsageLedger.period_start == period_start,
    )
    ledger = (await session.execute(ledger_stmt)).scalar_one_or_none()
    if ledger:
        ledger.consumed += amount
    else:
        ledger = UsageLedger(
            id=str(uuid.uuid4()), workspace_id=workspace_id,
            period_start=period_start, period_end=period_end,
            metric_type=metric_type, consumed=amount,
        )
        session.add(ledger)
    await session.flush()
    return event


async def get_usage_summary(session: AsyncSession, workspace_id: str) -> dict:
    """Сводка usage по всем метрикам за текущий период."""
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    stmt = select(UsageLedger).where(UsageLedger.workspace_id == workspace_id, UsageLedger.period_start == period_start)
    result = await session.execute(stmt)
    ledgers = result.scalars().all()
    return {l.metric_type: {"consumed": l.consumed, "limit": l.limit_value, "remaining": max(0, l.limit_value - l.consumed)} for l in ledgers}
