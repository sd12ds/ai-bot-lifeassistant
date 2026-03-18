"""
Сервис AI Coach — 4 функции для фитнес-ассистента.

Каждая функция формирует промпт, вызывает LLM и возвращает структурированный ответ.
Паттерн: ChatOpenAI → промпт → JSON-ответ.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from langchain_openai import ChatOpenAI
from config import OPENAI_API_KEY, OPENAI_LLM_MODEL
from db import fitness_storage as fs

logger = logging.getLogger(__name__)


def _get_llm(temperature: float = 0.7) -> ChatOpenAI:
    """Создаёт экземпляр LLM с заданной температурой."""
    return ChatOpenAI(
        model=OPENAI_LLM_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=temperature,
    )


def _clean_json(text: str) -> str:
    """Убирает markdown-обёртки из ответа LLM."""
    text = text.strip()
    if text.startswith("```"):
        # Убираем ```json или ``` в начале
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0]
    return text.strip()


async def build_workout(
    user_id: int,
    muscle_groups: list[str],
    duration_min: int = 60,
    location: str = "gym",
    difficulty: str = "intermediate",
    notes: str = "",
) -> dict:
    """
    Собрать тренировку по группам мышц.
    Возвращает dict с name, description и списком упражнений.
    """
    # Получаем справочник упражнений для контекста
    exercises = await fs.search_exercises(query="", limit=200)
    exercise_names = [
        f"{e['id']}: {e['name']} ({e.get('muscle_group', '?')}, {e.get('equipment', '?')})"
        for e in exercises
    ]

    # Получаем историю тренировок для персонализации
    stats = await fs.get_workout_stats(user_id=user_id, days=30)
    records = await fs.get_personal_records(user_id=user_id)

    # Метки уровня и локации
    diff_labels = {"beginner": "начинающий", "intermediate": "средний", "advanced": "продвинутый"}
    loc_labels = {"gym": "зал", "home": "дом", "outdoor": "улица"}

    # Контекст пользователя
    user_context = ""
    if stats.get("total_sessions", 0) > 0:
        user_context = f"""
КОНТЕКСТ ПОЛЬЗОВАТЕЛЯ (за последние 30 дней):
- Тренировок: {stats['total_sessions']}
- Общий объём: {round(stats.get('total_volume_kg', 0))} кг
- Streak: {stats.get('current_streak_days', 0)} дней подряд"""
    if records:
        user_context += "\n- Рекорды: " + ", ".join(
            f"{r['exercise']} {r['value']}кг" for r in records[:5]
        )

    prompt = f"""Ты — профессиональный фитнес-тренер. Собери тренировку.

ПАРАМЕТРЫ:
- Группы мышц: {', '.join(muscle_groups)}
- Длительность: ~{duration_min} мин
- Место: {loc_labels.get(location, location)}
- Уровень: {diff_labels.get(difficulty, difficulty)}
{f'- Примечания: {notes}' if notes else ''}
{user_context}

ДОСТУПНЫЕ УПРАЖНЕНИЯ (id: название):
{chr(10).join(exercise_names[:100])}

ОТВЕТЬ СТРОГО В JSON (без markdown):
{{
  "name": "Название тренировки",
  "description": "Краткое описание (1-2 предложения)",
  "exercises": [
    {{
      "exercise_id": 1,
      "exercise_name": "Жим лёжа",
      "sets": 4,
      "reps": 8,
      "rest_sec": 90,
      "notes": "Краткая подсказка по технике"
    }}
  ]
}}

