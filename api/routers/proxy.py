"""
Image Proxy — проксирует внешние картинки (Instagram CDN и др.) через наш сервер.
Нужен потому что Instagram CDN блокирует запросы из браузера с Referer заголовком.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

router = APIRouter(prefix="/proxy", tags=["proxy"])

# Разрешённые домены — только нужные CDN
_ALLOWED_DOMAINS = {
    "scontent-ord5-3.cdninstagram.com",
    "scontent-ams4-1.cdninstagram.com",
    "scontent-fra3-1.cdninstagram.com",
    "scontent-lax3-1.cdninstagram.com",
    "scontent-msp1-1.cdninstagram.com",
    "cdninstagram.com",
    "instagram.com",
    "fbcdn.net",
}


def _is_allowed(url: str) -> bool:
    """Проверяет что URL принадлежит разрешённому CDN."""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower()
        return any(host.endswith(d) for d in _ALLOWED_DOMAINS)
    except Exception:
        return False


@router.get("/image")
async def proxy_image(url: str = Query(..., description="URL картинки для проксирования")):
    """Проксирует картинку с внешнего CDN без Referer заголовка."""
    if not _is_allowed(url):
        raise HTTPException(400, "URL не разрешён для проксирования")

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            # Запрос без Referer — CDN отдаёт картинку
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            })
            if resp.status_code != 200:
                raise HTTPException(502, f"CDN вернул {resp.status_code}")
            content_type = resp.headers.get("content-type", "image/jpeg")
            return Response(
                content=resp.content,
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=3600"},  # кэш 1 час
            )
    except httpx.TimeoutException:
        raise HTTPException(504, "Timeout при загрузке картинки")
    except Exception as e:
        raise HTTPException(502, str(e))
