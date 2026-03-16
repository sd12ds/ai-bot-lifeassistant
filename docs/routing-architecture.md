# Архитектура маршрутизации сообщений (Routing Architecture)

> **Версия:** v3 (март 2026)  
> **Статус:** Актуальная архитектура после рефакторинга

---

## Концепция и главный принцип

Бот обрабатывает сообщения из нескольких источников: текст, голос, фото, кнопки FSM.  
Задача routing-системы — определить, какой агент должен обработать сообщение, и гарантировать корректную передачу даже при многошаговых диалогах (черновики, подтверждения).

**Главный принцип:**
> **Handlers — тупые I/O каналы. Вся логика маршрутизации — только в `agents/supervisor.py`.**

Handler делает ровно две вещи:
1. Получает входные данные (text / voice→STT / photo→vision)
2. Вызывает `process_message(user_id, user_mode, text)` и возвращает ответ

Никакой логики домена, `draft`, `force_agent` в handler'е не должно быть.  
Supervisor **сам гарантирует** корректный роутинг при любых входных данных.

---

## Схема компонентов

```
Telegram
  │
  ├── text.py ──────────────┐
  ├── voice.py (STT) ───────┤
  ├── photo.py (*) ─────────┤──→ process_message(user_id, mode, text)
  ├── coaching_handler.py(**) │           │
  └── будущие handlers ────┘           │
                                        ▼
                              agents/supervisor.py
                                        │
                              ┌─────────┴──────────┐
                              │   classify_intent   │
                              │                     │
                              │  L0a: Draft Guard   │
                              │  L0b: Confirm Guard │
                              │  L1: force_agent    │
                              │  L2: rule-based     │
                              │  L3: sticky domain  │
                              │  L4: LLM classifier │
                              └─────────┬───────────┘
                                        │
                     ┌──────────────────┼──────────────────┐
                     ▼                  ▼                  ▼
              nutrition_agent    reminder_agent    coaching_agent  ...
```

> `(*)` — `photo.py` создаёт draft напрямую через `create_draft()`, supervisor не вызывает  
> `(**)` — `coaching_handler.py` использует FSM aiogram, supervisor не вызывает

---

## Пирамида защиты (3 независимых слоя)

Каждый слой независим — если один не сработал, следующий подхватывает.

### Слой 1 — `process_message` (ядро, 100% надёжность)

**Файл:** `agents/supervisor.py`, функция `process_message`

Единственная точка входа для ВСЕХ handler'ов. При вызове **до передачи в граф** проверяет:

```python
if not force_agent:
    ctx = get_context(user_id)
    if ctx and ctx.draft:
        force_agent = ctx.active_domain or "nutrition"
        # → сообщение принудительно идёт к агенту, создавшему черновик
```

**Гарантия:** любой handler — в том числе написанный в будущем — автоматически корректен.  
Разработчик нового handler'а не обязан знать о существовании drafts или session context.

---

### Слой 2 — `classify_intent` уровень 0 (defence-in-depth)

**Файл:** `agents/supervisor.py`, функция `classify_intent`

Два guard'а **в самом начале** функции, до `force_agent`, до rule-based, до LLM.

#### 0a. Draft Guard

```python
ctx = get_context(user_id)
if ctx and ctx.draft:
    agent = ctx.active_domain or "nutrition"
    return {**state, "agent_type": agent}
    # → логгируется как "(L0a draft guard)"
```

Срабатывает даже если Слой 1 не сработал (например, вызов через нестандартный путь).

#### 0b. Confirmation Guard

```python
_CONFIRM_PATTERN = re.compile(
    r'^(да|нет|ок|ладно|хорошо|подтверди|подтверждаю|отмени|отменить|cancel|yes|no)[\.\!\?\s]*$',
    re.IGNORECASE
)

if ctx and ctx.pending_confirmation and _CONFIRM_PATTERN.match(user_text.strip()):
    agent = ctx.active_domain or "nutrition"
    return {**state, "agent_type": agent}
    # → логгируется как "(L0b confirmation guard)"
```

Закрывает класс багов: **«однословный ответ маршрутируется не туда»**.  
Пользователь говорит/пишет «Да.» → всегда попадает к агенту, который ожидает подтверждения.

