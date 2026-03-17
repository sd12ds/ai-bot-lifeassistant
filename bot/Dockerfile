FROM python:3.12-slim

WORKDIR /app

# Системные зависимости: ffmpeg нужен pydub для обработки голосовых сообщений
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Python-зависимости (кешируется отдельным слоем)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта
COPY . .

ENV PYTHONPATH=/app

# Точка входа бота (polling + handlers + supervisor)
CMD ["python", "main.py"]
