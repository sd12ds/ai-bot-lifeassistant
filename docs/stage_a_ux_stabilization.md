# Этап A — Стабилизация текущего UX: Детальный проект

## 1. Цель этапа

Устранить критические UX-проблемы в разделе питания **без капитальной перестройки архитектуры** (архитектура — Этап B).
Результат: пользователь может отправить фото с подписью, получить единый meal draft, подправить его естественным языком, подтвердить — и всё это в рамках **одного непрерывного диалога**.

### 1.1. Решаемые проблемы (из реального кейса)

| # | Проблема | Где ломается сейчас | Файл |
|---|----------|---------------------|------|
| P1 | Фото и caption обрабатываются раздельно | `photo_handler` игнорирует `message.caption` | `bot/handlers/photo.py:97` |
| P2 | Vision не получает пользовательский текст | `recognize_food_photo()` принимает только base64 | `integrations/vision/food_recognizer.py:107` |
| P3 | Бот создал 3 meal вместо 1 | photo handler и agent — изолированные pipeline'ы | `photo.py` + `text.py` |
| P4 | Редактирование граммовок — мучительный FSM | `EditMealStates.waiting_for_grams` — ввод чисел | `bot/handlers/photo.py:176` |
| P5 | Бот не понимает «занёс?», «сохранил?» | Supervisor перенаправляет в agent, но тот не знает контекст фото | `agents/supervisor.py` |
| P6 | Нет подтверждения перед сохранением через agent | `meal_log` tool сразу пишет в БД | `tools/nutrition_tools.py:24` |
| P7 | Pending meals хранятся in-memory | `_pending_meals: dict` — при рестарте теряются | `bot/handlers/photo.py:30` |

---

## 2. Текущая архитектура (AS-IS)

### 2.1. Два изолированных pipeline'а

**Pipeline 1: Фото**
```
message.photo → photo_handler → download → recognize_food_photo(base64) → _pending_meals[temp_id] → inline keyboard (save/edit/cancel) → add_meal()
```
- Caption **полностью игнорируется** (строка 97: `photo_handler` не читает `message.caption`)
- Результат хранится в `_pending_meals` dict (in-memory, volatile)
- Редактирование — через FSM (кнопка по каждому продукту → ввод числа)
- После `meal_save` → `ns.add_meal()` → сообщение обновляется → конец

**Pipeline 2: Текст**
```
message.text → text_handler → process_message(supervisor) → classify_intent → nutrition_agent → meal_log tool → ns.add_meal()
```
- Не знает о фото pipeline
- `meal_log` сразу пишет в БД без подтверждения
- Нет доступа к `_pending_meals`

### 2.2. Ключевые файлы

- `bot/handlers/photo.py` (280 строк) — полный цикл фото: handler + callbacks + FSM
- `bot/handlers/text.py` (30 строк) — проброс в supervisor
- `agents/supervisor.py` (190 строк) — классификатор + маршрутизация
- `agents/personal/nutrition_agent.py` (120 строк) — промпт + build_nutrition_agent
- `tools/nutrition_tools.py` (290 строк) — 8 tools: meal_log, meal_delete, water_log, nutrition_stats, nutrition_goals_set, meal_from_template, food_search, ewa_product_info
- `integrations/vision/food_recognizer.py` (140 строк) — GPT-4o Vision, без caption
- `db/nutrition_storage.py` (450 строк) — CRUD: add_meal, templates, search, stats

### 2.3. Регистрация роутеров (main.py)

```
photo.router  ← F.photo (приоритет выше)
voice.router  ← F.voice
text.router   ← F.text  (последний)
```

FSM-состояние `EditMealStates.waiting_for_grams` зарегистрировано в `photo.router` — перехватывает текстовые сообщения когда активен FSM.

---

## 3. Целевая архитектура (TO-BE) для Этапа A

### 3.1. Единый pipeline: фото → nutrition agent

