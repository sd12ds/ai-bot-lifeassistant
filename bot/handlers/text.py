"""
Обработчик текстовых сообщений.
Передаёт текст в Supervisor и возвращает ответ пользователю.
При активном draft или sticky domain — принудительно направляет в соответствующего агента.
"""
from __future__ import annotations

import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message

from agents.supervisor import process_message
from bot.core.session_context import get_context

router = Router()
logger = logging.getLogger(__name__)

# Максимальное время ожидания ответа от LLM (секунды)
LLM_TIMEOUT_SECONDS = 30


@router.message(F.text)
async def text_handler(message: Message, user_db: dict | None = None, bot: Bot = None):
    """Обрабатывает текстовые сообщения через Supervisor."""
    await bot.send_chat_action(message.chat.id, "typing")

    # Получаем режим пользователя из БД (или personal по умолчанию)
    user_mode = user_db.get("mode", "personal") if user_db else "personal"
    user_id = message.from_user.id

    logger.info("TEXT user=%s mode=%s: %s", user_id, user_mode, message.text)

    # Проверяем контекст сессии — только активный draft принудительно
    # фиксирует агента. Sticky domain НЕ используется здесь намеренно:
    # он обрабатывается в supervisor.classify_intent на уровне 2 (после
    # rule-based классификатора). Это позволяет пользователю явно сменить
    # раздел (напр.: "запиши в задачи...") даже когда активен sticky nutrition.
    force_agent = None
    ctx = get_context(user_id)
    if ctx and ctx.draft:
        # Активный черновик — принудительно в домен (подтверждение/уточнение)
        force_agent = ctx.active_domain or "nutrition"
        logger.info("TEXT user=%s: активный draft → force_agent=%s", user_id, force_agent)

    try:
        # Оборачиваем вызов LLM в таймаут — если OpenAI не отвечает > LLM_TIMEOUT_SECONDS,
        # возвращаем пользователю вежливый fallback вместо зависания
        response = await asyncio.wait_for(
            process_message(
                user_id=user_id,
                user_mode=user_mode,
                text=message.text,
                force_agent=force_agent,
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
