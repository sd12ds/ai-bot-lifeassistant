"""
Middleware: при каждом входящем сообщении регистрирует/находит пользователя в БД
и добавляет его данные в data для обработчиков.
"""
from __future__ import annotations

from typing import Any, Callable, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message

from db.storage import get_or_create_user


class UserContextMiddleware(BaseMiddleware):
    """
    Добавляет в data["user_db"] словарь с данными пользователя из БД.
    Гарантирует, что каждый пользователь зарегистрирован перед обработкой.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Получаем telegram_id из события
        user = data.get("event_from_user")
        if user:
            # Регистрируем/получаем пользователя из БД
            user_db = await get_or_create_user(user.id)
            data["user_db"] = user_db
        else:
            data["user_db"] = None

        return await handler(event, data)
