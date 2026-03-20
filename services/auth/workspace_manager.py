"""
WorkspaceManager - управление workspace и membership.
"""
from __future__ import annotations
import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Workspace, Membership

logger = logging.getLogger(__name__)


async def create_personal_workspace(session: AsyncSession, user_id: int) -> Workspace:
    """Создает Personal Workspace для пользователя (при первом входе)."""
    # Проверяем что ещё нет workspace
    existing = await get_user_workspaces(session, user_id)
    if existing:
        return existing[0]
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="Personal Workspace",
        owner_user_id=user_id,
        settings={},
    )
    session.add(ws)
    # Создаем membership с ролью owner
    membership = Membership(
        id=str(uuid.uuid4()),
        user_id=user_id,
        workspace_id=ws.id,
        role="owner",
        status="active",
        joined_at=datetime.now(timezone.utc),
    )
    session.add(membership)
    await session.flush()
    logger.info("Personal workspace created: ws=%s user=%d", ws.id, user_id)
    return ws


async def get_workspace(session: AsyncSession, workspace_id: str) -> Workspace | None:
    """Получает workspace по ID."""
    return await session.get(Workspace, workspace_id)


async def get_user_workspaces(session: AsyncSession, user_id: int) -> list[Workspace]:
    """Список workspace пользователя."""
    stmt = (
        select(Workspace)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user_id, Membership.status == "active")
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_user_role(session: AsyncSession, user_id: int, workspace_id: str) -> str | None:
    """Получает роль пользователя в workspace."""
    stmt = select(Membership.role).where(
        Membership.user_id == user_id,
        Membership.workspace_id == workspace_id,
        Membership.status == "active",
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_default_workspace(session: AsyncSession, user_id: int) -> Workspace | None:
    """Получает workspace по умолчанию (первый active)."""
    workspaces = await get_user_workspaces(session, user_id)
    return workspaces[0] if workspaces else None
