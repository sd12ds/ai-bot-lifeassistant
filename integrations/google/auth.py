"""
Google OAuth2 авторизация.
Перенесено из google_auth.py с подключением к config.
"""
from __future__ import annotations

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Права доступа к Google Calendar
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Пути к файлам учётных данных (рядом с корнем проекта)
_BASE = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
CREDENTIALS_FILE = os.path.join(_BASE, "credentials.json")
TOKEN_FILE = os.path.join(_BASE, "token.json")


def get_google_creds() -> Credentials:
    """Возвращает валидные Google credentials, обновляет токен при необходимости."""
    creds: Credentials | None = None

    # Загружаем сохранённый токен
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # Если токен истёк — обновляем
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)
    elif not creds or not creds.valid:
        # Первичная авторизация через браузер
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        _save_token(creds)

    return creds


def _save_token(creds: Credentials) -> None:
    """Сохраняет токен на диск."""
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