---

### Слой 3 — Существующий pipeline классификации (уровни 1–4)

Обычный поток для сообщений без активного черновика:

| Уровень | Метод | Описание | TTL |
|---------|-------|----------|-----|
| L1 | `force_agent` | Явное указание из handler'а | — |
| L2 | rule-based | Ключевые слова без LLM | мгновенно |
| L3 | sticky domain | Продолжение предыдущей темы | 8 мин |
| L4 | LLM | `gpt-4.1-nano`, анализ контекста | — |

---

## SessionContext — структура и жизненный цикл

**Файл:** `bot/core/session_context.py`

```python
@dataclass
class SessionContext:
    user_id: int
    active_domain: str = ""           # "nutrition" | "fitness" | "tasks" | ...
    draft: BaseDraft | None = None    # Текущий черновик (любого домена)
    pending_confirmation: bool = False # True пока ждём "да/нет"
    domain_sticky_until: datetime | None = None  # TTL sticky-домена
    last_activity: datetime = ...
    last_source: str = ""             # "photo" | "text" | "voice"
    meta: dict = ...                  # Доп. данные (свободный слот)
```

### Жизненный цикл при работе с черновиком

```
1. Агент вызывает set_draft(user_id, draft)
      → ctx.draft = draft
      → ctx.active_domain = draft.domain
      → ctx.pending_confirmation = True

2. Пользователь отвечает "Да." (текст или голос)
      → Слой 1: force_agent = draft.domain  (draft ещё активен)
      → Агент получает подтверждение, сохраняет данные
      → Вызывает clear_draft(user_id)

3. clear_draft(user_id)
      → ctx.draft = None
      → ctx.pending_confirmation = False
      → ctx.activate_sticky(minutes=10)  ← домен остаётся "липким" 10 мин
         (пользователь может уточнить "изменить порцию" без явного упоминания раздела)
```

### TTL параметры

| Где | Значение | Обоснование |
|-----|----------|-------------|
| После rule-based/LLM классификации | 8 мин | Пользователь может думать 3-4 мин |
| После `clear_draft` | 10 мин | Уточнения к сохранённому приёму пищи |
| Session TTL (неактивность) | 30 мин | Полная очистка контекста |

---

## Файловая структура routing-системы

```
agents/
  supervisor.py          ← Главный файл: process_message + classify_intent + граф
  
bot/core/
  session_context.py     ← SessionContext, set_draft, clear_draft, get_context
  intent_classifier.py   ← Rule-based: ключевые слова по доменам

bot/handlers/
  text.py                ← Текстовые сообщения → process_message(...)
  voice.py               ← Голос → STT → process_message(...)
  photo.py               ← Фото → vision → create_draft() напрямую
  coaching_handler.py    ← FSM aiogram, supervisor не использует

agents/personal/
  nutrition_agent.py     ← Вызывает set_draft / clear_draft
  reminder_agent.py
  fitness_agent.py
  coaching_agent.py
  assistant_agent.py
  calendar_agent.py
```

---

## Чеклист: добавление нового раздела (агента)

При добавлении домена `X` (например, "finance", "sleep", "medical"):

### 1. Создать агента

```python
# agents/personal/X_agent.py
def build_X_agent(checkpointer, user_id: int):
    """Агент для работы с X."""
    # ...
    return builder.compile(checkpointer=checkpointer)
```

Стандарт: `build_X_agent(checkpointer, user_id)` — именно такая сигнатура.

### 2. Добавить ключевые слова в rule-based

```python
# bot/core/intent_classifier.py

_X_STRONG = {
    "ключевое слово1",  # однозначный маркер домена
    "ключевое слово2",
}

_X_NORMAL = {
    "обычное слово",    # нужно >= 2 совпадения
}

_X_ANTI = {
    "напомни",          # слова, которые исключают этот домен
}
```

Добавить в `classify_by_rules` по образцу существующих доменов.

### 3. Обновить supervisor.py в двух местах

**3а. Добавить описание в `_CLASSIFY_PROMPT`:**

```python
_CLASSIFY_PROMPT = """...
X — краткое описание: что делает агент, примеры фраз пользователя
..."""
```

**3б. Добавить `AgentType` в Literal:**

