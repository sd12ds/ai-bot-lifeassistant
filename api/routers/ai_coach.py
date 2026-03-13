"""
REST API роутер для AI Coach (/api/ai).
Эндпоинты для AI-ассистента: сборка тренировки, замена упражнения,
анализ прогресса, рекомендации.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.models import User
from services import ai_coach

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai-coach"])


# ── Pydantic-схемы запросов/ответов ──────────────────────────────────────────

class BuildWorkoutDto(BaseModel):
    """DTO для сборки тренировки AI Coach."""
    muscle_groups: list[str] = Field(..., description="Группы мышц: chest, back, legs, shoulders, arms, core")
    duration_min: int = Field(60, ge=15, le=180, description="Длительность тренировки в минутах")
    location: str = Field("gym", description="Место: gym, home, outdoor")
    difficulty: str = Field("intermediate", description="Уровень: beginner, intermediate, advanced")
    notes: str = Field("", description="Дополнительные пожелания")


class BuildWorkoutExercise(BaseModel):
    """Упражнение в собранной тренировке."""
    exercise_id: int
    exercise_name: str
    sets: int
    reps: int
    rest_sec: int = 90
    notes: str = ""


class BuildWorkoutOut(BaseModel):
    """Ответ — собранная тренировка."""
    name: str
    description: str
    exercises: list[BuildWorkoutExercise] = []


class ReplaceExerciseDto(BaseModel):
    """DTO для замены упражнения."""
    exercise_id: int = Field(..., description="ID упражнения для замены")
    reason: str = Field("", description="Причина замены (необязательно)")


class AlternativeExercise(BaseModel):
    """Альтернативное упражнение."""
    exercise_id: int
    exercise_name: str
    reason: str


class ReplaceExerciseOut(BaseModel):
    """Ответ — альтернативы для замены."""
    original: str
    alternatives: list[AlternativeExercise] = []


class ProgressHighlight(BaseModel):
    """Ключевое наблюдение в анализе прогресса."""
    text: str


class AnalyzeProgressOut(BaseModel):
    """Ответ — анализ прогресса."""
    analysis: str
    highlights: list[str] = []
    trend: str = "insufficient_data"


class Recommendation(BaseModel):
    """Одна рекомендация."""
    icon: str = "💡"
    title: str
    text: str


class RecommendationsOut(BaseModel):
    """Ответ — персональные рекомендации."""
    recommendations: list[Recommendation] = []
    weekly_focus: str = ""


# ── Эндпоинты ────────────────────────────────────────────────────────────────

@router.post("/build-workout", response_model=BuildWorkoutOut)
async def build_workout(dto: BuildWorkoutDto, user: User = Depends(get_current_user)):
    """Собрать тренировку по группам мышц с помощью AI."""
    try:
        result = await ai_coach.build_workout(
            user_id=user.telegram_id,
            muscle_groups=dto.muscle_groups,
            duration_min=dto.duration_min,
            location=dto.location,
            difficulty=dto.difficulty,
            notes=dto.notes,
        )
        return result
    except Exception as e:
        logger.error(f"AI build-workout error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка генерации тренировки")


@router.post("/replace-exercise", response_model=ReplaceExerciseOut)
async def replace_exercise(dto: ReplaceExerciseDto, user: User = Depends(get_current_user)):
    """Предложить альтернативы для замены упражнения."""
    try:
        result = await ai_coach.replace_exercise(
            user_id=user.telegram_id,
            exercise_id=dto.exercise_id,
            reason=dto.reason,
        )
        # Проверяем на ошибку от сервиса
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI replace-exercise error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка подбора альтернатив")


@router.get("/analyze-progress", response_model=AnalyzeProgressOut)
async def analyze_progress(user: User = Depends(get_current_user)):
    """AI-анализ прогресса пользователя."""
    try:
        result = await ai_coach.analyze_progress(user_id=user.telegram_id)
        return result
    except Exception as e:
        logger.error(f"AI analyze-progress error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка анализа прогресса")


@router.get("/recommendations", response_model=RecommendationsOut)
async def get_recommendations(user: User = Depends(get_current_user)):
    """Персональные AI-рекомендации."""
    try:
        result = await ai_coach.get_recommendations(user_id=user.telegram_id)
        return result
    except Exception as e:
        logger.error(f"AI recommendations error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка генерации рекомендаций")
