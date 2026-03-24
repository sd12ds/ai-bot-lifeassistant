"""
ParseEngine — основной pipeline парсинга одного источника.
create run → collect posts → deduplicate → save → update next_run_at → notify.
"""
from __future__ import annotations

import dataclasses
import logging
from datetime import datetime, timezone

from db.session import get_async_session
from db import social_storage as storage

logger = logging.getLogger(__name__)


def _get_provider(platform: str):
    """Получает провайдер по платформе."""
    if platform == "instagram":
        from integrations.social.instagram.provider import InstagramProvider
        return InstagramProvider()
    elif platform == "telegram":
        from integrations.social.telegram_parser.provider import TelegramProvider
        return TelegramProvider()
    raise ValueError(f"Неизвестная платформа: {platform}")


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

    try:
        provider = _get_provider(source.platform)
        config = source.collection_config or {}
        results_type = config.get("results_type", "posts")
        limit = config.get("limit", 50)

        # Инкрементальный сбор — только новые посты
        since = source.last_parsed_at
        if since and since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        logger.info("ParseEngine: source=%s platform=%s type=%s since=%s", source_id, source.platform, results_type, since)

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
                metrics={"results_type": results_type},
            )
            await storage.update_source(session, source_id,
                last_parsed_at=datetime.now(timezone.utc),
                error_count=0,
                last_error=None,
            )
            await session.commit()

        logger.info("ParseEngine completed: source=%s found=%d new=%d", source_id, posts_found, posts_new)

        # Уведомление в Telegram
        if notify_callback and posts_new > 0:
            try:
                await notify_callback(source.created_by, f"[{source.platform}] {source.source_name}: +{posts_new} новых постов")
            except Exception:
                pass

        return {"status": "completed", "posts_found": posts_found, "posts_new": posts_new}

    except Exception as e:
        error_msg = str(e)
        logger.error("ParseEngine failed: source=%s error=%s", source_id, e, exc_info=True)
        async with get_async_session() as session:
            await storage.update_run(session, run.id,
                status="failed",
                finished_at=datetime.now(timezone.utc),
                error_details=error_msg,
            )
            # Увеличиваем счётчик ошибок; после 5 — ставим на паузу
            new_error_count = (source.error_count or 0) + 1
            new_status = "error" if new_error_count >= 5 else source.status
            await storage.update_source(session, source_id,
                error_count=new_error_count,
                last_error=error_msg[:500],
                status=new_status,
            )
            await session.commit()

        return {"status": "failed", "error": error_msg}
