"""
Реестр провайдеров соцсетей.
Единая точка получения провайдера по имени платформы (DRY / SOLID).
"""
from __future__ import annotations

from integrations.social.base import SocialProvider


def get_provider(platform: str) -> SocialProvider:
    """Возвращает провайдер для указанной платформы (lazy-импорт внутри для избежания circular imports)."""
    if platform == "instagram":
        from integrations.social.instagram.provider import InstagramProvider
        return InstagramProvider()
    elif platform == "telegram":
        from integrations.social.telegram_parser.provider import TelegramProvider
        return TelegramProvider()
    raise ValueError(f"Неизвестная платформа: {platform}")
