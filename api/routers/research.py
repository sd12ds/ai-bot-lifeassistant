"""
FastAPI роутер для Research домена.
Phase 2: RBAC + workspace isolation (get_workspace_context, require_permission)
Phase 3: billing guard (require_active_subscription) на запуск задач
Phase 4: audit logging на все мутирующие операции + rate limiting на POST
"""
from __future__ import annotations

import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from db.session import get_session
from db import research_storage as storage
from services.research.execution_engine import run_job
from services.auth.permission_checker import get_workspace_context, require_permission
from services.auth.rbac import Permission
from services.billing.billing_guard import require_active_subscription
from services.audit import audit_logger
from api.middleware.rate_limit import rate_limit

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
    workspace_id: str | None = None
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

@router.post("/jobs", response_model=JobResponse,
             dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60))])
async def create_job(
    request: Request,
    data: JobCreate,
    ctx=Depends(require_permission(Permission.JOB_CREATE)),
    session: AsyncSession = Depends(get_session),
):
    """Создание задачи исследования (manager+). Phase 2: workspace isolation + RBAC."""
    # Input validation
    if data.title and len(data.title) > 500:
        raise HTTPException(400, "Title too long (max 500)")
    if data.description and len(data.description) > 5000:
        raise HTTPException(400, "Description too long (max 5000)")
    if data.normalized_spec and data.normalized_spec.get("urls"):
        for url in data.normalized_spec["urls"]:
            if not url.startswith(("http://", "https://")):
                raise HTTPException(400, f"Invalid URL: {url}")

    job = await storage.create_job(
        session=session,
        created_by=ctx["user_id"],
        title=data.title,
        job_type=data.job_type,
        description=data.description,
        original_request=data.original_request,
        normalized_spec=data.normalized_spec,
        config=data.config,
        visibility=data.visibility,
        origin="web",
        tags=data.tags,
        workspace_id=ctx["workspace_id"],  # Phase 2: привязка к workspace
    )
    await session.commit()

    # Phase 4: audit log создания задачи
    await audit_logger.log_event(
        session, workspace_id=ctx["workspace_id"], actor_id=ctx["user_id"],
        action="job.create", resource_type="research_job", resource_id=job.id,
        source="web", ip=request.client.host if request.client else None,
    )
    await session.commit()

    return _job_response(job)


@router.get("/jobs")
async def list_jobs(
    status: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    ctx=Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Список задач workspace (viewer+). Phase 2: фильтр по workspace_id."""
    jobs = await storage.list_jobs(
        session,
        user_id=ctx["user_id"],
        workspace_id=ctx["workspace_id"],  # Phase 2: изоляция по workspace
        status_filter=status,
        offset=offset,
        limit=limit,
    )
    return [_job_response(j) for j in jobs]


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    ctx=Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Детали задачи (viewer+)."""
    job = await _get_job_or_404(session, job_id, ctx)
    return _job_response(job)


@router.patch("/jobs/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    data: JobUpdate,
    ctx=Depends(require_permission(Permission.JOB_EDIT)),
    session: AsyncSession = Depends(get_session),
):
    """Обновление задачи (manager+)."""
    await _get_job_or_404(session, job_id, ctx)
    updates = data.model_dump(exclude_unset=True)
    job = await storage.update_job(session, job_id, **updates)
    await session.commit()
    return _job_response(job)


@router.post("/jobs/{job_id}/run",
             dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60))])
async def run_job_endpoint(
    request: Request,
    job_id: str,
    ctx=Depends(require_permission(Permission.JOB_RUN)),
    _sub=Depends(require_active_subscription),   # Phase 3: проверка подписки
    session: AsyncSession = Depends(get_session),
):
    """Запуск задачи (manager+ + активная подписка). Phase 3: billing guard."""
    job = await _get_job_or_404(session, job_id, ctx)
    if job.status in ("running",):
        raise HTTPException(409, "Job already running")

    # Обновляем статус на pending
    await storage.update_job_status(session, job_id, "pending", actor_id=ctx["user_id"], source="web")

    # Phase 4: audit log запуска
    await audit_logger.log_event(
        session, workspace_id=ctx["workspace_id"], actor_id=ctx["user_id"],
        action="job.run", resource_type="research_job", resource_id=job_id,
        source="web", ip=request.client.host if request.client else None,
    )
    await session.commit()

    # Фоновый запуск pipeline
    asyncio.create_task(run_job(job_id))
    return {"status": "started", "job_id": job_id}


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    request: Request,
    job_id: str,
    ctx=Depends(require_permission(Permission.JOB_RUN)),
    session: AsyncSession = Depends(get_session),
):
    """Отмена задачи (manager+)."""
    await _get_job_or_404(session, job_id, ctx)
    job = await storage.update_job_status(session, job_id, "canceled", actor_id=ctx["user_id"], source="web")

    # Phase 4: audit log отмены
    await audit_logger.log_event(
        session, workspace_id=ctx["workspace_id"], actor_id=ctx["user_id"],
        action="job.cancel", resource_type="research_job", resource_id=job_id,
        source="web", ip=request.client.host if request.client else None,
    )
    await session.commit()
    return {"status": "canceled", "job_id": job_id}


