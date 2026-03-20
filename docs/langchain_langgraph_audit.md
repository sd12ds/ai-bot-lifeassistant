# Аудит использования LangChain / LangGraph / LangSmith в ai-assistant

## 1. Версии пакетов

- **langchain** — 1.2.10
- **langchain-core** — 1.2.17
- **langchain-openai** — 1.1.10
- **langgraph** — 1.0.10
- **langgraph-checkpoint** — 4.0.1
- **langsmith** — 0.7.13

Версии актуальные — используется LangChain v1 + LangGraph v1 (не legacy 0.x).

---

## 2. LangGraph — используется полноценно (⭐⭐⭐⭐ из 5)

### 2.1. Supervisor Graph (центральный оркестратор)

`agents/supervisor.py` (464 строк) — кастомный `StateGraph` с продвинутой маршрутизацией:

- **SupervisorState** — типизированный TypedDict с `Annotated[list[BaseMessage], add_messages]`
- **Топология**: `START → classify_intent → route (conditional_edges) → agent_node → END`
- **8 агентских узлов**: calendar, reminder, nutrition, fitness, coaching, crm, team, assistant
- **5-уровневая классификация** (от дешёвых к дорогим):
  - L0a: Draft Guard (без LLM)
  - L0b: Confirmation Guard (без LLM)
  - L1: force_agent из handler'а
  - L2: Rule-based pre-classifier (keyword matching)
  - L3: Sticky domain (8 мин TTL)
  - L4: LLM-классификатор (gpt-4.1-nano)
- **add_conditional_edges** — маршрутизация по результату classify_intent

**Оценка**: отличное использование. Кастомный граф вместо шаблонного — правильный подход для multi-agent системы с оптимизацией LLM-вызовов.

### 2.2. ReAct-агенты (предсобранные)

Каждый доменный агент создаётся через `create_react_agent()` из `langgraph.prebuilt`:

- **nutrition_agent.py** — 20 tools, ~160 строк промпта
- **fitness_agent.py** — 22 tools, ~200 строк промпта
- **coaching_agent.py** — 47 tools (40+7 context), ~280 строк промпта
- **reminder_agent.py** — 10 tools, ~100 строк промпта
- **calendar_agent.py** — 8 tools
- **assistant_agent.py** — общий агент
- **crm_agent.py** — 7 tools
- **team_agent.py** — без tools

**Итого: ~114 @tool функций** привязанных к LLM через ReAct-паттерн.

### 2.3. Checkpointer (персистентная память)

`db/checkpointer.py` — **AsyncPostgresSaver** (PostgreSQL):

- Полная персистентность диалогов между перезапусками бота
- Fallback на MemorySaver при ошибке подключения
- Уникальные thread_id формата `{user_id}_{agent_type}` — каждый агент хранит свою историю отдельно
- Retry с новым thread_id при ошибках

**Оценка**: грамотная реализация. thread_id-изоляция по агентам — редко встречаемый паттерн, но правильный.

---

## 3. LangChain — используется хорошо (⭐⭐⭐⭐ из 5)

### 3.1. Что используется активно

- **ChatOpenAI** — основная LLM-обёртка (2 инстанса: classifier gpt-4.1-nano + agent gpt-4.1-mini)
- **langchain.tools.tool** — декоратор @tool для всех 114 инструментов
- **langchain_core.messages** — HumanMessage, AIMessage, BaseMessage для коммуникации
- **model_kwargs** — fine-tuning поведения LLM (parallel_tool_calls: False)

### 3.2. Что НЕ используется (но могло бы)

- **Prompt Templates** (ChatPromptTemplate) — промпты написаны как raw strings. Не критично, но templates дали бы версионирование и переиспользование.
- **Output Parsers** — парсинг ответов LLM делается вручную (regex в supervisor). Можно было бы использовать StrOutputParser или PydanticOutputParser.
- **Chains (LCEL)** — не используются. Всё через ainvoke() напрямую. Для текущей архитектуры это нормально.
- **Retrievers / VectorStores** — нет RAG. Вся «база знаний» — в системных промптах и tool-ответах.

---

## 4. LangSmith — НЕ используется (⭐ из 5)

- Пакет langsmith==0.7.13 установлен (зависимость langchain), но:
  - Нет LANGCHAIN_TRACING_V2 в env-переменных
  - Нет LANGCHAIN_API_KEY
  - Нет ни одного прямого импорта langsmith в проектном коде
  - Нет трейсинга, нет дашбордов, нет мониторинга

**Что это значит**: полностью отсутствует observability LLM-вызовов. Нет данных о:
- Latency/стоимости каждого вызова
- Какие tools вызываются и как часто
- Ошибках и hallucinations
- Качестве классификации по доменам

---

## 5. Архитектурная оценка

### Сильные стороны

- **Multi-agent orchestration** через LangGraph StateGraph — профессиональная архитектура
- **5-уровневая классификация** с оптимизацией стоимости (rule-based → sticky → LLM)
- **114 tool-функций** с user_id-привязкой через замыкания — масштабируемо
- **AsyncPostgresSaver** — продовая персистентность, не MemorySaver
- **Изолированные thread_id** по агентам — контекст не смешивается
- **Кастомный session_context** + intent_classifier — гибридный подход (rules + LLM)

### Слабые стороны / точки роста

1. **LangSmith не подключён** — главный пробел. Без трейсинга невозможно оптимизировать промпты и отлаживать проблемы
2. **Нет streaming** — все ответы через ainvoke() (batch). Можно переключить на astream() для UX
3. **Нет Human-in-the-Loop** из LangGraph (interrupt/resume) — draft-механика реализована вручную
4. **Нет LangGraph Store** — долгосрочная память юзера хранится в custom DB, не в нативном store
5. **Нет sub-graphs** — все агенты плоские. Coaching с 47 tools мог бы выиграть от декомпозиции на sub-graphs
6. **Промпты не вынесены** в отдельные файлы/templates — сложно A/B тестировать

### Общая оценка: 7/10

LangGraph используется на уровне выше среднего, LangChain — как базовый фреймворк, LangSmith — полностью отсутствует.

---

*Дата аудита: 2026-03-20*
