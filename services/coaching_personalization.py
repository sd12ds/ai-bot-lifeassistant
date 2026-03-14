"""
coaching_personalization.py — Adaptive Personalization & Learning (Phase 8).

Отвечает за:
- Анализ поведенческих паттернов пользователя (implicit learning)
- Запись выводов в coaching_memory + behavior_patterns
- Обработку явных поправок (corrections log)
- Персонализацию тона и формата ответов
- Сброс настроек персонализации (reversible learning)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# =============================================================================
# АНАЛИЗ ПОВЕДЕНЧЕСКИХ ПАТТЕРНОВ (§19.2 архитектурного документа)
# =============================================================================

async def analyze_behavioral_patterns(
    session: AsyncSession,
    user_id: int,
) -> dict:
    """
    Анализирует поведение пользователя и возвращает словарь паттернов.

    Проверяет:
    - morning_person: >70% активности до 12:00
    - overcommits_goals: регулярно берёт >3 активных цели
    - streak_dependent: процент выполнения растёт при наличии стрика
    - best_engagement_time: час наибольшей активности
    - evening_checkin_avoidance: редко делает чекин после 20:00
    """
    from db import coaching_storage as cs
    from db.models import GoalCheckIn, Goal

    patterns = {}
    now = datetime.now(timezone.utc)
    lookback = now - timedelta(days=30)  # Анализируем последние 30 дней

    # 1. Morning person — анализ времени чекинов
    try:
        checkins = await cs.get_checkins(session, user_id, limit=50)
        if len(checkins) >= 5:
            # Timezone-safe: берём час UTC
            morning_count = sum(
                1 for c in checkins
                if c.created_at and c.created_at.hour < 12
            )
            ratio = morning_count / len(checkins)
            patterns["morning_person"] = {
                "value": ratio > 0.7,
                "confidence": min(0.3 + ratio * 0.7, 1.0),
                "ratio": round(ratio, 2),
            }
    except Exception as e:
        logger.debug("morning_person analysis failed: %s", e)

    # 2. Best engagement time — час с наибольшим количеством чекинов
    try:
        checkins = await cs.get_checkins(session, user_id, limit=100)
        if len(checkins) >= 5:
            hour_counts: dict[int, int] = {}
            for c in checkins:
                if c.created_at:
                    h = c.created_at.hour
                    hour_counts[h] = hour_counts.get(h, 0) + 1
            if hour_counts:
                best_hour = max(hour_counts, key=lambda h: hour_counts[h])
                patterns["best_engagement_time"] = {
                    "value": f"{best_hour:02d}:00",
                    "confidence": min(0.4 + 0.06 * len(checkins), 0.95),
                    "hour": best_hour,
                }
    except Exception as e:
        logger.debug("best_engagement_time analysis failed: %s", e)

    # 3. Overcommits goals — берёт >3 цели, но completion rate падает
    try:
        goals = await cs.get_goals(session, user_id)
        total_goals = len(goals)
        if total_goals >= 3:
            achieved = [g for g in goals if g.status == "achieved"]
            active = [g for g in goals if g.status == "active"]
            if total_goals > 0:
                completion_rate = len(achieved) / total_goals
                overcommits = len(active) > 3 or (total_goals > 5 and completion_rate < 0.3)
                if overcommits:
                    patterns["overcommits_goals"] = {
                        "value": True,
                        "confidence": 0.6 + (0.1 if len(active) > 5 else 0),
                        "active_count": len(active),
                    }
    except Exception as e:
        logger.debug("overcommits_goals analysis failed: %s", e)

    # 4. Streak dependent — привычки с долгим стриком выполняются чаще
    try:
        habits = await cs.get_habits(session, user_id, is_active=True)
        if len(habits) >= 2:
            high_streak = [h for h in habits if h.current_streak and h.current_streak >= 7]
            low_streak  = [h for h in habits if not h.current_streak or h.current_streak < 3]
            # Если у привычек с высоким стриком completion_rate выше — зависим от стрика
            if high_streak and low_streak:
                avg_high = sum(
                    h.completion_rate or 0 for h in high_streak
                ) / len(high_streak)
                avg_low = sum(
                    h.completion_rate or 0 for h in low_streak
                ) / len(low_streak)
                if avg_high - avg_low > 0.2:
                    patterns["streak_dependent"] = {
                        "value": True,
                        "confidence": 0.65,
                        "gap": round(avg_high - avg_low, 2),
                    }
    except Exception as e:
        logger.debug("streak_dependent analysis failed: %s", e)

    return patterns


async def update_memory_from_behavior(
    session: AsyncSession,
    user_id: int,
    patterns: dict,
) -> None:
    """
    Сохраняет выведенные паттерны в coaching_memory и behavior_patterns.
    Не перезаписывает явные корректировки (is_explicit=True).
    """
    from db import coaching_storage as cs

    for key, data in patterns.items():
        value = data.get("value")
        confidence = data.get("confidence", 0.5)

        if value is None:
            continue

        try:
            # Проверяем: есть ли явная коррекция (не трогаем её)
            existing = await cs.get_memory(session, user_id, key=key)
            if existing and existing[0].is_explicit:
                logger.debug("Skipping implicit update for explicit memory key=%s", key)
                continue

            # Сохраняем/обновляем запись
            value_str = str(value)
            await cs.upsert_memory(
                session, user_id,
                memory_type="pattern",
                key=key,
                value=value_str,
                confidence=confidence,
                is_explicit=False,
            )

            # Паттерны в BehaviorPattern (описательно)
            if key == "morning_person" and value:
                await cs.upsert_behavior_pattern(
                    session, user_id,
                    pattern_type="morning_person",
                    description="Активность >70% до 12:00 — «утренний человек»",
                    frequency="often",
                    affected_areas=["habits", "checkin"],
                )
            elif key == "overcommits_goals" and value:
                await cs.upsert_behavior_pattern(
                    session, user_id,
                    pattern_type="overcommits",
                    description=f"Регулярно берёт >{data.get('active_count', 3)} целей одновременно",
                    frequency="often",
                    affected_areas=["goals"],
                )
            elif key == "streak_dependent" and value:
                await cs.upsert_behavior_pattern(
                    session, user_id,
                    pattern_type="streak_dependent",
                    description=f"Completion rate растёт при стрике (разрыв {data.get('gap', 0):.0%})",
                    frequency="often",
                    affected_areas=["habits"],
                )

        except Exception as e:
            logger.warning("Failed to update memory key=%s: %s", key, e)


# =============================================================================
# ЯВНЫЕ КОРРЕКТИРОВКИ (§19.3 — corrections log)
# =============================================================================

async def apply_explicit_correction(
    session: AsyncSession,
    user_id: int,
    key: str,
    value: str,
    description: str = "",
) -> None:
    """
    Сохраняет явную коррекцию пользователя.
    is_explicit=True + confidence=1.0 — эти данные имеют наивысший приоритет.
    """
    from db import coaching_storage as cs
    await cs.upsert_memory(
        session, user_id,
        memory_type="correction",
        key=key,
        value=value,
        confidence=1.0,
        is_explicit=True,
    )
    logger.info("Explicit correction applied: user=%s key=%s value=%s", user_id, key, value)


# =============================================================================
# ПЕРСОНАЛИЗИРОВАННЫЙ ТОН (§19.1, §19.2)
# =============================================================================

def get_personalized_tone_instruction(
    state: str,
    coach_tone: str = "friendly",
    patterns: list | None = None,
) -> str:
    """
    Возвращает инструкцию по тону с учётом:
    - Текущего состояния пользователя (state)
    - Предпочтения тона (coach_tone из профиля)
    - Поведенческих паттернов

    Для кризисных состояний (overload/risk) — всегда мягкий тон,
    независимо от предпочтений (безопасность важнее).
    """
    patterns = patterns or []

    # Кризисные состояния переопределяют тон
    if state == "overload":
        return (
            "Пользователь ПЕРЕГРУЖЕН. ОБЯЗАТЕЛЬНО: мягкий тон, нет давления, "
            "помоги разгрузиться. Предложи убрать лишнее."
        )
    if state == "risk":
        return (
            "ВЫСОКИЙ РИСК DROPOUT. Заботливый и прямой тон. "
            "Одно простое действие прямо сейчас. Без осуждений."
        )
    if state == "recovery":
        return (
            "Пользователь ВОЗВРАЩАЕТСЯ после паузы. "
            "Мягкий тон, без упрёков. Маленький шаг вперёд."
        )

    # Адаптация под предпочтение тона
    tone_instructions = {
        "strict": (
            "Пользователь предпочитает ТРЕБОВАТЕЛЬНЫЙ стиль. "
            "Прямые формулировки, высокие ожидания, конкретные сроки."
        ),
        "motivational": (
            "Пользователь предпочитает МОТИВАЦИОННЫЙ стиль. "
            "Энергия, вдохновение, акцент на достижениях и потенциале."
        ),
        "soft": (
            "Пользователь предпочитает МЯГКИЙ стиль. "
            "Поддержка без давления, понимание, принятие."
        ),
        "friendly": (
            "Пользователь предпочитает ДРУЖЕЛЮБНЫЙ стиль. "
            "Тёплый, разговорный, как друг-наставник."
        ),
    }
    base = tone_instructions.get(coach_tone, tone_instructions["friendly"])

    # Дополнение под паттерны
    additions = []
    if "streak_dependent" in patterns:
        additions.append("Всегда упоминай серию (стрик) — это главный мотиватор.")
    if "overcommits" in patterns:
        additions.append("Мягко предупреждай о перегрузке при новых целях/привычках.")
    if "morning_person" in patterns:
        additions.append("Лучшее время для задач — утро, планируй на это.")

    if additions:
        return base + " " + " ".join(additions)
    return base


# =============================================================================
# КОНТЕКСТ АДАПТАЦИИ ДЛЯ АГЕНТА
# =============================================================================

async def get_adaptation_context(
    session: AsyncSession,
    user_id: int,
    state: str = "stable",
) -> dict:
    """
    Возвращает персонализированный контекст для инъекции в системный промпт:
    - tone_instruction: инструкция по тону
    - best_time: лучшее время активности
    - active_patterns: список активных паттернов
    - has_corrections: есть ли явные корректировки
    """
    from db import coaching_storage as cs

    profile = await cs.get_or_create_profile(session, user_id)
    memories = await cs.get_memory(session, user_id, top_n=20)
    patterns_db = await cs.get_behavior_patterns(session, user_id)

    # Список активных паттернов по типу
    active_patterns = [p.pattern_type for p in patterns_db]

    # Лучшее время из памяти
    best_time = None
    for m in memories:
        if m.key == "best_engagement_time":
            best_time = m.value
            break

    # Проверяем явные корректировки
    has_corrections = any(m.is_explicit for m in memories)

    # Персонализированная инструкция по тону
    tone_instruction = get_personalized_tone_instruction(
        state=state,
        coach_tone=getattr(profile, "coach_tone", "friendly"),
        patterns=active_patterns,
    )

    return {
        "tone_instruction": tone_instruction,
        "best_time": best_time,
        "active_patterns": active_patterns,
        "has_corrections": has_corrections,
        "focus_areas": getattr(profile, "focus_areas", None) or [],
    }


# =============================================================================
# СБРОС ПЕРСОНАЛИЗАЦИИ (§19.4 — reversible learning)
# =============================================================================

async def reset_personalization(
    session: AsyncSession,
    user_id: int,
) -> None:
    """
    Полный сброс настроек коуча:
    - Очищает coaching_memory (все ключи кроме явных предпочтений пользователя)
    - Сбрасывает UserCoachingProfile к default
    - Удаляет behavior_patterns

    НЕ очищает: onboarding_state, history check-ins, goals, habits.
    """
    from db import coaching_storage as cs
    from db.models import CoachingMemory, BehaviorPattern
    from sqlalchemy import delete

    # Удаляем coaching_memory (ВСЕ — включая explicit, т.к. пользователь явно просит сброс)
    await session.execute(
        delete(CoachingMemory).where(CoachingMemory.user_id == user_id)
    )

    # Удаляем behavior_patterns
    await session.execute(
        delete(BehaviorPattern).where(BehaviorPattern.user_id == user_id)
    )

    # Сбрасываем profile к default
    await cs.update_profile(session, user_id, {
        "coach_tone": "friendly",
        "coaching_mode": "standard",
        "preferred_checkin_time": None,
        "morning_brief_enabled": True,
        "evening_reflection_enabled": True,
        "max_daily_nudges": 3,
        "focus_areas": None,
    })

    logger.info("Personalization reset for user=%s", user_id)
