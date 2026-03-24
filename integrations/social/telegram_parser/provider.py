"""
TelegramProvider — парсинг каналов и групп Telegram через Telethon (MTProto API).
Работает от имени отдельного аккаунта-парсера, сессия хранится в файле.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from integrations.social.base import SocialProvider, SourceInfo, ParsedPost
from config import (
    TELEGRAM_PARSER_API_ID, TELEGRAM_PARSER_API_HASH,
    TELEGRAM_PARSER_PHONE, TELEGRAM_PARSER_SESSION,
)

logger = logging.getLogger(__name__)


class TelegramProvider(SocialProvider):
    """Парсинг Telegram через Telethon MTProto API."""

    def __init__(self):
        self._client = None  # Telethon TelegramClient (lazy init)

    def _is_configured(self) -> bool:
        return bool(TELEGRAM_PARSER_API_ID and TELEGRAM_PARSER_API_HASH)

    async def _get_client(self):
        """Получает или создаёт Telethon клиент."""
        if self._client and self._client.is_connected():
            return self._client
        from telethon import TelegramClient
        self._client = TelegramClient(
            TELEGRAM_PARSER_SESSION,
            TELEGRAM_PARSER_API_ID,
            TELEGRAM_PARSER_API_HASH,
        )
        await self._client.start(phone=TELEGRAM_PARSER_PHONE or None)
        logger.info("TelegramClient подключён")
        return self._client

    async def resolve_url(self, url: str) -> SourceInfo:
        """Определяет источник по t.me/username или @username."""
        # Извлекаем username из ссылки
        username = url.rstrip("/").split("/")[-1].lstrip("@")
        if "t.me/" in url:
            username = url.split("t.me/")[-1].rstrip("/").split("/")[0]
        return await self.get_source_info(username)

    async def get_source_info(self, source_id: str, source_type: str = "channel") -> SourceInfo:
        """Получает информацию о канале/группе через Telethon."""
        if not self._is_configured():
            raise RuntimeError("Telegram Parser не настроен (TELEGRAM_PARSER_API_ID/HASH)")
        client = await self._get_client()
        try:
            from telethon.tl.types import Channel, Chat
            entity = await client.get_entity(source_id)
            title = getattr(entity, "title", source_id)
            username = getattr(entity, "username", source_id) or source_id
            # Количество подписчиков
            participants_count = 0
            try:
                full = await client.get_participants(entity, limit=0)
                participants_count = full.total
            except Exception:
                participants_count = getattr(entity, "participants_count", 0)
            is_channel = hasattr(entity, "broadcast") and entity.broadcast
            src_type = "channel" if is_channel else "group"
            return SourceInfo(
                source_id=username,
                source_name=title,
                platform="telegram",
                source_type=src_type,
                subscribers_count=participants_count,
                description=getattr(entity, "about", ""),
                is_verified=getattr(entity, "verified", False),
                extra={
                    "is_megagroup": getattr(entity, "megagroup", False),
                    "is_restricted": getattr(entity, "restricted", False),
                },
            )
        except Exception as e:
            logger.error("get_source_info failed: %s", e)
            raise

    async def get_posts(
        self,
        source_id: str,
        results_type: str = "posts",
        since: Any = None,
        limit: int = 50,
        extra_config: dict | None = None,
    ) -> list[ParsedPost]:
        """Получает сообщения из Telegram канала/группы."""
        if not self._is_configured():
            raise RuntimeError("Telegram Parser не настроен")
        client = await self._get_client()

        posts = []
        try:
            kwargs: dict = {"limit": limit}
            if since:
                kwargs["offset_date"] = since
                kwargs["reverse"] = False

            async for message in client.iter_messages(source_id, **kwargs):
                # Пропускаем сервисные сообщения
                if message.action:
                    continue
                # Инкрементальный фильтр по дате
                if since and message.date and message.date.replace(tzinfo=timezone.utc) <= since:
                    break

                post = self._map_message(message, source_id)
                posts.append(post)

                # FloodWait — пауза при необходимости
                await asyncio.sleep(0.05)

        except Exception as e:
            # Обрабатываем FloodWaitError отдельно
            if "FloodWait" in type(e).__name__:
                wait_secs = getattr(e, "seconds", 60)
                logger.warning("Telegram FloodWait: ждём %d сек", wait_secs)
                await asyncio.sleep(wait_secs)
            else:
                logger.error("get_posts failed: %s", e)
                raise

        logger.info("Telegram %s: собрано %d постов", source_id, len(posts))
        return posts

    def _map_message(self, message, source_id: str) -> ParsedPost:
        """Маппинг Telethon Message → ParsedPost."""
        from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
        # Медиа
        media_urls = []
        post_type = "text"
        if message.media:
            if isinstance(message.media, MessageMediaPhoto):
                post_type = "image"
                # URL не доступен напрямую — сохраняем флаг для скачивания
                media_urls.append(f"tg_photo:{message.id}")
            elif isinstance(message.media, MessageMediaDocument):
                doc = message.media.document
                mime = getattr(doc, "mime_type", "")
                if mime.startswith("video"):
                    post_type = "video"
                    media_urls.append(f"tg_video:{message.id}")
                else:
                    media_urls.append(f"tg_doc:{message.id}")
        # Реакции
        reactions = {}
        if message.reactions and message.reactions.results:
            for r in message.reactions.results:
                emoji = getattr(r.reaction, "emoticon", "?")
                reactions[emoji] = r.count
        # Автор
        author_name = source_id
        author_id = ""
        if message.sender_id:
            author_id = str(message.sender_id)
        # Дедупликация
        dedupe_key = f"tg:{source_id}:{message.id}"
        dedupe_hash = hashlib.sha256(dedupe_key.encode()).hexdigest()[:16]
        return ParsedPost(
            platform_post_id=str(message.id),
            content=message.text or "",
            post_url=f"https://t.me/{source_id}/{message.id}",
            post_type=post_type,
            posted_at=message.date,
            author_name=author_name,
            author_id=author_id,
            metrics={
                "views":    getattr(message, "views", 0) or 0,
                "forwards": getattr(message, "forwards", 0) or 0,
                "replies":  getattr(message.replies, "replies", 0) if message.replies else 0,
                "reactions": reactions,
            },
            media_urls=media_urls,
            is_pinned=bool(getattr(message, "pinned", False)),
            raw_data={
                "id": message.id,
                "grouped_id": str(message.grouped_id) if message.grouped_id else None,
            },
        )

    def get_platform_name(self) -> str:
        return "telegram"
