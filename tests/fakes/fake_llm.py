"""
Заглушка для LLM (вместо реального OpenAI/LangChain).
Позволяет тестировать агентов без API-ключей.
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Iterator, List, Optional
from unittest.mock import AsyncMock, MagicMock


class FakeLLMResponse:
    """Имитирует ответ LLM."""

    def __init__(self, content: str = "Тестовый ответ коуча") -> None:
        self.content = content
        self.additional_kwargs: dict = {}


class FakeLLM:
    """
    Заглушка LLM для тестирования.
    Возвращает предсказуемые ответы без сетевых запросов.
    """

    def __init__(self, response: str = "Тестовый ответ коуча") -> None:
        # Ответ по умолчанию
        self.default_response = response
        # Очередь кастомных ответов (pop FIFO)
        self._responses: list[str] = []
        # Счётчик вызовов для проверки в тестах
        self.call_count: int = 0
        self.last_messages: list = []

    def set_next_response(self, response: str) -> None:
        """Устанавливает следующий ответ в очередь."""
        self._responses.append(response)

    def set_responses(self, responses: list[str]) -> None:
        """Устанавливает список ответов по порядку."""
        self._responses = list(responses)

    async def ainvoke(self, messages: Any, **kwargs) -> FakeLLMResponse:
        """Асинхронный вызов LLM — возвращает следующий ответ из очереди."""
        self.call_count += 1
        self.last_messages = messages if isinstance(messages, list) else [messages]
        content = self._responses.pop(0) if self._responses else self.default_response
        return FakeLLMResponse(content=content)

    def invoke(self, messages: Any, **kwargs) -> FakeLLMResponse:
        """Синхронный вызов LLM."""
        self.call_count += 1
        self.last_messages = messages if isinstance(messages, list) else [messages]
        content = self._responses.pop(0) if self._responses else self.default_response
        return FakeLLMResponse(content=content)

    def reset(self) -> None:
        """Сбрасывает счётчики и очередь ответов."""
        self.call_count = 0
        self.last_messages = []
        self._responses = []


class FakeLLMWithError(FakeLLM):
    """Заглушка LLM, которая выбрасывает ошибку — для тестирования resilience."""

    def __init__(self, error: Exception | None = None) -> None:
        super().__init__()
        # Исключение для генерации при вызове
        self.error = error or RuntimeError("LLM недоступен (тест resilience)")
        self.fail_count: int = 0       # сколько раз упасть перед успехом
        self.fail_remaining: int = 0

    def set_failures(self, count: int) -> None:
        """Настраивает N неудачных попыток перед успешным ответом."""
        self.fail_remaining = count

    async def ainvoke(self, messages: Any, **kwargs) -> FakeLLMResponse:
        """Падает заданное число раз, затем возвращает ответ."""
        if self.fail_remaining > 0:
            self.fail_remaining -= 1
            raise self.error
        return await super().ainvoke(messages, **kwargs)
