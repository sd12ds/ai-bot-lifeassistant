# Проектная документация: домен Research (Data Collection & Parsing)
> SaaS-подсистема сбора, парсинга и анализа данных из интернета
> Дата: 2026-03-20

---

## 1. Общее описание

### 1.1. Что это
Новый домен **Research** — полноценная SaaS-подсистема внутри Jarvis, через которую **внешние платные пользователи** могут:
- Ставить задачи на сбор информации из интернета (через Telegram-чат или Web UI)
- Запускать crawling / scraping / extraction через Firecrawl (и другие провайдеры в будущем)
- Получать структурированные результаты в веб-панели
- Управлять задачами, шаблонами, экспортом

### 1.2. Ключевые принципы
- **Security-first**: авторизация, изоляция данных, аудит на всех уровнях
- **SaaS-ready**: подписки, тарифы, billing, usage accounting, квоты
- **Multi-user / Multi-tenant**: workspace, роли, права доступа
- **Расширяемость**: provider abstraction (Firecrawl первый, но не единственный)
- **Интеграция**: органично встраивается в существующую архитектуру supervisor/agents

### 1.3. Выбранный нейминг
**`research`** — используется единообразно везде: в коде, routing, API, UI, БД.

---

## 2. High-level архитектура

### 2.1. Встраивание в Jarvis

```
Telegram Chat ──► Supervisor (classify_intent) ──► research_agent ──► Research Service Layer
                                                                         │
Web UI (React) ──► FastAPI /api/research/* ─────────────────────────────►─┘
                                                                         │
                                                          ┌──────────────┴──────────────┐
                                                          │   Research Service Layer     │
                                                          │  ┌─────────────────────────┐│
                                                          │  │ AuthZ / Billing Guard    ││
                                                          │  │ Job Manager              ││
                                                          │  │ Execution Engine         ││
                                                          │  │ Provider Layer           ││
                                                          │  │   └─ FirecrawlProvider   ││
                                                          │  │   └─ (future providers)  ││
                                                          │  │ Usage Accounting         ││
                                                          │  │ Audit Logger             ││
                                                          │  └─────────────────────────┘│
                                                          └─────────────┬───────────────┘
                                                                        │
                                                                   PostgreSQL
                                                          (research_*, billing_*, audit_*)
```

### 2.2. Слои архитектуры

1. **Presentation Layer** — Telegram agent + FastAPI routers + React Web UI
2. **AuthZ / Billing Guard** — middleware: проверка прав, подписки, квот
3. **Domain Layer** — ResearchJob, Run, Result, Template — бизнес-логика
4. **Service Layer** — JobManager, ExecutionEngine, ExtractionPipeline
5. **Provider Layer** — FirecrawlProvider (abstraction для scraping-провайдеров)
6. **Usage / Billing Layer** — UsageLedger, QuotaChecker, BillingEventEmitter
7. **Audit Layer** — AuditLogger, SecurityEventLogger
8. **Storage Layer** — SQLAlchemy models, PostgreSQL

---

## 3. Identity, Auth и Authorization

### 3.1. Модель пользователя (расширение существующей)

Текущий User (telegram_id) расширяется:
- `email` — для web-логина (опционально)
- `auth_provider` — telegram / email / google (в будущем)
- Связь через таблицу `ExternalIdentity` (telegram_id ↔ web account)

### 3.2. Account Linking Flow

```
Telegram user ──► бот отправляет magic link ──► web login ──► связывание accounts
                                                               │
                                                     User.telegram_id = ExternalIdentity.provider_id
```

Уже частично реализовано через `create_jwt()` / `verify_jwt()` в `api/deps.py`.

### 3.3. Workspace / Tenant

- **Workspace** — изолированное пространство (personal или team)
- Каждый User автоматически получает Personal Workspace
- Team Workspace создаётся отдельно (Phase 2)

### 3.4. Уровни управления

| Уровень | Кто управляет | Что управляет |
|---------|--------------|---------------|
| **Платформа** (мы — операторы Jarvis) | Администратор платформы | Firecrawl API key, тарифы, лимиты, провайдеры, мониторинг всех пользователей |
| **Workspace** (пользователь) | owner / admin | Участники, роли, подписка, настройки workspace |
| **Задачи** (пользователь) | manager | Создание / запуск research jobs |