```
message.photo
  → photo_handler (ОБЛЕГЧЁННЫЙ):
      1. download + base64
      2. caption = message.caption
      3. recognize_food_photo(base64, caption)   ← НОВЫЙ параметр
      4. Формирует vision_payload + сохраняет в nutrition session context
      5. Передаёт в supervisor → nutrition_agent (принудительно)
      6. Agent получает vision_payload + caption в system message
      7. Agent создаёт draft через meal_draft_create tool
      8. Agent отвечает карточкой + спрашивает подтверждение
```

### 3.2. Nutrition Session Context (in-memory + Redis-ready)

Новый модуль `bot/nutrition_context.py` — хранилище сессий питания:

```python
@dataclass
class NutritionSessionContext:
    user_id: int
    # Текущий черновик
    draft: MealDraft | None = None
    # Последний сохранённый meal (для ответов «записал?»)
    last_saved_meal: dict | None = None
    # Время последнего взаимодействия
    last_activity: datetime = field(default_factory=lambda: datetime.now(DEFAULT_TZ))
    # Источник последнего входа
    last_source: str = ""  # "photo" | "text" | "voice"

@dataclass
class MealDraft:
    draft_id: str                    # uuid hex[:8]
    items: list[dict]                # [{name, amount_g, calories, protein_g, fat_g, carbs_g, confidence, source}]
    meal_type: str                   # breakfast | lunch | dinner | snack
    source_type: str                 # photo | text | mixed
    photo_file_id: str | None        # Telegram file_id фото
    vision_result: dict | None       # Сырой результат Vision API
    caption: str | None              # Подпись пользователя
    status: str = "draft"            # draft | awaiting_confirmation | confirmed | saved | discarded
    total: dict = field(default_factory=dict)  # {calories, protein_g, fat_g, carbs_g}
    message_id: int | None = None    # ID сообщения с карточкой (для обновления)
    created_at: datetime = field(default_factory=lambda: datetime.now(DEFAULT_TZ))
    updated_at: datetime = field(default_factory=lambda: datetime.now(DEFAULT_TZ))
```

Хранилище: `dict[int, NutritionSessionContext]` с TTL 30 минут (cleanup по таймеру). В Этапе B можно мигрировать в Redis или БД.

### 3.3. Smart Merge Engine (caption + vision)

Новый модуль `services/nutrition_merge.py`:

```python
async def merge_vision_and_caption(
    vision_items: list[dict],    # Результат Vision API
    caption: str | None,         # Подпись пользователя
    user_text: str | None = None # Дополнительный текст
) -> list[dict]:
    """
    Слияние данных vision и текста пользователя.
    
    Правила приоритета:
    1. Если caption указывает граммовку — она важнее vision
    2. Если caption называет продукт, а vision его не нашёл — добавить
    3. Если vision нашёл продукт, а caption его не упоминает — оставить с пометкой uncertain
    4. Если продукты совпадают по названию — fuzzy merge (fuzz ratio > 70)
    """
```

Реализация через LLM-вызов: передаём vision_items + caption в structured output и просим вернуть merged list. Это проще и надёжнее, чем ручной парсинг.

### 3.4. Обновлённый photo handler (gateway)

`bot/handlers/photo.py` — упрощается до ~60 строк:

1. Скачать фото, получить base64 и `photo.file_id`
2. Вызвать `recognize_food_photo(base64, caption=message.caption)` — обновлённый
3. Слить через `merge_vision_and_caption(vision_items, caption)`
4. Создать `MealDraft` и сохранить в `NutritionSessionContext`
5. Передать в `process_message()` supervisor'а с **специальным маркером** — `[NUTRITION_PHOTO]` prefix в тексте + `vision_payload` в state
6. **Не** показывать карточку самому — пусть agent формирует ответ

Альтернативный вариант (менее инвазивный, рекомендуемый):
- photo handler по-прежнему показывает карточку, но:
  - Учитывает caption при merge
  - Сохраняет draft в NutritionSessionContext
  - Карточка содержит обновлённые кнопки (Quick Actions 2.0)
  - После показа карточки следующие текстовые сообщения пользователя **в контексте этого draft** обрабатываются nutrition agent'ом (через inject контекста)

