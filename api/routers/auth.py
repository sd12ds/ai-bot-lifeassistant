"""
Роутер авторизации:
- POST /auth/exchange — обменять magic-link токен (из бота) на сессионный JWT (24ч)
- GET  /auth/me       — проверить текущего пользователя
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import create_jwt, verify_jwt, get_current_user
from db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    """Ответ с JWT токеном."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24 часа


class MeResponse(BaseModel):
    """Текущий пользователь."""
    telegram_id: int
    mode: str
    timezone: str


@router.post("/exchange", response_model=TokenResponse)
async def exchange_token(token: str):
    """Обменять magic-link токен (5 мин, purpose=magic) на сессионный JWT (24ч).
    Вызывается фронтендом при переходе по magic link из бота.
    """
    # Верифицируем одноразовый magic-токен
    telegram_id = verify_jwt(token, expected_purpose="magic")

    # Создаём долгоживущий сессионный токен (24 часа)
    session_token = create_jwt(telegram_id, expires_in=86400, purpose="session")

    return TokenResponse(access_token=session_token)


@router.get("/me", response_model=MeResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Проверить текущего пользователя (работает и с initData, и с JWT)."""
    return MeResponse(
        telegram_id=user.telegram_id,
        mode=user.mode or "personal",
        timezone=user.timezone or "Europe/Moscow",
    )
