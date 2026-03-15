# Управление целями — техническая документация

> Версия: 1.0 | Дата: 2026-03-15
> Основа: coaching-architecture.md §4.1, §4.2, §7.1, §9.1, §12.2, §13.3, §13.5, §5.2

---

## 1. Концепция

Цели — центральный объект модуля коучинга. Каждая цель:
- имеет **воронку этапов** (milestones) — конкретные промежуточные точки с дедлайнами
- связана с **привычками** через `goal_id` — ежедневные действия, которые ведут к ней
- отслеживается через **прогресс** (0–100%) и **чекины** — периодические отметки состояния
- обрабатывается **коучем** — получает AI-инсайты, алерты при застревании, напоминания о дедлайне

---

## 2. Модель данных

### 2.1 Таблица `goals`

```
id              INTEGER PK
user_id         BIGINT FK → users.telegram_id
title           VARCHAR(300)       — название цели
description     TEXT               — описание (опционально)
area            VARCHAR(30)        — область: health | finance | career | personal | relationships | productivity | mindset | sport
status          VARCHAR(20)        — active | achieved | cancelled
progress_pct    INTEGER (0–100)    — текущий прогресс, обновляется вручную или по milestone'ам
target_date     DATE               — дедлайн цели
priority        VARCHAR(20)        — high | medium | low
is_frozen       BOOLEAN            — цель на паузе
frozen_reason   TEXT               — причина заморозки
first_step      TEXT               — конкретное первое действие
why_statement   TEXT               — глубинная мотивация «зачем»
coaching_notes  TEXT               — заметки коуча / личные заметки пользователя
last_coaching_at TIMESTAMPTZ       — когда коуч последний раз работал с целью
parent_goal_id  INTEGER FK → goals — для вложенных под-целей
linked_habit_ids JSONB             — list[int] id привязанных привычек (legacy, предпочтительнее habit.goal_id)
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

**Статусы цели:**

| Статус      | Описание                              | Переход из           |
|-------------|---------------------------------------|----------------------|
| `active`    | Цель активна, прогресс отслеживается  | Начальный / restart  |
| `achieved`  | Цель достигнута, прогресс = 100%      | active               |
| `cancelled` | Цель архивирована / удалена           | active / frozen      |
| `frozen`    | Цель заморожена (is_frozen=True)      | active               |

> Внимание: `frozen` — это не отдельный статус в поле `status`, а флаг `is_frozen`. Статус при заморозке остаётся `active`.

### 2.2 Таблица `goal_milestones`

```
id           INTEGER PK
goal_id      INTEGER FK → goals (CASCADE DELETE)
user_id      BIGINT FK → users.telegram_id
title        VARCHAR(300)       — название этапа
description  TEXT               — описание (опционально)
due_date     DATE               — дедлайн этапа
status       VARCHAR(20)        — pending | done | skipped
sort_order   INTEGER (0+)       — порядок отображения
completed_at TIMESTAMPTZ        — когда отмечен выполненным
created_at   TIMESTAMPTZ
```

**Логика прогресса по milestone'ам:**
- Прогресс цели = `done_count / total_count * 100` (округлённо)
- При `complete_milestone` — обновляется `progress_pct` в goals
- Milestone можно только отметить выполненным, skipped-статус доступен только через bot/API

### 2.3 Таблица `goal_checkins`

Чекины — это дневные отметки состояния. Один чекин может быть привязан к конкретной цели или быть общим (goal_id = NULL).

```
id            INTEGER PK
goal_id       INTEGER FK → goals (SET NULL при удалении)
user_id       BIGINT FK → users.telegram_id
progress_pct  INTEGER (0–100)   — субъективная оценка прогресса по цели в этот день
energy_level  INTEGER (1–5)     — уровень энергии
mood          VARCHAR(20)       — great | good | ok | tired | bad
notes         TEXT              — рефлексия, ответ на «как прошёл день»
blockers      TEXT              — что мешало
wins          TEXT              — победы
time_slot     VARCHAR(10)       — morning | midday | evening | manual
check_date    DATE              — явная дата чекина
created_at    TIMESTAMPTZ
```

### 2.4 Таблица `goal_reviews`

Weekly / monthly review по цели, генерируется ботом или вручную.

```
id            INTEGER PK
goal_id       INTEGER FK → goals
review_type   VARCHAR(20)  — weekly | monthly
summary       TEXT         — AI-генерированный или ручной итог
highlights    JSONB        — list[str] достижения
blockers      JSONB        — list[str] препятствия
next_actions  JSONB        — list[str] следующие шаги
ai_assessment TEXT         — оценка коуча
score         INTEGER      — 0–100
created_at    TIMESTAMPTZ
```

---

## 3. API-эндпоинты

### 3.1 Цели (Goals)

| Метод  | Путь                          | Описание                                      | Статус |
|--------|-------------------------------|-----------------------------------------------|--------|
| GET    | `/coaching/goals`             | Список целей (`?status=active\|achieved\|all`) | ✅     |
| POST   | `/coaching/goals`             | Создать цель                                  | ✅     |
| GET    | `/coaching/goals/{id}`        | Детали цели                                   | ✅     |
| PUT    | `/coaching/goals/{id}`        | Обновить поля (включая progress_pct)          | ✅     |
| DELETE | `/coaching/goals/{id}`        | Архивировать (status=cancelled)               | ✅     |
| POST   | `/coaching/goals/{id}/freeze` | Заморозить (is_frozen=True + frozen_reason)   | ✅     |
| POST   | `/coaching/goals/{id}/resume` | Разморозить (is_frozen=False)                 | ✅     |
| POST   | `/coaching/goals/{id}/restart`| Перезапустить (progress_pct=0, is_frozen=False) | ✅   |
| POST   | `/coaching/goals/{id}/achieve`| Отметить достигнутой (status=achieved, pct=100) | ✅  |
| GET    | `/coaching/goals/{id}/analytics` | Аналитика: checkins_count, days_without_progress | ✅ |

**Недостающие эндпоинты (Phase 2):**
- `POST /coaching/goals/{id}/generate-plan` — AI-генерация milestone'ов через LLM

### 3.2 Этапы (Milestones)

| Метод | Путь                                  | Описание                    | Статус |
|-------|---------------------------------------|-----------------------------|--------|
| GET   | `/coaching/milestones?goal_id={id}`   | Список этапов цели          | ✅     |
| POST  | `/coaching/milestones`                | Создать этап                | ✅     |
| POST  | `/coaching/milestones/{id}/complete`  | Отметить выполненным        | ✅     |

**Body для POST /milestones:**
```json
{
  "goal_id": 42,
  "title": "Пройти онлайн-курс",
  "due_date": "2026-04-15",
  "description": "Coursera: Machine Learning",
  "order_index": 1
}
```

### 3.3 Привычки, привязанные к цели

`GET /coaching/habits` поддерживает `?goal_id=` параметр на уровне storage, но **не на уровне API endpoint** (задача плана — добавить).

Текущий workaround: фильтрация на клиенте по `habit.goal_id`.

---

## 4. TypeScript-интерфейсы (frontend)

### 4.1 Goal

```typescript
interface Goal {
  id: number
  title: string
  description: string | null
  area: string | null              // health | finance | career | personal | ...
  status: 'active' | 'achieved' | 'cancelled'
  priority: number                 // 1=high, 2=medium, 3=low (в БД строки high|medium|low)
  progress_pct: number             // 0–100
  target_date: string | null       // ISO date
  why_statement: string | null
  first_step: string | null
  is_frozen: boolean
  frozen_reason: string | null
  coaching_notes: string | null
  created_at: string
  updated_at: string
  // Опциональные поля из аналитики
  milestones_completed?: number
  milestones_total?: number
  ai_insight?: string | null
}
```

### 4.2 Milestone

```typescript
interface Milestone {
  id: number
  goal_id: number
  title: string
  status: 'pending' | 'done' | 'skipped'
  due_date: string | null          // ISO date
  description: string | null
  order_index: number              // в API: sort_order
  completed_at: string | null
}
```

### 4.3 CreateGoalDto / UpdateGoalDto

```typescript
interface CreateGoalDto {
  title: string
  description?: string
  area?: string
  target_date?: string
  why_statement?: string
  first_step?: string
  priority?: number
}

