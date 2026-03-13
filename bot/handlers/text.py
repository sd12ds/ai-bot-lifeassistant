"""
Обработчик текстовых сообщений.
Передаёт текст в Supervisor и возвращает ответ пользователю.
При активном draft — принудительно направляет в nutrition-агента.
"""
from __future__ import annotations

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message

from agents.supervisor import process_message
from bot.nutrition_context import get_context

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text)
async def text_handler(message: Message, user_db: dict | None = None, bot: Bot = None):
    """Обрабатывает текстовые сообщения через Supervisor."""
    await bot.send_chat_action(message.chat.id, "typing")

    # Получаем режим пользователя из БД (или personal по умолчанию)
    user_mode = user_db.get("mode", "personal") if user_db else "personal"
    user_id = message.from_user.id

    logger.info("TEXT user=%s mode=%s: %s", user_id, user_mode, message.text)

    # Проверяем активный draft — если есть, принудительно направляем в nutrition
    force_agent = None
    ctx = get_context(user_id)
    if ctx and ctx.draft:
        force_agent = "nutrition"
        logger.info("TEXT user=%s: активный draft → force_agent=nutrition", user_id)

    try:
        response = await process_message(
            user_id=user_id,
            user_mode=user_mode,
            text=message.text,
            force_agent=force_agent,
        )
    except Exception as e:
        logger.error("Ошибка обработки сообщения: %s", e, exc_info=True)
        response = "Произошла ошибка при обработке запроса. Попробуй ещё раз."

    await message.answer(response)
