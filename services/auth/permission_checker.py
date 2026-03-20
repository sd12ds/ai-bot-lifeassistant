"""
PermissionChecker - FastAPI dependencies для проверки прав.
"""
from __future__ import annotations
from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from db.session import get_session
from api.deps import get_current_user
from services.auth.rbac import Permission, has_permission
from services.auth.workspace_manager import get_user_role, get_default_workspace, create_personal_workspace


async def get_workspace_context(
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    x_workspace_id: Optional[str] = Header(None),
):
    """Определяет текущий workspace из header или по умолчанию. Auto-provisioning при необходимости."""
    if x_workspace_id:
        role = await get_user_role(session, user.telegram_id, x_workspace_id)
        if not role:
            raise HTTPException(403, "No access to this workspace")
        return {"workspace_id": x_workspace_id, "role": role, "user_id": user.telegram_id}

    # Без явного workspace - берем дефолтный
    ws = await get_default_workspace(session, user.telegram_id)
    if not ws:
        # Auto-provisioning: создаем Personal Workspace
        ws = await create_personal_workspace(session, user.telegram_id)
        await session.commit()
    role = await get_user_role(session, user.telegram_id, ws.id)
    return {"workspace_id": ws.id, "role": role or "owner", "user_id": user.telegram_id}


def require_permission(permission: Permission):
    """FastAPI dependency factory: проверяет разрешение у текущего пользователя."""
    async def checker(ctx=Depends(get_workspace_context)):
        if not has_permission(ctx["role"], permission):
            raise HTTPException(403, f"Permission denied: {permission.value}")
        return ctx
    return checker
