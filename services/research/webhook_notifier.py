"""
Webhook Notifier - отправка уведомлений при завершении job.
Phase 5: callback URL, exports API.
"""
from __future__ import annotations
import logging
import httpx

logger = logging.getLogger(__name__)


async def notify_webhook(webhook_url: str, job_id: str, status: str, results_count: int):
    """Отправляет POST webhook при завершении job."""
    if not webhook_url:
        return
    payload = {
        "event": "job.completed" if status == "completed" else "job.failed",
        "job_id": job_id,
        "status": status,
        "results_count": results_count,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            logger.info("Webhook sent to %s: %d", webhook_url, resp.status_code)
    except Exception as e:
        logger.warning("Webhook failed for %s: %s", webhook_url, e)
