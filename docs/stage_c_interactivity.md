# Этап C — Интерактивность и Retention

## 1. Контекст
Этап A (Draft Engine) реализован — бот создаёт черновики, принимает правки текстом, сливает фото+caption.
Этап C добавляет **пользовательскую ценность поверх инфраструктуры**: бот становится проактивным помощником, а не пассивным трекером.

## 2. Что уже есть (повторно не реализовывать)
- `services/nutrition_insights.py` — `generate_daily_tips()`, `generate_weekly_tips()`, `generate_evening_summary()` (базовые правила, НЕ LLM)
- `db/nutrition_storage.py` — `get_recent_meals()`, `get_frequent_foods()`, `create_template_from_meal()`, `apply_template()`, `find_template_by_name()`, `get_nutrition_summary()`
- `tools/nutrition_tools.py` — `meal_from_template`, `nutrition_stats` (13 tools всего)
- `api/routers/nutrition.py` — шаблоны CRUD, meals CRUD, goals, water
- `miniapp/features/nutrition/TemplatesSheet.tsx` — UI шаблонов уже есть

## 3. Новые компоненты (6 штук)

### 3.1. Tool: `nutrition_remaining_today`
**Файл:** `tools/nutrition_tools.py` (добавить в `make_nutrition_tools`)
**Что делает:** Показывает сколько КБЖУ и воды осталось до цели на сегодня.
**Вызывается:** Агентом при фразах «сколько осталось», «что ещё можно съесть», «остаток на день».
**Реализация:**
```
async def nutrition_remaining_today() -> str:
    summary = await ns.get_nutrition_summary(user_id, date.today())
    goals = summary["goals"]
    totals = summary["totals"]
    water = summary["water_ml"]
    # Вычислить разницу по каждому макросу
    # Вернуть: "🎯 Осталось: 847 ккал · Б 62г · Ж 28г · У 95г · 💧 1200 мл"
```

### 3.2. Tool: `meal_clone_recent`
**Файл:** `tools/nutrition_tools.py`
**Что делает:** Находит похожий приём пищи в истории и создаёт draft из него.
**Вызывается:** При фразах «как вчера», «повтори завтрак», «тот же обед», «обычный кофе».
**Параметры:** `query: str` — описание («вчерашний завтрак», «обед как обычно»).
**Реализация:**
```
async def meal_clone_recent(query: str) -> str:
    # 1. Определить meal_type и дату из query (вчера/позавчера/последний)
    # 2. ns.get_recent_meals(user_id, meal_type, limit=5)
    # 3. Выбрать самый подходящий
    # 4. create_draft(user_id, items=meal["items"], meal_type, source="history")
    # 5. Вернуть карточку draft
```
**Зависимости:** `get_recent_meals()` уже есть в storage (строка 631).

### 3.3. Tool: `meal_template_save`
**Файл:** `tools/nutrition_tools.py`
**Что делает:** Сохраняет последний приём пищи или текущий draft как шаблон.
**Вызывается:** При «сохрани как шаблон», «запомни этот завтрак», «сохрани как мой обычный обед».
**Параметры:** `name: str` — название шаблона.
**Реализация:**
```
async def meal_template_save(name: str) -> str:
    # 1. Проверить: есть draft? → сохранить items из draft как шаблон
    # 2. Нет draft? → взять последний сохранённый meal пользователя
    # 3. ns.create_template(user_id, name, meal_type, items)
    # 4. Вернуть: "💾 Шаблон «Мой завтрак» сохранён (3 продукта)"
```
**Зависимости:** `create_template()` уже есть в storage (строка 650).

### 3.4. Сервис: Follow-up Suggestions после сохранения
**Файл:** `services/nutrition_followup.py` (новый)
**Что делает:** После `meal_draft_confirm` генерирует 1-2 проактивные подсказки.
**Логика (правила, НЕ LLM — быстро и дёшево):**
```
async def generate_followup(user_id: int) -> str | None:
    summary = await ns.get_nutrition_summary(user_id, date.today())
    goals = summary["goals"]
    totals = summary["totals"]
    water = summary["water_ml"]
    tips = []

    # Правило 1: Остаток белка
    if goals and goals["protein_g"]:
        prot_left = goals["protein_g"] - totals["protein_g"]
        if 20 < prot_left < 80:
            tips.append(f"🥩 До цели по белку осталось {prot_left:.0f}г")

    # Правило 2: Вода отстаёт
    if goals and goals["water_ml"]:
        water_pct = water / goals["water_ml"]
        if water_pct < 0.4:
            tips.append("💧 Воды сегодня мало — выпей стаканчик?")

    # Правило 3: Калории > 90% — предупреждение
    if goals and goals["calories"]:
        cal_pct = totals["calories"] / goals["calories"]
        if cal_pct > 0.9:
            tips.append("⚠️ Калории почти закрыты — на остаток дня лёгкий вариант")

    # Правило 4: Первый приём за день — поздний старт
    meals_count = len(summary.get("meals", []))
    if meals_count == 1:
        from datetime import datetime
        from config import DEFAULT_TZ
        hour = datetime.now(DEFAULT_TZ).hour
        if hour >= 14:
            tips.append("📝 Это первый приём за сегодня — не пропускай приёмы пищи")

    # Правило 5: Предложить сохранить шаблон (если > 3 items)
    # Проверяем последний meal — если items >= 3 и нет такого шаблона
    # tips.append("💾 Хочешь сохранить это как шаблон?")

    return "\n".join(tips[:2]) if tips else None
```
**Интеграция:** Вызывать в `meal_draft_confirm` tool после успешного сохранения. Добавить результат к ответу агента.

