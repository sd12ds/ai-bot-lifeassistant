import os
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

BASE_DIR = Path.home() / "ai-assistant"
TOKEN_FILE = BASE_DIR / "token.json"
CREDS_FILE = BASE_DIR / "credentials.json"

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_google_creds():
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        return creds

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)

    # важно: явно задаём redirect_uri
    flow.redirect_uri = "http://localhost:8080/"

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )

    print("\nОткрой эту ссылку в браузере:\n")
    print(auth_url)
    print("\nПосле входа Google перекинет тебя на localhost и браузер покажет ошибку.")
    print("Это нормально.")
    print("Скопируй ПОЛНЫЙ URL из адресной строки и вставь сюда.\n")

    authorization_response = input("Вставь полный URL: ").strip()

    flow.fetch_token(authorization_response=authorization_response)
    creds = flow.credentials

    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return creds
