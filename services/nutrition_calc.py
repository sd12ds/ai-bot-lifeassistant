"""
Сервис расчёта КБЖУ на основе параметров тела и цели.

Формулы:
  - BMR: Миффлин — Сан Жеор
  - TDEE: BMR × коэффициент активности
  - Целевые макросы зависят от goal_type (lose / maintain / gain)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ── Перечисления ────────────────────────────────────────────

class Gender(str, Enum):
    """Пол пользователя."""
    MALE = "male"
    FEMALE = "female"


class GoalType(str, Enum):
    """Тип цели по питанию."""
    LOSE = "lose"          # похудение
    MAINTAIN = "maintain"  # удержание
    GAIN = "gain"          # набор массы


class ActivityLevel(str, Enum):
    """Уровень физической активности."""
    SEDENTARY = "sedentary"        # сидячий образ жизни
    LIGHT = "light"                # лёгкие тренировки 1-3 р/нед
    MODERATE = "moderate"          # умеренные тренировки 3-5 р/нед
    ACTIVE = "active"              # интенсивные тренировки 6-7 р/нед
    VERY_ACTIVE = "very_active"    # тяжёлая физ. работа / 2 тренировки в день


# Коэффициенты активности для расчёта TDEE
ACTIVITY_MULTIPLIERS: dict[ActivityLevel, float] = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHT: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.ACTIVE: 1.725,
    ActivityLevel.VERY_ACTIVE: 1.9,
}


# ── Результат расчёта ──────────────────────────────────────

@dataclass(frozen=True)
class NutritionTargets:
    """Рассчитанные суточные цели по КБЖУ."""
    calories: int      # ккал
    protein_g: int     # белки, г
    fat_g: int         # жиры, г
    carbs_g: int       # углеводы, г
    water_ml: int      # вода, мл (по умолчанию 2000)


# ── Функции расчёта ────────────────────────────────────────

def calculate_bmr(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: Gender | str,
) -> float:
    """
    Базовый метаболизм по формуле Миффлина — Сан Жеора.

    Мужчины:  10 × вес(кг) + 6.25 × рост(см) − 5 × возраст − 161 + 166
              (упрощённо: +5 для мужчин)
    Женщины:  10 × вес(кг) + 6.25 × рост(см) − 5 × возраст − 161

    Возвращает BMR в ккал/сутки.
    """
    # Приведение строки к enum, если нужно
    if isinstance(gender, str):
        gender = Gender(gender.lower())

    # Базовая часть формулы
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age

    if gender == Gender.MALE:
        bmr += 5       # мужская поправка
    else:
        bmr -= 161     # женская поправка

    return round(bmr, 1)


def calculate_tdee(
    bmr: float,
    activity_level: ActivityLevel | str,
) -> float:
    """
    Суточный расход энергии (TDEE) = BMR × коэффициент активности.

    Возвращает TDEE в ккал/сутки.
    """
    # Приведение строки к enum, если нужно
    if isinstance(activity_level, str):
        activity_level = ActivityLevel(activity_level.lower())

    multiplier = ACTIVITY_MULTIPLIERS[activity_level]
    return round(bmr * multiplier, 1)


def calculate_goals(
    tdee: float,
    goal_type: GoalType | str,
    weight_kg: float,
    water_ml: int = 2000,
) -> NutritionTargets:
    """
    Рассчитать целевые КБЖУ на основе TDEE, типа цели и веса.

    Правила:
      - Похудение (lose):     TDEE − 500 ккал, белок 2 г/кг, жиры 0.8 г/кг
      - Удержание (maintain):  TDEE,           белок 1.6 г/кг, жиры 1 г/кг
      - Набор (gain):          TDEE + 300 ккал, белок 2 г/кг, жиры 1 г/кг
      - Углеводы = остаток калорий / 4

    Возвращает NutritionTargets.
    """
    # Приведение строки к enum, если нужно
    if isinstance(goal_type, str):
        goal_type = GoalType(goal_type.lower())

    # Калорийная коррекция в зависимости от цели
    if goal_type == GoalType.LOSE:
        calories = tdee - 500
        protein_per_kg = 2.0
        fat_per_kg = 0.8
    elif goal_type == GoalType.MAINTAIN:
        calories = tdee
        protein_per_kg = 1.6
        fat_per_kg = 1.0
    else:  # GAIN
        calories = tdee + 300
        protein_per_kg = 2.0
        fat_per_kg = 1.0

    # Белки и жиры по весу
    protein_g = round(protein_per_kg * weight_kg)
    fat_g = round(fat_per_kg * weight_kg)

    # Калории от белков (4 ккал/г) и жиров (9 ккал/г)
    protein_cal = protein_g * 4
    fat_cal = fat_g * 9

    # Остаток калорий → углеводы (4 ккал/г)
    remaining_cal = max(calories - protein_cal - fat_cal, 0)
    carbs_g = round(remaining_cal / 4)

    # Итоговые калории пересчитываем для точности
    final_calories = protein_cal + fat_cal + carbs_g * 4

    return NutritionTargets(
        calories=round(final_calories),
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
        water_ml=water_ml,
    )


def calculate_full(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: Gender | str,
    activity_level: ActivityLevel | str,
    goal_type: GoalType | str,
    water_ml: int = 2000,
) -> NutritionTargets:
    """
    Удобная обёртка: все параметры → готовые КБЖУ за один вызов.

    Последовательно выполняет:
      1. calculate_bmr  →  BMR
      2. calculate_tdee  →  TDEE
      3. calculate_goals →  NutritionTargets
    """
    bmr = calculate_bmr(weight_kg, height_cm, age, gender)
    tdee = calculate_tdee(bmr, activity_level)
    return calculate_goals(tdee, goal_type, weight_kg, water_ml)
