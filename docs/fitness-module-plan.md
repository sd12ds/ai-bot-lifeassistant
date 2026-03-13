# Фитнес-модуль — детальный план разработки

Второй ключевой модуль продукта. Работает в связке с Питанием, образуя единый AI-контур здоровья.
Три канала ввода: Mini App, бот текстом, бот голосом.

## Текущее состояние

**БД (уже есть модели в `db/models.py`):**
- `ExerciseLibrary` — справочник упражнений (name, category, muscle_group)
- `WorkoutTemplate` / `WorkoutTemplateExercise` — шаблоны тренировок
- `WorkoutSession` / `WorkoutSet` — фактические тренировки и подходы
- `BodyMetric` — замеры тела (weight, body_fat, chest, waist, hips)

**Чего НЕТ:**
- Storage-слой (аналог `nutrition_storage.py`)
- API роутер (аналог `api/routers/nutrition.py`)
- Fitness-агент и tools для бота
- Фронтенд (заглушка `ComingSoon`)
- Справочник упражнений (seed data)
- Система прогресса, рекордов, streak
- Связка с питанием
- Программы тренировок

## Архитектура (по аналогии с Nutrition)

```
Бот (текст/голос) → Supervisor → FitnessAgent → fitness_tools.py → fitness_storage.py → БД
Mini App → api/routers/fitness.py → fitness_storage.py → БД
```

Файловая структура:
- `db/fitness_storage.py` — CRUD + бизнес-логика
- `tools/fitness_tools.py` — LangChain tools для агента
- `agents/personal/fitness_agent.py` — агент с промптом
- `api/routers/fitness.py` — REST API для Mini App
- `miniapp/src/api/fitness.ts` — API-клиент
- `miniapp/src/features/fitness/` — React-компоненты
- `services/fitness_insights.py` — аналитика, рекорды, советы
- `scripts/seed_exercises.py` — наполнение справочника

---

## Фаза 1 — Фундамент: БД, Storage, Seed

### 1.1 Доработка схемы БД

Текущие модели покрывают базу, но нужны расширения:

**ExerciseLibrary — расширить:**
- `equipment` (String, nullable) — штанга, гантели, тренажёр, без оборудования, турник
- `difficulty` (String, default "intermediate") — beginner / intermediate / advanced
- `is_compound` (Boolean, default False) — базовое или изолирующее
- `instructions` (Text, default "") — краткое описание техники
- `aliases` (JSONB, default []) — русские варианты названий для голосового поиска ("жим лёжа", "bench press")

**WorkoutSession — расширить:**
- `workout_type` (String, default "strength") — strength / cardio / home / functional / stretching
- `total_volume_kg` (Float, nullable) — суммарный объём (подходы × повторы × вес)
- `total_duration_sec` (Integer, nullable) — общее время тренировки
- `calories_burned` (Float, nullable) — оценка сожжённых калорий
- `mood_before` (Integer, nullable) — настроение до (1-5)
- `mood_after` (Integer, nullable) — настроение после (1-5)

**WorkoutSet — расширить:**
- `distance_m` (Float, nullable) — дистанция для кардио (метры)
- `pace_sec_per_km` (Integer, nullable) — темп для бега
- `set_type` (String, default "working") — warmup / working / drop / failure

**BodyMetric — расширить:**
- `bicep_cm` (Float, nullable) — бицепс
- `thigh_cm` (Float, nullable) — бедро
- `energy_level` (Integer, nullable) — уровень энергии (1-5)
- `sleep_hours` (Float, nullable) — сон
- `recovery_rating` (Integer, nullable) — восстановление (1-5)
- `photo_file_id` (String, nullable) — фото прогресса (Telegram file_id)
- `notes` (Text, default "") — заметки

