"""
TeamAgent — агент для управления командой.
Использует calendar tools для создания совместных событий.
Доступен только в бизнес-режиме.
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from config import OPENAI_API_KEY, OPENAI_AGENT_MODEL
from tools.calendar_tools import CALENDAR_TOOLS

_SYSTEM_PROMPT = """Ты бизнес-ассистент для управления командой.
Отвечай на русском языке, профессионально.

КОНТЕКСТ ДИАЛОГА (КРИТИЧНО):
- ВСЕГДА помни о чём шёл разговор. Не теряй нить диалога.
- Если пользователь пишет "подробнее", "ещё", "а что?", "расскажи больше" — он продолжает ТЕКУЩУЮ тему.
- НЕ спрашивай уточнения, если из контекста уже понятно о чём речь.
- Уточняй только если запрос ДЕЙСТВИТЕЛЬНО неоднозначен.
Помогай планировать встречи команды, создавать совместные события в календаре,
управлять расписанием сотрудников.
При создании командных встреч уточняй список участников и добавляй их в описание события."""

_llm = ChatOpenAI(
    model=OPENAI_AGENT_MODEL,
    api_key=OPENAI_API_KEY,
    temperature=0,
)


def build_team_agent(checkpointer=None):
    """Строит TeamAgent с calendar tools для командного планирования."""
    return create_react_agent(
        model=_llm,
        tools=CALENDAR_TOOLS,
        prompt=_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