Пользователь **НЕ видит и НЕ настраивает** провайдеров (Firecrawl и др.). Для него Research — чёрный ящик: написал задачу → получил результат → заплатил по тарифу.

Firecrawl API key — **один, платформенный**, хранится в env-переменных сервера. Себестоимость вызовов закладывается в цену тарифных планов.

### 3.5. Роли внутри workspace

Роли существуют внутри workspace. Один человек может быть owner в своём personal workspace и viewer в чужом team workspace.

**owner** — создатель workspace
- Создаёт / удаляет / настраивает workspace
- Приглашает / удаляет участников, назначает роли
- Оформляет / меняет / отменяет подписку
- Всё остальное что могут другие роли

**admin** — доверенный управляющий
- Приглашает / удаляет участников, назначает роли (кроме owner)
- Видит audit-логи
- Всё что может manager

**billing_admin** — финансовый управляющий (может быть совмещён с admin)
- Оформляет / меняет / отменяет подписку
- Видит usage, квоты, историю платежей
- НЕ может создавать / запускать задачи

**manager** — основной работник
- Создаёт research jobs (задачи на сбор)
- Запускает / останавливает / перезапускает jobs
- Редактирует задачи, управляет шаблонами
- Экспортирует результаты
- Видит все задачи workspace

**analyst** — аналитик (чтение + экспорт)
- Видит все задачи и результаты workspace
- Экспортирует данные
- НЕ может создавать / запускать / редактировать jobs

**viewer** — наблюдатель (только чтение)
- Видит задачи и результаты workspace
- НЕ может экспортировать, создавать, запускать

### 3.6. Матрица прав

| Действие | owner | admin | billing_admin | manager | analyst | viewer |
|----------|-------|-------|--------------|---------|---------|--------|
| Создать research job | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| Запустить / перезапустить job | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| Остановить / отменить job | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| Редактировать job | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| Удалить / архивировать job | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Смотреть jobs и результаты | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ |
| Экспортировать результаты | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ |
| Управлять шаблонами | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| Приглашать участников | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Назначать роли | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Оформить / изменить подписку | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Видеть usage / квоты | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Видеть billing / платежи | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Видеть audit-логи | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Удалить workspace | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

### 3.7. Типичные сценарии

**Solo-пользователь:**
Регистрируется → получает Personal Workspace (роль owner) → оформляет подписку Starter → создаёт задачи из чата или web UI → видит только свои данные.

**Команда из 3 человек:**
Руководитель создаёт Team Workspace (owner) → приглашает аналитика (analyst) и помощника (manager) → оформляет подписку Team → manager создаёт/запускает задачи → analyst смотрит результаты и экспортирует → лимиты общие на workspace.

**Человек в нескольких workspace:**
У пользователя свой Personal Workspace (owner, подписка Starter) + его пригласили в Team Workspace компании (роль analyst). В Telegram — workspace switcher. В Web UI — переключатель workspace в header.

### 3.8. Модель доступа (RBAC)

Права проверяются на 3 уровнях:
1. **API middleware** — `require_permission("research.job.create")`
2. **DB-запросы** — все SELECT/UPDATE содержат `WHERE workspace_id = :ws_id`
3. **UI** — скрытие элементов по ролям

Защита от горизонтального доступа:
- Все endpoints принимают workspace_id из сессии (НЕ из параметров запроса)
- Job ID — UUID (не sequential int)
- Результаты фильтруются на уровне БД, не фронта

---

## 4. Subscription, Billing и Usage

### 4.1. Тарифные планы

| План | Лимиты/мес | Цена |
|------|-----------|------|
| **Free / Trial** | 5 jobs, 100 pages crawl, 10K LLM tokens | 0₽ / 14 дней |
| **Starter** | 50 jobs, 5K pages, 500K tokens | TBD |
| **Pro** | 500 jobs, 50K pages, 5M tokens | TBD |
| **Team** | Pro × seats, shared workspace | TBD |
| **Enterprise** | Custom limits | Custom |

