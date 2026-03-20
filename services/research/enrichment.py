"""
Enrichment pipeline - обогащение данных после сбора.
Phase 5: email lookup, social profiles, company info.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


async def enrich_results(items: list[dict], enrichment_config: dict | None = None) -> list[dict]:
    """Обогащает результаты дополнительными данными.

    Цепочка: collect -> extract -> ENRICH -> persist
    Пока заглушка - добавляет domain-based обогащение.
    В будущем: email lookup, social profiles, company databases.
    """
    if not enrichment_config:
        return items

    enriched = []
    for item in items:
        # Базовое обогащение по домену
        domain = item.get("domain", "")
        if domain:
            item.setdefault("extracted_fields", {})
            item["extracted_fields"]["_enriched"] = True
            item["extracted_fields"]["_domain_info"] = {"domain": domain}

        # TODO Phase 5+: email lookup через Hunter.io / Snov.io
        # TODO Phase 5+: social profiles через LinkedIn API
        # TODO Phase 5+: company info через CrunchBase API

        enriched.append(item)

    logger.info("Enriched %d items", len(enriched))
    return enriched
