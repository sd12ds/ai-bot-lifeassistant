from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import dateparser
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message
from dotenv import load_dotenv
from openai import AsyncOpenAI

from google_calendar import (
    list_upcoming_events,
    list_events_for_day,
    search_events_text,
    create_event_from_datetime,
    delete_events_by_title,
    move_event_by_title,
    rename_event_by_title,
    change_duration_by_title,
)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
VOICE_REPLY_MODE = os.getenv("VOICE_REPLY_MODE", "auto")
OPENAI_STT_MODEL = os.getenv("OPENAI_STT_MODEL", "gpt-4o-mini-transcribe")
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "alloy")
DEFAULT_TZ = ZoneInfo("Europe/Moscow")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN not set")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

CHAT_STATE = defaultdict(lambda: {"last_search_title": None})


def should_reply_with_voice(message: Message) -> bool:
    if VOICE_REPLY_MODE == "always":
        return True
    if VOICE_REPLY_MODE == "never":
        return False
    return bool(message.voice or message.audio)


async def ask_llm(user_text: str) -> str:
    response = await client.responses.create(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": "Ты Telegram-ассистент. Отвечай по-русски, коротко и по делу."},
            {"role": "user", "content": user_text},
        ],
    )
    return response.output_text.strip()


async def transcribe_audio(path: str) -> str:
    with open(path, "rb") as audio_file:
        transcript = await client.audio.transcriptions.create(
            model=OPENAI_STT_MODEL,
            file=audio_file,
        )
    return getattr(transcript, "text", "").strip()


