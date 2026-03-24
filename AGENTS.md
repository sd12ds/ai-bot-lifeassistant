# AGENTS.md — Правила разработки ai-assistant

## Проект

Telegram-бот **Jarvis** — мультиагентный AI-ассистент на LangGraph/LangChain.
Сервер: `77.238.235.171`, папка `/root/ai-assistant`.
Стек: Python 3.12, aiogram 3, LangGraph 1.0, LangChain 1.2, FastAPI, PostgreSQL, Docker Compose.

---

## Архитектура

### Слои (от внешнего к внутреннему)

```
Telegram → aiogram handlers (bot/handlers/)
        → supervisor.py (LangGraph StateGraph)
        → agents/personal/X_agent.py (create_react_agent)
        → tools/X_tools.py (@tool функции)
        → services/ + db/
```

### Supervisor граф (`agents/supervisor.py`)

- Единственное место routing-логики
- 5-уровневая классификация: L0a Draft Guard → L0b Confirm Guard → L1 force_agent → L2 rule-based → L3 sticky → L4 LLM
- Добавление нового домена требует ВСЕХ 5 шагов:
  1. `AgentType` Literal
  2. описание в `_CLASSIFY_PROMPT`
  3. `async def run_X(state)` → `_run_agent(agent, state)`
  4. `builder.add_node("X", run_X)`
  5. маппинг в `add_conditional_edges` + `add_edge(node, END)`
- `stream_message()` — async generator для стриминга токенов (использует `astream(stream_mode="messages")`)
- `process_message()` — batch вариант (используется voice/photo handler'ами)

### Агенты (`agents/personal/X_agent.py`)

- Создаются через `create_react_agent()` из `langgraph.prebuilt`
- Сигнатура: `build_X_agent(checkpointer=None, user_id: int = 0)`
- LLM: `ChatOpenAI` из `config.OPENAI_AGENT_MODEL` с `parallel_tool_calls: False`
- Системный промпт — ТОЛЬКО через `load_prompt("X")` из `utils/prompts.py`
- **НЕ хранить промпт inline в коде агента**

### Tools (`tools/X_tools.py`)

- Декоратор `@tool` из `langchain_core.tools`
- Группируются в `make_X_tools(user_id) -> list[tool]`
- `user_id` привязывается через замыкание
- Возвращают `str` (не dict, не объект)
- Async: все операции с БД через `async/await`

### Промпты (`prompts/`)

- Файлы: `prompts/X.txt` — один файл на агента
- Загрузка: `from utils.prompts import load_prompt` → `load_prompt("X")`
- `lru_cache` — файл читается один раз за жизнь процесса
- Редактировать промпт можно без `--build`, только `docker compose up -d bot`

---

## Handlers (`bot/handlers/`)

- Handler'ы вызывают ТОЛЬКО `process_message(user_id, mode, text)` или `stream_message(...)`
- **НИКАКОЙ routing-логики в handler'ах** — всё в supervisor.py
- **НЕ читать session_context для routing решений** — это зона supervisor.py
- Черновик в агенте — только `set_draft()/clear_draft()` из `bot/core/session_context.py`
- `text.py` использует streaming: placeholder ⌛ → редактирование с курсором ▌ → финал
- Fallback на `process_message` если `stream_message` вернул 0 токенов (L0/L1 без LLM)

---

## База данных

- **НИКОГДА не менять схему** (Alembic миграции, модели SQLAlchemy) без явного согласования
- Checkpointer: `AsyncPostgresSaver` → `db/checkpointer.py` → `get_checkpointer()`
- `thread_id` формат: `{user_id}_{agent_type}` — у каждого агента своя история

---

## Добавление нового агента/домена

1. `agents/personal/X_agent.py` → `build_X_agent(checkpointer, user_id)`
2. `prompts/X.txt` → системный промпт
3. `tools/X_tools.py` → `make_X_tools(user_id)`
4. `bot/core/intent_classifier.py` → `_X_STRONG / _X_NORMAL / _X_ANTI` + `classify_by_rules()`
5. `agents/supervisor.py` → все 5 шагов (AgentType, CLASSIFY_PROMPT, run_X, add_node, add_edge)
6. **НЕ добавлять routing в handlers**

---

## LangSmith (observability)

- Переменные в `.env`: `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY=...`, `LANGSMITH_PROJECT=ai-assistant`
- Трейсинг автоматический — не требует изменений кода агентов
- Статус при старте: `INFO LangSmith трейсинг ВКЛЮЧЕН | проект: ai-assistant`

---

## Деплой

```bash
# Пересборка бота (с изменением кода)
docker compose up -d --build bot

# Только рестарт (изменили промпт в prompts/*.txt)
docker compose up -d bot

# Проверка логов
docker logs ai_bot --tail 20

# НИКОГДА не использовать systemctl restart ai-bot.service
```

---

## Git-workflow

После завершения задачи:
1. `git add .`
2. `git commit -m "краткое описание на русском"`  
   Коммит-сообщение включает `Co-Authored-By: Oz <oz-agent@warp.dev>`
3. `git push`
4. Запись в `docs/changelog.md`: `## [hash] — дата\n📦 описание`

**Не коммитить промежуточные изменения** — только финальный результат задачи.
`docs/changelog.md` не включается в коммит.

---

## Стек версий (актуально)

- langchain 1.2.10 / langchain-core 1.2.17 / langchain-openai 1.1.10
- langgraph 1.0.10 / langgraph-checkpoint 4.0.1
- langsmith 0.7.13
- aiogram 3.x
- FastAPI (сервис `api/`)
- PostgreSQL 16 (Docker)

---

## Что НЕ делать

- ❌ Не трогать `.env`
- ❌ Не менять схему БД без согласования
- ❌ Не добавлять routing в handlers
- ❌ Не хранить промпты inline в коде агентов
- ❌ Не использовать `systemctl restart ai-bot.service`
- ❌ Не вызывать `graph.ainvoke()` напрямую — только через `_run_agent()`
- ❌ Не использовать `MemorySaver` в продакшене — только `AsyncPostgresSaver`
- ❌ Не делать Tools возвращающими dict — только str

---

## Miniapp (`miniapp/`)

Стек: React 19 + Vite 7 + TypeScript 5.9 + Tailwind CSS v4 + Zustand + React Query
Деплой: `cd /root/ai-assistant/miniapp && npm run deploy`
Домен: `https://77-238-235-171.sslip.io`
API: FastAPI на порту 8000, проксируется через nginx `/api/`