### 4.2. Жизненный цикл подписки

```
trial → active → past_due → grace_period → suspended → canceled
                    │                                      │
                    └── оплата ──► active                   └── реактивация → active
```

### 4.3. Поведение при разных статусах

| Статус | Создать job | Запустить run | Смотреть результаты | Экспорт | Billing UI |
|--------|-------------|--------------|---------------------|---------|------------|
| **active** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **trial** | ✅ (с лимитами) | ✅ | ✅ | ❌ | ✅ |
| **past_due** | ❌ | ❌ | ✅ (read-only) | ❌ | ✅ |
| **grace_period** | ❌ | ❌ | ✅ (read-only) | ✅ | ✅ |
| **suspended** | ❌ | ❌ | ❌ | ❌ | ✅ |
| **canceled** | ❌ | ❌ | ✅ (30 дней) | ✅ (30 дней) | ✅ |
| **quota_exceeded** | ❌ | ❌ | ✅ | ✅ | ✅ |

### 4.4. Usage Accounting

Что учитываем:
- **LLM tokens** — input + output для agent/extraction
- **Crawl pages** — количество страниц, обработанных Firecrawl
- **Scrape operations** — отдельные scrape-вызовы
- **Job runs** — количество запусков
- **Storage** — объём сохранённых данных
- **Exports** — количество экспортов

Структура:
```
UsageLedger: period + workspace_id + metric_type → consumed / limit / remaining
UsageEvent: actor + scope + metric + amount + source_job + timestamp + cost_meta
```

Проверка квот:
- **До запуска job** — preflight check: хватает ли лимитов
- **Во время выполнения** — инкрементальное списание
- **Soft limit** — предупреждение при 80% использования
- **Hard limit** — блокировка при 100%

### 4.5. Billing Architecture (abstraction)

```
BillingAccount (workspace-level)
    └── Subscription → Plan
    └── Invoice[]
    └── Payment[]
    └── BillingEvent[]
```

Billing provider — за abstraction layer:
- Webhook handler для обработки payment events
- Не привязываемся к конкретному провайдеру (Stripe/Tinkoff/etc)

---

## 5. Domain Model (сущности БД)

### 5.1. Core Platform (новые таблицы)

```sql
-- Рабочие пространства
workspaces (id UUID PK, name, owner_user_id FK, settings JSONB, created_at)

-- Членство в workspace
memberships (id, user_id FK, workspace_id FK, role VARCHAR, status, invited_at, joined_at)

-- Внешние идентичности (Telegram ↔ web)
external_identities (id, user_id FK, provider, provider_id, metadata JSONB)

-- Тарифные планы
plans (id, name, features JSONB, quotas JSONB, price_monthly, price_yearly, is_active)

-- Подписки
subscriptions (id, workspace_id FK, plan_id FK, status, period_start, period_end,
               grace_end, cancel_at, canceled_at, trial_end, billing_account_id)

-- Billing accounts
billing_accounts (id, workspace_id FK, provider, provider_customer_id, metadata JSONB)

-- Usage ledger (агрегация за период)
usage_ledgers (id, workspace_id FK, period_start, period_end, metric_type,
               consumed NUMERIC, reserved NUMERIC, limit_value NUMERIC)

-- Usage events (атомарные события)
usage_events (id, workspace_id FK, user_id FK, metric_type, amount NUMERIC,
              source_type, source_id, provider, cost_metadata JSONB, created_at)

-- Quota policies (привязка к плану)
quota_policies (id, plan_id FK, metric_type, limit_value NUMERIC, period, enforcement)
```

### 5.2. Research Domain

