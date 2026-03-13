# Personal & Business Assistant — доменная модель и архитектура продукта

## Концепция продукта
Телеграм-бот + Telegram Mini App — единая платформа для управления жизнью и бизнесом.
Два режима: **Personal** и **Business**. Расширяется модулями без переписывания ядра.

---

## Домены и модули

### Personal
- **Tasks & Calendar** — задачи, события, расписание
- **Nutrition** — контроль питания, КБЖУ, вода
- **Fitness** — тренировки, упражнения, замеры тела
- **Coaching** — цели, привычки, AI-коуч

### Business
- **CRM** — контакты, сделки, воронка, активности
- **Team** — команды, участники, командные задачи
- **Scheduler** — слоты доступности, встречи

---

## Технологический стек

### Backend
- **FastAPI** — REST API, OpenAPI схема (автогенерация TypeScript-типов для фронта)
- **PostgreSQL** — основная БД (миграция с SQLite через Alembic)
- **Alembic** — версионные миграции схемы
- **asyncpg / SQLAlchemy 2.x async** — ORM + асинхронный драйвер
- **APScheduler** — планировщик уведомлений (уже есть, адаптировать)
- **Telegram initData HMAC** — верификация подписи Mini App запросов

### Frontend (Mini App)
- **React 18 + Vite** — сборка, HMR
- **React Router v6** — навигация между разделами
- **FullCalendar** — UI календаря (месяц/неделя/день)
- **Zustand** — state management
- **TailwindCSS** — стили + адаптация под Telegram-тему
- **Telegram Web App SDK** — авторизация, тема, haptics, back button
- **TanStack Query (React Query)** — кеш и синхронизация с API

### Инфраструктура
- **Docker Compose** — бот + FastAPI + PostgreSQL + nginx
- **nginx** — reverse proxy, раздача статики Mini App
- **GitHub Actions** — CI/CD (lint + deploy)

---

## Полная схема БД (PostgreSQL)

### Системные таблицы

```sql
users
  telegram_id     BIGINT PRIMARY KEY
  mode            TEXT DEFAULT 'personal'       -- personal | business
  timezone        TEXT DEFAULT 'Europe/Moscow'
  notification_offset_min INT DEFAULT 15
  created_at      TIMESTAMPTZ DEFAULT now()

user_profiles
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users
  first_name      TEXT
  last_name       TEXT
  bio             TEXT
  avatar_url      TEXT
  updated_at      TIMESTAMPTZ DEFAULT now()

reminders                                       -- универсальные для всех доменов
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users
  entity_type     TEXT    -- task | event | habit | appointment
  entity_id       INT
  remind_at       TIMESTAMPTZ
  is_sent         BOOLEAN DEFAULT false
  sent_at         TIMESTAMPTZ
  telegram_message_id BIGINT
  created_at      TIMESTAMPTZ DEFAULT now()

notification_log
  id              SERIAL PRIMARY KEY
  reminder_id     INT REFERENCES reminders
  user_id         BIGINT REFERENCES users
  message_text    TEXT
  sent_at         TIMESTAMPTZ DEFAULT now()
```

### Домен: Tasks & Calendar

```sql
calendars
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users
  name            TEXT             -- «Личное», «Работа», «Здоровье»
  color           TEXT DEFAULT '#5B8CFF'
  is_default      BOOLEAN DEFAULT false
  created_at      TIMESTAMPTZ DEFAULT now()

tasks
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users
  calendar_id     INT REFERENCES calendars      -- опционально
  title           TEXT NOT NULL
  description     TEXT DEFAULT ''
  event_type      TEXT DEFAULT 'task'           -- task | event
  status          TEXT DEFAULT 'todo'           -- todo | in_progress | done | cancelled
  priority        INT DEFAULT 2                 -- 1 высокий, 2 обычный, 3 низкий
  tags            JSONB DEFAULT '[]'
  due_datetime    TIMESTAMPTZ                   -- для задач — дедлайн
  start_at        TIMESTAMPTZ                   -- для событий — начало
  end_at          TIMESTAMPTZ                   -- для событий — конец
  is_all_day      BOOLEAN DEFAULT false
  remind_at       TIMESTAMPTZ
  recurrence_rule TEXT                          -- RFC 5545 RRULE
  parent_task_id  INT REFERENCES tasks          -- подзадачи
  is_done         BOOLEAN DEFAULT false
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()
```

Индексы: `(user_id, is_done, due_datetime)`, `(user_id, start_at)`, `(calendar_id)`

### Домен: Nutrition

