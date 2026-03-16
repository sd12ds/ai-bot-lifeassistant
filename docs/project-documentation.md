# Документация проекта: AI Life Assistant (Jarvis)

> Версия: 1.0 | Дата: 2026-03-16
> Сервер: 77.238.235.171 | Путь: /root/ai-assistant

---

## 1. ОБЗОР ПРОЕКТА

**AI Life Assistant (Jarvis)** — мультиагентный Telegram-бот + Mini App (WebApp) для управления жизнью и бизнесом.

**Два режима работы:**
- **Personal** — задачи, календарь, питание, фитнес, AI-коучинг
- **Business** — CRM, управление командой, планировщик встреч

**Ключевая идея:** Все взаимодействия через чат (текст/голос/фото), LangGraph Supervisor маршрутизирует запросы к специализированным AI-агентам.

---

## 2. ТЕХНОЛОГИЧЕСКИЙ СТЕК

### Backend
- **Python 3.11+** — основной язык
- **aiogram 3.x** — Telegram Bot API фреймворк
- **FastAPI** — REST API для Mini App
- **LangGraph + LangChain** — мультиагентная оркестрация
- **OpenAI GPT-4.1-mini/nano** — LLM для агентов и классификации
- **SQLAlchemy 2.x (async)** — ORM
- **PostgreSQL 16** — основная БД (через asyncpg)
- **Alembic** — миграции БД

### Frontend (Mini App)
- **React 18 + Vite** — SPA
- **TypeScript** + **TailwindCSS**
- **Telegram Web App SDK** — авторизация

### Инфраструктура
- **Docker Compose** — postgres + api (FastAPI) + nginx
- **Бот** — запускается через nohup python main.py

---

## 3. СТРУКТУРА ПРОЕКТА