**Новая модель — FitnessGoal:**
- `user_id` (FK users)
- `goal_type` — lose_weight / gain_muscle / maintain / endurance / strength / home_fitness / return_to_form
- `workouts_per_week` (Integer, default 3)
- `preferred_duration_min` (Integer, default 60)
- `training_location` — gym / home / outdoor / mixed
- `available_equipment` (JSONB, default []) — список доступного инвентаря
- `experience_level` — beginner / intermediate / advanced
- `current_program_id` (FK workout_templates, nullable)

**Новая модель — WorkoutProgram:**
- `id`, `user_id`, `name`, `description`
- `goal_type`, `duration_weeks`, `days_per_week`
- `difficulty`, `location` (gym/home/mixed)
- `is_active` (Boolean)
- `created_at`, `started_at`
- связь: `days: List[WorkoutProgramDay]`

**Новая модель — WorkoutProgramDay:**
- `program_id` (FK)
- `day_number` (1, 2, 3...)
- `day_name` ("День 1: Грудь + Трицепс")
- `template_id` (FK workout_templates)

**Новая модель — PersonalRecord:**
- `user_id`, `exercise_id`
- `record_type` — max_weight / max_reps / max_volume / best_time / max_distance
- `value` (Float)
- `achieved_at` (DateTime)
- `session_id` (FK)

**Новая модель — ActivityLog:**
- `user_id`
- `activity_type` — steps / run / walk / cycling / swimming / other
- `value` (Float) — кол-во (шаги, км, минуты)
- `unit` — steps / km / min / m
- `duration_min` (Integer, nullable)
- `calories_burned` (Float, nullable)
- `logged_at` (DateTime)
- `notes` (Text)

### 1.2 Seed: справочник упражнений

Файл: `scripts/seed_exercises.py`
Минимум 80-100 упражнений, покрывающих:

**Силовые (strength):**
- Грудь: жим лёжа, жим гантелей, разводка, отжимания, жим в наклоне
- Спина: тяга штанги, тяга гантели, подтягивания, тяга верхнего блока, гиперэкстензия
- Ноги: приседания, жим ногами, выпады, румынская тяга, разгибания, сгибания
- Плечи: жим стоя, махи в стороны, махи перед собой, тяга к подбородку
- Бицепс: сгибания штанги, молотки, концентрированные сгибания
- Трицепс: французский жим, разгибания на блоке, отжимания на брусьях
- Кор: планка, скручивания, подъём ног, русский твист

**Кардио (cardio):**
- Бег, ходьба, велосипед, эллипс, плавание, скакалка, гребля

**Домашние (home):**
- Отжимания (варианты), приседания без веса, бёрпи, прыжки, планка (варианты), jumping jacks, mountain climbers

**Растяжка/мобильность (flexibility):**
- Растяжка квадрицепсов, хамстрингов, грудных, плеч, спины, шпагат

Каждое упражнение с полями:
- `name` (русское), `category`, `muscle_group`, `equipment`, `difficulty`
- `aliases` — массив вариантов названий: ["жим лёжа", "bench press", "жим штанги лёжа"]
- `is_compound`, `instructions`

### 1.3 Storage-слой

Файл: `db/fitness_storage.py`

Функции (async):

**Упражнения:**
- `search_exercises(query, category, muscle_group, limit)` — поиск по имени/алиасам
- `get_exercise(exercise_id)` → dict

**Тренировки (сессии):**
- `start_workout(user_id, name, workout_type, template_id?)` → dict (создаёт WorkoutSession)
- `finish_workout(session_id, user_id)` → dict (ставит ended_at, считает total_volume)
- `add_set(session_id, exercise_id, reps, weight_kg, duration_sec?, distance_m?, set_type?)` → dict
- `delete_set(set_id, user_id)` → bool
- `log_workout(user_id, name, workout_type, exercises_data, notes?)` → dict (быстрый лог без start/finish — для бота)
- `get_session(session_id, user_id)` → dict (с упражнениями и подходами)
- `get_sessions_for_date(user_id, date)` → list
- `get_sessions_for_range(user_id, date_from, date_to)` → list
- `delete_session(session_id, user_id)` → bool
- `repeat_workout(session_id, user_id, progression_kg?)` → dict (копирует тренировку, опционально +вес)

