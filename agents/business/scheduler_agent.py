"""
SchedulerAgent — агент поиска свободных временных слотов для команды.
Использует calendar tools для анализа занятости участников.
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from config import OPENAI_API_KEY, OPENAI_LLM_MODEL
from tools.calendar_tools import CALENDAR_TOOLS

_SYSTEM_PROMPT = """Ты ассистент по поиску удобного времени для встреч команды.
Отвечай на русском языке.
Используй инструменты для просмотра календаря участников.
Анализируй расписание и предлагай свободные временные слоты.
Учитывай рабочие часы (9:00-18:00 по московскому времени)."""

_llm = ChatOpenAI(
    model=OPENAI_LLM_MODEL,
    api_key=OPENAI_API_KEY,
    temperature=0,
)


def build_scheduler_agent(checkpointer=None):
    """Строит SchedulerAgent для поиска свободного времени."""
    return create_react_agent(
        model=_llm,
        tools=CALENDAR_TOOLS,
        prompt=_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
