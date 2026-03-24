from __future__ import annotations
import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message
from agents.supervisor import process_message, stream_message
router = Router()
logger = logging.getLogger(__name__)
LLM_TIMEOUT_SECONDS = 120
_MIN_EDIT_INTERVAL = 0.8
_MIN_NEW_CHARS = 20

@router.message(F.text)
async def text_handler(message: Message, user_db: dict | None = None, bot: Bot = None):
    await bot.send_chat_action(message.chat.id, "typing")
    user_mode = user_db.get("mode", "personal") if user_db else "personal"
    user_id = message.from_user.id
    logger.info("TEXT user=%s mode=%s: %s", user_id, user_mode, message.text)
    sent = await message.answer("⌛")
    accumulated = ""
    last_edit_time = 0.0
    last_edit_len = 0
    has_tokens = False
    deadline = asyncio.get_event_loop().time() + LLM_TIMEOUT_SECONDS
    try:
        async for chunk in stream_message(user_id=user_id, user_mode=user_mode, text=message.text):
            if asyncio.get_event_loop().time() > deadline:
                break
            accumulated += chunk
            has_tokens = True
            now = asyncio.get_event_loop().time()
            new_chars = len(accumulated) - last_edit_len
            if now - last_edit_time >= _MIN_EDIT_INTERVAL and new_chars >= _MIN_NEW_CHARS:
                try:
                    await bot.edit_message_text(chat_id=message.chat.id, message_id=sent.message_id, text=accumulated + " ▌")
                    last_edit_time = now
                    last_edit_len = len(accumulated)
                except Exception:
                    pass
        if has_tokens and accumulated:
            try:
                await bot.edit_message_text(chat_id=message.chat.id, message_id=sent.message_id, text=accumulated)
            except Exception:
                pass
        else:
            try:
                response = await asyncio.wait_for(process_message(user_id=user_id, user_mode=user_mode, text=message.text), timeout=LLM_TIMEOUT_SECONDS)
                await bot.edit_message_text(chat_id=message.chat.id, message_id=sent.message_id, text=response)
            except asyncio.TimeoutError:
                await bot.edit_message_text(chat_id=message.chat.id, message_id=sent.message_id, text="⏳ Запрос занял слишком много времени. Попробуй ещё раз.")
    except Exception as e:
        logger.error("Ошибка user=%s: %s", user_id, e, exc_info=True)
        try:
            await bot.edit_message_text(chat_id=message.chat.id, message_id=sent.message_id, text="Произошла ошибка. Попробуй ещё раз.")
        except Exception:
            pass
