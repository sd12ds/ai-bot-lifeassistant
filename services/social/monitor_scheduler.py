"""
MonitorScheduler — цикл мониторинга соцсетей.
Каждые 5 минут проверяет какие источники пора парсить и запускает их фоново.
Подключается к scheduler-сервису при старте.
"""
from __future__ import annotations

import asyncio
import logging

from db.session import get_async_session
from db import social_storage as storage
from services.social.parse_engine import run_source

logger = logging.getLogger(__name__)

_running = False


async def start_monitor_loop(notify_callback=None):
    """Запускает бесконечный цикл мониторинга источников."""
    global _running
    _running = True
    logger.info("Social Monitor Scheduler запущен (интервал проверки: 5 мин)")
    while _running:
        try:
            await _check_and_run_due_sources(notify_callback)
        except Exception as e:
            logger.error("Monitor loop error: %s", e, exc_info=True)
        # Проверка каждые 5 минут
        await asyncio.sleep(300)


async def _check_and_run_due_sources(notify_callback=None):
    """Проверяет какие источники пора запустить и запускает их фоново."""
    async with get_async_session() as session:
        due_sources = await storage.list_due_sources(session)

    if not due_sources:
        return

    logger.info("Social Monitor: %d источников к запуску", len(due_sources))
    for source in due_sources:
        # Запуск в фоне — не блокирует основной цикл
        asyncio.create_task(
            run_source(source.id, notify_callback=notify_callback),
            name=f"social_parse_{source.id[:8]}",
        )
        # Небольшая пауза между запусками чтобы не перегружать API
        await asyncio.sleep(1)


def stop_monitor_loop():
    """Останавливает цикл мониторинга."""
    global _running
    _running = False
    logger.info("Social Monitor Scheduler остановлен")
