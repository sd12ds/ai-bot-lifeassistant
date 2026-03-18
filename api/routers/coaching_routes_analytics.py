"""
Coaching API — аналитика, промпты, инсайты, рекомендации, память,
персонализация, orchestration, кросс-модульный анализ.

Группы endpoints:
  GET  /analytics/weekly|habits|goals|engagement|streaks|habits/detailed
       /analytics/dropout-risk|goals/detailed
  GET  /prompts                        — sample prompts для UI
  GET  /insights                       — список инсайтов
  POST /insights/{id}/read
  GET  /recommendations                — список рекомендаций
  POST /recommendations/{id}/dismiss
  GET  /memory                         — coaching-память
  DELETE /memory                       — сброс памяти
  GET  /profile/personalization        — поведенческий профиль
  POST /profile/reset                  — сброс персонализации
  GET  /orchestration/pending          — ожидающие подтверждения действия
  POST /orchestration/{id}/confirm|reject
  POST /cross-module/analyze           — ручной запуск анализа
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from db.models import User, CoachingOrchestrationAction
from db.session import get_session
import db.coaching_storage as cs
from services.coaching_analytics import (
    get_goal_metrics,
    get_habit_detailed_metrics,
    get_engagement_metrics,
    get_streak_analytics,
    compute_weekly_score_auto,
    compute_dropout_risk_detailed,
    DROPOUT_RISK_HIGH_THRESHOLD,
)
from services.coaching_cross_module import (
    run_cross_module_analysis,
    execute_orchestration_action,
)
from services.coaching_personalization import (
    get_adaptation_context,
    reset_personalization as reset_personalization_svc,
)
from services.coaching_engine import (
    compute_user_state,
    compute_risk_scores,
)

from .coaching_schemas import WeeklyAnalyticsOut, SAMPLE_PROMPTS, _goal_to_dict, _habit_to_dict

# Отдельный роутер без prefix — prefix задаётся в coaching.py через include_router
router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/analytics/weekly", response_model=WeeklyAnalyticsOut)
async def weekly_analytics(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Сводная аналитика за текущую неделю с детальным breakdown скора."""
    user_id = current_user.telegram_id
    from sqlalchemy import select as _sel4
    from db.models import GoalCheckin as _GC4
    _r4 = await db.execute(
        _sel4(_GC4).where(_GC4.user_id == user_id).order_by(_GC4.created_at.desc()).limit(7)
    )
    checkins = list(_r4.scalars().all())
    goals, state_data, risks = await asyncio.gather(
        cs.get_goals(db, user_id, status="active"),
        compute_user_state(db, user_id),
        compute_risk_scores(db, user_id),
    )
    # Auto-расчёт weekly score из DB с детализацией
    weekly_score, score_breakdown = await compute_weekly_score_auto(db, user_id)

    # Completion rate привычек из breakdown
    habits_completion_rate = round(score_breakdown.get("habits", 0) / 40, 2)

    dropout_risk = risks.get("dropout", 0.0)
    if dropout_risk >= DROPOUT_RISK_HIGH_THRESHOLD:
        dropout_level = "critical"
    elif dropout_risk >= 0.5:
        dropout_level = "high"
    elif dropout_risk >= 0.3:
        dropout_level = "medium"
    elif dropout_risk >= 0.1:
        dropout_level = "low"
    else:
        dropout_level = "none"

    return WeeklyAnalyticsOut(
        weekly_score=weekly_score,
        weekly_score_breakdown=score_breakdown,
        goals_progress=[_goal_to_dict(g) for g in goals],
        habits_completion_rate=habits_completion_rate,
        checkins_this_week=score_breakdown.get("checkins_this_week", len(checkins)),
        dropout_risk=dropout_risk,
        dropout_risk_level=dropout_level,
        state=state_data["state"],
    )


