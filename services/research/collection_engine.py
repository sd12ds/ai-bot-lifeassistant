"""
CollectionEngine - координация провайдеров сбора данных.
Выбирает провайдера, вызывает нужный метод, записывает sources.
"""
from __future__ import annotations

import logging
from integrations.firecrawl.provider import FirecrawlProvider
from integrations.firecrawl.mapper import map_job_to_firecrawl_config
from integrations.base_provider import CollectionProvider

logger = logging.getLogger(__name__)

# Реестр провайдеров (пока один - Firecrawl)
_providers: dict[str, CollectionProvider] = {}


def get_provider(name: str = "firecrawl") -> CollectionProvider:
    """Получает или создает экземпляр провайдера по имени."""
    if name not in _providers:
        if name == "firecrawl":
            _providers[name] = FirecrawlProvider()
        else:
            raise ValueError(f"Неизвестный провайдер: {name}")
    return _providers[name]


async def collect(job_type: str, provider_name: str, normalized_spec: dict | None, urls: list[str] | None = None) -> dict:
    """
    Основная функция сбора данных. Выбирает провайдера и метод по типу задачи.
    Возвращает dict с результатами и метриками.
    """
    provider = get_provider(provider_name)
    spec = normalized_spec or {}
    config = map_job_to_firecrawl_config(job_type, spec)
    target_urls = urls or spec.get("urls", spec.get("seed_urls", []))

    if job_type == "crawl":
        # Обход сайта
        if not target_urls:
            return {"error": "Не указаны URL для обхода", "items": []}
        result = await provider.crawl(target_urls[0], config=config)
        items = [{"source_url": p["url"], "title": p.get("title", ""), "raw_content": p.get("markdown", ""), "metadata": p.get("metadata")} for p in result.pages]
        return {"items": items, "metrics": {"urls_found": result.urls_found, "pages_crawled": result.pages_crawled}, "provider_metadata": result.provider_metadata}

    elif job_type == "scrape":
        # Скрейпинг конкретных URL
        items = []
        for url in target_urls:
            result = await provider.scrape(url, config=config)
            items.append({"source_url": url, "title": result.metadata.get("title", ""), "raw_content": result.markdown, "metadata": result.metadata})
        return {"items": items, "metrics": {"pages_crawled": len(items)}, "provider_metadata": {}}

    elif job_type == "extract":
        # Извлечение данных по схеме
        schema = spec.get("extraction_schema", {})
        items = []
        for url in target_urls:
            result = await provider.extract(url, schema=schema, config=config)
            for entry in result.data:
                items.append({"source_url": url, "extracted_fields": entry, "metadata": {}})
        return {"items": items, "metrics": {"pages_crawled": len(target_urls), "items_extracted": len(items)}, "provider_metadata": {}}

    elif job_type == "search":
        # Поиск: пока scrape первых URL (search API в будущем)
        items = []
        for url in target_urls[:config.get("search_limit", 10)]:
            result = await provider.scrape(url, config=config)
            items.append({"source_url": url, "title": result.metadata.get("title", ""), "raw_content": result.markdown, "metadata": result.metadata})
        return {"items": items, "metrics": {"pages_crawled": len(items)}, "provider_metadata": {}}

    else:
        # multi_step и прочие - пока как crawl
        if target_urls:
            result = await provider.crawl(target_urls[0], config=config)
            items = [{"source_url": p["url"], "title": p.get("title", ""), "raw_content": p.get("markdown", ""), "metadata": p.get("metadata")} for p in result.pages]
            return {"items": items, "metrics": {"urls_found": result.urls_found, "pages_crawled": result.pages_crawled}, "provider_metadata": result.provider_metadata}
        return {"items": [], "metrics": {}, "provider_metadata": {}}
