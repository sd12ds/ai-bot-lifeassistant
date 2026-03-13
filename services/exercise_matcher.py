"""
Маппинг названий упражнений из текста на ExerciseLibrary.
Использует get_or_create_exercise: поиск по имени → создание если не найдено.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from db import fitness_storage as fs

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Результат маппинга одного упражнения."""
    exercise_id: int
    exercise_name: str       # имя из справочника (может отличаться от входного)
    original_name: str       # оригинальное имя из текста пользователя
    created: bool            # True если создано новое пользовательское упражнение
    sets: int
    reps: int | None
    muscle_group: str | None
    equipment: str | None


async def match_exercise(
    user_id: int,
    name: str,
    sets: int = 3,
    reps: int | None = None,
    muscle_group: str | None = None,
    equipment: str | None = None,
) -> MatchResult:
    """
    Маппит одно упражнение по имени на ExerciseLibrary.
    Если не найдено — создаёт пользовательское.
    """
    # Маппинг оборудования: текст парсера → формат БД
    equipment_map = {
        "штанга": "штанга",
        "гантели": "гантели",
        "тренажёр": "тренажёр",
        "тренажер": "тренажёр",
        "кроссовер": "тренажёр",
        "гравитрон": "тренажёр",
        "смит": "тренажёр",
        "без оборудования": "без оборудования",
    }
    eq_normalized = equipment_map.get(equipment, equipment) if equipment else None

    ex = await fs.get_or_create_exercise(
        user_id=user_id,
        name=name,
        category="strength",
        muscle_group=muscle_group,
        equipment=eq_normalized,
    )

    # Определяем создано ли новое: если user_id != None → пользовательское
    created = ex.get("user_id") is not None and ex.get("name", "").strip().lower() == name.strip().lower()

    return MatchResult(
        exercise_id=ex["id"],
        exercise_name=ex["name"],
        original_name=name,
        created=created,
        sets=sets,
        reps=reps,
        muscle_group=muscle_group,
        equipment=equipment,
    )


async def match_all(
    user_id: int,
    exercises: list[dict],
) -> list[MatchResult]:
    """
    Маппит список упражнений из парсера.
    exercises: [{"name": "...", "sets": 3, "reps": 12, "muscle_group": "...", "equipment": "..."}]
    """
    results = []
    for ex in exercises:
        result = await match_exercise(
            user_id=user_id,
            name=ex.get("name", ""),
            sets=ex.get("sets", 3),
            reps=ex.get("reps"),
            muscle_group=ex.get("muscle_group"),
            equipment=ex.get("equipment"),
        )
        results.append(result)

    found = sum(1 for r in results if not r.created)
    created = sum(1 for r in results if r.created)
    logger.info(
        "Exercise matching: %d найдено в справочнике, %d создано как пользовательские",
        found, created,
    )
    return results
