"""
Централизованная конфигурация проекта.
Все настройки читаются из .env через python-dotenv.
"""
from __future__ import annotations

import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")

# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_LLM_MODEL: str = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
OPENAI_STT_MODEL: str = os.getenv("OPENAI_STT_MODEL", "gpt-4o-mini-transcribe")
OPENAI_TTS_MODEL: str = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
OPENAI_TTS_VOICE: str = os.getenv("OPENAI_TTS_VOICE", "alloy")

# ── Голосовой режим ───────────────────────────────────────────────────────────
# "auto" — голос только если пришло голосовое, "always" / "never"
VOICE_REPLY_MODE: str = os.getenv("VOICE_REPLY_MODE", "auto")

# ── Часовой пояс ──────────────────────────────────────────────────────────────
DEFAULT_TIMEZONE_STR: str = os.getenv("DEFAULT_TIMEZONE", "Europe/Moscow")
DEFAULT_TZ: ZoneInfo = ZoneInfo(DEFAULT_TIMEZONE_STR)

# ── База данных ───────────────────────────────────────────────────────────────
# Хранилище пользовательских данных (users, tasks, crm_*)
DB_PATH: str = os.getenv("DB_PATH", "/root/ai-assistant/db/app.db")
# Хранилище чекпоинтов LangGraph (память диалогов)
CHECKPOINTS_DB_PATH: str = os.getenv(
    "CHECKPOINTS_DB_PATH", "/root/ai-assistant/db/checkpoints.db"
)

# ── PostgreSQL (основная БД, Этап 1+) ────────────────────────────────────────
# Если DATABASE_URL задан — бот и API используют PostgreSQL.
# Если не задан — фолбэк на SQLite (обратная совместимость).
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{DB_PATH}",
)

# ── Доступ к бизнес-режиму ────────────────────────────────────────────────────
# Telegram user_id через запятую: "123456,789012"
# Если пусто — бизнес-режим доступен всем
_biz_users_raw: str = os.getenv("BUSINESS_MODE_USERS", "")
BUSINESS_MODE_USERS: set[int] = (
    {int(uid.strip()) for uid in _biz_users_raw.split(",") if uid.strip()}
    if _biz_users_raw
    else set()
)

# ── Валидация обязательных переменных ─────────────────────────────────────────
def validate() -> None:
    """Вызывается при старте — падает с понятным сообщением если что-то не задано."""
    missing = []
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if missing:
        raise RuntimeError(f"Не заданы обязательные переменные окружения: {', '.join(missing)}")
