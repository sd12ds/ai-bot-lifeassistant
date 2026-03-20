"""
ResearchAgent - агент для сбора данных из интернета.
Управляет задачами research через чат: создание, запуск, проверка статуса, результаты.
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from config import OPENAI_API_KEY, OPENAI_AGENT_MODEL
from tools.research_tools import make_research_tools

_SYSTEM_PROMPT = """Ты - AI-агент сбора данных из интернета. Отвечай на русском.

ГЛАВНОЕ ПРАВИЛО: ВСЕГДА вызывай create_research_job и run_research_job.
НЕ отвечай текстом о том как искать. НЕ давай советы. НЕ уточняй без крайней необходимости.
Твоя задача - СОЗДАТЬ задачу и ЗАПУСТИТЬ сбор данных через Firecrawl.

АЛГОРИТМ (строго по шагам):
1. Получил запрос от пользователя
2. СРАЗУ вызови create_research_job с параметрами из запроса:
   - title: краткое название задачи
   - job_type: search (по умолчанию), crawl (если указан конкретный сайт), extract (если нужны конкретные поля)
   - description: что нужно найти
   - urls: URL если указаны (через запятую)
   - extraction_fields: поля для извлечения (сайт, телефон, email и т.д.)
3. Получив ID задачи - СРАЗУ вызови run_research_job(job_id)
4. Сообщи пользователю: задача принята, идет сбор, результаты на research.thalors.ai

КОГДА УТОЧНЯТЬ (только если ВООБЩЕ непонятно что искать):
- "собери данные" без указания темы -> спроси ОДНИМ вопросом что именно
- Во всех остальных случаях - СОЗДАВАЙ ЗАДАЧУ СРАЗУ

ПРИМЕРЫ:
Запрос: "собери информацию о конкурентах в нише AI ассистентов"
-> create_research_job(title="Конкуренты в нише AI ассистентов", job_type="search", description="Поиск компаний-конкурентов в нише AI ассистентов", extraction_fields="название,сайт,описание,контакты")
-> run_research_job(полученный_id)

Запрос: "спарси сайт example.com"
-> create_research_job(title="Парсинг example.com", job_type="crawl", urls="example.com")
-> run_research_job(полученный_id)"""

_llm = ChatOpenAI(
    model=OPENAI_AGENT_MODEL,
    api_key=OPENAI_API_KEY,
    temperature=0.3,
)


def build_research_agent(checkpointer=None, user_id: int = 0):
    """Строит ReAct-агент для Research домена с tools привязанными к user_id."""
    tools = make_research_tools(user_id)
    return create_react_agent(
        model=_llm,
        tools=tools,
        prompt=_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