Подбери 4-6 упражнений. Используй ТОЛЬКО id из списка выше. Рекомендуй подходящий вес/повторы для уровня."""

    llm = _get_llm(temperature=0.7)
    response = await llm.ainvoke(prompt)
    content = _clean_json(response.content)
    return json.loads(content)


async def replace_exercise(
    user_id: int,
    exercise_id: int,
    reason: str = "",
) -> dict:
    """
    Предложить 3 альтернативы для замены упражнения.
    Возвращает dict с original и alternatives.
    """
    # Получаем оригинальное упражнение
    original = await fs.get_exercise_by_id(exercise_id)
    if not original:
        return {"error": "Упражнение не найдено"}

    # Получаем все упражнения для альтернатив
    exercises = await fs.search_exercises(query="", limit=200)
    exercise_names = [
        f"{e['id']}: {e['name']} ({e.get('muscle_group', '?')}, {e.get('equipment', '?')})"
        for e in exercises
        if e['id'] != exercise_id  # исключаем оригинал
    ]

    # Цель пользователя
    goal = await fs.get_fitness_goal(user_id=user_id)
    location = goal.get("training_location", "gym") if goal else "gym"
    loc_labels = {"gym": "зал", "home": "дом", "outdoor": "улица"}

    prompt = f"""Ты — фитнес-тренер. Предложи 3 альтернативы для замены упражнения.

ОРИГИНАЛ:
- Название: {original['name']}
- Группа мышц: {original.get('muscle_group', '?')}
- Оборудование: {original.get('equipment', '?')}
- Категория: {original.get('category', '?')}
{f'- Причина замены: {reason}' if reason else ''}

МЕСТО ТРЕНИРОВКИ: {loc_labels.get(location, location)}

ДОСТУПНЫЕ УПРАЖНЕНИЯ:
{chr(10).join(exercise_names[:100])}

ОТВЕТЬ СТРОГО В JSON (без markdown):
{{
  "original": "{original['name']}",
  "alternatives": [
    {{
      "exercise_id": 2,
      "exercise_name": "Название",
      "reason": "Почему подходит как замена (1 предложение)"
    }}
  ]
}}

Подбери альтернативы, которые нагружают ту же группу мышц. Используй ТОЛЬКО id из списка."""

    llm = _get_llm(temperature=0.5)
    response = await llm.ainvoke(prompt)
    content = _clean_json(response.content)
    return json.loads(content)


async def analyze_progress(user_id: int) -> dict:
    """
    AI-анализ прогресса — текстовый отчёт на основе данных.
    Возвращает dict с analysis (текст) и highlights (список).
    """
    # Собираем данные за 30 и 90 дней
    stats_30 = await fs.get_workout_stats(user_id=user_id, days=30)
    stats_90 = await fs.get_workout_stats(user_id=user_id, days=90)
    records = await fs.get_personal_records(user_id=user_id)
    body_metrics = await fs.get_body_metrics(user_id=user_id, days=90, limit=50)
    weekly_volume = await fs.get_weekly_volume(user_id=user_id, weeks=12)
    goal = await fs.get_fitness_goal(user_id=user_id)

    # Формируем данные для промпта
    weight_history = [
        f"{m.get('logged_at', '?')[:10]}: {m['weight_kg']}кг"
        for m in body_metrics if m.get('weight_kg')
    ][:20]

    volume_history = [
        f"Нед {w['week']}: {w['sessions']} тр, {round(w['volume'])}кг объём"
        for w in weekly_volume
    ]

    prompt = f"""Ты — персональный фитнес-тренер. Проанализируй прогресс пользователя.

СТАТИСТИКА ЗА 30 ДНЕЙ:
- Тренировок: {stats_30.get('total_sessions', 0)}
- Объём: {round(stats_30.get('total_volume_kg', 0))} кг
- Время: {round(stats_30.get('total_time_min', 0))} мин
- Streak: {stats_30.get('current_streak_days', 0)} дней
- Активностей (кардио, растяжка и пр.): {stats_30.get('total_activities', 0)}
- Время активностей: {round(stats_30.get('total_activity_time_min', 0))} мин
- Калории от активностей: {round(stats_30.get('total_activity_calories', 0))} ккал

СТАТИСТИКА ЗА 90 ДНЕЙ:
- Тренировок: {stats_90.get('total_sessions', 0)}
- Объём: {round(stats_90.get('total_volume_kg', 0))} кг
- Активностей: {stats_90.get('total_activities', 0)}
- Время активностей: {round(stats_90.get('total_activity_time_min', 0))} мин