### 3.5. Инъекция контекста в nutrition agent

При вызове nutrition agent'а через supervisor — добавлять в сообщение контекст из `NutritionSessionContext`:

```python
# В supervisor.py → run_nutrition():
ctx = get_nutrition_context(state["user_id"])
context_block = ""
if ctx and ctx.draft:
    context_block = format_draft_context(ctx.draft)
if ctx and ctx.last_saved_meal:
    context_block += format_last_saved_context(ctx.last_saved_meal)

# Добавляем к HumanMessage:
enriched_text = f"{context_block}\n\nСообщение пользователя: {user_text}"
```

Это позволяет agent'у видеть pending draft и отвечать на «занёс?» / «сыра 30г» / «убери хлебец».

---

## 4. Детальные изменения по файлам

### 4.1. НОВЫЙ: `bot/nutrition_context.py`

**Назначение:** Хранение сессий питания с draft'ами.

Содержит:
- `NutritionSessionContext` — dataclass контекста пользователя
- `MealDraft` — dataclass черновика
- `get_context(user_id) → NutritionSessionContext | None`
- `set_context(user_id, ctx)` — сохранить/обновить контекст
- `clear_context(user_id)` — очистить
- `cleanup_expired()` — удалить просроченные (вызывается по таймеру)
- TTL: 30 минут неактивности

### 4.2. НОВЫЙ: `services/nutrition_merge.py`

**Назначение:** Smart Merge Engine — слияние vision + caption + follow-up.

Содержит:
- `merge_vision_and_caption(vision_items, caption) → merged_items`
- `apply_user_correction(draft_items, user_text) → updated_items` — для follow-up правок
- Оба метода используют LLM (gpt-4o-mini, temperature=0) для понимания свободного текста

Промпт для `merge_vision_and_caption`:
```
Ты получил результат распознавания фото еды (vision) и текстовую подпись пользователя (caption).
Объедини их в один список продуктов.

ПРАВИЛА ПРИОРИТЕТА:
1. Если пользователь указал граммовку — она важнее vision
2. Если пользователь назвал продукт, которого нет в vision — добавь его
3. Если vision нашёл продукт, а пользователь его не упомянул — оставь как есть
4. Для каждого item укажи confidence: "high" если совпадает с текстом, "medium" если только vision, "low" если неуверен

Верни JSON-массив. Каждый элемент:
{name, amount_g, calories, protein_g, fat_g, carbs_g, confidence, source}
source: "caption" | "vision" | "merged"
```

Промпт для `apply_user_correction`:
```
У пользователя есть черновик приёма пищи (items). Он написал сообщение для корректировки.
Определи, что он хочет: изменить граммовку, убрать продукт, добавить продукт, изменить тип приёма.

Текущий черновик: {items_json}
Сообщение пользователя: {user_text}

Верни JSON:
{
  "action": "update_item" | "remove_item" | "add_item" | "change_meal_type" | "confirm" | "discard" | "unknown",
  "updated_items": [...],  // полный обновлённый список (если action != unknown)
  "meal_type": "...",       // если change_meal_type
  "explanation": "..."      // что было понято и изменено
}
```

### 4.3. ИЗМЕНЕНИЕ: `integrations/vision/food_recognizer.py`

**Что меняется:** `recognize_food_photo()` получает параметр `caption`.

```python
async def recognize_food_photo(
    photo_base64: str,
    caption: str | None = None,      # ← НОВЫЙ параметр
) -> dict[str, Any]:
```

Если caption передан — добавляется в user message для Vision API:
```python
user_content = [
    {
        "type": "text",
        "text": f"Проанализируй эту еду. Определи продукты, вес и КБЖУ.\n\n"
                f"Пользователь написал подпись к фото: «{caption}»\n"
                f"ВАЖНО: Если пользователь указал граммовку или название продукта — "
                f"его данные имеют ПРИОРИТЕТ над визуальной оценкой."
        if caption else
        "Проанализируй эту еду. Определи продукты, вес и КБЖУ.",
    },
    {
        "type": "image_url",
        "image_url": {
            "url": f"data:image/jpeg;base64,{photo_base64}",
            "detail": "high",
        },
    },
]
```

