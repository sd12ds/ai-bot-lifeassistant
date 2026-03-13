"""
FastAPI dependencies:
- get_current_user: верификация через Telegram initData ИЛИ JWT Bearer token
- get_db: async SQLAlchemy session

Два режима авторизации:
1. Telegram WebApp — заголовок X-Init-Data (HMAC-SHA256)
2. Браузер — заголовок Authorization: Bearer <jwt> (для magic link из бота)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Optional
from urllib.parse import parse_qsl, unquote

import jwt as pyjwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User
from dotenv import load_dotenv
from db.session import get_session

# Загружаем .env до чтения переменных окружения
load_dotenv()

# Telegram Bot Token — используется и для initData, и для JWT подписи
BOT_TOKEN: str = os.environ.get("TELEGRAM_TOKEN", "")

# Секрет для JWT — SHA256 от BOT_TOKEN (чтобы не хранить отдельный ключ)
JWT_SECRET: str = hashlib.sha256(BOT_TOKEN.encode()).hexdigest()
JWT_ALGORITHM: str = "HS256"


def create_jwt(telegram_id: int, expires_in: int = 86400, purpose: str = "session") -> str:
    """Создать JWT токен для пользователя.
    telegram_id — Telegram user ID
    expires_in — время жизни в секундах (по умолчанию 24 часа)
    purpose — тип токена: 'magic' (одноразовая ссылка, 5 мин) или 'session' (сессия, 24ч)
    """
    payload = {
        "sub": str(telegram_id),
        "purpose": purpose,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_in,
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt(token: str, expected_purpose: str = "session") -> int:
    """Верифицировать JWT, вернуть telegram_id или выбросить HTTPException."""
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Проверяем назначение токена
    if payload.get("purpose") != expected_purpose:
        raise HTTPException(status_code=401, detail="Wrong token purpose")

    telegram_id = payload.get("sub")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="No user id in token")

    return int(telegram_id)


def _verify_init_data(init_data: str, bot_token: str) -> dict:
    """
    Верифицирует Telegram WebApp initData по HMAC-SHA256.
    Возвращает словарь с данными пользователя или выбрасывает HTTPException.
    """
    # Парсим строку initData
    parsed = dict(parse_qsl(unquote(init_data), keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing hash")

    # Проверяем свежесть данных (не старше 1 часа)
    auth_date = int(parsed.get("auth_date", 0))
    if time.time() - auth_date > 3600:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="initData expired")

    # Строка для верификации: отсортированные пары key=value через \n
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )

    # Ключ = HMAC-SHA256("WebAppData", bot_token)
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    # Извлекаем user из поля "user"
    user_json = parsed.get("user", "{}")
    try:
        user_data = json.loads(user_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user data")

    return user_data


async def get_current_user(
    x_init_data: Optional[str] = Header(None, alias="X-Init-Data"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_session),
) -> User:
    """
    Dual-auth dependency:
    1. X-Init-Data (Telegram WebApp) — приоритет
    2. Authorization: Bearer <jwt> — fallback для браузерного доступа
    """
    telegram_id: int | None = None

    # Способ 1: Telegram initData
    if x_init_data:
        user_data = _verify_init_data(x_init_data, BOT_TOKEN)
        telegram_id = user_data.get("id")

    # Способ 2: JWT Bearer token
    if telegram_id is None and authorization:
        # Извлекаем токен из "Bearer <token>"
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            telegram_id = verify_jwt(parts[1], expected_purpose="session")

    if telegram_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid auth: provide X-Init-Data or Authorization Bearer token",
        )

    # Получаем или создаём пользователя в БД
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=telegram_id,
            mode="personal",
            timezone="Europe/Moscow",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user