ИСТОРИЯ ВЕСА ТЕЛА:
{chr(10).join(weight_history) if weight_history else 'Нет данных'}

ОБЪЁМ ПО НЕДЕЛЯМ:
{chr(10).join(volume_history) if volume_history else 'Нет данных'}

ЛИЧНЫЕ РЕКОРДЫ:
{chr(10).join(f"- {r['exercise']}: {r['value']}кг" for r in records[:10]) if records else 'Нет данных'}

{f"ЦЕЛЬ: {goal.get('goal_type', '?')}, {goal.get('workouts_per_week', '?')} тр/нед, целевой вес: {goal.get('target_weight_kg', 'не указан')}кг" if goal else ''}

ОТВЕТЬ СТРОГО В JSON (без markdown):
{{
  "analysis": "Подробный анализ прогресса (3-5 предложений, на русском)",
  "highlights": [
    "Ключевое наблюдение 1",
    "Ключевое наблюдение 2",
    "Ключевое наблюдение 3"
  ],
  "trend": "improving | stable | declining | insufficient_data"
}}

Будь конкретным — используй цифры из данных. Не придумывай несуществующие данные."""

    llm = _get_llm(temperature=0.4)
    response = await llm.ainvoke(prompt)
    content = _clean_json(response.content)
    return json.loads(content)


async def get_recommendations(user_id: int) -> dict:
    """
    Персональные рекомендации на основе данных пользователя.
    Возвращает dict со списком рекомендаций.
    """
    # Собираем контекст
    stats = await fs.get_workout_stats(user_id=user_id, days=30)
    records = await fs.get_personal_records(user_id=user_id)
    goal = await fs.get_fitness_goal(user_id=user_id)
    body_metrics = await fs.get_body_metrics(user_id=user_id, days=30, limit=10)
    weekly_volume = await fs.get_weekly_volume(user_id=user_id, weeks=8)

    # Последний вес
    last_weight = None
    for m in body_metrics:
        if m.get("weight_kg"):
            last_weight = m["weight_kg"]
            break

    # Частота тренировок
    sessions_per_week = []
    for w in weekly_volume:
        sessions_per_week.append(w.get("sessions", 0))

    prompt = f"""Ты — персональный фитнес-тренер. Дай рекомендации на ближайшую неделю.

ДАННЫЕ ПОЛЬЗОВАТЕЛЯ:
- Тренировок за 30 дней: {stats.get('total_sessions', 0)}
- Активностей (кардио, растяжка и пр.): {stats.get('total_activities', 0)}
- Время активностей: {round(stats.get('total_activity_time_min', 0))} мин
- Streak: {stats.get('current_streak_days', 0)} дней
- Объём за месяц: {round(stats.get('total_volume_kg', 0))} кг
{f'- Текущий вес: {last_weight} кг' if last_weight else ''}
{f'- Тренировок по неделям: {sessions_per_week}' if sessions_per_week else ''}

{f"ЦЕЛЬ: {goal.get('goal_type', '?')}, {goal.get('workouts_per_week', '?')} тр/нед" if goal else 'Цель не установлена'}

ЛИЧНЫЕ РЕКОРДЫ: {', '.join(f"{r['exercise']} {r['value']}кг" for r in records[:5]) if records else 'Нет'}

ТОП УПРАЖНЕНИЙ: {', '.join(f"{e.get('name', '?')} ({e.get('sets_count', 0)} подх)" for e in stats.get('top_exercises', [])[:5])}

ОТВЕТЬ СТРОГО В JSON (без markdown):
{{
  "recommendations": [
    {{
      "icon": "💪",
      "title": "Заголовок рекомендации",
      "text": "Подробное описание (1-2 предложения)"
    }}
  ],
  "weekly_focus": "Краткий фокус на неделю (1 предложение)"
}}

Дай 3-5 конкретных, персонализированных рекомендаций. Используй данные пользователя."""

    llm = _get_llm(temperature=0.6)
    response = await llm.ainvoke(prompt)
    content = _clean_json(response.content)
    return json.loads(content)
