# AI Coaching System — Full Architecture & Development Plan

> Версия: 1.0 | Дата: 2026-03-14
> Проект: Personal & Business Assistant
> Уровень: Senior Product Architect + AI Systems Architect + Conversational UX Architect

---

## СОДЕРЖАНИЕ

1. Концепция и принципы
2. Coaching как управляющий мета-слой
3. Архитектура системы (слои)
4. Модель данных — новые таблицы
5. Proactive Coaching System
6. AI-Coach Logic
7. Tools для агента
8. Chat-first управление и Telegram UX
9. Interactive Telegram Coaching UX (кнопки)
10. User Guidance / Onboarding / Coaching Prompt Education
11. Question Templates / Example Interactions
12. Semi-Educational Coaching Layer
13. Mini App UX/UI Architecture
14. API Layer
15. Cross-Module Intelligence Layer
16. Whole-User State Model
17. Cross-Module Recommendation Engine
18. Context-aware Proactive Coaching
19. Adaptive Personalization Layer
20. Уведомления и ритуалы
21. Интеграции с другими модулями
22. Аналитика и инсайты
23. Этапы реализации (10 фаз)
24. Definition of Done

---

## 1. КОНЦЕПЦИЯ И ПРИНЦИПЫ

### 1.1 Что такое Coaching в этом продукте

Coaching — не раздел «целей и привычек». Это **верхний управляющий интеллектуальный слой** над всей Personal-экосистемой ассистента. Он не хранит данные сам по себе — он **интерпретирует, синтезирует, оркестрирует и направляет** данные из всех модулей: Tasks, Calendar, Nutrition, Fitness, Reminders.

Аналогия: если Tasks — это список дел, Calendar — расписание, Nutrition — дневник питания, Fitness — трекер тренировок, то Coaching — это **личный исполнительный директор**, который смотрит на картину целиком и говорит: «вот где ты сейчас, вот куда движешься, вот что нужно изменить сегодня».

### 1.2 Ключевые принципы

**Proactive-first.** Коуч не ждёт, пока пользователь сам что-то спросит. Он инициирует диалог на основе контекста.

**Conversational-first.** Всё управление доступно через естественный язык в Telegram-чате. Mini App — визуальное дополнение, а не замена чата.

**Context-aware.** Каждое решение коуча основывается на агрегированных сигналах из всех модулей, а не только из goals/habits.

**Non-intrusive.** Бот умеет давить, но умеет и молчать. Проактивность ограничена правилами антиспама и учитывает контекст дня пользователя.

**Adaptive.** Стиль, тон, частота, глубина сообщений адаптируются под поведенческий профиль пользователя.

**Educational by design.** Коуч обучает пользователя работе с системой не через инструкции, а через контекстуальные подсказки в процессе использования.

---

## 2. COACHING КАК УПРАВЛЯЮЩИЙ МЕТА-СЛОЙ

### 2.1 Позиция в архитектуре продукта

```
┌─────────────────────────────────────────────────────────┐
│                  COACHING LAYER (мета-слой)             │
│  Анализ · Интерпретация · Рекомендации · Оркестрация    │
└────────────┬──────────┬──────────┬──────────┬───────────┘
             │          │          │          │
        ┌────▼───┐ ┌────▼───┐ ┌───▼────┐ ┌───▼────┐
        │ Tasks  │ │ Nutr.  │ │Fitness │ │Calendar│
        └────────┘ └────────┘ └────────┘ └────────┘
```

Coaching не является одним из модулей наравне с остальными. Он **надстраивается поверх** них и использует их данные для построения целостной картины.

### 2.2 Роли коуча

- **Аналитик**: видит паттерны, которые пользователь не замечает
- **Интерпретатор**: объясняет, почему что-то не работает
- **Планировщик**: строит реальный план с учётом контекста всей жизни
- **Мотиватор**: поддерживает, не занудствуя
- **Коректор**: предлагает снизить нагрузку или усилить темп на основе сигналов
- **Оркестратор**: инициирует действия в других модулях
- **Учитель**: обучает пользователя лучше работать с системой

### 2.3 Что коуч НЕ делает

- Не генерирует бессмысленную мотивацию ("ты молодец, продолжай!")
- Не игнорирует контекст других модулей при рекомендациях
- Не создаёт новые задачи/события без подтверждения пользователя
- Не пушит уведомления, если пользователь перегружен
- Не строит планы, которые физически невозможно выполнить при текущем расписании

---

## 3. АРХИТЕКТУРА СИСТЕМЫ — СЛОИ

### 3.1 Полная схема слоёв

```
┌──────────────────────────────────────────────────────────────┐
│  COACHING ENGINE                                             │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 1. Coaching Input Layer                             │    │
│  │    Telegram chat · Mini App · Proactive triggers    │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────┐    │
│  │ 2. Goal & Habit Context Layer                       │    │
│  │    Загрузка целей, привычек, streak, milestones     │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────┐    │
│  │ 3. Cross-Module Intelligence Layer                  │    │
│  │    Tasks · Calendar · Nutrition · Fitness signals   │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────┐    │
│  │ 4. Whole-User State Computation                     │    │
│  │    daily_state · risk_state · momentum_state        │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────┐    │
│  │ 5. Coaching Intent Resolution                       │    │
│  │    Routing: chat · proactive · review · check-in   │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────┐    │
│  │ 6. Coaching Action Layer                            │    │
│  │    Tools · LLM-генерация · Confirmed actions        │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────┐    │
│  │ 7. Recommendation & Guidance Layer                  │    │
│  │    Cross-module рекомендации · Следующий шаг        │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────┐    │
│  │ 8. Reflection & Review Layer                        │    │
│  │    Daily check-in · Weekly review · Monthly reset   │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────┐    │
│  │ 9. Proactive Trigger Layer                          │    │
│  │    APScheduler · Event-driven triggers · Nudges     │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────┐    │
│  │ 10. Adaptive Personalization Layer                  │    │
│  │     Memory · Behavioral profile · Tone adaptation  │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Файловая структура

```
agents/personal/coaching_agent.py         # Основной LangGraph агент
tools/coaching_tools.py                   # Все инструменты агента
tools/coaching_context_tools.py           # Cross-module контекст
db/coaching_storage.py                    # Storage layer
services/coaching_engine.py               # Бизнес-логика, вычисление состояний
services/coaching_proactive.py            # Proactive trigger engine
services/coaching_personalization.py      # Personalization layer
services/coaching_recommendations.py      # Recommendation engine
api/routers/coaching.py                   # FastAPI router
miniapp/src/features/coaching/            # UI
  CoachingDashboard.tsx
  GoalsPage.tsx
  GoalDetailPage.tsx
  HabitsPage.tsx
  CheckInPage.tsx
  WeeklyReviewPage.tsx
  InsightsPage.tsx
  OnboardingPage.tsx
  RecommendationsPage.tsx
  components/
    GoalCard.tsx
    HabitCard.tsx
    StreakWidget.tsx
    StateIndicator.tsx
    QuickActionSheet.tsx
    CoachPromptBubble.tsx
    WeeklyScoreCard.tsx
