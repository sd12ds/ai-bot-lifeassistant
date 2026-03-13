# Загрузка и редактирование программы тренировок через чат

## 1. Проблема
Сейчас программа тренировок создаётся только через miniapp (ProgramEditorPage) или через API `/programs/generate`.
Пользователь не может:
- Скинуть свою программу обычным текстом/голосом и получить структурированную программу
- Редактировать упражнения через чат: «замени французский жим на жим узким хватом»
- Добавить/удалить упражнение голосовой командой

## 2. Текущая архитектура (что уже есть)
### Модели БД (менять НЕ нужно)
- `WorkoutProgram` → `WorkoutProgramDay` (day_number, day_name, template_id)
- `WorkoutTemplate` → `WorkoutTemplateExercise` (exercise_id, sets, reps, weight_kg, rest_sec, sort_order)
- `ExerciseLibrary` (name, category, muscle_group, equipment, aliases JSONB)

### Storage-функции (db/fitness_storage.py)
- `create_program(...)` — создаёт программу с днями
- `create_template(...)` — создаёт шаблон с упражнениями (exercises_data)
- `update_program_day(day_id, ..., exercises_data)` — обновляет день, пересоздаёт шаблон
- `add_program_day(program_id, ..., exercises_data)` — добавляет день
- `remove_program_day(day_id, ...)` — удаляет день
- `search_exercises(query)` — поиск по name + aliases (ILIKE)

### Fitness agent
- Промпт ориентирован на логирование тренировок, НЕ на управление программами
- Tools: `program_info()`, `next_workout_tool()` — только чтение
- Нет tool для создания/редактирования программы

### API + Miniapp
- REST API: полный CRUD для programs/days/templates
- ProgramEditorPage: визуальный редактор (работает)

## 3. Целевое поведение (UX-сценарии)

### Сценарий A: Загрузка программы из текста
```
Пользователь: [скидывает текст программы — 3 дня, 21 упражнение]

Бот: 📋 Распознал программу тренировок — 3 дня:

День 1 (Ноги + трицепс):
  1. Болгарские сплит-приседания в Смите ✅
  2. Румынская тяга со штангой ✅
  3. Разгибание бедра стоя в кроссовере ✅
  4. Сгибание голени лёжа в тренажёре ✅
  5. Горизонтальный жим платформы ✅
  6. Французский жим лёжа с гантелями ✅
  7. Сгибание предплечья сидя на скамье ✅

День 2 (Спина + грудь + пресс):
  1. Подтягивания в гравитроне прямым хватом ✅
  ...

День 3 (Ноги + плечи):
  ...

✅ = найдено в справочнике | ⚠️ = создано как пользовательское

[Сохранить программу] [Изменить]
```

### Сценарий B: Редактирование через чат/голос
```
Пользователь: замени французский жим на жим узким хватом
Бот: ✅ День 1: заменил «Французский жим лёжа с гантелями» → «Жим штанги узким хватом»

Пользователь: добавь подъём на бицепс в день 2
Бот: ✅ День 2: добавил «Подъём штанги на бицепс» (позиция 8)

Пользователь: убери пресс из второго дня
Бот: ✅ День 2: убрал «Пресс (сгибание бёдер лёжа с приподниманием таза)»

Пользователь: поменяй местами день 1 и день 3
Бот: ✅ День 1 ↔ День 3 — поменял местами

Пользователь: покажи программу
Бот: [полная карточка со всеми днями и упражнениями]
```

### Сценарий C: Голосовой ввод
Голос уже конвертируется в текст через voice handler. Далее fitness agent обрабатывает как обычный текст. Специальной логики не нужно.

## 4. Архитектура решения

### 4.1. Новый сервис: `services/workout_program_parser.py`
Парсер текста программы тренировок через LLM.

**Вход**: произвольный текст (как в примере пользователя)
**Выход**: структурированный JSON:
```json
{
  "name": "Программа 3 дня (Ноги-Верх-Ноги)",
  "days": [
    {
      "day_number": 1,
      "day_name": "Ноги + трицепс",
      "exercises": [
        {"name": "Болгарские сплит-приседания в Смите с опорой о скамью", "sets": 3, "reps": 12},
        {"name": "Румынская тяга со штангой", "sets": 3, "reps": 10},
        ...
      ]
    },
    ...
  ]
}
```

**Логика**:
1. LLM (gpt-4.1-mini) парсит текст → JSON со структурой дней и упражнений
2. LLM сам определяет название программы, названия дней (по мышечным группам), дефолтные подходы/повторения
3. Если пользователь указал подходы/повторения/вес — LLM их сохраняет

### 4.2. Новый сервис: `services/exercise_matcher.py`
Маппинг названий упражнений на ExerciseLibrary.

**Алгоритм для каждого упражнения из парсера**:
1. `search_exercises(name)` — точный поиск по name + aliases
2. Если найдено 1 результат с высоким совпадением → используем его exercise_id
3. Если найдено несколько → LLM выбирает лучшее совпадение
4. Если не найдено → создаём пользовательское упражнение в ExerciseLibrary (user_id != NULL)

