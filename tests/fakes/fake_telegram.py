"""
Заглушка Telegram Bot для тестирования без реального API.
"""
from __future__ import annotations

from typing import Any


class FakeTelegramBot:
    """
    Имитирует aiogram Bot для тестов.
    Записывает все отправленные сообщения — проверяем в ассертах.
    """

    def __init__(self) -> None:
        # Список всех отправленных сообщений
        self.sent_messages: list[dict] = []
        # Список вызовов answer_callback_query
        self.answered_callbacks: list[dict] = []

    async def send_message(
        self,
        chat_id: int,
        text: str,
        **kwargs: Any,
    ) -> dict:
        """Записывает исходящее сообщение."""
        msg = {"chat_id": chat_id, "text": text, **kwargs}
        self.sent_messages.append(msg)
        return {"message_id": len(self.sent_messages)}

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str = "",
        **kwargs: Any,
    ) -> bool:
        """Записывает ответ на callback-запрос."""
        self.answered_callbacks.append({
            "callback_query_id": callback_query_id,
            "text": text,
        })
        return True

    async def edit_message_text(
        self,
        text: str,
        chat_id: int,
        message_id: int,
        **kwargs: Any,
    ) -> dict:
        """Записывает редактирование сообщения."""
        msg = {
            "action": "edit",
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            **kwargs,
        }
        self.sent_messages.append(msg)
        return {}

    def reset(self) -> None:
        """Очищает записанные сообщения."""
        self.sent_messages = []
        self.answered_callbacks = []

    def last_message_text(self) -> str | None:
        """Возвращает текст последнего сообщения."""
        if self.sent_messages:
            return self.sent_messages[-1].get("text")
        return None

    def messages_to(self, chat_id: int) -> list[dict]:
        """Возвращает все сообщения для заданного чата."""
        return [m for m in self.sent_messages if m.get("chat_id") == chat_id]
