"""
CoachingScheduler — фоновый планировщик proactive-коучинга.

Запускается как asyncio-Task при старте бота (аналог notification_scheduler).

Цикл каждые N секунд:
  1. Получает список всех пользователей с активным coaching-профилем
  2. Для каждого запускает run_proactive_for_user() из coaching_proactive
  3. Graceful error handling — один сбой не останавливает всех остальных

Интервал проверки: 60 секунд (настраивается).
Реальная частота отправки ограничена antispam через check_antispam().
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from sqlalchemy import select

from db.session import AsyncSessionLocal
from db.models import UserCoachingProfile
from services.coaching_proactive import run_proactive_for_user

logger = logging.getLogger(__name__)


async def _get_active_user_ids() -> list[int]:
    """
    Возвращает список user_id всех пользователей, у которых есть
    CoachingProfile (т.е. они хотя бы раз взаимодействовали с коучем).
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserCoachingProfile.user_id)
        )
        return [row[0] for row in result.fetchall()]


async def _run_proactive_cycle(bot: Bot) -> None:
    """
    Один цикл проверки: для каждого активного пользователя
    запускает proactive pipeline.
    """
    try:
        user_ids = await _get_active_user_ids()
    except Exception as exc:
        logger.error("Coaching scheduler: ошибка получения пользователей: %s", exc)
        return

    if not user_ids:
        return

    logger.debug("Coaching scheduler: проверяем %d пользователей", len(user_ids))
    sent_count = 0

    for user_id in user_ids:
        try:
            async with AsyncSessionLocal() as session:
                sent = await run_proactive_for_user(session, bot, user_id)
                if sent:
                    sent_count += 1
        except Exception as exc:
            # Один сбой не должен останавливать цикл для остальных
            logger.error(
                "Coaching scheduler: ошибка для user=%s: %s",
                user_id, exc, exc_info=False,
            )

    if sent_count > 0:
        logger.info("Coaching scheduler: отправлено %d proactive сообщений", sent_count)


async def _coaching_scheduler_loop(bot: Bot, interval_seconds: int) -> None:
    """Основной asyncio-цикл планировщика."""
    logger.info("Coaching scheduler запущен, интервал=%ds", interval_seconds)

    # Смещение относительно notification_scheduler (запускаем через 30с)
    await asyncio.sleep(30)

    tick = 0
    while True:
        try:
            await _run_proactive_cycle(bot)
        except Exception as exc:
            logger.error("Coaching scheduler: критическая ошибка цикла: %s", exc, exc_info=True)
        tick += 1
        await asyncio.sleep(interval_seconds)


def start_coaching_scheduler(bot: Bot, interval_seconds: int = 60) -> asyncio.Task:
    """
    Запускает фоновый планировщик coaching proactive как asyncio.Task.

    Возвращает Task — живёт до завершения event loop.
    Вызывать после запуска dp.start_polling().
    """
    loop = asyncio.get_event_loop()
    task = loop.create_task(
        _coaching_scheduler_loop(bot, interval_seconds),
        name="coaching_proactive_scheduler",
    )
    logger.info("Coaching proactive scheduler зарегистрирован")
    return task