```

---

## 4. МОДЕЛЬ ДАННЫХ — НОВЫЕ ТАБЛИЦЫ

### 4.1 Расширение существующих таблиц

**goals** — добавить поля:
- `priority` INT DEFAULT 2 (1=critical, 2=normal, 3=low)
- `is_frozen` BOOLEAN DEFAULT false
- `frozen_reason` TEXT
- `parent_goal_id` INT REFERENCES goals (для под-целей)
- `linked_habit_ids` INT[] (массив привязанных привычек)
- `first_step` TEXT (конкретное первое действие)
- `why_statement` TEXT (мотивация «зачем»)
- `coaching_notes` TEXT (заметки коуча)
- `last_coaching_at` TIMESTAMPTZ

**habits** — добавить поля:
- `goal_id` INT REFERENCES goals (к какой цели привязана)
- `cue` TEXT (триггер-якорь привычки)
- `reward` TEXT (вознаграждение)
- `best_time` TEXT (утро/день/вечер/custom)
- `difficulty` INT DEFAULT 2 (1-5)
- `current_streak` INT DEFAULT 0
- `longest_streak` INT DEFAULT 0
- `total_completions` INT DEFAULT 0
- `last_logged_at` TIMESTAMPTZ

### 4.2 Новые таблицы

#### goal_milestones
**Назначение**: разбивка цели на конкретные этапы с дедлайнами.
```sql
id              SERIAL PRIMARY KEY
goal_id         INT REFERENCES goals ON DELETE CASCADE
user_id         BIGINT REFERENCES users
title           TEXT NOT NULL
description     TEXT DEFAULT ''
target_date     DATE
status          TEXT DEFAULT 'pending'   -- pending | done | skipped
order_index     INT DEFAULT 0
completed_at    TIMESTAMPTZ
created_at      TIMESTAMPTZ DEFAULT now()
```
**Связи**: goal → milestones (1:many). Каждый milestone может быть превращён в Task.
**Продуктовая роль**: ключевой инструмент для разбиения большой цели на реальные этапы. Без milestones цель висит абстрактно.

#### goal_checkins
**Назначение**: периодические отметки прогресса по цели.
```sql
id              SERIAL PRIMARY KEY
goal_id         INT REFERENCES goals ON DELETE CASCADE
user_id         BIGINT REFERENCES users
progress_pct    INT
energy_level    INT   -- 1-5
notes           TEXT DEFAULT ''
blockers        TEXT DEFAULT ''   -- что мешает
wins            TEXT DEFAULT ''   -- что получилось
logged_at       TIMESTAMPTZ DEFAULT now()
```
**Продуктовая роль**: фиксирует субъективный прогресс + контекст. Используется коучем для анализа динамики и выявления паттернов блокеров.

#### goal_reviews
**Назначение**: weekly/monthly review по цели.
```sql
id              SERIAL PRIMARY KEY
goal_id         INT REFERENCES goals ON DELETE CASCADE
user_id         BIGINT REFERENCES users
period_type     TEXT   -- weekly | monthly
period_start    DATE
period_end      DATE
summary         TEXT   -- AI-generated или ручной
highlights      JSONB  -- массив строк: достижения
blockers        JSONB  -- массив строк: препятствия
adjustments     TEXT   -- что скорректировать
next_actions    JSONB  -- массив: конкретные следующие шаги
ai_assessment   TEXT   -- оценка прогресса от коуча
score           INT    -- 1-10: насколько продвинулись
created_at      TIMESTAMPTZ DEFAULT now()
```

#### habit_streaks
**Назначение**: детальная аналитика стриков привычек.
```sql
id              SERIAL PRIMARY KEY
habit_id        INT REFERENCES habits ON DELETE CASCADE
user_id         BIGINT REFERENCES users
streak_start    DATE
streak_end      DATE   -- NULL если активный
length          INT DEFAULT 0
broken_at       DATE
break_reason    TEXT DEFAULT ''
is_current      BOOLEAN DEFAULT false
```
**Продуктовая роль**: история стриков помогает анализировать паттерны срывов, определять опасные периоды, персонализировать напоминания.

#### habit_templates
**Назначение**: библиотека готовых привычек для быстрого старта.
```sql
id              SERIAL PRIMARY KEY
title           TEXT NOT NULL
description     TEXT
area            TEXT   -- health | productivity | mindset | sport
frequency       TEXT DEFAULT 'daily'
target_count    INT DEFAULT 1
difficulty      INT DEFAULT 2   -- 1-5
cue             TEXT   -- рекомендуемый триггер
reward          TEXT   -- рекомендуемое вознаграждение
best_time       TEXT
icon            TEXT
is_system       BOOLEAN DEFAULT true   -- системный или пользовательский
tags            TEXT[]
use_count       INT DEFAULT 0
```

#### coaching_sessions
**Назначение**: лог всех коучинговых диалогов для аналитики.
```sql
id              SERIAL PRIMARY KEY
user_id         BIGINT REFERENCES users
session_type    TEXT   -- chat | proactive | checkin | review | onboarding
started_at      TIMESTAMPTZ DEFAULT now()
ended_at        TIMESTAMPTZ
intent          TEXT   -- goal_creation | habit_log | review | motivation | etc
outcome         TEXT   -- created | updated | completed | abandoned
entities        JSONB  -- { goal_id, habit_id, milestone_id }
user_satisfaction INT  -- 1-5, если пользователь оценил
```

#### coaching_insights
**Назначение**: хранение AI-сгенерированных инсайтов о пользователе.
```sql
id              SERIAL PRIMARY KEY
user_id         BIGINT REFERENCES users
insight_type    TEXT   -- dropout_risk | pattern | recommendation | achievement
title           TEXT
body            TEXT
severity        TEXT DEFAULT 'info'   -- info | warning | critical
source_modules  TEXT[]   -- ['fitness', 'tasks', 'nutrition']
is_read         BOOLEAN DEFAULT false
is_actioned     BOOLEAN DEFAULT false
action_taken    TEXT
valid_until     TIMESTAMPTZ
created_at      TIMESTAMPTZ DEFAULT now()
```

#### user_coaching_profile
**Назначение**: настройки и персональный профиль взаимодействия с коучем.
```sql
id              SERIAL PRIMARY KEY
user_id         BIGINT REFERENCES users UNIQUE
coach_tone      TEXT DEFAULT 'balanced'  -- soft | balanced | direct | harsh
coaching_mode   TEXT DEFAULT 'guided'    -- autonomous | guided | minimal
preferred_checkin_time TEXT DEFAULT 'evening'
preferred_review_day   TEXT DEFAULT 'sunday'
morning_brief_enabled  BOOLEAN DEFAULT true
evening_reflection_enabled BOOLEAN DEFAULT true
max_daily_nudges INT DEFAULT 3
onboarding_completed BOOLEAN DEFAULT false
onboarding_step TEXT DEFAULT 'welcome'
focus_areas     TEXT[]   -- ['fitness', 'productivity', 'health']
coaching_style_inferred TEXT   -- auto-determined from behavior
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
```

#### coaching_recommendations
**Назначение**: очередь рекомендаций коуча (сгенерированных, ожидающих показа).
```sql
id              SERIAL PRIMARY KEY
user_id         BIGINT REFERENCES users
rec_type        TEXT   -- next_step | adjust_goal | habit_suggestion | schedule_fix | etc
priority        INT DEFAULT 5   -- 1 highest
title           TEXT
body            TEXT
action_type     TEXT   -- create_task | update_goal | reschedule | adjust_habit | etc
action_payload  JSONB
source_modules  TEXT[]
shown_at        TIMESTAMPTZ
acted_on        BOOLEAN DEFAULT false
dismissed       BOOLEAN DEFAULT false
expires_at      TIMESTAMPTZ
created_at      TIMESTAMPTZ DEFAULT now()
```

#### coaching_memory
**Назначение**: долгосрочная память коуча о пользователе (не история чата, а выводы).
```sql
id              SERIAL PRIMARY KEY
user_id         BIGINT REFERENCES users
memory_type     TEXT   -- preference | pattern | blocker | motivation | correction
key             TEXT   -- уникальный ключ памяти (e.g. 'morning_person', 'drops_mondays')
value           TEXT   -- значение/описание
confidence      FLOAT DEFAULT 0.5   -- 0.0 - 1.0
evidence_count  INT DEFAULT 1
last_confirmed_at TIMESTAMPTZ
is_explicit     BOOLEAN DEFAULT false   -- явно сказал или выведено
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
```

#### behavior_patterns
**Назначение**: выявленные паттерны поведения пользователя.
```sql
id              SERIAL PRIMARY KEY
user_id         BIGINT REFERENCES users
pattern_type    TEXT   -- dropout | overcommit | time_preference | energy_pattern | etc
description     TEXT
frequency       TEXT   -- always | often | sometimes
affected_areas  TEXT[]
first_detected_at TIMESTAMPTZ
last_seen_at    TIMESTAMPTZ
occurrence_count INT DEFAULT 1
is_active       BOOLEAN DEFAULT true
```

#### coaching_nudges_log
**Назначение**: лог отправленных proactive-сообщений для управления частотой.
```sql
id              SERIAL PRIMARY KEY
user_id         BIGINT REFERENCES users
nudge_type      TEXT   -- daily_checkin | habit_reminder | goal_stuck | weekly_review | etc
content_preview TEXT
channel         TEXT DEFAULT 'telegram'
sent_at         TIMESTAMPTZ DEFAULT now()
opened          BOOLEAN DEFAULT false
acted_on        BOOLEAN DEFAULT false
response_type   TEXT   -- positive | negative | ignored
```

#### coaching_onboarding_state
**Назначение**: состояние онбординга пользователя в модуле.
```sql
id              SERIAL PRIMARY KEY
user_id         BIGINT REFERENCES users UNIQUE
current_step    TEXT DEFAULT 'welcome'
steps_completed TEXT[] DEFAULT '{}'
first_goal_created BOOLEAN DEFAULT false
first_habit_created BOOLEAN DEFAULT false
first_checkin_done BOOLEAN DEFAULT false
first_review_done BOOLEAN DEFAULT false
profile_configured BOOLEAN DEFAULT false
started_at      TIMESTAMPTZ DEFAULT now()
completed_at    TIMESTAMPTZ
```

#### coaching_dialog_drafts
**Назначение**: черновики незавершённых диалогов (цель создаётся в несколько сообщений).
```sql
id              SERIAL PRIMARY KEY
user_id         BIGINT REFERENCES users
draft_type      TEXT   -- goal | habit | checkin | review
payload         JSONB   -- накопленные данные
step            TEXT   -- текущий шаг диалога
expires_at      TIMESTAMPTZ
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
```

#### coaching_context_snapshots
**Назначение**: периодические снимки состояния пользователя для cross-module анализа.
```sql
id              SERIAL PRIMARY KEY
user_id         BIGINT REFERENCES users
snapshot_date   DATE
tasks_overdue   INT DEFAULT 0
tasks_completed_today INT DEFAULT 0
calendar_events_today INT DEFAULT 0
free_slots_today INT DEFAULT 0
habits_done_today INT DEFAULT 0
habits_total_today INT DEFAULT 0
nutrition_logged BOOLEAN DEFAULT false
fitness_logged   BOOLEAN DEFAULT false
active_goals    INT DEFAULT 0
stuck_goals     INT DEFAULT 0   -- цели без прогресса >7 дней
streak_at_risk  INT DEFAULT 0   -- привычки с streak >= 3 без лога сегодня
overall_state   TEXT   -- momentum | stable | overload | recovery | risk
computed_at     TIMESTAMPTZ DEFAULT now()
```

#### coaching_risk_scores
**Назначение**: динамические оценки рисков (срыв, перегруз, выпадение).
```sql
id              SERIAL PRIMARY KEY
user_id         BIGINT REFERENCES users
risk_type       TEXT   -- dropout | overload | goal_failure | habit_death
score           FLOAT   -- 0.0 - 1.0
factors         JSONB   -- список факторов с весами
recommended_action TEXT
computed_at     TIMESTAMPTZ DEFAULT now()
```

#### coaching_orchestration_actions
**Назначение**: лог действий, инициированных коучем в других модулях.
```sql
id              SERIAL PRIMARY KEY
user_id         BIGINT REFERENCES users
action_type     TEXT   -- create_task | create_event | update_reminder | etc
target_module   TEXT   -- tasks | calendar | fitness | nutrition
payload         JSONB
status          TEXT DEFAULT 'pending'   -- pending | confirmed | executed | rejected
coaching_insight_id INT REFERENCES coaching_insights
initiated_at    TIMESTAMPTZ DEFAULT now()
confirmed_at    TIMESTAMPTZ
executed_at     TIMESTAMPTZ
```

---

## 5. PROACTIVE COACHING SYSTEM

### 5.1 Философия проактивности

Проактивный коуч — это не «напоминалка по расписанию». Это **контекстно-осознанная система**, которая анализирует сигналы из всей экосистемы и решает: когда и как вмешаться, чтобы это было полезным, а не раздражающим.

**Три режима проактивности:**
- **Ритуальный**: предсказуемые, ожидаемые события (утренний бриф, вечерний check-in, Sunday review)
- **Событийный**: реакция на конкретные триггеры из данных
- **Превентивный**: упреждение проблем до их наступления

### 5.2 Trigers — полный реестр

| Триггер | Условие | Тип сообщения | Приоритет |
|---|---|---|---|
| goal_no_progress | Нет обновления цели > 7 дней | goal_stuck | HIGH |
| habit_dying | Streak привычки 3+ дня без лога | habit_reminder | HIGH |
| no_checkin_3days | Нет check-in > 3 дней | reactivation | CRITICAL |
| goal_no_milestones | Активная цель без milestones | structure_suggestion | MEDIUM |
| goal_no_first_step | Цель без первого действия | first_step_prompt | HIGH |
| overdue_tasks_spike | > 5 просроченных задач | workload_warning | MEDIUM |
| calendar_overload | > 8 событий завтра | load_advisory | LOW |
| habit_perfect_week | 7/7 привычек за неделю | celebration | MEDIUM |
| goal_deadline_near | До target_date < 14 дней | deadline_warning | HIGH |
| new_week_no_plan | Понедельник, нет плана на неделю | weekly_planning | MEDIUM |
| sunday_no_review | Воскресенье, нет weekly review | review_prompt | MEDIUM |
| discipline_drop | Completion rate -30% за неделю | recovery_mode | HIGH |
| no_fitness_7days | Нет тренировок > 7 дней | fitness_prompt | LOW |
| nutrition_unstable | Нет логов питания 3+ дня | nutrition_check | LOW |
| goal_achieved | progress_pct = 100 | achievement | CRITICAL |
| streak_milestone | Streak 7/30/100 дней | streak_celebration | HIGH |
| reactivation | Не было активности > 5 дней | gentle_return | CRITICAL |
| goal_conflict | Слишком много активных целей (>5) | focus_suggestion | MEDIUM |

### 5.3 Приоритетность и антиспам

**Лимиты:**
- Максимум **3 proactive-сообщения в день** (по умолчанию, настраивается в профиле)
- Между двумя сообщениями одного типа — минимум **48 часов**
- Между любыми двумя proactive-сообщениями — минимум **4 часа**
- Нет сообщений с 23:00 до 08:00 (кроме утреннего брифа)
- Если пользователь активен в чате — сообщения не отправляются (ждём завершения диалога)
- После отклонённого (dismissed) nudge — пауза минимум **24 часа** для этого типа

**Приоритизация:**
1. CRITICAL (ответ > 5 дней отсутствия, goal_achieved, streak_milestone)
2. HIGH (goal_stuck, habit_dying, deadline_warning)
3. MEDIUM (structure, planning, review)
4. LOW (low-stakes советы)

В один день отправляется не более одного сообщения приоритета HIGH и одного MEDIUM.

### 5.4 Структура proactive-сообщения

Каждое proactive-сообщение содержит:
- **Контекст**: почему коуч пишет сейчас (1 предложение)
- **Суть**: конкретное наблюдение (1-2 предложения)
- **Вопрос или действие**: что предлагается сделать
- **Кнопки**: 2-4 быстрых действия
- **Мягкость**: учитываем current_state (recovery → мягче, momentum → активнее)

Пример:
```
Ты не отмечался по цели «Выучить испанский» уже 9 дней.

