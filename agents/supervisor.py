"""
Supervisor — центральный LangGraph граф маршрутизации запросов.
Принимает сообщение пользователя + его режим (personal/business),
определяет нужного агента и делегирует выполнение.

Схема:
  START → classify_intent → route (conditional) → agent → END
"""
from __future__ import annotations

import logging
from typing import Annotated, Literal

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from config import OPENAI_API_KEY, OPENAI_LLM_MODEL
from db.checkpointer import get_checkpointer

logger = logging.getLogger(__name__)

# ── Типы агентов ──────────────────────────────────────────────────────────────
AgentType = Literal["calendar", "reminder", "nutrition", "fitness", "crm", "team", "assistant"]

# Агенты, доступные только в бизнес-режиме
_BUSINESS_ONLY_AGENTS: set[AgentType] = {"crm", "team"}

# Память последнего использованного агента на пользователя (для сохранения контекста)
_last_agent_per_user: dict[int, str] = {}


# ── Состояние графа ───────────────────────────────────────────────────────────

class SupervisorState(TypedDict):
    """Состояние, передаваемое между узлами графа."""
    messages: Annotated[list[BaseMessage], add_messages]  # История сообщений
    user_mode: str        # 'personal' | 'business'
    user_id: int          # Telegram user_id
    agent_type: str       # Определённый тип агента
    response: str         # Финальный ответ


# ── Классификатор намерений ───────────────────────────────────────────────────

_classifier_llm = ChatOpenAI(
    model=OPENAI_LLM_MODEL,
    api_key=OPENAI_API_KEY,
    temperature=0,
)

_CLASSIFY_PROMPT = """Определи тип агента для обработки запроса пользователя.
Ответь ОДНИМ словом из списка: reminder, nutrition, fitness, crm, team, assistant

ВАЖНО: если запрос является продолжением или уточнением предыдущей темы
(например: "подробнее", "ещё", "а что по ценам?", "расскажи больше", "а как готовить?", "сравни"),
и указан предыдущий агент — выбери ТОГО ЖЕ агента.
Предыдущий агент: {last_agent}

reminder — задачи, напоминания, записи (к врачу, мастеру, на процедуры), встречи, события, расписание, перенос встреч, календарь — любые действия с датой и/или временем
nutrition — еда, питание, калории, КБЖУ, приём пищи, вода, диета, продукты, перекус, завтрак, обед, ужин, сколько съел, что я ел, выпил воды, EWA, bodybox, протеин, зефир, батончик, вафли, какао, состав продукта, польза продукта, ева, эва, бодибокс, боди бокс, зерозефир, зеро зефир, суп ева, коктейль ева
fitness — тренировка, упражнения, жим, присед, тяга, подтягивания, бег, пробежка, пробежал, прошёл, шаги, велосипед, плавание, кардио, зал, качалка, фитнес, спорт, замеры тела, вес, взвесился, мышцы, подходы, повторения, workout, набор массы, похудение, программа тренировок, streak, статистика тренировок, сколько тренировок
crm — клиенты, контакты, сделки, продажи (только бизнес-режим)
team — команда, сотрудники, совместные события (только бизнес-режим)
assistant — всё остальное (вопросы, разговор, объяснения, помощь без даты)

Режим пользователя: {mode}
Запрос: {text}

Ответ (одно слово):"""


