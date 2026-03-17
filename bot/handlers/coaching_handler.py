"""
CoachingHandler — тонкий entry point.

Подключает 6 sub-router'ов:
  coaching_callbacks_onboarding — главное меню + onboarding
  coaching_callbacks_goals      — goals callbacks
  coaching_callbacks_habits     — habits callbacks
  coaching_callbacks_checkins   — checkins, reviews, flow control, daily proactive
  coaching_callbacks_proactive  — recommendations, memory, reset, orchestration, motivational, states
  coaching_fsm                  — FSM text handlers + Voice Checkin flow
"""
from aiogram import Router

from .coaching_callbacks_onboarding import router as onboarding_router
from .coaching_callbacks_goals import router as goals_router
from .coaching_callbacks_habits import router as habits_router
from .coaching_callbacks_checkins import router as checkins_router
from .coaching_callbacks_proactive import router as proactive_router
from .coaching_fsm import router as fsm_router

# Главный роутер модуля — регистрируется в bot/core/
router = Router()

# Порядок важен: FSM-хендлеры последними (меньший приоритет)
router.include_router(onboarding_router)
router.include_router(goals_router)
router.include_router(habits_router)
router.include_router(checkins_router)
router.include_router(proactive_router)
router.include_router(fsm_router)