```sql
-- Задачи исследования
research_jobs (
    id UUID PK, workspace_id FK, created_by FK,
    title, description, original_request TEXT,
    normalized_spec JSONB,  -- структурированная спецификация задачи
    status VARCHAR,  -- draft/pending/running/completed/failed/canceled/archived
    job_type VARCHAR,  -- search/crawl/scrape/extract/multi_step
    provider VARCHAR,  -- firecrawl / future
    config JSONB,  -- provider-specific config
    visibility VARCHAR,  -- private/workspace/shared
    origin VARCHAR,  -- chat/web/api/system
    usage_estimate JSONB,
    tags JSONB,
    last_run_at, created_at, updated_at
)

-- Запуски задач
research_job_runs (
    id UUID PK, job_id FK,
    status VARCHAR,  -- queued/running/completed/failed/canceled
    started_at, finished_at,
    provider_metadata JSONB,
    error_details TEXT,
    metrics JSONB,  -- urls_found, pages_crawled, items_extracted, etc
    usage_actual JSONB,  -- tokens, crawl_pages, scrape_ops
    created_at
)

-- Результаты (отдельные найденные элементы)
research_result_items (
    id UUID PK, job_id FK, run_id FK,
    source_url, domain,
    title, raw_content TEXT,  -- markdown/html
    extracted_fields JSONB,  -- структурированные данные
    dedupe_hash VARCHAR,
    metadata JSONB,
    created_at
)

-- Шаблоны задач
research_templates (
    id UUID PK, workspace_id FK, created_by FK,
    name, description,
    spec_template JSONB,
    is_public BOOLEAN,
    created_at, updated_at
)

-- Источники / seed URLs
research_sources (
    id UUID PK, job_id FK,
    url, domain, source_type,  -- seed/discovered/search_result
    status VARCHAR,
    metadata JSONB
)

-- Лог сообщений агента (история диалога по задаче)
research_message_logs (
    id, job_id FK, role VARCHAR, content TEXT, created_at
)

-- Статусные события задачи
research_status_events (
    id, job_id FK, run_id FK,
    event_type, old_status, new_status,
    actor_id, source VARCHAR,
    metadata JSONB, created_at
)
```

### 5.3. Audit / Security

```sql
-- Audit trail
audit_events (
    id UUID PK, workspace_id FK, actor_id FK,
    action VARCHAR,  -- job.create, job.run, result.export, billing.upgrade, etc
    resource_type, resource_id,
    source VARCHAR,  -- chat/web/api/system
    ip_address, user_agent,
    metadata JSONB, created_at
)

-- Provider credentials (ПЛАТФОРМЕННЫЙ уровень, НЕ per-workspace)
-- Управляется только операторами Jarvis через admin panel / env variables
platform_provider_configs (
    id, provider_type VARCHAR,  -- firecrawl / future
    config JSONB,  -- non-sensitive settings (rate limits, defaults)
    is_active BOOLEAN,
    created_at, updated_at
)
-- API ключи провайдеров хранятся в env-переменных сервера (FIRECRAWL_API_KEY и др.)
-- НЕ в БД, НЕ per-workspace
```

---

## 6. Backend структура (файлы и модули)

### 6.1. Новые файлы

```
agents/personal/research_agent.py          — LangGraph ReAct-агент домена Research
tools/research_tools.py                    — @tool функции для агента
bot/core/intent_classifier.py              — + _RESEARCH_STRONG / _RESEARCH_NORMAL маркеры
agents/supervisor.py                       — + research узел + routing

services/research/                         — Service Layer
  ├── job_manager.py                       — создание, обновление, управление jobs
  ├── execution_engine.py                  — оркестрация pipeline выполнения
  ├── extraction_pipeline.py               — обработка raw → structured данных
  ├── collection_engine.py                 — координация provider-вызовов
  └── result_processor.py                  — дедупликация, нормализация результатов

integrations/firecrawl/                    — Provider Layer
  ├── __init__.py
  ├── provider.py                          — FirecrawlProvider (implements CollectionProvider)
  ├── client.py                            — HTTP-клиент Firecrawl API
  └── mapper.py                            — маппинг задач → Firecrawl режимы

services/billing/                          — Billing Layer
  ├── subscription_manager.py              — CRUD подписок, lifecycle
  ├── quota_checker.py                     — проверка лимитов перед запуском
  ├── usage_tracker.py                     — запись usage events, агрегация
  └── billing_guard.py                     — middleware для API

services/auth/                             — AuthZ Layer (расширение)
  ├── workspace_manager.py                 — управление workspace
  ├── rbac.py                              — role-based access control
  └── permission_checker.py                — проверка прав на действия

services/audit/                            — Audit Layer
  ├── audit_logger.py                      — запись audit events
  └── security_logger.py                   — security-sensitive events

db/research_storage.py                     — CRUD для research сущностей
db/billing_storage.py                      — CRUD для billing сущностей
db/models.py                               — + новые ORM-модели

api/routers/research.py                    — API endpoints для research
api/routers/billing.py                     — API endpoints для billing/subscription
api/routers/workspace.py                   — API endpoints для workspace/membership
api/middleware/billing_guard.py            — FastAPI middleware проверки подписки

miniapp/src/features/research/             — Web UI
  ├── ResearchDashboard.tsx
  ├── JobsList.tsx
  ├── JobDetail.tsx
  ├── ResultsExplorer.tsx
  ├── TemplatesList.tsx
  ├── NewJobForm.tsx
  └── components/
      ├── JobCard.tsx
      ├── ResultTable.tsx
      ├── StatusBadge.tsx
      ├── UsageBar.tsx
      └── QuotaIndicator.tsx

miniapp/src/features/billing/              — Billing UI
  ├── BillingDashboard.tsx
  ├── PlanSelector.tsx
  ├── UsageCharts.tsx
  └── SubscriptionStatus.tsx

miniapp/src/api/research.ts                — API-клиент research
miniapp/src/api/billing.ts                 — API-клиент billing
```

