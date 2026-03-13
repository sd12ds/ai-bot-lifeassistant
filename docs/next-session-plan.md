# 📋 План действий — следующие сессии разработки

> Документ создан: 2026-03-13
> Текущее состояние: MVP всех Personal-модулей работает (Tasks, Calendar, Nutrition, Fitness).
> Стек: aiogram 3 + FastAPI + PostgreSQL + React/Vite miniapp + OpenAI gpt-4.1-mini

---

## 📊 Текущее состояние проекта

### ✅ Что уже работает
- **Бот (Telegram):** мультиагентная система (supervisor → 5 personal + 3 business агентов), smart routing (rule-based → sticky → LLM), голосовой ввод (STT/TTS), фото распознавание еды
- **Tasks & Calendar:** CRUD задач, события, календарь (месяц/неделя/день), напоминания, повторяющиеся задачи (RRULE парсер есть)
- **Nutrition:** draft-based UX, vision распознавание, КБЖУ расчёт, вода, шаблоны, клонирование, daily score, weekly summary, follow-up, альбомы фото
- **Fitness:** программы тренировок (импорт текстом, редактирование через чат), активные тренировки, история, прогресс, замеры тела, AI-коуч, рекорды, синхронизация с календарём
- **Miniapp:** 15+ страниц (задачи, календарь, питание, фитнес), dual-auth (Telegram + JWT браузер)
- **API:** FastAPI с 6 роутерами (tasks, calendars, nutrition, fitness, ai_coach, auth, voice)
- **Инфраструктура:** PostgreSQL (44 таблицы), nginx + SSL, GitHub CI

### ⚠️ Что существует но не доведено
- **Google Calendar** — интеграция написана (`integrations/google/`) но не подключена к UI/боту
- **Привычки (Habits)** — таблицы `habits` + `habit_logs` существуют, данных 0, нет UI/агента
- **Коучинг** — miniapp показывает заглушку "Coming Soon", AI-коуч есть только как API
- **Бизнес-модули** — агенты (CRM, Team, Scheduler) существуют, таблицы есть, но нет miniapp UI
- **Повторяющиеся задачи** — парсер RRULE есть (`db/recurrence.py`), но не интегрирован в UI
- **Тесты** — минимальные (3 файла), нет CI pipeline

---

## 🎯 Приоритет 1 — Стабилизация и качество (1-2 сессии)

### 1.1. Багфиксы и UX-полировка
**Файлы:** `bot/handlers/`, `miniapp/src/features/`

- [ ] **Miniapp: pull-to-refresh** — при переключении вкладок данные не обновляются (react-query staleTime)
- [ ] **Miniapp: loading states** — некоторые страницы не показывают скелетон при загрузке
- [ ] **Miniapp: error boundaries** — при ошибке API показывать toast, а не белый экран
- [ ] **Bot: таймаут LLM** — если OpenAI не отвечает >15 сек, бот молчит. Нужен fallback-ответ
- [ ] **Bot: команда /help** — обновить список команд (добавить /web, описание модулей)
- [ ] **API: rate limiting** — защита от спама (slowapi или custom middleware)
- [ ] **API: access log** — добавить `--access-log` в start_api.sh на постоянной основе
- [ ] **Fitness: валидация времени** — program_set_schedule: проверять HH:MM формат до записи в БД
- [ ] **Nutrition: draft expiry** — draft старше 30 мин нужно автоочищать

### 1.2. Автоматический деплой (CI/CD)
**Файлы:** `.github/workflows/deploy.yml`, `start_api.sh`, `Makefile`

- [ ] GitHub Actions workflow:
  - На push в main → SSH на сервер → git pull → pip install → npm build → deploy → restart
- [ ] Makefile с командами: `make deploy`, `make restart`, `make logs`
- [ ] Health-check endpoint (`GET /api/health`) с проверкой БД
- [ ] Systemd юниты для бота и API (вместо nohup)

### 1.3. Тестирование
**Файлы:** `tests/`, `miniapp/src/__tests__/`

- [ ] Backend: pytest + httpx для API endpoints (минимум: auth, tasks CRUD, nutrition CRUD)
- [ ] Frontend: vitest для критических компонентов (TaskCard, MealCard, CalorieRing)
- [ ] E2E: Playwright для основных сценариев (авторизация, создать задачу, записать приём пищи)

---

## 🎯 Приоритет 2 — Новые фичи Personal (2-3 сессии)

