"""
Обработчик голосовых сообщений.

Логика роутинга:
  1. Транскрибируем голос через STT
  2. Если текст похож на чекин (is_checkin_message) → запускаем voice checkin flow:
       detect_slot + detect_date + parse_checkin_fields → карточка + confirm_kb → FSM
  3. Иначе → передаём в Supervisor (обычная обработка)
"""
from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from agents.supervisor import process_message
from integrations.voice.stt import transcribe_audio
from bot.keyboards.voice_checkin_kb import voice_checkin_confirm_kb
from bot.states import VoiceCheckinFlow
from services.voice_checkin_parser import (
    is_checkin_message,
    detect_slot,
    detect_date,
    parse_checkin_fields,
    format_checkin_card,
)
import config

router = Router()
logger = logging.getLogger(__name__)


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
async def voice_handler(message: Message, user_db: dict | None = None, bot: Bot = None, state: FSMContext = None):
    """
    Обрабатывает голосовые сообщения.

    Если текст после STT похож на чекин — запускает voice checkin flow.
    Иначе — передаёт в Supervisor как обычно.
    """
    stop_typing = asyncio.Event()
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

        user_id = message.from_user.id
        user_mode = user_db.get("mode", "personal") if user_db else "personal"

        # ── 2. Проверяем: это чекин или обычное сообщение? ───────────────────
        checkin = await is_checkin_message(user_text)

        if checkin:
            # ── 3а. Голосовой чекин flow ─────────────────────────────────────
            logger.info("VOICE CHECKIN user=%s: routing to checkin flow", user_id)

            # Определяем слот по часу (МСК = UTC+3)
            now_msk = datetime.now(timezone.utc)
            current_hour = (now_msk.hour + 3) % 24

            slot = detect_slot(user_text, current_hour)
            check_date = detect_date(user_text)
            fields = await parse_checkin_fields(user_text, slot)

            # Формируем карточку подтверждения
            card_text = format_checkin_card(
                slot=slot,
                check_date=check_date,
                fields=fields,
                transcribed_text=user_text,
            )

            stop_typing.set()
            check_date_str = check_date.isoformat()

            # Сохраняем данные в FSM state для последующей обработки
            if state:
                await state.set_state(VoiceCheckinFlow.waiting_confirmation)
                await state.update_data(
                    slot=slot,
                    check_date=check_date_str,
                    fields=json.dumps(fields, ensure_ascii=False),
                    original_text=user_text,
                )

            await message.answer(
                card_text,
                parse_mode="Markdown",
                reply_markup=voice_checkin_confirm_kb(slot, check_date_str),
            )

        else:
            # ── 3б. Обычное сообщение → Supervisor ───────────────────────────
            try:
                response = await process_message(
                    user_id=user_id,
                    user_mode=user_mode,
                    text=user_text,
                )
            except Exception as e:
                logger.error("Ошибка обработки голосового: %s", e, exc_info=True)
                response = "Произошла ошибка при обработке запроса."

            stop_typing.set()
            await message.answer(response)

    finally:
        stop_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass
