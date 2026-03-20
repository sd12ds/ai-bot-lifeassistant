"""
ExecutionEngine - основной pipeline выполнения research-задачи.
Оркестрирует: create run -> collect -> extract -> process -> save -> update status.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from db.session import get_async_session
from db import research_storage as storage
from services.research.collection_engine import collect
from services.research.result_processor import process_results
from services.research.extraction_pipeline import extract_structured

logger = logging.getLogger(__name__)


async def run_job(job_id: str, notify_callback=None) -> dict:
    """
    Основной pipeline выполнения задачи.
    Возвращает dict с результатами run.
    notify_callback(user_id, message) - для отправки уведомления в Telegram.
    """
    async with get_async_session() as session:
        # 1. Загружаем задачу
        job = await storage.get_job(session, job_id)
        if not job:
            return {"error": f"Job {job_id} не найден"}

        # 2. Создаем run
        run = await storage.create_run(session, job_id)

        # 3. Обновляем статусы
        await storage.update_job_status(session, job_id, "running", source="system", run_id=run.id)
        await storage.update_run(session, run.id, status="running", started_at=datetime.now(timezone.utc))
        await session.commit()

    # 4. Выполняем сбор данных (вне транзакции - может быть долгим)
    try:
        spec = job.normalized_spec or {}
        urls = spec.get("urls", spec.get("seed_urls", []))

        collection_result = await collect(
            job_type=job.job_type,
            provider_name=job.provider,
            normalized_spec=spec,
            urls=urls,
        )

        raw_items = collection_result.get("items", [])
        metrics = collection_result.get("metrics", {})

        # 5. LLM extraction если есть схема
        extraction_schema = spec.get("extraction_schema")
        if extraction_schema and raw_items:
            for item in raw_items:
                if item.get("raw_content") and not item.get("extracted_fields"):
                    extracted = await extract_structured(item["raw_content"], extraction_schema)
                    if extracted:
                        item["extracted_fields"] = extracted

        # 6. Дедупликация и нормализация
        processed_items = process_results(raw_items)
        metrics["items_extracted"] = len(processed_items)

        # 7. Сохраняем результаты
        async with get_async_session() as session:
            await storage.save_results(session, job_id, run.id, processed_items)

            # 8. Обновляем run и job
            await storage.update_run(session, run.id,
                status="completed",
                finished_at=datetime.now(timezone.utc),
                metrics=metrics,
                provider_metadata=collection_result.get("provider_metadata"),
            )
            await storage.update_job_status(session, job_id, "completed", source="system", run_id=run.id)
            await storage.update_job(session, job_id, last_run_at=datetime.now(timezone.utc))
            await session.commit()

        logger.info("Job %s completed: %d items", job_id, len(processed_items))

        # 9. Уведомление в Telegram
        if notify_callback:
            try:
                msg = f"Сбор завершен: найдено {len(processed_items)} результатов. Детали в Research -> Jobs."
                await notify_callback(job.created_by, msg)
            except Exception as e:
                logger.warning("Notify failed: %s", e)

        return {"run_id": run.id, "status": "completed", "items_count": len(processed_items), "metrics": metrics}

    except Exception as e:
        # Обработка ошибки - сохраняем partial results если есть
        logger.error("Job %s failed: %s", job_id, e, exc_info=True)
        async with get_async_session() as session:
            await storage.update_run(session, run.id,
                status="failed",
                finished_at=datetime.now(timezone.utc),
                error_details=str(e),
            )
            await storage.update_job_status(session, job_id, "failed", source="system", run_id=run.id)
            await session.commit()

        if notify_callback:
            try:
                await notify_callback(job.created_by, f"Ошибка сбора данных: {str(e)[:200]}")
            except Exception:
                pass

        return {"run_id": run.id, "status": "failed", "error": str(e)}
