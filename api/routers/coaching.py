"""
Coaching API Router — тонкий aggregator.

Подключает 4 sub-router'а:
  coaching_routes_checkins  — dashboard, state, checkins, reviews, profile, onboarding
  coaching_routes_goals     — goals CRUD + milestones
  coaching_routes_habits    — habits CRUD + tracking
  coaching_routes_analytics — analytics, insights, recommendations, memory, personalization,
                              orchestration, cross-module, prompts
"""
from fastapi import APIRouter

from .coaching_routes_checkins import router as checkins_router
from .coaching_routes_goals import router as goals_router
from .coaching_routes_habits import router as habits_router
from .coaching_routes_analytics import router as analytics_router

# Главный роутер с общим prefix и тегом для документации
router = APIRouter(prefix="/coaching", tags=["coaching"])

# Подключаем sub-router'ы (без prefix — пути уже прописаны в sub-router'ах)
router.include_router(checkins_router)
router.include_router(goals_router)
router.include_router(habits_router)
router.include_router(analytics_router)
