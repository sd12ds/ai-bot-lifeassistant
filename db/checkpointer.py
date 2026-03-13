"""
LangGraph checkpointer — персистентная память диалогов через PostgreSQL.
Использует AsyncPostgresSaver для полной совместимости с ainvoke().
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# DSN для psycopg3 (формат: postgresql://user:pass@host:port/db)
_PG_DSN: str = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://aiuser:changeme@localhost:5432/aiassistant",
).replace("postgresql+asyncpg://", "postgresql://")

# Единственный экземпляр checkpointer
_checkpointer = None
# Ссылка на контекст-менеджер для корректного закрытия пула
_checkpointer_cm = None


async def init_checkpointer() -> None:
    """Асинхронная инициализация PostgreSQL checkpointer.
    Вызывать один раз при старте (из main.py).
    """
    global _checkpointer, _checkpointer_cm
    if _checkpointer is not None:
        return
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        # from_conn_string возвращает async context manager
        _checkpointer_cm = AsyncPostgresSaver.from_conn_string(_PG_DSN)
        # Входим в контекст — получаем реальный async checkpointer
        _checkpointer = await _checkpointer_cm.__aenter__()
        # Создаём таблицы checkpoints если их нет
        await _checkpointer.setup()
        logger.info("AsyncPostgresSaver checkpointer инициализирован: %s", _PG_DSN.split("@")[-1])
    except Exception as e:
        logger.warning("Не удалось подключить AsyncPostgresSaver: %s. Фолбэк на MemorySaver.", e)
        from langgraph.checkpoint.memory import MemorySaver
        _checkpointer = MemorySaver()


def get_checkpointer():
    """Возвращает глобальный checkpointer (должен быть инициализирован через init_checkpointer)."""
    if _checkpointer is None:
        # Фолбэк если init_checkpointer не вызван (например, в тестах)
        logger.warning("Checkpointer не инициализирован — используем MemorySaver")
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
    return _checkpointer
