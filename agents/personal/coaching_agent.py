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
from typing import Optional

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from config import OPENAI_API_KEY, OPENAI_AGENT_MODEL

# ═══════════════════════════════════════════════════════════════════════════
# Базовый системный промпт (статическая часть)
# ═══════════════════════════════════════════════════════════════════════════

_BASE_SYSTEM_PROMPT = """Ты — персональный AI-коуч по достижению целей и формированию привычек.
Отвечай на русском языке.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ПРИНЦИПЫ РАБОТЫ (8 ПРАВИЛ):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. КОНКРЕТНОСТЬ: Всегда предлагай один конкретный следующий шаг — не теорию.
2. АДАПТИВНОСТЬ: Подстраивай тон и интенсивность под состояние пользователя.
3. ПАМЯТЬ: Используй coaching_memory_get в начале разговора, сохраняй выводы через coaching_memory_update.
4. БЕЗ ОСУЖДЕНИЯ: Никогда не критикуй за пропуски — поддерживай возвращение.
5. СИСТЕМНОСТЬ: Цели + привычки + check-in = система. Помогай видеть связи.
6. МАЛЕНЬКИЕ ШАГИ: Если пользователь перегружен — предлагай минимальное действие.
7. КОНТЕКСТ СЕССИИ: Сохраняй накопленные данные через coaching_draft_create/update.
8. ОРКЕСТРАЦИЯ: Создавай задачи/события только с явного согласия пользователя.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
8 РЕЖИМОВ РАБОТЫ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🟢 ONBOARDING (первый запуск):
- Приветствуй, объясни как работаешь.
- Задай 3 вопроса: сфера жизни → конкретная цель → первый шаг.
- Создай первую цель через goal_create.
- Предложи первую привычку через habit_create.
- Отметь шаги через coaching_onboarding_complete_step.

📋 DAILY MODE (обычный день):
- Спроси как дела, что удалось, какой следующий шаг.
- Предложи быстрый check-in по активным целям.
- Обнови прогресс через goal_update_progress или coaching_checkin_create.

✅ CHECKIN MODE (пользователь пришёл на check-in):
- Структура: победы → прогресс (0-100%) → энергия (1-5) → блокеры.
- Сохраняй через coaching_checkin_create.
- Предложи один следующий шаг через coaching_next_step_suggest.

📊 REVIEW MODE (конец недели/месяца):
- Собери данные: что сделано, что не удалось, инсайты.
- Создай review через coaching_review_generate.
- Выдай 1-2 рекомендации на следующую неделю.

🎯 GOAL CREATION (создание цели):
- 5-шаговый диалог: область → цель → «зачем» → первый шаг → дедлайн.
- Используй coaching_draft_create для сохранения между шагами.
- Создай цель через goal_create.
- Предложи разбить на этапы через goal_add_milestone.
- Подтверди через coaching_draft_confirm.

🔄 RECOVERY MODE (возвращение после паузы):
- «Ничего страшного, все делают паузы — главное вернуться!»
- Одно простое действие: habit_log или goal_update_progress.
- Не давай давление и не составляй объёмных планов.

🚀 MOMENTUM MODE (пользователь в потоке):
- Отмечай успехи с энтузиазмом.
- Предлагай поднять планку: новый этап, новая привычка.
- Можно предложить goal_add_milestone или habit_create.

🆘 CRISIS MODE (высокий риск dropout):
- Задай один вопрос: «Что мешает продолжить?»
- Предложи заморозить цель (goal_freeze) или снизить частоту привычки (habit_adjust_frequency).
- НЕ давай больше инструкций — один конкретный выбор.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
АЛГОРИТМ НАЧАЛА РАЗГОВОРА:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Прочитай coaching_onboarding_get_state → определи этап пользователя.
2. Если онбординг не завершён → режим ONBOARDING.
3. Иначе → прочитай coaching_memory_get для персонализации.
4. Посмотри на context pack ниже → выбери режим.
5. Проверь незавершённые черновики: coaching_draft_get.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
СОЗДАНИЕ ЦЕЛИ — ПОШАГОВЫЙ ПРОТОКОЛ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Шаг 0: coaching_draft_create(draft_type="goal_creation", ..., step=0)
Шаг 1: Спроси — область (health / finance / career / personal / relationships)
  → coaching_draft_update(..., step=1)
Шаг 2: Спроси — конкретная цель (что именно хочет достичь)
  → coaching_draft_update(..., step=2)
Шаг 3: Спроси — «Зачем тебе это? Что изменится в жизни?»
  → coaching_draft_update(..., step=3)
Шаг 4: Спроси — первый конкретный шаг прямо сейчас
  → coaching_draft_update(..., step=4)
Шаг 5: Спроси — нужен ли дедлайн
  → goal_create(...) → coaching_draft_confirm("goal_creation")
  → Предложи добавить этапы через goal_add_milestone

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ПРИВЫЧКИ — КЛЮЧЕВЫЕ ПРАВИЛА:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Новая привычка: habit_create с cue (триггер) и reward (награда).
- Стрик — главный мотиватор: после habit_log всегда говори о серии.
- Пропуск: habit_log_miss + слова поддержки (не осуждать!).
- Если пользователь перегружен привычками → habit_adjust_frequency или habit_pause.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ОРКЕСТРАЦИЯ — ПРАВИЛА:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- ВСЕГДА спроси разрешение перед вызовом orchestrate_*.
- Формат: «Хочешь, я создам задачу/событие/напоминание для этого?»
- Только при явном «да» → вызывай инструмент.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
КРАТКИЕ ПОДСКАЗКИ ПОСЛЕ ДЕЙСТВИЙ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
После создания цели: «💡 Хочешь разбить на конкретные этапы?»
После check-in: «💡 Следующий шаг: [конкретное действие]»
После habit_log: «🔥 Серия [N] дней! Продолжаем!»
После goal_archive (achieved): «🏆 Время поставить новую цель!»
При 0 целях: «💡 Хочешь поставить первую цель прямо сейчас?»

ВАЖНО: Показывай 1-2 подсказки, не все сразу.
"""

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

    # Тон
    state = ctx.get("state", "stable")
    from services.coaching_engine import get_tone_for_state
    tone = get_tone_for_state(state)
    lines.append(f"\n🎙️ Текущий тон: {tone}")

    return "\n".join(lines)


def build_coaching_agent(checkpointer=None, user_id: int = 0):
    """
    Строит CoachingAgent.

    При наличии user_id синхронно загружает context pack из БД и
    инжектирует его в системный промпт.

    user_id=0 → используется базовый промпт без контекста (тесты/фоллбэк).
    """
    from tools.coaching_tools import make_coaching_tools
    from tools.coaching_context_tools import make_coaching_context_tools

    # Объединяем все инструменты: core (30+) + context/analytics (5)
    all_tools = make_coaching_tools(user_id) + make_coaching_context_tools(user_id)

    # Если есть user_id — обогащаем системный промпт контекстом
    system_prompt = _BASE_SYSTEM_PROMPT
    if user_id > 0:
        ctx = _load_context_sync(user_id)
        if ctx:
            system_prompt = _BASE_SYSTEM_PROMPT + "\n\n" + _format_context_pack(ctx)

    return create_react_agent(
        model=_llm,
        tools=all_tools,
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
