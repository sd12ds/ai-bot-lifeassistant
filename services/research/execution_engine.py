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
from services.research.enrichment import enrich_results

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
    processed_items = []
    try:
        spec = job.normalized_spec or {}
        urls = spec.get("urls", spec.get("seed_urls", []))

        # 4a. Cost estimation — оценка расхода перед запуском
        from integrations.firecrawl.provider import FirecrawlProvider
        from integrations.firecrawl.mapper import map_job_to_firecrawl_config
        est_config = map_job_to_firecrawl_config(job.job_type, spec)
        provider_inst = FirecrawlProvider()
        usage_est = provider_inst.estimate_usage(est_config)
        async with get_async_session() as session:
            await storage.update_job(session, job_id, usage_estimate={"pages": usage_est.estimated_pages, "tokens": usage_est.estimated_tokens, "cost": usage_est.estimated_cost_units})
            await session.commit()

        # 4b. Сбор данных
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

        # 5a. Enrichment pipeline
        enrichment_config = spec.get("enrichment")
        if enrichment_config:
            raw_items = await enrich_results(raw_items, enrichment_config)

        # 6. Дедупликация и нормализация
        processed_items = process_results(raw_items)
        metrics["items_extracted"] = len(processed_items)

        # 7. Сохраняем результаты
        async with get_async_session() as session:
            await storage.save_results(session, job_id, run.id, processed_items)

            # 7a. Auto-summarize результатов через LLM
            summary_text = None
            if processed_items:
                try:
                    titles = [p.get("title", p.get("source_url", ""))[:80] for p in processed_items[:20]]
                    from services.research.extraction_pipeline import _llm
                    summary_resp = await _llm.ainvoke(
                        f"Кратко резюмируй результаты сбора данных (1-2 предложения на русском).\nНайдено {len(processed_items)} результатов:\n" + "\n".join(f"- {t}" for t in titles)
                    )
                    summary_text = summary_resp.content.strip()
                except Exception as se:
                    logger.warning("Auto-summarize failed: %s", se)

            # 8. Обновляем run и job
            run_update = dict(status="completed", finished_at=datetime.now(timezone.utc), metrics=metrics, provider_metadata=collection_result.get("provider_metadata"))
            if summary_text:
                run_update["metrics"] = {**(metrics or {}), "summary": summary_text}
            await storage.update_run(session, run.id, **run_update)
            await storage.update_job_status(session, job_id, "completed", source="system", run_id=run.id)
            await storage.update_job(session, job_id, last_run_at=datetime.now(timezone.utc))

            # 8a. Usage recording — записываем фактическое потребление
            try:
                from services.billing.usage_tracker import record_usage
                pages = metrics.get("pages_crawled", metrics.get("search_results", len(processed_items)))
                await record_usage(session, workspace_id=job.workspace_id or "", user_id=job.created_by,
                                   metric_type="crawl_pages", amount=float(pages), source_type="job", source_id=job_id, provider=job.provider)
                await record_usage(session, workspace_id=job.workspace_id or "", user_id=job.created_by,
                                   metric_type="job_runs", amount=1.0, source_type="job", source_id=job_id)
            except Exception as ue:
                logger.warning("Usage recording failed: %s", ue)

            await session.commit()

        logger.info("Job %s completed: %d items", job_id, len(processed_items))

        # 9. Уведомление в Telegram
        if notify_callback:
            try:
                msg = f"Сбор завершен: найдено {len(processed_items)} результатов."
                if summary_text:
                    msg += f"\n{summary_text}"
                msg += "\nДетали на research.thalors.ai"
                await notify_callback(job.created_by, msg)
            except Exception as e:
                logger.warning("Notify failed: %s", e)

        # 9a. Webhook notification
        try:
            from services.research.webhook_notifier import notify_webhook
            webhook_url = (spec.get("webhook_url") or "")
            if webhook_url:
                await notify_webhook(webhook_url, job_id, "completed", len(processed_items))
        except Exception:
            pass

        return {"run_id": run.id, "status": "completed", "items_count": len(processed_items), "metrics": metrics, "summary": summary_text}

    except Exception as e:
        # Partial failure — записываем что успели собрать + usage за фактически использованное
        logger.error("Job %s failed: %s", job_id, e, exc_info=True)
        async with get_async_session() as session:
            # Сохраняем partial results если есть
            if processed_items:
                try:
                    await storage.save_results(session, job_id, run.id, processed_items)
                    logger.info("Job %s: saved %d partial results", job_id, len(processed_items))
                except Exception:
                    pass

            await storage.update_run(session, run.id,
                status="failed",
                finished_at=datetime.now(timezone.utc),
                error_details=str(e),
                metrics={"partial_items": len(processed_items)},
            )
            await storage.update_job_status(session, job_id, "failed", source="system", run_id=run.id)

            # Partial usage recording
            if processed_items:
                try:
                    from services.billing.usage_tracker import record_usage
                    await record_usage(session, workspace_id=job.workspace_id or "", user_id=job.created_by,
                                       metric_type="crawl_pages", amount=float(len(processed_items)), source_type="job", source_id=job_id)
                except Exception:
                    pass

            await session.commit()

        if notify_callback:
            try:
                await notify_callback(job.created_by, f"Ошибка сбора: {str(e)[:200]}")
            except Exception:
                pass

        return {"run_id": run.id, "status": "failed", "error": str(e), "partial_items": len(processed_items)}
