"""
FastAPI dependencies:
- get_current_user: верификация Telegram initData (HMAC-SHA256)
- get_db: async SQLAlchemy session
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qsl, unquote

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User
from dotenv import load_dotenv
from db.session import get_session

# Загружаем .env до чтения переменных окружения (uvicorn не вызывает load_dotenv сам)
load_dotenv()

# Telegram Bot Token — нужен для верификации initData
BOT_TOKEN: str = os.environ.get("TELEGRAM_TOKEN", "")


def _verify_init_data(init_data: str, bot_token: str) -> dict:
    """
    Верифицирует Telegram WebApp initData по HMAC-SHA256.
    Возвращает словарь с данными пользователя или выбрасывает HTTPException.
    Документация: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
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
    x_init_data: str = Header(..., alias="X-Init-Data"),
    db: AsyncSession = Depends(get_session),
) -> User:
    """
    Dependency: проверяет Telegram initData из заголовка X-Init-Data,
    возвращает объект User из БД (создаёт если не существует).
    """
    user_data = _verify_init_data(x_init_data, BOT_TOKEN)
    telegram_id = user_data.get("id")
    if not telegram_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No user id in initData")

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