async def synthesize_speech_to_ogg(text: str) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        mp3_path = Path(tmpdir) / "reply.mp3"
        ogg_path = Path(tmpdir) / "reply.ogg"

        audio = await client.audio.speech.create(
            model=OPENAI_TTS_MODEL,
            voice=OPENAI_TTS_VOICE,
            input=text[:4000],
        )

        with open(mp3_path, "wb") as f:
            f.write(audio.read())

        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-i",
            str(mp3_path),
            "-c:a",
            "libopus",
            "-b:a",
            "24k",
            "-vbr",
            "on",
            "-compression_level",
            "10",
            str(ogg_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        code = await proc.wait()
        if code != 0 or not ogg_path.exists():
            raise RuntimeError("ffmpeg conversion failed")

        final_path = Path(tempfile.gettempdir()) / f"tg_reply_{os.getpid()}_{id(text)}.ogg"
        final_path.write_bytes(ogg_path.read_bytes())
        return str(final_path)


async def send_text_and_optional_voice(message: Message, text: str, send_voice: bool = True):
    if send_voice:
        ogg_path = await synthesize_speech_to_ogg(text)
        try:
            await message.answer_voice(FSInputFile(ogg_path))
            await message.answer(text)
        finally:
            try:
                os.remove(ogg_path)
            except OSError:
                pass
    else:
        await message.answer(text)


def parse_datetime(date_text: str, time_text: str | None = None) -> datetime | None:
    date_text = (date_text or "").strip()
    time_text = (time_text or "").strip()

    if time_text:
        time_text = re.sub(r"\b(\d{1,2})\.(\d{2})\b", r"\1:\2", time_text)

        def _hour_to_time(match, plus12=False):
            hour = int(match.group(1))
            if plus12 and hour < 12:
                hour += 12
            return f"{hour:02d}:00"

        time_text = re.sub(r"\b(\d{1,2})\s*час(?:а|ов)?\s*дня\b", lambda m: _hour_to_time(m, True), time_text, flags=re.IGNORECASE)
        time_text = re.sub(r"\b(\d{1,2})\s*час(?:а|ов)?\s*вечера\b", lambda m: _hour_to_time(m, True), time_text, flags=re.IGNORECASE)
        time_text = re.sub(r"\b(\d{1,2})\s*час(?:а|ов)?\s*утра\b", lambda m: _hour_to_time(m, False), time_text, flags=re.IGNORECASE)
        time_text = re.sub(r"\b(\d{1,2})\s*час(?:а|ов)?\b", lambda m: f"{int(m.group(1)):02d}:00", time_text, flags=re.IGNORECASE)

    combined = f"{date_text} {time_text}".strip()
    parsed = dateparser.parse(
        combined,
        languages=["ru", "uk"],
        settings={
            "TIMEZONE": "Europe/Moscow",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
        },
    )
    if not parsed:
        return None
    return parsed.astimezone(DEFAULT_TZ)


def parse_duration_minutes(text: str) -> int | None:
    text = text.lower()
    m = re.search(r"(\d+)\s*мин", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*час", text)
    if m:
        return int(m.group(1)) * 60
    if "полчаса" in text:
        return 30
    return None


def extract_duration_change_rule(user_text: str) -> dict | None:
    text = user_text.strip()
    text_lower = text.lower()

    if not any(x in text_lower for x in ["не на", "длительност", "минут", "час"]):
        return None

    duration_minutes = parse_duration_minutes(text_lower)
    if not duration_minutes:
        return None

    patterns = [
        r"(?:сделай|измени|поменяй)\s+(?:встречу|событие|созвон|задачу)\s+(.+?)\s+не\s+на\s+.+?а\s+на\s+\d+\s*(?:мин|минут|час|часа|часов)",
        r"(?:сделай|измени|поменяй)\s+(.+?)\s+не\s+на\s+.+?а\s+на\s+\d+\s*(?:мин|минут|час|часа|часов)",
        r"(?:уменьши|увеличь)\s+длительность\s+(?:встречи|события|созвона|задачи)\s+(.+?)\s+до\s+\d+\s*(?:мин|минут|час|часа|часов)",
    ]

    title = None
    for pattern in patterns:
        m = re.search(pattern, text_lower, flags=re.IGNORECASE)
        if m:
            title = m.group(1).strip(" .,!?:;\"'«»")
            break

    if not title:
        return None

    title = re.sub(r"^(встречу|событие|созвон|задачу)\s+", "", title, flags=re.IGNORECASE).strip()

    return {
        "intent": "change_duration",
        "title": title,
        "duration_minutes": duration_minutes,
        "date_text": "",
        "old_date_text": "",
    }


def looks_calendar_related(text: str) -> bool:
    text = text.lower()
    keywords = [
        "встреч", "созвон", "календар", "событ", "задач", "напомин",
        "поставь", "запланиру", "создай", "добавь", "удали", "перенеси",
        "найди", "покажи", "их", "все", "завтра", "послезавтра", "сегодня",
        "понедельник", "вторник", "сред", "четверг", "пятниц", "суббот",
        "воскрес", "выходн", "переимен", "не на час", "минут",
    ]
    return any(k in text for k in keywords)


def extract_simple_calendar_rule(user_text: str) -> dict | None:
    text = user_text.strip()
    low = text.lower().strip()

    if (
        ("что у меня" in low or "что в календаре" in low or "покажи" in low or "какие" in low)
        and ("календар" in low or "встреч" in low or "событ" in low or "созвон" in low)
    ) or low.startswith("что у меня завтра") or low.startswith("что у меня послезавтра"):
        date_text = ""
        for token in [
            "сегодня", "завтра", "послезавтра", "на выходных",
            "понедельник", "вторник", "среду", "среда", "четверг",
            "пятницу", "пятница", "субботу", "суббота", "воскресенье",
        ]:
            if token in low:
                date_text = token
                break
        m = re.search(r"(\d{1,2}\.\d{1,2}(?:\.\d{4})?)", low)
        if m:
            date_text = m.group(1)
        return {"intent": "list_events", "date_text": date_text, "time_text": ""}

    if low.startswith("найди") or low.startswith("покажи все встречи") or low.startswith("покажи встречи"):
        title = low
        title = re.sub(r"^(найди|покажи)\s+", "", title)
        title = re.sub(r"^(мне\s+)?", "", title)
        title = re.sub(r"^(все\s+)?", "", title)
        title = re.sub(r"^(встречи|встречу|события|событие|созвоны|созвон|задачи|задачу)\s+", "", title)
        title = title.strip(" .,!?:;")
        if title:
            return {"intent": "search_events", "title": title, "date_text": "", "time_text": ""}

    m = re.search(r"удали\s+все\s+(?:встречи|события|созвоны|задачи)?\s*(.+)$", low)
    if m:
        title = m.group(1).strip(" .,!?:;")
        return {
            "intent": "delete_event",
            "title": title,
            "delete_all": True,
            "date_text": "",
            "time_text": "",
            "old_date_text": "",
        }

    if low in {"удали их", "удали его", "удали ее", "удали её"}:
        return {
            "intent": "delete_event",
            "title": "",
            "delete_all": True,
            "date_text": "",
            "time_text": "",
            "old_date_text": "",
        }

    return None


async def extract_calendar_intent(user_text: str) -> dict:
    prompt = f"""
Разбери сообщение пользователя как команду календаря.
Верни только JSON, без markdown и без пояснений.

Формат:
{{
  "intent": "create_event" | "delete_event" | "move_event" | "list_events" | "search_events" | "rename_event" | "change_duration" | "none",
  "title": "строка",
  "new_title": "строка",
  "date_text": "строка",
  "time_text": "HH:MM или пустая строка",
  "old_date_text": "строка",
  "new_date_text": "строка",
  "new_time_text": "HH:MM или пустая строка",
  "delete_all": false,
  "duration_minutes": 60
}}

Правила:
- create_event: создать встречу / задачу / событие / созвон.
- delete_event: удалить событие.
- move_event: перенести событие на новую дату/время.
- list_events: показать, что в календаре на дату/день.
- search_events: найти события по названию.
- rename_event: переименовать событие.
- change_duration: изменить длительность события. Пример: "сделай встречу тест не на час, а на 30 минут" -> intent="change_duration", title="тест", duration_minutes=30.
- none: не календарная команда.
- title: короткое название события без слов "встреча", "событие", "созвон", если это просто тип.
- new_title: новое название при переименовании.
- Если пользователь пишет "удали их", title оставь пустым, delete_all=true.
- Если пользователь пишет "удали все встречи тест", title="тест", delete_all=true.
- old_date_text: исходная дата события, если пользователь её уточняет, например "с 12.03.2026".
- time_text/new_time_text: приводить к HH:MM.
- duration_minutes: если пользователь просит изменить длительность, верни нужное число минут.
- Ответ только JSON.

Сообщение пользователя:
{user_text}
""".strip()

    response = await client.responses.create(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": "Ты сервис разбора календарных команд. Отвечай только валидным JSON."},
            {"role": "user", "content": prompt},
        ],
    )

    raw = response.output_text.strip()
    logging.info("CALENDAR RAW: %s", raw)
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {"intent": "none"}
        return data
    except json.JSONDecodeError:
        return {"intent": "none", "raw": raw}


async def handle_calendar_command(chat_id: int, user_text: str) -> tuple[bool, object]:
    if not looks_calendar_related(user_text):
        return False, ""

    simple_rule = extract_simple_calendar_rule(user_text)
    if simple_rule:
        data = simple_rule
    else:
        rule_data = extract_duration_change_rule(user_text)
        if rule_data:
            data = rule_data
        else:
            data = await extract_calendar_intent(user_text)

    intent = data.get("intent", "none")
    state = CHAT_STATE[chat_id]

    if intent == "create_event":
        title = (data.get("title") or "Встреча").strip()
        date_text = data.get("date_text", "")
        time_text = data.get("time_text", "")
        duration_minutes = int(data.get("duration_minutes") or 60)

        start_dt = parse_datetime(date_text, time_text)
        if not start_dt:
            return True, "Не смог понять дату и время."

        link = create_event_from_datetime(title, start_dt, duration_minutes=duration_minutes)
        return True, {
            "voice": None,
            "text": (
                f"Событие создано: {title}\n"
                f"Дата: {start_dt.strftime('%d.%m.%Y %H:%M')}\n"
                f"{link}"
            ),
        }

    if intent == "search_events":
        title = (data.get("title") or "").strip()
        if not title:
            return True, "Не понял, какие события искать."
        date_text = data.get("date_text", "")
        time_text = data.get("time_text", "")
        target_dt = parse_datetime(date_text, time_text) if date_text or time_text else None
        state["last_search_title"] = title
        result = search_events_text(title, target_dt=target_dt)
        return True, {"voice": result, "text": result}

    if intent == "delete_event":
        delete_all = bool(data.get("delete_all"))
        title = (data.get("title") or "").strip()
        if delete_all and not title:
            title = state.get("last_search_title") or ""
        if not title:
            return True, "Не понял, какое событие удалить."

        date_text = data.get("date_text") or data.get("old_date_text", "")
        time_text = data.get("time_text", "")
        target_dt = parse_datetime(date_text, time_text) if date_text or time_text else None

        result = delete_events_by_title(title, target_dt=target_dt, delete_all=delete_all)
        return True, {"voice": result, "text": result}

    if intent == "move_event":
        title = (data.get("title") or "").strip()
        if not title:
            return True, "Не понял, какое событие переносить."

        old_date_text = data.get("old_date_text", "")
        target_dt = parse_datetime(old_date_text, "") if old_date_text else None

        new_date_text = data.get("new_date_text") or data.get("date_text", "")
        new_time_text = data.get("new_time_text") or data.get("time_text", "")
        new_start_dt = parse_datetime(new_date_text, new_time_text)
        if not new_start_dt:
            return True, f"Не смог понять новую дату и время. Я получил: дата='{new_date_text}', время='{new_time_text}'."

        result = move_event_by_title(title, new_start_dt, target_dt=target_dt)
        voice_text = f"Событие перенесено: {title}. Новая дата: {new_start_dt.strftime('%d.%m.%Y %H:%M')}."
        return True, {"voice": voice_text, "text": result}

    if intent == "rename_event":
        title = (data.get("title") or "").strip()
        new_title = (data.get("new_title") or "").strip()
        if not title or not new_title:
            return True, "Не понял, что именно переименовать."
        date_text = data.get("date_text") or data.get("old_date_text", "")
        target_dt = parse_datetime(date_text, "") if date_text else None
        result = rename_event_by_title(title, new_title, target_dt=target_dt)
        return True, {"voice": result, "text": result}

    if intent == "change_duration":
        title = (data.get("title") or "").strip()
        if not title:
            return True, "Не понял, для какого события менять длительность."
        duration_minutes = int(data.get("duration_minutes") or 0)
        if duration_minutes <= 0:
            duration_minutes = parse_duration_minutes(user_text) or 0
        if duration_minutes <= 0:
            return True, "Не понял новую длительность."
        date_text = data.get("date_text") or data.get("old_date_text", "")
        target_dt = parse_datetime(date_text, "") if date_text else None
        result = change_duration_by_title(title, duration_minutes, target_dt=target_dt)
        return True, {"voice": result, "text": result}

    if intent == "list_events":
        target_dt = parse_datetime(data.get("date_text", ""), data.get("time_text", ""))
        result = list_events_for_day(target_dt) if target_dt else list_upcoming_events()
        return True, {"voice": result, "text": result}

    return False, ""


@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        "Привет. Я умею работать с календарём.\n\n"
        "Примеры:\n"
        "— создай встречу завтра в 15 с названием тест\n"
        "— найди мне все встречи тест\n"
        "— удали встречу тест на 13.03.2026\n"
        "— удали все встречи тест\n"
        "— удали их\n"
        "— перенеси встречу тест с 13.03.2026 на пятницу в 18:30\n"
        "— переименуй встречу тест в созвон с командой\n"
        "— сделай встречу тест не на час, а на 30 минут\n"
        "— что у меня в календаре завтра"
    )