async def classify_intent(state: SupervisorState) -> SupervisorState:
    """Определяет тип агента по тексту последнего сообщения."""
    # Если agent_type уже задан (force_agent из обработчика) — пропускаем классификацию
    if state.get("agent_type"):
        forced = state["agent_type"]
        _last_agent_per_user[state["user_id"]] = forced
        logger.info("Пользователь %s → force_agent=%s (пропуск классификации)", state["user_id"], forced)
        return state

    # Берём текст последнего сообщения от пользователя
    last_human = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        None,
    )
    if not last_human:
        return {**state, "agent_type": "assistant"}

    user_text = last_human.content
    # Получаем последний использованный агент для контекста
    last_agent = _last_agent_per_user.get(state["user_id"], "нет (первое сообщение)")
    prompt = _CLASSIFY_PROMPT.format(
        mode=state["user_mode"],
        text=user_text,
        last_agent=last_agent,
    )

    response = await _classifier_llm.ainvoke([HumanMessage(content=prompt)])
    agent_type = response.content.strip().lower()

    # Если режим personal, но запросили бизнес-агента — переключаем на ассистента
    if agent_type in _BUSINESS_ONLY_AGENTS and state["user_mode"] != "business":
        logger.info(
            "Агент '%s' недоступен в режиме personal, переключаем на assistant", agent_type
        )
        agent_type = "assistant"

    # Защита от неожиданных значений
    # Google Calendar отключён — перенаправляем в reminder
    if agent_type == "calendar":
        agent_type = "reminder"

    if agent_type not in {"calendar", "reminder", "nutrition", "fitness", "crm", "team", "assistant"}:
        agent_type = "assistant"

    # Сохраняем выбранный агент для контекста следующего сообщения
    _last_agent_per_user[state["user_id"]] = agent_type
    logger.info("Пользователь %s, режим=%s → агент=%s (пред: %s)", state["user_id"], state["user_mode"], agent_type, last_agent)
    return {**state, "agent_type": agent_type}


def route_to_agent(state: SupervisorState) -> str:
    """Условное ребро: направляет к нужному узлу на основе agent_type."""
    return state["agent_type"]


# ── Узлы-агенты ───────────────────────────────────────────────────────────────

async def _run_agent(agent_graph, state: SupervisorState) -> SupervisorState:
    """Общий запуск агента — передаёт ТОЛЬКО новое сообщение.
    Каждый агент хранит свою историю в отдельном checkpoint (thread_id с суффиксом агента).
    """
    # Уникальный thread_id для каждого типа агента — чтобы checkpoints не смешивались
    agent_thread_id = f"{state['user_id']}_{state['agent_type']}"
    config = {"configurable": {"thread_id": agent_thread_id}}

    # Передаём только последнее сообщение пользователя — историю берёт checkpointer
    last_human = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        None,
    )
    input_msgs = [last_human] if last_human else state["messages"]

    try:
        result = await agent_graph.ainvoke(
            {"messages": input_msgs},
            config=config,
        )
    except (ValueError, Exception) as exc:
        # Битая история — повтор с чистым thread
        import logging
        logging.getLogger(__name__).warning("Agent error (retrying without history): %s", exc)
        result = await agent_graph.ainvoke(
            {"messages": input_msgs},
            config={"configurable": {"thread_id": f"{agent_thread_id}_retry_{__import__('time').time():.0f}"}},
        )
    # Берём текст последнего AI-сообщения как финальный ответ
    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
    response_text = ai_messages[-1].content if ai_messages else "Не смог обработать запрос."
    return {**state, "response": response_text, "messages": result["messages"]}


# ── Фабрика графа Supervisor ──────────────────────────────────────────────────

