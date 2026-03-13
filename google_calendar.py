from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from google_auth import get_google_creds

MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def get_calendar_service():
    creds = get_google_creds()
    return build("calendar", "v3", credentials=creds)


def _to_moscow(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=MOSCOW_TZ)
    return dt.astimezone(MOSCOW_TZ)


def _parse_event_start(event: dict) -> Optional[datetime]:
    start_raw = event.get("start", {}).get("dateTime")
    if not start_raw:
        return None
    try:
        return datetime.fromisoformat(start_raw.replace("Z", "+00:00")).astimezone(MOSCOW_TZ)
    except Exception:
        return None


def _parse_event_end(event: dict) -> Optional[datetime]:
    end_raw = event.get("end", {}).get("dateTime")
    if not end_raw:
        return None
    try:
        return datetime.fromisoformat(end_raw.replace("Z", "+00:00")).astimezone(MOSCOW_TZ)
    except Exception:
        return None


def _format_event_line(event: dict) -> str:
    start_raw = event["start"].get("dateTime", event["start"].get("date"))
    summary = event.get("summary", "Без названия")
    try:
        if "T" in start_raw:
            dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00")).astimezone(MOSCOW_TZ)
            start_str = dt.strftime("%d.%m.%Y %H:%M")
        else:
            start_str = start_raw
    except Exception:
        start_str = start_raw
    return f"{start_str} — {summary}"


def _normalize_title(value: str) -> str:
    value = (value or "").strip().lower()
    for ch in ['"', "'", "«", "»", ".", ",", "!", "?", ":", ";", "(", ")", "[", "]", "{", "}"]:
        value = value.replace(ch, "")
    return " ".join(value.split())


