"""
FastAPI роутер для Workspace Management.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from api.deps import get_current_user
from db.session import get_session
from db.models import Workspace, Membership
from services.auth.workspace_manager import get_user_workspaces, get_user_role, create_personal_workspace
from services.auth.permission_checker import get_workspace_context
from services.auth.rbac import Permission, has_permission

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    settings: dict | None = None

class InviteRequest(BaseModel):
    user_id: int
    role: str = "viewer"

class RoleUpdate(BaseModel):
    role: str


@router.get("")
async def list_workspaces(user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    """Список workspace пользователя."""
    workspaces = await get_user_workspaces(session, user.telegram_id)
    result = []
    for ws in workspaces:
        role = await get_user_role(session, user.telegram_id, ws.id)
        result.append({"id": ws.id, "name": ws.name, "owner_user_id": ws.owner_user_id, "role": role, "created_at": ws.created_at.isoformat() if ws.created_at else None})
    return result


@router.patch("/{workspace_id}")
async def update_workspace(workspace_id: str, data: WorkspaceUpdate, ctx=Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    """Обновление workspace (admin+)."""
    if not has_permission(ctx["role"], Permission.MEMBER_MANAGE):
        raise HTTPException(403, "Permission denied")
    ws = await session.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(404, "Workspace not found")
    if data.name: ws.name = data.name
    if data.settings is not None: ws.settings = data.settings
    await session.commit()
    return {"id": ws.id, "name": ws.name}


@router.get("/{workspace_id}/members")
async def list_members(workspace_id: str, ctx=Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    """Список участников workspace."""
    stmt = select(Membership).where(Membership.workspace_id == workspace_id, Membership.status == "active")
    result = await session.execute(stmt)
    members = result.scalars().all()
    return [{"user_id": m.user_id, "role": m.role, "joined_at": m.joined_at.isoformat() if m.joined_at else None} for m in members]


@router.post("/{workspace_id}/invite")
async def invite_member(workspace_id: str, data: InviteRequest, ctx=Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    """Приглашение участника (admin+)."""
    if not has_permission(ctx["role"], Permission.MEMBER_INVITE):
        raise HTTPException(403, "Permission denied")
    # Проверяем что пользователь ещё не в workspace
    existing = await get_user_role(session, data.user_id, workspace_id)
    if existing:
        raise HTTPException(409, "User already in workspace")
    membership = Membership(id=str(uuid.uuid4()), user_id=data.user_id, workspace_id=workspace_id, role=data.role, status="active", joined_at=datetime.now(timezone.utc))
    session.add(membership)
    await session.commit()
    return {"status": "invited", "user_id": data.user_id, "role": data.role}


@router.patch("/{workspace_id}/members/{user_id}")
async def update_member_role(workspace_id: str, user_id: int, data: RoleUpdate, ctx=Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    """Изменение роли участника (admin+)."""
    if not has_permission(ctx["role"], Permission.MEMBER_MANAGE):
        raise HTTPException(403, "Permission denied")
    stmt = select(Membership).where(Membership.workspace_id == workspace_id, Membership.user_id == user_id, Membership.status == "active")
    result = await session.execute(stmt)
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(404, "Member not found")
    if membership.role == "owner":
        raise HTTPException(403, "Cannot change owner role")
    membership.role = data.role
    await session.commit()
    return {"user_id": user_id, "role": data.role}


@router.delete("/{workspace_id}/members/{user_id}")
async def remove_member(workspace_id: str, user_id: int, ctx=Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    """Удаление участника (admin+)."""
    if not has_permission(ctx["role"], Permission.MEMBER_MANAGE):
        raise HTTPException(403, "Permission denied")
    stmt = select(Membership).where(Membership.workspace_id == workspace_id, Membership.user_id == user_id, Membership.status == "active")
    result = await session.execute(stmt)
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(404, "Member not found")
    if membership.role == "owner":
        raise HTTPException(403, "Cannot remove owner")
    membership.status = "removed"
    await session.commit()
    return {"status": "removed", "user_id": user_id}
