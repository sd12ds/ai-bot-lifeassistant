# Этап B+D: Reusable Chat-Core — универсальное conversational ядро

## 1. Цель
Вынести nutrition-специфичные паттерны (session context, draft lifecycle, action resolver, followup engine) в **универсальный слой** `bot/core/`, пригодный для повторного использования в Fitness, Tasks, Coaching и других модулях.

Параллельно — реализовать **Chat Action Resolver**, которого не хватало в Этапе B.

## 2. Текущее состояние

### Что уже работает (nutrition-специфично):
- `bot/nutrition_context.py` — in-memory хранилище MealDraft + NutritionSessionContext с TTL 30 мин
- `services/nutrition_followup.py` — rule-based подсказки после сохранения приёма
- `bot/handlers/text.py` — проверяет `ctx.draft` → `force_agent="nutrition"`
- `agents/supervisor.py` — принимает `force_agent`, пропускает классификацию
- Draft lifecycle в tools: create → update → confirm → discard

### Чего нет:
- **Chat Action Resolver** — слой «это новая запись или правка?» (логика зашита в промпте)
- **Общий Session Context Manager** — `nutrition_context.py` привязан к nutrition
- **Общий Draft** — `MealDraft` содержит nutrition-поля (meal_type, vision_result)
- **Общий Followup Engine** — `nutrition_followup.py` знает только про КБЖУ

## 3. Архитектура нового слоя `bot/core/`

### 3.1. `bot/core/base_draft.py` — Абстрактный Draft
```
@dataclass
class BaseDraft:
    draft_id: str                   # uuid hex[:8]
    domain: str                     # "nutrition" | "fitness" | "tasks"
    items: list[dict]               # Универсальный список элементов
    status: str                     # draft → awaiting_confirmation → confirmed → saved → discarded
    source_type: str                # photo | text | voice | mixed
    meta: dict                      # Домен-специфичные данные (meal_type, workout_type, etc.)
    created_at: datetime
    updated_at: datetime
    version: int = 1

    def recalc(self) -> None:
        """Переопределяется в доменных наследниках."""
        pass
```

Для Nutrition наследуется `MealDraft(BaseDraft)` с полями `meal_type`, `photo_file_id`, `vision_result`, `total`.
Для Fitness — `WorkoutDraft(BaseDraft)` с полями `workout_type`, `exercises`, `duration`.
Для Tasks — `TaskDraft(BaseDraft)` с полями `due_date`, `priority`, `tags`.

### 3.2. `bot/core/session_context.py` — Универсальный Session Context Manager
```
@dataclass
class SessionContext:
    user_id: int
    active_domain: str              # "nutrition" | "fitness" | "tasks" | ""
    draft: BaseDraft | None         # Текущий черновик (любого домена)
    last_saved_entity: dict | None  # Последняя сохранённая сущность
    last_activity: datetime
    last_source: str                # "photo" | "text" | "voice"
    pending_confirmation: bool      # Ждём подтверждения?
    meta: dict                      # Доп. данные домена
```

Функции:
- `get_context(user_id)` → `SessionContext | None`
- `get_or_create_context(user_id, domain)` → `SessionContext`
- `set_draft(user_id, draft: BaseDraft)` → None
- `clear_draft(user_id)` → None
- `get_active_domain(user_id)` → `str`
- `cleanup_expired()` — TTL-очистка

Хранилище: in-memory dict (как сейчас). В будущем — Redis.

### 3.3. `bot/core/action_resolver.py` — Chat Action Resolver
Задача: определить **что хочет пользователь** относительно текущего контекста.

```
class ActionType(Enum):
    NEW_ENTITY = "new"              # Создать новую сущность
    EDIT_DRAFT = "edit"             # Правка текущего черновика
    CONFIRM = "confirm"             # Подтверждение
    DISCARD = "discard"             # Отмена
    STATUS_CHECK = "status"         # «записал?», «сохранил?»
    QUERY = "query"                 # Вопрос/статистика (не action)
    UNKNOWN = "unknown"             # Не определено — пусть агент решает

@dataclass
class ResolvedAction:
    action: ActionType
    confidence: float               # 0.0 - 1.0
    domain: str                     # "nutrition" | "fitness" | ...
    details: dict                   # Доп. инфо (например, какой item правится)
```

Логика:
1. Если есть активный draft + короткое сообщение (< 50 символов) → вероятно `EDIT_DRAFT`
2. Паттерны подтверждения: «да», «ок», «сохрани», «верно», «записал?» → `CONFIRM` / `STATUS_CHECK`
3. Паттерны отмены: «нет», «отмена», «не надо», «удали» → `DISCARD`
4. Если нет draft + описание еды/тренировки → `NEW_ENTITY`
5. Если вопрос (начинается с «сколько», «что», «покажи», «статистика») → `QUERY`