```python
AgentType = Literal["calendar", "reminder", "nutrition", "fitness", 
                    "crm", "team", "coaching", "assistant", "X"]  # ← добавить
```

**3в. Добавить `run_X` узел в `build_supervisor`:**

```python
async def run_X(state):
    from agents.personal.X_agent import build_X_agent
    agent = build_X_agent(checkpointer=get_checkpointer(), user_id=state["user_id"])
    return await _run_agent(agent, state)

builder.add_node("X", run_X)

# В add_conditional_edges добавить:
"X": "X",

# В финальный цикл добавить:
for node in [..., "X"]:
    builder.add_edge(node, END)
```

### 4. Если агент работает с черновиками

```python
# Внутри агента, когда нужно запросить подтверждение:
from bot.core.session_context import set_draft, clear_draft
from bot.core.base_draft import BaseDraft

draft = MyDraft(domain="X", ...)  # наследник BaseDraft
set_draft(user_id, draft)
# → теперь pending_confirmation = True, active_domain = "X"
# → все следующие сообщения автоматически пойдут к агенту X

# После подтверждения / отмены:
clear_draft(user_id)
```

### Что НЕ нужно делать

- ❌ Редактировать `text.py`, `voice.py`, `photo.py` — там нет routing-логики
- ❌ Добавлять `force_agent` в какой-либо handler
- ❌ Добавлять `get_context` в handler для проверки домена
- ❌ Напрямую устанавливать `active_domain` в handler'е

---

## Тестирование routing

### Обязательные тест-кейсы при добавлении нового агента

**1. Подтверждение голосом при активном черновике**
```
1. Отправить сообщение о еде → должен создаться draft (nutrition)
2. Отправить голосовое "Да." → должно идти в nutrition, не в другой агент
```

**2. Подтверждение текстом при активном черновике**
```
1. Создать draft любого агента
2. Написать текстом "Да" → должно идти к агенту черновика
```

**3. Смена домена при активном sticky**
```
1. Отправить запрос в nutrition → sticky = nutrition (8 мин)
2. Написать "напомни мне позвонить завтра в 9" → должно идти в reminder
   (rule-based перебивает sticky)
```

**4. Продолжение диалога**
```
1. Отправить запрос в nutrition
2. Через 2 мин написать "поменяй сыр на творог" → должно идти в nutrition
   (sticky domain активен)
```

**5. Новый агент X не ломает существующие**
```
1. Голосовое о еде → nutrition ✓
2. Текст "напомни" → reminder ✓
3. Текст из домена X → X ✓
4. "Да." при черновике nutrition → nutrition ✓ (не X)
```

---

## Известные ограничения

### In-memory сессии

`SessionContext` хранится в оперативной памяти (`dict[int, SessionContext]`).  
При **рестарте бота** все активные черновики и sticky-домены теряются.  
Пользователь, у которого был активный черновик, просто потеряет его — это приемлемо.

**Влияние:** при рестарте нет неправильного роутинга — контекст просто пустой, LLM определит домен заново.

**Будущее решение:** мигрировать `SessionContext` в Redis с TTL.

### История агентов

Каждый агент имеет свой тред checkpoint `{user_id}_{agent_type}`.  
При неправильном роутинге (до v3) в тред агента могли попасть нерелевантные сообщения.  
С новыми guards (v3) это больше не происходит.  
Старые "мусорные" сообщения в тредах не критичны — агент просто игнорирует их как контекст.

### Масштабирование

При нескольких воркерах in-memory `_last_agent_per_user` и `SessionContext` не синхронизированы между процессами. Решение: Redis или sticky-sessions на уровне балансировщика.

---

## История изменений

| Версия | Дата | Изменения |
|--------|------|-----------|
| v1 | 2025 | Базовый supervisor: rule-based + LLM |
| v2 | 2026-01 | Sticky domain (3 мин), force_agent в text.py |
| v2.1 | 2026-02 | Coaching agent добавлен в граф |
| v2.2 | 2026-03 | TTL sticky domain = 3 мин, fix: rule-based обновляет sticky |
| v3 | 2026-03 | **Draft Auto-Force в process_message. L0a/L0b guards. TTL 8/10 мин. Handlers упрощены.** |
