"""
Абстрактный интерфейс провайдера сбора данных.
Firecrawl - первый провайдер, в будущем можно добавить другие.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CrawlResult:
    """Результат обхода сайта (crawl)."""
    pages: list[dict] = field(default_factory=list)  # список страниц с контентом
    urls_found: int = 0
    pages_crawled: int = 0
    provider_metadata: dict = field(default_factory=dict)


@dataclass
class ScrapeResult:
    """Результат скрейпинга одной страницы."""
    url: str = ""
    markdown: str = ""
    html: str = ""
    metadata: dict = field(default_factory=dict)
    provider_metadata: dict = field(default_factory=dict)


@dataclass
class ExtractResult:
    """Результат извлечения структурированных данных."""
    data: list[dict] = field(default_factory=list)  # извлеченные объекты
    source_url: str = ""
    provider_metadata: dict = field(default_factory=dict)


@dataclass
class MapResult:
    """Результат маппинга сайта (список URL)."""
    urls: list[str] = field(default_factory=list)
    provider_metadata: dict = field(default_factory=dict)


@dataclass
class UsageEstimate:
    """Предварительная оценка расхода ресурсов."""
    estimated_pages: int = 0
    estimated_tokens: int = 0
    estimated_cost_units: float = 0.0


class CollectionProvider(ABC):
    """Абстрактный интерфейс провайдера сбора данных."""

    @abstractmethod
    async def crawl(self, url: str, config: dict | None = None) -> CrawlResult:
        """Обход сайта - получение всех страниц."""
        ...

    @abstractmethod
    async def scrape(self, url: str, config: dict | None = None) -> ScrapeResult:
        """Скрейпинг одной страницы."""
        ...

    @abstractmethod
    async def map_site(self, url: str) -> MapResult:
        """Получение списка URL сайта."""
        ...

    @abstractmethod
    async def extract(self, url: str, schema: dict, config: dict | None = None) -> ExtractResult:
        """Извлечение структурированных данных со страницы по схеме."""
        ...

    @abstractmethod
    def estimate_usage(self, task_spec: dict) -> UsageEstimate:
        """Предварительная оценка расхода ресурсов для задачи."""
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        """Название провайдера."""
        ...
