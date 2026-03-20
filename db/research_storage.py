"""
CRUD-слой для Research домена.
Все функции принимают AsyncSession и работают с research_* таблицами.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    ResearchTemplate,
    ResearchJob,
    ResearchJobRun,
    ResearchResultItem,
    ResearchSource,
    ResearchMessageLog,
    ResearchStatusEvent,
)


# ==============================================================================
# ResearchJob CRUD
# ==============================================================================

async def create_job(
    session: AsyncSession,
    created_by: int,
    title: str,
    job_type: str = "search",
    description: str | None = None,
    original_request: str | None = None,
    normalized_spec: dict | None = None,
    provider: str = "firecrawl",
    config: dict | None = None,
    visibility: str = "private",
    origin: str = "chat",
    tags: dict | None = None,
    workspace_id: str | None = None,
) -> ResearchJob:
    """Создает новую задачу исследования в статусе draft."""
    job = ResearchJob(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        created_by=created_by,
        title=title,
        description=description,
        original_request=original_request,
        normalized_spec=normalized_spec,
        status="draft",
        job_type=job_type,
        provider=provider,
        config=config,
        visibility=visibility,
        origin=origin,
        tags=tags,
    )
    session.add(job)
    await session.flush()
    # Создаем начальное событие статуса
    await _add_status_event(
        session, job.id, None, "status_change", None, "draft", created_by, origin
    )
    return job


async def get_job(
    session: AsyncSession, job_id: str, user_id: int | None = None
) -> ResearchJob | None:
    """Получает задачу по ID. Если user_id указан - проверяет владельца."""
    stmt = select(ResearchJob).where(ResearchJob.id == job_id)
    if user_id is not None:
        stmt = stmt.where(ResearchJob.created_by == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_jobs(
    session: AsyncSession,
    user_id: int,
    status_filter: str | None = None,
    workspace_id: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[ResearchJob]:
    """Список задач пользователя с фильтрацией и пагинацией."""
    stmt = select(ResearchJob).where(ResearchJob.created_by == user_id)
    if workspace_id:
        stmt = stmt.where(ResearchJob.workspace_id == workspace_id)
    if status_filter:
        stmt = stmt.where(ResearchJob.status == status_filter)
    stmt = stmt.order_by(ResearchJob.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_job(
    session: AsyncSession, job_id: str, **kwargs
) -> ResearchJob | None:
    """Обновляет поля задачи (кроме статуса - для этого update_job_status)."""
    job = await session.get(ResearchJob, job_id)
    if not job:
        return None
    for key, value in kwargs.items():
        if hasattr(job, key) and key != "status":
            setattr(job, key, value)
    await session.flush()
    return job


async def update_job_status(
    session: AsyncSession,
    job_id: str,
    new_status: str,
    actor_id: int | None = None,
    source: str = "system",
    run_id: str | None = None,
) -> ResearchJob | None:
    """Обновляет статус задачи и создает событие смены статуса."""
    job = await session.get(ResearchJob, job_id)
    if not job:
        return None
    old_status = job.status
    job.status = new_status
    # Запись события смены статуса
    await _add_status_event(
        session, job_id, run_id, "status_change", old_status, new_status, actor_id, source
    )
    await session.flush()
    return job


# ==============================================================================
# ResearchJobRun CRUD
# ==============================================================================

async def create_run(session: AsyncSession, job_id: str) -> ResearchJobRun:
    """Создает новый запуск задачи в статусе queued."""
    run = ResearchJobRun(
        id=str(uuid.uuid4()),
        job_id=job_id,
        status="queued",
    )
    session.add(run)
    await session.flush()
    return run


async def get_run(session: AsyncSession, run_id: str) -> ResearchJobRun | None:
    """Получает запуск по ID."""
    return await session.get(ResearchJobRun, run_id)


async def list_runs(session: AsyncSession, job_id: str) -> list[ResearchJobRun]:
    """Список запусков задачи, отсортированных по дате."""
    stmt = (
        select(ResearchJobRun)
        .where(ResearchJobRun.job_id == job_id)
        .order_by(ResearchJobRun.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_run(
    session: AsyncSession, run_id: str, **kwargs
) -> ResearchJobRun | None:
    """Обновляет поля запуска (статус, метрики, ошибки и т.д.)."""
    run = await session.get(ResearchJobRun, run_id)
    if not run:
        return None
    for key, value in kwargs.items():
        if hasattr(run, key):
            setattr(run, key, value)
    await session.flush()
    return run


# ==============================================================================
# ResearchResultItem CRUD
# ==============================================================================

async def save_results(
    session: AsyncSession,
    job_id: str,
    run_id: str,
    items: list[dict],
) -> list[ResearchResultItem]:
    """Массовое сохранение результатов задачи."""
    result_objects = []
    for item in items:
        obj = ResearchResultItem(
            id=str(uuid.uuid4()),
            job_id=job_id,
            run_id=run_id,
            source_url=item.get("source_url"),
            domain=item.get("domain"),
            title=item.get("title"),
            raw_content=item.get("raw_content"),
            extracted_fields=item.get("extracted_fields"),
            dedupe_hash=item.get("dedupe_hash"),
            extra_metadata=item.get("metadata"),
        )
        session.add(obj)
        result_objects.append(obj)
    await session.flush()
    return result_objects


async def get_results(
    session: AsyncSession,
    job_id: str,
    offset: int = 0,
    limit: int = 100,
) -> list[ResearchResultItem]:
    """Получает результаты задачи с пагинацией."""
    stmt = (
        select(ResearchResultItem)
        .where(ResearchResultItem.job_id == job_id)
        .order_by(ResearchResultItem.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_result_count(session: AsyncSession, job_id: str) -> int:
    """Количество результатов задачи."""
    stmt = (
        select(func.count())
        .select_from(ResearchResultItem)
        .where(ResearchResultItem.job_id == job_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


# ==============================================================================
# ResearchSource CRUD
# ==============================================================================

async def add_sources(
    session: AsyncSession,
    job_id: str,
    sources: list[dict],
) -> list[ResearchSource]:
    """Массовое добавление источников задачи."""
    source_objects = []
    for src in sources:
        obj = ResearchSource(
            id=str(uuid.uuid4()),
            job_id=job_id,
            url=src["url"],
            domain=src.get("domain"),
            source_type=src.get("source_type", "seed"),
            status=src.get("status", "pending"),
            extra_metadata=src.get("metadata"),
        )
        session.add(obj)
        source_objects.append(obj)
    await session.flush()
    return source_objects


async def list_sources(
    session: AsyncSession, job_id: str
) -> list[ResearchSource]:
    """Список источников задачи."""
    stmt = (
        select(ResearchSource)
        .where(ResearchSource.job_id == job_id)
        .order_by(ResearchSource.source_type)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ==============================================================================
# ResearchMessageLog CRUD
# ==============================================================================

async def add_message_log(
    session: AsyncSession,
    job_id: str,
    role: str,
    content: str,
) -> ResearchMessageLog:
    """Добавляет запись в лог сообщений задачи."""
    msg = ResearchMessageLog(
        id=str(uuid.uuid4()),
        job_id=job_id,
        role=role,
        content=content,
    )
    session.add(msg)
    await session.flush()
    return msg


async def get_message_logs(
    session: AsyncSession, job_id: str
) -> list[ResearchMessageLog]:
    """Получает историю сообщений задачи."""
    stmt = (
        select(ResearchMessageLog)
        .where(ResearchMessageLog.job_id == job_id)
        .order_by(ResearchMessageLog.created_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ==============================================================================
# Вспомогательная функция - создание события статуса
# ==============================================================================

async def _add_status_event(
    session: AsyncSession,
    job_id: str,
    run_id: str | None,
    event_type: str,
    old_status: str | None,
    new_status: str | None,
    actor_id: int | None,
    source: str | None,
) -> ResearchStatusEvent:
    """Создает событие смены статуса (внутренняя функция)."""
    event = ResearchStatusEvent(
        id=str(uuid.uuid4()),
        job_id=job_id,
        run_id=run_id,
        event_type=event_type,
        old_status=old_status,
        new_status=new_status,
        actor_id=actor_id,
        source=source,
    )
    session.add(event)
    await session.flush()
    return event


# ==============================================================================
# ResearchTemplate CRUD
# ==============================================================================

async def create_template(session: AsyncSession, created_by: int, name: str, description: str | None = None,
                          spec_template: dict | None = None, is_public: bool = False, workspace_id: str | None = None) -> ResearchTemplate:
    t = ResearchTemplate(id=str(uuid.uuid4()), workspace_id=workspace_id, created_by=created_by,
                         name=name, description=description, spec_template=spec_template, is_public=is_public)
    session.add(t)
    await session.flush()
    return t


async def list_templates(session: AsyncSession, user_id: int, workspace_id: str | None = None) -> list[ResearchTemplate]:
    from sqlalchemy import or_
    stmt = select(ResearchTemplate).where(
        or_(ResearchTemplate.created_by == user_id, ResearchTemplate.is_public == True)
    ).order_by(ResearchTemplate.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_template(session: AsyncSession, template_id: str) -> ResearchTemplate | None:
    return await session.get(ResearchTemplate, template_id)


async def delete_template(session: AsyncSession, template_id: str) -> bool:
    t = await session.get(ResearchTemplate, template_id)
    if not t:
        return False
    await session.delete(t)
    await session.flush()
    return True