**Шаблоны:**
- `create_template(user_id, name, exercises_data)` → dict
- `list_templates(user_id)` → list
- `apply_template(template_id, user_id)` → dict (создаёт сессию из шаблона)
- `delete_template(template_id, user_id)` → bool

**Программы:**
- `create_program(user_id, name, goal_type, days_data)` → dict
- `get_active_program(user_id)` → dict|None
- `get_next_workout(user_id)` → dict (следующая тренировка из программы)

**Показатели тела:**
- `add_body_metric(user_id, weight_kg?, body_fat_pct?, chest_cm?, waist_cm?, ...)` → dict
- `get_body_metrics(user_id, limit)` → list
- `get_latest_body_metric(user_id)` → dict|None

**Активность:**
- `log_activity(user_id, activity_type, value, unit, duration_min?, calories?)` → dict
- `get_activity_for_date(user_id, date)` → list

**Прогресс и рекорды:**
- `get_personal_records(user_id, exercise_id?)` → list
- `check_and_update_records(user_id, session_id)` → list[новые рекорды]
- `get_workout_stats(user_id, period)` → dict (today/week/month)
- `get_streak(user_id)` → dict (текущий streak, максимальный streak)
- `get_exercise_progress(user_id, exercise_id, period)` → list (история весов/повторов)

**Фитнес-цели:**
- `set_fitness_goal(user_id, goal_type, workouts_per_week, ...)` → dict
- `get_fitness_goal(user_id)` → dict|None

---

## Фаза 2 — Бот: Fitness Agent + Tools

### 2.1 Fitness Tools

Файл: `tools/fitness_tools.py` → `make_fitness_tools(user_id)`

**workout_log** — залогировать тренировку:
- Принимает JSON с упражнениями, подходами, весами
- Поддерживает текстовый парсинг: "жим 80x8 3" → 3 подхода по 8 повторов с 80кг
- Определяет workout_type автоматически

**workout_repeat** — повторить тренировку:
- По ID или "последнюю" / "прошлую на грудь"
- Опционально с прогрессией (+2.5кг, +5кг)

**workout_stats** — статистика:
- today / week / month
- Streak, кол-во тренировок, объём, рекорды

**exercise_search** — поиск упражнения:
- По имени, группе мышц, категории
- Возвращает описание и технику

**body_metric_log** — записать замеры:
- Вес, замеры, самочувствие, энергия

**activity_log** — записать активность:
- Шаги, бег, ходьба, вело, плавание

**fitness_goal_set** — установить фитнес-цель:
- Цель, уровень, локация, инвентарь, частота

**program_info** — информация о программе:
- Текущая программа, следующая тренировка

### 2.2 Fitness Agent

Файл: `agents/personal/fitness_agent.py`

Промпт должен включать:

**Распознавание форматов ввода:**
- "жим 80x8 3" → жим лёжа, 80кг, 8 повторов, 3 подхода
- "жим 80 на 8, 3 подхода" → то же
- "присед 100x5, 105x5, 110x3" → 3 подхода с разным весом
- "пробежал 5 км за 31 минуту" → кардио: бег, 5 км, 31 мин
- "50 отжиманий" → домашняя: отжимания, 50 повторов
- "тренировка ноги" → создать сессию с типом "ноги"
- "повтори прошлую тренировку" → repeat
- "повтори прошлую на грудь +2.5" → repeat с прогрессией

**Голосовые примеры:**
- "Запиши тренировку: жим лёжа 80 на 8, потом 85 на 6, потом разводка и трицепс"
- "Сегодня бег 40 минут в среднем темпе"
- "Сделал домашнюю тренировку: отжимания, приседания и планка"

