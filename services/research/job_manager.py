"""
JobManager - управление жизненным циклом research-задач.
Валидация, создание, обновление, отмена задач.
"""
from __future__ import annotations

import logging
from db.session import get_async_session
from db import research_storage as storage

logger = logging.getLogger(__name__)


async def create_research_job(
    user_id: int,
    title: str,
    job_type: str = "search",
    description: str | None = None,
    original_request: str | None = None,
    normalized_spec: dict | None = None,
    config: dict | None = None,
    origin: str = "chat",
    tags: dict | None = None,
) -> dict:
    """Создает новую задачу и возвращает её данные."""
    async with get_async_session() as session:
        job = await storage.create_job(
            session=session,
            created_by=user_id,
            title=title,
            job_type=job_type,
            description=description,
            original_request=original_request,
            normalized_spec=normalized_spec,
            config=config,
            origin=origin,
            tags=tags,
        )
        await session.commit()
        logger.info("Job создан: id=%s user=%d type=%s", job.id, user_id, job_type)
        return {"id": job.id, "title": job.title, "status": job.status, "job_type": job.job_type}


async def get_job(user_id: int, job_id: str) -> dict | None:
    """Получает задачу по ID с проверкой владельца."""
    async with get_async_session() as session:
        job = await storage.get_job(session, job_id, user_id)
        if not job:
            return None
        return _job_to_dict(job)


async def list_jobs(user_id: int, status_filter: str | None = None, offset: int = 0, limit: int = 50) -> list[dict]:
    """Список задач пользователя."""
    async with get_async_session() as session:
        jobs = await storage.list_jobs(session, user_id, status_filter=status_filter, offset=offset, limit=limit)
        return [_job_to_dict(j) for j in jobs]


async def cancel_job(user_id: int, job_id: str) -> dict | None:
    """Отменяет задачу."""
    async with get_async_session() as session:
        job = await storage.get_job(session, job_id, user_id)
        if not job or job.status in ("completed", "canceled", "archived"):
            return None
        job = await storage.update_job_status(session, job_id, "canceled", actor_id=user_id, source="chat")
        await session.commit()
        logger.info("Job отменен: id=%s user=%d", job_id, user_id)
        return _job_to_dict(job)


def _job_to_dict(job) -> dict:
    """Конвертация ORM -> dict."""
    return {
        "id": job.id, "title": job.title, "description": job.description,
        "status": job.status, "job_type": job.job_type, "provider": job.provider,
        "origin": job.origin, "created_by": job.created_by,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
    }
