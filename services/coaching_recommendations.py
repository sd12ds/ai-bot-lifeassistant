"""
Coaching Recommendations Service — генератор персональных рекомендаций.

Анализирует snapshot + risk scores → создаёт очередь рекомендаций.
Правило: максимум 2 активные рекомендации одновременно (§17.2).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from db import coaching_storage as cs

logger = logging.getLogger(__name__)

# Приоритет по типу рекомендации (1 = наивысший)
_REC_PRIORITIES = {
    "dropout_reactivation": 1,
    "goal_decompose": 2,
    "workload_reduce": 2,
    "habit_rescue": 2,
    "schedule_fix": 3,
    "habit_time_adjust": 3,
    "goal_freeze": 3,
    "weekly_review": 4,
    "habit_new": 4,
    "cross_module_plan": 4,
    "nutrition_fitness_link": 5,
}


async def generate_recommendations(
    session: AsyncSession,
    user_id: int,
) -> list[dict]:
    """
    Анализирует риски и snapshot → генерирует рекомендации → сохраняет в БД.
    Возвращает список созданных рекомендаций.

    Принцип §17.2: максимум 2 одновременно активных рекомендации.
    """
    # Проверяем текущее количество активных рекомендаций
    existing = await cs.get_active_recommendations(session, user_id, limit=10)
    if len(existing) >= 2:
        logger.debug("Уже есть %d активных рекомендаций, пропускаем генерацию", len(existing))
        return []

    snapshot = await cs.get_latest_snapshot(session, user_id)
    risks = await cs.get_risk_scores(session, user_id)
    risk_map = {r.risk_type: r.score for r in risks}

    candidates = []

    # ── Критические сигналы ────────────────────────────────────────────────
    dropout_score = risk_map.get("dropout", 0.0)
    if dropout_score > 0.7:
        candidates.append({
            "rec_type": "dropout_reactivation",
            "title": "Вернись к работе над целями",
            "body": (
                "Ты давно не делал check-in. Одно маленькое действие сейчас "
                "лучше, чем план на «потом». Какая цель требует внимания прямо сейчас?"
            ),
            "priority": 1,
            "action_type": "open_checkin",
        })

    # ── Перегрузка ─────────────────────────────────────────────────────────
    overload_score = risk_map.get("overload", 0.0)
    if overload_score > 0.6 and snapshot and snapshot.tasks_overdue > 5:
        candidates.append({
            "rec_type": "workload_reduce",
            "title": "Слишком много задач — стоит расставить приоритеты",
            "body": (
                f"У тебя {snapshot.tasks_overdue} просроченных задач. "
                "Давай разберём что можно перенести или делегировать."
            ),
            "priority": 2,
            "action_type": "open_goals",
        })

    # ── Зависшие цели ──────────────────────────────────────────────────────
    goal_failure = risk_map.get("goal_failure", 0.0)
    if goal_failure > 0.5:
        stuck = await cs.get_stuck_goals(session, user_id, 7)
        if stuck:
            candidates.append({
                "rec_type": "goal_decompose",
                "title": f"Цель «{stuck[0].title}» требует внимания",
                "body": (
                    "Нет прогресса больше недели. Попробуй разбить на этапы "
                    "или сформулировать один конкретный шаг на сегодня."
                ),
                "priority": 2,
                "action_type": "open_goal",
                "action_payload": {"goal_id": stuck[0].id},
            })

    # ── Привычки под угрозой ───────────────────────────────────────────────
    habit_death = risk_map.get("habit_death", 0.0)
    if habit_death > 0.5:
        at_risk = await cs.get_habits_at_risk(session, user_id, days_no_log=3)
        if at_risk:
            habit_names = ", ".join(h.title for h in at_risk[:2])
            candidates.append({
                "rec_type": "habit_rescue",
                "title": f"Стрик под угрозой: {habit_names}",
                "body": (
                    "Привычка теряет силу без регулярности. "
                    "Залоги прямо сейчас — даже минимальное выполнение считается."
                ),
                "priority": 2,
                "action_type": "open_habits",
            })

    # ── Нет плана на неделю (понедельник без review) ──────────────────────
    latest_review = await cs.get_latest_review(session, user_id, review_type="weekly")
    if latest_review:
        days_since_review = (datetime.utcnow() - latest_review.created_at).days
        if days_since_review > 7:
            candidates.append({
                "rec_type": "weekly_review",
                "title": "Пора сделать недельный обзор",
                "body": "Последний review был больше недели назад. Посмотрим как идут дела?",
                "priority": 4,
                "action_type": "open_review",
            })

    if not candidates:
        return []

    # ── Сортируем по приоритету, берём топ-2 ──────────────────────────────
    candidates.sort(key=lambda x: x["priority"])
    slots_available = 2 - len(existing)
    to_create = candidates[:slots_available]

    created = []
    expires_at = datetime.utcnow() + timedelta(days=3)

    for c in to_create:
        rec = await cs.create_recommendation(
            session=session,
            user_id=user_id,
            rec_type=c["rec_type"],
            title=c["title"],
            body=c.get("body"),
            priority=c["priority"],
            action_type=c.get("action_type"),
            action_payload=c.get("action_payload"),
            source_modules=["coaching"],
            expires_at=expires_at,
        )
        created.append({"id": rec.id, "title": rec.title, "rec_type": rec.rec_type})
        logger.info("Создана рекомендация: [%s] %s для user=%s", c["rec_type"], c["title"], user_id)

    return created
