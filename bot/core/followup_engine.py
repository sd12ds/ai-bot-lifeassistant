"""
Универсальный Followup Engine — генерация подсказок после сохранения.

Доменные провайдеры регистрируются через register_followup_provider().
Движок вызывает провайдер нужного домена и возвращает 0-2 подсказки.
"""
from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class FollowupProvider(Protocol):
    """Протокол провайдера follow-up подсказок для конкретного домена."""

    async def generate(self, user_id: int, **kwargs: Any) -> list[str]:
        """Вернуть 0-2 подсказки после сохранения сущности."""
        ...


# ── Реестр провайдеров ───────────────────────────────────────────────────────
_providers: dict[str, FollowupProvider] = {}


def register_followup_provider(domain: str, provider: FollowupProvider) -> None:
    """Зарегистрировать провайдер подсказок для домена."""
    _providers[domain] = provider
    logger.info("Зарегистрирован followup provider для домена '%s'", domain)


def get_followup_provider(domain: str) -> FollowupProvider | None:
    """Получить провайдер по имени домена."""
    return _providers.get(domain)


async def generate_followup(domain: str, user_id: int, **kwargs: Any) -> list[str]:
    """
    Сгенерировать follow-up подсказки для указанного домена.

    Returns:
        Список строк-подсказок (0-2 шт.) или пустой список если нет провайдера.
    """
    provider = _providers.get(domain)
    if provider is None:
        return []

    try:
        tips = await provider.generate(user_id, **kwargs)
        return tips[:2]  # Максимум 2 подсказки
    except Exception as e:
        logger.error("Ошибка followup provider '%s': %s", domain, e)
        return []


def format_followup(tips: list[str]) -> str:
    """Универсальное форматирование подсказок для Telegram."""
    if not tips:
        return ""
    return "\n".join(["", "💡 **Совет:**"] + tips)
