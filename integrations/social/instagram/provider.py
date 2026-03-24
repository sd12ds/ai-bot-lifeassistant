"""
InstagramProvider — парсинг Instagram через Apify Actor apify/instagram-scraper.
SDK синхронный → все вызовы через asyncio.to_thread().
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any

from integrations.social.base import SocialProvider, SourceInfo, ParsedPost
from config import APIFY_API_KEY

logger = logging.getLogger(__name__)

# Маппинг results_type → параметры Apify Actor
_RESULTS_TYPE_MAP = {
    "posts":       {"resultsType": "posts"},
    "reels":       {"resultsType": "reels"},
    "comments":    {"resultsType": "comments"},
    "mentions":    {"resultsType": "taggedPosts"},
    "taggedPosts": {"resultsType": "taggedPosts"},
    "search":      {"resultsType": "details", "searchType": "hashtags"},
    "location":    {"resultsType": "posts"},
    "hashtag":     {"resultsType": "posts"},
}


def _detect_source_type(url: str) -> str:
    """Автоматически определяет тип источника по URL Instagram."""
    if "/explore/tags/" in url:
        return "hashtag"
    if "/explore/locations/" in url:
        return "location"
    if "/p/" in url or "/reel/" in url:
        return "post"
    return "profile"


class InstagramProvider(SocialProvider):
    """Провайдер Instagram через Apify Actor apify/instagram-scraper."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or APIFY_API_KEY
        if not self._api_key:
            logger.warning("APIFY_API_KEY не задан — Instagram парсинг недоступен")

    def _get_client(self):
        """Получает Apify клиент (lazy init)."""
        from apify_client import ApifyClient
        return ApifyClient(self._api_key)

    def _run_actor(self, run_input: dict) -> list[dict]:
        """Синхронный запуск актора (оборачивается в asyncio.to_thread)."""
        client = self._get_client()
        run = client.actor("apify/instagram-scraper").call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        logger.info("Apify run завершён: %d items", len(items))
        return items

    async def resolve_url(self, url: str) -> SourceInfo:
        """Определяет тип источника и получает базовую информацию."""
        source_type = _detect_source_type(url)
        # Извлекаем source_id из URL
        source_id = url.rstrip("/").split("/")[-1].lstrip("@")
        if "/explore/tags/" in url:
            source_id = url.split("/explore/tags/")[-1].rstrip("/")
        elif "/explore/locations/" in url:
            source_id = url.split("/explore/locations/")[-1].split("/")[0]

        try:
            info = await self.get_source_info(source_id, source_type)
            return info
        except Exception as e:
            logger.warning("resolve_url fallback: %s", e)
            return SourceInfo(
                source_id=source_id, source_name=source_id,
                platform="instagram", source_type=source_type,
            )

    async def get_source_info(self, source_id: str, source_type: str = "profile") -> SourceInfo:
        """Получает информацию о профиле/хэштеге через Apify."""
        if not self._api_key:
            raise RuntimeError("APIFY_API_KEY не задан")

        run_input = {
            "directUrls": [f"https://www.instagram.com/{source_id}/"],
            "resultsType": "details",
            "resultsLimit": 1,
        }
        items = await asyncio.to_thread(self._run_actor, run_input)
        if not items:
            return SourceInfo(source_id=source_id, source_name=source_id,
                              platform="instagram", source_type=source_type)
        item = items[0]
        return SourceInfo(
            source_id=item.get("username", source_id),
            source_name=item.get("fullName", "") or item.get("username", source_id),
            platform="instagram",
            source_type=source_type,
            subscribers_count=item.get("followersCount", 0),
            description=item.get("biography", ""),
            photo_url=item.get("profilePicUrl", ""),
            is_verified=item.get("verified", False),
            extra={
                "follows_count": item.get("followsCount", 0),
                "posts_count": item.get("postsCount", 0),
                "is_business": item.get("isBusinessAccount", False),
                "business_category": item.get("businessCategoryName", ""),
                "external_url": item.get("externalUrl", ""),
                "is_private": item.get("private", False),
                "has_channel": item.get("hasChannel", False),
                "joined_recently": item.get("joinedRecently", False),
                "related_profiles": item.get("relatedProfiles", []),
            },
        )

    async def get_posts(
        self,
        source_id: str,
        results_type: str = "posts",
        since: Any = None,
        limit: int = 50,
        extra_config: dict | None = None,
    ) -> list[ParsedPost]:
        """Получает посты через Apify с поддержкой инкрементального сбора."""
        if not self._api_key:
            raise RuntimeError("APIFY_API_KEY не задан")

        apify_params = _RESULTS_TYPE_MAP.get(results_type, {"resultsType": "posts"})

        # Определяем URL источника по типу
        if results_type == "hashtag":
            url = f"https://www.instagram.com/explore/tags/{source_id}/"
        elif results_type == "location":
            url = f"https://www.instagram.com/explore/locations/{source_id}/"
        else:
            url = f"https://www.instagram.com/{source_id}/"

        run_input = {
            "directUrls": [url],
            "resultsLimit": limit,
            **apify_params,
        }

        # Инкрементальный сбор — только посты новее since
        if since:
            run_input["newerThan"] = since.strftime("%Y-%m-%dT%H:%M:%S.000Z") if hasattr(since, "strftime") else str(since)

        if extra_config:
            run_input.update(extra_config)

        logger.info("Instagram %s → Apify run: url=%s limit=%d since=%s", results_type, url, limit, since)
        items = await asyncio.to_thread(self._run_actor, run_input)
        return [self._map_item(item, results_type, source_id) for item in items]

    def _map_item(self, item: dict, results_type: str, source_id: str) -> ParsedPost:
        """Маппинг Apify item → ParsedPost."""
        shortcode = item.get("shortCode", item.get("id", ""))
        post_url = item.get("url", f"https://www.instagram.com/p/{shortcode}/")

        # Дата публикации
        posted_at = None
        ts = item.get("timestamp")
        if ts:
            try:
                posted_at = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            except Exception:
                pass

        # Тип поста
        type_map = {"Image": "image", "Video": "video", "Sidecar": "carousel", "GraphSidecar": "carousel"}
        post_type = type_map.get(item.get("type", ""), "image")
        if results_type == "reels":
            post_type = "reel"

        # Медиа
        media_urls = []
        if item.get("displayUrl"):
            media_urls.append(item["displayUrl"])
        for edge in item.get("images", []):
            if isinstance(edge, str):
                media_urls.append(edge)
        for node in item.get("videoUrl", []):
            if isinstance(node, str):
                media_urls.append(node)

        # Хэштеги и упоминания из caption
        caption = item.get("caption", "") or ""
        hashtags = re.findall(r"#(\w+)", caption)
        mentions = re.findall(r"@(\w+)", caption)

        # Дедупликация и ограничение до 5
        seen = set()
        media_urls = [u for u in media_urls if u not in seen and not seen.add(u)][:5]

        return ParsedPost(
            platform_post_id=shortcode or item.get("id", ""),
            content=caption,
            post_url=post_url,
            post_type=post_type,
            posted_at=posted_at,
            author_name=item.get("ownerUsername", source_id),
            author_id=item.get("ownerId", ""),
            metrics={
                "likes":    item.get("likesCount", 0),
                "comments": item.get("commentsCount", 0),
                "views":    item.get("videoViewCount", 0),
                "plays":    item.get("videoPlayCount", 0),
            },
            media_urls=media_urls,
            hashtags=hashtags,
            mentions=mentions,
            location={
                "name": item.get("locationName", ""),
                "id":   item.get("locationId", ""),
            } if item.get("locationName") else {},
            raw_data=item,
        )

    def get_platform_name(self) -> str:
        return "instagram"
