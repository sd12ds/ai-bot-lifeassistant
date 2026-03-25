"""
ParseEngine — основной pipeline парсинга одного источника.
create run → collect posts → deduplicate → save → update next_run_at → notify.
С retry-логикой: transient-ошибки повторяются через exponential backoff.
"""
from __future__ import annotations

import asyncio
import dataclasses
import logging
from datetime import datetime, timezone

from db.session import get_async_session
from db import social_storage as storage
from integrations.social import get_provider

logger = logging.getLogger(__name__)

# Максимальное число повторов для transient-ошибок
MAX_RETRIES = 3
# Задержки между повторами (exponential backoff), секунды
RETRY_DELAYS = [30, 60, 120]


def _is_transient(error: Exception) -> bool:
    """Классифицирует ошибку как временную (можно повторить)."""
    err_str = str(error).lower()
    err_type = type(error).__name__
    # HTTP-коды: 429 (rate-limit), 502, 503 (server errors)
    transient_codes = ["429", "502", "503", "504"]
    if any(code in err_str for code in transient_codes):
        return True
    # Типы ошибок: timeout, connection
    transient_types = ["timeout", "connectionerror", "connecttimeout", "floodwait"]
    if any(t in err_type.lower() for t in transient_types):
        return True
    if any(t in err_str for t in ["timeout", "connection reset", "connection refused", "temporarily unavailable"]):
        return True
    return False


async def run_source(source_id: str, notify_callback=None) -> dict:
    """Запускает полный pipeline парсинга для одного источника."""
    async with get_async_session() as session:
        source = await storage.get_source(session, source_id)
        if not source:
            return {"error": f"Source {source_id} не найден"}

        # Создаём run
        run = await storage.create_run(session, source_id)
        await session.commit()

    posts_found = 0
    posts_new = 0
    error_msg = None
    retry_count = 0

    while True:
        try:
            provider = get_provider(source.platform)
            config = source.collection_config or {}
            results_type = config.get("results_type", "posts")
            limit = config.get("limit", 50)

            # Инкрементальный сбор — только новые посты
            since = source.last_parsed_at
            if since and since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)

            logger.info("ParseEngine: source=%s platform=%s type=%s since=%s attempt=%d",
                        source_id, source.platform, results_type, since, retry_count + 1)

            # Собираем посты через провайдер
            parsed_posts = await provider.get_posts(
                source_id=source.source_id,
                results_type=results_type,
                since=since,
                limit=limit,
            )

            # Конвертируем ParsedPost → dict для storage
            posts_dicts = [dataclasses.asdict(p) for p in parsed_posts]

            # Сохраняем (дедупликация внутри save_posts)
            async with get_async_session() as session:
                posts_found, posts_new = await storage.save_posts(
                    session, source_id, source.workspace_id, posts_dicts
                )
                # Обновляем run и источник
                await storage.update_run(session, run.id,
                    status="completed",
                    finished_at=datetime.now(timezone.utc),
                    posts_found=posts_found,
                    posts_new=posts_new,
                    metrics={"results_type": results_type, "retry_count": retry_count},
                )
                await storage.update_source(session, source_id,
                    last_parsed_at=datetime.now(timezone.utc),
                    error_count=0,
                    last_error=None,
                )
                await session.commit()

            logger.info("ParseEngine completed: source=%s found=%d new=%d retries=%d",
                        source_id, posts_found, posts_new, retry_count)

            # Уведомление в Telegram
            if notify_callback and posts_new > 0:
                try:
                    await notify_callback(
                        source.created_by,
                        f"[{source.platform}] {source.source_name}: +{posts_new} новых постов"
                    )
                except Exception:
                    pass

            return {"status": "completed", "posts_found": posts_found, "posts_new": posts_new}

        except Exception as e:
            error_msg = str(e)

            # Классифицируем ошибку
            if _is_transient(e) and retry_count < MAX_RETRIES:
                # Transient-ошибка — повторяем с backoff, НЕ инкрементируем error_count
                delay = RETRY_DELAYS[min(retry_count, len(RETRY_DELAYS) - 1)]
                retry_count += 1
                logger.warning(
                    "ParseEngine transient error (attempt %d/%d): source=%s error=%s → retry in %ds",
                    retry_count, MAX_RETRIES, source_id, e, delay,
                )
                # Обновляем run с информацией о retry
                async with get_async_session() as session:
                    await storage.update_run(session, run.id,
                        metrics={"retry_count": retry_count, "last_error": error_msg[:200]},
                    )
                    await session.commit()
                await asyncio.sleep(delay)
                continue  # Повтор цикла

            # Permanent-ошибка или исчерпаны retry — фиксируем
            logger.error("ParseEngine failed: source=%s error=%s retries=%d", source_id, e, retry_count, exc_info=True)
            async with get_async_session() as session:
                await storage.update_run(session, run.id,
                    status="failed",
                    finished_at=datetime.now(timezone.utc),
                    error_details=error_msg,
                    metrics={"retry_count": retry_count, "is_transient": _is_transient(e)},
                )
                # Инкрементируем error_count; после 5 — статус error
                new_error_count = (source.error_count or 0) + 1
                new_status = "error" if new_error_count >= 5 else source.status
                await storage.update_source(session, source_id,
                    error_count=new_error_count,
                    last_error=error_msg[:500],
                    status=new_status,
                )
                await session.commit()

            return {"status": "failed", "error": error_msg, "retries": retry_count}
