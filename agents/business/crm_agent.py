"""
CrmAgent — агент для работы с CRM (контакты, клиенты, сделки).
Доступен только в бизнес-режиме.
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from config import OPENAI_API_KEY, OPENAI_LLM_MODEL

_SYSTEM_PROMPT = """Ты бизнес-ассистент для управления клиентской базой (CRM).
Отвечай на русском языке, профессионально и по делу.

КОНТЕКСТ ДИАЛОГА (КРИТИЧНО):
- ВСЕГДА помни о чём шёл разговор. Не теряй нить диалога.
- Если пользователь пишет "подробнее", "ещё", "а что?", "расскажи больше" — он продолжает ТЕКУЩУЮ тему.
- НЕ спрашивай уточнения, если из контекста уже понятно о чём речь.
- Уточняй только если запрос ДЕЙСТВИТЕЛЬНО неоднозначен.
Помогай управлять контактами, клиентами и сделками.
Статусы сделок: new (новая), in_progress (в работе), won (выиграна), lost (проиграна)."""

_llm = ChatOpenAI(
    model=OPENAI_LLM_MODEL,
    api_key=OPENAI_API_KEY,
    temperature=0,
)


def build_crm_agent(checkpointer=None, user_id: int = 0):
    """Строит CrmAgent с CRM tools, привязанными к user_id."""
    from tools.crm_tools import make_crm_tools
    crm_tools = make_crm_tools(user_id)
    return create_react_agent(
        model=_llm,
        tools=crm_tools,
        prompt=_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
