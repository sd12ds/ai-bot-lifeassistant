# Веб-чат Jarvis — ChatGPT-подобный интерфейс

## 1. Обзор
Отдельное веб-приложение с ChatGPT-подобным дизайном на поддомене **chat.thalors.ai**.
Подключается к тем же агентам, что и Telegram-бот, через общий слой `core/agent_runner.py`.
Поддержка нескольких пользователей, стриминг ответов (SSE), авторизация через Telegram и логин/пароль.

## 2. Архитектура: Shared Core + Adapters

### Текущая схема (только Telegram)
```
Telegram → bot/handlers/ → supervisor.process_message() → ainvoke() → ответ
```

### Новая схема (два канала)
```
                    ┌─ bot/handlers/ → supervisor.process_message() → ainvoke() → текст
core/agent_runner   │
                    └─ api/routers/chat.py → agent_runner.stream() → SSE → веб-чат
```

### Ключевой принцип
- **core/agent_runner.py** — единый интерфейс запуска агентов (sync + stream)
- **supervisor.py** — адаптер для Telegram (без изменений в поведении)
- **api/routers/chat.py** — адаптер для веб-чата (SSE streaming)
- Агенты и tools остаются без изменений — переиспользуются обоими каналами

## 3. Core Layer: agent_runner.py

### Файл: `/root/ai-assistant/core/__init__.py` (пустой)

### Файл: `/root/ai-assistant/core/agent_runner.py`

Назначение: инкапсулирует логику запуска агентов, предоставляя два режима:

**`run_agent(agent, state) -> str`** — текущее поведение:
- Вызывает `agent.ainvoke()` с checkpointer
- Формирует thread_id как `{user_id}_{agent_type}`
- Возвращает строку — финальный ответ

**`stream_agent(agent, state) -> AsyncGenerator[str, None]`** — новое:
- Вызывает `agent.astream_events(version="v2")`
- Фильтрует события `on_chat_model_stream` → извлекает токены
- Yield'ит каждый токен по мере получения

Обе функции используют единую логику:
- Формирование thread_id
- Подготовка input (только последнее HumanMessage)
- Обработка ошибок (retry с новым thread_id при битой истории)
- Инжекция контекста (время МСК, draft контекст для nutrition)

### Рефакторинг supervisor.py
Функция `_run_agent()` из supervisor.py заменяется на вызов `core.agent_runner.run_agent()`.
Поведение Telegram-бота НЕ меняется — только перенос логики в переиспользуемый модуль.

## 4. Backend: API для веб-чата

### Файл: `/root/ai-assistant/api/routers/chat.py`

#### Эндпоинты

**POST `/api/chat/conversations`** — создать новый диалог
- Request: `{ "title": "optional" }`
- Response: `{ "id": "uuid", "title": "Новый диалог", "created_at": "..." }`

**GET `/api/chat/conversations`** — список диалогов пользователя
- Response: `[{ "id", "title", "updated_at", "last_message_preview" }]`
- Сортировка: по updated_at DESC

**DELETE `/api/chat/conversations/{id}`** — удалить диалог

**PATCH `/api/chat/conversations/{id}`** — переименовать диалог
- Request: `{ "title": "Новое название" }`

**GET `/api/chat/conversations/{id}/messages`** — история сообщений
- Response: `[{ "id", "role", "content", "created_at" }]`
- Пагинация: `?limit=50&before=message_id`

**POST `/api/chat/conversations/{id}/send`** — отправить сообщение (SSE streaming)
- Request: `{ "content": "текст сообщения" }`
- Response: `text/event-stream` (Server-Sent Events)
- Формат событий:
```
event: token
data: {"t": "Привет"}

event: token
data: {"t": ", как"}

event: done
data: {"message_id": "uuid", "agent_type": "assistant"}
```
- Сообщение пользователя и полный ответ AI сохраняются в БД после стриминга

**POST `/api/chat/conversations/{id}/send`** (без Accept: text/event-stream) — синхронный режим
- Response: `{ "message_id": "uuid", "content": "...", "agent_type": "..." }`

