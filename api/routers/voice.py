"""
REST API роутер для голосового ввода (/api/voice).
Транскрибирует аудио через OpenAI STT, парсит фитнес-интент через LLM.
"""
from __future__ import annotations

import json
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from api.deps import get_current_user
from db.models import User
from config import OPENAI_API_KEY, OPENAI_STT_MODEL, OPENAI_LLM_MODEL

router = APIRouter(prefix="/voice", tags=["voice"])

# Максимальный размер аудиофайла — 10 МБ
MAX_AUDIO_SIZE = 10 * 1024 * 1024
# Допустимые MIME-типы аудио
ALLOWED_AUDIO_TYPES = {"audio/webm", "audio/ogg", "audio/wav", "audio/mp4", "audio/mpeg", "audio/mp3"}


class TranscribeResponse(BaseModel):
    """Ответ транскрипции с распознанным интентом."""
    text: str  # Распознанный текст
    intent: str  # Интент: add_set | add_exercise | rest_timer | finish | unknown
    params: dict  # Параметры интента


# Промпт для парсинга фитнес-интентов из текста
INTENT_PARSE_PROMPT = """Ты — парсер голосовых команд для фитнес-приложения.
Из текста пользователя определи интент и параметры.

ИНТЕНТЫ:
1. add_set — записать подход. Параметры: weight_kg (число), reps (число)
   Примеры: "записать подход 80 кг 10 повторов", "подход 60 на 12", "80 кг 8 раз"
2. add_exercise — добавить упражнение. Параметры: exercise_name (строка)
   Примеры: "добавить жим лёжа", "добавь приседания", "подтягивания"
3. rest_timer — запустить таймер отдыха. Параметры: seconds (число)
   Примеры: "отдых 90 секунд", "отдых 2 минуты", "перерыв"
4. finish — завершить тренировку. Параметры: нет
   Примеры: "завершить", "конец тренировки", "закончить"
5. unknown — не удалось распознать

ОТВЕТЬ СТРОГО В JSON (без markdown):
{"intent": "...", "params": {...}}

Текст пользователя: """


async def _transcribe_audio(audio_data: bytes, filename: str) -> str:
    """Транскрибирует аудио через OpenAI STT API."""
    from openai import AsyncOpenAI

    # Определяем расширение файла для OpenAI
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "webm"
    
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    # Сохраняем во временный файл (OpenAI API требует файловый объект)
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name

    try:
        # Вызов STT API
        with open(tmp_path, "rb") as audio_file:
            transcript = await client.audio.transcriptions.create(
                model=OPENAI_STT_MODEL,
                file=audio_file,
                language="ru",
            )
        return transcript.text.strip()
    finally:
        import os
        os.unlink(tmp_path)


async def _parse_intent(text: str) -> dict:
    """Парсит фитнес-интент из распознанного текста через LLM."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    response = await client.chat.completions.create(
        model=OPENAI_LLM_MODEL,
        messages=[
            {"role": "system", "content": "Ты — парсер команд. Отвечай только JSON."},
            {"role": "user", "content": INTENT_PARSE_PROMPT + text},
        ],
        temperature=0.1,
        max_tokens=200,
    )

    content = response.choices[0].message.content.strip()
    # Убираем возможные markdown-обёртки
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        content = content.rsplit("```", 1)[0]

    try:
        parsed = json.loads(content)
        return {
            "intent": parsed.get("intent", "unknown"),
            "params": parsed.get("params", {}),
        }
    except json.JSONDecodeError:
        return {"intent": "unknown", "params": {}}


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_voice(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """
    Транскрибирует голосовую команду и парсит фитнес-интент.
    Принимает аудиофайл (webm/ogg/wav/mp4), возвращает текст + интент + параметры.
    """
    # Валидация типа файла
    content_type = file.content_type or ""
    if content_type and content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=400, detail=f"Формат {content_type} не поддерживается")

    # Читаем аудио
    audio_data = await file.read()
    if len(audio_data) > MAX_AUDIO_SIZE:
        raise HTTPException(status_code=400, detail="Файл слишком большой (макс. 10 МБ)")
    if len(audio_data) < 100:
        raise HTTPException(status_code=400, detail="Файл слишком маленький")

    # Транскрибируем
    text = await _transcribe_audio(audio_data, file.filename or "audio.webm")
    if not text:
        return TranscribeResponse(text="", intent="unknown", params={})

    # Парсим интент
    result = await _parse_intent(text)

    return TranscribeResponse(
        text=text,
        intent=result["intent"],
        params=result["params"],
    )