@dp.message(Command("voice_on"))
async def voice_on_handler(message: Message):
    global VOICE_REPLY_MODE
    VOICE_REPLY_MODE = "always"
    await message.answer("Теперь отвечаю голосом.")


@dp.message(Command("voice_off"))
async def voice_off_handler(message: Message):
    global VOICE_REPLY_MODE
    VOICE_REPLY_MODE = "never"
    await message.answer("Теперь отвечаю текстом.")


@dp.message(Command("gcal_list"))
async def gcal_list_handler(message: Message):
    await bot.send_chat_action(message.chat.id, "typing")
    try:
        result = list_upcoming_events()
    except Exception as e:
        result = f"Ошибка календаря: {e}"
    await message.answer(result)


@dp.message(F.voice)
async def voice_handler(message: Message):
    await bot.send_chat_action(message.chat.id, "typing")

    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = Path(tmpdir) / "voice.ogg"
        file = await bot.get_file(message.voice.file_id)
        await bot.download_file(file.file_path, destination=src_path)

        user_text = await transcribe_audio(str(src_path))
        logging.info("VOICE RAW: %s", user_text)

        if not user_text:
            await message.answer("Не смог разобрать голосовое.")
            return

        handled, reply_payload = await handle_calendar_command(message.chat.id, user_text)
        if handled:
            if isinstance(reply_payload, dict):
                text_text = reply_payload.get("text", "")
                voice_text = reply_payload.get("voice", text_text)
                send_voice = voice_text is not None and should_reply_with_voice(message)
            else:
                text_text = str(reply_payload)
                voice_text = text_text
                send_voice = should_reply_with_voice(message)

            if send_voice:
                await send_text_and_optional_voice(message, str(voice_text), send_voice=True)
                if str(voice_text) != text_text:
                    await message.answer(text_text)
            else:
                await message.answer(text_text)
            return

        answer = await ask_llm(user_text)
        await send_text_and_optional_voice(message, answer, send_voice=should_reply_with_voice(message))


@dp.message(F.text)
async def text_handler(message: Message):
    await bot.send_chat_action(message.chat.id, "typing")
    logging.info("TEXT RAW: %s", message.text)

    handled, reply_payload = await handle_calendar_command(message.chat.id, message.text)
    if handled:
        if isinstance(reply_payload, dict):
            text_text = reply_payload.get("text", "")
            voice_text = reply_payload.get("voice", text_text)
            send_voice = voice_text is not None
        else:
            text_text = str(reply_payload)
            voice_text = text_text
            send_voice = True

        if send_voice:
            await send_text_and_optional_voice(message, str(voice_text), send_voice=True)
            if str(voice_text) != text_text:
                await message.answer(text_text)
        else:
            await message.answer(text_text)
        return

    answer = await ask_llm(message.text)
    await send_text_and_optional_voice(message, answer, send_voice=True)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