```
ai-assistant/
  main.py                      — Точка входа бота (polling)
  bot.py                       — Устаревший бот (только Google Calendar)
  config.py                    — Централизованная конфигурация (.env)

  agents/                      — LangGraph агенты
    supervisor.py              — Supervisor: маршрутизация (classify → route → agent)
    personal/
      assistant_agent.py       — Общий ассистент (без tools)
      calendar_agent.py        — Календарь (Google Calendar, отключён)
      coaching_agent.py        — AI-коуч (цели, привычки, check-in)
      fitness_agent.py         — Фитнес-тренер (тренировки, замеры)
      nutrition_agent.py       — Нутрициолог (питание, КБЖУ, вода)
      reminder_agent.py        — Задачи и напоминания
    business/
      crm_agent.py             — CRM (контакты, сделки)
      team_agent.py            — Команды
      scheduler_agent.py       — Планировщик встреч

  bot/                         — Telegram bot layer (aiogram)
    handlers/
      common.py                — /start, /help
      text.py                  — Текстовые сообщения → Supervisor
      voice.py                 — Голосовые → STT → Supervisor
      photo.py                 — Фото еды → Vision → Nutrition
      coaching_handler.py      — Кнопки/FSM для коучинга (~1700 строк)
      task_menu.py             — Меню задач (ReplyKeyboard)
      task_actions.py          — Callback: ✅ Выполнено
      settings.py              — ⚙️ Настройки бота
    flows/
      coaching_flows.py        — Многошаговые диалоги коучинга (FSM)
    core/
      intent_classifier.py     — Rule-based pre-classifier (keywords)
      session_context.py       — In-memory контекст сессии (draft, sticky domain)
      followup_engine.py       — Follow-up советы после действий
      action_resolver.py       — Резолвер действий из LLM ответов
      base_draft.py            — Базовый класс черновика
      adapters/                — Адаптеры доменов
    keyboards/                 — Inline/Reply клавиатуры
    middleware/
      user_context.py          — Middleware: загрузка пользователя из БД
    nutrition_context.py       — Контекст draft/last_saved для nutrition агента
    states.py                  — FSM состояния (aiogram)

  services/                    — Бизнес-логика (чистые вычисления)
    coaching_engine.py         — Скоринг, risk, context pack
    coaching_analytics.py      — Метрики целей/привычек/вовлечённости
    coaching_proactive.py      — 17 триггеров + proactive nudges
    coaching_personalization.py — Поведенческие паттерны, адаптивный тон
    coaching_recommendations.py — Очередь рекомендаций
    coaching_cross_module.py   — Кросс-модульный анализ (Tasks+Fitness+Nutrition)
    ai_coach.py                — Общий AI-coach сервис
    nutrition_calc.py          — Расчёты КБЖУ
    nutrition_score.py         — Скоринг дня питания (0-100)
    nutrition_followup.py      — Follow-up советы по питанию
    nutrition_insights.py      — Инсайты по питанию
    nutrition_merge.py         — Слияние продуктов
    nutrition_weekly_summary.py — Недельная сводка питания
    fitness_insights.py        — Инсайты по фитнесу
    exercise_matcher.py        — Поиск упражнений по алиасам
    voice_checkin_parser.py    — Парсер голосовых чекинов
    workout_program_parser.py  — Парсер программ тренировок

  tools/                       — LangGraph tools для агентов
    coaching_tools.py          — 30+ инструментов коучинга
    coaching_context_tools.py  — Контекстные tools (analytics, memory)
    nutrition_tools.py         — Инструменты питания
    fitness_tools.py           — Инструменты фитнеса
    calendar_tools.py          — Google Calendar tools
    reminder_tools.py          — Задачи и напоминания
    crm_tools.py               — CRM tools

  db/                          — Слой данных
    models.py                  — SQLAlchemy ORM модели (~50 таблиц)
    session.py                 — Async session factory
    storage.py                 — Общие CRUD операции
    coaching_storage.py        — CRUD для coaching-таблиц
    fitness_storage.py         — CRUD для fitness-таблиц
    nutrition_storage.py       — CRUD для nutrition-таблиц
    checkpointer.py            — PostgreSQL checkpointer для LangGraph
    recurrence.py              — Повторяющиеся задачи (RFC 5545)
    reminders.py               — Работа с напоминаниями
    migrations/                — Alembic миграции

  api/                         — FastAPI REST API
    main.py                    — Приложение FastAPI + CORS + роутеры
    deps.py                    — Зависимости (авторизация через Telegram initData)
    routers/
      auth.py                  — Авторизация (/api/auth)
      tasks.py                 — Задачи CRUD (/api/tasks)
      calendars.py             — Календари (/api/calendars)
      coaching.py              — Coaching API (~1500 строк)
      nutrition.py             — Питание API
      fitness.py               — Фитнес API
      voice.py                 — Голосовой ввод API
      ai_coach.py              — AI Coach chat API

  infrastructure/scheduler/
    notification_scheduler.py  — Планировщик уведомлений (60с цикл)
    nutrition_tips_scheduler.py — Советы по питанию
    coaching_scheduler.py      — Proactive coaching (60с цикл)

  integrations/
    google/                    — Google Calendar OAuth
    vision/food_recognizer.py  — Распознавание еды по фото (OpenAI Vision)
    voice/stt.py               — Speech-to-Text (Whisper)
    voice/tts.py               — Text-to-Speech

  miniapp/                     — Telegram Mini App (React)
    src/api/                   — API клиенты
    src/features/              — Компоненты по доменам
    e2e/                       — Playwright E2E тесты

  tests/                       — Тесты
    coaching/                  — 15+ тестовых файлов коучинга
    e2e/coaching/              — E2E тесты коучинга
    factories/                 — Фабрики тестовых данных
    fakes/                     — Моки (fake_llm, fake_telegram)

  scripts/                     — Утилиты (seed, миграция)
  data/                        — Каталог продуктов EWA
  docker-compose.yml           — Инфраструктура
```

---

## 4. АРХИТЕКТУРА МАРШРУТИЗАЦИИ

### Обработка сообщений: полный pipeline

