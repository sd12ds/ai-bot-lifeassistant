"""
ResultProcessor - дедупликация, нормализация, хеширование результатов.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse


def process_results(raw_items: list[dict]) -> list[dict]:
    """Обрабатывает сырые результаты: дедупликация, нормализация, хеш."""
    seen_hashes = set()
    processed = []
    for item in raw_items:
        # Нормализация URL
        url = item.get("source_url", item.get("url", ""))
        domain = urlparse(url).netloc if url else ""
        # Очистка контента
        raw = item.get("raw_content", item.get("markdown", ""))
        title = item.get("title", "")
        # Дедупликация по хешу URL + контент
        dedupe_hash = hashlib.sha256(f"{url}:{raw[:500]}".encode()).hexdigest()[:16]
        if dedupe_hash in seen_hashes:
            continue
        seen_hashes.add(dedupe_hash)
        processed.append({
            "source_url": url,
            "domain": domain,
            "title": title,
            "raw_content": raw,
            "extracted_fields": item.get("extracted_fields"),
            "dedupe_hash": dedupe_hash,
            "metadata": item.get("metadata"),
        })
    return processed