```sql
food_items                                      -- справочник продуктов
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users       -- NULL = системный справочник
  name            TEXT NOT NULL
  calories        REAL                          -- ккал на 100г
  protein_g       REAL
  fat_g           REAL
  carbs_g         REAL
  fiber_g         REAL
  barcode         TEXT                          -- для сканирования штрихкода
  created_at      TIMESTAMPTZ DEFAULT now()

meals                                           -- приём пищи
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users
  meal_type       TEXT    -- breakfast | lunch | dinner | snack
  eaten_at        TIMESTAMPTZ
  notes           TEXT DEFAULT ''
  created_at      TIMESTAMPTZ DEFAULT now()

meal_items                                      -- состав приёма пищи
  id              SERIAL PRIMARY KEY
  meal_id         INT REFERENCES meals ON DELETE CASCADE
  food_item_id    INT REFERENCES food_items
  amount_g        REAL NOT NULL

water_logs
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users
  amount_ml       INT NOT NULL
  logged_at       TIMESTAMPTZ DEFAULT now()

nutrition_goals                                 -- суточные цели пользователя
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users UNIQUE
  calories        INT
  protein_g       INT
  fat_g           INT
  carbs_g         INT
  water_ml        INT DEFAULT 2000
  updated_at      TIMESTAMPTZ DEFAULT now()
```

### Домен: Fitness

```sql
exercise_library                               -- справочник упражнений
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users      -- NULL = системный справочник
  name            TEXT NOT NULL
  category        TEXT    -- strength | cardio | flexibility | sport
  muscle_group    TEXT    -- chest | back | legs | shoulders | arms | core | full_body
  description     TEXT DEFAULT ''
  created_at      TIMESTAMPTZ DEFAULT now()

workout_templates                              -- шаблоны тренировок
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users
  name            TEXT NOT NULL
  description     TEXT DEFAULT ''
  created_at      TIMESTAMPTZ DEFAULT now()

workout_template_exercises                     -- упражнения в шаблоне
  id              SERIAL PRIMARY KEY
  template_id     INT REFERENCES workout_templates ON DELETE CASCADE
  exercise_id     INT REFERENCES exercise_library
  sets            INT DEFAULT 3
  reps            INT
  weight_kg       REAL
  duration_sec    INT              -- для кардио
  rest_sec        INT DEFAULT 60
  sort_order      INT DEFAULT 0

workout_sessions                               -- фактические тренировки
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users
  template_id     INT REFERENCES workout_templates
  name            TEXT
  started_at      TIMESTAMPTZ
  ended_at        TIMESTAMPTZ
  notes           TEXT DEFAULT ''
  created_at      TIMESTAMPTZ DEFAULT now()

workout_sets                                   -- подходы внутри тренировки
  id              SERIAL PRIMARY KEY
  session_id      INT REFERENCES workout_sessions ON DELETE CASCADE
  exercise_id     INT REFERENCES exercise_library
  set_num         INT
  reps            INT
  weight_kg       REAL
  duration_sec    INT
  is_personal_record BOOLEAN DEFAULT false

body_metrics                                   -- замеры тела
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users
  weight_kg       REAL
  body_fat_pct    REAL
  muscle_mass_kg  REAL
  chest_cm        REAL
  waist_cm        REAL
  hips_cm         REAL
  logged_at       TIMESTAMPTZ DEFAULT now()
```

### Домен: Coaching

```sql
goals                                          -- цели пользователя
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users
  title           TEXT NOT NULL
  description     TEXT DEFAULT ''
  area            TEXT    -- health | finance | career | personal | relationships
  target_date     DATE
  status          TEXT DEFAULT 'active'        -- active | achieved | cancelled
  progress_pct    INT DEFAULT 0
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()

habits                                         -- трекер привычек
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users
  title           TEXT NOT NULL
  description     TEXT DEFAULT ''
  area            TEXT    -- health | productivity | mindset | sport
  frequency       TEXT DEFAULT 'daily'         -- daily | weekly | custom
  target_count    INT DEFAULT 1
  color           TEXT DEFAULT '#5B8CFF'
  is_active       BOOLEAN DEFAULT true
  created_at      TIMESTAMPTZ DEFAULT now()

habit_logs                                     -- факт выполнения привычки
  id              SERIAL PRIMARY KEY
  habit_id        INT REFERENCES habits ON DELETE CASCADE
  user_id         BIGINT REFERENCES users
  logged_at       TIMESTAMPTZ DEFAULT now()
  value           INT DEFAULT 1                -- количество (стаканы воды и т.п.)
  notes           TEXT DEFAULT ''
```

### Домен: CRM (расширение текущего)

```sql
crm_companies
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users
  name            TEXT NOT NULL
  industry        TEXT
  website         TEXT
  notes           TEXT DEFAULT ''
  created_at      TIMESTAMPTZ DEFAULT now()

crm_contacts                                   -- расширение текущей таблицы
  + company_id    INT REFERENCES crm_companies
  + position      TEXT DEFAULT ''
  + telegram      TEXT DEFAULT ''
  + tags          JSONB DEFAULT '[]'

crm_pipelines                                  -- воронки продаж
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users
  name            TEXT NOT NULL
  is_default      BOOLEAN DEFAULT false

crm_pipeline_stages
  id              SERIAL PRIMARY KEY
  pipeline_id     INT REFERENCES crm_pipelines ON DELETE CASCADE
  name            TEXT NOT NULL
  sort_order      INT DEFAULT 0
  color           TEXT

crm_deals                                      -- расширение текущей таблицы
  + pipeline_id   INT REFERENCES crm_pipelines
  + stage_id      INT REFERENCES crm_pipeline_stages
  + company_id    INT REFERENCES crm_companies
  + currency      TEXT DEFAULT 'RUB'
  + expected_close DATE
  + updated_at    TIMESTAMPTZ DEFAULT now()

crm_activities                                 -- активности по контакту/сделке
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users
  contact_id      INT REFERENCES crm_contacts
  deal_id         INT REFERENCES crm_deals
  type            TEXT    -- call | meeting | email | note | task
  description     TEXT NOT NULL
  happened_at     TIMESTAMPTZ DEFAULT now()
```