```
Telegram Message
  → Aiogram Handler (text/voice/photo/callback)
  → process_message(user_id, mode, text, force_agent?)
  → agents/supervisor.py → classify_intent()

Уровни классификации:
  0: Force Agent     — draft активен → принудительно в домен
  1: Rule-based      — keyword/regex (бесплатно, быстро)
  2: Sticky Domain   — 3-5 мин после последнего взаимодействия
  3: LLM Classifier  — gpt-4.1-nano (дешёвый, точный)

Результат → route_to_agent() → один из 8 агентов:
  nutrition | fitness | reminder | coaching | calendar | crm | team | assistant

Агент (LangGraph ReAct) → Tools → БД → Response
```

### Агенты

- **Supervisor** — gpt-4.1-nano — Классификация intent + маршрутизация
- **CoachingAgent** — gpt-4.1-mini — AI-коуч: цели, привычки, check-in, review
- **NutritionAgent** — gpt-4.1-mini — Питание: КБЖУ, draft-система, EWA продукты
- **FitnessAgent** — gpt-4.1-mini — Тренировки: логирование, программы, замеры
- **ReminderAgent** — gpt-4.1-mini — Задачи: создание, управление, напоминания
- **AssistantAgent** — gpt-4.1-mini — Общий диалог (без tools)
- **CRMAgent** — gpt-4.1-mini — CRM (только business mode)
- **TeamAgent** — gpt-4.1-mini — Управление командой (только business mode)

---

## 5. МОДЕЛЬ ДАННЫХ (основные домены)

### 5.1 Системные
- **User** — пользователь (telegram_id, mode, timezone)
- **UserProfile** — профиль (вес, рост, возраст для расчёта КБЖУ)
- **Reminder** — универсальные напоминания
- **NotificationLog** — лог уведомлений

### 5.2 Tasks и Calendar
- **Calendar** — календари пользователя
- **Task** — задача/событие (event_type: task|event, recurrence RFC 5545)

### 5.3 Nutrition
- **FoodItem** — справочник продуктов (системный + пользовательский)
- **Meal** → **MealItem** — приём пищи с позициями
- **WaterLog** — потребление воды
- **NutritionGoal** — суточные цели КБЖУ
- **FavoriteFood** — избранные продукты
- **MealTemplate** → **MealTemplateItem** — шаблоны приёмов

### 5.4 Fitness
- **ExerciseLibrary** — справочник упражнений
- **WorkoutTemplate** → **WorkoutTemplateExercise** — шаблоны тренировок
- **WorkoutSession** → **WorkoutSet** — фактические тренировки
- **WorkoutProgram** → **WorkoutProgramDay** — программы тренировок
- **BodyMetric** — замеры тела
- **PersonalRecord** — личные рекорды
- **ActivityLog** — кардио/шаги/активность
- **FitnessGoal** — фитнес-цели

### 5.5 Coaching
- **Goal** — цели с приоритетом, заморозкой, why-statement
- **GoalMilestone** — этапы цели
- **GoalCheckin** — дневные чекины (прогресс, энергия, настроение)
- **GoalReview** — недельные/месячные обзоры
- **Habit** → **HabitLog** — привычки и их выполнение
- **HabitStreak** — история стриков
- **HabitTemplate** — библиотека шаблонов привычек
- **CoachingSession** — лог сессий с коучем
- **CoachingInsight** — AI-инсайты (risk, pattern, achievement)
- **UserCoachingProfile** — настройки коуча (тон, частота nudges)
- **CoachingRecommendation** — очередь рекомендаций
- **CoachingMemory** — долгосрочная память коуча
- **BehaviorPattern** — поведенческие паттерны
- **CoachingNudgeLog** — лог proactive-сообщений (антиспам)
- **CoachingOnboardingState** — прогресс онбординга
- **CoachingDialogDraft** — черновики многошаговых диалогов
- **CoachingContextSnapshot** — ежедневные снимки контекста
- **CoachingRiskScore** — оценка рисков (dropout, overload)
- **CoachingOrchestrationAction** — действия коуча в других модулях

### 5.6 CRM
- **CrmCompany**, **CrmContact**, **CrmPipeline** → **CrmPipelineStage**, **CrmDeal**, **CrmActivity**

