"""
HTTP-клиент Firecrawl - обертка над firecrawl-py SDK.
Инкапсулирует настройки, retry-логику и логирование вызовов.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from firecrawl import Firecrawl
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import FIRECRAWL_API_KEY, RESEARCH_MAX_PAGES_PER_JOB, RESEARCH_DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)


class FirecrawlClient:
    """Обертка над Firecrawl SDK с retry, timeout и логированием."""

    def __init__(self, api_key: str | None = None):
        # API-ключ из параметра или из конфигурации
        key = api_key or FIRECRAWL_API_KEY
        if not key:
            raise ValueError("FIRECRAWL_API_KEY не задан. Добавьте в .env файл.")
        self._client = Firecrawl(api_key=key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def scrape_url(self, url: str, formats: list[str] | None = None, **kwargs) -> dict:
        """Скрейпинг одной страницы."""
        start = time.time()
        logger.info("Firecrawl scrape: %s", url)
        try:
            result = self._client.scrape(
                url,
                formats=formats or ["markdown"],
                timeout=kwargs.get("timeout", RESEARCH_DEFAULT_TIMEOUT * 1000),
                **{k: v for k, v in kwargs.items() if k != "timeout"},
            )
            elapsed = time.time() - start
            logger.info("Firecrawl scrape OK: %s (%.1fs)", url, elapsed)
            return result
        except Exception as e:
            elapsed = time.time() - start
            logger.error("Firecrawl scrape FAIL: %s (%.1fs) - %s", url, elapsed, e)
            raise

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def crawl_url(self, url: str, limit: int | None = None, **kwargs) -> dict:
        """Обход сайта - получение нескольких страниц."""
        start = time.time()
        page_limit = limit or RESEARCH_MAX_PAGES_PER_JOB
        logger.info("Firecrawl crawl: %s (limit=%d)", url, page_limit)
        try:
            result = self._client.crawl(
                url,
                limit=page_limit,
                scrape_options={"formats": ["markdown"]},
                **kwargs,
            )
            elapsed = time.time() - start
            logger.info("Firecrawl crawl OK: %s (%.1fs)", url, elapsed)
            return result
        except Exception as e:
            elapsed = time.time() - start
            logger.error("Firecrawl crawl FAIL: %s (%.1fs) - %s", url, elapsed, e)
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def map_url(self, url: str) -> list[str]:
        """Получение списка URL сайта."""
        start = time.time()
        logger.info("Firecrawl map: %s", url)
        try:
            result = self._client.map(url)
            elapsed = time.time() - start
            # result может быть списком URL или dict с ключом links
            urls = result if isinstance(result, list) else result.get("links", [])
            logger.info("Firecrawl map OK: %s - %d URLs (%.1fs)", url, len(urls), elapsed)
            return urls
        except Exception as e:
            elapsed = time.time() - start
            logger.error("Firecrawl map FAIL: %s (%.1fs) - %s", url, elapsed, e)
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def extract_url(self, url: str, schema: dict, **kwargs) -> dict:
        """Извлечение структурированных данных со страницы по JSON-схеме."""
        start = time.time()
        logger.info("Firecrawl extract: %s", url)
        try:
            result = self._client.scrape(
                url,
                formats=[{"type": "json", "schema": schema}],
                timeout=kwargs.get("timeout", RESEARCH_DEFAULT_TIMEOUT * 1000),
            )
            elapsed = time.time() - start
            logger.info("Firecrawl extract OK: %s (%.1fs)", url, elapsed)
            return result
        except Exception as e:
            elapsed = time.time() - start
            logger.error("Firecrawl extract FAIL: %s (%.1fs) - %s", url, elapsed, e)
            raise