Это нормально — иногда буксуем. Хочешь разберём, что мешает?

[✅ Продолжаю] [🔄 Скорректировать цель] [❄️ Заморозить] [📝 Рассказать]
```

### 5.5 Механика умных nudges

**Контекстная адаптация:**
- Если calendar_overload сегодня → не отправляем productivity-nudges
- Если fitness не логировался + discipline_drop → отправляем recovery, не мотивацию
- Если user в recovery_state → тон мягкий, требования снижены
- Если user в momentum_state → тон бодрый, можно предложить усилить

**Обучение на реакциях:**
- Пользователь нажал "Пропустить" 3+ раза на nudge одного типа → временно отключаем
- Пользователь регулярно реагирует в определённое время → адаптируем время отправки
- Пользователь игнорирует вечерние сообщения → пробуем утром

---

## 6. AI-COACH LOGIC

### 6.1 Системный промпт и persona

**Персонаж коуча**: адаптивный. Базовый — дружелюбный-прямой. Пользователь может настроить: мягкий, нейтральный, прямой, жёсткий.

**Ядро промпта:**
```
Ты — личный AI-коуч в Personal Assistant.
Твоя роль: помогать пользователю ставить реальные цели, двигаться к ним,
формировать привычки и не сливаться.

ПРИНЦИПЫ:
1. Ты видишь полный контекст жизни пользователя — используй его
2. Не давай абстрактных советов — говори конкретно
3. Не мотивируй без понимания — сначала анализируй
4. Предлагай следующий КОНКРЕТНЫЙ шаг, а не общую стратегию
5. Адаптируй тон под текущее состояние пользователя
6. Объясняй логику своих рекомендаций (но коротко)
7. Если цель абстрактна — помоги сделать её конкретной
8. Замечай, когда пользователь перегружен, и говори об этом

ТЕКУЩИЙ КОНТЕКСТ:
{user_state}
{active_goals_summary}
{habits_summary}
{cross_module_snapshot}
{coaching_memory_summary}