### 3.5. Сервис: Daily Nutrition Score
**Файл:** `services/nutrition_score.py` (новый)
**Что делает:** Считает дневной score 0–100 по нескольким критериям.
**Формула:**
```
async def calculate_daily_score(user_id: int, target_date: date = None) -> dict:
    # Компоненты score (каждый 0-100, веса):
    # 1. Калории (25%) — попадание в ±10% от цели = 100, отклонение пропорционально
    # 2. Белок (25%) — >= 90% цели = 100
    # 3. Баланс БЖУ (15%) — жиры и углеводы в пределах ±20% от цели
    # 4. Вода (15%) — >= 80% цели = 100
    # 5. Регулярность (10%) — >= 3 приёмов пищи = 100, 2 = 70, 1 = 30
    # 6. Тайминг (10%) — есть завтрак до 11, обед до 15, ужин до 21

    return {
        "total": 82,
        "breakdown": {
            "calories": {"score": 90, "detail": "1850 / 2000 ккал"},
            "protein": {"score": 75, "detail": "98 / 130г"},
            "balance": {"score": 85, "detail": "БЖУ в балансе"},
            "water": {"score": 60, "detail": "1200 / 2000 мл"},
            "regularity": {"score": 100, "detail": "3 приёма пищи"},
            "timing": {"score": 80, "detail": "завтрак вовремя"},
        },
        "emoji": "🟢",  # 🟢 80+ / 🟡 60-79 / 🔴 <60
    }
```
**Интеграция:**
- Новый tool `nutrition_daily_score` — агент вызывает при «оценка за день», «как я сегодня», «мой score»
- API endpoint `GET /api/nutrition/score?date=2026-03-13` — для MiniApp

### 3.6. Сервис: Weekly AI Summary
**Файл:** `services/nutrition_weekly_summary.py` (новый)
**Что делает:** Раз в неделю (или по запросу) генерирует **LLM-powered** краткий обзор.
**Реализация:**
```
async def generate_weekly_summary(user_id: int) -> str:
    # 1. Собрать данные за 7 дней: daily scores, totals, meals count
    # 2. Отправить в LLM (gpt-4o-mini) с промптом:
    #    "Ты нутрициолог. Вот данные за неделю. Дай 3-5 коротких выводов и 2-3 рекомендации.
    #     Формат: позитивный, мотивирующий, конкретный."
    # 3. Вернуть текст
```
**Интеграция:**
- Новый tool `nutrition_weekly_summary` — при «итоги за неделю», «как я питался на неделе»
- (Опционально) cron-задача по воскресеньям → отправка через Telegram

## 4. Изменения в существующих файлах

### 4.1. `tools/nutrition_tools.py`
Добавить 4 новых tool:
- `nutrition_remaining_today` — остаток КБЖУ на день
- `meal_clone_recent` — повтор из истории
- `meal_template_save` — сохранение шаблона из чата
- `nutrition_daily_score` — дневной score

### 4.2. `tools/nutrition_tools.py` → `meal_draft_confirm`
После сохранения в БД — вызвать `generate_followup()` и добавить подсказки к ответу.

### 4.3. `agents/personal/nutrition_agent.py` → промпт
Добавить в секцию инструкций:
```
FOLLOW-UP И ПРОАКТИВНОСТЬ:
- После сохранения приёма пищи — покажи follow-up подсказку (остаток белка, вода, score)
- «как вчера», «повтори завтрак» → meal_clone_recent
- «сколько осталось» → nutrition_remaining_today
- «оценка за день» → nutrition_daily_score
- «итоги за неделю» → nutrition_weekly_summary
- «сохрани как шаблон» → meal_template_save

ШАБЛОНЫ:
- Если пользователь > 3 раз ел похожее — предложи сохранить шаблон
- «мой обычный завтрак» → meal_from_template или meal_clone_recent
```

### 4.4. `api/routers/nutrition.py`
Добавить эндпоинты:
- `GET /api/nutrition/score` — дневной score (для MiniApp)
- `GET /api/nutrition/remaining` — остаток на день (для MiniApp)
- `GET /api/nutrition/weekly-summary` — недельный отчёт

## 5. НЕ трогаем (за рамками Этапа C)
- Схему БД — новых таблиц и миграций НЕТ
- MiniApp компоненты — UI score/summary добавим позже
- Cron / scheduled messages — отложим
- `.env` файл — не трогаем

## 6. Порядок реализации
1. `services/nutrition_score.py` — Daily Score (независимый)
2. `services/nutrition_followup.py` — Follow-up Suggestions (независимый)
3. `services/nutrition_weekly_summary.py` — Weekly Summary (LLM)
4. `tools/nutrition_tools.py` — 4 новых tool + follow-up в confirm
5. `agents/personal/nutrition_agent.py` — обновление промпта
6. `api/routers/nutrition.py` — 3 новых эндпоинта
7. Проверка компиляции и перезапуск через `start_api.sh`

## 7. Критерии проверки
1. «сколько осталось» → бот отвечает с конкретными числами остатка КБЖУ
2. «как вчера на завтрак» → бот создаёт draft из вчерашнего завтрака
3. «сохрани как шаблон Мой завтрак» → шаблон появляется в списке
4. После подтверждения draft → бот добавляет 1-2 подсказки (белок/вода)
5. «оценка за день» → бот показывает score с разбивкой
6. «итоги за неделю» → бот генерирует краткий LLM-обзор
