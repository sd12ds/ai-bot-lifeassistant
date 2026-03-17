"""
Точка входа для отдельного контейнера планировщиков.

Создаёт экземпляр Bot только для отправки сообщений (без Dispatcher и polling).
Запускает все три фоновых планировщика как asyncio-задачи и держит
event loop живым до получения сигнала остановки.

Это позволяет scheduler'ам работать независимо от основного бота:
падение бота не прерывает уведомления и наоборот.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import os

# Добавляем корень проекта в PYTHONPATH для корректных импортов
sys.path.insert(0, os.path.dirname(__file__))

from aiogram import Bot

import config
from db.storage import init_db
from infrastructure.scheduler.notification_scheduler import start_notification_scheduler
from infrastructure.scheduler.nutrition_tips_scheduler import start_nutrition_tips_scheduler
from infrastructure.scheduler.coaching_scheduler import start_coaching_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    # Проверяем обязательные переменные окружения
    config.validate()

    # Инициализируем БД — scheduler'ам нужен доступ к данным пользователей
    await init_db()
    logger.info("БД инициализирована: %s", config.DATABASE_URL)

    # Создаём Bot только для отправки сообщений (polling не запускаем)
    bot = Bot(token=config.TELEGRAM_TOKEN)

    logger.info("Запускаем планировщики...")

    # Запускаем все три планировщика как фоновые asyncio-задачи
    start_notification_scheduler(bot, interval_seconds=60)
    start_nutrition_tips_scheduler(bot, check_interval=60)
    start_coaching_scheduler(bot, interval_seconds=60)

    logger.info("Все планировщики запущены. Ожидаю событий (без polling)...")

    # Держим event loop живым бесконечно — контейнер работает пока не остановят
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