### 2.1. Модуль «Коучинг» (привычки + цели)
**Новые файлы:** `agents/personal/coaching_agent.py`, `tools/coaching_tools.py`, `api/routers/coaching.py`, `miniapp/src/features/coaching/`

Сейчас: таблицы `habits`, `habit_logs`, `goals` существуют но пустые. AI Coach API работает.

**Шаги:**
- [ ] `tools/coaching_tools.py` — tools: `habit_create`, `habit_log`, `habit_stats`, `goal_set`, `goal_progress`
- [ ] `agents/personal/coaching_agent.py` — промпт с контекстом привычек/целей пользователя
- [ ] `db/coaching_storage.py` — CRUD для habits + goals + streaks
- [ ] `api/routers/coaching.py` — REST: `GET/POST /habits`, `POST /habits/{id}/log`, `GET/PUT /goals`
- [ ] `miniapp/src/features/coaching/`:
  - `HabitsPage.tsx` — список привычек с прогресс-барами + streak
  - `GoalsPage.tsx` — цели с этапами (milestones)
  - `HabitLogSheet.tsx` — быстрая отметка привычки
- [ ] `intent_classifier.py` — keywords: "привычка", "цель", "трекер", "streak"
- [ ] Ежедневный reminder: "Не забудь отметить привычки 🔔"
- [ ] Интеграция с AI Coach — персонализированные советы на основе streak/целей

### 2.2. Google Calendar двусторонняя синхронизация
**Файлы:** `integrations/google/`, `api/routers/calendars.py`, `tools/calendar_tools.py`

Сейчас: `integrations/google/calendar.py` (320 строк) написана, но не подключена.

**Шаги:**
- [ ] OAuth2 flow: бот отправляет ссылку авторизации → callback сохраняет refresh_token в БД
- [ ] `api/routers/calendars.py` — эндпоинт `/calendars/google/connect`, `/calendars/google/sync`
- [ ] Двусторонний sync: task.due_datetime ↔ Google Calendar event
- [ ] Webhook или periodic sync (каждые 15 мин) для новых событий из Google
- [ ] Miniapp: кнопка "Подключить Google Calendar" в настройках
- [ ] Конфликты: если событие изменено и там и там — показывать diff пользователю

### 2.3. Повторяющиеся задачи (полная интеграция RRULE)
**Файлы:** `db/recurrence.py`, `api/routers/tasks.py`, `miniapp/src/features/tasks/`

Сейчас: парсер `parse_recurrence_nl()` и `expand_rrule()` написаны.

**Шаги:**
- [ ] API: при создании задачи с recurrence — сохранять RRULE в поле `recurrence_rule`
- [ ] API: `GET /tasks` — раскрывать RRULE в конкретные occurrence для указанного периода
- [ ] Bot: агент calendar_agent распознаёт "каждый понедельник в 9:00" → RRULE
- [ ] Miniapp: иконка 🔁 на повторяющихся задачах, редактирование правила
- [ ] Завершение occurrence: отмечать конкретный экземпляр (exception dates)

### 2.4. Расширенная аналитика
**Файлы:** `services/analytics.py`, `api/routers/analytics.py`, `miniapp/src/features/analytics/`

- [ ] Кросс-модульный дашборд:
  - Продуктивность (задачи выполнено/просрочено)
  - Питание (среднее КБЖУ за неделю/месяц, тренд)
  - Фитнес (объём, прогрессия весов, streak)
  - Привычки (completion rate, longest streak)
- [ ] API: `GET /analytics/dashboard?period=week|month`
- [ ] Miniapp: страница `/analytics` с графиками (recharts или chart.js)
- [ ] Еженедельный отчёт в бот (воскресенье вечером)

---

## 🎯 Приоритет 3 — Бизнес-модули в Miniapp (2-3 сессии)

### 3.1. CRM miniapp
**Файлы:** `miniapp/src/features/business/crm/`

Сейчас: агент `crm_agent.py` + tools `crm_tools.py` работают в чате. Таблицы: contacts, companies, deals, pipeline_stages, activities.

- [ ] `ContactsPage.tsx` — список контактов с поиском + фильтрами
- [ ] `DealsPage.tsx` — kanban-доска со стадиями воронки (drag-n-drop)
- [ ] `ContactDetailPage.tsx` — карточка контакта + история активностей
- [ ] `DealDetailPage.tsx` — карточка сделки + связанные контакты
- [ ] API: `GET/POST/PUT /crm/contacts`, `GET/POST /crm/deals`, `PUT /crm/deals/{id}/stage`