#### SSE реализация
```python
from fastapi.responses import StreamingResponse

async def stream_chat(conversation_id, content, user):
    async def event_generator():
        # 1. Определяем агента через classify_intent
        # 2. Запускаем stream_agent() из core/agent_runner
        # 3. Yield SSE events для каждого токена
        full_response = ""
        async for token in agent_runner.stream_agent(agent, state):
            full_response += token
            yield f"event: token\ndata: {json.dumps({'t': token})}\n\n"
        # 4. Сохраняем полный ответ в БД
        yield f"event: done\ndata: {json.dumps({'message_id': msg_id})}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

#### Авто-генерация названия диалога
После первого сообщения в новом диалоге — фоново (не блокируя стрим) генерируем название:
- LLM-вызов gpt-4.1-nano: "Придумай короткое название (3-5 слов) для диалога: {first_message}"
- Обновляем conversation.title через asyncio.create_task()

## 5. База данных

### Новые таблицы (Alembic миграция)

**`chat_conversations`**
- `id` — UUID, PK
- `user_id` — BigInteger, FK -> users.telegram_id
- `title` — String(200), default "Новый диалог"
- `created_at` — DateTime(tz), server_default=now()
- `updated_at` — DateTime(tz), onupdate=now()

**`chat_messages`**
- `id` — UUID, PK
- `conversation_id` — UUID, FK -> chat_conversations.id (CASCADE)
- `role` — String(20): "user" | "assistant" | "system"
- `content` — Text
- `agent_type` — String(30), nullable (для ответов assistant)
- `created_at` — DateTime(tz), server_default=now()

Индексы:
- `chat_messages(conversation_id, created_at)` — быстрая выборка истории
- `chat_conversations(user_id, updated_at DESC)` — быстрая выборка списка

**Примечание:** LangGraph checkpointer используется параллельно для памяти агентов.
thread_id для веб-чата: `web_{user_id}_{conversation_id}_{agent_type}` — изолированно от Telegram.

## 6. Авторизация

### Два способа входа

**Способ 1: Telegram Login Widget**
- На странице логина — кнопка "Войти через Telegram" (Telegram Login Widget)
- Бэкенд верифицирует данные виджета (HMAC-SHA256 с BOT_TOKEN)
- Создаёт/находит User, выдаёт JWT (access 15 мин + refresh 7 дней в httpOnly cookie)
- Новый эндпоинт: `POST /api/auth/telegram-login`

**Способ 2: Email + пароль**
- Регистрация: `POST /api/auth/register` — email, password
- Создаёт нового User (без telegram_id), хеширует пароль (bcrypt)
- Вход: `POST /api/auth/login` — email, password -> JWT
- Для связки с Telegram — опционально через /api/auth/link-telegram

**Дополнительно:**
- Существующая система (initData / magic-link JWT) остаётся для miniapp без изменений
- Веб-чат использует httpOnly cookies для хранения токенов (безопаснее localStorage)

### Новые поля в User (миграция)
- `password_hash` — String(255), nullable (для email-пароль авторизации)
- Поле `email` уже существует в модели

## 7. Frontend: Chat App

### Проект: `/root/ai-assistant/chat-app/`

### Стек (тот же что miniapp)
- React 19 + Vite 7 + TypeScript 5.9
- Tailwind CSS v4
- Zustand (состояние)
- React Query (серверные данные)
- Framer Motion (анимации)

### Структура
```
chat-app/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── api/
    │   └── client.ts          — axios + JWT httpOnly cookies
    ├── features/
    │   ├── auth/
    │   │   ├── LoginPage.tsx          — Telegram Widget + email/пароль форма
    │   │   ├── RegisterPage.tsx       — регистрация по email
    │   │   └── useAuth.ts             — Zustand store авторизации
    │   └── chat/
    │       ├── ChatLayout.tsx         — главный лейаут (sidebar + main)
    │       ├── Sidebar.tsx            — список диалогов + кнопка "Новый чат"
    │       ├── ConversationItem.tsx   — элемент в sidebar
    │       ├── ChatWindow.tsx         — основная область чата
    │       ├── MessageList.tsx        — список сообщений со scroll
    │       ├── MessageBubble.tsx      — одно сообщение (user/assistant)
    │       ├── ChatInput.tsx          — поле ввода + кнопка отправки
    │       ├── MarkdownRenderer.tsx   — рендер markdown в ответах
    │       ├── StreamingMessage.tsx   — сообщение с печатающимся текстом
    │       ├── useConversations.ts    — React Query: CRUD диалогов
    │       ├── useMessages.ts         — React Query: история + отправка
    │       ├── useSSE.ts              — хук для SSE стриминга
    │       └── chatStore.ts           — Zustand: активный диалог, UI state
    ├── shared/
    │   ├── components/
    │   │   ├── ThemeToggle.tsx    — переключатель темы
    │   │   └── Avatar.tsx         — аватар пользователя/AI
    │   └── hooks/
    │       └── useTheme.ts        — тёмная/светлая тема
    └── styles/
        └── globals.css