### 5.7 Team
- **Team** → **TeamMember**, **TeamTask**

---

## 6. COACHING — ДЕТАЛЬНОЕ ОПИСАНИЕ

### 6.1 Концепция
Coaching — не отдельный модуль, а **управляющий мета-слой** над всей экосистемой. Он интерпретирует данные из Tasks, Calendar, Nutrition, Fitness и строит целостную картину пользователя.

### 6.2 Восемь режимов работы CoachingAgent
1. **Onboarding** — знакомство, создание первой цели/привычки
2. **Daily Mode** — ежедневное общение, обновление прогресса
3. **Checkin Mode** — структурированный check-in (победы → прогресс → энергия → блокеры)
4. **Review Mode** — недельный/месячный обзор результатов
5. **Goal Creation** — 5-шаговый диалог (область → цель → «зачем» → первый шаг → дедлайн)
6. **Recovery Mode** — возвращение после паузы (без давления)
7. **Momentum Mode** — пользователь в потоке (новые вызовы)
8. **Crisis Mode** — высокий риск dropout (один вопрос + простой выбор)

### 6.3 Context Pack (динамический системный промпт)
При каждом запросе coaching_agent динамически загружает:
- Состояние пользователя (momentum/stable/overload/recovery/risk)
- Скор (0-100)
- Активные цели с прогрессом
- Привычки со стриками
- Рекомендации
- Память о пользователе (preferences, patterns)
- Инструкция по тону (адаптивная)
- Кросс-модульные выводы

### 6.4 Proactive Coaching System
- **17 триггеров** + **4 multi-signal** паттерна
- **Ритуалы:** утренний бриф, дневной чекин, вечерняя рефлексия, недельный обзор
- **Антиспам:** max_daily_nudges, тихие часы 23:00-08:00
- **Планировщик:** asyncio-task, цикл 60 секунд

### 6.5 Кросс-модульный анализ
Типы выводов: conflict, cause_effect, imbalance, overload, failure_pattern, blind_spot.
Данные из Tasks + Calendar + Fitness + Nutrition → рекомендации.

### 6.6 Coaching Handler (Telegram UX)
~1700 строк: inline-кнопки для всех coaching-операций.
Callback префиксы: `cg_g_*` (цели), `cg_h_*` (привычки), `cg_ci_*` (чекин), `cg_wr_*` (review), `cg_ob_*` (онбординг).
FSM-машина для многошаговых диалогов (goal creation, habit creation, checkin, review).

---

## 7. ОСТАЛЬНЫЕ МОДУЛИ

### 7.1 bot.py (устаревший Calendar-бот)
Отдельный standalone Telegram-бот для Google Calendar.
Содержит: regex парсинг команд, Google Calendar API, LLM-классификатор интентов, STT/TTS.
**Статус:** НЕ используется в main.py. Функциональность частично мигрирована в reminder_agent.

### 7.2 Nutrition Module
- **Draft-система:** meal_draft_create → edit → confirm/discard
- **EWA Product:** 24 специализированных продукта
- **Распознавание фото еды** через OpenAI Vision
- **Scoring:** оценка дня 0-100 по 6 компонентам
- **Follow-up:** автоматические советы

### 7.3 Fitness Module
- **Программы тренировок:** импорт текста → парсинг → программа
- **Логирование:** голосовой/текстовый ввод (формат: «жим 80x8 3»)
- **Замеры тела:** вес, талия, энергия, сон
- **Активность:** шаги, бег, велосипед, плавание

### 7.4 Reminder/Tasks Module
- CRUD задач с приоритетами и дедлайнами
- Повторяющиеся задачи (RFC 5545 RRULE)
- Уведомления за N минут до события

### 7.5 CRM Module (business mode)
- Компании, контакты, сделки, воронка продаж, активности

### 7.6 Team Module (business mode)
- Команды, участники, командные задачи

---

## 8. ФОНОВЫЕ ПРОЦЕССЫ

