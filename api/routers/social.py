"""
FastAPI роутер для Social Monitor домена.
CRUD источников, запуск парсинга, просмотр постов, статистика.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from db.session import get_session
from db import social_storage as storage
from services.social import source_manager, parse_engine
from services.auth.permission_checker import get_workspace_context

router = APIRouter(prefix="/social", tags=["social"])


# ── Pydantic схемы ────────────────────────────────────────────────────────────

class SourceCreate(BaseModel):
    url: str
    collection_config: dict | None = None
    schedule: dict | None = None

class SourceUpdate(BaseModel):
    source_name: str | None = None
    collection_config: dict | None = None
    schedule: dict | None = None
    status: str | None = None

class ResolveRequest(BaseModel):
    url: str


# ── Resolve URL (preview перед добавлением) ───────────────────────────────────

@router.post("/resolve")
async def resolve_url(data: ResolveRequest, user=Depends(get_current_user)):
    """Предварительный резолв URL — показывает инфо без сохранения (Шаг 1 AddSourceDrawer)."""
    try:
        info = await source_manager.resolve_source(data.url)
        return info
    except Exception as e:
        raise HTTPException(400, f"Не удалось определить источник: {str(e)}")


# ── Sources CRUD ──────────────────────────────────────────────────────────────

@router.post("/sources")
async def create_source(
    data: SourceCreate,
    ctx=Depends(get_workspace_context),
):
    """Создание источника мониторинга с auto-resolve URL."""
    try:
        source = await source_manager.create_source(
            user_id=ctx["user_id"],
            url=data.url,
            collection_config=data.collection_config,
            schedule=data.schedule,
            workspace_id=ctx["workspace_id"],
        )
        return source
    except Exception as e:
        raise HTTPException(400, str(e))


@router.get("/sources")
async def list_sources(
    platform: str | None = None,
    ctx=Depends(get_workspace_context),
):
    """Список источников workspace."""
    sources = await source_manager.list_sources(
        ctx["user_id"], workspace_id=ctx["workspace_id"], platform=platform
    )
    return sources


@router.get("/sources/{source_id}")
async def get_source(source_id: str, ctx=Depends(get_workspace_context)):
    """Детали источника."""
    source = await source_manager.get_source(ctx["user_id"], source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    return source


@router.patch("/sources/{source_id}")
async def update_source(source_id: str, data: SourceUpdate, ctx=Depends(get_workspace_context)):
    """Обновление настроек источника."""
    updates = data.model_dump(exclude_unset=True)
    source = await source_manager.update_source(ctx["user_id"], source_id, **updates)
    if not source:
        raise HTTPException(404, "Source not found")
    return source


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str, ctx=Depends(get_workspace_context)):
    """Удаление источника."""
    ok = await source_manager.delete_source(ctx["user_id"], source_id)
    if not ok:
        raise HTTPException(404, "Source not found")
    return {"status": "deleted", "id": source_id}


# ── Parse trigger ─────────────────────────────────────────────────────────────

@router.post("/sources/{source_id}/parse")
async def trigger_parse(source_id: str, ctx=Depends(get_workspace_context)):
    """Ручной запуск парсинга источника (фоновый)."""
    source = await source_manager.get_source(ctx["user_id"], source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    asyncio.create_task(parse_engine.run_source(source_id))
    return {"status": "started", "source_id": source_id}


# ── Posts ─────────────────────────────────────────────────────────────────────

@router.get("/sources/{source_id}/posts")
async def get_posts(
    source_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    ctx=Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Посты конкретного источника с фильтрами."""
    source = await storage.get_source(session, source_id, ctx["user_id"])
    if not source:
        raise HTTPException(404, "Source not found")
    df = datetime.fromisoformat(date_from) if date_from else None
    dt = datetime.fromisoformat(date_to) if date_to else None
    posts = await storage.get_posts(session, source_id, offset=offset, limit=limit,
                                     search=search, date_from=df, date_to=dt)
    total = await storage.count_posts(session, source_id)
    return {"total": total, "offset": offset, "limit": limit, "items": [_post_dict(p) for p in posts]}


@router.get("/sources/{source_id}/runs")
async def get_runs(source_id: str, ctx=Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    """История запусков источника."""
    source = await storage.get_source(session, source_id, ctx["user_id"])
    if not source:
        raise HTTPException(404, "Source not found")
    runs = await storage.list_runs(session, source_id)
    return [_run_dict(r) for r in runs]


# ── Feed (общая лента) ────────────────────────────────────────────────────────

@router.get("/feed")
async def get_feed(
    source_ids: str | None = None,    # через запятую
    platform: str | None = None,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx=Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Общая лента постов со всех источников workspace."""
    sids = [s.strip() for s in source_ids.split(",")] if source_ids else None
    df = datetime.fromisoformat(date_from) if date_from else None
    dt = datetime.fromisoformat(date_to) if date_to else None
    posts, total = await storage.get_feed_posts(
        session, ctx["workspace_id"],
        source_ids=sids, platform=platform, search=search,
        date_from=df, date_to=dt, offset=offset, limit=limit,
    )
    return {"total": total, "offset": offset, "limit": limit, "items": [_post_dict(p) for p in posts]}


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(ctx=Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    """Статистика для dashboard: источники, посты, ошибки."""
    from sqlalchemy import select, func
    from db.models import SocialSource, SocialPost
    ws_id = ctx["workspace_id"]

    # Источники по статусам
    status_stmt = select(SocialSource.status, func.count())\
        .where(SocialSource.workspace_id == ws_id)\
        .group_by(SocialSource.status)
    status_counts = dict((await session.execute(status_stmt)).fetchall())

    # Посты за неделю
    from datetime import timedelta, timezone
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    week_posts = (await session.execute(
        select(func.count()).select_from(SocialPost)
        .where(SocialPost.workspace_id == ws_id)
        .where(SocialPost.created_at >= week_ago)
    )).scalar_one()

    return {
        "workspace_id": ws_id,
        "total_sources": sum(status_counts.values()),
        "active_sources": status_counts.get("active", 0),
        "error_sources": status_counts.get("error", 0),
        "paused_sources": status_counts.get("paused", 0),
        "posts_this_week": week_posts,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _post_dict(p) -> dict:
    return {
        "id": p.id, "source_id": p.source_id,
        "platform_post_id": p.platform_post_id, "post_url": p.post_url,
        "post_type": p.post_type, "content": p.content,
        "posted_at": p.posted_at.isoformat() if p.posted_at else None,
        "author_name": p.author_name, "author_id": p.author_id,
        "metrics": p.metrics, "media_urls": p.media_urls,
        "hashtags": p.hashtags, "mentions": p.mentions, "location": p.location,
    }

def _run_dict(r) -> dict:
    return {
        "id": r.id, "source_id": r.source_id, "status": r.status,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "posts_found": r.posts_found, "posts_new": r.posts_new,
        "error_details": r.error_details, "metrics": r.metrics,
    }
