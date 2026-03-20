"""
SecurityLogger - запись security events.
"""
from __future__ import annotations
import uuid, logging
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import SecurityEvent

logger = logging.getLogger(__name__)


async def log_access_denied(session: AsyncSession, actor_id: int | None, resource: str, permission: str, source: str | None = None, ip: str | None = None):
    event = SecurityEvent(id=str(uuid.uuid4()), actor_id=actor_id, event_type="access_denied", ip_address=ip, details={"resource": resource, "permission": permission, "source": source})
    session.add(event)
    await session.flush()
    logger.warning("ACCESS DENIED: actor=%s resource=%s perm=%s", actor_id, resource, permission)


async def log_auth_event(session: AsyncSession, actor_id: int | None, event_type: str, source: str | None = None, ip: str | None = None):
    event = SecurityEvent(id=str(uuid.uuid4()), actor_id=actor_id, event_type=event_type, ip_address=ip, details={"source": source})
    session.add(event)
    await session.flush()


async def log_billing_change(session: AsyncSession, workspace_id: str, actor_id: int | None, change_type: str, details: dict | None = None):
    event = SecurityEvent(id=str(uuid.uuid4()), workspace_id=workspace_id, actor_id=actor_id, event_type=f"billing.{change_type}", details=details)
    session.add(event)
    await session.flush()


async def log_quota_enforcement(session: AsyncSession, workspace_id: str, metric_type: str, action: str, details: dict | None = None):
    event = SecurityEvent(id=str(uuid.uuid4()), workspace_id=workspace_id, event_type="quota_enforcement", details={"metric": metric_type, "action": action, **(details or {})})
    session.add(event)
    await session.flush()


async def log_suspicious_usage(session: AsyncSession, actor_id: int | None, pattern: str, details: dict | None = None, ip: str | None = None):
    event = SecurityEvent(id=str(uuid.uuid4()), actor_id=actor_id, event_type="suspicious_usage", ip_address=ip, details={"pattern": pattern, **(details or {})})
    session.add(event)
    await session.flush()
    logger.warning("SUSPICIOUS: actor=%s pattern=%s", actor_id, pattern)