@router.get("/analytics/habits")
async def habits_analytics(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Аналитика по всем привычкам: completion rate, streaks."""
    habits = await cs.get_habits(db, current_user.telegram_id, is_active=True)
    at_risk = await cs.get_habits_at_risk(db, current_user.telegram_id, days_no_log=3)
    return {
        "total_habits": len(habits),
        "at_risk_count": len(at_risk),
        "avg_streak": round(sum(h.current_streak for h in habits) / len(habits), 1) if habits else 0,
        "habits": [_habit_to_dict(h) for h in habits],
    }


@router.get("/analytics/goals")
async def goals_analytics(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Аналитика по целям: прогресс, stuck, achieved."""
    user_id = current_user.telegram_id
    active = await cs.get_goals(db, user_id, status="active")
    achieved = await cs.get_goals(db, user_id, status="achieved")
    stuck = await cs.get_stuck_goals(db, user_id, days_without_progress=7)
    return {
        "active_count": len(active),
        "achieved_count": len(achieved),
        "stuck_count": len(stuck),
        "avg_progress": round(sum(g.progress_pct for g in active) / len(active), 1) if active else 0,
        "goals": [_goal_to_dict(g) for g in active],
    }


@router.get("/analytics/engagement")
async def engagement_analytics(
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Метрики вовлечённости: частота check-in, nudge response rate, сессии с коучем,
    использование функций за последние N дней.
    """
    return await get_engagement_metrics(db, current_user.telegram_id, days=days)


@router.get("/analytics/streaks")
async def streaks_analytics(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Аналитика стриков: топ привычки, рекорды, привычки под угрозой срыва.
    """
    return await get_streak_analytics(db, current_user.telegram_id)


@router.get("/analytics/habits/detailed")
async def habits_detailed_analytics(
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list:
    """
    Детальные метрики привычек: consistency score, лучший/худший день недели,
    временные паттерны (утро/день/вечер) за последние N дней.
    """
    return await get_habit_detailed_metrics(db, current_user.telegram_id, days=days)


@router.get("/analytics/dropout-risk")
async def dropout_risk_analytics(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Детальный анализ риска дропаута (§22.2):
    score, level, факторы, рекомендации.
    Score > 0.7 → HIGH RISK → запускается reactivation-сценарий.
    """
    return await compute_dropout_risk_detailed(db, current_user.telegram_id)


@router.get("/analytics/goals/detailed")
async def goals_detailed_analytics(
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Детальные метрики целей: completion rate, среднее время достижения,
    abandonment rate, milestone completion rate, распределение по областям.
    """
    return await get_goal_metrics(db, current_user.telegram_id, days=days)


# ══════════════════════════════════════════════════════════════════════════════
# PROMPTS (sample prompts для UI)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/prompts")
async def get_prompts(
    context: Optional[str] = Query(None),  # onboarding|dashboard|goal|habit|review
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[str]:
    """
    Sample prompts для CoachPromptBubble и каруселей в UI.
    Контекстно-зависимые по параметру context.
    """
    state_data = await compute_user_state(db, current_user.telegram_id)
    state = state_data["state"]

    # Контекстно-специфичные промпты для разных экранов Mini App
    context_prompts = {
        "onboarding": [
            "Расскажи как ты работаешь",
            "Помоги поставить первую цель",
            "Покажи примеры привычек",
        ],
        "goal": [
            "Разбей эту цель на этапы",
            "Что мне сделать сегодня для этой цели?",
            "Оцени реалистичность дедлайна",
            "Найди связь этой цели с моими привычками",
        ],
        "habit": [
            "Как усилить эту привычку?",
            "Почему я срываюсь?",
            "Свяжи эту привычку с целью",
        ],
        "review": [
            "Оцени мою неделю",
            "Что у меня получилось?",
            "Что стоит изменить на следующей неделе?",
        ],
        "empty": [
            "С чего начать?",
            "Поставим первую цель",
            "Создадим привычку",
            "Расскажи о себе чтобы я мог помочь",
        ],
    }

    if context and context in context_prompts:
        return context_prompts[context]

    return SAMPLE_PROMPTS.get(state, SAMPLE_PROMPTS["default"])


# ══════════════════════════════════════════════════════════════════════════════
# INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/insights")
async def list_insights(
    limit: int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list:
    insights = await cs.get_active_insights(db, current_user.telegram_id, limit=limit)
    return [
        {
            "id": i.id,
            "insight_type": i.insight_type,
            "severity": i.severity,
            "title": getattr(i, 'title', ''),
            "body": getattr(i, 'body', ''),
            "is_read": i.is_read,
            "created_at": i.created_at.isoformat(),
        }
        for i in insights
    ]


@router.post("/insights/{insight_id}/read")
async def mark_insight_read(
    insight_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    await cs.mark_insight_read(db, insight_id, current_user.telegram_id)
    await db.commit()
    return {"read": True}


# ══════════════════════════════════════════════════════════════════════════════
# RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/recommendations")
async def list_recommendations(
    limit: int = Query(default=5, le=20),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list:
    recs = await cs.get_active_recommendations(db, current_user.telegram_id, limit=limit)
    return [
        {
            "id": r.id,
            "rec_type": r.rec_type,
            "priority": r.priority,
            "title": r.title,
            "body": getattr(r, 'body', ''),
            "action_type": r.action_type,
            "action_payload": r.action_payload,
        }
        for r in recs
    ]


@router.post("/recommendations/{rec_id}/dismiss")
async def dismiss_recommendation(
    rec_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    await cs.dismiss_recommendation(db, rec_id, current_user.telegram_id)
    await db.commit()
    return {"dismissed": True}


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/memory")
async def get_memory(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list:
    memories = await cs.get_memory(db, current_user.telegram_id, top_n=20)
    return [
        {
            "key": m.key,
            "value": m.value,
            "confidence": m.confidence,
            "is_explicit": m.is_explicit,
        }
        for m in memories
    ]


@router.delete("/memory")
async def clear_memory(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Сбросить coaching-память (reversible learning)."""
    count = await cs.clear_memory(db, current_user.telegram_id)
    await db.commit()
    return {"cleared": count}


# ══════════════════════════════════════════════════════════════════════════════
# PERSONALIZATION
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/profile/personalization")
async def get_personalization_profile(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Возвращает поведенческий профиль адаптации коуча:
    тон общения, выявленные паттерны, области фокуса, лучшее время для работы.
    """
    state_data = await compute_user_state(db, current_user.telegram_id)
    state = state_data["state"]
    profile = state_data.get("profile")
    coach_tone = profile.coach_tone if profile else "motivational"

    # Получаем полный контекст адаптации из сервиса персонализации
    adaptation = await get_adaptation_context(db, current_user.telegram_id, state)

    return {
        "tone": coach_tone,
        "tone_instruction": adaptation.get("tone_instruction"),
        "best_time": adaptation.get("best_time"),
        "active_patterns": adaptation.get("active_patterns", []),
        "focus_areas": adaptation.get("focus_areas", []),
        "has_explicit_corrections": adaptation.get("has_corrections", False),
    }


@router.post("/profile/reset", status_code=status.HTTP_200_OK)
async def reset_personalization_endpoint(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Сбрасывает всю персонализацию коуча: coaching_memory и behavior_patterns.
    Профиль, цели и привычки НЕ затрагиваются.
    """
    await reset_personalization_svc(db, current_user.telegram_id)
    await db.commit()
    return {
        "ok": True,
        "message": "Персонализация сброшена. Коуч начнёт адаптироваться заново.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATION ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/orchestration/pending")
async def get_pending_orchestration_actions(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list:
    """
    Список orchestration-действий, ожидающих подтверждения пользователя.
    Коуч предлагает создать задачу/событие/напоминание — пользователь подтверждает здесь.
    """
    actions = await cs.get_pending_actions(db, current_user.telegram_id)
    return [
        {
            "id": a.id,
            "action_type": a.action_type,
            "target_module": a.target_module,
            "payload": a.payload,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in actions
    ]


@router.post("/orchestration/{action_id}/confirm")
async def confirm_orchestration_action(
    action_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Подтвердить и выполнить orchestration-действие.
    Создаёт задачу/событие/напоминание в соответствующем модуле.
    """
    from sqlalchemy import select as sa_select
    # Ищем действие с проверкой принадлежности пользователю
    result = await db.execute(
        sa_select(CoachingOrchestrationAction).where(
            CoachingOrchestrationAction.id == action_id,
            CoachingOrchestrationAction.user_id == current_user.telegram_id,
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Действие не найдено")
    if action.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Действие уже в статусе: {action.status}")

    # Сначала помечаем как подтверждённое, потом выполняем
    await cs.confirm_orchestration_action(db, action_id, current_user.telegram_id)

    success, message = await execute_orchestration_action(db, action)
    await db.commit()

    return {"ok": success, "message": message, "action_id": action_id}


@router.post("/orchestration/{action_id}/reject")
async def reject_orchestration_action(
    action_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Отклонить orchestration-действие — оно не будет выполнено.
    """
    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(CoachingOrchestrationAction)
        .where(
            CoachingOrchestrationAction.id == action_id,
            CoachingOrchestrationAction.user_id == current_user.telegram_id,
        )
        .values(status="rejected")
    )
    await db.commit()
    return {"ok": True, "message": "Действие отклонено", "action_id": action_id}


# ══════════════════════════════════════════════════════════════════════════════
# CROSS-MODULE ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/cross-module/analyze")
async def trigger_cross_module_analysis(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Запустить кросс-модульный анализ вручную.
    Собирает сигналы из всех модулей, генерирует выводы и сохраняет рекомендации.
    Возвращает найденные проблемы и число сохранённых рекомендаций.
    """
    state_data = await compute_user_state(db, current_user.telegram_id)
    state = state_data["state"]

    result = await run_cross_module_analysis(db, current_user.telegram_id, state)
    await db.commit()

    return {
        "state": state,
        "inferences_found": len(result.get("inferences", [])),
        "recommendations_saved": result.get("saved_recommendations", 0),
        "top_inference": result.get("top_inference"),
        "signals_summary": {
            "tasks_overdue": result["signals"].get("tasks_overdue", 0),
            "calendar_events_today": result["signals"].get("calendar_events_today", 0),
            "last_workout_days_ago": result["signals"].get("last_workout_days_ago", 0),
            "habits_completion_rate": result["signals"].get("habits_completion_rate_week", 0),
            "activities_this_week": result["signals"].get("activities_this_week", 0),
            "last_activity_days_ago": result["signals"].get("last_activity_days_ago", 999),
        },
    }
