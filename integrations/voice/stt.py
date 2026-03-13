"""
Speech-to-Text через OpenAI Whisper API.
"""
from __future__ import annotations

from openai import AsyncOpenAI

from config import OPENAI_API_KEY, OPENAI_STT_MODEL

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def transcribe_audio(path: str) -> str:
    """Транскрибирует аудиофайл, возвращает текст."""
    with open(path, "rb") as audio_file:
        transcript = await _client.audio.transcriptions.create(
            model=OPENAI_STT_MODEL,
            file=audio_file,
        )
    return getattr(transcript, "text", "").strip()
