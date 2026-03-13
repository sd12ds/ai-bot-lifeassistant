# Nutrition Tracker — Архитектура модуля

## 1. Обзор
Модуль трекинга питания позволяет пользователю:
- **Фотографировать еду** → AI распознаёт продукты, оценивает граммовку и КБЖУ
- **Редактировать** распознанные данные (продукты, порции, нутриенты)
- **Логировать вручную** через текст или голос («съел 200г куриной грудки и рис»)
- **Отслеживать воду** (стаканы, мл)
- **Устанавливать цели** (суточный калораж, БЖУ, вода)
- **Просматривать статистику** (день / неделя / месяц)
- **Видеть прогресс** в Miniapp (дашборд с прогресс-барами)

## 2. Поток распознавания фото

```
Пользователь               Telegram Bot                 GPT-4o Vision              БД
    │                           │                            │                      │
    ├── 📸 фото еды ──────────►│                            │                      │
    │                           ├── скачать файл             │                      │
    │                           ├── base64 + prompt ────────►│                      │
    │                           │                            ├── JSON ответ          │
    │                           │◄── [{name, amount_g,       │   (продукты +        │
    │                           │      calories, p, f, c}]   │    граммовка)        │
    │                           │                            │                      │
    │◄── карточка приёма пищи ──┤                            │                      │
    │    с кнопками:            │                            │                      │
    │    [✅ Сохранить]          │                            │                      │
    │    [✏️ Редактировать]      │                            │                      │
    │    [🗑 Отменить]           │                            │                      │
    │                           │                            │                      │
    ├── ✅ Сохранить ──────────►│                            │                      │
    │                           ├── save meal ──────────────────────────────────────►│
    │◄── «Сохранено! 520 ккал» ─┤                            │                      │
```

### 2.1 Prompt для GPT-4o Vision
Системный промпт для анализа фото еды:
- Определить все продукты/блюда на фото
- Оценить вес каждого продукта в граммах
- Рассчитать КБЖУ на основе оценённого веса
- Определить тип приёма пищи (breakfast/lunch/dinner/snack) по времени
- Вернуть структурированный JSON

Формат ответа:
```json
{
  "meal_type": "lunch",
  "items": [
    {
      "name": "Куриная грудка (варёная)",
      "amount_g": 150,
      "calories": 165,
      "protein_g": 31,
      "fat_g": 3.6,
      "carbs_g": 0
    },
    {
      "name": "Рис белый",
      "amount_g": 200,
      "calories": 260,
      "protein_g": 5.4,
      "fat_g": 0.6,
      "carbs_g": 57
    }
  ],
  "total": {
    "calories": 425,
    "protein_g": 36.4,
    "fat_g": 4.2,
    "carbs_g": 57
  }
}
```

### 2.2 Карточка приёма пищи (Telegram)
После распознавания бот отправляет сообщение вида:

```
🍽 Обед · 12:35

🔸 Куриная грудка (варёная) — 150г
   165 ккал · Б 31 · Ж 3.6 · У 0

🔸 Рис белый — 200г
   260 ккал · Б 5.4 · Ж 0.6 · У 57

─────────────────
📊 Итого: 425 ккал · Б 36.4 · Ж 4.2 · У 57

[✅ Сохранить] [✏️ Редактировать] [🗑 Отменить]
```

При нажатии «Редактировать» — бот отправляет inline-кнопки для каждого продукта → пользователь может:
- Изменить граммовку (ввод числа)
- Удалить продукт
- Добавить продукт (текстом)

## 3. Архитектура компонентов

### 3.1 Новые файлы
```
agents/personal/nutrition_agent.py    — LangGraph агент питания
tools/nutrition_tools.py              — Tool-функции (meal_log, food_photo, water_log, stats, goals)
bot/handlers/photo.py                 — Обработчик фото (photo → Vision API)
integrations/vision/food_recognizer.py — Обёртка GPT-4o Vision для распознавания еды
db/nutrition_storage.py               — CRUD для meals, food_items, water_logs, goals
api/routers/nutrition.py              — REST API для miniapp
miniapp/src/features/nutrition/       — React-компоненты (NutritionPage, MealCard, WaterWidget, GoalsForm)
scripts/seed_food_items.py            — Сид БД: ~200 популярных продуктов с КБЖУ
```

### 3.2 NutritionAgent
Агент обрабатывает запросы пользователя через LangGraph. Ключевые tools:

| Tool | Описание | Параметры |
|------|----------|-----------|
| `meal_log` | Логирование приёма пищи из текста | `items: [{name, amount_g}], meal_type` |
| `meal_photo` | Распознавание еды по фото | `photo_base64` |
| `meal_edit` | Редактирование приёма пищи | `meal_id, updates` |
| `meal_delete` | Удаление приёма пищи | `meal_id` |
| `water_log` | Логирование воды | `amount_ml` |
| `nutrition_stats` | Статистика КБЖУ за период | `period: today/week/month` |
| `nutrition_goals_set` | Установка целей | `calories, protein_g, fat_g, carbs_g, water_ml` |
| `food_search` | Поиск продукта в справочнике | `query` |