Остальная логика (fallback на gpt-4o-mini, JSON-парсинг) не меняется.

### 4.4. ИЗМЕНЕНИЕ: `bot/handlers/photo.py`

**Полная переработка.** Основные изменения:

1. **Читать caption:** `caption = message.caption or ""`
2. **Передать caption в Vision:** `recognize_food_photo(base64, caption=caption)`
3. **Merge:** `merge_vision_and_caption(vision_items, caption)` — если есть caption
4. **Создать MealDraft** и сохранить в `NutritionSessionContext`
5. **Сохранить photo_file_id** в draft: `message.photo[-1].file_id`
6. **Обновлённая карточка** с confidence-маркерами:
   - `🔸 Овсянка — 50г` (уверен)
   - `🔹 Сыр — 30г (??)` (неуверен)
7. **Новая клавиатура** Quick Actions:
   - ✅ Сохранить | ✏️ Исправить текстом | 🗑 Отменить
   - Кнопка «✏️ Исправить текстом» → просто сообщение «Напиши что поправить, например: овсянка 80г, убери сыр»
8. **Удалить FSM** `EditMealStates.waiting_for_grams` — заменяется на естественный парсинг через nutrition agent

**Callback `meal_save`:** при сохранении — записать `last_saved_meal` в `NutritionSessionContext`.

**Callback `meal_edit_start`:** вместо кнопок по каждому продукту — отправить текстовое сообщение:
```
✏️ Напиши что поправить. Примеры:
• овсянка 80г
• убери хлебец
• добавь банан 120г
• сыра не 50, а 30
```
Далее текстовые правки обрабатываются через nutrition agent (который видит draft из контекста).

### 4.5. ИЗМЕНЕНИЕ: `bot/handlers/text.py`

**Что меняется:** Перед передачей в supervisor — проверить, есть ли активный draft.

```python
@router.message(F.text)
async def text_handler(message: Message, user_db: dict | None = None, bot: Bot = None):
    await bot.send_chat_action(message.chat.id, "typing")
    user_id = message.from_user.id
    user_mode = user_db.get("mode", "personal") if user_db else "personal"

    # Проверяем, есть ли активный nutrition draft
    from bot.nutrition_context import get_context
    ctx = get_context(user_id)
    
    # Если есть активный draft и сообщение короткое — вероятно это правка
    if ctx and ctx.draft and ctx.draft.status in ("draft", "awaiting_confirmation"):
        # Принудительно направляем в nutrition agent с контекстом draft
        response = await process_message(
            user_id=user_id,
            user_mode=user_mode,
            text=message.text,
            force_agent="nutrition",  # ← НОВЫЙ параметр
        )
    else:
        response = await process_message(
            user_id=user_id,
            user_mode=user_mode,
            text=message.text,
        )
    
    # Обработать результат: если agent вернул обновлённый draft — обновить карточку
    await _handle_response(message, response, bot, user_id)
```

### 4.6. ИЗМЕНЕНИЕ: `agents/supervisor.py`

**Что меняется:**

1. Функция `process_message()` получает опциональный `force_agent`:
```python
async def process_message(
    user_id: int,
    user_mode: str,
    text: str,
    force_agent: str | None = None,  # ← НОВЫЙ
) -> str:
```

2. Если `force_agent` задан — `classify_intent` пропускается, используется указанный agent.

3. Перед вызовом nutrition agent — обогащение контекста:
```python
async def run_nutrition(state):
    from bot.nutrition_context import get_context, format_context_for_agent
    ctx = get_context(state["user_id"])
    
    # Инжектим контекст draft в сообщение
    enriched_state = state
    if ctx:
        context_prefix = format_context_for_agent(ctx)
        # Модифицируем последнее HumanMessage
        ...
    
    agent = build_nutrition_agent(checkpointer=get_checkpointer(), user_id=state["user_id"])
    return await _run_agent(agent, enriched_state)
```

