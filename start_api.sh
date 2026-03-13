#!/bin/bash
# Запускает FastAPI через uvicorn с PostgreSQL.
# DATABASE_URL экспортируется до load_dotenv() — имеет приоритет над .env
cd /root/ai-assistant
export DATABASE_URL='postgresql+asyncpg://aiuser:changeme@localhost:5432/aiassistant'
exec venv/bin/python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2