### Домен: Team

```sql
teams
  id              SERIAL PRIMARY KEY
  owner_id        BIGINT REFERENCES users
  name            TEXT NOT NULL
  description     TEXT DEFAULT ''
  created_at      TIMESTAMPTZ DEFAULT now()

team_members
  id              SERIAL PRIMARY KEY
  team_id         INT REFERENCES teams ON DELETE CASCADE
  user_id         BIGINT REFERENCES users
  role            TEXT DEFAULT 'member'        -- owner | admin | member
  joined_at       TIMESTAMPTZ DEFAULT now()

team_tasks
  id              SERIAL PRIMARY KEY
  team_id         INT REFERENCES teams
  created_by      BIGINT REFERENCES users
  assignee_id     BIGINT REFERENCES users
  title           TEXT NOT NULL
  description     TEXT DEFAULT ''
  status          TEXT DEFAULT 'todo'
  priority        INT DEFAULT 2
  due_datetime    TIMESTAMPTZ
  created_at      TIMESTAMPTZ DEFAULT now()
```

### Домен: Scheduler

```sql
availability_slots                             -- слоты доступности
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users
  day_of_week     INT              -- 0=пн ... 6=вс
  start_time      TIME
  end_time        TIME
  is_active       BOOLEAN DEFAULT true

appointments                                   -- встречи/созвоны
  id              SERIAL PRIMARY KEY
  user_id         BIGINT REFERENCES users
  contact_id      INT REFERENCES crm_contacts
  title           TEXT NOT NULL
  description     TEXT DEFAULT ''
  start_at        TIMESTAMPTZ
  end_at          TIMESTAMPTZ
  location        TEXT DEFAULT ''
  status          TEXT DEFAULT 'scheduled'     -- scheduled | done | cancelled
  created_at      TIMESTAMPTZ DEFAULT now()
```

---

## Структура репозитория (монорепо)

```
ai-assistant/
├── bot/                    # Текущий aiogram-бот (сохраняется)
├── api/                    # FastAPI backend
│   ├── routers/
│   │   ├── tasks.py
│   │   ├── nutrition.py
│   │   ├── fitness.py
│   │   ├── coaching.py
│   │   ├── crm.py
│   │   ├── team.py
│   │   └── scheduler.py
│   ├── models/             # SQLAlchemy модели
│   ├── schemas/            # Pydantic схемы
│   ├── services/           # Бизнес-логика
│   ├── deps.py             # Auth, db session
│   └── main.py
├── miniapp/                # React фронтенд
│   └── src/
│       ├── features/
│       │   ├── calendar/
│       │   ├── nutrition/
│       │   ├── fitness/
│       │   ├── coaching/
│       │   └── business/
│       │       ├── crm/
│       │       ├── team/
│       │       └── scheduler/
│       ├── shared/
│       └── App.tsx
├── db/
│   ├── migrations/         # Alembic миграции
│   ├── models.py           # SQLAlchemy модели (shared)
│   └── storage.py          # Текущий слой (постепенно заменяется)
├── docker-compose.yml
└── nginx.conf
```

---

## Навигация Mini App

```
Нижний таббар: [Личное] [Бизнес]

Личное:                     Бизнес:
  📅 Календарь/Задачи         👥 CRM
  🥗 Питание                  👨‍💼 Команда
  💪 Тренировки               📆 Планировщик
  🎯 Коучинг
```

---

## Стратегия миграции с SQLite

1. PostgreSQL + Docker Compose рядом с ботом
2. SQLAlchemy модели по новой схеме + Alembic
3. Скрипт переноса данных: SQLite → PostgreSQL
4. Переключить бот (storage.py → SQLAlchemy)
5. Запустить FastAPI поверх той же БД
6. Деплой Mini App

> Бот работает без остановки — SQLite активен до финального переключения.

---

## Поэтапный план реализации

**Этап 1 — Фундамент**
- PostgreSQL + Docker Compose
- Alembic + миграция схемы
- FastAPI с авторизацией через Telegram initData
- Перенос текущих данных (users, tasks, crm)

**Этап 2 — Mini App scaffold**
- React + Vite + Tailwind + роутинг
- Авторизация через Telegram SDK
- Раздел Задачи/Календарь (первый рабочий раздел)

**Этап 3 — Personal модули**
- Питание (КБЖУ-трекер)
- Тренировки
- Коучинг (цели + привычки)

**Этап 4 — Business модули**
- CRM с воронкой
- Команда
- Планировщик встреч

**Этап 5 — Полировка**
- Push-уведомления
- Повторяющиеся события (RRULE)
- Экспорт данных
- Аналитика и дашборд