```

### UI/UX дизайн (ChatGPT-like)

**Лейаут:**
- Sidebar слева (280px, сворачиваемый на мобильных): список диалогов, кнопка "Новый чат"
- Основная область справа: сообщения + поле ввода внизу

**Сообщения:**
- User: выравнивание справа, синий/серый фон
- Assistant: выравнивание слева, без фона или лёгкий серый
- Markdown рендеринг: код с подсветкой, списки, заголовки, bold, italic
- Код-блоки: с кнопкой копирования

**Стриминг:**
- Текст появляется по токенам (как в ChatGPT)
- Мигающий курсор во время генерации
- Кнопка "Остановить генерацию"

**Темы:**
- Тёмная тема по умолчанию (как ChatGPT)
- Светлая тема через toggle

**Адаптивность:**
- Desktop: sidebar + chat рядом
- Mobile: sidebar по гамбургеру, chat на весь экран

## 8. Деплой и инфраструктура

### Поддомен
- **chat.thalors.ai** (или chat.77-238-235-171.sslip.io на время разработки)
- SSL через Certbot (как research.thalors.ai)

### Nginx
Новый server block `/etc/nginx/sites-available/chat`:
```nginx
server {
    server_name chat.thalors.ai;
    root /var/www/chat;
    index index.html;

    location = /index.html {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }
    location /assets/ {
        add_header Cache-Control "public, max-age=31536000, immutable";
    }
    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # SSE: отключаем буферизацию для streaming
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
    listen 443 ssl;
    # ... certbot managed
}
```

**Важно для SSE:** `proxy_buffering off` — иначе nginx буферизирует SSE и токены приходят пачками.

### Vite конфиг
- `outDir: /var/www/chat` — пишет напрямую в nginx webroot
- `emptyOutDir: false` — НЕ чистить (как в miniapp)
- Деплой: `cd /root/ai-assistant/chat-app && npm run deploy`

### CORS
Добавить `https://chat.thalors.ai` в `ALLOWED_ORIGINS` в `.env`

### Docker
Отдельный docker-сервис НЕ нужен — фронтенд статический (Vite build -> nginx).
Бэкенд обслуживается тем же контейнером `ai_api` (FastAPI).

## 9. Порядок реализации

### Фаза 1: Core Layer (рефакторинг)
1. Создать `core/agent_runner.py` с `run_agent()` и `stream_agent()`
2. Рефакторинг `supervisor.py` — заменить `_run_agent()` на вызов `core.agent_runner.run_agent()`
3. Проверить что Telegram-бот работает как прежде

### Фаза 2: Backend
4. Alembic миграция: таблицы `chat_conversations`, `chat_messages`, поле `password_hash`
5. `api/routers/chat.py` — CRUD диалогов + SSE send
6. `api/routers/auth.py` — эндпоинты Telegram Login + email/password
7. Тестирование SSE через curl

### Фаза 3: Frontend
8. Инициализация проекта chat-app (React + Vite + Tailwind)
9. Auth flow: Login/Register страницы
10. Chat UI: layout, sidebar, messages, input
11. SSE стриминг: useSSE хук + StreamingMessage
12. Markdown рендеринг + code highlighting

### Фаза 4: Деплой
13. DNS: chat.thalors.ai -> 77.238.235.171
14. Nginx конфиг + Certbot SSL
15. Vite build -> /var/www/chat
16. CORS + тестирование
