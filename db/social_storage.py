"""
CRUD-слой для Social Monitor домена.
Все функции работают с social_sources, social_posts, social_parse_runs.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SocialSource, SocialPost, SocialParseRun


# ── SocialSource ──────────────────────────────────────────────────────────────

async def create_source(
    session: AsyncSession,
    created_by: int,
    platform: str,
    source_url: str,
    source_id: str,
    source_name: str = "",
    source_type: str = "profile",
    collection_config: dict | None = None,
    schedule: dict | None = None,
    source_meta: dict | None = None,
    workspace_id: str | None = None,
) -> SocialSource:
    """Создаёт новый источник мониторинга."""
    obj = SocialSource(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        created_by=created_by,
        platform=platform,
        source_url=source_url,
        source_id=source_id,
        source_name=source_name,
        source_type=source_type,
        collection_config=collection_config or {"results_type": "posts", "metrics": True, "media": True, "limit": 50},
        schedule=schedule or {"interval_hours": 6},
        source_meta=source_meta,
        status="active",
    )
    session.add(obj)
    await session.flush()
    return obj


async def get_source(session: AsyncSession, source_id: str, user_id: int | None = None) -> SocialSource | None:
    stmt = select(SocialSource).where(SocialSource.id == source_id)
    if user_id:
        stmt = stmt.where(SocialSource.created_by == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_sources(
    session: AsyncSession,
    user_id: int,
    workspace_id: str | None = None,
    platform: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[SocialSource]:
    stmt = select(SocialSource).where(SocialSource.created_by == user_id)
    if workspace_id:
        stmt = stmt.where(SocialSource.workspace_id == workspace_id)
    if platform:
        stmt = stmt.where(SocialSource.platform == platform)
    if status:
        stmt = stmt.where(SocialSource.status == status)
    stmt = stmt.order_by(SocialSource.created_at.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def list_due_sources(session: AsyncSession) -> list[SocialSource]:
    """Возвращает активные источники у которых пришло время парсинга."""
    now = datetime.now(timezone.utc)
    stmt = select(SocialSource).where(SocialSource.status == "active")
    sources = list((await session.execute(stmt)).scalars().all())
    due = []
    for s in sources:
        sched = s.schedule or {}
        interval_hours = sched.get("interval_hours", 6)
        if s.last_parsed_at is None:
            due.append(s)
        else:
            lp = s.last_parsed_at
            if lp.tzinfo is None:
                lp = lp.replace(tzinfo=timezone.utc)
            delta_hours = (now - lp).total_seconds() / 3600
            if delta_hours >= interval_hours:
                due.append(s)
    return due


async def update_source(session: AsyncSession, source_id: str, **kwargs) -> SocialSource | None:
    obj = await session.get(SocialSource, source_id)
    if not obj:
        return None
    for k, v in kwargs.items():
        if hasattr(obj, k):
            setattr(obj, k, v)
    await session.flush()
    return obj


async def delete_source(session: AsyncSession, source_id: str) -> bool:
    obj = await session.get(SocialSource, source_id)
    if not obj:
        return False
    await session.delete(obj)
    await session.flush()
    return True


# ── SocialPost ────────────────────────────────────────────────────────────────

async def save_posts(
    session: AsyncSession,
    source_id: str,
    workspace_id: str | None,
    posts: list[dict],
) -> tuple[int, int]:
    """Сохраняет посты, пропуская дубликаты по dedupe_hash. Возвращает (found, new)."""
    found = len(posts)
    new_count = 0
    for p in posts:
        dedupe_hash = p.get("dedupe_hash") or hashlib.sha256(
            f"{source_id}:{p.get('platform_post_id', '')}".encode()
        ).hexdigest()[:16]
        # Проверяем дубликат
        existing = (await session.execute(
            select(SocialPost.id).where(SocialPost.dedupe_hash == dedupe_hash)
        )).scalar_one_or_none()
        if existing:
            continue
        obj = SocialPost(
            id=str(uuid.uuid4()),
            source_id=source_id,
            workspace_id=workspace_id,
            platform_post_id=str(p.get("platform_post_id", "")),
            post_url=p.get("post_url"),
            post_type=p.get("post_type", "text"),
            content=p.get("content"),
            posted_at=p.get("posted_at"),
            author_name=p.get("author_name"),
            author_id=p.get("author_id"),
            metrics=p.get("metrics"),
            media_urls=p.get("media_urls"),
            hashtags=p.get("hashtags"),
            mentions=p.get("mentions"),
            location=p.get("location"),
            raw_data=p.get("raw_data"),
            dedupe_hash=dedupe_hash,
        )
        session.add(obj)
        new_count += 1
    await session.flush()
    return found, new_count


async def get_posts(
    session: AsyncSession,
    source_id: str,
    offset: int = 0,
    limit: int = 50,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    post_type: str | None = None,
) -> list[SocialPost]:
    stmt = select(SocialPost).where(SocialPost.source_id == source_id)
    if search:
        stmt = stmt.where(SocialPost.content.ilike(f"%{search}%"))
    if date_from:
        stmt = stmt.where(SocialPost.posted_at >= date_from)
    if date_to:
        stmt = stmt.where(SocialPost.posted_at <= date_to)
    if post_type:
        stmt = stmt.where(SocialPost.post_type == post_type)
    stmt = stmt.order_by(SocialPost.posted_at.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def count_posts(session: AsyncSession, source_id: str) -> int:
    stmt = select(func.count()).select_from(SocialPost).where(SocialPost.source_id == source_id)
    return (await session.execute(stmt)).scalar_one()


async def get_feed_posts(
    session: AsyncSession,
    workspace_id: str,
    source_ids: list[str] | None = None,
    platform: str | None = None,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    post_type: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[SocialPost], int]:
    """Общая лента постов по workspace с фильтрами."""
    stmt = select(SocialPost).where(SocialPost.workspace_id == workspace_id)
    if source_ids:
        stmt = stmt.where(SocialPost.source_id.in_(source_ids))
    if platform:
        stmt = stmt.join(SocialSource, SocialPost.source_id == SocialSource.id)\
                   .where(SocialSource.platform == platform)
    if search:
        stmt = stmt.where(SocialPost.content.ilike(f"%{search}%"))
    if date_from:
        stmt = stmt.where(SocialPost.posted_at >= date_from)
    if date_to:
        stmt = stmt.where(SocialPost.posted_at <= date_to)
    if post_type:
        stmt = stmt.where(SocialPost.post_type == post_type)
    total = (await session.execute(
        select(func.count()).select_from(stmt.subquery())
    )).scalar_one()
    stmt = stmt.order_by(SocialPost.posted_at.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all()), total


# ── SocialParseRun ────────────────────────────────────────────────────────────

async def create_run(session: AsyncSession, source_id: str) -> SocialParseRun:
    obj = SocialParseRun(
        id=str(uuid.uuid4()),
        source_id=source_id,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    session.add(obj)
    await session.flush()
    return obj


async def update_run(session: AsyncSession, run_id: str, **kwargs) -> SocialParseRun | None:
    obj = await session.get(SocialParseRun, run_id)
    if not obj:
        return None
    for k, v in kwargs.items():
        if hasattr(obj, k):
            setattr(obj, k, v)
    await session.flush()
    return obj


async def list_runs(session: AsyncSession, source_id: str, limit: int = 20) -> list[SocialParseRun]:
    stmt = select(SocialParseRun).where(SocialParseRun.source_id == source_id)\
           .order_by(SocialParseRun.created_at.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


# ── Sparkline данные ──────────────────────────────────────────────────────────

async def get_daily_post_counts(
    session: AsyncSession,
    source_id: str,
    days: int = 7,
) -> list[dict]:
    """Количество постов по дням за последние N дней (для sparkline)."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = select(
        func.date(SocialPost.posted_at).label("day"),
        func.count().label("count"),
    ).where(
        SocialPost.source_id == source_id,
        SocialPost.posted_at >= cutoff,
    ).group_by(func.date(SocialPost.posted_at)).order_by(func.date(SocialPost.posted_at))
    rows = (await session.execute(stmt)).fetchall()
    return [{"day": str(r.day), "count": r.count} for r in rows]


