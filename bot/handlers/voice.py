"""
Обработчик голосовых сообщений.
STT → текст → Supervisor → текстовый ответ сразу + TTS голос фоном.
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import FSInputFile, Message

from agents.supervisor import process_message
from integrations.voice.stt import transcribe_audio
from integrations.voice.tts import synthesize_to_ogg
import config

router = Router()
logger = logging.getLogger(__name__)


def _should_reply_with_voice() -> bool:
    """Голосовые ответы на голосовые сообщения по умолчанию."""
    return config.VOICE_REPLY_MODE != "never"


async def _keep_typing(bot: Bot, chat_id: int, stop_event: asyncio.Event) -> None:
    """
    Фоновая задача: обновляет индикатор 'печатает' каждые 4 секунды
    пока не установлен stop_event.
    """
    try:
        while not stop_event.is_set():
            await bot.send_chat_action(chat_id, "typing")
            await asyncio.sleep(4)
    except Exception:
        pass  # Не критично если не удалось отправить


@router.message(F.voice)
async def voice_handler(message: Message, user_db: dict | None = None, bot: Bot = None):
    """Обрабатывает голосовые сообщения: STT → агент → текст сразу + TTS фоном."""
    stop_typing = asyncio.Event()
    # Запускаем фоновый тикер "печатает"
    typing_task = asyncio.create_task(_keep_typing(bot, message.chat.id, stop_typing))

    try:
        # ── 1. Скачиваем и транскрибируем голос ──────────────────────────────
        with tempfile.TemporaryDirectory() as tmpdir:
            ogg_path = Path(tmpdir) / "input.ogg"
            file = await bot.get_file(message.voice.file_id)
            await bot.download_file(file.file_path, destination=ogg_path)
            user_text = await transcribe_audio(str(ogg_path))

        logger.info("VOICE STT user=%s: %s", message.from_user.id, user_text)

        if not user_text:
            await message.answer("Не смог распознать голосовое сообщение.")
            return

        # ── 2. Обрабатываем через Supervisor ─────────────────────────────────
        user_mode = user_db.get("mode", "personal") if user_db else "personal"
        user_id = message.from_user.id

        try:
            response = await process_message(
                user_id=user_id,
                user_mode=user_mode,
                text=user_text,
            )
        except Exception as e:
            logger.error("Ошибка обработки голосового: %s", e, exc_info=True)
            response = "Произошла ошибка при обработке запроса."

        # ── 3. Сразу отправляем текстовый ответ ──────────────────────────────
        stop_typing.set()  # Останавливаем "печатает"
        await message.answer(response)

        # ── 4. Голосовой ответ отключён — отвечаем только текстом ────────────
        # if _should_reply_with_voice():
        #     ... TTS отключён

    finally:
        stop_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass
