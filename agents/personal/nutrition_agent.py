"""
NutritionAgent — агент для трекинга питания.
Инструменты привязываются к user_id через make_nutrition_tools.
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI
from utils.prompts import load_prompt
from langgraph.prebuilt import create_react_agent

from config import OPENAI_API_KEY, OPENAI_AGENT_MODEL

# Системный промпт для агента питания
_SYSTEM_PROMPT = load_prompt("nutrition")

# LLM для агента — parallel_tool_calls=False чтобы не было параллельных вызовов meal_log
_llm = ChatOpenAI(
    model=OPENAI_AGENT_MODEL,
    api_key=OPENAI_API_KEY,
    temperature=0,
    model_kwargs={"parallel_tool_calls": False},
)


def build_nutrition_agent(checkpointer=None, user_id: int = 0):
    """
    Строит NutritionAgent. user_id нужен для привязки tools к пользователю.
    """
    from tools.nutrition_tools import make_nutrition_tools
    # Создаём tools привязанные к user_id
    nutrition_tools = make_nutrition_tools(user_id)
    return create_react_agent(
        model=_llm,
        tools=nutrition_tools,
        prompt=_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