ТОНАЛЬНОСТЬ: {coach_tone}
```

### 6.2 Режимы коуча

| Режим | Описание | Когда активируется |
|---|---|---|
| onboarding | Объяснение, первые шаги | Первые 3 сессии |
| daily_mode | Обычный диалог + текущий контекст | Default |
| checkin_mode | Структурированный daily check-in | По расписанию или запросу |
| review_mode | Weekly/monthly review | По расписанию или запросу |
| goal_creation | Помощь в формулировке и структуризации цели | goal_create intent |
| recovery_mode | Мягкий возврат, упрощение | После срыва/выпадения |
| momentum_mode | Усиление темпа, новые вызовы | При устойчивом прогрессе |
| crisis_mode | Пользователь явно overwhelmed | При overload_state |

### 6.3 Что делает код, а не LLM

**Код (детерминированная логика):**
- Вычисление streak, completion rate
- Определение user_state (momentum/overload/recovery)
- Trigging proactive-сообщений по расписанию и событиям
- Сохранение goal/habit/checkin в БД
- Применение antispam-правил
- Вычисление risk_score
- Агрегация cross-module snapshot
- Генерация context-pack для LLM

**LLM (генеративная логика):**
- Интерпретация намерения пользователя
- Формулировка ответа и рекомендаций
- Разбиение абстрактной цели на конкретные шаги
- Анализ blockers из check-in
- Генерация weekly review summary
- Объяснение паттернов и рекомендаций
- Адаптация тона к контексту

### 6.4 Tools, которые должен иметь агент

Подробный реестр — см. раздел 7.

### 6.5 Данные, обязательные для коуча

Коуч ВСЕГДА получает перед каждым ответом:
- Список активных целей + прогресс + последний check-in
- Список активных привычек + streak + логи за последние 7 дней
- Текущий user_state (из coaching_context_snapshots)
- Список топ-3 рекомендаций (из coaching_recommendations)
- Релевантная память из coaching_memory (топ-5 по confidence)
- Незавершённые milestones на этой неделе

---

## 7. TOOLS ДЛЯ АГЕНТА

### 7.1 Обязательные инструменты (core)

**goal_create(user_id, title, description, area, target_date, why_statement, first_step)**
Создаёт цель. Перед созданием коуч должен уточнить «зачем» (why_statement) и первый шаг.

**goal_update(goal_id, user_id, **fields)**
Обновляет любые поля цели. Используется при корректировке через диалог.

**goal_update_progress(goal_id, user_id, progress_pct, notes)**
Обновляет прогресс. Логирует в goal_checkins.

**goal_add_milestone(goal_id, user_id, title, target_date, order_index)**
Добавляет milestone к цели.

**goal_complete_milestone(milestone_id, user_id)**
Отмечает milestone выполненным. Обновляет progress_pct цели.

**goal_archive(goal_id, user_id, reason)**
Архивирует цель (status='cancelled').

**goal_freeze(goal_id, user_id, reason)**
Замораживает цель (is_frozen=True). Останавливает напоминания.

**goal_resume(goal_id, user_id)**
Размораживает цель.

**goal_restart(goal_id, user_id)**
Сбрасывает прогресс, создаёт новую точку старта, сохраняет историю.

**goal_generate_plan(goal_id, user_id)**
Генерирует набор milestones + первые задачи через LLM. Требует подтверждения.

**habit_create(user_id, title, area, frequency, target_count, cue, best_time, goal_id)**
Создаёт привычку.

**habit_log(habit_id, user_id, value, notes)**
Логирует выполнение привычки. Обновляет streak.

**habit_log_miss(habit_id, user_id, reason)**
Фиксирует пропуск. Обновляет streak-логику.

**habit_pause(habit_id, user_id, reason, days)**
Ставит привычку на паузу на N дней.

**habit_resume(habit_id, user_id)**
Возобновляет привычку.

**habit_adjust_frequency(habit_id, user_id, new_frequency, new_target_count)**
Корректирует частоту выполнения.

**habit_archive(habit_id, user_id)**

**coaching_checkin_create(user_id, energy_level, mood, notes, blockers, wins, goal_id)**
Создаёт daily check-in. Обновляет context_snapshot.

**coaching_review_generate(user_id, period_type)**
Генерирует weekly/monthly review: агрегирует данные, вызывает LLM для summary.

**coaching_next_step_suggest(user_id, goal_id)**
Определяет следующий конкретный шаг по цели на основе milestones и context.

**coaching_plan_generate(user_id, horizon)**
Строит план на день/неделю с учётом целей, задач, календаря. Требует подтверждения.

**coaching_insight_get(user_id, limit)**
Возвращает актуальные инсайты и рекомендации.

**coaching_memory_get(user_id, memory_type)**
Читает память коуча о пользователе.

**coaching_memory_update(user_id, key, value, is_explicit)**
Обновляет/добавляет запись в память.

**coaching_draft_create(user_id, draft_type, payload)**
Создаёт черновик незавершённого диалога.

**coaching_draft_update(draft_id, user_id, step, payload)**

**coaching_draft_confirm(draft_id, user_id)**
Завершает черновик, выполняет итоговое действие.

**coaching_template_apply(user_id, template_id)**
Применяет шаблон привычки к пользователю.

### 7.2 Аналитические инструменты

**coaching_context_snapshot_get(user_id)**
Возвращает свежий снимок состояния (вычисляет on-the-fly если нет за сегодня).

**coaching_risk_assess(user_id)**
Вычисляет текущие risk scores по всем типам.

**coaching_behavior_patterns_get(user_id)**
Возвращает активные паттерны поведения.

**coaching_progress_analytics(user_id, goal_id, period)**
Детальная аналитика прогресса по цели.

**coaching_habit_analytics(user_id, habit_id, period)**
Детальная аналитика привычки: completion rate, лучшие дни, риски.

### 7.3 Proactive инструменты

**coaching_nudge_schedule(user_id, nudge_type, content, send_at)**
Планирует отправку proactive-сообщения.

**coaching_nudge_cancel(user_id, nudge_type)**
Отменяет запланированный nudge.

**coaching_check_antispam(user_id, nudge_type)**
Проверяет, можно ли отправлять сообщение (возвращает True/False + причину).

### 7.4 Onboarding инструменты

**coaching_onboarding_step_get(user_id)**
Возвращает текущий шаг онбординга.

**coaching_onboarding_step_update(user_id, step, completed)**

**coaching_prompt_examples_get(user_id, context)**
Возвращает релевантные примеры запросов для текущего контекста (пустое состояние, after_failure, review и т.д.).

### 7.5 Orchestration инструменты (cross-module)

**orchestrate_create_task_from_milestone(user_id, milestone_id)**
Создаёт задачу в Tasks из milestone цели.

**orchestrate_create_calendar_event(user_id, title, datetime, duration_min, linked_goal_id)**
Создаёт событие в Calendar для тренировки/привычки.

**orchestrate_update_reminder(user_id, habit_id, new_time)**
Меняет время напоминания привычки.

---

## 8. CHAT-FIRST УПРАВЛЕНИЕ

### 8.1 Conversational flows

**Создание цели через чат:**
1. Пользователь: «Хочу выучить английский»
2. Коуч: уточняет зачем, к какому сроку, что уже пробовал → draft
3. Коуч: предлагает структуру + первый шаг + привязку к привычке
4. Пользователь: подтверждает или корректирует
5. Коуч: создаёт цель + опционально milestones + напоминание

**Daily check-in:**
1. Коуч инициирует вечером: «Как прошёл день? Отметь быстро 👇»
2. Кнопки: [🔥 Продуктивно] [😐 Нормально] [😔 Тяжело] [💀 Провал]
3. Коуч: задаёт 1 уточняющий вопрос на основе выбора
4. Сохраняет check-in, обновляет state, корректирует план

**Weekly review:**
1. Коуч в воскресенье: «Разберём неделю?»
2. Кнопки: [Давай] [Не сейчас] [Сделать коротко]
3. Коуч: по каждой активной цели — прогресс?
4. Коуч: по привычкам — что держалось, что сорвалось?
5. Коуч: AI summary + топ-3 инсайта + план на следующую неделю

### 8.2 Conversational drafts и pending state

Если пользователь начал создавать цель и не завершил → coaching_dialog_drafts сохраняет состояние. При следующем входе в чат коуч предлагает продолжить.

**Pending coaching state:** если коуч задал вопрос и ждёт ответа — следующее сообщение пользователя интерпретируется в контексте вопроса (через state machine в draft).

### 8.3 Context-aware follow-ups

После каждого значимого действия коуч добавляет релевантный follow-up:
- Создана цель → «Разбить на этапы?»
- Залогирована привычка → «Стрик 5 дней! Добавить сложности?»
- Check-in «тяжело» → «Что конкретно мешало?»
- Пропущена привычка → «Что случилось? Скорректируем?»

### 8.4 Memory последних целей

В каждом диалоге коуч имеет доступ к последним 5 целям и 10 привычкам пользователя и может ссылаться на них по имени без дополнительного контекста.

---

## 9. INTERACTIVE TELEGRAM COACHING UX

### 9.1 Кнопки для целей

**После создания цели:**
```
[📌 Разбить на этапы] [✅ Первый шаг] [🔔 Напомнить] [📊 Открыть в App]
```

**Карточка цели (при просмотре):**
```
[📈 Обновить прогресс] [➕ Добавить шаг]
[✏️ Скорректировать] [❄️ Заморозить]
```

**Зависшая цель (nudge):**
```
[✅ Продолжаю] [🔄 Скорректировать] [❄️ Заморозить] [📝 Объясню]
```

**Достижение цели:**
```
[🎉 Ура! Что дальше?] [📝 Написать рефлексию] [🆕 Новая цель]
```

### 9.2 Кнопки для привычек

**Ежедневный напоминатель:**
```
[✅ Выполнено] [❌ Пропускаю] [⏰ Напомни позже]
```

**После логирования:**
```
[🔥 Стрик {N} дней!] → [Поделиться] [Посмотреть прогресс]
```

**Серия привычек:**
```
🏃 Пробежка      [✅] [❌]
📚 Чтение 20 мин [✅] [❌]
💧 Вода 8 ст.    [✅] [❌]
```

**Управление привычкой:**
```
[⏸️ Пауза на 3 дня] [🔄 Изменить частоту] [📊 Статистика]
```

### 9.3 Daily check-in кнопки

```
Как прошёл день?
[🔥 Отлично] [👍 Норм] [😐 Так себе] [😔 Тяжело] [💀 Провал]
```

После выбора:
```
[Расскажу что мешало] [Дай следующий шаг] [Всё ок, спасибо]
```

### 9.4 Weekly review кнопки

```
[📊 Начать review] [⚡ Быстрый review] [➡️ Пропустить неделю]
```

В процессе review по каждой цели:
```
«Цель: Выучить испанский»
[🟢 Двигаюсь] [🟡 Медленно] [🔴 Буксую] [❄️ Заморожена]
```

После review:
```
[🔧 Скорректировать план] [📉 Снизить нагрузку] [📈 Усилить темп] [✅ Всё устраивает]
```

### 9.5 Motivational кнопки

```
[💪 Подбодри] [🔥 Жёсткий разбор] [🗺️ Следующий шаг] [🎯 Упрости маршрут]
```

### 9.6 Onboarding кнопки (первый запуск)

```
Привет! Я твой AI-коуч. Помогу ставить цели и двигаться к ним.
[🎯 Начать с цели] [🔄 Начать с привычки] [❓ Что ты умеешь?] [⚙️ Настроить коуча]
```

### 9.7 Контекстные кнопки в зависимости от состояния

**overload_state:**
```
[📉 Снизить нагрузку] [🔄 Пересобрать план] [❄️ Заморозить лишнее]
```

**recovery_state:**
```
[🔄 Начать заново] [📝 Рассказать что случилось] [🆕 Простой план]
```

**momentum_state:**
```
[📈 Добавить вызов] [🆕 Новая цель] [🏆 Мои достижения]
```

---

## 10. USER GUIDANCE / ONBOARDING / COACHING PROMPT EDUCATION

### 10.1 Стартовый онбординг (3 шага)

**Шаг 1: Знакомство (welcome)**
Коуч рассказывает что умеет в 3 коротких блоках + 3 кнопки.

**Шаг 2: Профилирование**
- Что важно сейчас? (здоровье / продуктивность / карьера / отношения)
- Какой тон предпочитаешь? (мягкий / нейтральный / прямой)
- Когда удобно check-in? (утро / вечер)

**Шаг 3: Первое действие**
- Создать первую цель ИЛИ
- Создать первую привычку ИЛИ
- Посмотреть примеры

### 10.2 Contextual help

В Mini App в пустых состояниях всегда есть **CoachPromptBubble** — контекстуальный пузырь-подсказка. Примеры:

- Пустой список целей: «Попробуй написать в чат: "Помоги поставить цель на месяц"»
- Пустые привычки: «Напиши: "Создай привычку пить воду"»
- После создания цели: «Напиши "Разбей на этапы"»

### 10.3 Sample prompts в интерфейсе

В блоке «Попробуй спросить» (карусель/чипы) показываются контекстуальные примеры запросов. Обновляются на основе текущего состояния.

### 10.4 Повторное мягкое обучение

Если пользователь не использовал функцию > 14 дней:
- Коуч мягко напоминает: «Кстати, ты ещё не пробовал weekly review — это занимает 3 минуты и сильно помогает не потерять ритм»

---

## 11. QUESTION TEMPLATES / EXAMPLE INTERACTIONS

### 11.1 Постановка целей
- «Помоги поставить цель на 3 месяца»
- «Хочу похудеть на 10 кг — как структурировать?»
- «Разбей мою цель на реальные шаги»
- «С чего мне начать?»
- «Сделай план достижения цели»
- «Помоги сформулировать цель конкретнее»

### 11.2 Привычки
- «Создай привычку — каждый день читать 20 минут»
- «Подбери привычки под мою цель по здоровью»
- «Я сделал сегодня тренировку»
- «Я не выполнил привычку — что делать?»
- «Покажи мои привычки на сегодня»
- «Как улучшить мой стрик?»

### 11.3 Check-in
- «Как прошёл мой день?»
- «Сегодня был слабый день»
- «Я сорвался — помоги собраться»
- «Я не понимаю, что делать дальше»
- «Мне тяжело держать темп»
- «Что я сделал сегодня?»

### 11.4 Review
- «Проведи weekly review»
- «Покажи, где я буксую»
- «Разбери мой прогресс за неделю»
- «Что мне скорректировать?»
- «Как я справляюсь с целями?»

### 11.5 Мотивация и поддержка
- «Подбодри, но по делу»
- «Скажи жёстко, где я сливаю»
- «Упрости мне путь»
- «Дай следующий лучший шаг»
- «Я снова сорвался — что делать?»

### 11.6 Интеграции и планирование
- «Привяжи эту цель к задачам»
- «Сделай из цели план на неделю»
- «Преврати мою цель в привычки»
- «Сделай режим под похудение»
- «Посмотри на всё и скажи, где главная проблема»
- «Собери реальный план на завтра с учётом задач»

### 11.7 Контекст показа шаблонов

| Контекст | Шаблоны |
|---|---|
| Onboarding | Постановка цели, первая привычка, примеры |
| Пустой dashboard | «Начать с цели», «Создать привычку», «Что умеет коуч» |
| После провала | Check-in «сорвался», restart, упрощение |
| Weekly review | Review запросы, корректировки |
| Карточка цели | Следующий шаг, milestone, прогресс |
| Зависшая цель | Разбор блокеров, заморозка, перезапуск |
| momentum_state | Новый вызов, усиление темпа |
| Кнопки быстрого доступа | «Следующий шаг», «Отметить привычки», «Check-in» |

---

## 12. SEMI-EDUCATIONAL COACHING LAYER

### 12.1 Принцип встроенного обучения

Обучение встроено в UX ненавязчиво: не учебники, а **coaching tips** — короткие объяснения в нужный момент, по 1-2 предложения, с возможностью пропустить.

### 12.2 Micro-обучающие вставки

**При создании абстрактной цели:**
> «💡 Хорошая цель — измеримая и конкретная. "Стать здоровее" → "3 тренировки в неделю + минус 5 кг к июню". Так мозгу понятно, когда цель достигнута.»

**При слишком большом количестве привычек:**
> «💡 Исследования показывают: > 3 новых привычки одновременно — высокий риск бросить все. Начни с 1-2, доведи до автомата, потом расширяй.»

**При срыве привычки:**
> «💡 Пропуск не обнуляет привычку. Правило: никогда не пропускай дважды подряд — это защищает систему.»

**При постановке нереалистичного срока:**
> «💡 Ты ставишь 8 целей к концу месяца. Статистически людям удаётся реализовать 1-2 за месяц. Хочешь выбрать главную?»

**При отсутствии milestones:**
> «💡 Цель без этапов похожа на маршрут без промежуточных точек. Когда непонятно, как продвигаться, мозг откладывает. Добавим шаги?»

### 12.3 Coaching tips в режиме объяснений

Пользователь может написать «объясни» или «почему это важно» — коуч объясняет логику:

**«Почему стрик важен?»:**
> «Стрик — это не просто счётчик. Это психологический контракт с собой. После 21+ дней привычка начинает работать на автопилоте. До 21 — нужно сознательное усилие. Поэтому первые 3 недели — самые критичные.»

**«Зачем weekly review?»:**
> «Без review ты двигаешься на ощущениях. Review за 3-5 минут даёт ясность: что реально работало, где сливался, что скорректировать. Большинство срывов систем — не лень, а отсутствие осознанности.»

### 12.4 Советы по формулировке целей

При анализе цели через LLM коуч проверяет:
- Есть ли измеримый результат?
- Есть ли реальный срок?
- Реалистична ли цель с учётом контекста?
- Есть ли первый шаг?

Если нет — предлагает улучшить.

---

## 13. MINI APP UX/UI ARCHITECTURE

### 13.1 Главный экран Coaching (CoachingDashboard)

**Информационная иерархия (сверху вниз):**

1. **Daily State Card** (sticky top)
   - Текущий режим: 🔥 Momentum | ⚖️ Stable | 😮 Overload | 🔄 Recovery
   - Главный фокус дня (1 цель или задача)
   - Quick action: [Check-in] [Привычки] [Открыть чат]

2. **Habits Today Strip**
   - Горизонтальный список привычек на сегодня
   - Каждая: иконка + название + кнопка ✅/❌
   - Быстрое логирование одним тапом
   - Прогресс: 3/5 выполнено

3. **Active Goals** (карточки)
   - До 3 карточек активных целей
   - Каждая: название + прогресс-бар + deadline + статус
   - Тап → GoalDetailPage
   - «+ Добавить цель» в конце

4. **AI Insight Card**
   - Ключевой инсайт дня (из coaching_insights)
   - Если есть риск — выделено красным
   - Если всё хорошо — зелёный момент

5. **Recommendations Strip**
   - До 2 рекомендаций коуча
   - Карточка: заголовок + 2 кнопки действия

6. **Weekly Score**
   - Компактная карточка: прогресс недели в %
   - Ссылка на WeeklyReviewPage

### 13.2 Пустые состояния

**Пустой Dashboard (новый пользователь):**
- Крупный заголовок: «Начни с одной цели»
- Иллюстрация + короткий текст
- CTA: [🎯 Поставить первую цель] [🔄 Создать привычку] [❓ Как это работает]
- Плавающий пузырь коуча: «Напиши мне в чат: "Помоги поставить цель на месяц"»

**Нет привычек:**
- «У тебя пока нет привычек. Привычки — это маленькие ежедневные действия, которые ведут к большим целям.»
- CTA: [Создать привычку] [Подобрать шаблон]

### 13.3 Goals UI (GoalsPage + GoalDetailPage)

**GoalsPage:**
- Фильтры: Все | Активные | Заморожены | Достигнуты
- Поиск по названию
- Карточки целей (GoalCard)
- FAB: «+ Новая цель»

**GoalCard:**
- Emoji области + название + дедлайн
- Прогресс-бар + процент
- Статус-бейдж: 🟢 Active | ❄️ Frozen | 🔴 At Risk | ✅ Done
- Streak (если привязаны привычки)

**GoalDetailPage:**
- Полное название + why_statement
- Прогресс-бар (большой, интерактивный)
- Milestones list (чекбоксы)
- Привязанные привычки
- История check-ins (последние 5)
- Последний AI-инсайт по цели
- Sticky bottom: [Обновить прогресс] [Следующий шаг] [...]

### 13.4 Habits UI (HabitsPage)

**Режим Today:**
- Список привычек на сегодня с кнопками ✅/❌/⏰
- Счётчик: 3 из 5 выполнено
- Streak-бейджи

**Режим All:**
- Все привычки с completion rate за последние 7 дней
- Мини-тепловая карта (7 дней × N привычек)
- Статусы: Active | Paused | At Risk

**HabitDetailSheet (bottom-sheet):**
- Название + описание + триггер
- Streak + longest streak
- График выполнения за 30 дней
- Кнопки: [Выполнено] [Пауза] [Изменить] [Архивировать]

### 13.5 Check-in UI (CheckInPage)

**Быстрый вариант (по умолчанию):**
- Слайдер энергии 1-5
- 5 кнопок настроения
- Textarea «Что было важным сегодня?»
- Кнопка «Сохранить»

**Расширенный вариант (по выбору):**
- + Поле «Что мешало?»
- + Поле «Что получилось?»
- + Выбор привязки к цели

### 13.6 Weekly Review UI (WeeklyReviewPage)

**Секции:**
1. **Обзор недели** — период, числа, общий score
2. **Цели** — по каждой цели: прогресс + что сделано
3. **Привычки** — completion rate + стрики + срывы
4. **AI Summary** — 3-5 предложений от коуча
5. **Highlights & Blockers** — что работало / что мешало
6. **Следующая неделя** — 3 приоритета + корректировки

**Actions:** [Поделиться] [Скорректировать план] [Готово]

### 13.7 Insights UI (InsightsPage)

- Карточки инсайтов с иконками приоритета
- Фильтр по типу: риски | паттерны | рекомендации | достижения
- Каждый инсайт: заголовок + описание + источники модулей + кнопка действия
- Инсайт можно dismissать или actioned

### 13.8 Onboarding UI (OnboardingPage)

- Swipeable карточки (4 шага)
- Шаг 1: Что такое коуч
- Шаг 2: Как работать с целями
- Шаг 3: Как использовать привычки
- Шаг 4: Настройка профиля + первый шаг
- Прогресс-бар сверху
- Кнопка «Пропустить» на каждом шаге

### 13.9 UX-принципы для Telegram Mini App

- **Mobile-first**: все взаимодействия — одна рука, большие тапзоны
- **Minimal scroll**: важное в верхней половине экрана
- **Bottom-sheet**: детали открываются в sheet, не новой страницей
- **Sticky actions**: ключевые кнопки всегда видны внизу
- **Quick logging**: логирование привычки — 1 тап
- **Progressive disclosure**: детали по запросу, не сразу
- **Chat bridge**: каждая страница имеет кнопку «Открыть в чате»

---

## 14. API LAYER

### 14.1 Pydantic схемы (ключевые)

```python
class GoalCreateDto(BaseModel):
    title: str
    description: str = ""
    area: str = "personal"
    target_date: Optional[date]
    why_statement: str = ""
    first_step: str = ""
    priority: int = 2

