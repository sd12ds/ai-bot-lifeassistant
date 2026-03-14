# Coaching Module — Full Test Architecture & Test Implementation Plan

**Версия**: 1.0  
**Статус**: Рабочий документ  
**Уровень**: Senior QA Architect + Backend Architect + Conversational AI Systems Architect  
**Язык**: Русский  
**Модуль**: Coaching (цели, привычки, check-in, weekly review, AI-коуч, cross-module)

---

## Содержание

1. [Test Strategy — Стратегия тестирования](#1-test-strategy)
2. [Test Pyramid и Test Matrix](#2-test-pyramid--test-matrix)
3. [Scope of Testing](#3-scope-of-testing)
4. [Test Layers — Архитектура слоёв тестирования](#4-test-layers)
5. [Test Environments](#5-test-environments)
6. [Test Data Strategy](#6-test-data-strategy)
7. [Fixtures и Factories](#7-fixtures-и-factories)
8. [Init / Bootstrap Tests](#8-init--bootstrap-tests)
9. [Unit Tests](#9-unit-tests)
10. [Integration Tests](#10-integration-tests)
11. [API Tests](#11-api-tests)
12. [Chat / Agent / Supervisor Tests](#12-chat--agent--supervisor-tests)
13. [Command / Shortcut / Telegram UX Tests](#13-command--shortcut--telegram-ux-tests)
14. [E2E Tests](#14-e2e-tests)
15. [Mini App Tests](#15-mini-app-tests)
16. [Auth / Telegram initData Tests](#16-auth--telegram-initdata-tests)
17. [Reminder / Scheduler Tests](#17-reminder--scheduler-tests)
18. [Cross-Module Tests](#18-cross-module-tests)
19. [Failure / Edge Case / Resilience Tests](#19-failure--edge-case--resilience-tests)
20. [Observability / Logging / Debug Tests](#20-observability--logging--debug-tests)
21. [CI Pipeline / Quality Gates](#21-ci-pipeline--quality-gates)
22. [Rollout Safety / Regression Plan](#22-rollout-safety--regression-plan)
23. [Definition of Done for QA](#23-definition-of-done-for-qa)
24. [Phased Implementation Plan](#24-phased-implementation-plan)

---

## 1. Test Strategy

### 1.1 Философия тестирования Coaching

Coaching — это не CRUD-модуль. Это **conversational AI-система с памятью, контекстом и проактивной логикой**. Тестировать его как набор REST-ручек — принципиальная ошибка. Тестирование Coaching должно отвечать на вопрос:

> **«Ведёт ли себя система как живой AI-коуч — с правильной маршрутизацией, пониманием контекста, корректными инсайтами, устойчивостью к сбоям и понятными ответами пользователю?»**

Три оси тестирования Coaching:

1. **Correctness** — правильное поведение на типовых и граничных вводах
2. **Resilience** — устойчивость к ошибкам, отказам, неоднозначным данным
3. **Coherence** — связность диалога, контекст между сообщениями, адекватность AI-ответов

### 1.2 Ключевые риски, которые покрывают тесты

| Риск | Последствие | Покрывающие тесты |
|------|-------------|-------------------|
| Supervisor маршрутизирует coaching-запрос в другой агент | Пользователь не получает coaching-ответ | Supervisor routing tests |
| LLM возвращает технический мусор или JSON в ответе | Плохой UX | Agent response format tests |
| Цель создана в чате, но не сохранилась в БД | Данные потеряны | Storage integration tests |
| Привычка залогирована, но streak не обновился | Неправильная аналитика | Unit + storage tests |
| Cross-module данные не читаются при weekly review | Неполный AI-анализ | Cross-module tests |
| initData не проверяется → чужие данные доступны | Security breach | Auth/initData tests |
| Reminder отправлен дважды | Раздражение пользователя | Scheduler idempotency tests |
| Telegram callback устарел → FSM в неконсистентном состоянии | Зависший диалог | Stale callback tests |
| Mini App показывает данные со старой схемой | Frontend crash | Contract tests |

### 1.3 Принципы тестовой архитектуры

- **Изоляция**: каждый тест независим. Shared state между тестами запрещён.
- **Reproducibility**: тесты детерминированы. LLM и внешние сервисы — за фейками.
- **Granularity**: каждый слой тестируется отдельно. E2E — только для критичных сценариев.
- **Coverage by risk**: приоритет отдаётся высокорисковым путям, а не 100% line coverage.
- **Golden conversations**: для AI-поведения используются задокументированные эталонные диалоги.

---

## 2. Test Pyramid / Test Matrix

### 2.1 Test Pyramid для Coaching

```
              ┌────────────────────┐
              │   E2E / Smoke      │  ← 5% — критичные сценарии, медленно
              ├────────────────────┤
              │  Mini App / UI     │  ← 10% — React компоненты, hooks
              ├────────────────────┤
              │  API / Contract    │  ← 15% — FastAPI endpoints, auth
              ├────────────────────┤
              │  Chat / Agent      │  ← 20% — supervisor, tools, диалоги
              ├────────────────────┤
              │    Integration     │  ← 20% — DB, service, repo слои
              ├────────────────────┤
              │      Unit          │  ← 30% — бизнес-логика, helpers
              └────────────────────┘
```

### 2.2 Test Matrix — матрица покрытия

| Компонент | Unit | Integration | API | Chat | E2E | Mini App |
|-----------|------|-------------|-----|------|-----|----------|
| `db/models.py` (Coaching models) | ✓ | ✓ | — | — | — | — |
| `db/coaching_storage.py` | ✓ | ✓ | — | — | — | — |
| `services/coaching_engine.py` | ✓ | ✓ | — | — | — | — |
| `services/coaching_analytics.py` | ✓ | ✓ | ✓ | — | — | — |
| `services/coaching_personalization.py` | ✓ | ✓ | ✓ | — | — | — |
| `services/coaching_recommendations.py` | ✓ | ✓ | — | — | — | — |
| `services/coaching_cross_module.py` | ✓ | ✓ | ✓ | — | ✓ | — |
| `services/coaching_proactive.py` | ✓ | ✓ | — | — | ✓ | — |
| `agents/personal/coaching_agent.py` | ✓ | ✓ | — | ✓ | ✓ | — |
| `agents/supervisor.py` (coaching route) | — | ✓ | — | ✓ | — | — |
| `api/routers/coaching.py` | — | — | ✓ | — | ✓ | — |
| `api/deps.py` (auth/initData) | ✓ | ✓ | ✓ | — | — | — |
| `bot/handlers/coaching_handler.py` | — | ✓ | — | ✓ | ✓ | — |
| `bot/flows/coaching_flows.py` | ✓ | ✓ | — | ✓ | — | — |
| `bot/handlers/text.py` (routing) | — | ✓ | — | ✓ | — | — |
| `bot/states.py` (FSM) | ✓ | ✓ | — | ✓ | — | — |
| Mini App `CoachingDashboard` | — | — | — | — | — | ✓ |
| Mini App `GoalsPage` | — | — | — | — | — | ✓ |
| Mini App `HabitsPage` | — | — | — | — | — | ✓ |
| Mini App `CheckInPage` | — | — | — | — | — | ✓ |
| Mini App `api/coaching.ts` | — | — | ✓ | — | — | ✓ |
| APScheduler coaching jobs | ✓ | ✓ | — | — | ✓ | — |

---

## 3. Scope of Testing

### 3.1 В скоупе

**Backend:**
- Все endpoint'ы в `api/routers/coaching.py` (73 route handler'а)
- Весь `db/coaching_storage.py` (CRUD + аналитические запросы)
- Все сервисы: `coaching_engine`, `coaching_analytics`, `coaching_personalization`, `coaching_recommendations`, `coaching_cross_module`, `coaching_proactive`
- FSM состояния: `CoachingGoalCreation`, `CoachingHabitCreation`, `CoachingCheckIn`, `CoachingWeeklyReview`
- Bot handlers: `/coaching`, callbacks `cg_g_*`, `cg_h_*`, `cg_ci_*`, `cg_wr_*`, `cg_ob_*`
- Bot flows: `coaching_flows.py` (все функции создания/редактирования)
- Supervisor routing к `coaching` агенту
- `coaching_agent.py` — tools, prompt, ответы
- Alembic миграции для Coaching таблиц
- Auth middleware: X-Init-Data, JWT magic token
- APScheduler: утренний бриф, вечерняя рефлексия, weekly review trigger, proactive nudge

**Frontend (Mini App):**
- Все страницы coaching: Dashboard, Goals, GoalDetail, Habits, CheckIn, WeeklyReview, Insights, Onboarding
- Все компоненты: GoalCard, HabitCard, StateIndicator, CoachPromptBubble, StreakWidget
- API-клиент `miniapp/src/api/coaching.ts` — все хуки и функции
- React Query invalidation после мутаций
- Routing `/coaching/*`
- Auth flow через `X-Init-Data`

### 3.2 Вне скоупа (для данной версии)

- Тестирование самой LLM (OpenAI API) — только контракт
- UI регрессионные скриншоты (Storybook/Chromatic) — отдельная задача
- Load/performance тестирование — отдельная задача
- Тестирование Telegram Bot API напрямую — мокируется

---

## 4. Test Layers

### 4.1 Layer 0 — Init/Bootstrap Tests

Цель: убедиться, что модуль корректно поднимается.  
Запуск: первыми, до любых других тестов.  
Инструменты: `pytest`, `importlib`.

### 4.2 Layer 1 — Unit Tests

Цель: тестировать изолированные функции и классы без внешних зависимостей.  
Инструменты: `pytest`, `unittest.mock`, `freezegun` (для дат).  
Скорость: < 1 с на тест.

### 4.3 Layer 2 — Repository/Storage Tests

Цель: тестировать `coaching_storage.py` на реальной тестовой БД.  
Инструменты: `pytest-asyncio`, `testcontainers-python` (PostgreSQL), `sqlalchemy async`.  
Стратегия: каждый тест в транзакции с rollback.

### 4.4 Layer 3 — Service Tests

Цель: тестировать сервисный слой с реальной БД, но с моком LLM/HTTP.  
Инструменты: `pytest-asyncio`, `respx` (mock httpx), `unittest.mock`.

### 4.5 Layer 4 — API Tests

Цель: тестировать FastAPI endpoint'ы через `AsyncClient`.  
Инструменты: `httpx.AsyncClient`, `pytest-asyncio`, тестовая БД.

### 4.6 Layer 5 — Chat/Agent Tests

Цель: тестировать диалоги, маршрутизацию supervisor, tools, формат ответов.  
Инструменты: Aiogram фейки, `unittest.mock`, golden conversation fixtures.

### 4.7 Layer 6 — E2E Tests

Цель: полный пользовательский сценарий от чата до БД до API до Mini App.  
Инструменты: `playwright` (Mini App), настоящая тестовая БД, мок LLM.

### 4.8 Layer 7 — Mini App Tests

Цель: тестировать React компоненты, хуки, страницы.  
Инструменты: `Vitest`, `@testing-library/react`, `MSW` (Mock Service Worker).

---

## 5. Test Environments

### 5.1 Local Development Environment

- PostgreSQL в Docker (testcontainers или `docker-compose.test.yml`)
- `.env.test` с отдельными credentials
- LLM: мок (статические ответы через `unittest.mock`)
- Telegram Bot API: Aiogram test utils / фейковые updates
- APScheduler: отключён или с ручным trigger'ом

### 5.2 CI Environment (GitHub Actions)

- PostgreSQL service container
- Все переменные из GitHub Secrets (`TEST_DATABASE_URL`, `TEST_BOT_TOKEN_FAKE`, `TEST_SECRET_KEY`)
- LLM: всегда мок
- Нет реального интернета для внешних API

### 5.3 Staging Environment

- Реальная база (staging schema)
- Реальный LLM (rate-limited)
- E2E тесты через Playwright
- Smoke тесты после деплоя

### 5.4 Переменные окружения для тестов

```
TEST_DATABASE_URL=postgresql+asyncpg://test:test@localhost:5433/coaching_test
TEST_SECRET_KEY=test-secret-key-32chars-minimum
TEST_BOT_TOKEN=000000000:AAFakeTokenForTesting
TEST_MINIAPP_URL=http://localhost:5173
OPENAI_API_KEY=sk-fake-for-testing
COACHING_LLM_MOCK=true
```

### 5.5 Test Database Setup

- `pytest` fixture `db_session` — создаёт схему через Alembic, откатывает каждый тест
- `pytest` fixture `clean_db` — полная очистка для E2E тестов
- `testcontainers` — PostgreSQL контейнер поднимается один раз на test session

---

## 6. Test Data Strategy

### 6.1 Персонажи для тестовых данных

**Persona A — "Disciplined User" (Алёна)**
- 5 активных целей, все с прогрессом
- 3 привычки, streak 21+ дней
- check-in каждый день 30 дней
- Много данных в nutrition и fitness
- Используется для: happy path, analytics, personalization

**Persona B — "Dropout User" (Борис)**
- 2 цели, progress_pct < 10%
- Привычки есть, streak = 0 (пропускает)
- Последний check-in 14 дней назад
- Нет данных в других модулях
- Используется для: risk scoring, proactive nudge, recovery scenarios

**Persona C — "New User" (Вера)**
- Только что зарегистрировалась
- Нет целей, нет привычек
- Онбординг не завершён
- Используется для: onboarding flow, empty states, first-use scenarios

**Persona D — "Overloaded User" (Григорий)**
- 10+ целей в статусе active
- Нет check-in'ов за неделю
- Переполненный calendar
- Много невыполненных tasks
- Используется для: overload detection, scope reduction suggestions, coaching state = overload

**Persona E — "Health Goal User" (Дарья)**
- Цель "Похудеть на 10 кг" с area=health
- Регулярные fitness логи, нерегулярное nutrition
- Используется для: cross-module tests, nutrition+fitness+coaching связки

### 6.2 Минимальные датасеты по типам тестов

| Тип теста | Минимальный датасет |
|-----------|---------------------|
| Unit tests | Faker-объекты, без БД |
| Storage tests | 1-3 записи на тест, rollback |
| API tests | Persona A + Persona C |
| Chat tests | Отдельный тестовый user_id |
| E2E tests | Полные persona (A, B, C) |
| Cross-module | Persona D + Persona E |

### 6.3 Принципы изоляции данных

- Каждый тест использует уникальный `user_id` (из faker или `uuid4`)
- Storage тесты: транзакция с rollback после каждого теста
- API тесты: dedicated test user, создаётся в fixture, удаляется после
- Нет shared mutable state между тестами разных файлов
- Временны́е данные используют `freezegun` для фиксации даты

---

## 7. Fixtures и Factories

### 7.1 Python Factories (pytest + factory_boy или ручные)

**GoalFactory**
```
Поля: user_id, title, description, area, status, priority, progress_pct,
      target_date, why_statement, first_step, is_frozen, coaching_notes
Дефолты: status=active, progress_pct=0, priority=2
Варианты: GoalFactory.frozen(), GoalFactory.achieved(), GoalFactory.with_progress(50)
```

**HabitFactory**
```
Поля: user_id, title, area, frequency, target_count, cue, reward,
      best_time, is_active, current_streak, longest_streak, total_completions, last_logged_at
Дефолты: frequency=daily, target_count=1, is_active=True, current_streak=0
Варианты: HabitFactory.with_streak(7), HabitFactory.with_streak(0), HabitFactory.inactive()
```

**HabitLogFactory**
```
Поля: habit_id, user_id, logged_at, note
Дефолты: logged_at=now()
Варианты: HabitLogFactory.today(), HabitLogFactory.yesterday(), HabitLogFactory.n_days_ago(n)
```

**GoalMilestoneFactory**
```
Поля: goal_id, title, status, due_date, order_index
Дефолты: status=pending
```

**GoalCheckinFactory**
```
Поля: user_id, goal_id, energy_level, mood, notes, blockers, wins, progress_pct
Дефолты: energy_level=3
```

**CoachingInsightFactory**
```
Поля: user_id, insight_type, severity, title, body, is_read
Дефолты: is_read=False, severity=medium
```

**CoachingRecommendationFactory**
```
Поля: user_id, rec_type, title, body, action_type, is_dismissed
Дефолты: is_dismissed=False
```

**UserCoachingProfileFactory**
```
Поля: user_id, coach_tone, coaching_mode, preferred_checkin_time, preferred_review_day,
      morning_brief_enabled, evening_reflection_enabled, max_daily_nudges
Дефолты: coach_tone=friendly, coaching_mode=standard
```

### 7.2 Pytest Fixtures (conftest.py)

```
# tests/conftest.py (корневой)
engine                — asyncpg engine к тестовой БД
db_session            — AsyncSession, rollback после каждого теста
clean_db              — полная очистка (для E2E)
test_user             — создаёт User в БД, возвращает user_id
test_user_b           — второй пользователь (для isolation тестов)
api_client            — httpx.AsyncClient с тестовым X-Init-Data
api_client_user_b     — клиент для второго пользователя
fake_llm_response     — патч process_message → статический ответ
coaching_profile      — создаёт UserCoachingProfile для test_user
onboarding_done       — создаёт завершённый онбординг

# tests/coaching/conftest.py
goal_factory          — GoalFactory bound to test_user + db_session
habit_factory         — HabitFactory bound to test_user + db_session
persona_disciplined   — полный датасет Persona A
persona_dropout       — полный датасет Persona B
persona_new_user      — пустой датасет Persona C
```

### 7.3 Фейки для внешних систем

**FakeLLM**
- Заменяет `openai.AsyncOpenAI`
- Возвращает предзаданные ответы по ключевым словам
- Логирует все вызовы для assertions
- Конфигурируется через `FakeLLM.set_response(keyword, response)`

**FakeTelegramBot**
- Заменяет `aiogram.Bot`
- Записывает все `send_message`, `answer`, `edit_message_text` вызовы
- `FakeTelegramBot.get_last_message(user_id)` — для assertions
- `FakeTelegramBot.get_all_messages(user_id)` — история

**FakeAPScheduler**
- Заменяет APScheduler
- `FakeAPScheduler.trigger_job(job_id)` — ручной запуск job'а
- Логирует запланированные jobs

**FakeCoachingStorage**
- In-memory реализация `coaching_storage.py` интерфейса
- Для unit-тестов сервисов без реальной БД

---

## 8. Init / Bootstrap Tests

### 8.1 Цель и место в pipeline

Init тесты запускаются **первыми** в CI, до unit и integration. Если они падают — весь test run прерывается. Расположение: `tests/coaching/test_init.py`.

### 8.2 Import и Module Bootstrap Tests

**test_coaching_router_importable**
- `from api.routers import coaching` — без ошибок
- `coaching.router` существует и является `APIRouter`
- Проверка: нет `ImportError`, нет `CircularImportError`

**test_coaching_storage_importable**
- `from db import coaching_storage as cs`
- Все ожидаемые функции существуют: `get_goals`, `create_goal`, `get_habits`, `log_habit`, `get_dashboard_data`, и т.д.

**test_coaching_services_importable**
- Каждый сервис импортируется без ошибок:
  - `from services.coaching_engine import compute_user_state`
  - `from services.coaching_analytics import get_goal_metrics`
  - `from services.coaching_personalization import reset_personalization`
  - `from services.coaching_recommendations import generate_recommendations`
  - `from services.coaching_cross_module import collect_module_signals`
  - `from services.coaching_proactive import schedule_proactive_nudge`

**test_coaching_agent_importable**
- `from agents.personal.coaching_agent import CoachingAgent` (или главная функция)
- Нет circular imports с supervisor или другими агентами

**test_coaching_handler_importable**
- `from bot.handlers.coaching_handler import router`
- `router` является `aiogram.Router`
- Все flows импортируются: `from bot.flows.coaching_flows import *`
- Все FSM состояния: `from bot.states import CoachingGoalCreation, CoachingHabitCreation`

**test_coaching_keyboards_importable**
- `from bot.keyboards.coaching_keyboards import coaching_main_kb, goal_card_kb, ...`
- Все keyboard-функции вызываются без ошибок

### 8.3 FastAPI Router Registration Tests

**test_coaching_router_registered_in_app**
- `app.include_router(coaching.router)` не вызывает ошибок
- В `app.routes` есть маршруты с prefix `/api/coaching`

**test_coaching_router_has_required_routes**
- GET `/api/coaching/dashboard` зарегистрирован
- POST `/api/coaching/goals` зарегистрирован
- POST `/api/coaching/habits` зарегистрирован
- POST `/api/coaching/checkins` зарегистрирован
- GET `/api/coaching/analytics/weekly` зарегистрирован

**test_coaching_router_no_duplicate_routes**
- Нет двух route handler'ов на одном method+path

### 8.4 Database Model Bootstrap Tests

**test_coaching_models_mapped**
- `Goal`, `Habit`, `HabitLog`, `GoalMilestone`, `GoalCheckin`, `GoalReview`
- `CoachingInsight`, `CoachingRecommendation`, `UserCoachingProfile`
- `CoachingMemory`, `CoachingDialogDraft`, `CoachingSession`
- `CoachingOnboardingState`, `CoachingRiskScore`, `CoachingOrchestrationAction`
- Все классы имеют `__tablename__` и `__table__`
- Все relationship'ы не вызывают ошибок при конфигурации

**test_coaching_tables_creatable**
- `Base.metadata.create_all(engine)` для coaching таблиц — без ошибок
- Все таблицы создаются в тестовой БД

### 8.5 Alembic Migration Tests

**test_alembic_head_matches_models**
- `alembic check` не показывает расхождений (autogenerate пуст)
- Или: `alembic revision --autogenerate` не создаёт новых изменений

**test_alembic_upgrade_downgrade**
- `alembic upgrade head` — успешно
- `alembic downgrade -1` — успешно для последней миграции
- `alembic upgrade head` повторно — идемпотентно

**test_coaching_schema_version**
- После `upgrade head` в таблице `alembic_version` есть корректная версия

### 8.6 Supervisor / Agent Graph Bootstrap Tests

**test_coaching_route_registered_in_supervisor**
- В системе промптов supervisor есть слово `coaching`
- При тестовом тексте "поставь цель" supervisor возвращает `domain=coaching`

**test_coaching_agent_callable**
- Coaching agent принимает `(user_id, text, mode, context)` и возвращает строку
- С FakeLLM — не raises

### 8.7 Scheduler Bootstrap Tests

**test_coaching_scheduler_jobs_registered**
- После инициализации APScheduler есть jobs: `morning_brief`, `evening_reflection`, `weekly_review_trigger`
- Или соответствующие функции доступны для регистрации

### 8.8 Smoke Tests (запускаются первыми на staging)

**smoke_health_check**
- `GET /api/health` возвращает `{"status": "ok", "db": "ok"}`

**smoke_coaching_dashboard_responds**
- С валидным auth токеном `GET /api/coaching/dashboard` возвращает 200

**smoke_coaching_create_goal**
- `POST /api/coaching/goals` с `{"title": "Smoke test goal"}` возвращает 201

**smoke_coaching_create_habit**
- `POST /api/coaching/habits` с `{"title": "Smoke test habit"}` возвращает 201

**smoke_coaching_delete_test_data**
- Удаление созданных smoke-тест данных

---

## 9. Unit Tests

### 9.1 coaching_engine.py — State Resolver

**Тестируемый компонент**: `compute_user_state(goals, habits, checkins, risks)`

**Тест-кейсы:**

```
test_state_momentum_when_high_activity
  Input: 3+ привычки streak>7, цели с progress>50%, check-in вчера
  Expected: state="momentum"

test_state_stable_baseline
  Input: 1-2 привычки, цели с прогрессом, check-in 3 дня назад
  Expected: state="stable"

test_state_overload_when_too_many_goals
  Input: 8+ активных целей, много задач
  Expected: state="overload"

test_state_recovery_after_absence
  Input: последний check-in 10 дней назад, streak=0
  Expected: state="recovery"

test_state_risk_when_dropout_signal
  Input: цели без прогресса 14 дней, habit_death риск > 0.7
  Expected: state="risk"

test_state_score_range
  Input: любые данные
  Expected: state_score in [0, 100]

test_state_empty_user_data
  Input: нет целей, нет привычек, нет check-in'ов
  Expected: state="stable" (не raises, не "unknown")

test_state_all_goals_frozen
  Input: все цели is_frozen=True
  Expected: state in ["recovery", "stable"] — не "momentum"
```

**Фикстуры**: `fake_goals_list`, `fake_habits_list`, `fake_checkins_list`, `fake_risk_dict`  
**Моки**: нет (чистая функция)  
**Граничные значения**: 0 целей, 0 привычек, progress_pct=100, streak=365

### 9.2 coaching_analytics.py — Streak Calculation

**Тестируемый компонент**: streak-логика, `compute_weekly_score`

```
test_streak_consecutive_days
  Input: логи 7 последовательных дней
  Expected: current_streak=7

test_streak_broken_by_gap
  Input: логи 5 дней назад, потом 2 дня назад — без вчера
  Expected: current_streak=0 (не 2)

test_streak_today_counts
  Input: лог сегодня
  Expected: current_streak >= 1

test_streak_ignores_duplicates
  Input: 2 лога в один день
  Expected: streak=1, не 2

test_streak_longest_streak_preserved
  Input: текущий streak=3, longest_streak=10
  Expected: longest_streak остаётся 10

test_weekly_score_range
  Input: любые данные за неделю
  Expected: result in [0, 100]

test_weekly_score_zero_activity
  Input: нет активности за 7 дней
  Expected: score в [0, 20] (не 0, базовые очки)

test_weekly_score_full_activity
  Input: check-in каждый день, все привычки, цели с прогрессом
  Expected: score > 80
```

**Граничные значения**: `last_logged_at=None`, `last_logged_at=now()`, timezone edge cases

### 9.3 coaching_analytics.py — Dropout Risk

```
test_dropout_risk_high_on_absence
  Input: 14 дней без активности
  Expected: risk > 0.7

test_dropout_risk_low_on_activity
  Input: check-in вчера, streak>7
  Expected: risk < 0.3

test_dropout_risk_range
  Expected: result in [0.0, 1.0]

test_dropout_risk_level_thresholds
  risk=0.75 → level="critical"
  risk=0.55 → level="high"
  risk=0.35 → level="medium"
  risk=0.15 → level="low"
  risk=0.05 → level="none"
```

### 9.4 coaching_recommendations.py — Ranking Logic

```
test_recommendations_ordered_by_priority
  Input: несколько рекомендаций разного приоритета
  Expected: sorted by priority desc

test_no_duplicate_recommendation_types
  Input: генерация для overload user
  Expected: не более одной rec каждого rec_type в результате

test_recommendations_respect_max_count
  Input: limit=2
  Expected: len(result) <= 2

test_empty_recommendations_when_no_signals
  Input: perfect user — всё хорошо
  Expected: пустой список или только low-priority
```

### 9.5 Natural Language Helpers / Intent Parsing

**Если есть `coach_intent_classifier` или аналог:**

```
test_intent_create_goal
  Input: "хочу поставить цель похудеть"
  Expected: intent="create_goal"

test_intent_log_habit
  Input: "сделал зарядку сегодня"
  Expected: intent="log_habit"

test_intent_checkin
  Input: "сегодня было сложно, энергии мало"
  Expected: intent="checkin" or "create_checkin"

test_intent_weekly_review
  Input: "давай сделаем обзор недели"
  Expected: intent="weekly_review"

test_intent_ambiguous_phrase
  Input: "как дела?" (без явного coaching intent)
  Expected: intent="general" или fallback

test_intent_not_coaching
  Input: "добавь задачу купить молоко"
  Expected: НЕ coaching intent
```

### 9.6 Date Parsing Helpers

```
test_parse_date_natural_ru
  "завтра" → now() + 1 day (date only)
  "через неделю" → now() + 7 days
  "к концу месяца" → last day of current month
  "в пятницу" → nearest future Friday

test_parse_date_returns_none_on_ambiguous
  "когда-нибудь", "потом" → None

test_parse_date_past_raises_or_returns_none
  "вчера" → None или ValidationError
```

**Инструменты**: `freezegun` для фиксации `now()`

### 9.7 Progress Calculation

```
test_progress_pct_from_milestones
  Input: 3 из 5 milestones completed
  Expected: progress_pct=60

test_progress_pct_manual_override
  Input: progress_pct=75 set manually
  Expected: 75 (не перезаписывается)

test_progress_pct_range
  Expected: always in [0, 100]

test_progress_pct_all_done
  All milestones completed → pct=100
```

### 9.8 Session Context Helpers

```
test_context_is_sticky_after_coaching_interaction
  Input: последнее взаимодействие с coaching 2 минуты назад
  Expected: is_sticky() = True

test_context_not_sticky_after_timeout
  Input: последнее взаимодействие 30 минут назад
  Expected: is_sticky() = False

test_context_active_domain_set_on_coaching
  Input: обработан coaching запрос
  Expected: active_domain = "coaching"

test_context_draft_clears_on_completion
  Input: завершён GoalCreation flow
  Expected: draft = None
```

### 9.9 Response Formatting

```
test_goal_card_format
  Input: Goal объект с title, progress, target_date
  Expected: строка содержит title, "%" прогресса

test_habit_streak_format
  Input: Habit с streak=7
  Expected: "🔥 7 дней" или аналог

test_empty_goals_message
  Input: пустой список целей
  Expected: не пустая строка (human-friendly сообщение)

test_no_technical_json_in_response
  Input: любой AI ответ через FakeLLM
  Expected: no "{", "}", "[", "]" в начале строки
```

### 9.10 Permission / Ownership Checks

```
test_goal_belongs_to_user
  Input: goal.user_id = 1, requesting user_id = 1
  Expected: allowed

test_goal_not_belongs_to_user
  Input: goal.user_id = 1, requesting user_id = 2
  Expected: raises 403 или returns None

test_habit_ownership_check
  Аналогично для Habit
```

---

## 10. Integration Tests

### 10.1 Storage + Models Integration

**Файл**: `tests/coaching/test_coaching_storage.py`

**Тест-кейсы — Goals:**

```
test_create_goal_persists_to_db
  create_goal(session, user_id, GoalCreate(...))
  get_goal(session, goal_id, user_id) → не None, поля совпадают

test_create_goal_returns_correct_fields
  Все поля из GoalOut присутствуют, типы корректны

test_get_goals_filtered_by_status
  create active + frozen goals
  get_goals(status="active") → только active
  get_goals(status="frozen") → только frozen

test_get_goals_user_isolation
  user1 создаёт цель, user2 запрашивает → пустой список

test_update_goal_changes_fields
  update_goal(session, goal_id, user_id, UpdateGoal(progress_pct=50))
  get_goal(...) → progress_pct=50

test_update_goal_wrong_user_raises
  update_goal с чужим user_id → raises 404/403

test_freeze_goal_sets_is_frozen
  freeze_goal(session, goal_id, user_id)
  goal.is_frozen = True, goal.status stays "active"

test_achieve_goal_changes_status
  achieve_goal(session, goal_id, user_id)
  goal.status = "achieved"

test_delete_goal_removes_from_db
  delete_goal(session, goal_id, user_id)
  get_goal(...) → None

test_delete_goal_cascades_milestones
  Создать цель + milestone
  delete_goal → milestone тоже удалён
```

**Тест-кейсы — Habits:**

```
test_create_habit_persists
test_log_habit_increments_streak
test_log_habit_twice_today_idempotent
  Второй лог сегодня не увеличивает streak сверх 1

test_miss_habit_resets_streak
  current_streak=5 → log_miss → current_streak=0

test_miss_habit_is_idempotent
  Повторный miss не меняет streak

test_get_habits_active_only
  get_habits(is_active=True) → только активные

test_habit_last_logged_at_updated_on_log
  Запись has last_logged_at = today

test_habit_longest_streak_preserved_on_miss
  longest_streak не сбрасывается при miss
```

**Тест-кейсы — Check-ins:**

```
test_create_checkin_persists
test_get_today_checkin_returns_true_if_done
test_get_today_checkin_returns_false_if_not_done
test_checkin_history_ordered_desc
test_checkin_goal_id_link
  Если указан goal_id, checkin связан с целью
```

**Тест-кейсы — Insights:**

```
test_create_insight_persists
test_mark_insight_read
  insight.is_read = True
test_get_active_insights_excludes_read
test_insights_user_isolation
```

### 10.2 Service Layer Integration

**coaching_engine + storage:**

```
test_compute_user_state_with_real_db
  Создать Persona A в БД
  compute_user_state(db, user_id) → state="momentum" (или stable)
  Не raises, не None

test_compute_user_state_empty_user
  Пустой пользователь → state="stable"

test_get_context_pack_full
  Создать goals + habits + insights
  get_context_pack(db, user_id) → dict со всеми ключами
```

**coaching_analytics + storage:**

```
test_compute_weekly_score_with_real_data
  Persona A: score > 60
  Persona B: score < 40

test_get_goal_metrics_with_milestones
  Создать цель с 3 milestone'ами (2 done)
  get_goal_metrics → completion_rate = 0.666...

test_get_habit_detailed_metrics
  Создать привычку с 10 логами за 2 недели
  Проверить completion_rate, weekly_rate, streak_history
```

**coaching_recommendations + real_db:**

```
test_generate_recommendations_for_dropout_user
  Persona B в БД
  generate_recommendations → хотя бы 1 рекомендация
  рекомендации сохранены в БД

test_no_duplicate_recommendations_on_repeat_call
  Вызов 2 раза подряд → не дублирует записи
```

**coaching_cross_module + mocked external services:**

```
test_collect_module_signals_handles_empty_modules
  tasks_reader → [] (пустой)
  calendar_reader → [] (пустой)
  Не raises, возвращает dict с пустыми списками

test_cross_module_inference_with_overloaded_user
  Persona D: много tasks, перегруженный calendar
  generate_cross_module_recommendations → хотя бы 1 rec с type="workload_reduction"
```

### 10.3 Транзакционные и Idempotency Tests

```
test_log_habit_within_transaction_rollback
  Начать транзакцию, log_habit, rollback
  streak не изменился

test_create_goal_and_milestone_atomic
  create_goal → create_milestone в одной транзакции
  Если milestone creation fails → goal тоже не создаётся

test_achieve_goal_idempotent
  achieve_goal дважды → второй раз не raises, goal.status="achieved"

test_complete_milestone_idempotent
  complete_milestone дважды → streak не меняется, status остаётся "done"
```

### 10.4 Race Condition Tests

```
test_concurrent_habit_logs_same_day
  2 конкурентных вызова log_habit в один день
  В итоге: streak += 1 (не 2), ровно 1 HabitLog за сегодня

test_concurrent_goal_updates
  2 конкурентных update на progress_pct
  Последнее значение применено корректно
```

---

## 11. API Tests

### 11.1 Dashboard Tests

**GET /api/coaching/dashboard**

```
test_dashboard_200_authenticated
  X-Init-Data: валидный → 200

test_dashboard_401_no_auth
  Без заголовка → 401

test_dashboard_shape
  Ответ содержит: state, state_score, habits_today, goals_active,
  top_insight, recommendations, weekly_score, risks, dropout_risk_level

test_dashboard_habits_today_has_today_done_field
  Привычка залогирована сегодня → today_done=true в ответе
  Привычка не залогирована → today_done=false или absent

test_dashboard_empty_user
  Пользователь без данных → 200, пустые списки, state="stable"

test_dashboard_user_isolation
  user1 создаёт данные, user2 запрашивает dashboard → пустые списки user2
```

### 11.2 Goals Tests

**POST /api/coaching/goals**

```
test_create_goal_201
  {"title": "Выучить Python"} → 201, goal_id в ответе

test_create_goal_with_all_fields
  title, description, area, target_date, why_statement, first_step, priority → 201

test_create_goal_missing_title_422
  {} → 422 (title required)

test_create_goal_title_too_long_422
  title > 500 chars → 422

test_create_goal_wrong_area_422
  area="unknown_area" → 422 (если enum)

test_create_goal_past_target_date_422
  target_date="2020-01-01" → 422 или accept (бизнес-решение)
```

**GET /api/coaching/goals**

```
test_list_goals_200
test_list_goals_filter_active
test_list_goals_filter_frozen
test_list_goals_filter_achieved
test_list_goals_empty_returns_array
test_list_goals_user_isolation
  user1 goals не видны user2
```

**GET /api/coaching/goals/{id}**

```
test_get_goal_200
test_get_goal_404_wrong_id
test_get_goal_403_wrong_user
```

**PUT /api/coaching/goals/{id}**

```
test_update_goal_200
  update progress_pct=50 → returned goal has progress_pct=50
test_update_goal_partial
  only update title → other fields unchanged
test_update_goal_404_wrong_id
test_update_goal_403_wrong_user
```

**POST /api/coaching/goals/{id}/freeze**

```
test_freeze_goal_200
  goal.is_frozen = True
test_freeze_already_frozen_is_idempotent
test_freeze_achieved_goal_400_or_422
```

**POST /api/coaching/goals/{id}/achieve**

```
test_achieve_goal_200
  goal.status = "achieved"
test_achieve_frozen_goal_first_resume_then_achieve
```

**GET /api/coaching/goals/{id}/analytics**

```
test_goal_analytics_200
test_goal_analytics_has_expected_fields
  progress_history, milestone_completion_rate, days_since_created
```

### 11.3 Habits Tests

**POST /api/coaching/habits**

```
test_create_habit_201
test_create_habit_missing_title_422
test_create_habit_frequency_variants
  daily, weekly, custom → все 201
```

**POST /api/coaching/habits/{id}/log**

```
test_log_habit_200
  streak increases by 1
test_log_habit_today_twice_idempotent
  второй лог сегодня → streak не растёт
test_log_habit_response_has_streak_and_is_record
test_log_habit_404_wrong_id
test_log_habit_403_wrong_user
```

**POST /api/coaching/habits/{id}/miss**

```
test_miss_habit_200
  streak resets to 0
test_miss_habit_idempotent
```

**GET /api/coaching/habits/templates**

```
test_habit_templates_200
  возвращает список шаблонов
test_habit_templates_filter_by_area
  area="health" → только health templates
```

**GET /api/coaching/habits/{id}/analytics**

```
test_habit_analytics_200
test_habit_analytics_has_completion_rate
test_habit_analytics_no_logs_zero_rate
```

### 11.4 Check-in Tests

**POST /api/coaching/checkins**

```
test_create_checkin_201
  {"energy_level": 4} → 201
test_create_checkin_energy_out_of_range_422
  energy_level=0 → 422
  energy_level=6 → 422
test_create_checkin_second_today
  можно ли создать второй check-in за сегодня? (бизнес-правило)
```

**GET /api/coaching/checkins/today**

```
test_today_checkin_done_true
  После создания check-in → done=true
test_today_checkin_done_false
  До check-in → done=false
```

**GET /api/coaching/checkins/history**

```
test_checkin_history_200
test_checkin_history_ordered_desc_by_date
test_checkin_history_limit_param
  ?limit=5 → не более 5 записей
```

### 11.5 Profile и Personalization Tests

**GET /api/coaching/profile**

```
test_get_profile_200
test_get_profile_auto_created_for_new_user
  Пользователь без профиля → profile создаётся с дефолтами
```

**PUT /api/coaching/profile**

```
test_update_profile_coach_tone
  coach_tone="strict" → 200
test_update_profile_invalid_tone_422
  coach_tone="aggressive" → 422
```

**GET /api/coaching/profile/personalization**

```
test_personalization_200
test_personalization_has_expected_fields
```

**POST /api/coaching/profile/reset**

```
test_reset_profile_200
  profile возвращается к дефолтам
```

### 11.6 Onboarding Tests

```
test_get_onboarding_200
test_onboarding_auto_created_for_new_user
test_advance_onboarding_step_200
  steps_completed увеличивается
test_complete_onboarding_200
  bot_onboarding_done = True
test_complete_onboarding_idempotent
```

### 11.7 Analytics Tests

```
test_weekly_analytics_200
test_weekly_analytics_has_weekly_score
test_weekly_analytics_user_isolation

test_habits_analytics_200
test_goals_analytics_200
test_engagement_analytics_200
test_dropout_risk_200
  Ответ содержит dropout_risk_level
```

### 11.8 Pagination, Filtering, Sorting

```
test_goals_sorted_by_priority_desc
test_habits_limit_param
test_insights_filter_by_severity
  ?severity=high → только high
test_recommendations_limit_2_default
test_checkin_history_pagination
```

### 11.9 Contract Tests (API ↔ Frontend)

Для каждого endpoint, используемого в Mini App, проверяется:

```
test_dashboard_response_matches_frontend_interface
  Поля: state, habits_today[].today_done, goals_active[].progress_pct,
  top_insight.body, recommendations[].rec_type, recommendations[].body

test_goal_response_matches_GoalDto
  Поля: id, title, status, progress_pct, target_date, is_frozen, area

test_habit_response_matches_HabitDto
  Поля: id, title, current_streak, area, is_active, last_logged_at

test_checkin_response_matches_CheckInDto
  Поля: id, energy_level, notes, created_at

test_onboarding_response_matches_OnboardingState
  Поля: current_step, steps_completed, first_goal_created, bot_onboarding_done
```

---

## 12. Chat / Agent / Supervisor Tests

### 12.1 Supervisor Routing Tests

**Файл**: `tests/coaching/test_supervisor_routing.py`

```
test_supervisor_routes_goal_creation_to_coaching
  Input: "хочу поставить цель похудеть"
  Expected: domain="coaching"

test_supervisor_routes_habit_to_coaching
  Input: "хочу завести привычку читать 30 минут"
  Expected: domain="coaching"

test_supervisor_routes_checkin_to_coaching
  Input: "сегодня было сложно, устал"
  Expected: domain="coaching"

test_supervisor_routes_weekly_review_to_coaching
  Input: "давай сделаем обзор недели"
  Expected: domain="coaching"

test_supervisor_routes_task_to_tasks_not_coaching
  Input: "добавь задачу купить молоко"
  Expected: domain="tasks", NOT "coaching"

test_supervisor_routes_nutrition_to_nutrition_not_coaching
  Input: "записал завтрак: овсянка"
  Expected: domain="nutrition", NOT "coaching"

test_supervisor_routes_ambiguous_to_coaching_if_sticky
  Input: "помоги" при active coaching context
  Expected: domain="coaching" (sticky domain)

test_supervisor_handles_coaching_question_in_business_mode
  Input: "поставь бизнес-цель" в business mode
  Expected: domain="coaching" (coaching работает в обоих режимах)
```

### 12.2 Coaching Agent Tool Tests

**Тестируемые tools**: `create_goal_tool`, `log_habit_tool`, `get_goals_tool`, `get_habits_tool`, `get_context_tool`, `create_checkin_tool`

```
test_create_goal_tool_called_on_goal_intent
  Input: "создай цель выучить испанский"
  Expected: create_goal_tool вызван с title="выучить испанский"

test_create_goal_tool_args_extracted_correctly
  Input: "хочу к июлю похудеть на 5 кг"
  Expected: create_goal_tool(title="похудеть на 5 кг", target_date≈июль)

test_log_habit_tool_called_on_habit_log
  Input: "сделал зарядку сегодня"
  Expected: log_habit_tool вызван для habit с keyword "зарядка"

test_get_goals_tool_called_on_goals_request
  Input: "покажи мои цели"
  Expected: get_goals_tool вызван

test_tool_error_graceful_fallback
  Если create_goal_tool raises → агент отвечает понятным сообщением об ошибке
  НЕ выводит traceback или JSON ошибку

test_tool_result_formatted_for_user
  После успешного create_goal_tool → ответ содержит confirmation ("Цель создана")
  НЕ содержит raw JSON структуры
```

### 12.3 Golden Conversation Tests

Формат: предзаданный диалог (user_input → expected_response_keywords).  
Реализация: FakeLLM возвращает детерминированные ответы, assertions на формат.

**Диалог 1 — Создание цели через чат:**
```
Turn 1: User: "хочу поставить цель"
        Expected: бот спрашивает про название или область цели
        Response contains: ["цель", "название", "область"] (любое)

Turn 2: User: "выучить английский"
        Expected: бот спрашивает зачем / target date / первый шаг
        Response contains: ["зачем", "когда", "срок", "первый шаг"] (любое)

Turn 3: User: "к концу года"
        Expected: цель создана, confirmation
        In DB: Goal(title="выучить английский") exists for user
```

**Диалог 2 — Логирование привычки:**
```
Turn 1: User: "сегодня сделал зарядку"
        Pre-condition: habit "зарядка" существует
        Expected: подтверждение, новый streak
        In DB: HabitLog created for today
```

**Диалог 3 — Check-in:**
```
Turn 1: User: "энергии сегодня на 2 из 5, устал от работы"
        Expected: бот принял check-in, выражает поддержку
        In DB: GoalCheckin(energy_level=2) created
```

**Диалог 4 — Уточнение через follow-up:**
```
Turn 1: User: "создай цель"
Turn 2: User: "нет, отмена"
        Expected: цель НЕ создана
        In DB: Goal NOT created
```

### 12.4 Chat Resilience Tests

```
test_empty_message_no_crash
  User отправляет "" или " "
  Expected: graceful response, no exception

test_very_long_message
  User отправляет 2000+ символов
  Expected: processed without crash, response < 4096 chars (Telegram limit)

test_special_characters_in_message
  User: "цель: <script>alert(1)</script>"
  Expected: обработано безопасно, XSS не применим

test_repeated_same_message
  User отправляет одно и то же 5 раз
  Expected: нет дублей в БД, graceful handling

test_message_after_long_absence
  Контекст устарел (> 30 мин), user пишет "продолжим"
  Expected: бот не паникует, начинает заново

test_out_of_order_messages
  Быстрые сообщения быстрее processing предыдущего
  Expected: no race condition, no double-processing
```

### 12.5 FSM State Tests

```
test_fsm_goal_creation_flow_completes
  /coaching → кнопка "Новая цель" → area → title → why → first_step → deadline
  Final state: FSM выходит из CoachingGoalCreation

test_fsm_goal_creation_cancel
  В любой точке flow: кнопка "Отмена"
  Expected: FSM очищается, goal NOT created, пользователь видит главное меню

test_fsm_habit_creation_flow_completes
  start_habit_creation → title → area → cue → reward → finish
  Final: Habit created in DB, FSM cleared

test_fsm_checkin_flow_completes
  start_checkin → wins → progress → energy → finish
  Final: GoalCheckin created, FSM cleared

test_fsm_weekly_review_flow_completes
  start_weekly_review → summary → highlights → blockers → finish
  Final: GoalReview created, FSM cleared

test_fsm_state_isolation_between_users
  User1 в GoalCreation, User2 в CheckIn — состояния независимы

test_fsm_timeout_behavior
  Если пользователь бросил flow посередине
  Expected: при следующем сообщении FSM очищается или корректно обрабатывается
```

---

## 13. Command / Shortcut / Telegram UX Tests

### 13.1 Slash Commands

```
test_command_coaching_opens_main_menu
  /coaching → InlineKeyboard с кнопками "Цели", "Привычки", "Чекин", "Обзор"

test_command_coaching_shows_current_state
  Если у пользователя есть данные → показывает coaching state

test_command_reset_coach_resets_profile
  /reset_coach → CoachingProfile сброшен к дефолтам

test_command_unknown_coaching_not_handled_by_coaching_router
  /unknown_command → coaching_handler НЕ реагирует

test_command_coaching_in_unregistered_user
  Новый пользователь /coaching → онбординг предлагается
```

### 13.2 Callback / Inline Button Tests

**Callbacks: cg_g_* (Goals)**

```
test_callback_cg_g_list_shows_goals
  cg_g_list → список целей пользователя

test_callback_cg_g_new_starts_creation_flow
  cg_g_new → FSM переходит в CoachingGoalCreation.area

test_callback_cg_g_view_shows_goal_detail
  cg_g_view:{goal_id} → карточка цели

test_callback_cg_g_freeze_freezes_goal
  cg_g_freeze:{goal_id} → goal.is_frozen = True, confirmation message

test_callback_cg_g_achieve_achieves_goal
  cg_g_achieve:{goal_id} → goal.status = "achieved"

test_callback_goal_wrong_user_403
  Callback с goal_id чужого пользователя → ошибка, не обрабатывается
```

**Callbacks: cg_h_* (Habits)**

```
test_callback_cg_h_log_logs_habit
  cg_h_log:{habit_id} → streak++, confirmation

test_callback_cg_h_miss_misses_habit
  cg_h_miss:{habit_id} → streak reset, empathetic message

test_callback_cg_h_list_shows_habits
```

**Callbacks: cg_ci_* (Check-in)**

```
test_callback_cg_ci_start_starts_checkin_flow
test_callback_cg_ci_energy_1..5_sets_energy_level
```

**Callbacks: cg_ob_* (Onboarding)**

```
test_callback_onboarding_start_initiates_flow
test_callback_onboarding_skip_marks_done
test_callback_onboarding_done_marks_bot_onboarding_done
```

### 13.3 Stale Callback Protection

```
test_stale_callback_data_handled_gracefully
  Callback с goal_id, который был удалён
  Expected: "Цель не найдена" или graceful error, НЕ exception

test_expired_fsm_callback
  Callback для flow который был начат 1 час назад (FSM устарел)
  Expected: "Сессия устарела, начните заново"

test_duplicate_callback_click
  Одна кнопка нажата дважды быстро
  Expected: второй клик игнорируется или idempotent
```

### 13.4 Reply Keyboard Tests

```
test_coaching_back_button_returns_to_menu
  Кнопка "← Назад" во всех coaching экранах → главное coaching меню

test_skip_button_in_flow
  Кнопка "Пропустить" в optional step → переходит к следующему шагу

test_cancel_button_clears_fsm
  "Отмена" в любой точке → FSM очищается, главное меню
```

---

## 14. E2E Tests

### 14.1 E2E окружение

- Реальная тестовая PostgreSQL (testcontainers)
- FakeLLM с детерминированными ответами
- FastAPI через httpx AsyncClient
- Mini App через Playwright (staging only)
- APScheduler с ручным trigger'ом

### 14.2 E2E Сценарий 1 — First-time Coaching Setup

```
Шаги:
1. Новый пользователь (Persona C) — GET /api/coaching/onboarding
   Assert: bot_onboarding_done=False
2. POST /api/coaching/onboarding/complete
   Assert: 200
3. GET /api/coaching/dashboard
   Assert: state="stable", все списки пусты
4. POST /api/coaching/goals {"title": "Выучить Python", "area": "education"}
   Assert: 201, goal_id returned
5. GET /api/coaching/goals
   Assert: 1 goal, status="active"
6. GET /api/coaching/dashboard
   Assert: goals_active не пустой, содержит новую цель
```

### 14.3 E2E Сценарий 2 — Goal Through Chat → API → Mini App

```
Шаги:
1. Имитировать Telegram сообщение: "создай цель бегать по утрам"
   Through: FakeTelegramBot → text_handler → supervisor → coaching_agent
2. Assert: coaching_agent вызвал create_goal_tool
3. Assert: БД содержит новую Goal для пользователя
4. GET /api/coaching/goals
   Assert: новая цель присутствует в API ответе
5. (Playwright) Открыть /coaching в Mini App
   Assert: цель отображается на GoalsPage
```

### 14.4 E2E Сценарий 3 — Habit Tracking Full Cycle

```
Шаги:
1. POST /api/coaching/habits {"title": "Читать 30 минут", "frequency": "daily"}
2. POST /api/coaching/habits/{id}/log
   Assert: current_streak=1, today_done=true
3. GET /api/coaching/dashboard
   Assert: привычка в habits_today с today_done=true
4. POST /api/coaching/habits/{id}/log (второй раз сегодня)
   Assert: current_streak всё ещё 1 (idempotent)
5. (FakeAPScheduler) Trigger: следующий день
6. GET /api/coaching/habits/{id}
   Assert: last_logged_at = вчера
7. POST /api/coaching/habits/{id}/miss
   Assert: current_streak=0
8. GET /api/coaching/habits/{id}
   Assert: current_streak=0, longest_streak=1
```

### 14.5 E2E Сценарий 4 — Check-in → Recommendation → Dashboard

```
Шаги:
1. Создать Persona B (dropout) данные
2. POST /api/coaching/checkins {"energy_level": 1, "notes": "Нет сил, ничего не успел"}
3. FakeLLM вернуть инсайт про необходимость отдыха
4. GET /api/coaching/recommendations
   Assert: есть рекомендация типа "recovery"
5. GET /api/coaching/dashboard
   Assert: top_insight не null
6. POST /api/coaching/recommendations/{id}/dismiss
7. GET /api/coaching/dashboard
   Assert: рекомендация не отображается
```

### 14.6 E2E Сценарий 5 — Weekly Review

```
Шаги:
1. Создать Persona A данные (полная неделя активности)
2. Имитировать Telegram: "давай сделаем обзор недели"
3. Supervisor → coaching → weekly review flow
4. FSM собирает highlights, blockers
5. Assert: GoalReview создан в БД
6. GET /api/coaching/reviews/latest
   Assert: review.summary не null, review.score > 0
7. GET /api/coaching/analytics/weekly
   Assert: weekly_score присутствует
```

### 14.7 E2E Сценарий 6 — Proactive Recovery

```
Шаги:
1. Persona B: последний check-in 15 дней назад
2. FakeAPScheduler: trigger proactive nudge job
3. Assert: FakeTelegramBot.get_last_message(user_id) содержит motivational message
4. CoachingNudgeLog: запись об отправке
5. Trigger снова через 24 часа — nudge НЕ отправляется повторно
   Assert: идемпотентность
```

### 14.8 E2E Сценарий 7 — Cross-Module Health Goal

```
Шаги:
1. Создать цель area="health"
2. Добавить 5 записей nutrition за неделю (через nutrition API)
3. Добавить 3 fitness тренировки за неделю
4. GET /api/coaching/cross-module/analyze
5. Assert: response содержит signals из nutrition и fitness
6. Assert: coaching рекомендация ссылается на health-контекст
```

### 14.9 E2E Сценарий 8 — Mini App → Bot Consistency

```
Шаги:
1. (Playwright) В Mini App создать цель через GoalsPage UI
2. Assert: цель появилась в БД
3. Имитировать Telegram: "покажи мои цели"
4. Assert: бот перечисляет созданную через Mini App цель
```

---

## 15. Mini App Tests

### 15.1 Component Tests (Vitest + @testing-library/react)

**CoachingDashboard:**

```
test_dashboard_shows_loading_state
  MSW: задержка /api/coaching/dashboard
  Expected: Loader2 icon visible

test_dashboard_shows_onboarding_cta_when_no_data
  MSW: /api/coaching/dashboard → null
  Expected: "Начни свой путь" button visible

test_dashboard_shows_state_indicator
  MSW: dashboard с state="momentum"
  Expected: StateIndicator rendered с правильным состоянием

test_dashboard_shows_habits_list
  MSW: dashboard с 2 habits_today
  Expected: 2 HabitCard components rendered

test_dashboard_log_habit_button_triggers_mutation
  Click ✅ на HabitCard
  Expected: POST /api/coaching/habits/{id}/log вызван

test_dashboard_dismiss_recommendation
  Click "Скрыть" на рекомендации
  Expected: POST /api/coaching/recommendations/{id}/dismiss вызван
  Рекомендация исчезает из UI
```

**GoalsPage:**

```
test_goals_page_shows_goals_list
test_goals_page_filter_by_status
test_goals_page_create_goal_flow
  Fill form → Submit → Goal appears in list (optimistic or after refetch)
test_goals_page_empty_state
  Нет целей в фильтре → empty state message
test_goals_page_search_filters_results
```

**HabitsPage:**

```
test_habits_page_today_mode_shows_log_buttons
test_habits_page_all_mode_shows_stats
test_habits_page_create_habit_from_template
  Click template → title prefilled
test_habits_page_habit_logged_shows_checkmark
```

**CheckInPage:**

```
test_checkin_page_energy_slider
  Изменение slider → energy_level обновляется
test_checkin_submit_calls_api
test_checkin_today_already_done_shows_warning
```

**GoalDetailPage:**

```
test_goal_detail_shows_progress_bar
test_goal_detail_milestone_completion
  Click milestone → status changes to done
test_goal_detail_freeze_button
test_goal_detail_achieve_button
```

### 15.2 Hook Tests

**useDashboard:**
```
test_use_dashboard_fetches_on_mount
test_use_dashboard_refetches_on_focus
test_use_dashboard_stale_time_1_minute
```

**useLogHabit:**
```
test_use_log_habit_invalidates_dashboard_cache
test_use_log_habit_invalidates_habits_cache
```

**useCreateGoal:**
```
test_use_create_goal_invalidates_goals_cache
test_use_create_goal_invalidates_dashboard_cache
```

### 15.3 API Client Tests (coaching.ts)

```
test_fetch_dashboard_calls_correct_endpoint
test_create_goal_sends_correct_body
test_log_habit_sends_post_to_correct_url
test_dismiss_recommendation_calls_correct_endpoint
test_api_client_includes_auth_header
  X-Init-Data заголовок присутствует в каждом запросе
```

### 15.4 Routing Tests

```
test_coaching_route_renders_dashboard
  Navigate to /coaching → CoachingDashboard rendered
test_coaching_goals_route
  Navigate to /coaching/goals → GoalsPage rendered
test_coaching_goal_detail_route
  Navigate to /coaching/goals/123 → GoalDetailPage rendered
test_coaching_habits_route
test_coaching_checkin_route
test_coaching_onboarding_route
test_unknown_coaching_route_redirects
  /coaching/unknown → redirect to /coaching
```

### 15.5 Empty / Error States

```
test_coaching_dashboard_network_error
  MSW: /api/coaching/dashboard → 500
  Expected: error message shown, не blank screen

test_goals_page_api_error
  Expected: retry button shown

test_habit_log_failure
  POST /log → 500
  Expected: error toast, streak NOT updated in UI
```

### 15.6 Telegram Web App Integration

```
test_bottom_nav_coaching_tab_enabled
  Nav item для coaching не disabled

test_coaching_back_button_uses_telegram_back
  В GoalDetailPage: browser back или Telegram back работает

test_theme_applied_from_telegram_sdk
  Telegram dark theme → CSS variables обновлены
```

---

## 16. Auth / Telegram initData Tests

### 16.1 initData Validation Unit Tests

```
test_valid_initdata_passes_validation
  Корректный HMAC hash → validation passes, user_id extracted

test_invalid_hmac_returns_401
  Изменённый hash → 401

test_missing_initdata_header_returns_401
  Без X-Init-Data → 401

test_expired_initdata
  auth_date > 24 часа назад → 401 (если проверяется свежесть)

test_initdata_wrong_bot_token
  Hash computed with другим bot_token → 401

test_initdata_user_id_extraction
  Valid initData с user.id=12345 → request.state.user_id = 12345
```

### 16.2 API Auth Integration Tests

```
test_coaching_endpoint_requires_auth
  GET /api/coaching/dashboard без auth → 401

test_coaching_endpoint_accepts_valid_auth
  GET /api/coaching/dashboard с валидным X-Init-Data → 200

test_jwt_magic_token_accepted
  Magic token из /web → работает для API запросов

test_jwt_expired_magic_token_rejected
  Токен просрочен → 401

test_user_isolation_via_auth
  user1 token → не видит данные user2
  POST /api/coaching/goals/{user2_goal_id} с user1 token → 403/404
```

### 16.3 Security / Negative Tests

```
test_spoofed_user_id_in_initdata
  Изменить user.id в payload без пересчёта hash → 401

test_sql_injection_in_title
  POST /api/coaching/goals {"title": "'; DROP TABLE goals; --"}
  Expected: 201 (сохранено как строка, не выполнено)

test_xss_in_goal_title
  title="<script>alert(1)</script>"
  Expected: сохранено как есть, но в ответе API — escaped или raw string

test_unauthorized_delete_other_user_goal
  DELETE /api/coaching/goals/{other_user_goal_id} → 403 or 404
```

---

## 17. Reminder / Scheduler Tests

### 17.1 APScheduler Job Registration Tests

```
test_morning_brief_job_registered
  После init scheduler: job с id="coaching_morning_brief" или аналогичным существует

test_evening_reflection_job_registered
test_weekly_review_trigger_job_registered
test_proactive_nudge_job_registered
```

### 17.2 Proactive Nudge Tests

```
test_nudge_sent_to_dropout_user
  Persona B (14 дней без активности)
  FakeAPScheduler.trigger_job("proactive_nudge")
  Assert: FakeTelegramBot.get_last_message(user_id) не None

test_nudge_not_sent_to_active_user
  Persona A (check-in вчера)
  Trigger nudge
  Assert: FakeTelegramBot.get_last_message(user_id) IS None (нет сообщения)

test_nudge_idempotent_same_day
  Отправить nudge → попытаться отправить снова сегодня
  Assert: второй nudge НЕ отправлен
  Assert: CoachingNudgeLog содержит только 1 запись за сегодня

test_nudge_respects_max_daily_nudges
  max_daily_nudges=1 в профиле
  Trigger несколько раз
  Assert: отправлен не более 1 раза
```

### 17.3 Morning Brief Tests

```
test_morning_brief_sent_at_configured_time
  preferred_checkin_time="09:00"
  FakeAPScheduler trigger в 09:05
  Assert: сообщение отправлено

test_morning_brief_disabled_when_not_enabled
  morning_brief_enabled=False
  Trigger
  Assert: сообщение НЕ отправлено

test_morning_brief_content
  Assert: содержит список habits_today и goals_active count
```

### 17.4 Weekly Review Trigger Tests

```
test_weekly_review_triggered_on_preferred_day
  preferred_review_day="sunday"
  Trigger в воскресенье
  Assert: review prompt отправлен

test_weekly_review_not_triggered_on_wrong_day
  Trigger в понедельник при preferred_review_day="sunday"
  Assert: НЕ отправлен
```

### 17.5 Timezone Edge Cases

```
test_nudge_respects_user_timezone
  (Если поддерживается timezone)
  "09:00 UTC+3" для пользователя → не должно отправляться в 09:00 UTC

test_habit_streak_day_boundary_midnight
  Лог в 23:59 и лог в 00:01 следующего дня
  Assert: streak = 2 (разные дни), не 1
  freezegun используется для управления временем
```

---

## 18. Cross-Module Tests

### 18.1 Coaching читает Tasks

```
test_coaching_context_includes_pending_tasks_count
  Создать 5 pending tasks для пользователя
  get_context_pack(db, user_id)
  Assert: context["tasks"]["pending_count"] = 5

test_coaching_suggests_scope_reduction_on_many_tasks
  Persona D: 15 pending tasks + overloaded calendar
  cross_module_analyze → рекомендация типа "scope_reduction"

test_coaching_not_broken_when_no_tasks
  Пользователь без tasks
  get_context_pack → не raises, tasks секция пустая
```

### 18.2 Coaching читает Calendar

```
test_coaching_context_includes_upcoming_events
  Создать 3 события в calendar на следующие 7 дней
  cross_module_signals["calendar"]["upcoming_events"] = 3

test_coaching_detects_overloaded_week
  Calendar: 20+ событий за следующие 7 дней
  coaching inference → "calendar_overload" signal
```

### 18.3 Coaching + Nutrition

```
test_coaching_context_includes_nutrition_consistency
  Persona E: нерегулярные nutrition логи + health goal
  cross_module_signals["nutrition"]["consistency_score"] < 0.5

test_coaching_recommends_nutrition_tracking_for_health_goal
  health_goal + no nutrition logs for 7 days
  Рекомендация содержит упоминание питания

test_coaching_not_broken_when_no_nutrition_data
  Нет nutrition логов → не raises
```

### 18.4 Coaching + Fitness

```
test_coaching_context_includes_fitness_activity
test_coaching_detects_irregular_workouts_for_health_goal
test_coaching_congratulates_on_fitness_milestone
```

### 18.5 Graceful Degradation

```
test_cross_module_partial_failure_one_module_down
  tasks reader raises exception
  Остальные модули читаются корректно
  Coaching рекомендации генерируются (без tasks data)
  Assert: нет propagation exception

test_cross_module_all_empty
  Все модули пустые
  Assert: coaching state="stable", нет ошибок, пустые рекомендации

test_cross_module_inconsistent_data
  fitness says 5 workouts, но nutrition has 0 logs, goal is weight loss
  Assert: коуч не делает противоречивых выводов
  Assert: рекомендации логичны (не "ты отлично питаешься!")
```

---

## 19. Failure / Edge Case / Resilience Tests

### 19.1 Empty и Null Data Tests

```
test_goal_with_null_target_date
  goal.target_date = None → GoalCard не crashes

test_habit_with_null_last_logged_at
  streak calc → streak=0, не raises

test_dashboard_all_nulls
  state=None, top_insight=None, etc. → 200, nulls gracefully handled

test_checkin_null_notes
  energy_level=3, notes=None → принято

test_coaching_profile_missing
  get_profile для пользователя без профиля → auto-create с дефолтами
```

### 19.2 Duplicate и Idempotency Tests

```
test_create_same_goal_twice_not_deduplicated
  2 цели с одинаковым title → создаются (нет unique constraint на title)

test_log_habit_twice_today_idempotent
  streak не увеличивается дважды

test_complete_onboarding_twice_idempotent
  второй вызов → 200, status stays done

test_double_achieve_goal_idempotent
test_double_freeze_idempotent
test_double_dismiss_recommendation_idempotent
```

### 19.3 Broken / Malformed Data

```
test_goal_with_progress_pct_over_100
  Если вручную установлено progress_pct=150 в БД
  API ответ → 200, progress_pct=150 (или cap at 100 — по бизнес-правилу)

test_habit_with_negative_streak
  Если streak=-1 в БД → display as 0, не crash

test_invalid_json_in_coaching_memory
  CoachingMemory.data = "{broken json" → сервис не crashes

test_goal_with_future_created_at
  created_at в будущем → аналитика не crash
```

### 19.4 Database Failure Tests

```
test_api_returns_503_on_db_timeout
  Имитировать db timeout
  GET /api/coaching/goals → 503 или 500 (не 200 с пустыми данными)

test_partial_db_write_failure
  create_goal starts, но db fails on commit
  Assert: нет partial goal в БД

test_health_endpoint_shows_db_error
  DB недоступна → GET /api/health → {"status": "degraded", "db": "error: ..."}
```

### 19.5 LLM Timeout Tests

```
test_llm_timeout_returns_fallback_message
  LLM не отвечает 30+ секунд
  Expected: "⏳ Запрос занял слишком много времени..."
  NOT: бесконечное ожидание

test_llm_error_response_handled
  LLM возвращает 500
  Expected: graceful error message пользователю

test_llm_returns_empty_response
  LLM возвращает ""
  Expected: fallback message, не пустой ответ пользователю
```

### 19.6 Timezone и Date Boundary Tests

```
test_habit_log_at_midnight
  Лог в 00:00:00 UTC
  Expected: засчитывается как новый день, streak правильный

test_daily_score_calculation_at_day_boundary
  weekly_score вычисляется в 23:59 vs 00:01
  Expected: корректная разбивка по дням

test_target_date_in_past_goal_analytics
  goal.target_date прошло
  Expected: analytics показывает "overdue", не crash
```

### 19.7 Concurrent User Tests

```
test_concurrent_api_requests_user_isolation
  user1 и user2 одновременно запрашивают dashboard
  Assert: user1 не получает данные user2

test_concurrent_habit_logs_different_users
  user1 и user2 логируют одну и ту же по id привычку
  Expected: ошибка для user2 (ownership check)
```

---

## 20. Observability / Logging / Debug Tests

### 20.1 Critical Events Logging Tests

```
test_goal_created_logged
  create_goal → log entry с user_id, goal_id, "GOAL_CREATED"

test_habit_logged_logged
  log_habit → log entry с habit_id, streak value

test_checkin_created_logged
  create_checkin → log entry с energy_level

test_weekly_review_generated_logged
  weekly review generation → log entry с review_id, score

test_llm_timeout_logged_as_warning
  LLM timeout → logger.warning с user_id, timeout duration

test_cross_module_failure_logged
  Module read failure → logger.error с module name, exception
```

### 20.2 Структурированность логов

```
test_logs_include_user_id
  Все coaching операции → log record имеет user_id

test_logs_include_correlation_id
  (Если реализован) request_id / correlation_id присутствует

test_error_logs_include_stack_trace
  При exception → traceback в логе (exc_info=True)

test_coaching_agent_decision_logged
  При routing decision → supervisor логирует selected_domain

test_tool_call_logged
  Когда coaching_agent вызывает tool → log с tool_name, args (без secrets)
```

### 20.3 Audit Trail

```
test_recommendation_dismissal_audited
  dismiss_recommendation → запись в CoachingNudgeLog или audit_log

test_profile_reset_audited
  reset_personalization → log entry

test_goal_status_changes_audited
  freeze, achieve, archive goal → log entry с old_status, new_status
```

---

## 21. CI Pipeline / Quality Gates

### 21.1 PR Checks (на каждый Pull Request)

```
Stage 1: Linting & Type Check
  - ruff check (Python linting)
  - mypy / pyright (type checking для coaching сервисов)
  - tsc --noEmit (TypeScript для miniapp)
  - eslint (Mini App)

Stage 2: Init / Bootstrap Tests
  tests/coaching/test_init.py
  Timeout: 60s
  Условие: если fail → останавливаем весь pipeline

Stage 3: Unit Tests
  pytest tests/coaching/test_unit_*.py
  pytest tests/coaching/test_engine.py
  pytest tests/coaching/test_analytics.py
  Coverage: >= 80% для coaching сервисов
  Timeout: 2 мин

Stage 4: Storage Integration Tests
  pytest tests/coaching/test_storage.py
  Requires: PostgreSQL service container
  Timeout: 5 мин

Stage 5: API Tests
  pytest tests/coaching/test_api.py
  Requires: PostgreSQL + test app
  Timeout: 5 мин

Stage 6: Mini App Tests
  cd miniapp && npm run test
  Coverage: >= 70%
  Timeout: 3 мин
```

### 21.2 Push to Main — Additional Checks

```
Stage 7: Agent / Chat Tests
  pytest tests/coaching/test_chat.py
  pytest tests/coaching/test_supervisor.py
  Timeout: 5 мин

Stage 8: Cross-Module Tests
  pytest tests/coaching/test_cross_module.py
  Timeout: 5 мин

Stage 9: Alembic Migration Tests
  pytest tests/coaching/test_migrations.py
  Timeout: 3 мин

Stage 10: Contract Tests
  pytest tests/coaching/test_contracts.py
  Timeout: 2 мин
```

### 21.3 Nightly Tests

```
Stage 11: E2E Tests (полные сценарии)
  pytest tests/e2e/coaching/
  Timeout: 30 мин

Stage 12: Failure / Resilience Tests
  pytest tests/coaching/test_resilience.py
  Timeout: 10 мин

Stage 13: Performance Baseline
  Smoke latency check: /api/coaching/dashboard < 500ms
```

### 21.4 Post-Deploy Smoke Tests

```
smoke_health_check
smoke_coaching_dashboard_responds_200
smoke_create_and_delete_test_goal
smoke_log_test_habit
smoke_check_weekly_analytics
```

### 21.5 Quality Gates

| Метрика | Threshold | Action при fail |
|---------|-----------|-----------------|
| Unit test coverage (coaching services) | >= 80% | Блокирует merge |
| Integration test pass rate | 100% | Блокирует merge |
| API test pass rate | 100% | Блокирует merge |
| Smoke tests | 100% | Rollback deploy |
| E2E pass rate | >= 95% | Alert, не rollback |
| Mini App test coverage | >= 70% | Warning |
| Flaky test rate | < 2% | Требует фикса в 48ч |

### 21.6 Flaky Test Policy

- Flaky тест помечается `@pytest.mark.flaky(max_runs=3)`
- При 3+ fails подряд → issue создаётся автоматически
- Flaky тесты не блокируют merge, но отслеживаются в dashboard
- Deadline на починку: 1 спринт (2 недели)

### 21.7 Snapshot Update Policy

- Snapshot тесты (если используются) обновляются только вручную через `pytest --snapshot-update`
- Автоматическое обновление snapshots в CI — запрещено
- PR с изменением snapshots требует review от tech lead

---

## 22. Rollout Safety / Regression Plan

### 22.1 Pre-Deploy Checklist

- [ ] Все init/bootstrap тесты зелёные
- [ ] Все Alembic миграции применены без ошибок
- [ ] Smoke тесты на staging прошли
- [ ] Contract тесты подтверждают совместимость с frontend
- [ ] Coaching router зарегистрирован в `api/main.py`
- [ ] APScheduler jobs зарегистрированы

### 22.2 Regression Pack (Core Coaching)

Список тест-сценариев, которые ВСЕГДА запускаются перед любым release:

```
R-001: Создать цель через API
R-002: Получить dashboard с данными
R-003: Залогировать привычку, проверить streak
R-004: Создать check-in
R-005: Получить weekly analytics
R-006: Supervisor routes "поставь цель" → coaching
R-007: initData auth work
R-008: User isolation (user1 не видит user2)
R-009: Onboarding flow complete
R-010: Рекомендации генерируются для dropout user
```

### 22.3 Breaking Change Detection

- Изменение схемы ответа API → contract test fail → не деплоим без обновления frontend
- Изменение FSM состояний → migration тест + chat flow тест
- Изменение supervisor промпта → routing тесты + golden conversations
- Изменение DB schema → Alembic migration test

### 22.4 Rollback Criteria

- Smoke тест `smoke_coaching_dashboard_responds_200` падает → немедленный rollback
- Более 5% API 5xx ошибок на `/api/coaching/*` → alert + rollback
- FSM state corruption (пользователи жалуются на зависший диалог) → hotfix

---

## 23. Definition of Done for QA

### 23.1 DoD для новой фичи в Coaching

Фича считается готовой к merge, если:

- [ ] Unit тесты написаны для новой бизнес-логики (coverage >= 80%)
- [ ] Integration тест для нового storage метода
- [ ] API тест для нового endpoint (позитивный + негативный)
- [ ] Если фича меняет чат-поведение — golden conversation тест добавлен
- [ ] Если фича добавляет callback — callback тест добавлен
- [ ] Contract тест для нового API поля / нового endpoint
- [ ] Failure сценарий задокументирован (null, timeout, wrong user)
- [ ] CI pipeline зелёный

### 23.2 DoD для Coaching модуля в целом

- [ ] Init/Bootstrap тесты: 100% pass
- [ ] Unit tests: >= 80% coverage для coaching_engine, coaching_analytics, coaching_recommendations
- [ ] Storage tests: все CRUD операции покрыты
- [ ] API tests: все 73 endpoint'а покрыты (позитивный + auth + ownership)
- [ ] Chat tests: все FSM flows покрыты
- [ ] E2E tests: 10 основных сценариев зелёные
- [ ] Cross-module tests: все 5 модулей + graceful degradation
- [ ] Auth tests: HMAC validation, user isolation
- [ ] Scheduler tests: nudge idempotency, trigger timing
- [ ] Regression pack R-001..R-010: 100% pass
- [ ] Mini App tests: Dashboard, Goals, Habits, CheckIn, GoalDetail

---

## 24. Phased Implementation Plan

### Phase 1 — Foundation (Спринт 1, 1-2 недели)

**Приоритет: Инфраструктура тестирования**

1. `tests/conftest.py` — базовые fixtures (engine, db_session, test_user)
2. `tests/coaching/conftest.py` — coaching-специфичные fixtures
3. Factories: GoalFactory, HabitFactory, HabitLogFactory
4. FakeLLM, FakeTelegramBot реализации
5. `tests/coaching/test_init.py` — все bootstrap/init тесты
6. Тестовый `docker-compose.test.yml` с PostgreSQL

**Критерий готовности Phase 1**: init тесты зелёные, CI pipeline настроен

### Phase 2 — Unit и Storage (Спринт 2, 1-2 недели)

**Приоритет: Бизнес-логика**

1. `test_unit_engine.py` — state resolver, score calculator
2. `test_unit_analytics.py` — streak, dropout risk, weekly score
3. `test_unit_recommendations.py` — ranking, dedup
4. `test_storage_goals.py` — все CRUD + isolation
5. `test_storage_habits.py` — log, miss, streak
6. `test_storage_checkins.py`

**Критерий готовности Phase 2**: coverage >= 80% для сервисов

### Phase 3 — API Tests (Спринт 3, 1-2 недели)

**Приоритет: API корректность и безопасность**

1. `test_api_dashboard.py`
2. `test_api_goals.py`
3. `test_api_habits.py`
4. `test_api_checkins.py`
5. `test_api_analytics.py`
6. `test_api_auth.py` — initData, isolation
7. `test_contracts.py` — shape tests против frontend

**Критерий готовности Phase 3**: все API endpoint'ы покрыты, auth тесты зелёные

### Phase 4 — Chat / Agent (Спринт 4, 2 недели)

**Приоритет: Conversational AI правильность**

1. `test_supervisor_routing.py`
2. `test_agent_tools.py`
3. `test_fsm_flows.py` — GoalCreation, HabitCreation, CheckIn, WeeklyReview
4. `test_callbacks.py` — cg_g_*, cg_h_*, cg_ci_*, cg_ob_*
5. `test_golden_conversations.py` — 5-10 golden dialogs
6. `test_chat_resilience.py` — edge cases

**Критерий готовности Phase 4**: supervisor routing 100%, FSM flows 100%

### Phase 5 — Cross-Module и Scheduler (Спринт 5, 1-2 недели)

1. `test_cross_module.py` — все 5 модулей
2. `test_scheduler.py` — nudge, morning brief, weekly review trigger
3. `test_resilience.py` — failures, timeouts, edge cases

**Критерий готовности Phase 5**: cross-module graceful degradation, scheduler idempotency

### Phase 6 — E2E и Mini App (Спринт 6, 2 недели)

1. `miniapp/src/__tests__/coaching/` — component и hook тесты
2. `tests/e2e/coaching/test_e2e_scenarios.py` — 10 E2E сценариев
3. Playwright setup для Mini App (staging)

**Критерий готовности Phase 6**: DoD Coaching модуля выполнен полностью

---

## Приложение A — Структура директорий тестов

```
tests/
├── conftest.py                        # Базовые fixtures (engine, db, users, api_client)
├── factories/
│   ├── __init__.py
│   ├── goal_factory.py
│   ├── habit_factory.py
│   ├── checkin_factory.py
│   ├── insight_factory.py
│   ├── user_factory.py
│   └── coaching_profile_factory.py
├── fakes/
│   ├── fake_llm.py
│   ├── fake_telegram_bot.py
│   └── fake_scheduler.py
├── coaching/
│   ├── conftest.py                    # Coaching-специфичные fixtures
│   ├── test_init.py                   # Bootstrap / Import тесты
│   ├── test_unit_engine.py            # State resolver, score
│   ├── test_unit_analytics.py         # Streak, dropout, weekly score
│   ├── test_unit_recommendations.py   # Ranking, dedup
│   ├── test_unit_context.py           # Session context helpers
│   ├── test_unit_formatting.py        # Response formatting
│   ├── test_unit_date_parsing.py      # Date/NLP helpers
│   ├── test_storage_goals.py          # Goals CRUD + isolation
│   ├── test_storage_habits.py         # Habits + streak
│   ├── test_storage_checkins.py
│   ├── test_storage_insights.py
│   ├── test_storage_analytics.py
│   ├── test_api_dashboard.py
│   ├── test_api_goals.py
│   ├── test_api_habits.py
│   ├── test_api_checkins.py
│   ├── test_api_analytics.py
│   ├── test_api_profile.py
│   ├── test_api_onboarding.py
│   ├── test_api_auth.py
│   ├── test_contracts.py
│   ├── test_supervisor_routing.py
│   ├── test_agent_tools.py
│   ├── test_fsm_flows.py
│   ├── test_callbacks.py
│   ├── test_golden_conversations.py
│   ├── test_chat_resilience.py
│   ├── test_cross_module.py
│   ├── test_scheduler.py
│   ├── test_migrations.py
│   └── test_resilience.py
├── e2e/
│   └── coaching/
│       ├── conftest.py
│       ├── test_e2e_scenario_1_first_setup.py
│       ├── test_e2e_scenario_2_goal_chat_to_api.py
│       ├── test_e2e_scenario_3_habit_cycle.py
│       ├── test_e2e_scenario_4_checkin_to_dashboard.py
│       ├── test_e2e_scenario_5_weekly_review.py
│       ├── test_e2e_scenario_6_proactive_recovery.py
│       ├── test_e2e_scenario_7_cross_module_health.py
│       └── test_e2e_scenario_8_miniapp_to_bot.py
miniapp/src/__tests__/
├── coaching/
│   ├── CoachingDashboard.test.tsx
│   ├── GoalsPage.test.tsx
│   ├── HabitsPage.test.tsx
│   ├── CheckInPage.test.tsx
│   ├── GoalDetailPage.test.tsx
│   ├── components/
│   │   ├── GoalCard.test.tsx
│   │   ├── HabitCard.test.tsx
│   │   ├── StateIndicator.test.tsx
│   │   └── CoachPromptBubble.test.tsx
│   └── hooks/
│       ├── useDashboard.test.ts
│       ├── useLogHabit.test.ts
│       └── useCreateGoal.test.ts
└── mocks/
    └── coaching_handlers.ts           # MSW handlers для coaching API
```

---

## Приложение B — Инструменты и Зависимости

### Backend Testing Stack

```
pytest>=8.0
pytest-asyncio>=0.23
pytest-cov>=5.0
httpx>=0.27
testcontainers[postgresql]>=4.0
factory-boy>=3.3
faker>=25.0
freezegun>=1.5
respx>=0.21                    # Mock для httpx calls
aiogram[test]>=3.x             # Если есть test utilities
anyio>=4.0
```

### Frontend Testing Stack

```
vitest
@testing-library/react
@testing-library/user-event
msw (Mock Service Worker)
@vitest/coverage-v8
jsdom
```

### CI Tools

```
GitHub Actions
testcontainers (PostgreSQL 16)
playwright (E2E, staging only)
```

---

## Приложение C — Конфигурация pytest

```ini
# pytest.ini или pyproject.toml [tool.pytest.ini_options]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--tb=short",
    "--strict-markers",
    "-v",
]
markers = [
    "unit: unit tests (no DB, no external)",
    "integration: integration tests (require DB)",
    "api: API endpoint tests",
    "chat: chatbot / agent tests",
    "e2e: end-to-end tests",
    "smoke: smoke tests for CI",
    "slow: tests taking > 5 seconds",
    "flaky: known flaky tests with retry",
]

# Coverage config
[tool.coverage.run]
source = ["api", "services", "db", "agents", "bot"]
omit = ["*/test_*", "*/migrations/*", "*/alembic/*"]

[tool.coverage.report]
fail_under = 70
show_missing = true
```

---

*Документ создан: 2026-03-14*  
*Следующий review: при добавлении новых Coaching features*  
*Ответственный за документ: Tech Lead*
