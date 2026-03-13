# Проектирование системы задачника-календаря

## 1. Обзор системы

### Назначение
Персональный календарь и задачник, управляемый через Telegram-бота. Каждый пользователь получает изолированное пространство: свои календари, задачи, события и уведомления. Данные хранятся в собственной БД без зависимости от Google Calendar.

### Ключевые принципы
- **Clean Architecture** — domain, application, infrastructure, interface разделены
- **SOLID** — каждый модуль имеет одну ответственность, зависимости через интерфейсы
- **Масштабируемость** — SQLite сегодня, PostgreSQL без рефакторинга бизнес-логики
- **Расширяемость** — одна domain/application-модель служит Telegram-боту, Web API и future-интеграциям

---

## 2. Доменные сущности

### User (Пользователь)
Telegram-пользователь, зарегистрированный через бота.

| Поле | Тип | Описание |
|---|---|---|
| telegram_id | INTEGER PK | Уникальный идентификатор Telegram |
| username | TEXT | @username (может быть null) |
| first_name | TEXT | Имя |
| timezone | TEXT | Часовой пояс, IANA (например `Europe/Moscow`) |
| mode | TEXT | `personal` / `business` |
| notification_offset_minutes | INTEGER | За сколько минут до события присылать напоминание по умолчанию (default: 15) |
| created_at | TEXT | ISO 8601 |

### Calendar (Календарь)
У каждого пользователя минимум один calendario. Можно создавать несколько (Работа, Личное, Проекты).