### 3.3 Интеграция в Supervisor
Добавить `nutrition` в classify_intent:
```
nutrition — еда, питание, калории, КБЖУ, приём пищи, вода, диета, продукты, перекус
```
Обработка фото:
- `bot/handlers/photo.py` перехватывает все фото
- Если контекст = питание → отправляет в `food_recognizer`
- Если контекст неясен → спрашивает «Это фото еды?» или анализирует автоматически

## 4. Схема данных (уже в models.py)

Существующие модели полностью покрывают потребности:
- `FoodItem` — справочник (системный + пользовательский)
- `Meal` — приём пищи (тип, время)
- `MealItem` — продукт в приёме (food_item + amount_g)
- `WaterLog` — лог воды
- `NutritionGoal` — суточные цели

### 4.1 Необходимые доработки модели Meal
Добавить поле `photo_file_id` (Telegram file_id оригинального фото) — для отображения в miniapp.

### 4.2 Необходимые доработки модели MealItem
Расширить кеширование КБЖУ на момент логирования:
- `calories_snapshot` — ккал на момент записи (если продукт удалят/изменят, данные не потеряются)
- `protein_snapshot`, `fat_snapshot`, `carbs_snapshot`

## 5. API (FastAPI)

### 5.1 Эндпоинты
- `GET /api/nutrition/today` — сводка за сегодня (meals + totals + water + goals)
- `GET /api/nutrition/meals?date_from=&date_to=` — история приёмов
- `GET /api/nutrition/meal/{id}` — детали приёма
- `POST /api/nutrition/meal` — создать приём (из miniapp)
- `PUT /api/nutrition/meal/{id}` — редактировать
- `DELETE /api/nutrition/meal/{id}` — удалить
- `POST /api/nutrition/water` — залогировать воду
- `GET /api/nutrition/stats?period=week` — статистика
- `GET /api/nutrition/goals` — текущие цели
- `PUT /api/nutrition/goals` — обновить цели
- `GET /api/nutrition/food/search?q=` — поиск продуктов

### 5.2 Формат ответа `/api/nutrition/today`
```json
{
  "date": "2026-03-10",
  "goals": {"calories": 2200, "protein_g": 150, "fat_g": 70, "carbs_g": 250, "water_ml": 2000},
  "totals": {"calories": 1450, "protein_g": 98, "fat_g": 42, "carbs_g": 165},
  "water_ml": 1200,
  "meals": [
    {
      "id": 1,
      "meal_type": "breakfast",
      "eaten_at": "2026-03-10T08:30:00+03:00",
      "photo_file_id": null,
      "items": [
        {"name": "Овсянка на воде", "amount_g": 250, "calories": 190, "protein_g": 6.5, "fat_g": 3.5, "carbs_g": 33}
      ],
      "total_calories": 190
    }
  ]
}
```

## 6. Miniapp — UI

### 6.1 NutritionPage
Основной экран: круговая диаграмма калорий (потреблено / цель), прогресс-бары для Б/Ж/У, водный баланс.

### 6.2 Компоненты
- `CalorieRing` — кольцевая диаграмма (потреблено/осталось)
- `MacroProgressBar` — горизонтальный прогресс-бар для каждого макронутриента
- `WaterTracker` — стаканы воды (тап = +250 мл)
- `MealCard` — карточка приёма пищи (тип, время, продукты, фото если есть)
- `MealEditor` — форма редактирования (продукты, граммовка)
- `FoodSearch` — поиск продукта с автокомплитом
- `GoalsForm` — настройка целей
- `NutritionHistory` — график за неделю/месяц (recharts)

### 6.3 Навигация
Добавить иконку 🍎 в BottomNav miniapp (между задачами и календарём).

## 7. Сид данных — справочник продуктов

Предзаполнить `food_items` (~200 записей, `user_id = NULL` — системные):
- Крупы и каши (овсянка, рис, гречка, булгур...)
- Мясо и птица (куриная грудка, говядина, свинина...)
- Рыба и морепродукты (лосось, тунец, креветки...)
- Молочные (творог, молоко, сыр, йогурт...)
- Овощи и фрукты
- Хлеб и выпечка
- Напитки
- Фастфуд и готовые блюда
- Масла и соусы
- Снэки и сладости

Данные КБЖУ на 100г из открытых источников (USDA / CalorizatorRU).

## 8. Порядок реализации

**Шаг 1**: `integrations/vision/food_recognizer.py` + `db/nutrition_storage.py`
**Шаг 2**: `tools/nutrition_tools.py` + `agents/personal/nutrition_agent.py`
**Шаг 3**: `bot/handlers/photo.py` + интеграция в supervisor
**Шаг 4**: `api/routers/nutrition.py`
**Шаг 5**: Miniapp компоненты
**Шаг 6**: `scripts/seed_food_items.py` + деплой
**Шаг 7**: Тестирование E2E

## 9. Зависимости
- **GPT-4o** (или GPT-4o-mini) — Vision API для фото-распознавания (уже используется для чата)
- **Никаких новых пакетов** — всё через OpenAI SDK, который уже установлен
- Добавить `photo_file_id: Optional[str]` в модель `Meal` (миграция Alembic)
- Добавить snapshot-поля в `MealItem` (миграция Alembic)