class GoalUpdateDto(BaseModel):
    title: Optional[str]
    progress_pct: Optional[int]
    status: Optional[str]
    is_frozen: Optional[bool]
    first_step: Optional[str]
    why_statement: Optional[str]

class MilestoneCreateDto(BaseModel):
    title: str
    target_date: Optional[date]
    order_index: int = 0

class HabitCreateDto(BaseModel):
    title: str
    area: str = "health"
    frequency: str = "daily"
    target_count: int = 1
    cue: str = ""
    best_time: str = "evening"
    goal_id: Optional[int]
    color: str = "#5B8CFF"

class CheckInCreateDto(BaseModel):
    energy_level: int  # 1-5
    mood: str          # great | good | ok | hard | terrible
    notes: str = ""
    blockers: str = ""
    wins: str = ""
    goal_id: Optional[int]

class CoachingProfileUpdateDto(BaseModel):
    coach_tone: Optional[str]
    coaching_mode: Optional[str]
    preferred_checkin_time: Optional[str]
    morning_brief_enabled: Optional[bool]
    evening_reflection_enabled: Optional[bool]
    max_daily_nudges: Optional[int]
    focus_areas: Optional[List[str]]
```

### 14.2 Endpoints

```
# Goals
GET     /coaching/goals                    # список целей
POST    /coaching/goals                    # создать цель
GET     /coaching/goals/{id}               # детали цели
PUT     /coaching/goals/{id}               # обновить
DELETE  /coaching/goals/{id}               # архивировать
POST    /coaching/goals/{id}/freeze        # заморозить
POST    /coaching/goals/{id}/resume        # разморозить
POST    /coaching/goals/{id}/restart       # перезапустить
POST    /coaching/goals/{id}/checkin       # check-in по цели
POST    /coaching/goals/{id}/generate-plan # AI-план milestones
GET     /coaching/goals/{id}/progress      # история прогресса
GET     /coaching/goals/{id}/analytics     # аналитика

