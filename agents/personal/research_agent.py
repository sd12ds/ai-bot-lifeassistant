"""
ResearchAgent - агент для сбора данных из интернета.
Управляет задачами research через чат: создание, запуск, проверка статуса, результаты.
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from config import OPENAI_API_KEY, OPENAI_AGENT_MODEL
from tools.research_tools import make_research_tools
from utils.prompts import load_prompt


# Модель агента — общая для всего проекта
_llm = ChatOpenAI(
    model=OPENAI_AGENT_MODEL,
    api_key=OPENAI_API_KEY,
    temperature=0.3,
)


def build_research_agent(checkpointer=None, user_id: int = 0):
    """Строит ReAct-агент для Research домена с tools привязанными к user_id."""
    tools = make_research_tools(user_id)
    # Промпт загружается из prompts/research_agent.txt
    return create_react_agent(
        model=_llm,
        tools=tools,
        prompt=load_prompt("research_agent"),
        checkpointer=checkpointer,
    )
