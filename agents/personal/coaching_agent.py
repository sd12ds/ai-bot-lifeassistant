"""
CoachingAgent — персональный AI-коуч для достижения целей и формирования привычек.

Паттерн: build_coaching_agent(checkpointer, user_id) → CompiledGraph
Системный промпт динамически обогащается context pack пользователя.

8 режимов работы:
    onboarding    — первое знакомство, создание первой цели/привычки
    daily_mode    — ежедневные check-in и обновления прогресса
    checkin_mode  — структурированный check-in (прогресс, энергия, блокеры)
    review_mode   — недельный/месячный обзор результатов
    goal_creation — создание новой цели через 5-шаговый диалог
    recovery_mode — возвращение после паузы/срыва
    momentum_mode — пользователь в потоке, предлагаем новые вызовы
    crisis_mode   — высокий риск dropout, упрощённый сценарий
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from langchain_openai import ChatOpenAI
from utils.prompts import load_prompt
from langgraph.prebuilt import create_react_agent

from config import OPENAI_API_KEY, OPENAI_AGENT_MODEL

# ═══════════════════════════════════════════════════════════════════════════
logger = logging.getLogger(__name__)

_GOAL_KEYWORDS = frozenset({
    "\u0446\u0435\u043b", "goal", "\u044d\u0442\u0430\u043f", "milestone", "\u043f\u0440\u043e\u0433\u0440\u0435\u0441\u0441", "\u0434\u0435\u0434\u043b\u0430\u0439\u043d", "\u0434\u043e\u0441\u0442\u0438\u0436",
    "\u0437\u0430\u043c\u043e\u0440\u043e\u0437\u0438", "\u0430\u0440\u0445\u0438\u0432\u0438\u0440", "\u0432\u043e\u0437\u043e\u0431\u043d\u043e\u0432\u0438", "\u043f\u043b\u0430\u043d \u0446\u0435\u043b",
})
_HABIT_KEYWORDS = frozenset({
    "\u043f\u0440\u0438\u0432\u044b\u0447\u043a", "habit", "\u0441\u0435\u0440\u0438\u044f", "streak", "\u0442\u0440\u0435\u043a\u0435\u0440", "\u0435\u0436\u0435\u0434\u043d\u0435\u0432\u043d",
    "\u043f\u0440\u043e\u043f\u0443\u0441\u0442\u0438\u043b", "\u043f\u0440\u043e\u043f\u0443\u0441\u043a", "\u0448\u0430\u0431\u043b\u043e\u043d \u043f\u0440\u0438\u0432\u044b\u0447",
})
_ANALYSIS_KEYWORDS = frozenset({
    "\u0447\u0435\u043a\u0438\u043d", "check-in", "checkin", "\u043e\u0431\u0437\u043e\u0440", "review",
    "\u0438\u0442\u043e\u0433", "\u0430\u043d\u0430\u043b\u0438\u0437", "\u0438\u043d\u0441\u0430\u0439\u0442", "insight",
})


def _classify_coaching_domain(text: str) -> str:
    t = text.lower()
    has_goals = any(kw in t for kw in _GOAL_KEYWORDS)
    has_habits = any(kw in t for kw in _HABIT_KEYWORDS)
    has_analysis = any(kw in t for kw in _ANALYSIS_KEYWORDS)
    if has_goals and not has_habits:
        return "goals"
    if has_habits and not has_goals:
        return "habits"
    if has_analysis and not has_goals and not has_habits:
        return "analysis"
    return "general"


def _filter_tools_by_domain(all_tools: list, domain: str) -> list:
    if domain == "goals":
        return [t for t in all_tools
                if not t.name.startswith("habit_") and t.name != "coaching_template_apply"]
    if domain == "habits":
        return [t for t in all_tools if not t.name.startswith("goal_")]
    if domain == "analysis":
        return [t for t in all_tools if not (
            t.name.startswith("goal_") or
            t.name.startswith("habit_") or
            t.name.startswith("orchestrate_")
        )]
    return all_tools
# Базовый системный промпт (статическая часть)
# ═══════════════════════════════════════════════════════════════════════════

_BASE_SYSTEM_PROMPT = load_prompt("coaching")

# ═══════════════════════════════════════════════════════════════════════════
# LLM
# ═══════════════════════════════════════════════════════════════════════════

_llm = ChatOpenAI(
    model=OPENAI_AGENT_MODEL,
    api_key=OPENAI_API_KEY,
    temperature=0.1,  # Небольшая вариативность для коучинговых ответов
    model_kwargs={"parallel_tool_calls": False},
)


def _format_context_pack(ctx: dict) -> str:
    """Форматирует context pack для инъекции в системный промпт."""
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "ТЕКУЩИЙ КОНТЕКСТ ПОЛЬЗОВАТЕЛЯ:",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🧠 Состояние: {ctx.get('state', 'stable').upper()} | Скор: {ctx.get('score', 75)}/100",
    ]

    stuck = ctx.get("stuck_goals_count", 0)
    streak_risk = ctx.get("streak_at_risk_count", 0)
    if stuck > 0:
        lines.append(f"⚠️ Застрявших целей: {stuck}")
    if streak_risk > 0:
        lines.append(f"⚠️ Привычек под угрозой: {streak_risk}")

    goals = ctx.get("goals_summary", [])
    if goals:
        lines.append(f"\n🎯 Активные цели ({len(goals)}):")
        lines.extend(goals)
    else:
        lines.append("\n🎯 Активных целей нет")

    habits = ctx.get("habits_summary", [])
    if habits:
        lines.append(f"\n🔁 Привычки ({len(habits)}):")
        lines.extend(habits)

    recs = ctx.get("recommendations", [])
    if recs:
        lines.append(f"\n📌 Топ рекомендации:")
        lines.extend(recs)

    memories = ctx.get("memory", [])
    if memories:
        lines.append(f"\n🧠 Память о пользователе:")
        lines.extend(memories)

    # Персонализированный тон — приоритет у tone_instruction из context_pack (Phase 8)
    tone_instruction = ctx.get("tone_instruction")
    state = ctx.get("state", "stable")
    if tone_instruction:
        lines.append(f"\n🎙️ Инструкция по тону: {tone_instruction}")
    else:
        from services.coaching_engine import get_tone_for_state
        tone = get_tone_for_state(state)
        lines.append(f"\n🎙️ Текущий тон: {tone}")

    # Активные паттерны (если есть)
    patterns = ctx.get("active_patterns", [])
    if patterns:
        lines.append(f"\n🧠 Активные паттерны: {', '.join(patterns)}")

    # Фокусные области из профиля
    focus = ctx.get("focus_areas", [])
    if focus:
        lines.append(f"\n📍 Фокус пользователя: {', '.join(focus)}")

    # Топовый кросс-модульный вывод (Phase 9) — системный взгляд через модули
    cross_module = ctx.get("cross_module_top")
    if cross_module:
        lines.append(f"\n🔍 Кросс-модульный вывод: {cross_module}")

    return "\n".join(lines)


def build_coaching_agent(checkpointer=None, user_id: int = 0, message_text: str = ""):
    """
    Строит CoachingAgent.

    При наличии user_id синхронно загружает context pack из БД и
    инжектирует его в системный промпт.

    user_id=0 → используется базовый промпт без контекста (тесты/фоллбэк).
    """
    from tools.coaching_tools import make_coaching_tools
    from tools.coaching_context_tools import make_coaching_context_tools

    all_tools = make_coaching_tools(user_id) + make_coaching_context_tools(user_id)
    domain = _classify_coaching_domain(message_text)
    filtered = _filter_tools_by_domain(all_tools, domain)
    if domain != "general":
        logger.debug("coaching tools: %d->%d (domain=%s)", len(all_tools), len(filtered), domain)

    # Если есть user_id — обогащаем системный промпт контекстом
    system_prompt = _BASE_SYSTEM_PROMPT
    if user_id > 0:
        ctx = _load_context_sync(user_id)
        if ctx:
            system_prompt = _BASE_SYSTEM_PROMPT + "\n\n" + _format_context_pack(ctx)

    return create_react_agent(
        model=_llm,
        tools=filtered,
        prompt=system_prompt,
        checkpointer=checkpointer,
    )


def _load_context_sync(user_id: int) -> Optional[dict]:
    """
    Синхронная обёртка для загрузки context pack.

    Запускает async get_context_pack через asyncio.
    Используется только при инициализации агента.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # В async-контексте (например FastAPI/aiogram) — создаём задачу
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(_run_context_pack_in_new_loop, user_id)
                return future.result(timeout=5)
        else:
            return loop.run_until_complete(_async_load_context(user_id))
    except Exception:
        # При ошибке загрузки контекста — работаем без него
        return None


def _run_context_pack_in_new_loop(user_id: int) -> Optional[dict]:
    """Запускает async функцию в новом event loop (для thread pool)."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_async_load_context(user_id))
    finally:
        loop.close()


async def _async_load_context(user_id: int) -> Optional[dict]:
    """Async загрузка context pack из БД."""
    try:
        from db.session import get_async_session
        from services.coaching_engine import get_context_pack
        async with get_async_session() as session:
            return await get_context_pack(session, user_id)
    except Exception:
        return None
