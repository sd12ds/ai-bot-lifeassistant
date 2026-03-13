"""
DomainAdapter — протокол доменного адаптера.

Каждый модуль (nutrition, fitness, tasks) реализует этот протокол,
чтобы интегрироваться с универсальным core.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from bot.core.base_draft import BaseDraft
from bot.core.session_context import SessionContext


@runtime_checkable
class DomainAdapter(Protocol):
    """Интерфейс доменного адаптера для подключения модуля к core."""

    @property
    def domain(self) -> str:
        """Имя домена: 'nutrition' | 'fitness' | 'tasks' и т.д."""
        ...

    def create_draft(self, user_id: int, items: list[dict], **kwargs: Any) -> BaseDraft:
        """Создать черновик сущности домена."""
        ...

    def format_draft_card(self, draft: BaseDraft) -> str:
        """Отформатировать черновик в читабельную карточку для Telegram."""
        ...

    def format_context_for_agent(self, ctx: SessionContext) -> str:
        """Отформатировать контекст для инъекции в промпт агента."""
        ...

    async def save_draft(self, user_id: int, draft: BaseDraft) -> dict:
        """Сохранить черновик в БД, вернуть сохранённую сущность."""
        ...

    async def generate_followup(self, user_id: int) -> list[str]:
        """Сгенерировать follow-up подсказки после сохранения."""
        ...


# ── Реестр адаптеров ─────────────────────────────────────────────────────────
_adapters: dict[str, DomainAdapter] = {}


def register_adapter(adapter: DomainAdapter) -> None:
    """Зарегистрировать доменный адаптер."""
    _adapters[adapter.domain] = adapter


def get_adapter(domain: str) -> DomainAdapter | None:
    """Получить адаптер по имени домена."""
    return _adapters.get(domain)


def get_all_adapters() -> dict[str, DomainAdapter]:
    """Все зарегистрированные адаптеры."""
    return dict(_adapters)
