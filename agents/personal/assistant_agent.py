"""
AssistantAgent — общий персональный ассистент без специализированных инструментов.
Ведёт диалог с памятью через SqliteSaver (thread_id = user_id).
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from config import OPENAI_API_KEY, OPENAI_AGENT_MODEL

_SYSTEM_PROMPT = """Ты персональный AI-ассистент. 
Отвечай на русском языке.

КОНТЕКСТ ДИАЛОГА (КРИТИЧНО):
- ВСЕГДА помни о чём шёл разговор. Не теряй нить диалога.
- Если пользователь пишет "подробнее", "ещё", "а что?", "расскажи больше" — он продолжает ТЕКУЩУЮ тему.
- НЕ спрашивай уточнения, если из контекста уже понятно о чём речь.
- Уточняй только если запрос ДЕЙСТВИТЕЛЬНО неоднозначен.
Помогай с вопросами, анализом, планированием, написанием текстов.
Помни контекст предыдущих сообщений в этом диалоге."""

_llm = ChatOpenAI(
    model=OPENAI_AGENT_MODEL,
    api_key=OPENAI_API_KEY,
    temperature=0.7,  # Более творческий режим для общения
)


def build_assistant_agent(checkpointer=None):
    """
    Строит и возвращает граф AssistantAgent.
    Без tools — только GPT с памятью диалога.
    """
    return create_react_agent(
        model=_llm,
        tools=[],  # Нет инструментов — только диалог
        prompt=_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
