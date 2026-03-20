"""
AuditLogger - асинхронная запись audit events.
"""
from __future__ import annotations
import uuid, logging
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import AuditEvent

logger = logging.getLogger(__name__)


async def log_event(
    session: AsyncSession, workspace_id: str | None = None, actor_id: int | None = None,
    action: str = "", resource_type: str | None = None, resource_id: str | None = None,
    source: str | None = None, ip: str | None = None, user_agent: str | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    """Записывает audit event. Не блокирует основной поток."""
    event = AuditEvent(
        id=str(uuid.uuid4()), workspace_id=workspace_id, actor_id=actor_id,
        action=action, resource_type=resource_type, resource_id=resource_id,
        source=source, ip_address=ip, user_agent=user_agent, extra_metadata=metadata,
    )
    session.add(event)
    await session.flush()
    logger.debug("Audit: %s by %s on %s/%s", action, actor_id, resource_type, resource_id)
    return event
