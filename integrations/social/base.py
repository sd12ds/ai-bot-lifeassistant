"""
Абстрактный интерфейс провайдера для парсинга социальных сетей.
Каждая платформа реализует этот интерфейс: Telegram, Instagram, VK и т.д.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SourceInfo:
    """Информация об источнике (профиль, канал, хэштег)."""
    source_id: str
    source_name: str
    platform: str
    source_type: str                          # channel | group | profile | page | hashtag | location
    subscribers_count: int = 0
    description: str = ""
    photo_url: str = ""
    is_verified: bool = False
    extra: dict = field(default_factory=dict) # дополнительные поля платформы


@dataclass
class ParsedPost:
    """Один спарсенный пост/сообщение."""
    platform_post_id: str
    content: str = ""
    post_url: str = ""
    post_type: str = "text"                   # text | image | video | carousel | reel
    posted_at: Any = None                     # datetime
    author_name: str = ""
    author_id: str = ""
    metrics: dict = field(default_factory=dict)     # views, likes, comments, forwards, reactions
    media_urls: list = field(default_factory=list)  # список URL медиа
    hashtags: list = field(default_factory=list)    # хэштеги из текста
    mentions: list = field(default_factory=list)    # упомянутые аккаунты
    location: dict = field(default_factory=dict)    # геометка
    raw_data: dict = field(default_factory=dict)    # полный raw ответ API
    is_pinned: bool = False


class SocialProvider(ABC):
    """Абстрактный провайдер парсинга соцсетей."""

    @abstractmethod
    async def resolve_url(self, url: str) -> SourceInfo:
        """Определяет тип источника по URL и получает базовую информацию."""
        ...

    @abstractmethod
    async def get_source_info(self, source_id: str, source_type: str = "profile") -> SourceInfo:
        """Получает актуальную информацию об источнике."""
        ...

    @abstractmethod
    async def get_posts(
        self,
        source_id: str,
        results_type: str = "posts",
        since: Any = None,
        limit: int = 50,
        extra_config: dict | None = None,
    ) -> list[ParsedPost]:
        """Получает посты/контент из источника.

        Args:
            source_id: ID источника на платформе
            results_type: тип контента (posts | reels | comments | mentions | hashtag | location | search)
            since: дата с которой брать посты (инкрементальный сбор)
            limit: максимальное количество
            extra_config: дополнительные параметры платформы
        """
        ...

    @abstractmethod
    def get_platform_name(self) -> str:
        """Название платформы."""
        ...