# Milestones
GET     /coaching/goals/{id}/milestones
POST    /coaching/goals/{id}/milestones
PUT     /coaching/milestones/{id}
POST    /coaching/milestones/{id}/complete

# Habits
GET     /coaching/habits                   # список привычек
POST    /coaching/habits                   # создать
GET     /coaching/habits/{id}
PUT     /coaching/habits/{id}
POST    /coaching/habits/{id}/log          # залогировать
POST    /coaching/habits/{id}/miss         # пропуск
POST    /coaching/habits/{id}/pause
POST    /coaching/habits/{id}/resume
GET     /coaching/habits/{id}/analytics
GET     /coaching/habits/templates         # шаблоны

# Check-in
POST    /coaching/checkin                  # создать check-in
GET     /coaching/checkin/today            # check-in сегодня
GET     /coaching/checkin/history          # история

# Reviews
GET     /coaching/reviews                  # список review
POST    /coaching/reviews/generate         # сгенерировать review
GET     /coaching/reviews/{id}             # детали review

# Insights
GET     /coaching/insights                 # инсайты
POST    /coaching/insights/{id}/read
POST    /coaching/insights/{id}/action
POST    /coaching/insights/{id}/dismiss

# Recommendations
GET     /coaching/recommendations
POST    /coaching/recommendations/{id}/act
POST    /coaching/recommendations/{id}/dismiss

# Profile
GET     /coaching/profile
PUT     /coaching/profile

# Dashboard
GET     /coaching/dashboard                # полный снапшот для главного экрана

# State
GET     /coaching/state                    # текущее состояние пользователя

# Onboarding
GET     /coaching/onboarding/state
POST    /coaching/onboarding/step

# Analytics
GET     /coaching/analytics/weekly         # аналитика недели
GET     /coaching/analytics/habits         # сводка по привычкам
GET     /coaching/analytics/goals          # сводка по целям
GET     /coaching/analytics/streaks        # аналитика стриков

# Prompt templates
GET     /coaching/prompts                  # примеры запросов для текущего контекста
```

### 14.3 Dashboard endpoint (агрегация)

`GET /coaching/dashboard` возвращает единым запросом:
```json
{
  "state": { "mode": "momentum", "score": 78 },
  "habits_today": [...],
  "goals_active": [...],
  "top_insight": {...},
  "recommendations": [...],
  "weekly_score": 72,
  "nudge_pending": {...},
  "prompt_suggestions": [...]
}
```
Один запрос при открытии Mini App — минимизирует waterfall.

---

## 15. CROSS-MODULE INTELLIGENCE LAYER

### 15.1 Сбор сигналов

При каждом вычислении `coaching_context_snapshot` система запрашивает:

**Из Tasks:**
- tasks_overdue (кол-во просроченных)
- tasks_completed_today
- tasks_completion_rate_week (% выполненных за 7 дней)
- has_tasks_linked_to_goals (есть ли задачи, привязанные к активным целям)

**Из Calendar:**
- events_today (кол-во событий)
- free_slots_today (кол-во свободных блоков >30 мин)
- calendar_load_next_3days (загруженность ближайших дней)

**Из Fitness:**
- last_workout_days_ago
- workouts_this_week
- fitness_goal_progress (если есть связанная цель)

**Из Nutrition:**
- nutrition_logged_today
- nutrition_streak (дней подряд логировалось)
- avg_calories_adherence_week

**Из Reminders:**
- reminders_acknowledged_rate (% принятых напоминаний)
- best_engagement_time (время наибольшей реакции)

### 15.2 Интерпретация сигналов

Пример логики анализа в `services/coaching_engine.py`:

```python
# Псевдокод вычисления состояния
def compute_user_state(snapshot: ContextSnapshot) -> UserState:
    score = 100

    # Перегруз
    if snapshot.tasks_overdue > 5: score -= 20
    if snapshot.calendar_events_today > 8: score -= 15

    # Дисциплина
    if snapshot.habits_completion_today < 0.4: score -= 20
    if snapshot.tasks_completion_rate_week < 0.4: score -= 15

    # Активность
    if snapshot.last_workout_days_ago > 7: score -= 10
    if not snapshot.nutrition_logged_today: score -= 5

    # Определение состояния
    if score >= 75: return "momentum"
    elif score >= 50: return "stable"
    elif score >= 30: return "overload" if overdue_high else "recovery"
    else: return "recovery"
