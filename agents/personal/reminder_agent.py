"""
ReminderAgent — агент для управления задачами и напоминаниями.
Инструменты привязываются к user_id через make_reminder_tools.
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI
from utils.prompts import load_prompt
from langgraph.prebuilt import create_react_agent

from config import OPENAI_API_KEY, OPENAI_AGENT_MODEL

_SYSTEM_PROMPT = load_prompt("reminder")

_llm = ChatOpenAI(
    model=OPENAI_AGENT_MODEL,
    api_key=OPENAI_API_KEY,
    temperature=0,
)


def build_reminder_agent(checkpointer=None, user_id: int = 0):
    """
    Строит ReminderAgent. user_id нужен для привязки tools к пользователю.
    При вызове из Supervisor user_id передаётся из состояния.
    """
    from tools.reminder_tools import make_reminder_tools
    # Создаём tools с заглушкой user_id=0 — реальный user_id
    # передаётся через thread_id в конфигурации чекпоинтера
    reminder_tools = make_reminder_tools(user_id)
    return create_react_agent(
        model=_llm,
        tools=reminder_tools,
        prompt=_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
