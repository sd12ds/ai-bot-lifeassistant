"""
Coaching Context Tools — аналитические инструменты для агента.

Дают агенту возможность получать текущий контекст, риски, паттерны
и аналитику по целям/привычкам без бизнес-логики.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from langchain.tools import tool
from sqlalchemy import select, func

from db.session import get_async_session
from db import coaching_storage as cs
from db.models import HabitLog, GoalCheckin
from services.coaching_cross_module import (
    collect_module_signals,
    generate_cross_module_inferences,
    run_cross_module_analysis,
)
from services.coaching_engine import (
    compute_user_state,
    compute_risk_scores,
    get_context_pack,
)


def make_coaching_context_tools(user_id: int) -> list:
    """Создаёт аналитические инструменты, привязанные к user_id."""

    @tool
    async def coaching_context_snapshot_get() -> str:
        """
        Получить текущий снимок контекста пользователя:
        состояние (momentum/stable/overload/recovery/risk), скор, статистику
        привычек и целей на сегодня.
        """
        async with get_async_session() as session:
            snapshot = await cs.get_latest_snapshot(session, user_id)
            if not snapshot:
                return "Снимок контекста ещё не сформирован. Запроси update_daily_snapshot."

            return json.dumps({
                "state": snapshot.overall_state,
                "score": snapshot.score,
                "date": str(snapshot.snapshot_date),
                "tasks_overdue": snapshot.tasks_overdue,
                "habits_done_today": snapshot.habits_done_today,
                "habits_total_today": snapshot.habits_total_today,
                "stuck_goals": snapshot.stuck_goals,
                "streak_at_risk": snapshot.streak_at_risk,
                "calendar_events_today": snapshot.calendar_events_today,
            }, ensure_ascii=False)

    @tool
    async def coaching_risk_assess() -> str:
        """
        Оценить текущие риски пользователя:
        dropout, overload, goal_failure, habit_death.
        Threshold HIGH RISK: > 0.7
        """
        async with get_async_session() as session:
            risks = await compute_risk_scores(session, user_id)
            lines = ["📊 Оценка рисков:"]
            for risk_type, score in sorted(risks.items(), key=lambda x: -x[1]):
                level = "🔴 ВЫСОКИЙ" if score > 0.7 else ("🟡 СРЕДНИЙ" if score > 0.4 else "🟢 НИЗКИЙ")
                lines.append(f"  {level} {risk_type}: {score:.2f}")
            return "\n".join(lines)

    @tool
    async def coaching_behavior_patterns_get() -> str:
        """
        Получить поведенческие паттерны и долгосрочную память коуча о пользователе.
        Используй для персонализации советов.
        """
        async with get_async_session() as session:
            patterns = await cs.get_behavior_patterns(session, user_id)
            memories = await cs.get_memory(session, user_id, top_n=10)

            result = {"patterns": [], "memory": []}
            for p in patterns:
                result["patterns"].append({
                    "type": p.pattern_type,
                    "description": p.description,
                    "frequency": p.frequency,
                })
            for m in memories:
                result["memory"].append({
                    "key": m.key,
                    "value": m.value,
                    "confidence": m.confidence,
                    "is_explicit": m.is_explicit,
                })
            return json.dumps(result, ensure_ascii=False)

    @tool
    async def coaching_progress_analytics(days: int = 30) -> str:
        """
        Аналитика прогресса по целям за последние N дней.
        days — период в днях (по умолчанию 30).
        Показывает: активные цели, прогресс, check-in история.
        """
        async with get_async_session() as session:
            goals = await cs.get_goals(session, user_id, status="active")
            since = datetime.utcnow() - timedelta(days=days)

            result = []
            for g in goals:
                # Последние check-ins
                checkins = await cs.get_recent_goal_checkins(session, g.id, user_id, limit=5)
                avg_energy = (
                    sum(c.energy_level for c in checkins if c.energy_level) / len(checkins)
                    if checkins else None
                )
                result.append({
                    "id": g.id,
                    "title": g.title,
                    "progress_pct": g.progress_pct,
                    "priority": g.priority,
                    "is_frozen": g.is_frozen,
                    "checkins_count": len(checkins),
                    "avg_energy": round(avg_energy, 1) if avg_energy else None,
                    "why_statement": g.why_statement,
                })
            return json.dumps(result, ensure_ascii=False)

    @tool
    async def coaching_habit_analytics(days: int = 30) -> str:
        """
        Аналитика привычек за последние N дней.
        Показывает completion rate, стрики, паттерны выполнения.
        """
        async with get_async_session() as session:
            habits = await cs.get_habits(session, user_id, is_active=True)
            since = datetime.utcnow() - timedelta(days=days)

            result = []
            for h in habits:
                # Количество логов за период
                log_count_result = await session.execute(
                    select(func.count(HabitLog.id)).where(
                        HabitLog.habit_id == h.id,
                        HabitLog.logged_at >= since,
                    )
                )
                log_count = log_count_result.scalar_one() or 0
                completion_rate = log_count / days if days > 0 else 0

                result.append({
                    "id": h.id,
                    "title": h.title,
                    "area": h.area,
                    "current_streak": h.current_streak,
                    "longest_streak": h.longest_streak,
                    "total_completions": h.total_completions,
                    "completion_rate_30d": round(min(1.0, completion_rate), 2),
                    "difficulty": h.difficulty,
                    "goal_id": h.goal_id,
                })
            return json.dumps(result, ensure_ascii=False)

    @tool
    async def coaching_cross_module_signals_get() -> str:
        """
        Получить сигналы из всех модулей: Tasks, Calendar, Fitness, Nutrition, Reminders.
        Используй для понимания общей картины пользователя перед советом.
        """
        async with get_async_session() as session:
            signals = await collect_module_signals(session, user_id)
            return json.dumps(signals, ensure_ascii=False, default=str)

    @tool
    async def coaching_cross_module_analyze() -> str:
        """
        Запустить кросс-модульный анализ: собрать сигналы, сгенерировать выводы
        и сохранить рекомендации. Возвращает выводы с типами, severity и описанием.
        Используй когда нужно объяснить пользователю «почему буксуешь» целостно.
        """
        async with get_async_session() as session:
            # Получаем текущее состояние пользователя
            from services.coaching_engine import compute_user_state
            state_data = await compute_user_state(session, user_id)
            state = state_data.get("state", "stable")

            result = await run_cross_module_analysis(session, user_id, state)

            inferences = result.get("inferences", [])
            if not inferences:
                return "Кросс-модульных проблем не обнаружено — всё сбалансировано."

            lines = ["🔍 Кросс-модульный анализ:"]
            for inf in inferences:
                severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
                    inf.get("severity", "medium"), "🟡"
                )
                lines.append(
                    f"{severity_icon} [{inf['type']}] {inf['title']}\n"
                    f"  {inf['description']}"
                )
            if result.get("saved_recommendations"):
                lines.append(f"\n💡 Сохранено рекомендаций: {result['saved_recommendations']}")
            return "\n\n".join(lines)

    return [
        coaching_context_snapshot_get,
        coaching_risk_assess,
        coaching_behavior_patterns_get,
        coaching_progress_analytics,
        coaching_habit_analytics,
        coaching_cross_module_signals_get,
        coaching_cross_module_analyze,
    ]
