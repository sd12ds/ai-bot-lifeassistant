"""
CalendarAgent — агент для работы с Google Calendar.
Построен на LangGraph create_react_agent с набором calendar_tools.
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from config import OPENAI_API_KEY, OPENAI_LLM_MODEL
from tools.calendar_tools import CALENDAR_TOOLS

# Системный промпт агента
_SYSTEM_PROMPT = """Ты ассистент по управлению Google Calendar. 
Отвечай на русском языке, коротко и по делу.
Используй доступные инструменты для работы с событиями: создание, удаление, перенос, поиск.
Если не хватает информации (например, не указано время) — уточни у пользователя.
Текущий часовой пояс: Europe/Moscow."""

# LLM модель для агента
_llm = ChatOpenAI(
    model=OPENAI_LLM_MODEL,
    api_key=OPENAI_API_KEY,
    temperature=0,
)


def build_calendar_agent(checkpointer=None):
    """
    Строит и возвращает граф CalendarAgent.
    checkpointer передаётся из Supervisor для персистентной памяти.
    """
    return create_react_agent(
        model=_llm,
        tools=CALENDAR_TOOLS,
        prompt=_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
