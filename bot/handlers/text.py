"""
Обработчик текстовых сообщений.
Передаёт текст в Supervisor и возвращает ответ пользователю.
Routing (в т.ч. черновики) — полностью на стороне supervisor.py (L0a/L0b guards + Layer 1).
"""
from __future__ import annotations

import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message

from agents.supervisor import process_message
router = Router()
logger = logging.getLogger(__name__)

# Максимальное время ожидания ответа от LLM (секунды)
LLM_TIMEOUT_SECONDS = 120


@router.message(F.text)
async def text_handler(message: Message, user_db: dict | None = None, bot: Bot = None):
    """Обрабатывает текстовые сообщения через Supervisor."""
    await bot.send_chat_action(message.chat.id, "typing")

    # Получаем режим пользователя из БД (или personal по умолчанию)
    user_mode = user_db.get("mode", "personal") if user_db else "personal"
    user_id = message.from_user.id

    logger.info("TEXT user=%s mode=%s: %s", user_id, user_mode, message.text)

    try:
        # Оборачиваем вызов LLM в таймаут — если OpenAI не отвечает > LLM_TIMEOUT_SECONDS,
        # возвращаем пользователю вежливый fallback вместо зависания
        response = await asyncio.wait_for(
            process_message(
                user_id=user_id,
                user_mode=user_mode,
                text=message.text,
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("LLM timeout user=%s после %ds", user_id, LLM_TIMEOUT_SECONDS)
        response = (
            "⏳ Запрос занял слишком много времени. "
            "Попробуй ещё раз — сейчас нагрузка повышена."
        )
    except Exception as e:
        logger.error("Ошибка обработки сообщения: %s", e, exc_info=True)
        response = "Произошла ошибка при обработке запроса. Попробуй ещё раз."

    await message.answer(response)