def build_supervisor(
    calendar_agent,
    reminder_agent,
    assistant_agent,
    crm_agent=None,
    team_agent=None,
) -> StateGraph:
    """
    Собирает граф Supervisor из готовых агентов.
    Бизнес-агенты опциональны — если не переданы, запросы к ним
    уходят в assistant.
    """
    builder = StateGraph(SupervisorState)

    # Узел классификации
    builder.add_node("classify_intent", classify_intent)

    # ── Узлы-агенты ──
    async def run_calendar(state):
        # Google Calendar отключён — делегируем в reminder
        from agents.personal.reminder_agent import build_reminder_agent
        agent = build_reminder_agent(checkpointer=get_checkpointer(), user_id=state["user_id"])
        return await _run_agent(agent, state)

    async def run_reminder(state):
        # Динамически создаём reminder-агента под user_id
        from agents.personal.reminder_agent import build_reminder_agent
        agent = build_reminder_agent(checkpointer=get_checkpointer(), user_id=state["user_id"])
        return await _run_agent(agent, state)

    async def run_nutrition(state):
        # Динамически создаём nutrition-агента под user_id
        from agents.personal.nutrition_agent import build_nutrition_agent
        from bot.nutrition_context import format_context_for_agent
        agent = build_nutrition_agent(checkpointer=get_checkpointer(), user_id=state["user_id"])

        # Инжектируем контекст draft в сообщение пользователя (если есть активный draft)
        draft_ctx = format_context_for_agent(state["user_id"])
        if draft_ctx:
            # Обогащаем последнее HumanMessage контекстом draft
            msgs = list(state["messages"])
            for i in range(len(msgs) - 1, -1, -1):
                if isinstance(msgs[i], HumanMessage):
                    original = msgs[i].content
                    msgs[i] = HumanMessage(content=f"{draft_ctx}\n\n{original}")
                    break
            state = {**state, "messages": msgs}

        return await _run_agent(agent, state)


    async def run_fitness(state):
        # Динамически создаём fitness-агента под user_id
        from agents.personal.fitness_agent import build_fitness_agent
        agent = build_fitness_agent(checkpointer=get_checkpointer(), user_id=state["user_id"])
        return await _run_agent(agent, state)
    async def run_assistant(state):
        return await _run_agent(assistant_agent, state)

    builder.add_node("calendar", run_calendar)
    builder.add_node("reminder", run_reminder)
    builder.add_node("nutrition", run_nutrition)
    builder.add_node("fitness", run_fitness)
    builder.add_node("assistant", run_assistant)

    # Бизнес-агенты (если переданы — используем, иначе маршрутируем в assistant)
    if crm_agent:
        async def run_crm(state):
            return await _run_agent(crm_agent, state)
        builder.add_node("crm", run_crm)
    else:
        builder.add_node("crm", run_assistant)  # Fallback

    if team_agent:
        async def run_team(state):
            return await _run_agent(team_agent, state)
        builder.add_node("team", run_team)
    else:
        builder.add_node("team", run_assistant)  # Fallback

    # ── Рёбра ──
    builder.add_edge(START, "classify_intent")
    builder.add_conditional_edges(
        "classify_intent",
        route_to_agent,
        {
            "calendar": "calendar",
            "reminder": "reminder",
            "nutrition": "nutrition",
            "fitness": "fitness",
            "crm": "crm",
            "team": "team",
            "assistant": "assistant",
        },
    )
    # Все агенты завершаются
    for node in ["calendar", "reminder", "nutrition", "fitness", "crm", "team", "assistant"]:
        builder.add_edge(node, END)

    return builder


# ── Синглтон Supervisor ───────────────────────────────────────────────────────

_supervisor_graph = None


def get_supervisor():
    """Возвращает скомпилированный граф Supervisor (создаётся один раз)."""
    global _supervisor_graph
    if _supervisor_graph is None:
        _supervisor_graph = _create_supervisor()
    return _supervisor_graph


def _create_supervisor():
    """Инициализирует все агенты и собирает Supervisor граф."""
    from agents.personal.calendar_agent import build_calendar_agent
    from agents.personal.assistant_agent import build_assistant_agent
    from agents.personal.reminder_agent import build_reminder_agent
    from agents.business.crm_agent import build_crm_agent
    from agents.business.team_agent import build_team_agent

    checkpointer = get_checkpointer()

    calendar = build_calendar_agent(checkpointer=checkpointer)
    assistant = build_assistant_agent(checkpointer=checkpointer)
    # reminder-агент создаём динамически под конкретного пользователя в run_reminder
    crm = build_crm_agent(checkpointer=checkpointer)
    team = build_team_agent(checkpointer=checkpointer)

    builder = build_supervisor(
        calendar_agent=calendar,
        reminder_agent=None,
        assistant_agent=assistant,
        crm_agent=crm,
        team_agent=team,
    )
    return builder.compile()


async def process_message(
    user_id: int,
    user_mode: str,
    text: str,
    force_agent: str | None = None,
) -> str:
    """
    Точка входа для обработки сообщения пользователя.

    Args:
        user_id: Telegram user_id
        user_mode: 'personal' | 'business'
        text: текст сообщения
        force_agent: если задан — принудительно направляет в указанного агента
                     (пропускает классификацию). Используется при активном draft.

    Возвращает текстовый ответ агента.
    """
    supervisor = get_supervisor()
    state: SupervisorState = {
        "messages": [HumanMessage(content=text)],
        "user_mode": user_mode,
        "user_id": user_id,
        "agent_type": force_agent or "",
        "response": "",
    }
    result = await supervisor.ainvoke(
        state,
        config={"configurable": {"thread_id": str(user_id)}},
    )
    return result.get("response", "Не смог обработать запрос.")