### 6.2. Изменяемые существующие файлы

```
agents/supervisor.py           — + research agent node + routing
bot/core/intent_classifier.py  — + _RESEARCH_STRONG / _RESEARCH_NORMAL
db/models.py                   — + новые ORM-модели
api/main.py                    — + подключение research/billing/workspace routers
api/deps.py                    — + get_workspace, require_subscription, require_permission
config.py                      — + FIRECRAWL_API_KEY, RESEARCH_* конфиги
docker-compose.yml             — при необходимости
requirements.txt               — + firecrawl-py
```

---

## 7. Firecrawl Integration

### 7.1. Provider Abstraction

```python
class CollectionProvider(ABC):
    """Абстрактный интерфейс провайдера сбора данных."""
    async def crawl(self, urls, config) -> CrawlResult
    async def scrape(self, url, config) -> ScrapeResult
    async def map_site(self, url) -> list[str]
    async def extract(self, url, schema) -> ExtractResult
    def estimate_usage(self, task_spec) -> UsageEstimate
    def get_provider_name(self) -> str

class FirecrawlProvider(CollectionProvider):
    """Реализация через Firecrawl API."""
    ...
```

### 7.2. Маппинг задач → Firecrawl режимы

| Тип задачи | Firecrawl режим | Описание |
|------------|----------------|----------|
| Сбор сайтов по теме | `search` → `scrape` | Поиск + извлечение |
| Crawl одного сайта | `crawl` | Обход всех страниц |
| Извлечение данных со страницы | `scrape` + LLM extraction | Парсинг конкретных полей |
| Карта сайта | `map` | Получение списка URL |
| Multi-step research | `search` → `crawl` → `extract` | Полный pipeline |

### 7.3. Usage metering

Каждый вызов Firecrawl записывает:
- Количество обработанных страниц
- Объём полученных данных
- Provider cost units (credits Firecrawl)
- Время выполнения

---

## 8. Chat Interaction Flow (агент)

### 8.1. Pipeline обработки

```
User message
    │
    ▼
1. Supervisor → classify_intent → "research"
    │
    ▼
2. research_agent получает сообщение
    │
    ▼
3. LLM извлекает intent + task parameters
    │
    ▼
4. Достаточно данных?
    ├─ Нет → задать уточняющие вопросы (цикл)
    └─ Да ↓
    │
    ▼
5. Preflight checks:
    ├─ auth → workspace → permissions
    ├─ subscription active?
    ├─ quota available?
    └─ provider ready?
    │
    ├─ Fail → объяснить причину + что делать
    └─ Pass ↓
    │
    ▼
6. Создать ResearchJob + ResearchJobRun
    │
    ▼
7. Ответить: "Принял. Запускаю сбор... Результаты появятся в Research → Jobs."
    │
    ▼
8. Фоновое выполнение (не блокирует чат):
    ├─ Collection (Firecrawl)
    ├─ Extraction (LLM)
    ├─ Dedup / Normalize
    ├─ Persist results
    ├─ Record usage
    └─ Emit audit events
    │
    ▼
9. Уведомление в чат:
    "Сбор завершён: найдено 86 компаний. Детали → Research → Jobs."
```

