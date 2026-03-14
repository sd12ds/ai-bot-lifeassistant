"""
Заглушки (fakes) для тестирования без реальных внешних зависимостей.
"""
from .fake_llm import FakeLLM, FakeLLMWithError
from .fake_telegram import FakeTelegramBot
from .fake_scheduler import FakeScheduler

__all__ = [
    "FakeLLM",
    "FakeLLMWithError",
    "FakeTelegramBot",
    "FakeScheduler",
]
