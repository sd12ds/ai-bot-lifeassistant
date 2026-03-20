"""
RBAC - Role-Based Access Control для Research домена.
Матрица прав из research_domain_design.md 3.6.
"""
from __future__ import annotations
from enum import Enum


class Permission(str, Enum):
    # Research
    JOB_CREATE = "research.job.create"
    JOB_RUN = "research.job.run"
    JOB_EDIT = "research.job.edit"
    JOB_DELETE = "research.job.delete"
    RESULT_VIEW = "research.result.view"
    RESULT_EXPORT = "research.result.export"
    TEMPLATE_MANAGE = "research.template.manage"
    # Workspace
    MEMBER_INVITE = "workspace.member.invite"
    MEMBER_MANAGE = "workspace.member.manage"
    # Billing
    BILLING_SUBSCRIBE = "billing.subscribe"
    BILLING_VIEW = "billing.view"
    # Audit
    AUDIT_VIEW = "audit.view"
    # Workspace management
    WORKSPACE_DELETE = "workspace.delete"


# Матрица: роль -> набор разрешений (из RTF 3.6)
ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "owner": set(Permission),  # все права
    "admin": {
        Permission.JOB_CREATE, Permission.JOB_RUN, Permission.JOB_EDIT, Permission.JOB_DELETE,
        Permission.RESULT_VIEW, Permission.RESULT_EXPORT, Permission.TEMPLATE_MANAGE,
        Permission.MEMBER_INVITE, Permission.MEMBER_MANAGE,
        Permission.BILLING_VIEW, Permission.AUDIT_VIEW,
    },
    "billing_admin": {
        Permission.BILLING_SUBSCRIBE, Permission.BILLING_VIEW, Permission.RESULT_VIEW,
    },
    "manager": {
        Permission.JOB_CREATE, Permission.JOB_RUN, Permission.JOB_EDIT,
        Permission.RESULT_VIEW, Permission.RESULT_EXPORT, Permission.TEMPLATE_MANAGE,
        Permission.BILLING_VIEW,
    },
    "analyst": {
        Permission.RESULT_VIEW, Permission.RESULT_EXPORT, Permission.BILLING_VIEW,
    },
    "viewer": {
        Permission.RESULT_VIEW, Permission.BILLING_VIEW,
    },
}


def has_permission(role: str, permission: Permission) -> bool:
    """Проверяет есть ли у роли указанное разрешение."""
    perms = ROLE_PERMISSIONS.get(role, set())
    return permission in perms
