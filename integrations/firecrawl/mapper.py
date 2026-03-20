"""
Маппер задач Research -> конфигурация Firecrawl.
Преобразует normalized_spec задачи в параметры для вызовов Firecrawl SDK.
"""
from __future__ import annotations

import logging
from typing import Any

from config import RESEARCH_MAX_PAGES_PER_JOB

logger = logging.getLogger(__name__)


def map_job_to_firecrawl_config(job_type: str, normalized_spec: dict | None = None) -> dict:
    """
    Преобразует тип задачи и спецификацию в конфигурацию Firecrawl.

    Маппинг типов:
    - search -> search + scrape (поиск по запросу, затем скрейпинг результатов)
    - crawl -> crawl (обход всех страниц сайта)
    - scrape -> scrape (скрейпинг конкретных URL)
    - extract -> scrape + JSON schema (извлечение структурированных данных)
    - multi_step -> pipeline (поиск -> crawl -> extract)
    """
    spec = normalized_spec or {}

    # Базовая конфигурация
    config = {
        "mode": job_type,  # режим работы
        "formats": ["markdown"],  # формат по умолчанию
        "limit": spec.get("limit", RESEARCH_MAX_PAGES_PER_JOB),
    }

    if job_type == "search":
        # Поиск: используем запрос пользователя как search query
        config["search_query"] = spec.get("query", spec.get("objective", ""))
        config["search_limit"] = spec.get("search_limit", 10)

    elif job_type == "crawl":
        # Обход сайта: лимит страниц, глубина
        config["max_depth"] = spec.get("max_depth", 3)
        config["include_paths"] = spec.get("include_paths", [])
        config["exclude_paths"] = spec.get("exclude_paths", [])

    elif job_type == "scrape":
        # Скрейпинг: конкретные URL
        config["urls"] = spec.get("urls", [])
        config["formats"] = spec.get("formats", ["markdown", "html"])

    elif job_type == "extract":
        # Извлечение: JSON-схема для LLM extraction
        config["extraction_schema"] = spec.get("extraction_schema", {})
        config["only_main_content"] = spec.get("only_main_content", True)

    elif job_type == "multi_step":
        # Multi-step: последовательный pipeline
        config["steps"] = spec.get("steps", ["search", "scrape", "extract"])
        config["extraction_schema"] = spec.get("extraction_schema", {})

    # Общие параметры из спецификации
    if "urls" in spec and job_type != "scrape":
        config["seed_urls"] = spec["urls"]
    if "domains" in spec:
        config["allowed_domains"] = spec["domains"]
    if "language" in spec:
        config["language"] = spec["language"]

    logger.info("Маппинг job_type=%s -> config: %s", job_type, {k: v for k, v in config.items() if k != "extraction_schema"})
    return config