Реализация: **rule-based** (regex + эвристики), без LLM. Быстро и предсказуемо.

### 3.4. `bot/core/followup_engine.py` — Универсальный Followup Engine
Интерфейс:
```
class FollowupProvider(Protocol):
    async def generate(self, user_id: int, saved_entity: dict) -> list[str]:
        """Возвращает 0-2 подсказки после сохранения."""
        ...
```

Регистрация доменных провайдеров:
```
register_followup_provider("nutrition", NutritionFollowupProvider())
register_followup_provider("fitness", FitnessFollowupProvider())
```

`NutritionFollowupProvider` — обёртка над текущим `services/nutrition_followup.py`.

### 3.5. `bot/core/domain_adapter.py` — Интерфейс доменного адаптера
```
class DomainAdapter(Protocol):
    domain: str                         # "nutrition" | "fitness" | ...
    
    def create_draft(self, user_id, items, **kwargs) -> BaseDraft: ...
    def format_draft_card(self, draft: BaseDraft) -> str: ...
    def format_context_for_agent(self, ctx: SessionContext) -> str: ...
    async def save_draft(self, user_id, draft: BaseDraft) -> dict: ...
    async def generate_followup(self, user_id) -> list[str]: ...
```

Для Nutrition: `NutritionAdapter` — обёртка над текущей логикой из `nutrition_context.py` + `nutrition_tools.py`.

## 4. Интеграция с существующим кодом

### 4.1. `bot/handlers/text.py` — заменить nutrition-проверку на универсальную
Было:
```python
ctx = get_context(user_id)  # из nutrition_context
if ctx and ctx.draft:
    force_agent = "nutrition"
```
Станет:
```python
from bot.core.session_context import get_context
from bot.core.action_resolver import resolve_action

ctx = get_context(user_id)
if ctx and ctx.draft:
    force_agent = ctx.active_domain  # "nutrition" | "fitness" | ...
```

### 4.2. `agents/supervisor.py` — без изменений
Уже поддерживает `force_agent` — новый core просто передаёт правильное имя домена.

### 4.3. `bot/nutrition_context.py` → тонкий адаптер
Текущий модуль станет адаптером поверх core:
- `create_draft()` → вызывает `core.session_context.set_draft()` с `NutritionDraft`
- `get_context()` → вызывает `core.session_context.get_context()`
- `format_draft_card()` → делегирует `NutritionAdapter.format_draft_card()`
- Обратная совместимость: все текущие импорты продолжают работать.

### 4.4. `tools/nutrition_tools.py` — минимальные изменения
Инъекция action_resolver перед вызовом инструментов не нужна — resolver работает на уровне handler'ов. Tools остаются как есть.

## 5. Файловая структура

```
bot/core/
├── __init__.py
├── base_draft.py           # BaseDraft, DraftStatus enum
├── session_context.py      # SessionContext, get/set/clear, TTL, cleanup
├── action_resolver.py      # ActionType, ResolvedAction, resolve_action()
├── followup_engine.py      # FollowupProvider protocol, registry
└── domain_adapter.py       # DomainAdapter protocol

bot/core/adapters/
├── __init__.py
└── nutrition_adapter.py    # NutritionAdapter (реализация DomainAdapter)
```

## 6. Порядок реализации

1. `bot/core/base_draft.py` + `bot/core/session_context.py` — универсальные основы
2. `bot/core/action_resolver.py` — Chat Action Resolver (rule-based)
3. `bot/core/domain_adapter.py` + `bot/core/adapters/nutrition_adapter.py` — адаптер для nutrition
4. `bot/core/followup_engine.py` — универсальный followup с NutritionProvider
5. Рефакторинг `bot/nutrition_context.py` → тонкий адаптер поверх core
6. Рефакторинг `bot/handlers/text.py` — универсальная проверка домена
7. Проверка: все текущие сценарии nutrition работают как раньше

## 7. Критерии готовности

1. Все текущие сценарии Nutrition работают без регрессий
2. `bot/core/` не содержит nutrition-специфичного кода
3. Action resolver корректно определяет: CONFIRM / EDIT / DISCARD / NEW / QUERY
4. Для подключения нового домена (напр. fitness) достаточно:
   - Создать `FitnessDraft(BaseDraft)`
   - Создать `FitnessAdapter(DomainAdapter)`
   - Зарегистрировать followup provider
   - Всё остальное (session context, action resolver, force_agent) работает автоматически
