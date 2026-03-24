"""
Загрузка системных промптов агентов из файлов prompts/.
Промпты хранятся в /prompts/<name>.txt отдельно от кода агента:
это позволяет редактировать промпт без изменения логики агента.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# Корень проекта — директория prompts/ находится на два уровня выше utils/
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Загружает системный промпт из prompts/{name}.txt.

    Кэширует результат (файл читается один раз за жизнь процесса).
    """ 
    path = _PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        logger.error("Промпт не найден: %s", path)
        return f"Ты полезный ассистент. Отвечай на русском языке."
    text = path.read_text(encoding="utf-8")
    logger.debug("Промпт загружен: %s (%d симв)", name, len(text))
    return text