**Контекст диалога:**
- Помнить текущую тренировку
- "добавь ещё подход" — к последнему упражнению
- "а теперь трицепс" — продолжить ту же тренировку

**Связка с питанием:**
- После записи тренировки — рекомендация по белку
- Если есть цели по питанию — показать остаток

### 2.3 Supervisor: маршрутизация

Файл: `agents/supervisor.py`

Добавить:
- `fitness` в `AgentType`
- Ключевые слова: тренировка, жим, присед, бег, кардио, подход, повторы, вес, упражнение, отжимания, подтягивания, спина, ноги, грудь, бицепс, трицепс, плечи, фитнес, зал, программа тренировок, streak, рекорд, замеры, замер тела
- Ноду `run_fitness` по аналогии с `run_nutrition`

---

## Фаза 3 — REST API для Mini App

Файл: `api/routers/fitness.py`
Префикс: `/api/fitness`

### Эндпоинты:

**Упражнения:**
- `GET /exercises/search?q=...&category=...&muscle_group=...`
- `GET /exercises/{id}`

**Тренировки (сессии):**
- `POST /sessions` — начать / залогировать
- `GET /sessions?date=...&from=...&to=...`
- `GET /sessions/{id}`
- `DELETE /sessions/{id}`
- `POST /sessions/{id}/repeat`
- `POST /sessions/{id}/sets`
- `DELETE /sets/{id}`
- `PUT /sessions/{id}/finish`

**Шаблоны:**
- `GET /templates`
- `POST /templates`
- `POST /templates/{id}/apply`
- `DELETE /templates/{id}`

**Показатели тела:**
- `POST /body-metrics`
- `GET /body-metrics?limit=...`
- `GET /body-metrics/latest`

**Активность:**
- `POST /activities`
- `GET /activities?date=...`

**Прогресс:**
- `GET /stats?period=today|week|month`
- `GET /records`
- `GET /streak`
- `GET /exercises/{id}/progress?period=...`

**Программы:**
- `GET /programs/active`
- `GET /programs/next-workout`
- `POST /programs`

**Цели:**
- `GET /goals`
- `PUT /goals`

---

## Фаза 4 — Mini App: Фронтенд

### 4.1 Структура файлов

```
miniapp/src/
  api/fitness.ts
  features/fitness/
    FitnessPage.tsx
    WorkoutSession/
      ActiveWorkout.tsx
      WorkoutComplete.tsx
      SetInput.tsx
      ExerciseCard.tsx
    History/
      WorkoutHistory.tsx
      WorkoutDetail.tsx
    Progress/
      ProgressDashboard.tsx
      WeightChart.tsx
      VolumeChart.tsx
      BodyChart.tsx
      StreakBadge.tsx
      RecordCard.tsx
    Body/
      BodyMetricsPage.tsx
      BodyMetricForm.tsx
      ProgressPhotos.tsx
    Programs/
      ProgramsList.tsx
      ProgramDetail.tsx
      ProgramCreate.tsx
    QuickLog/
      QuickWorkoutSheet.tsx
      ExerciseSearch.tsx
    shared/
      WorkoutTypeBadge.tsx
      MuscleGroupIcon.tsx
      WeeklySummary.tsx
```

### 4.2 Главная страница — FitnessPage.tsx

Структура (скролл сверху вниз):
1. **Заголовок** — "Фитнес" + дата
2. **Streak-виджет** — текущий streak дней тренировок 🔥
3. **Недельная активность** — 7 кружков (Пн-Вс), заполненные = дни тренировок
4. **Быстрые действия:**
   - "Начать тренировку" (primary button)
   - "Повторить последнюю" (если есть)
   - "Следующая по программе" (если есть активная программа)
5. **Сегодняшние тренировки** — карточки (если есть)
6. **Прогресс-сводка:**
   - Тренировок за неделю: X/Y цель
   - Общий объём за неделю
   - Новые рекорды
7. **Замеры тела** — компактный виджет (последний вес + тренд)
8. **Навигация:**
   - История тренировок
   - Мои программы
   - Замеры тела
   - Прогресс