- **notification_scheduler** — 60с — Отправка напоминаний о задачах/событиях
- **nutrition_tips_scheduler** — 60с — Советы по питанию
- **coaching_scheduler** — 60с — Proactive coaching: триггеры + ритуалы
- **daily_personalization** — 24ч — Анализ поведенческих паттернов

---

## 9. API ENDPOINTS (FastAPI)

Базовый URL: `http://77.238.235.171/api/`

- `/api/auth` — Авторизация через Telegram initData
- `/api/tasks` — CRUD задач
- `/api/calendars` — Календари
- `/api/nutrition` — Питание, КБЖУ, вода
- `/api/fitness` — Тренировки, замеры, программы
- `/api/voice` — Голосовой ввод
- `/api/ai-coach` — Чат с AI коучем
- `/api/coaching` — Цели, привычки, чекины, обзоры, аналитика
- `/api/health` — Статус сервиса (uptime, db)

---

## 10. КОНФИГУРАЦИЯ (.env)

- `TELEGRAM_TOKEN` — Токен Telegram бота
- `OPENAI_API_KEY` — Ключ OpenAI API
- `OPENAI_LLM_MODEL` — Модель LLM (default: gpt-4o-mini)
- `OPENAI_CLASSIFIER_MODEL` — Модель классификатора (default: gpt-4.1-nano)
- `OPENAI_AGENT_MODEL` — Модель агентов (default: gpt-4.1-mini)
- `OPENAI_STT_MODEL` — Модель STT (default: gpt-4o-mini-transcribe)
- `OPENAI_TTS_MODEL` — Модель TTS (default: gpt-4o-mini-tts)
- `DATABASE_URL` — PostgreSQL connection string
- `MINIAPP_URL` — URL Mini App (для кнопки меню)
- `VOICE_REPLY_MODE` — auto/always/never
- `DEFAULT_TIMEZONE` — Europe/Moscow
- `BUSINESS_MODE_USERS` — Telegram ID через запятую

---

## 11. ЗАПУСК И РАЗВЁРТЫВАНИЕ

```bash
# Запуск бота
cd /root/ai-assistant
nohup python main.py > bot.log 2>&1 &

# Запуск инфраструктуры
docker-compose up -d  # postgres + api + nginx

# Миграции БД
alembic upgrade head
```

---

## 12. ТЕСТИРОВАНИЕ

```bash
pytest tests/              # Все тесты
pytest tests/coaching/ -v  # Coaching-тесты (15+ файлов)
pytest tests/e2e/ -v       # E2E тесты
cd miniapp && npx playwright test  # Mini App тесты
```

---

## 13. ИЗВЕСТНЫЕ ОСОБЕННОСТИ И ПОТЕНЦИАЛЬНЫЕ ПРОБЛЕМЫ

1. **bot.py vs main.py** — два бота. bot.py устаревший, не используется, не удалён.
2. **Google Calendar отключён** — calendar_agent → reminder_agent. OAuth файлы остались.
3. **Синхронная загрузка контекста в coaching_agent** — `_load_context_sync()` через ThreadPoolExecutor.
4. **In-memory SessionContext** — draft и sticky domains в памяти. При рестарте теряются.
5. **Coaching handler ~1700 строк** — крупный файл.
6. **CORS allow_origins=["*"]** — нужно ограничить в продакшене.
7. **Бот вне Docker** — запускается через nohup отдельно от docker-compose.
8. **Нет CI/CD** — GitHub Actions не настроен.

---

## 14. ФАЙЛЫ ДОКУМЕНТАЦИИ

- `docs/coaching-architecture.md` — Полная архитектура коучинга (24 раздела)
- `docs/product-architecture.md` — Доменная модель и стек
- `docs/routing-architecture.md` — Маршрутизация сообщений (v3)
- `docs/fitness-module-plan.md` — План фитнес-модуля
- `docs/nutrition-tracker.md` — Документация питания
- `docs/goals-management.md` — Управление целями
- `docs/changelog.md` — Лог изменений
- `docs/project-documentation.md` — Этот файл
