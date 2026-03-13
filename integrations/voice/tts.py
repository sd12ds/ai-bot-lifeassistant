"""
Text-to-Speech через OpenAI TTS API.
Конвертирует текст в OGG Opus для Telegram voice message.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from openai import AsyncOpenAI

from config import OPENAI_API_KEY, OPENAI_TTS_MODEL, OPENAI_TTS_VOICE

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def synthesize_to_ogg(text: str) -> str:
    """
    Синтезирует речь из текста и возвращает путь к временному .ogg файлу.
    Вызывающий код обязан удалить файл после использования.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        mp3_path = Path(tmpdir) / "reply.mp3"
        ogg_path = Path(tmpdir) / "reply.ogg"

        # Генерация MP3 через OpenAI TTS
        audio = await _client.audio.speech.create(
            model=OPENAI_TTS_MODEL,
            voice=OPENAI_TTS_VOICE,
            input=text[:4000],
        )
        mp3_path.write_bytes(audio.read())

        # Конвертация MP3 → OGG Opus для Telegram
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(mp3_path),
            "-c:a", "libopus", "-b:a", "24k", "-vbr", "on",
            "-compression_level", "10", str(ogg_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        if await proc.wait() != 0 or not ogg_path.exists():
            raise RuntimeError("ffmpeg: конвертация MP3→OGG не удалась")

        # Перемещаем в системный tmpdir (tmpdir будет удалён после with-блока)
        final_path = Path(tempfile.gettempdir()) / f"tg_tts_{os.getpid()}_{id(text)}.ogg"
        final_path.write_bytes(ogg_path.read_bytes())
        return str(final_path)