| Поле | Тип | Описание |
|---|---|---|
| id | INTEGER PK | |
| user_id | INTEGER FK | → users.telegram_id |
| name | TEXT | Название: «Личный», «Работа», «Проект X» |
| color | TEXT | HEX-код цвета (#4285F4) |
| is_default | INTEGER | 1 — основной календарь пользователя |
| created_at | TEXT | |

### Event (Событие)
Запись в календаре с точным временем начала и конца.

| Поле | Тип | Описание |
|---|---|---|
| id | INTEGER PK | |
| user_id | INTEGER FK | → users (для быстрых запросов без JOIN) |
| calendar_id | INTEGER FK | → calendars |
| title | TEXT | Название события |
| description | TEXT | Описание |
| location | TEXT | Место проведения |
| start_at | TEXT | ISO 8601 с TZ: `2026-03-10T15:00:00+03:00` |
| end_at | TEXT | ISO 8601 с TZ |
| is_all_day | INTEGER | 1 — событие на весь день |
| status | TEXT | `active` / `cancelled` / `done` |
| recurrence_rule | TEXT | RRULE (RFC 5545), null если не повторяется |
| recurrence_parent_id | INTEGER | FK → events.id для исключений повторяющихся событий |
| created_at | TEXT | |
| updated_at | TEXT | |

### Task (Задача)
Персональная задача с дедлайном, приоритетом и статусом.

| Поле | Тип | Описание |
|---|---|---|
| id | INTEGER PK | |
| user_id | INTEGER FK | → users |
| calendar_id | INTEGER FK | → calendars, nullable |
| title | TEXT | Название задачи |
| description | TEXT | Подробное описание |
| priority | INTEGER | 1=Высокий, 2=Средний, 3=Низкий |
| tags | TEXT | JSON-массив тегов: `["work","urgent"]` |
| due_datetime | TEXT | Дедлайн ISO 8601, nullable |
| remind_at | TEXT | Точное время первого уведомления ISO 8601, nullable |
| status | TEXT | `todo` / `in_progress` / `done` / `cancelled` |
| recurrence_rule | TEXT | RRULE для повторяющихся задач, nullable |
| parent_task_id | INTEGER | FK → tasks.id для подзадач, nullable |
| created_at | TEXT | |
| updated_at | TEXT | |

### Reminder (Напоминание)
Запись о запланированном уведомлении. Одна задача/событие могут иметь несколько напоминаний.

| Поле | Тип | Описание |
|---|---|---|
| id | INTEGER PK | |
| user_id | INTEGER FK | → users |
| entity_type | TEXT | `task` / `event` |
| entity_id | INTEGER | ID задачи или события |
| remind_at | TEXT | ISO 8601 — точное время отправки |
| is_sent | INTEGER | 0 / 1 |
| sent_at | TEXT | Фактическое время отправки, nullable |
| telegram_message_id | INTEGER | ID отправленного сообщения (для редактирования), nullable |
| created_at | TEXT | |

### NotificationLog (Лог уведомлений)
История всех отправленных уведомлений для аудита и аналитики.

| Поле | Тип | Описание |
|---|---|---|
| id | INTEGER PK | |
| reminder_id | INTEGER FK | → reminders |
| user_id | INTEGER FK | → users |
| message_text | TEXT | Текст отправленного сообщения |
| sent_at | TEXT | |

---

## 3. Схема базы данных (DDL)

```sql
CREATE TABLE IF NOT EXISTS users (
    telegram_id               INTEGER PRIMARY KEY,
    username                  TEXT    DEFAULT '',
    first_name                TEXT    DEFAULT '',
    timezone                  TEXT    NOT NULL DEFAULT 'Europe/Moscow',
    mode                      TEXT    NOT NULL DEFAULT 'personal',
    notification_offset_min   INTEGER NOT NULL DEFAULT 15,
    created_at                TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS calendars (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    name        TEXT    NOT NULL DEFAULT 'Личный',
    color       TEXT    NOT NULL DEFAULT '#4285F4',
    is_default  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS events (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id              INTEGER NOT NULL,
    calendar_id          INTEGER NOT NULL,
    title                TEXT    NOT NULL,
    description          TEXT    DEFAULT '',
    location             TEXT    DEFAULT '',
    start_at             TEXT    NOT NULL,    -- ISO 8601 с TZ
    end_at               TEXT    NOT NULL,    -- ISO 8601 с TZ
    is_all_day           INTEGER NOT NULL DEFAULT 0,
    status               TEXT    NOT NULL DEFAULT 'active',  -- active|cancelled|done
    recurrence_rule      TEXT    DEFAULT NULL,               -- RRULE RFC 5545
    recurrence_parent_id INTEGER DEFAULT NULL,               -- FK для исключений
    created_at           TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id)              REFERENCES users(telegram_id),
    FOREIGN KEY (calendar_id)          REFERENCES calendars(id),
    FOREIGN KEY (recurrence_parent_id) REFERENCES events(id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL,
    calendar_id      INTEGER DEFAULT NULL,
    title            TEXT    NOT NULL,
    description      TEXT    DEFAULT '',
    priority         INTEGER NOT NULL DEFAULT 2,  -- 1=высокий, 2=средний, 3=низкий
    tags             TEXT    NOT NULL DEFAULT '[]',  -- JSON-массив
    due_datetime     TEXT    DEFAULT NULL,            -- ISO 8601 с TZ
    remind_at        TEXT    DEFAULT NULL,            -- ISO 8601 с TZ
    status           TEXT    NOT NULL DEFAULT 'todo', -- todo|in_progress|done|cancelled
    recurrence_rule  TEXT    DEFAULT NULL,
    parent_task_id   INTEGER DEFAULT NULL,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id)        REFERENCES users(telegram_id),
    FOREIGN KEY (calendar_id)    REFERENCES calendars(id),
    FOREIGN KEY (parent_task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS reminders (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL,
    entity_type        TEXT    NOT NULL,  -- 'task' | 'event'
    entity_id          INTEGER NOT NULL,
    remind_at          TEXT    NOT NULL,  -- ISO 8601 с TZ
    is_sent            INTEGER NOT NULL DEFAULT 0,
    sent_at            TEXT    DEFAULT NULL,
    telegram_message_id INTEGER DEFAULT NULL,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS notification_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    reminder_id  INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    message_text TEXT    NOT NULL,
    sent_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (reminder_id) REFERENCES reminders(id),
    FOREIGN KEY (user_id)     REFERENCES users(telegram_id)
);

-- Индексы для быстрых запросов планировщика
CREATE INDEX IF NOT EXISTS idx_reminders_pending
    ON reminders (is_sent, remind_at);

CREATE INDEX IF NOT EXISTS idx_tasks_user_status
    ON tasks (user_id, status, due_datetime);

CREATE INDEX IF NOT EXISTS idx_events_user_start
    ON events (user_id, start_at, status);

CREATE INDEX IF NOT EXISTS idx_calendars_user
    ON calendars (user_id, is_default);
```

### Миграция существующей БД
Поскольку БД уже содержит данные, изменения вносятся через `ALTER TABLE`:

```sql
-- Добавить поля в tasks (если не существуют)
ALTER TABLE tasks ADD COLUMN priority INTEGER NOT NULL DEFAULT 2;
ALTER TABLE tasks ADD COLUMN tags TEXT NOT NULL DEFAULT '[]';
ALTER TABLE tasks ADD COLUMN remind_at TEXT DEFAULT NULL;
ALTER TABLE tasks ADD COLUMN status TEXT NOT NULL DEFAULT 'todo';
ALTER TABLE tasks ADD COLUMN recurrence_rule TEXT DEFAULT NULL;
ALTER TABLE tasks ADD COLUMN parent_task_id INTEGER DEFAULT NULL;
ALTER TABLE tasks ADD COLUMN updated_at TEXT NOT NULL DEFAULT (datetime('now'));
-- Синхронизировать status с is_done
UPDATE tasks SET status = 'done' WHERE is_done = 1;

-- Добавить поля в users
ALTER TABLE users ADD COLUMN username TEXT DEFAULT '';
ALTER TABLE users ADD COLUMN first_name TEXT DEFAULT '';
ALTER TABLE users ADD COLUMN notification_offset_min INTEGER NOT NULL DEFAULT 15;
```

---

## 4. Архитектура сервисов (Clean Architecture)

```
ai-assistant/
├── domain/                         # Чистая доменная логика (без фреймворков)
│   ├── models/
│   │   ├── user.py                 # Датакласс User
│   │   ├── calendar.py             # Датакласс Calendar
│   │   ├── event.py                # Датакласс Event + RecurrenceExpander
│   │   ├── task.py                 # Датакласс Task
│   │   └── reminder.py             # Датакласс Reminder
│   └── interfaces/
│       ├── repositories.py         # ABC: IUserRepo, ICalendarRepo, IEventRepo, ITaskRepo, IReminderRepo
│       └── services.py             # ABC: INotificationService, ISchedulerService
│
├── application/                    # Use-cases: бизнес-логика без I/O
│   ├── task_service.py             # create, update, complete, delete, list, reschedule
│   ├── event_service.py            # create, update, cancel, list, expand_recurring
│   ├── calendar_service.py         # create_calendar, get_agenda, get_week_view
│   ├── reminder_service.py         # create_reminder, calculate_remind_at
│   └── notification_service.py     # get_pending_reminders, mark_sent
│
├── infrastructure/
│   ├── db/
│   │   ├── storage.py              # aiosqlite реализации репозиториев
│   │   ├── migrations.py           # Применение ALTER TABLE миграций
│   │   └── schema.sql              # Полный DDL (источник истины)
│   └── scheduler/
│       └── notification_scheduler.py  # APScheduler AsyncScheduler
│
├── agents/                         # LangGraph агенты (используют application-сервисы)
│   ├── personal/
│   │   ├── reminder_agent.py       # Управление задачами через LLM
│   │   └── calendar_agent.py       # Управление событиями через LLM
│   └── supervisor.py
│
├── tools/                          # @tool обёртки (вызывают application-сервисы)
│   ├── task_tools.py               # task_add, task_list, task_done, task_edit, task_remind
│   ├── event_tools.py              # event_add, event_list, event_cancel, event_reschedule
│   └── calendar_tools.py           # calendar_agenda, calendar_week
│
├── bot/
│   ├── handlers/
│   │   ├── common.py               # /start, /help, /settings
│   │   ├── task_handlers.py        # /tasks, inline-кнопки задач
│   │   ├── event_handlers.py       # /events, /today, /week
│   │   └── calendar_handlers.py    # Навигация по календарю
│   ├── keyboards/
│   │   ├── task_kb.py              # InlineKeyboard для задач
│   │   └── calendar_kb.py          # InlineKeyboard календаря
│   ├── states/
│   │   ├── task_states.py          # FSM состояния создания задачи
│   │   └── event_states.py         # FSM состояния создания события
│   └── middleware/
│       └── user_context.py         # Middleware регистрации пользователя
│
├── config.py
├── main.py
└── docs/
    └── calendar-taskmanager-design.md  # Этот файл
```

### Поток зависимостей
```
bot/handlers → agents/ → tools/ → application/services → infrastructure/db
                                                          infrastructure/scheduler
```
Domain не зависит ни от чего. Infrastructure реализует domain-интерфейсы. Application использует domain-интерфейсы (Dependency Inversion).

---

## 5. Система уведомлений

### Технология: APScheduler 4.x (AsyncScheduler)
Запускается как фоновая задача в том же asyncio event loop, что и aiogram.

### Алгоритм работы

```
main.py
  └── запускает AsyncScheduler.start_in_background()
        └── каждые 60 секунд: check_and_send_reminders(bot)
              └── SELECT * FROM reminders
                    WHERE is_sent = 0 AND remind_at <= datetime('now')
              └── для каждого reminder:
                    ├── получить задачу/событие (entity_type + entity_id)
                    ├── сформировать текст сообщения
                    ├── bot.send_message(user_id, text, reply_markup=action_kb)
                    ├── UPDATE reminders SET is_sent=1, sent_at=now, telegram_message_id=msg_id
                    └── INSERT INTO notification_log
```

### Форматы уведомлений

**Задача (за N минут до дедлайна):**
```
⏰ Напоминание о задаче
📋 Встреча с клиентом Иванов
🕐 Дедлайн: сегодня в 15:00
🔴 Приоритет: Высокий

[✅ Выполнено] [⏩ Перенести] [🗑 Удалить]
```

**Событие (за N минут до начала):**
```
📅 Событие через 15 минут
🎯 Ежеквартальный ревью
🕐 15:00 – 16:30
📍 Переговорная №2

[✅ Буду] [❌ Не смогу] [⏩ Перенести]
```

### Создание напоминаний
При добавлении задачи/события система автоматически создаёт запись в `reminders`:
- **Задача с дедлайном**: remind_at = due_datetime − notification_offset_min (настраивается пользователем, default: 15 мин)
- **Событие**: remind_at = start_at − notification_offset_min
- Пользователь может добавить **несколько напоминаний** (за 30 мин, за день, в день события в 9:00)

### Парсинг времени напоминания (dateparser)
```
«напомни за 30 минут до»     → remind_at = due_datetime - 30 min
«напомни за день до»         → remind_at = due_datetime - 24 hours
«напомни завтра в 9 утра»    → remind_at = datetime(tomorrow, 9, 0)
«через 2 часа»               → remind_at = now + 2 hours
```

---

## 6. Telegram-интерфейс

### Команды бота

| Команда | Описание |
|---|---|
| `/start` | Регистрация / приветствие |
| `/tasks` | Список активных задач |
| `/today` | Повестка дня: задачи + события |
| `/week` | Задачи и события на эту неделю |
| `/add_task [текст]` | Быстро добавить задачу |
| `/add_event [текст]` | Быстро добавить событие |
| `/events` | Список ближайших событий |
| `/calendars` | Список календарей пользователя |
| `/settings` | Настройки: таймзона, смещение напоминания |
| `/help` | Справка |

### Режим AI (основной)
Пользователь пишет естественным языком — LLM определяет интент и вызывает нужный инструмент:

```
«Добавь задачу встреча с Петровым во вторник в 14:00, напомни за час»
→ TaskAgent → task_add(title="Встреча с Петровым", due="2026-03-10T14:00+03:00")
→ reminder_service.create_reminder(remind_at=due - 60min)
→ «✅ Задача добавлена. Напомню 10.03 в 13:00»
```

### Inline-клавиатуры

**Карточка задачи:**
```
📋 Подготовить презентацию
🕐 До: 10.03 15:00 | 🔴 Высокий

[✅ Выполнить]  [✏️ Редактировать]
[⏰ Напомнить]  [↩️ Перенести]
[🗑 Удалить]
```

**Список задач (пагинация):**
```
Ваши задачи (3/12):
⬜ [5] Встреча с Петровым | до 10.03 14:00
⬜ [7] Оплатить счёт | до 11.03
⬜ [8] Купить продукты | без дедлайна

[◀ Пред]  [1/4]  [След ▶]
[+ Добавить задачу]
```

**Навигация по календарю (месяц):**
```
     ◀ Февраль 2026 ▶
Пн  Вт  Ср  Чт  Пт  Сб  Вс
                          1
 2   3  [4]  5   6   7   8    ← [4] — сегодня
 9  10  11  12  13  14  15   ● — есть события
16  17  18  [●] 20  21  22
```

### FSM: Создание задачи (пошаговый режим)

```
Состояния: CreateTask.title → CreateTask.due → CreateTask.priority → CreateTask.reminder

/add_task
  → «Введите название задачи:»
  → [пользователь вводит] «Подготовить презентацию»
  → «Дедлайн? (например: завтра в 15:00 / 10.03 / пропустить)»
  → [пользователь вводит] «10 марта в 15:00»
  → «Приоритет?» [🔴 Высокий] [🟡 Средний] [🟢 Низкий]
  → [нажимает кнопку] 🔴 Высокий
  → «Напомнить?» [За 15 мин] [За 1 час] [За день] [Своё время] [Без напоминания]
  → [нажимает] За 1 час
  → ✅ «Задача создана! Напомню 10.03 в 14:00»
```

### FSM: Создание события

```
Состояния: CreateEvent.title → CreateEvent.start → CreateEvent.end → CreateEvent.reminder

/add_event
  → «Название события:»
  → «Когда начинается?» → парсинг: «10 марта в 15:00»
  → «Когда заканчивается?» → [+1 час] [+2 часа] [Своё время]
  → «Напомнить за:» [15 мин] [30 мин] [1 час] [День]
  → ✅ «Событие добавлено в Личный календарь»
```

---

## 7. Повторяющиеся события и задачи (Recurrence)

### Формат хранения: RRULE (RFC 5545)
```
FREQ=DAILY                          → каждый день
FREQ=WEEKLY;BYDAY=MO,WE,FR          → каждые пн, ср, пт
FREQ=MONTHLY;BYMONTHDAY=1           → 1-го числа каждого месяца
FREQ=YEARLY;BYMONTH=1;BYMONTHDAY=1  → 1 января каждый год
FREQ=WEEKLY;COUNT=10                → 10 раз, еженедельно
FREQ=DAILY;UNTIL=20260401T000000Z   → до 1 апреля 2026
```

### Стратегия генерации
Инстансы повторяющихся событий **не создаются заранее** в БД. Они генерируются на лету с помощью Python-библиотеки `rrule` из пакета `python-dateutil`:

```python
from dateutil.rrule import rrulestr
from datetime import datetime

def expand_recurring(rule_str: str, dtstart: datetime, window_end: datetime):
    rule = rrulestr(rule_str, dtstart=dtstart)
    return list(rule.between(dtstart, window_end, inc=True))
```

### Модификация конкретного вхождения
Если пользователь переносит **одно конкретное** вхождение повторяющегося события:
1. Исходное событие остаётся с `recurrence_rule` нетронутым
2. В таблице `events` создаётся новая запись-исключение с `recurrence_parent_id = <оригинал>` и `start_at` = новое время
3. Планировщик исключает эту дату из оригинального RRULE при генерации (через `EXDATE`)

---

## 8. Масштабирование

### Текущее состояние: SQLite
- Подходит для < 500 одновременно активных пользователей
- Один writer — ограничение конкурентной записи
- Нет партиционирования

### Переход на PostgreSQL (без изменения бизнес-логики)
Благодаря абстракции через `domain/interfaces/repositories.py`:
1. Создать `infrastructure/db/postgres_storage.py` с реализацией тех же интерфейсов на `asyncpg` / `SQLAlchemy async`
2. Заменить реализацию в DI-контейнере (config или `main.py`)
3. Перенести DDL в Alembic-миграции

### APScheduler при горизонтальном масштабировании
Несколько инстансов бота не должны отправлять одно уведомление дважды. Решение:
- APScheduler с **PostgreSQL DataStore** — единая очередь задач
- Или: `SELECT ... FOR UPDATE SKIP LOCKED` при получении `reminders` (pessimistic lock)
- Или: Redis Lua-скрипт атомарного захвата записи

### Кеширование
- `user_settings` (timezone, offset) кешировать в памяти процесса (TTL 5 мин)
- `default_calendar_id` для пользователя кешировать на время сессии
- Горизонтальный кеш: Redis при > 1 инстанса

---

## 9. Дорожная карта расширений

### Фаза 1 (текущий спринт): Уведомления + улучшенный задачник
- Миграция схемы БД (ALTER TABLE)
- APScheduler `notification_scheduler.py`
- Поля `priority`, `tags`, `remind_at`, `status` в задачах
- Таблица `reminders` + автоматическое создание при добавлении задачи/события
- Обновление `tools/task_tools.py` с новыми полями

### Фаза 2: События и календарная навигация
- Таблица `calendars` и `events`
- `EventService`, `CalendarService`
- Inline-клавиатура навигации по месяцу
- `/today`, `/week` команды
- FSM создания события

### Фаза 3: Повторяющиеся события
- Поле `recurrence_rule` в events/tasks
- `python-dateutil` для разворачивания RRULE
- Обработка исключений (перенос одного вхождения)
- UI: «Изменить только это событие / все события»

### Фаза 4: Командные календари
- Таблица `calendar_members` (user_id, calendar_id, role: owner/editor/viewer)
- Приглашение через Telegram username или deep link
- Общие события с RSVP (Приду / Не смогу / Может быть)
- Уведомления всем участникам

### Фаза 5: Web-интерфейс
- FastAPI backend (те же domain/application слои)
- React frontend с FullCalendar.js
- JWT-аутентификация через Telegram Login Widget
- REST API: `/api/v1/tasks`, `/api/v1/events`, `/api/v1/calendars`

### Фаза 6: Аналитика и AI-планирование
- Статистика: выполнено / пропущено / перенесено
- Тепловая карта активности (GitHub-style)
- AI-предложения: «Вы часто переносите задачи на утро — переставить автоматически?»
- Умный scheduling: «Найди свободное время на 2 часа на этой неделе»

---

## 10. Технологический стек

| Слой | Технология |
|---|---|
| Язык | Python 3.11+ |
| Telegram Bot | aiogram 3.x |
| AI-агенты | LangGraph 1.x, LangChain |
| LLM | OpenAI GPT-4o-mini |
| База данных (dev) | SQLite + aiosqlite |
| База данных (prod) | PostgreSQL + asyncpg |
| Планировщик | APScheduler 4.x (AsyncScheduler) |
| Парсинг времени | dateparser + python-dateutil |
| Повторения | python-dateutil (rrule) |
| Кеш (опц.) | Redis |
| Веб (фаза 5) | FastAPI + React |

---

## 11. Зависимости для установки (Фаза 1)

```bash
pip install apscheduler python-dateutil dateparser
```

`apscheduler` — фоновый планировщик уведомлений
`python-dateutil` — разворачивание RRULE для повторяющихся событий
`dateparser` — парсинг естественного языка в datetime (уже используется в коде, но не установлен)