### 4.7. ИЗМЕНЕНИЕ: `agents/personal/nutrition_agent.py`

**Что меняется:**

1. **Обновлённый системный промпт** — добавляются правила conversational contract:

```python
_SYSTEM_PROMPT = """Ты — персональный нутрициолог и трекер питания.
Отвечай на русском языке, коротко и по делу.

... (существующие секции ЛОГИРОВАНИЕ, ВОДА, ЦЕЛИ, СТАТИСТИКА, EWA) ...

КОНТЕКСТ ЧЕРНОВИКА (PENDING MEAL DRAFT):
- В начале сообщения может быть блок [NUTRITION_CONTEXT]. Это текущий черновик приёма пищи.
- Если черновик есть — пользователь, скорее всего, хочет его отредактировать или подтвердить.
- "занёс?", "сохранил?", "записал?" — проверь контекст и ответь по делу.
- "овсянка 80г", "сыра 30", "убери хлебец" — это правки к draft. Вызови meal_draft_update.
- "да", "ок", "сохрани", "всё верно" — подтверждение. Вызови meal_draft_confirm.
- "нет", "отмена", "не надо" — отмена. Вызови meal_draft_discard.

ПРАВИЛА ОТВЕТОВ:
- После создания или обновления draft — ВСЕГДА покажи что получилось:
  список продуктов с граммовкой + суммарное КБЖУ
- Спрашивай подтверждение: "Сохранить?" / "Что-то поправить?"
- Не показывай ID, JSON, технические ошибки
- Будь живой и человекоподобной: "Записала завтрак: ...", "Ой, сыр убрала..."
- После сохранения — кратко: "✅ Готово! 260 ккал. До цели по белку осталось 48г"
"""
```

2. **Новые tools** (добавляются к существующим):

### 4.8. ИЗМЕНЕНИЕ: `tools/nutrition_tools.py`

**Новые tools:**

```python
@tool
async def meal_draft_create(
    items_json: str,
    meal_type: str = "snack",
    source: str = "text",
) -> str:
    """Создать черновик приёма пищи (НЕ сохраняет в БД).
    Используй когда пользователь описывает еду текстом.
    items_json — JSON-массив продуктов.
    """
    # Создаёт MealDraft в NutritionSessionContext
    # Возвращает форматированную карточку

@tool
async def meal_draft_update(
    correction: str,
) -> str:
    """Обновить текущий черновик на основе текстовой правки пользователя.
    correction — что пользователь хочет изменить, например: "овсянка 80г", "убери сыр".
    """
    # Вызывает apply_user_correction() из nutrition_merge
    # Обновляет MealDraft в NutritionSessionContext
    # Возвращает обновлённую карточку

@tool
async def meal_draft_confirm() -> str:
    """Подтвердить и сохранить текущий черновик в БД.
    Вызывай когда пользователь говорит "да", "сохрани", "всё верно".
    """
    # Берёт draft из NutritionSessionContext
    # Вызывает ns.add_meal() с данными из draft
    # Переносит в last_saved_meal
    # Очищает draft
    # Возвращает подтверждение + краткую аналитику остатка на день

@tool
async def meal_draft_discard() -> str:
    """Отменить текущий черновик. Пользователь передумал."""
    # Очищает draft из NutritionSessionContext

@tool
async def meal_check_pending() -> str:
    """Проверить статус: есть ли несохранённый черновик или последний сохранённый meal.
    Вызывай на вопросы типа "занёс?", "сохранил?", "записал?".
    """
    # Читает NutritionSessionContext
    # Отвечает: "Да, записала: ..." или "Есть несохранённый черновик: ..."
```

**Важно:** tools получают `user_id` через замыкание (как сейчас). Context берут из `bot.nutrition_context`.

### 4.9. ИЗМЕНЕНИЕ: `bot/states.py`