### 8.2. Маркеры для intent_classifier

**_RESEARCH_STRONG:**
```
"собери сайты", "найди компании", "спарси", "вытащи контакты",
"собери информацию", "проанализируй сайт", "обойди сайт",
"найди конкурентов", "собери данные", "extraction", "crawl",
"scrape", "парсинг", "research"
```

**_RESEARCH_NORMAL:**
```
"найди сайты", "собери", "список компаний", "контакты",
"поставщики", "конкуренты", "производители"
```

---

## 9. Web UI архитектура

### 9.1. Страницы / роуты

```
/research                    — Dashboard (статистика, быстрый запуск, usage)
/research/jobs               — Список задач (фильтры, поиск, пагинация)
/research/jobs/:id           — Детальная карточка задачи
/research/jobs/:id/results   — Результаты задачи (таблица, карточки, экспорт)
/research/templates          — Шаблоны задач
/admin                       — (Внутренняя admin panel — только для операторов платформы)
/billing                     — Подписка, план, usage, квоты
/billing/history             — История платежей
/settings/workspace          — Workspace, роли, участники
/settings/security           — Audit log, сессии
```

### 9.2. Ключевые компоненты

- **QuotaIndicator** — показывает остаток лимитов (в header)
- **SubscriptionBanner** — предупреждение при past_due / quota_exceeded
- **UsageCharts** — графики потребления за период
- **ResultTable** — таблица результатов с сортировкой, фильтрацией, экспортом
- **JobStatusTimeline** — визуализация шагов выполнения задачи

---

## 10. API Surface

### 10.1. Research API

| Method | Endpoint | Роль min | Проверки |
|--------|----------|---------|----------|
| POST | `/api/research/jobs` | manager | auth + permission + subscription + quota |
| GET | `/api/research/jobs` | viewer | auth + workspace scope |
| GET | `/api/research/jobs/:id` | viewer | auth + ownership check |
| PATCH | `/api/research/jobs/:id` | manager | auth + ownership |
| POST | `/api/research/jobs/:id/run` | manager | auth + subscription + quota |
| POST | `/api/research/jobs/:id/cancel` | manager | auth + ownership |
| DELETE | `/api/research/jobs/:id` | admin | auth + ownership + audit |
| GET | `/api/research/jobs/:id/results` | viewer | auth + ownership |
| GET | `/api/research/jobs/:id/runs` | viewer | auth + ownership |
| GET | `/api/research/jobs/:id/runs/:rid/logs` | analyst | auth + ownership |
| POST | `/api/research/jobs/:id/export` | analyst | auth + subscription + quota(export) |
| CRUD | `/api/research/templates` | manager | auth + workspace scope |

### 10.2. Billing API

| Method | Endpoint | Роль min |
|--------|----------|---------|
| GET | `/api/billing/subscription` | viewer |
| GET | `/api/billing/usage` | viewer |
| GET | `/api/billing/plans` | viewer |
| POST | `/api/billing/subscribe` | billing_admin |
| POST | `/api/billing/upgrade` | billing_admin |
| POST | `/api/billing/cancel` | billing_admin |
| GET | `/api/billing/invoices` | billing_admin |

### 10.3. Workspace API

| Method | Endpoint | Роль min |
|--------|----------|---------|
| GET | `/api/workspaces` | viewer |
| PATCH | `/api/workspaces/:id` | admin |
| GET | `/api/workspaces/:id/members` | viewer |
| POST | `/api/workspaces/:id/invite` | admin |
| PATCH | `/api/workspaces/:id/members/:uid` | admin |

---

## 11. Security Architecture

### 11.1. Изоляция данных
- Все research-таблицы содержат `workspace_id`
- Все SELECT-запросы фильтруют по `workspace_id` из сессии
- Job ID — UUID v4 (не guessable)
- Export защищён проверкой ownership + subscription

