"""
Точка входа мультиагентного Telegram-бота.
Инициализирует БД, собирает Supervisor граф, запускает polling.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import os
import hashlib
import glob

# Добавляем корень проекта в PYTHONPATH для корректных импортов
sys.path.insert(0, os.path.dirname(__file__))

from aiogram import Bot, Dispatcher
from aiogram.types import MenuButtonWebApp, MenuButtonDefault, WebAppInfo

import config
from db.storage import init_db
from bot.middleware.user_context import UserContextMiddleware
from bot.handlers import common, text, voice, photo
from db.checkpointer import init_checkpointer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def _setup_menu_button(bot: Bot) -> None:
    """
    Устанавливает кнопку меню бота.
    Если задан MINIAPP_URL — показывает кнопку «Открыть Jarvis» для запуска WebApp.
    Иначе — стандартная кнопка меню.
    """
    miniapp_url = os.getenv("MINIAPP_URL", "").strip()
    if miniapp_url:
        # Cache-busting: добавляем ?v=<hash> на основе текущего билда
        # Telegram WebView агрессивно кеширует — без этого старая версия застревает
        build_hash = ""
        try:
            js_files = glob.glob("/var/www/jarvis/assets/index-*.js")
            if js_files:
                build_hash = hashlib.md5(os.path.basename(js_files[0]).encode()).hexdigest()[:8]
        except Exception:
            build_hash = hashlib.md5(str(os.getpid()).encode()).hexdigest()[:8]
        versioned_url = f"{miniapp_url}?v={build_hash}" if build_hash else miniapp_url
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🤖 Открыть Jarvis",
                web_app=WebAppInfo(url=versioned_url),
            )
        )
        logger.info("Menu button → WebApp: %s", versioned_url)
    else:
        # Возвращаем стандартную кнопку если URL не задан
        await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
        logger.info("MINIAPP_URL не задан — кнопка меню стандартная")


async def main() -> None:
    # Проверяем обязательные переменные окружения
    config.validate()

    # Инициализируем БД (создаём таблицы при первом запуске)
    await init_db()
    logger.info("БД инициализирована: %s", config.DATABASE_URL)

    # Инициализируем PostgreSQL checkpointer (async) для LangGraph
    await init_checkpointer()

    # Инициализируем Supervisor (создаёт агентов и checkpointer)
    from agents.supervisor import get_supervisor
    get_supervisor()
    logger.info("Supervisor готов")

    # Создаём бота и диспетчер
    bot = Bot(token=config.TELEGRAM_TOKEN)
    dp = Dispatcher()

    # Устанавливаем кнопку меню (WebApp если задан MINIAPP_URL)
    await _setup_menu_button(bot)

    # Регистрируем middleware
    dp.message.middleware(UserContextMiddleware())

    # Регистрируем роутеры. Порядок важен:
    # 1) Общие команды (/start, /help)
    # 2) Меню задач (ReplyKeyboard) — должно идти до текстового обработчика
    # 3) Голосовые/текстовые обработчики
    from bot.handlers import task_menu, settings, task_actions, coaching_handler
    dp.include_router(common.router)
    dp.include_router(task_menu.router)
    dp.include_router(settings.router)  # ⚙️ Настройки — до текстового хендлера
    dp.include_router(task_actions.router)  # callback «✅ Выполнено»
    dp.include_router(photo.router)  # 📸 Фото еды — до voice и text
    dp.include_router(voice.router)
    dp.include_router(coaching_handler.router)  # 🤖 Coaching — до text.router
    dp.include_router(text.router)

    logger.info("Бот запущен (scheduler'ы вынесены в отдельный сервис)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