def list_upcoming_events(max_results: int = 10) -> str:
    service = get_calendar_service()
    now = datetime.now(timezone.utc).isoformat()

    events_result = service.events().list(
        calendarId="primary",
        timeMin=now,
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = events_result.get("items", [])
    if not events:
        return "Ближайших событий нет."

    return "\n".join(_format_event_line(event) for event in events)


def list_events_for_range(start_dt: datetime, end_dt: datetime, max_results: int = 100) -> list[dict]:
    service = get_calendar_service()
    start_dt = _to_moscow(start_dt)
    end_dt = _to_moscow(end_dt)

    events_result = service.events().list(
        calendarId="primary",
        timeMin=start_dt.astimezone(timezone.utc).isoformat(),
        timeMax=end_dt.astimezone(timezone.utc).isoformat(),
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return events_result.get("items", [])


def list_events_for_day(target_dt: datetime, max_results: int = 100) -> str:
    target_dt = _to_moscow(target_dt)
    day_start = target_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    events = list_events_for_range(day_start, day_end, max_results=max_results)

    if not events:
        return f"На {day_start.strftime('%d.%m.%Y')} событий нет."

    header = f"События на {day_start.strftime('%d.%m.%Y')}:"
    body = "\n".join(_format_event_line(event) for event in events)
    return f"{header}\n{body}"


def create_event(summary: str, start_iso: str, end_iso: str) -> str:
    service = get_calendar_service()
    event = {
        "summary": summary,
        "start": {"dateTime": start_iso, "timeZone": "Europe/Moscow"},
        "end": {"dateTime": end_iso, "timeZone": "Europe/Moscow"},
    }
    created = service.events().insert(calendarId="primary", body=event).execute()
    return created.get("htmlLink", "Событие создано")


def create_event_from_datetime(summary: str, start_dt: datetime, duration_minutes: int = 60) -> str:
    start_dt = _to_moscow(start_dt).replace(microsecond=0)
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    return create_event(summary, start_dt.isoformat(), end_dt.isoformat())


def find_events_by_title(
    title: str,
    max_results: int = 100,
    days_forward: int = 365,
    target_dt: Optional[datetime] = None,
) -> list[dict]:
    service = get_calendar_service()
    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=days_forward)

    events_result = service.events().list(
        calendarId="primary",
        timeMin=now.isoformat(),
        timeMax=time_max.isoformat(),
        q=title,
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = events_result.get("items", [])
    wanted = _normalize_title(title)

    exact = []
    contains = []
    reverse_contains = []

    for event in events:
        normalized = _normalize_title(event.get("summary", ""))
        if normalized == wanted:
            exact.append(event)
        elif wanted and wanted in normalized:
            contains.append(event)
        elif wanted and normalized in wanted:
            reverse_contains.append(event)

    ranked = exact or contains or reverse_contains or events

    if target_dt is not None:
        target_dt = _to_moscow(target_dt)
        day_start = target_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        same_day = []
        for event in ranked:
            event_start = _parse_event_start(event)
            if event_start and day_start <= event_start < day_end:
                same_day.append(event)
        if same_day:
            ranked = same_day

    ranked.sort(key=lambda e: _parse_event_start(e) or datetime.max.replace(tzinfo=MOSCOW_TZ))
    return ranked


def search_events_text(title: str, target_dt: Optional[datetime] = None) -> str:
    events = find_events_by_title(title, target_dt=target_dt)
    if not events:
        return f"События с названием '{title}' не найдены."

    header = f"Нашёл {len(events)} событий по запросу '{title}':"
    body = "\n".join(f"— {_format_event_line(event)}" for event in events[:20])
    return f"{header}\n{body}"


def _ambiguity_message(action_example: str, title: str, events: list[dict]) -> str:
    lines = [f"Нашёл несколько событий с названием '{title}'. Уточни дату:"]
    for event in events[:8]:
        lines.append(f"— {_format_event_line(event)}")
    lines.append(action_example)
    return "\n".join(lines)


def delete_events_by_title(title: str, target_dt: Optional[datetime] = None, delete_all: bool = False) -> str:
    service = get_calendar_service()
    events = find_events_by_title(title, target_dt=target_dt)

    if not events:
        return f"Событие '{title}' не найдено."

    if not delete_all and target_dt is None and len(events) > 1:
        return _ambiguity_message(
            f"Например: удали встречу {title} на 12.03.2026",
            title,
            events,
        )

    to_delete = events if delete_all else [events[0]]
    deleted_lines = []

    for event in to_delete:
        service.events().delete(calendarId="primary", eventId=event["id"]).execute()
        deleted_lines.append(f"— {_format_event_line(event)}")

    if len(to_delete) == 1:
        event = to_delete[0]
        return f"Событие удалено: {event.get('summary', 'Без названия')}\nДата: {_format_event_line(event).split(' — ')[0]}"

    return f"Удалил {len(to_delete)} событий:\n" + "\n".join(deleted_lines)


def move_event_by_title(
    title: str,
    new_start_dt: datetime,
    duration_minutes: Optional[int] = None,
    target_dt: Optional[datetime] = None,
) -> str:
    service = get_calendar_service()
    events = find_events_by_title(title, target_dt=target_dt)

    if not events:
        return f"Событие '{title}' не найдено."

    if target_dt is None and len(events) > 1:
        return _ambiguity_message(
            f"Например: перенеси встречу {title} с 12.03.2026 на пятницу в 18:30",
            title,
            events,
        )

    event = events[0]
    new_start_dt = _to_moscow(new_start_dt).replace(microsecond=0)

    if duration_minutes is None:
        old_start = _parse_event_start(event)
        old_end = _parse_event_end(event)
        if old_start and old_end:
            duration_minutes = max(1, int((old_end - old_start).total_seconds() // 60))
        else:
            duration_minutes = 60

    new_end_dt = new_start_dt + timedelta(minutes=duration_minutes)
    event["start"] = {"dateTime": new_start_dt.isoformat(), "timeZone": "Europe/Moscow"}
    event["end"] = {"dateTime": new_end_dt.isoformat(), "timeZone": "Europe/Moscow"}

    updated = service.events().update(calendarId="primary", eventId=event["id"], body=event).execute()
    link = updated.get("htmlLink", "")
    return (
        f"Событие перенесено: {updated.get('summary', 'Без названия')}\n"
        f"Новая дата: {new_start_dt.strftime('%d.%m.%Y %H:%M')}\n"
        f"{link}"
    )


def rename_event_by_title(title: str, new_title: str, target_dt: Optional[datetime] = None) -> str:
    service = get_calendar_service()
    events = find_events_by_title(title, target_dt=target_dt)

    if not events:
        return f"Событие '{title}' не найдено."

    if target_dt is None and len(events) > 1:
        return _ambiguity_message(
            f"Например: переименуй встречу {title} на 12.03.2026 в {new_title}",
            title,
            events,
        )

    event = events[0]
    event["summary"] = new_title
    updated = service.events().update(calendarId="primary", eventId=event["id"], body=event).execute()
    return f"Событие переименовано: {title} → {updated.get('summary', new_title)}"


def change_duration_by_title(title: str, duration_minutes: int, target_dt: Optional[datetime] = None) -> str:
    service = get_calendar_service()
    events = find_events_by_title(title, target_dt=target_dt)

    if not events:
        return f"Событие '{title}' не найдено."

    if target_dt is None and len(events) > 1:
        return _ambiguity_message(
            f"Например: сделай встречу {title} на 12.03.2026 не на час, а на 30 минут",
            title,
            events,
        )

    event = events[0]
    start_dt = _parse_event_start(event)
    if not start_dt:
        return "Не смог изменить длительность события."

    new_end_dt = start_dt + timedelta(minutes=duration_minutes)
    event["end"] = {"dateTime": new_end_dt.isoformat(), "timeZone": "Europe/Moscow"}
    updated = service.events().update(calendarId="primary", eventId=event["id"], body=event).execute()
    return (
        f"Длительность события изменена: {updated.get('summary', title)}\n"
        f"Новая длительность: {duration_minutes} минут"
    )
