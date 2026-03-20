"""
FirecrawlProvider - реализация CollectionProvider через Firecrawl API.
Инкапсулирует всю логику работы с Firecrawl, usage metering.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from integrations.base_provider import (
    CollectionProvider, CrawlResult, ScrapeResult,
    ExtractResult, MapResult, UsageEstimate,
)
from integrations.firecrawl.client import FirecrawlClient
from integrations.firecrawl.mapper import map_job_to_firecrawl_config

logger = logging.getLogger(__name__)


class FirecrawlProvider(CollectionProvider):
    """Реализация CollectionProvider через Firecrawl API."""

    def __init__(self, api_key: str | None = None):
        self._client = FirecrawlClient(api_key=api_key)

    async def crawl(self, url: str, config: dict | None = None) -> CrawlResult:
        """Обход сайта через Firecrawl crawl."""
        cfg = config or {}
        # Firecrawl SDK синхронный - запускаем в executor
        raw = await asyncio.to_thread(
            self._client.crawl_url,
            url,
            limit=cfg.get("limit", 100),
        )
        # Парсим результат Firecrawl
        pages = []
        if isinstance(raw, dict):
            data = raw.get("data", [])
            if isinstance(data, list):
                for page in data:
                    pages.append({
                        "url": page.get("url", page.get("sourceURL", "")),
                        "markdown": page.get("markdown", ""),
                        "title": page.get("metadata", {}).get("title", ""),
                        "metadata": page.get("metadata", {}),
                    })
        return CrawlResult(
            pages=pages,
            urls_found=len(pages),
            pages_crawled=len(pages),
            provider_metadata={"raw_status": raw.get("status") if isinstance(raw, dict) else None},
        )

    async def scrape(self, url: str, config: dict | None = None) -> ScrapeResult:
        """Скрейпинг одной страницы через Firecrawl scrape."""
        cfg = config or {}
        formats = cfg.get("formats", ["markdown"])
        raw = await asyncio.to_thread(self._client.scrape_url, url, formats=formats)
        # Парсим результат
        if isinstance(raw, dict):
            return ScrapeResult(
                url=url,
                markdown=raw.get("markdown", ""),
                html=raw.get("html", ""),
                metadata=raw.get("metadata", {}),
                provider_metadata=raw.get("provider_metadata", {}),
            )
        return ScrapeResult(url=url)

    async def map_site(self, url: str) -> MapResult:
        """Получение списка URL сайта через Firecrawl map."""
        urls = await asyncio.to_thread(self._client.map_url, url)
        return MapResult(urls=urls)

    async def extract(self, url: str, schema: dict, config: dict | None = None) -> ExtractResult:
        """Извлечение структурированных данных через Firecrawl + JSON schema."""
        raw = await asyncio.to_thread(self._client.extract_url, url, schema=schema)
        # Извлекаем данные из ответа
        data = []
        if isinstance(raw, dict):
            # Firecrawl возвращает extracted данные в разных форматах
            json_data = raw.get("json", raw.get("data", {}))
            if isinstance(json_data, dict):
                data = [json_data]
            elif isinstance(json_data, list):
                data = json_data
        return ExtractResult(
            data=data,
            source_url=url,
            provider_metadata=raw if isinstance(raw, dict) else {},
        )

    def estimate_usage(self, task_spec: dict) -> UsageEstimate:
        """Оценка расхода ресурсов для задачи."""
        job_type = task_spec.get("mode", "scrape")
        limit = task_spec.get("limit", 10)

        if job_type == "crawl":
            # Crawl: ~1 credit за страницу
            return UsageEstimate(
                estimated_pages=limit,
                estimated_tokens=limit * 2000,  # ~2K токенов на страницу для LLM
                estimated_cost_units=float(limit),
            )
        elif job_type == "search":
            # Search: search credits + scrape credits
            search_limit = task_spec.get("search_limit", 10)
            return UsageEstimate(
                estimated_pages=search_limit,
                estimated_tokens=search_limit * 2000,
                estimated_cost_units=float(search_limit + 1),  # 1 за поиск + N за скрейпинг
            )
        elif job_type == "extract":
            # Extract: scrape + LLM tokens
            return UsageEstimate(
                estimated_pages=1,
                estimated_tokens=5000,  # больше токенов на extraction
                estimated_cost_units=2.0,  # scrape + extraction
            )
        else:
            # Scrape: 1 credit за страницу
            urls_count = len(task_spec.get("urls", [1]))
            return UsageEstimate(
                estimated_pages=urls_count,
                estimated_tokens=urls_count * 1500,
                estimated_cost_units=float(urls_count),
            )

    def get_provider_name(self) -> str:
        return "firecrawl"
