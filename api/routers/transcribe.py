"""
Транскрибирование рилсов через OpenAI Whisper.
Берёт videoUrl из raw_data поста, скачивает mp4, отправляет в Whisper.
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from db.session import get_session
from db.models import SocialPost, SocialSource
from config import OPENAI_API_KEY

router = APIRouter(prefix="/social/posts", tags=["transcribe"])
logger = logging.getLogger(__name__)


async def _download_video(url: str) -> bytes:
    """Скачивает видео по URL без Referer (обход Instagram CDN)."""
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        resp = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"
        })
        if resp.status_code != 200:
            raise ValueError(f"Не удалось скачать видео: HTTP {resp.status_code}")
        return resp.content


async def _whisper_transcribe(video_bytes: bytes, filename: str = "reel.mp4") -> str:
    """Отправляет видео в OpenAI Whisper и возвращает транскрипт."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    # Записываем во временный файл (Whisper API требует file-like object)
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            response = await client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="ru",          # авто-определение если убрать
                response_format="text",
            )
        return response if isinstance(response, str) else response.text
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.post("/{post_id}/transcribe")
async def transcribe_post(
    post_id: str,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Транскрибирует рил/видео через OpenAI Whisper.
    Берёт videoUrl из raw_data, скачивает mp4, возвращает текст.
    """
    # Проверяем доступ через источник
    stmt = (
        select(SocialPost, SocialSource)
        .join(SocialSource, SocialPost.source_id == SocialSource.id)
        .where(SocialPost.id == post_id)
        .where(SocialSource.created_by == user.telegram_id)
    )
    result = await session.execute(stmt)
    row = result.first()
    if not row:
        raise HTTPException(404, "Пост не найден")

    post, source = row

    # Если транскрипт уже есть — возвращаем сразу
    if post.transcript:
        return {"transcript": post.transcript, "cached": True}

    # Ищем videoUrl в raw_data
    raw = post.raw_data or {}
    video_url = raw.get("videoUrl") or raw.get("video_url")

    if not video_url or not isinstance(video_url, str) or len(video_url) < 20:
        raise HTTPException(422, "Видео URL не найден. Этот пост не содержит видео или был собран без него.")

    logger.info("Transcribe: post=%s url=%s...", post_id[:8], video_url[:60])

    try:
        # Скачиваем видео
        video_bytes = await _download_video(video_url)
        size_mb = len(video_bytes) / 1_048_576
        logger.info("Видео скачано: %.1f MB", size_mb)

        if size_mb > 24:
            raise HTTPException(413, f"Видео слишком большое ({size_mb:.1f} MB). Whisper принимает до 25 MB.")

        # Транскрибируем
        transcript = await _whisper_transcribe(video_bytes)

        # Сохраняем в БД
        await session.execute(
            update(SocialPost)
            .where(SocialPost.id == post_id)
            .values(transcript=transcript)
        )
        await session.commit()
        logger.info("Transcript saved: post=%s len=%d", post_id[:8], len(transcript))

        return {"transcript": transcript, "cached": False}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Transcribe failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Ошибка транскрибирования: {str(e)[:200]}")
