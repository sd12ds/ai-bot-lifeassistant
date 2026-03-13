FROM python:3.12-slim

WORKDIR /app

# Копируем зависимости
COPY venv/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY venv/bin/uvicorn /usr/local/bin/uvicorn

# Копируем код проекта
COPY api/ ./api/
COPY db/ ./db/
COPY config.py ./

ENV PYTHONPATH=/app

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
