"""
Универсальный Session Context Manager.

Хранит активный домен, черновик и последнюю сохранённую сущность
для каждого пользователя. In-memory с TTL.
Не содержит nutrition/fitness/tasks-специфичного кода.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from config import DEFAULT_TZ
from bot.core.base_draft import BaseDraft

logger = logging.getLogger(__name__)

# TTL контекста сессии — 30 минут неактивности
_SESSION_TTL = timedelta(minutes=30)


@dataclass
class SessionContext:
    """Контекст сессии пользователя (универсальный, не привязан к домену)."""
    user_id: int
    active_domain: str = ""                     # "nutrition" | "fitness" | "tasks" | ""
    draft: BaseDraft | None = None              # Текущий черновик (любого домена)
    last_saved_entity: dict | None = None       # Последняя сохранённая сущность
    last_activity: datetime = field(default_factory=lambda: datetime.now(DEFAULT_TZ))
    last_source: str = ""                       # "photo" | "text" | "voice"
    pending_confirmation: bool = False          # Ждём подтверждения?
    meta: dict[str, Any] = field(default_factory=dict)  # Доп. данные домена


# ── In-memory хранилище ──────────────────────────────────────────────────────
_contexts: dict[int, SessionContext] = {}
_locks: dict[int, asyncio.Lock] = {}


def _get_lock(user_id: int) -> asyncio.Lock:
    """Возвращает asyncio Lock для конкретного пользователя."""
    if user_id not in _locks:
        _locks[user_id] = asyncio.Lock()
    return _locks[user_id]


def get_context(user_id: int) -> SessionContext | None:
    """Получить контекст сессии пользователя (или None если нет / истёк)."""
    ctx = _contexts.get(user_id)
    if ctx is None:
        return None
    # Проверяем TTL
    if datetime.now(DEFAULT_TZ) - ctx.last_activity > _SESSION_TTL:
        _contexts.pop(user_id, None)
        logger.debug("Session context для user=%s истёк (TTL)", user_id)
        return None
    return ctx


def get_or_create_context(user_id: int, domain: str = "") -> SessionContext:
    """Получить существующий контекст или создать новый."""
    ctx = get_context(user_id)
    if ctx is None:
        ctx = SessionContext(user_id=user_id, active_domain=domain)
        _contexts[user_id] = ctx
    elif domain and ctx.active_domain != domain:
        # Смена домена — обновляем
        ctx.active_domain = domain
    return ctx


def set_draft(user_id: int, draft: BaseDraft) -> SessionContext:
    """Установить черновик в контексте. Создаёт контекст если нет."""
    ctx = get_or_create_context(user_id, domain=draft.domain)
    ctx.draft = draft
    ctx.active_domain = draft.domain
    ctx.pending_confirmation = True
    ctx.last_activity = datetime.now(DEFAULT_TZ)
    return ctx


def clear_draft(user_id: int) -> None:
    """Очистить только draft, оставив last_saved_entity."""
    ctx = _contexts.get(user_id)
    if ctx:
        ctx.draft = None
        ctx.pending_confirmation = False
        ctx.last_activity = datetime.now(DEFAULT_TZ)


def set_last_saved(user_id: int, entity: dict) -> None:
    """Запомнить последнюю сохранённую сущность (для 'записал?')."""
    ctx = _contexts.get(user_id)
    if ctx:
        ctx.last_saved_entity = entity
        ctx.last_activity = datetime.now(DEFAULT_TZ)


def get_active_domain(user_id: int) -> str:
    """Получить имя активного домена (или пустую строку)."""
    ctx = get_context(user_id)
    return ctx.active_domain if ctx else ""


def clear_context(user_id: int) -> None:
    """Полностью очистить контекст пользователя."""
    _contexts.pop(user_id, None)


def cleanup_expired() -> int:
    """Удалить все просроченные контексты. Возвращает количество удалённых."""
    now = datetime.now(DEFAULT_TZ)
    expired = [
        uid for uid, ctx in _contexts.items()
        if now - ctx.last_activity > _SESSION_TTL
    ]
    for uid in expired:
        _contexts.pop(uid, None)
    if expired:
        logger.debug("Очищено %d просроченных session context'ов", len(expired))
    return len(expired)