async def get_sparklines_batch(
    session: AsyncSession,
    source_ids: list[str],
    days: int = 7,
) -> dict[str, list[dict]]:
    """Batch-получение sparkline данных для нескольких источников."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = select(
        SocialPost.source_id,
        func.date(SocialPost.posted_at).label("day"),
        func.count().label("count"),
    ).where(
        SocialPost.source_id.in_(source_ids),
        SocialPost.posted_at >= cutoff,
    ).group_by(SocialPost.source_id, func.date(SocialPost.posted_at)).order_by(
        SocialPost.source_id, func.date(SocialPost.posted_at)
    )
    rows = (await session.execute(stmt)).fetchall()
    # Группируем по source_id
    result: dict[str, list[dict]] = {sid: [] for sid in source_ids}
    for r in rows:
        result[r.source_id].append({"day": str(r.day), "count": r.count})
    return result


# ── Проверка активного парсинга ───────────────────────────────────────────────

async def has_running_run(session: AsyncSession, source_id: str) -> bool:
    """Проверяет есть ли активный (running) запуск для источника."""
    stmt = select(func.count()).select_from(SocialParseRun).where(
        SocialParseRun.source_id == source_id,
        SocialParseRun.status == "running",
    )
    count = (await session.execute(stmt)).scalar_one()
    return count > 0
