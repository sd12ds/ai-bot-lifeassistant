"""
ExtractionPipeline - извлечение структурированных данных из контента через LLM.
"""
from __future__ import annotations

import json
import logging
from langchain_openai import ChatOpenAI
from config import OPENAI_API_KEY, OPENAI_AGENT_MODEL

logger = logging.getLogger(__name__)

_llm = ChatOpenAI(model=OPENAI_AGENT_MODEL, api_key=OPENAI_API_KEY, temperature=0)


async def extract_structured(raw_content: str, schema: dict) -> dict:
    """Извлекает структурированные данные из контента по JSON-схеме через LLM."""
    if not raw_content or not schema:
        return {}
    fields_desc = json.dumps(schema, ensure_ascii=False, indent=2)
    prompt = f"""Извлеки данные из текста ниже по указанной схеме. Верни ТОЛЬКО JSON.

Схема полей:
{fields_desc}

Текст:
{raw_content[:4000]}

Ответ (JSON):"""
    try:
        response = await _llm.ainvoke(prompt)
        text = response.content.strip()
        # Убираем markdown обертку если есть
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(text)
    except Exception as e:
        logger.warning("LLM extraction failed: %s", e)
        return {}