interface UpdateGoalDto {
  title?: string
  area?: string
  target_date?: string | null
  why_statement?: string
  first_step?: string
  priority?: number
  progress_pct?: number            // ключевое поле для ручного обновления прогресса
  status?: string
  coaching_notes?: string
}
```

---

## 5. React Query хуки

### 5.1 Реализованные

| Хук                  | Метод              | Описание                         |
|----------------------|--------------------|----------------------------------|
| `useGoals(status?)`  | GET /goals         | Список с фильтром по статусу     |
| `useGoal(id)`        | GET /goals/{id}    | Одна цель                        |
| `useCreateGoal()`    | POST /goals        | Создать цель                     |
| `useUpdateGoal()`    | PUT /goals/{id}    | Обновить (включая progress_pct)  |
| `useFreezeGoal()`    | POST /goals/{id}/freeze | Заморозить                  |
| `useResumeGoal()`    | POST /goals/{id}/resume | Разморозить                 |
| `useAchieveGoal()`   | POST /goals/{id}/achieve | Отметить достигнутой       |
| `useMilestones(id)`  | GET /milestones?goal_id= | Список этапов             |
| `useCompleteMilestone()` | POST /milestones/{id}/complete | Отметить выполненным |

### 5.2 Отсутствующие (задача плана)

| Хук                    | Метод                        | Описание                           |
|------------------------|------------------------------|------------------------------------|
| `useCreateMilestone()` | POST /milestones             | Создать этап из UI                 |
| `useRestartGoal()`     | POST /goals/{id}/restart     | Перезапустить цель                 |
| `useHabitsByGoal(id)`  | GET /habits?goal_id=         | Привычки, привязанные к цели       |

---

## 6. Текущий UI: GoalDetailPage

Файл: `miniapp/src/features/coaching/GoalDetailPage.tsx`

### 6.1 Что отображается сейчас

- **Шапка**: название цели, кнопка «назад»
- **Блок «Зачем мне это»**: `why_statement`
- **Прогресс**: read-only прогресс-бар + «X из Y этапов»
- **Этапы**: список `milestones` — только checkbox-отметка выполнения
- **История чекинов**: последние 5, фильтр по `goal_id`
- **AI-инсайт**: если `goal.ai_insight` не пустой
- **Sticky-панель**: «Заморозить» + «Достигнуто» (active) / «Возобновить» (frozen)

### 6.2 Что скрыто / отсутствует

| Поле / функция           | Где хранится                | Почему не показывается       |
|--------------------------|-----------------------------|------------------------------|
| `target_date`            | Goal.target_date            | Не выведен в UI              |
| `first_step`             | Goal.first_step             | Не выведен в UI              |
| `frozen_reason`          | Goal.frozen_reason          | Не выведен при заморозке     |
| `coaching_notes`         | Goal.coaching_notes         | Нет поля ввода/отображения   |
| `Milestone.due_date`     | GoalMilestone.due_date      | Не выведен в списке этапов   |
| Добавление milestone     | POST /milestones ✅ в API   | Нет хука и формы в UI        |
| Обновление прогресса     | PUT /goals/{id} ✅ в API    | Нет интерактивного контрола  |
| Привязанные привычки     | Habit.goal_id ✅ в БД       | Нет секции, нет хука         |
| Кнопка «Перезапустить»   | POST /goals/{id}/restart ✅ | Нет хука `useRestartGoal`    |

---

## 7. Запланированные изменения (план 83ae6009)

### 7.1 Шапка — мета-блок цели

**До:** только название + кнопка назад.
**После:**
- Строка: `{AREA_EMOJI} {area_label}` + статус-бейдж
- Дедлайн с цветом: зелёный >30 дней, жёлтый 7–30, красный <7 или просрочен
- Плашка «🚀 Первый шаг: {first_step}» если заполнен
- Плашка «❄️ Заморожена: {frozen_reason}» если заморожена

**Цветовые статусы бейджа:**
```
active (не просрочена)  → 🟢 Активна   (#4ade80)
active (просрочена)     → 🔴 Просрочена (#f87171)
frozen                  → ❄️ Заморожена (#94a3b8)
achieved                → ✅ Достигнута (#4ade80)
```

### 7.2 Секция «Этапы» — воронка

**До:** простой список checkbox, нет дат, нет добавления.
**После:**

```
[1] ──●── Зарегистрироваться на курс        ✅ выполнено      15 мар
[2] ──●── Пройти первые 3 модуля            ○ в процессе     до 31 мар
[3] ──●── Финальный проект                  ○ ожидает        до 20 апр
         [+ Добавить этап]
```

Форма добавления (inline, раскрывается под списком):
```
[ Название этапа        ] [ Дата (опционально) ] [Добавить]
```

Если milestone'ов нет — информационный блок:
> 💡 Разбей цель на этапы — без промежуточных точек мозг откладывает.
> [Добавить первый этап]

### 7.3 Секция «Привязанные привычки»

После секции этапов — компактный список:
```
🏃 Пробежка 3×/неделю    🔥 12 дней    [✅ сегодня]
📚 Читать 20 мин         🔥 5 дней     [○ не отмечено]
                         [+ Привязать привычку]
```

### 7.4 Bottom sheet «📈 Обновить прогресс»

Открывается кнопкой в sticky-панели:
```
Прогресс по цели

[■■■■■■■░░░░░░░░] 45%

◄──────────●──────────► (слайдер 0–100, шаг 5)

Заметка (опционально):
[ Что сдвинулось? Что мешает?        ]

[ Сохранить прогресс ]
```

При progress = 100% — дополнительный вопрос:
> Цель выполнена на 100%. Отметить как достигнутую?
> [✅ Да, достигнута] [Позже]

### 7.5 Sticky-панель — полный набор кнопок

**До:**
```
[ ❄️ Заморозить ] [ 🏆 Достигнуто ]
```

**После (active):**
```
[ 📈 Прогресс ] [ ➕ Этап ] [ … ]
                               └─ [🔄 Перезапустить]
                                  [❄️ Заморозить]
                                  [🏆 Достигнуто]
```

**После (frozen):**
```
[ 📈 Прогресс ] [ ➕ Этап ] [ ▶️ Возобновить ]
```

Кнопка «🔄 Перезапустить» доступна только если `is_frozen = true` или `progress_pct > 0`. Требует подтверждения (диалог: «Сбросить прогресс цели до 0%?»).

---

## 8. Бизнес-логика прогресса

### 8.1 Два способа обновления прогресса

**Автоматический (через milestone'ы):**
- При `complete_milestone` → backend пересчитывает `progress_pct = done/total * 100`
- Работает если milestone'ы созданы

**Ручной (через bottom sheet):**
- `PUT /goals/{id}` с `{ progress_pct: N }`
- Использует `useUpdateGoal()` с полем `coaching_notes`
- Работает всегда, даже без milestone'ов

> При наличии milestone'ов рекомендуется закрывать их — тогда прогресс обновляется объективно. Ручной прогресс используется как дополнение или в случае когда milestone'ы не созданы.

### 8.2 Логика дедлайна

```
days_left = target_date - today

days_left > 30  → зелёный   «до {date} · {N} дней»
days_left 7–30  → жёлтый    «до {date} · {N} дней»
days_left 1–6   → красный   «до {date} · {N} дней»
days_left = 0   → красный   «сегодня дедлайн!»
days_left < 0   → красный   «просрочена на {|N|} дней»
```

Аналогичная логика применяется к `Milestone.due_date`.

### 8.3 Триггеры коуча по целям (§5.2)

| Триггер              | Условие                              | Приоритет |
|----------------------|--------------------------------------|-----------|
| `goal_no_progress`   | Нет обновления цели > 7 дней         | HIGH      |
| `goal_no_milestones` | Активная цель без milestone'ов       | MEDIUM    |
| `goal_no_first_step` | Цель без `first_step`                | HIGH      |
| `goal_deadline_near` | До `target_date` < 14 дней           | HIGH      |
| `goal_achieved`      | `progress_pct = 100`                 | CRITICAL  |

---

## 9. Области жизни (area)

| Ключ            | Метка          | Emoji |
|-----------------|----------------|-------|
| `health`        | Здоровье       | 💪    |
| `productivity`  | Продуктивность | ⚡    |
| `career`        | Карьера        | 🚀    |
| `finance`       | Финансы        | 💰    |
| `relationships` | Отношения      | ❤️    |
| `mindset`       | Мышление       | 🧠    |
| `sport`         | Спорт          | 🏃    |
| `personal`      | Личное         | 🌱    |

---

## 10. Работа с целями через бот

Текущие возможности через Telegram:
- «Помоги поставить цель» — создание с уточнениями (why, first_step)
- «Разбей мою цель на этапы» — генерация milestone'ов через LLM
- «Обнови прогресс по цели» — `goal_update_progress` tool
- «Заморозь цель» — `goal_freeze` tool
- Проактивный nudge при застревании > 7 дней

**Рекомендуемый flow создания цели через бот:**
1. Пользователь называет цель
2. Бот уточняет: «Зачем тебе это?» → `why_statement`
3. Бот уточняет: «К какому сроку?» → `target_date`
4. Бот предлагает первый шаг → `first_step`
5. Бот сохраняет цель и предлагает разбить на этапы
6. Пользователь открывает в Mini App для детального управления

---

## 11. Файловая структура

```
api/routers/coaching.py              — REST API (GoalOut, MilestoneCreateDto, endpoint'ы)
db/models.py                         — ORM модели Goal, GoalMilestone, GoalCheckin, GoalReview
db/coaching_storage.py               — CRUD функции (get_goals, create_milestone, complete_milestone)
miniapp/src/api/coaching.ts          — TypeScript хуки и интерфейсы
miniapp/src/features/coaching/
  GoalsPage.tsx                      — список целей, создание (форма в bottom sheet)
  GoalDetailPage.tsx                 — детальный экран (plan: полная переработка)
  components/GoalCard.tsx            — карточка цели (compact + full)
```

---

## 12. Что будет реализовано в ближайшем плане

1. Бэкенд: `GET /habits?goal_id=` — одна строка в `list_habits`
2. Три новых хука в `coaching.ts`: `useCreateMilestone`, `useRestartGoal`, `useHabitsByGoal`
3. Полная переработка `GoalDetailPage.tsx`:
   - Мета-блок: area emoji, дедлайн с цветом, first_step, frozen_reason
   - Воронка этапов с датами и inline-формой добавления
   - Секция привязанных привычек
   - Bottom sheet обновления прогресса
   - Расширенная sticky-панель: Прогресс / Этап / Перезапустить / Заморозить / Достигнуто

---

> Документ создан: 2026-03-15
> Следующий шаг: реализация плана 83ae6009 (GoalDetailPage)