### 11.2. Secrets
- Firecrawl API key — **платформенный**, хранится в env-переменных сервера (НЕ в БД, НЕ per-workspace)
- Billing provider identifiers — отдельная таблица
- Пользователи НЕ имеют доступа к API-ключам провайдеров

### 11.3. Audit Trail
- Все CRUD-операции с jobs, results, billing — логируются в `audit_events`
- Все access-denied — логируются в `audit_events` (action=`access_denied`)
- Все billing state changes — логируются
- Source: chat / web / api / system

### 11.4. Защита API
- Auth required by default (dependency `get_current_user`)
- `require_permission(action)` — RBAC middleware
- `require_active_subscription()` — billing guard
- `check_quota(metric, amount)` — quota enforcement
- Rate limiting на research endpoints
- Safe error messages (не раскрывать internal details)

---

## 12. Поэтапный план реализации

### Phase 1: MVP (2-3 недели)
**Цель**: рабочий сбор данных из чата + просмотр в web UI

1. DB: таблицы `research_jobs`, `research_job_runs`, `research_result_items`
2. `integrations/firecrawl/` — FirecrawlProvider (crawl + scrape + extract)
3. `services/research/` — JobManager, ExecutionEngine (базовый pipeline)
4. `agents/personal/research_agent.py` — ReAct-агент с tools
5. `tools/research_tools.py` — create_job, run_job, check_status, list_results
6. Supervisor routing — + research домен + маркеры
7. `api/routers/research.py` — базовые CRUD endpoints
8. Web UI: JobsList + JobDetail + ResultsExplorer (базовые)
9. Фоновое выполнение через asyncio (как в scheduler)

### Phase 2: Auth + Multi-user (1-2 недели)
**Цель**: workspace isolation + роли

1. DB: `workspaces`, `memberships`, `external_identities`
2. `services/auth/` — workspace_manager, rbac, permission_checker
3. `api/deps.py` — `get_workspace()`, `require_permission()`
4. Фильтрация по workspace_id во всех запросах
5. Account linking flow (Telegram ↔ web)
6. Web UI: workspace switcher, role-aware navigation

### Phase 3: Billing + Usage (1-2 недели)
**Цель**: подписки, квоты, учёт usage

1. DB: `plans`, `subscriptions`, `billing_accounts`, `usage_ledgers`, `usage_events`, `quota_policies`
2. `services/billing/` — subscription_manager, quota_checker, usage_tracker
3. Billing guard middleware
4. Preflight checks в execution pipeline
5. Usage recording при каждом provider call
6. Web UI: BillingDashboard, UsageCharts, QuotaIndicator, SubscriptionStatus

### Phase 4: Security Hardening + Audit (1 неделя)
**Цель**: audit trail, security events, export protection

1. DB: `audit_events`, `provider_credentials`
2. `services/audit/` — audit_logger
3. Encrypted credential storage
4. Rate limiting
5. Export protection (subscription check)
6. Web UI: Admin/Audit section

### Phase 5: Расширение (ongoing)
- Templates / Recipes
- Recurring / Monitor mode
- Enrichment pipeline
- Дополнительные providers (search engines, API-based sources)
- Team collaboration
- Overage billing / credits
- Enterprise features

---

## 13. Риски и узкие места

| Риск | Вероятность | Митигация |
|------|------------|-----------|
| Firecrawl rate limits / downtime | Средняя | Retry + circuit breaker + provider abstraction |
| Долгие задачи блокируют ресурсы | Средняя | Фоновое выполнение + timeout + partial results |
| Утечка данных между workspace | Высокая без защиты | workspace_id в каждом запросе + тесты |
| Сложность billing интеграции | Средняя | Abstraction layer + поэтапная реализация |
| Перерасход квот при параллельных запусках | Средняя | Reservation-based usage + atomic counters |
| Giant god-object agent | Средняя | Разделение на sub-agents по типу задачи |
| Стоимость LLM для extraction | Высокая | Usage metering + cost-aware execution policies |

---

*Документ является живым и обновляется по мере реализации.*