### 3.2. Team miniapp
**Файлы:** `miniapp/src/features/business/team/`

- [ ] `TeamPage.tsx` — список участников команды + их задачи
- [ ] `TeamTasksPage.tsx` — командные задачи с назначениями
- [ ] API: `GET /team/members`, `GET/POST /team/tasks`

### 3.3. Scheduler miniapp
**Файлы:** `miniapp/src/features/business/scheduler/`

- [ ] `SchedulerPage.tsx` — слоты доступности (calendar view)
- [ ] `AppointmentsPage.tsx` — список встреч
- [ ] Публичная ссылка для записи (как Calendly)

---

## 🎯 Приоритет 4 — Продвинутые фичи (по мере готовности)

### 4.1. Push-уведомления (Telegram → Web Push)
- [ ] Service Worker для miniapp
- [ ] `navigator.serviceWorker.register()` + Push API
- [ ] Backend: web-push библиотека, хранение subscription в БД
- [ ] Fallback: Telegram уведомления для тех, кто не подписался на web push

### 4.2. Экспорт данных
- [ ] `GET /export/tasks?format=csv|json`
- [ ] `GET /export/nutrition?format=csv|json`
- [ ] `GET /export/fitness?format=csv|json`
- [ ] Бот: команда `/export` → отправляет файл

### 4.3. Мультиязычность
- [ ] i18n для miniapp (react-intl или i18next)
- [ ] Агенты: определять язык пользователя, отвечать на нём

### 4.4. Настройки пользователя (miniapp)
- [ ] Страница `/settings`:
  - Часовой пояс
  - Формат времени (24h / 12h)
  - Единицы (кг/фунты, см/дюймы)
  - Google Calendar (подключить/отключить)
  - Уведомления (вкл/выкл по типам)
  - Тема (auto/dark/light)

### 4.5. Оффлайн-режим miniapp
- [ ] Service Worker + Cache API
- [ ] IndexedDB для локального кеша данных
- [ ] Sync при возврате онлайн

---

## 🔧 Технический долг

### Рефакторинг
- [ ] `db/fitness_storage.py` (1200+ строк) — разбить на модули: program_storage, session_storage, metrics_storage
- [ ] `db/nutrition_storage.py` — аналогично разбить
- [ ] `tools/fitness_tools.py` (800+ строк) — выделить program_tools, workout_tools
- [ ] `api/routers/fitness.py` (900+ строк) — разбить на sub-routers
- [ ] Типизация: добавить Pydantic response models ко всем API endpoint'ам
- [ ] Миграции: добавить Alembic auto-generate для новых таблиц

### Мониторинг и логирование
- [ ] Structured logging (JSON формат) для всех модулей
- [ ] Error tracking (Sentry или аналог)
- [ ] Метрики: количество запросов, время ответа, ошибки LLM
- [ ] Uptime monitoring (простой healthcheck каждые 5 мин)

### Безопасность
- [ ] Rate limiting на API (slowapi)
- [ ] CORS: ограничить origins (вместо `*`)
- [ ] JWT: добавить refresh token flow (access 15 мин + refresh 7 дней)
- [ ] Audit log: кто когда что изменил
- [ ] Input validation: sanitize все пользовательские данные

---

## 📝 Рекомендуемый порядок следующих сессий

**Сессия 1:** Приоритет 1.1 (багфиксы) + 1.2 (CI/CD + systemd)
**Сессия 2:** Приоритет 2.1 (Коучинг — привычки и цели)
**Сессия 3:** Приоритет 2.3 (RRULE) + 2.2 (Google Calendar)
**Сессия 4:** Приоритет 3.1 (CRM miniapp)
**Сессия 5:** Приоритет 2.4 (Аналитика) + 4.4 (Настройки)
**Сессия 6:** Приоритет 3.2-3.3 (Team + Scheduler miniapp)

---

## 🗂 Контекст для LLM-агента в новой сессии

При старте новой сессии, скажи агенту:
```
Сервер: 77.238.235.171, проект /root/ai-assistant
Стек: aiogram 3, FastAPI, PostgreSQL (docker: ai_postgres), React miniapp
Запуск API: bash /root/ai-assistant/start_api.sh
Запуск бота: /root/ai-assistant/venv/bin/python3 /root/ai-assistant/main.py
Deploy miniapp: npm run deploy (из /root/ai-assistant/miniapp)
Документация: docs/product-architecture.md, docs/next-session-plan.md
Changelog: docs/changelog.md
```
