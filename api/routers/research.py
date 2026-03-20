"""
FastAPI роутер для Research домена.
CRUD для jobs, results, runs, sources.
"""
from __future__ import annotations

import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from db.session import get_session
from db import research_storage as storage
from services.research.execution_engine import run_job

router = APIRouter(prefix="/research", tags=["research"])


# ── Pydantic-схемы ────────────────────────────────────────────────────────────

class JobCreate(BaseModel):
    title: str
    job_type: str = "search"
    description: str | None = None
    original_request: str | None = None
    normalized_spec: dict | None = None
    config: dict | None = None
    visibility: str = "private"
    tags: dict | None = None

class JobUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    normalized_spec: dict | None = None
    config: dict | None = None
    tags: dict | None = None

class JobResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    status: str
    job_type: str
    provider: str
    origin: str
    visibility: str
    created_by: int
    created_at: str | None = None
    updated_at: str | None = None
    last_run_at: str | None = None

class RunResponse(BaseModel):
    id: str
    job_id: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    metrics: dict | None = None
    error_details: str | None = None

class ResultResponse(BaseModel):
    id: str
    source_url: str | None = None
    domain: str | None = None
    title: str | None = None
    extracted_fields: dict | None = None
    dedupe_hash: str | None = None


# ── Job endpoints ─────────────────────────────────────────────────────────────

@router.post("/jobs", response_model=JobResponse)
async def create_job(
    data: JobCreate,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Создание задачи исследования."""
    job = await storage.create_job(
        session=session,
        created_by=user.telegram_id,
        title=data.title,
        job_type=data.job_type,
        description=data.description,
        original_request=data.original_request,
        normalized_spec=data.normalized_spec,
        config=data.config,
        visibility=data.visibility,
        origin="web",
        tags=data.tags,
    )
    await session.commit()
    return _job_response(job)


@router.get("/jobs")
async def list_jobs(
    status: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Список задач пользователя."""
    jobs = await storage.list_jobs(session, user.telegram_id, status_filter=status, offset=offset, limit=limit)
    return [_job_response(j) for j in jobs]


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Детали задачи."""
    job = await storage.get_job(session, job_id, user.telegram_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_response(job)


@router.patch("/jobs/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    data: JobUpdate,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Обновление задачи."""
    job = await storage.get_job(session, job_id, user.telegram_id)
    if not job:
        raise HTTPException(404, "Job not found")
    updates = data.model_dump(exclude_unset=True)
    job = await storage.update_job(session, job_id, **updates)
    await session.commit()
    return _job_response(job)


@router.post("/jobs/{job_id}/run")
async def run_job_endpoint(
    job_id: str,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Запуск задачи на выполнение (фоновый)."""
    job = await storage.get_job(session, job_id, user.telegram_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status in ("running",):
        raise HTTPException(409, "Job already running")
    # Обновляем статус на pending
    await storage.update_job_status(session, job_id, "pending", actor_id=user.telegram_id, source="web")
    await session.commit()
    # Запуск в фоне
    asyncio.create_task(run_job(job_id))
    return {"status": "started", "job_id": job_id}


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Отмена задачи."""
    job = await storage.get_job(session, job_id, user.telegram_id)
    if not job:
        raise HTTPException(404, "Job not found")
    job = await storage.update_job_status(session, job_id, "canceled", actor_id=user.telegram_id, source="web")
    await session.commit()
    return {"status": "canceled", "job_id": job_id}


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Удаление задачи (архивация)."""
    job = await storage.get_job(session, job_id, user.telegram_id)
    if not job:
        raise HTTPException(404, "Job not found")
    job = await storage.update_job_status(session, job_id, "archived", actor_id=user.telegram_id, source="web")
    await session.commit()
    return {"status": "archived", "job_id": job_id}


# ── Results / Runs / Sources ──────────────────────────────────────────────────

@router.get("/jobs/{job_id}/results")
async def get_results(
    job_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Результаты задачи."""
    # Проверяем доступ
    job = await storage.get_job(session, job_id, user.telegram_id)
    if not job:
        raise HTTPException(404, "Job not found")
    results = await storage.get_results(session, job_id, offset=offset, limit=limit)
    count = await storage.get_result_count(session, job_id)
    return {"total": count, "offset": offset, "limit": limit, "items": [_result_response(r) for r in results]}


@router.get("/jobs/{job_id}/runs")
async def get_runs(
    job_id: str,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Список запусков задачи."""
    job = await storage.get_job(session, job_id, user.telegram_id)
    if not job:
        raise HTTPException(404, "Job not found")
    runs = await storage.list_runs(session, job_id)
    return [_run_response(r) for r in runs]


@router.get("/jobs/{job_id}/sources")
async def get_sources(
    job_id: str,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Список источников задачи."""
    job = await storage.get_job(session, job_id, user.telegram_id)
    if not job:
        raise HTTPException(404, "Job not found")
    sources = await storage.list_sources(session, job_id)
    return [{"id": s.id, "url": s.url, "domain": s.domain, "source_type": s.source_type, "status": s.status} for s in sources]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _job_response(job) -> dict:
    return {
        "id": job.id, "title": job.title, "description": job.description,
        "status": job.status, "job_type": job.job_type, "provider": job.provider,
        "origin": job.origin, "visibility": job.visibility, "created_by": job.created_by,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
    }

def _run_response(run) -> dict:
    return {
        "id": run.id, "job_id": run.job_id, "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "metrics": run.metrics, "error_details": run.error_details,
    }

def _result_response(r) -> dict:
    return {
        "id": r.id, "source_url": r.source_url, "domain": r.domain,
        "title": r.title, "extracted_fields": r.extracted_fields, "dedupe_hash": r.dedupe_hash,
    }