```

### 15.3 Cross-module выводы

Коуч умеет строить следующие типы cross-module выводов:

1. **Конфликт**: «Цель требует 5 часов в неделю, но в календаре нет свободных окон»
2. **Причинно-следственная связь**: «Падение дисциплины совпадает с нарушением режима питания»
3. **Дисбаланс**: «Ты ставишь цели в фитнесе, но не логируешь тренировки»
4. **Перегруз**: «35 активных задач + 5 целей + 8 привычек — это нереально»
5. **Паттерн срывов**: «Каждый понедельник после >8 событий пропускаешь привычки»
6. **Слепое пятно**: «Цель "стать здоровее" никак не отражена в задачах и питании»

---

## 16. WHOLE-USER STATE MODEL

### 16.1 Состояния пользователя

| Состояние | Описание | Score | Признаки |
|---|---|---|---|
| momentum | Всё идёт хорошо, темп устойчивый | 75-100 | Высокий completion rate, streak, прогресс по целям |
| stable | Нормально, без явных проблем | 50-74 | Средние показатели, нет критических сигналов |
| overload | Перегружен, риск срыва | 30-49 + overdue_spike | Много просроченного, перегружен календарь |
| recovery | Выпал, нужно мягко вернуться | 30-49 + low_engagement | Долго не логировал, стрики сломаны |
| risk | Критический момент | <30 | Несколько дней без активности + срыв |

### 16.2 Адаптация коуча под состояние

| Состояние | Тон | Глубина | Действия |
|---|---|---|---|
| momentum | Бодрый, энергичный | Можно новые вызовы | Предлагать усиление |
| stable | Нейтральный | Стандартный | Поддержание ритма |
| overload | Внимательный, без давления | Краткий | Разгрузить, упростить |
| recovery | Мягкий, без упрёков | Минималистичный | Маленький первый шаг |
| risk | Заботливый + прямой | Фокус на сути | Reactivation сценарий |

---

## 17. CROSS-MODULE RECOMMENDATION ENGINE

### 17.1 Типы рекомендаций

**schedule_fix**: «Перенеси привычку на утро — вечером у тебя регулярно перегруз»

**goal_decompose**: «Цель без задач не двигается. Создадим 3 конкретных шага?»

**workload_reduce**: «У тебя 40 задач и 6 целей. Реально за месяц — 8-10 задач и 1-2 цели»

**habit_time_adjust**: «Ты пропускаешь чтение по вечерам. Попробуй утром после кофе»

**nutrition_fitness_link**: «Цель по снижению веса слабо продвигается. Питание не отслеживается 5 дней»

**cross_module_plan**: «На следующей неделе предлагаю: 3 тренировки утром (пн/ср/пт) + трекинг калорий»

### 17.2 Приоритизация рекомендаций

Рекомендации ранжируются по:
1. severity рисков (risk_score > 0.7 → priority 1)
2. количеству затронутых модулей (cross-module весомее)
3. давности последней похожей рекомендации (dedup)
4. релевантности текущему состоянию

Показывается максимум **2 рекомендации одновременно** (чтобы не перегружать).

---

## 18. CONTEXT-AWARE PROACTIVE COACHING

### 18.1 Multi-signal triggers

Триггеры, основанные на совокупности сигналов:

**overload_intervention**: tasks_overdue > 5 AND calendar_load_high AND habits_completion < 50%
→ Сообщение: «Похоже, ты сейчас перегружен. Хочешь разберём и упростим план?»

**recovery_mode_trigger**: no_activity > 3 days AND streak_broken > 2 habits
→ Сообщение: «Ты пропал на несколько дней. Это нормально. Давай вернёмся с чего-то маленького»

**momentum_boost**: 7/7 habits AND goal_progress_positive AND tasks_rate > 70%
→ Сообщение: «Ты в отличной форме! Хочешь добавить новый вызов или усилить темп?»

**silent_goal**: active_goal AND no_tasks_linked AND no_checkin > 7 days
→ Сообщение: «Цель "X" существует 12 дней, но ни одного действия. Что мешает?»

### 18.2 Recovery mode logic

В recovery_state коуч:
- Не отправляет motivation-push (не работает при усталости)
- Предлагает micro-win: «Сделай одно маленькое действие сегодня»
- Не показывает все проваленные цели — фокус на 1
- Использует мягкий тон без упрёков
- Предлагает «reset week» — перезапустить план с нуля

### 18.3 Momentum mode logic

В momentum_state коуч:
- Может предложить новую цель или привычку
- Добавляет stretch challenge к существующим целям
- Усиливает глубину weekly review
- Предлагает разобраться с застрявшими задачами

---

## 19. ADAPTIVE PERSONALIZATION LAYER

### 19.1 Что накапливается

**Явные предпочтения (explicit):**
- Тон коуча (настраивается)
- Время check-in
- Фокусные области
- Режим взаимодействия

**Выводимые предпочтения (implicit):**
- «Утренний человек» (активность в first half of day > 70%)
- «Серийный перегрузчик» (overdue > 5 регулярно)
- «Боится длинных списков» (goals > 3 → completion drops)
- «Реагирует на жёсткость» (direct-tone → лучший outcome)
- «Стрик-зависимый» (strak motivation pattern detected)

### 19.2 Behavioral profile

`coaching_memory` накапливает записи вида:
- `morning_person: true, confidence: 0.8`
- `overcommits_goals: true, confidence: 0.7`
- `best_engagement_time: 09:00, confidence: 0.9`
- `motivator: streak, confidence: 0.75`
- `blocker: evening_overload, confidence: 0.6`

### 19.3 Corrections log

Если пользователь явно исправляет коуча («нет, я сказал другое», «это неправильно»):
- Коуч обновляет релевантную memory с is_explicit=true
- Confidence устанавливается в 1.0
- Следующие рекомендации учитывают это

### 19.4 Персонализация ограничена

**Что не персонализируется:**
- Антиспам правила (фиксированные)
- Правила безопасности данных
- Базовая структура check-in и review (изменяется только тон)

**Reversible learning:**
Пользователь может сбросить профиль через «Сбросить настройки коуча» → coaching_memory очищается, профиль возвращается к default.

---

## 20. УВЕДОМЛЕНИЯ И РИТУАЛЫ

### 20.1 Ежедневные ритуалы

**Morning Brief (07:00-09:00, по профилю):**
- Главный фокус дня (1 цель)
- Привычки на сегодня (список)
- Одна рекомендация
- Кнопки: [Готов] [Изменить план] [Пропустить]

**Evening Check-in (20:00-22:00, по профилю):**
- «Как прошёл день?» + 5 кнопок
- После ответа: краткий фидбек + план на завтра
- Кнопки: [Подробнее] [Всё ок] [Спасибо]

### 20.2 Еженедельные ритуалы

**Sunday Weekly Review (воскресенье, 18:00):**
- Предложение провести review
- 5 минут структурированного диалога
- AI summary + план на следующую неделю

**Monday Morning Focus (понедельник, 08:00):**
- Топ-3 фокуса на неделю
- Привычки недели
- Предупреждение о рисках

### 20.3 Месячный reset

Первый день месяца:
- Обзор месяца (если не делали)
- Предложение пересмотреть цели
- Архивирование достигнутого

### 20.4 Anti-dropout reminders

- 3 дня без активности → мягкий nudge
- 5 дней без активности → reactivation сценарий
- 10 дней → последняя попытка + предложение простого старта

### 20.5 Smart vs Dumb режимы

**Soft mode**: только ритуалы, без event-driven nudges
**Standard mode**: ритуалы + топ-приоритетные trigers (default)
**Active mode**: ритуалы + все триггеры + советы

---

## 21. ИНТЕГРАЦИИ С ДРУГИМИ МОДУЛЯМИ

### 21.1 Tasks & Calendar

- Milestone → задача: `orchestrate_create_task_from_milestone`
- Цель → недельный план: создаёт блок событий в Calendar
- Coaching review тянет tasks completion rate за неделю
- Если tasks_overdue > threshold → риск-инсайт в coaching
- Calendar загруженность влияет на рекомендации по нагрузке

### 21.2 Fitness

- `fitness_goal` (strength/weight_loss) → связывается с coaching goal
- Тренировки влияют на `overall_state` пользователя
- Если цель по здоровью + нет тренировок 7 дней → coaching insight
- Прогресс замеров тела → поддержка в coaching check-in

### 21.3 Nutrition

- Если цель связана со здоровьем → nutrition adherence влияет на coaching recommendations
- Нет логов питания 3+ дня → coaching_context учитывает
- Energy уровень в check-in может коррелировать с nutrition patterns

### 21.4 Reminders

- Каждая привычка создаёт Reminder в reminders-таблице
- Время reminder адаптируется под best_engagement_time из памяти
- `orchestrate_update_reminder` меняет время напоминания
- Статистика срабатывания reminders влияет на personalization

### 21.5 Scheduler

- Coaching может предложить зафиксировать время тренировки как recurring event
- Если Scheduler перегружен → coaching учитывает при рекомендациях

---

## 22. АНАЛИТИКА И INSIGHTS

### 22.1 Метрики пользователя

**Goal metrics:**
- completion rate (% достигнутых целей за период)
- avg time to achieve (среднее время достижения)
- goal abandonment rate
- milestone completion rate

**Habit metrics:**
- daily completion rate
- current streak / longest streak
- consistency score (7-day rolling average)
- best/worst days of week
- time-of-day patterns

**Engagement metrics:**
- check-in frequency
- response to nudges (открыто / проигнорировано)
- coaching sessions per week
- feature usage breakdown

### 22.2 Dropout risk score

Вычисляется как взвешенная сумма факторов:
- no_checkin_days × 0.3
- habit_completion_drop × 0.25
- goal_progress_stale × 0.25
- task_overdue_spike × 0.2

Score > 0.7 → HIGH RISK → активируется reactivation сценарий

### 22.3 Weekly score

Интегральная оценка недели (0-100):
- Goals: прогресс по активным целям (30%)
- Habits: completion rate (40%)
- Engagement: check-ins, reviews (20%)
- Recovery: возврат после срывов (10%)

---

## 23. ЭТАПЫ РЕАЛИЗАЦИИ

### Фаза 1: Storage & Data Model (3-4 дня)

**Цель**: создать полную схему БД для coaching.

**Файлы**:
- `db/models.py` — новые модели + расширение Goal/Habit
- `db/migrations/` — Alembic migration
- `db/coaching_storage.py` — CRUD для всех новых таблиц

**Что реализуется:**
- Все 16 новых таблиц из раздела 4
- Расширение goal + habit новыми полями
- Базовые CRUD методы: get/create/update/delete

**Тестируется:**
- Создание/чтение всех сущностей
- Корректность foreign keys
- Alembic migration up/down

**Ожидаемый результат:** Полная схема БД, работающий storage layer.

**Риски:** Согласование изменений схемы (правило: без изменений БД без согласования).

**Зависимости:** Нет.

---

### Фаза 2: Coaching Engine & Tools (5-7 дней)

**Цель**: ядро вычислений и инструменты агента.

**Файлы**:
- `services/coaching_engine.py` — вычисление состояний, snapshot
- `services/coaching_recommendations.py` — движок рекомендаций
- `tools/coaching_tools.py` — все инструменты агента
- `tools/coaching_context_tools.py` — cross-module агрегация
- `agents/personal/coaching_agent.py` — LangGraph агент

**Что реализуется:**
- Все 30+ инструментов из раздела 7
- Вычисление UserState (momentum/stable/overload/recovery)
- Context snapshot aggregation
- Risk score computation
- Базовый промпт coaching агента
- Routing в supervisor (добавить "coaching" как отдельный тип)

**Тестируется:**
- Корректность вычисления состояний
- Работа каждого tool через unit тест
- Routing запросов к coaching агенту

**Ожидаемый результат:** Coaching агент работает в чате, создаёт цели/привычки, логирует.

---

### Фаза 3: Chat UX & Interactive Controls (3-4 дня)

**Цель**: полноценный conversational UX в Telegram.

**Файлы**:
- `bot/handlers/coaching_handler.py` — обработчики кнопок
- `bot/keyboards/coaching_keyboards.py` — все inline/reply клавиатуры
- `bot/flows/coaching_flows.py` — state machine для диалогов

**Что реализуется:**
- Все кнопки из раздела 9
- Daily check-in flow
- Goal creation flow с уточнениями
- Habit logging flow
- Draft state machine (coaching_dialog_drafts)

**Тестируется:**
- Каждый conversational flow end-to-end
- Корректность сохранения drafts
- Отмена / выход из flow

**Ожидаемый результат:** Полный chat-first UX работает.

---

### Фаза 4: Proactive Logic & Nudges (3-4 дня)

**Цель**: умная система проактивных сообщений.

**Файлы**:
- `services/coaching_proactive.py` — trigger engine
- `bot/schedulers/coaching_scheduler.py` — APScheduler jobs

**Что реализуется:**
- Все триггеры из раздела 5.2
- Antispam логика
- Morning brief
- Evening check-in prompt
- Sunday review prompt
- Reactivation сценарий

**Тестируется:**
- Корректность срабатывания триггеров
- Antispam (не более N сообщений в день)
- Тихие часы соблюдаются

**Ожидаемый результат:** Коуч проактивно пишет в нужные моменты.

---

### Фаза 5: REST API (3-4 дня)

**Цель**: полный API слой.

**Файлы**:
- `api/routers/coaching.py` — все endpoints из раздела 14

**Что реализуется:**
- Все 40+ endpoints
- Dashboard aggregation endpoint
- Pydantic схемы с валидацией
- Auth через существующий get_current_user

**Тестируется:**
- Все endpoints (pytest + httpx)
- Auth проверки
- Pydantic валидация edge cases

---

### Фаза 6: Mini App UI (7-10 дней)

**Цель**: полноценный UI модуля Coaching.

**Файлы**:
- `miniapp/src/features/coaching/` — все компоненты из раздела 13
- `miniapp/src/api/coaching.ts` — хуки React Query

**Что реализуется:**
- CoachingDashboard с daily state card
- GoalsPage + GoalDetailPage
- HabitsPage + HabitDetailSheet
- CheckInPage
- WeeklyReviewPage
- InsightsPage
- Все пустые состояния
- CoachPromptBubble компонент

**Тестируется:**
- Каждый экран рендерится без ошибок
- Пустые состояния корректны
- Quick logging работает

---

### Фаза 7: Onboarding & Guidance Layer (2-3 дня)

**Цель**: онбординг и обучение через интерфейс.

**Файлы**:
- `miniapp/src/features/coaching/OnboardingPage.tsx`
- Обновления в coaching_agent.py (onboarding промпт)
- coaching_onboarding_state CRUD

**Что реализуется:**
- 4-шаговый онбординг в Mini App
- Contextual prompt examples (CoachPromptBubble)
- Sample prompts в пустых состояниях
- Semi-educational micro-вставки в агенте
- /start интеграция в боте

---

### Фаза 8: Personalization Layer (3-4 дня)

**Цель**: адаптивный профиль пользователя.

**Файлы**:
- `services/coaching_personalization.py`
- Обновления в coaching_engine.py
- CRUD для coaching_memory, behavior_patterns

**Что реализуется:**
- Накопление implicit preferences
- Адаптация тона на основе memory
- Адаптация времени nudges
- Behavioral pattern detection
- Profile reset functionality

---

### Фаза 9: Integrations (3-4 дня)

**Цель**: связи с другими модулями.

**Файлы**:
- `tools/coaching_context_tools.py` — дополнить cross-module запросами
- Обновления в coaching_engine.py (cross-module state)

**Что реализуется:**
- Полный cross-module snapshot (Tasks + Calendar + Fitness + Nutrition)
- Orchestration actions (create_task, create_event)
- Cross-module recommendations
- Integration в coaching_context_snapshot

---

### Фаза 10: Analytics, Polish & Migrations (2-3 дня)

**Цель**: аналитика, тесты, финальная полировка.

**Файлы**:
- `api/routers/coaching.py` — analytics endpoints
- Alembic finalize migrations
- Tests finalization

**Что реализуется:**
- Weekly score calculation
- Dropout risk scoring
- Habit consistency analytics
- Goal completion forecast
- Финальная полировка UX

---

## 24. DEFINITION OF DONE

### Telegram chat
- Создание цели естественным языком → сохраняется в БД
- Создание привычки → сохраняется + reminder создаётся
- Логирование привычки одной фразой → обновляет streak
- Daily check-in через кнопки → сохраняется + обновляет state
- Weekly review через диалог → генерирует summary
- Коуч проактивно пишет по триггерам → antispam соблюдается
- Корректировка цели follow-up сообщениями работает

### Telegram кнопки
- Все кнопки из раздела 9 функционируют
- Контекстные кнопки появляются в нужных ситуациях
- Onboarding кнопки ведут в правильные flow

### Mini App
- Все 8 экранов реализованы и работают
- Dashboard загружается одним запросом
- Quick logging привычки — 1 тап
- Пустые состояния с CTA во всех разделах
- Онбординг проходится полностью

### API
- Все 40+ endpoints работают
- Dashboard endpoint <500ms
- Pydantic валидация отражает ошибки корректно

### Proactive mode
- Все 17 триггеров срабатывают по условиям
- Antispam ≤ 3 сообщения/день
- Тихие часы соблюдаются
- Reactivation сценарий работает после 5 дней молчания

### Onboarding
- Новый пользователь проходит онбординг
- Prompt examples показываются в пустых состояниях
- Micro-обучающие вставки появляются в нужных моментах

### Personalization
- Коуч адаптирует тон через 3-5 сессий
- Время nudges адаптируется под активность пользователя
- Behavioral patterns детектируются после 14+ дней

### Логирование
- Все coaching sessions логируются
- Nudges log ведётся
- Orchestration actions логируются
- Coaching errors в structured log

### MVP (минимально готовый модуль)
Фазы 1, 2, 3, 4, 5, 6 — обязательно.

### Advanced version
Фазы 7, 8, 9, 10 — расширение и полировка.

---

> Документ создан: 2026-03-14
> Проект: Personal & Business Assistant
> Версия для: Warp AI реализации

