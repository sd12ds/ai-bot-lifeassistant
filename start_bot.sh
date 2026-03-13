#!/bin/bash
# Запускает Telegram-бот с PostgreSQL в качестве хранилища.
# DATABASE_URL экспортируется до load_dotenv() — имеет приоритет над .env
cd /root/ai-assistant
export DATABASE_URL='postgresql+asyncpg://aiuser:changeme@localhost:5432/aiassistant'
exec venv/bin/python3 main.py