**Удалить** `EditMealStates` — FSM-редактирование граммовок больше не нужно.
Весь `EditMealStates.waiting_for_grams` flow заменяется на естественный парсинг через agent.

---

## 5. Формат контекста для agent

Блок, который инжектится перед HumanMessage пользователя:

```
[NUTRITION_CONTEXT]
Статус: есть несохранённый черновик

Черновик приёма пищи (draft_id: abc12345):
Тип: 🌅 Завтрак
Статус: awaiting_confirmation
Источник: фото + подпись

Продукты:
1. Овсянка — 50г (150 ккал) [источник: caption, уверенность: high]
2. Топинг шоколадный — 15г (52 ккал) [источник: vision, уверенность: medium]  
3. Хлебец — 10г (35 ккал) [источник: caption, уверенность: high]
4. Сыр — 30г (105 ккал) [источник: merged, уверенность: medium]

Итого: 342 ккал · Б 15г · Ж 12г · У 42г

Подпись пользователя: "50г овсянки, ложка топинга, 1 хлебец и 3 кусочка сыра"
[/NUTRITION_CONTEXT]
```

Если draft нет, но есть `last_saved_meal`:
```
[NUTRITION_CONTEXT]
Статус: нет активного черновика
Последний сохранённый приём: 🌅 Завтрак в 09:15
  Овсянка 50г, Топинг 15г, Хлебец 10г, Сыр 30г — 342 ккал
[/NUTRITION_CONTEXT]
```

---

## 6. Обновлённые inline-кнопки (Quick Actions)

### 6.1. Карточка draft (после распознавания фото)

Ряд 1: `✅ Сохранить` | `✏️ Поправить`
Ряд 2: `🗑 Отменить`

При нажатии «✏️ Поправить» — бот отправляет подсказку:
```
Напиши что изменить, например:
• овсянка 80г
• убери хлебец  
• добавь банан
• это был перекус
```

### 6.2. Карточка после сохранения

Ряд 1: `💧 +250мл воды` | `📊 Остаток на день`

---

## 7. Сценарии работы (end-to-end)

### 7.1. Фото + подпись → правка → сохранение

```
👤 [Отправляет фото + подпись "50г овсянки, ложка топинга, 1 хлебец и 3 кусочка сыра"]

🤖 🌅 Завтрак · 09:15
   🔸 Овсянка — 50г (150 ккал)
   🔸 Топинг шоколадный — 15г (52 ккал)
   🔸 Хлебец — 10г (35 ккал)
   🔹 Сыр — 30г (??) (105 ккал)
   ─────────────────
   📊 Итого: 342 ккал · Б 15 · Ж 12 · У 42
   
   По сыру не совсем уверена в порции — оставляем 30г?
   
   [✅ Сохранить] [✏️ Поправить] [🗑 Отменить]

👤 "сыра 20г"

🤖 Обновила! Сыр — теперь 20г (70 ккал)
   📊 Итого: 307 ккал · Б 14 · Ж 10 · У 42
   Сохранить?
   
   [✅ Сохранить] [🗑 Отменить]

👤 "да"

🤖 ✅ Записала завтрак — 307 ккал
   До цели по белку осталось 106г. Хорошего дня!
```

### 7.2. Текстовый ввод → draft → подтверждение

```
👤 "съел 200г курицы и рис"

🤖 Записываю обед:
   🔸 Куриная грудка — 200г (220 ккал)
   🔸 Рис белый — 150г (195 ккал)
   ─────────────────
   📊 Итого: 415 ккал · Б 50 · Ж 3 · У 43
   
   Сохранить?

👤 "да, и ещё салат"

🤖 Добавила салат! Обед:
   🔸 Куриная грудка — 200г (220 ккал)
   🔸 Рис белый — 150г (195 ккал)
   🔸 Салат овощной — 150г (45 ккал)
   ─────────────────
   📊 Итого: 460 ккал · Б 52 · Ж 4 · У 50
   
   Теперь сохранить?

👤 "да"

🤖 ✅ Обед записан — 460 ккал
```