### 4.3 Активная тренировка — ActiveWorkout.tsx

Экран с таймером:
- Таймер тренировки (время с начала)
- Список добавленных упражнений
- Для каждого упражнения: подходы (вес × повторы), кнопка "+ подход"
- Кнопка "+ упражнение" → ExerciseSearch → выбрать → добавить
- Таймер отдыха между подходами (с вибрацией)
- Кнопка "Завершить тренировку"

### 4.4 Экран завершения — WorkoutComplete.tsx

После завершения тренировки:
- Длительность, объём, кол-во упражнений
- Новые рекорды (если есть) — с анимацией 🎉
- Настроение после (1-5 смайлики)
- Кнопка "Сохранить как шаблон"
- **Связка с питанием:** "Ты потратил ~350 ккал. Тебе нужно ещё 40г белка сегодня."

---

## Фаза 5 — AI-фичи и связка с Питанием

### 5.1 Умные советы (services/fitness_insights.py)
- После тренировки: сколько белка добрать, остаток калорий
- Определение overtraining: >6 тренировок в неделю или одна группа мышц 3 дня подряд
- Рекомендация дня отдыха
- Определение plateau: вес не растёт 3+ недели → совет
- Weekly summary: кол-во тренировок, прогресс, что улучшить

### 5.2 AI-генерация программ
- Пользователь задаёт параметры (цель, уровень, инвентарь, частота)
- LLM генерирует программу из справочника упражнений
- Программа сохраняется как WorkoutProgram с днями и шаблонами
- Возможность адаптировать: "замени жим гантелей на отжимания"

### 5.3 Связка Fitness ↔ Nutrition
- Тренировка завершена → бот: "Отличная тренировка! Тебе нужно ещё Xг белка сегодня"
- День с высокой нагрузкой → корректировка калорийной цели (+200-300 ккал)
- Неделя хороших тренировок → сравнение с дисциплиной по питанию
- Снижение весов + дефицит калорий → предупреждение
- Плохое восстановление → рекомендации по питанию и сну

### 5.4 Мотивация и удержание
- **Streak** — непрерывная серия дней с тренировками
- **Бейджи:** первая тренировка, 7 дней подряд, 30 дней, 100 тренировок, первый рекорд, жим своего веса
- **Недельная цель** — X тренировок в неделю (из FitnessGoal)
- **Напоминания** — "Ты обычно тренируешься в среду, а сегодня среда 💪"
- **Итоги недели** — автоматический weekly report в чат
- **Рекорды** — уведомление при новом PR

---

## Порядок реализации (приоритет)

**Спринт 1 — MVP бот + базовый UI (1-2 недели):**
1. Расширение моделей БД + миграция
2. Seed упражнений
3. `fitness_storage.py` — базовые функции
4. `fitness_tools.py` + `fitness_agent.py` → бот умеет логировать тренировки
5. Supervisor: маршрутизация в fitness

**Спринт 2 — Mini App базовый (1-2 недели):**
6. `api/routers/fitness.py` — CRUD эндпоинты
7. `FitnessPage.tsx` — главная с виджетами
8. `QuickWorkoutSheet.tsx` — быстрый лог
9. `WorkoutHistory.tsx` — история
10. `ExerciseSearch.tsx` — поиск упражнений

**Спринт 3 — Активная тренировка + прогресс (1-2 недели):**
11. `ActiveWorkout.tsx` — живая тренировка с таймером
12. `WorkoutComplete.tsx` — экран завершения
13. `ProgressDashboard.tsx` — графики
14. Рекорды и streak

**Спринт 4 — Программы + AI + Связка (1-2 недели):**
15. Программы тренировок (WorkoutProgram)
16. AI-генерация программ
17. Связка с питанием
18. Weekly summary
19. Мотивация, бейджи, напоминания
20. Замеры тела + фото прогресса
