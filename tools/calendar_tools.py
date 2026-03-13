"""
calendar_tools.py — Google Calendar ОТКЛЮЧЁН.
Все инструменты возвращают заглушку. Используйте reminder-систему.
"""
from __future__ import annotations
from langchain.tools import tool

_DISABLED = (
    "⚠️ Google Calendar отключён. "
    "Для создания задач и напоминаний используй команды reminder-агента."
)


@tool
def calendar_list_upcoming(max_results: int = 10) -> str:
    """Показывает ближайшие события (Google Calendar отключён)."""
    return _DISABLED


@tool
def calendar_list_day(date_text: str, time_text: str = "") -> str:
    """Показывает события на день (Google Calendar отключён)."""
    return _DISABLED


@tool
def calendar_search(title: str, date_text: str = "") -> str:
    """Поиск событий (Google Calendar отключён)."""
    return _DISABLED


@tool
def calendar_create(
    title: str,
    date_text: str,
    time_text: str,
    duration_minutes: int = 60,
) -> str:
    """Создаёт событие (Google Calendar отключён)."""
    return _DISABLED


@tool
def calendar_delete(
    title: str,
    date_text: str = "",
    delete_all: bool = False,
) -> str:
    """Удаляет событие (Google Calendar отключён)."""
    return _DISABLED


@tool
def calendar_move(
    title: str,
    new_date_text: str,
    new_time_text: str,
    old_date_text: str = "",
) -> str:
    """Переносит событие (Google Calendar отключён)."""
    return _DISABLED


@tool
def calendar_rename(title: str, new_title: str, date_text: str = "") -> str:
    """Переименовывает событие (Google Calendar отключён)."""
    return _DISABLED


@tool
def calendar_change_duration(
    title: str,
    duration_minutes: int,
    date_text: str = "",
) -> str:
    """Изменяет длительность события (Google Calendar отключён)."""
    return _DISABLED


# Список всех calendar tools (стабы) для совместимости с calendar_agent
CALENDAR_TOOLS = [
    calendar_list_upcoming,
    calendar_list_day,
    calendar_search,
    calendar_create,
    calendar_delete,
    calendar_move,
    calendar_rename,
    calendar_change_duration,
]