@router.delete("/jobs/{job_id}")
async def delete_job(
    request: Request,
    job_id: str,
    ctx=Depends(require_permission(Permission.JOB_DELETE)),
    session: AsyncSession = Depends(get_session),
):
    """Удаление задачи (admin+)."""
    await _get_job_or_404(session, job_id, ctx)
    job = await storage.update_job_status(session, job_id, "archived", actor_id=ctx["user_id"], source="web")

    # Phase 4: audit log удаления
    await audit_logger.log_event(
        session, workspace_id=ctx["workspace_id"], actor_id=ctx["user_id"],
        action="job.delete", resource_type="research_job", resource_id=job_id,
        source="web", ip=request.client.host if request.client else None,
    )
    await session.commit()
    return {"status": "archived", "job_id": job_id}


# ── Results / Runs / Sources ──────────────────────────────────────────────────

@router.get("/jobs/{job_id}/results")
async def get_results(
    job_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    ctx=Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Результаты задачи (viewer+)."""
    await _get_job_or_404(session, job_id, ctx)
    results = await storage.get_results(session, job_id, offset=offset, limit=limit)
    count = await storage.get_result_count(session, job_id)
    return {"total": count, "offset": offset, "limit": limit, "items": [_result_response(r) for r in results]}


@router.get("/jobs/{job_id}/runs")
async def get_runs(
    job_id: str,
    ctx=Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Список запусков задачи (viewer+)."""
    await _get_job_or_404(session, job_id, ctx)
    runs = await storage.list_runs(session, job_id)
    return [_run_response(r) for r in runs]


@router.get("/jobs/{job_id}/sources")
async def get_sources(
    job_id: str,
    ctx=Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Список источников задачи (viewer+)."""
    await _get_job_or_404(session, job_id, ctx)
    sources = await storage.list_sources(session, job_id)
    return [{"id": s.id, "url": s.url, "domain": s.domain, "source_type": s.source_type, "status": s.status} for s in sources]


@router.get("/results/{result_id}")
async def get_result_item(
    result_id: str,
    ctx=Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Конкретный result item по ID (viewer+)."""
    from sqlalchemy import select
    from db.models import ResearchResultItem
    stmt = select(ResearchResultItem).where(ResearchResultItem.id == result_id)
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Result not found")
    # Проверяем доступ через job
    await _get_job_or_404(session, item.job_id, ctx)
    return _result_response(item)


@router.post("/jobs/{job_id}/duplicate")
async def duplicate_job(
    job_id: str,
    ctx=Depends(require_permission(Permission.JOB_CREATE)),
    session: AsyncSession = Depends(get_session),
):
    """Дублирование задачи (manager+)."""
    job = await _get_job_or_404(session, job_id, ctx)
    new_job = await storage.create_job(
        session=session,
        created_by=ctx["user_id"],
        title=f"{job.title} (копия)",
        job_type=job.job_type,
        description=job.description,
        original_request=job.original_request,
        normalized_spec=job.normalized_spec,
        config=job.config,
        visibility=job.visibility,
        origin="web",
        tags=job.tags,
        workspace_id=ctx["workspace_id"],
    )
    await session.commit()
    return _job_response(new_job)


@router.post("/jobs/{job_id}/export")
async def export_results(
    request: Request,
    job_id: str,
    format: str = "json",
    ctx=Depends(require_permission(Permission.RESULT_EXPORT)),
    session: AsyncSession = Depends(get_session),
):
    """Экспорт результатов (analyst+). Phase 4: audit log."""
    await _get_job_or_404(session, job_id, ctx)
    results = await storage.get_results(session, job_id, limit=10000)

    # Phase 4: audit log экспорта
    await audit_logger.log_event(
        session, workspace_id=ctx["workspace_id"], actor_id=ctx["user_id"],
        action="result.export", resource_type="research_job", resource_id=job_id,
        source="web", ip=request.client.host if request.client else None,
        metadata={"format": format, "count": len(results)},
    )
    await session.commit()

    if format == "csv":
        import csv, io
        output = io.StringIO()
        if results:
            fields = ["source_url", "domain", "title", "dedupe_hash"]
            if results[0].extracted_fields:
                fields.extend(results[0].extracted_fields.keys())
            writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for r in results:
                row = {"source_url": r.source_url, "domain": r.domain, "title": r.title, "dedupe_hash": r.dedupe_hash}
                if r.extracted_fields:
                    row.update(r.extracted_fields)
                writer.writerow(row)
        from fastapi.responses import Response
        return Response(content=output.getvalue(), media_type="text/csv",
                       headers={"Content-Disposition": f"attachment; filename=research_{job_id[:8]}.csv"})
    else:
        return {"job_id": job_id, "total": len(results), "items": [_result_response(r) for r in results]}


# ── Templates CRUD ────────────────────────────────────────────────────────────

@router.get("/templates")
async def list_templates_endpoint(
    ctx=Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Список шаблонов workspace (viewer+)."""
    templates = await storage.list_templates(session, ctx["user_id"], workspace_id=ctx["workspace_id"])
    return [{"id": t.id, "name": t.name, "description": t.description, "is_public": t.is_public,
             "spec_template": t.spec_template, "created_at": t.created_at.isoformat() if t.created_at else None} for t in templates]


class TemplateCreate(BaseModel):
    name: str
    description: str | None = None
    spec_template: dict | None = None
    is_public: bool = False

@router.post("/templates")
async def create_template_endpoint(
    data: TemplateCreate,
    ctx=Depends(require_permission(Permission.TEMPLATE_MANAGE)),
    session: AsyncSession = Depends(get_session),
):
    """Создание шаблона (manager+)."""
    t = await storage.create_template(session, created_by=ctx["user_id"], name=data.name,
                                       description=data.description, spec_template=data.spec_template,
                                       is_public=data.is_public, workspace_id=ctx["workspace_id"])
    await session.commit()
    return {"id": t.id, "name": t.name}


@router.delete("/templates/{template_id}")
async def delete_template_endpoint(
    template_id: str,
    ctx=Depends(require_permission(Permission.TEMPLATE_MANAGE)),
    session: AsyncSession = Depends(get_session),
):
    """Удаление шаблона (manager+)."""
    ok = await storage.delete_template(session, template_id)
    if not ok:
        raise HTTPException(404, "Template not found")
    await session.commit()
    return {"status": "deleted"}


@router.post("/templates/{template_id}/use")
async def use_template(
    template_id: str,
    ctx=Depends(require_permission(Permission.JOB_CREATE)),
    session: AsyncSession = Depends(get_session),
):
    """Создать job из шаблона (manager+)."""
    t = await storage.get_template(session, template_id)
    if not t:
        raise HTTPException(404, "Template not found")
    job = await storage.create_job(
        session, created_by=ctx["user_id"], title=f"Из шаблона: {t.name}",
        job_type=t.spec_template.get("job_type", "search") if t.spec_template else "search",
        description=t.description, normalized_spec=t.spec_template, origin="web",
        workspace_id=ctx["workspace_id"],
    )
    await session.commit()
    return _job_response(job)


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_research_stats(
    ctx=Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Статистика задач workspace для dashboard. Phase 2: по workspace_id."""
    from sqlalchemy import select, func
    from db.models import ResearchJob, ResearchResultItem
    ws_id = ctx["workspace_id"]

    # Считаем задачи по статусам в рамках workspace
    stmt = (
        select(ResearchJob.status, func.count())
        .where(ResearchJob.workspace_id == ws_id)
        .group_by(ResearchJob.status)
    )
    result = await session.execute(stmt)
    status_counts = dict(result.fetchall())

    # Общее количество результатов в workspace
    total_results_stmt = (
        select(func.count()).select_from(ResearchResultItem)
        .join(ResearchJob, ResearchResultItem.job_id == ResearchJob.id)
        .where(ResearchJob.workspace_id == ws_id)
    )
    total_results = (await session.execute(total_results_stmt)).scalar_one()
    return {
        "workspace_id": ws_id,
        "total_jobs": sum(status_counts.values()),
        "running": status_counts.get("running", 0),
        "completed": status_counts.get("completed", 0),
        "failed": status_counts.get("failed", 0),
        "draft": status_counts.get("draft", 0),
        "canceled": status_counts.get("canceled", 0),
        "total_results": total_results,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_job_or_404(session, job_id: str, ctx: dict):
    """Получает job с проверкой принадлежности workspace. 404 если не найден."""
    from sqlalchemy import select
    from db.models import ResearchJob
    stmt = select(ResearchJob).where(
        ResearchJob.id == job_id,
        ResearchJob.workspace_id == ctx["workspace_id"],
    )
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    return job


def _job_response(job) -> dict:
    return {
        "id": job.id, "title": job.title, "description": job.description,
        "status": job.status, "job_type": job.job_type, "provider": job.provider,
        "origin": job.origin, "visibility": job.visibility, "created_by": job.created_by,
        "workspace_id": job.workspace_id,
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
