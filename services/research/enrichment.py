"""
Enrichment pipeline - обогащение данных после сбора.
Phase 5: базовое обогащение через regex (email, phone, domain info).
Future: Hunter.io, LinkedIn API, CrunchBase API.
"""
from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)

# Regex-паттерны для извлечения контактов из raw_content
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(
    r"(?:\+7|8)?[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
    r"|(?:\+\d{1,3}[\s\-]?)?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{4}",
)


def _extract_emails(text: str) -> list[str]:
    """Извлекает уникальные email-адреса из текста."""
    return list(dict.fromkeys(_EMAIL_RE.findall(text)))


def _extract_phones(text: str) -> list[str]:
    """Извлекает уникальные номера телефонов из текста."""
    raw = _PHONE_RE.findall(text)
    # Нормализация: убираем пробелы и дубли
    seen, result = set(), []
    for p in raw:
        norm = re.sub(r"[\s\-()]", "", p)
        if len(norm) >= 10 and norm not in seen:
            seen.add(norm)
            result.append(p.strip())
    return result


async def enrich_results(items: list[dict], enrichment_config: dict | None = None) -> list[dict]:
    """Обогащает результаты дополнительными данными.

    Цепочка: collect -> extract -> ENRICH -> persist
    Phase 5: извлечение email/phone через regex из raw_content.
    Future: Hunter.io, LinkedIn, CrunchBase.
    """
    if not enrichment_config and not items:
        return items

    enriched = []
    emails_found = 0
    phones_found = 0

    for item in items:
        raw = item.get("raw_content", "")
        extracted = item.setdefault("extracted_fields", {}) or {}

        # Базовое обогащение по домену
        domain = item.get("domain", "")
        if domain:
            extracted["_domain_info"] = {"domain": domain}

        # Извлечение email из контента (если не было задано через LLM extraction)
        if raw and "email" not in extracted:
            emails = _extract_emails(raw)
            if emails:
                extracted["email"] = emails[0] if len(emails) == 1 else emails
                emails_found += 1

        # Извлечение телефона из контента
        if raw and "phone" not in extracted:
            phones = _extract_phones(raw)
            if phones:
                extracted["phone"] = phones[0] if len(phones) == 1 else phones
                phones_found += 1

        item["extracted_fields"] = extracted

        # TODO Phase 5+: email lookup через Hunter.io / Snov.io
        # TODO Phase 5+: social profiles через LinkedIn API
        # TODO Phase 5+: company info через CrunchBase API

        enriched.append(item)

    logger.info(
        "Enrichment: %d items, %d emails found, %d phones found",
        len(enriched), emails_found, phones_found,
    )
    return enriched
