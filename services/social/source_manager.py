"""
SourceManager — CRUD источников мониторинга соцсетей + auto-resolve URL.
"""
from __future__ import annotations

import logging
from db.session import get_async_session
from db import social_storage as storage
from integrations.social import get_provider

logger = logging.getLogger(__name__)


def _detect_platform(url: str) -> str:
    """Определяет платформу по URL."""
    url = url.lower()
    if "instagram.com" in url or url.startswith("@") and "." not in url.split("@")[-1]:
        return "instagram"
    if "t.me" in url or "telegram.me" in url:
        return "telegram"
    if "vk.com" in url:
        return "vk"
    if "tiktok.com" in url:
        return "tiktok"
    # Fallback — если это просто @username без домена, пробуем Telegram
    if url.startswith("@"):
        return "telegram"
    return "instagram"


async def resolve_source(url: str) -> dict:
    """Резолвит URL → информация об источнике (без сохранения)."""
    platform = _detect_platform(url)
    provider = get_provider(platform)
    info = await provider.resolve_url(url)
    return {
        "platform": platform,
        "source_id": info.source_id,
        "source_name": info.source_name,
        "source_type": info.source_type,
        "subscribers_count": info.subscribers_count,
        "description": info.description,
        "photo_url": info.photo_url,
        "is_verified": info.is_verified,
        "extra": info.extra,
    }


async def create_source(
    user_id: int,
    url: str,
    collection_config: dict | None = None,
    schedule: dict | None = None,
    workspace_id: str | None = None,
) -> dict:
    """Резолвит URL и сохраняет источник в БД."""
    info = await resolve_source(url)
    platform = info["platform"]
    async with get_async_session() as session:
        source = await storage.create_source(
            session=session,
            created_by=user_id,
            platform=platform,
            source_url=url,
            source_id=info["source_id"],
            source_name=info["source_name"],
            source_type=info["source_type"],
            collection_config=collection_config,
            schedule=schedule,
            source_meta={
                "subscribers_count": info["subscribers_count"],
                "photo_url": info["photo_url"],
                "is_verified": info["is_verified"],
                **info.get("extra", {}),
            },
            workspace_id=workspace_id,
        )
        await session.commit()
        logger.info("Source создан: id=%s platform=%s source_id=%s", source.id, platform, info["source_id"])
        return _source_to_dict(source)


async def get_source(user_id: int, source_id: str) -> dict | None:
    async with get_async_session() as session:
        obj = await storage.get_source(session, source_id, user_id)
        return _source_to_dict(obj) if obj else None


async def list_sources(user_id: int, workspace_id: str | None = None, platform: str | None = None) -> list[dict]:
    async with get_async_session() as session:
        sources = await storage.list_sources(session, user_id, workspace_id=workspace_id, platform=platform)
        return [_source_to_dict(s) for s in sources]


async def update_source(user_id: int, source_id: str, **kwargs) -> dict | None:
    async with get_async_session() as session:
        obj = await storage.get_source(session, source_id, user_id)
        if not obj:
            return None
        updated = await storage.update_source(session, source_id, **kwargs)
        await session.commit()
        return _source_to_dict(updated)


async def delete_source(user_id: int, source_id: str) -> bool:
    async with get_async_session() as session:
        obj = await storage.get_source(session, source_id, user_id)
        if not obj:
            return False
        await storage.delete_source(session, source_id)
        await session.commit()
        return True


def _source_to_dict(s) -> dict:
    return {
        "id": s.id, "platform": s.platform, "source_url": s.source_url,
        "source_id": s.source_id, "source_name": s.source_name, "source_type": s.source_type,
        "status": s.status, "workspace_id": s.workspace_id, "created_by": s.created_by,
        "collection_config": s.collection_config, "schedule": s.schedule,
        "source_meta": s.source_meta, "last_parsed_at": s.last_parsed_at.isoformat() if s.last_parsed_at else None,
        "error_count": s.error_count, "last_error": s.last_error,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