**Для этого нужна новая функция в fitness_storage.py**:
```python
async def get_or_create_exercise(
    user_id: int,
    name: str,
    category: str = "strength",
    muscle_group: str | None = None,
    equipment: str | None = None,
) -> dict
```
- Сначала ищет в ExerciseLibrary (ILIKE по name + aliases)
- Если не нашла — создаёт с `user_id` (пользовательское упражнение)

### 4.3. Новые tools для fitness agent (`tools/fitness_tools.py`)

#### `program_import(text: str) -> str`
Основной инструмент загрузки программы.
- Вызывает `workout_program_parser.parse(text)` → структура
- Вызывает `exercise_matcher.match_all(exercises)` → exercise_id для каждого
- Вызывает `create_program()` + `create_template()` для каждого дня
- Возвращает карточку программы с кнопками

#### `program_show() -> str`
Показать полную программу с упражнениями (расширение текущего `program_info`).
- Загружает программу + все шаблоны + все упражнения
- Форматирует в читаемую карточку по дням

#### `program_replace_exercise(exercise_old: str, exercise_new: str, day_number: int = 0) -> str`
Заменить упражнение.
- `day_number=0` → ищет во всех днях (заменяет первое вхождение)
- Матчит старое имя → находит в шаблоне → заменяет на новое (через exercise_matcher)
- Вызывает `update_program_day()` с обновлёнными exercises_data

#### `program_add_exercise(exercise_name: str, day_number: int, position: int = -1) -> str`
Добавить упражнение в день.
- `position=-1` → в конец
- Матчит имя → добавляет в шаблон дня

#### `program_remove_exercise(exercise_name: str, day_number: int = 0) -> str`
Убрать упражнение из дня.
- Матчит имя → убирает из шаблона
- `day_number=0` → ищет во всех днях

#### `program_swap_days(day_a: int, day_b: int) -> str`
Поменять местами два дня.

### 4.4. Обновление промпта fitness agent
Добавить секцию:

```
ПРОГРАММА ТРЕНИРОВОК:
Если пользователь скинул текст с программой тренировок (список дней/упражнений) → вызови program_import(text).
Для редактирования:
- «замени X на Y» → program_replace_exercise(exercise_old="X", exercise_new="Y")
- «добавь X в день N» → program_add_exercise(exercise_name="X", day_number=N)
- «убери X» → program_remove_exercise(exercise_name="X")
- «поменяй дни 1 и 3» → program_swap_days(day_a=1, day_b=3)
- «покажи программу» → program_show()
```

### 4.5. Обновление intent_classifier.py
Добавить ключевые слова в `_FITNESS_STRONG`:
- `программа тренировок`, `тренировочная программа`, `план тренировок`
- `день 1`, `день 2`, `день 3` (в контексте упражнений)

Добавить в `_FITNESS_NORMAL`:
- `замени упражнение`, `добавь упражнение`, `убери упражнение`

## 5. Поток данных

```
Текст/голос пользователя
  ↓
intent_classifier → fitness agent
  ↓
fitness agent определяет intent:
  ├─ Загрузка программы → program_import(text)
  │    ├─ workout_program_parser.parse(text) → structured JSON
  │    ├─ exercise_matcher.match_all(exercises) → exercise_ids
  │    ├─ create_program() + create_template() per day
  │    └─ → карточка программы
  │
  ├─ Редактирование → program_replace/add/remove_exercise()
  │    ├─ exercise_matcher.match(name) → exercise_id
  │    ├─ update_program_day(exercises_data)
  │    └─ → подтверждение
  │
  └─ Просмотр → program_show()
       └─ → карточка по дням
```

## 6. Файлы для создания/изменения

### Новые файлы:
- `services/workout_program_parser.py` — LLM парсер текста программы
- `services/exercise_matcher.py` — маппинг названий → ExerciseLibrary

### Изменяемые файлы:
- `db/fitness_storage.py` — добавить `get_or_create_exercise()`, `get_program_with_exercises()`
- `tools/fitness_tools.py` — добавить 6 новых tools
- `agents/personal/fitness_agent.py` — обновить промпт (секция про программы)
- `bot/core/intent_classifier.py` — добавить fitness-ключевые слова для программ

### НЕ меняем:
- `db/models.py` — текущая схема БД полностью покрывает потребности
- API роуты — чат-flow не требует новых API эндпоинтов
- Miniapp — ProgramEditorPage уже работает для визуального редактирования

## 7. Очерёдность реализации

**Этап 1**: Базовая загрузка
- `services/workout_program_parser.py`
- `services/exercise_matcher.py`
- `db/fitness_storage.py` → `get_or_create_exercise()`, `get_program_with_exercises()`
- `tools/fitness_tools.py` → `program_import()`, `program_show()`
- Обновить промпт fitness agent

**Этап 2**: Редактирование
- `tools/fitness_tools.py` → `program_replace_exercise()`, `program_add_exercise()`, `program_remove_exercise()`, `program_swap_days()`
- Обновить промпт fitness agent
- Обновить intent_classifier.py

**Этап 3**: Полировка UX
- Форматирование карточки программы (Telegram markdown)
- Inline-кнопки (опционально): подтверждение после импорта
- Обработка edge-cases: дублирующие упражнения, нет активной программы, и т.д.