### 7.3. Проверка статуса

```
👤 "записала?"

🤖 Да, последний приём записан:
   🍽 Обед в 13:20 — курица, рис, салат — 460 ккал
```

```
👤 "сохранила?"   (когда draft ещё не подтверждён)

🤖 Пока нет — жду твоего подтверждения:
   🌅 Завтрак: овсянка, топинг, хлебец, сыр — 307 ккал
   Сохранить?
```

---

## 8. Порядок реализации (подзадачи)

### Шаг 1: `bot/nutrition_context.py` — хранилище draft-сессий
- Dataclass'ы `MealDraft`, `NutritionSessionContext`
- CRUD: get/set/clear/cleanup
- Функция `format_context_for_agent(ctx) → str`

### Шаг 2: `services/nutrition_merge.py` — Smart Merge Engine
- `merge_vision_and_caption()` — LLM-слияние vision + caption
- `apply_user_correction()` — LLM-парсинг корректировок
- Тесты на типовых сценариях

### Шаг 3: `integrations/vision/food_recognizer.py` — caption-aware Vision
- Добавить параметр `caption` в `recognize_food_photo()`
- Включить caption в user message для Vision API

### Шаг 4: `tools/nutrition_tools.py` — новые draft tools
- `meal_draft_create`
- `meal_draft_update` (использует `apply_user_correction`)
- `meal_draft_confirm`
- `meal_draft_discard`
- `meal_check_pending`
- Интеграция с `NutritionSessionContext`

### Шаг 5: `agents/personal/nutrition_agent.py` — обновлённый промпт
- Добавить правила conversational contract
- Подключить новые tools

### Шаг 6: `agents/supervisor.py` — инъекция контекста
- Параметр `force_agent` в `process_message()`
- Обогащение HumanMessage контекстом draft

### Шаг 7: `bot/handlers/photo.py` — новый photo handler
- Чтение caption
- Вызов merge engine
- Создание MealDraft
- Обновлённая карточка + кнопки
- Удаление FSM-логики

### Шаг 8: `bot/handlers/text.py` — проброс контекста
- Проверка активного draft
- `force_agent="nutrition"` если draft активен

### Шаг 9: `bot/states.py` — удаление EditMealStates
- Убрать `EditMealStates` (FSM-редактирование заменено на agent)

### Шаг 10: Тестирование и отладка
- E2E тест: фото + caption → правка → сохранение
- E2E тест: текст → draft → подтверждение
- E2E тест: «занёс?» → корректный ответ
- Рестарт бота → проверка что draft теряется (ожидаемо для in-memory; БД-хранение — Этап B)

---

## 9. Зависимости и ограничения

### 9.1. Без изменений БД
Этап A **не требует миграций БД**. Все draft'ы хранятся in-memory. Поле `photo_file_id` на модели `Meal` уже существует.

### 9.2. Обратная совместимость
- Существующий `meal_log` tool продолжает работать (для прямого логирования текстом без draft)
- Inline-кнопки старого формата на уже отправленных сообщениях перестанут работать (это нормально — `_pending_meals` не переживают рестарт и сейчас)

### 9.3. Риски
- **LLM-зависимость merge engine:** Каждая правка → вызов LLM. Mitigation: кэш типовых паттернов, быстрая модель (gpt-4o-mini)
- **In-memory draft:** теряется при рестарте. Mitigation: приемлемо для Этапа A; Redis — Этап B
- **Race condition:** два быстрых сообщения подряд. Mitigation: asyncio Lock per user_id

---

## 10. Метрики успешности

1. **Фото + caption → один meal** (а не 3 отдельных)
2. **Правка «сыра 30г» → обновляет draft** (а не создаёт новый meal)
3. **«Занёс?» → осмысленный ответ** (а не «уточните что именно»)
4. **Время от фото до сохранения** < 3 сообщений в типовом случае
5. **Нет FSM-шагов** — весь ввод естественным языком
