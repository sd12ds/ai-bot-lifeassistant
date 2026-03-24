"""
FitnessAgent — агент для трекинга тренировок, замеров тела и активности.
Инструменты привязываются к user_id через make_fitness_tools.
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI
from utils.prompts import load_prompt
from langgraph.prebuilt import create_react_agent

from config import OPENAI_API_KEY, OPENAI_AGENT_MODEL

# Системный промпт для фитнес-агента
_SYSTEM_PROMPT = load_prompt("fitness")

# LLM для агента
_llm = ChatOpenAI(
    model=OPENAI_AGENT_MODEL,
    api_key=OPENAI_API_KEY,
    temperature=0,
    model_kwargs={"parallel_tool_calls": False},
)


def build_fitness_agent(checkpointer=None, user_id: int = 0):
    """
    Строит FitnessAgent. user_id нужен для привязки tools к пользователю.
    """
    from tools.fitness_tools import make_fitness_tools
    # Создаём tools привязанные к user_id
    fitness_tools = make_fitness_tools(user_id)
    # Динамически добавляем текущее время и таймзону (для парсинга «в 11 утра» → ISO)
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    _MSK = _tz(_td(hours=3))
    _now_msk = _dt.now(_MSK).strftime("%Y-%m-%dT%H:%M:%S+03:00")
    _dynamic_prompt = (
        _SYSTEM_PROMPT
        + f"\n\nТекущее время (МСК): {_now_msk}"
        + "\nЧасовой пояс: Europe/Moscow (UTC+3)"
    )
    return create_react_agent(
        model=_llm,
        tools=fitness_tools,
        prompt=_dynamic_prompt,
        checkpointer=checkpointer,
    )
