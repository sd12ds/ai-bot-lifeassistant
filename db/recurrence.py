"""
Утилиты для работы с повторяющимися задачами/событиями.
Парсинг естественного языка → RRULE, генерация экземпляров (occurrence).
Используем dateutil.rrule для раскрытия RRULE строк.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional

from dateutil.rrule import rrulestr, rrule, DAILY, WEEKLY, MONTHLY, YEARLY, MO, TU, WE, TH, FR, SA, SU


# ── Маппинг русских паттернов → RRULE ────────────────────────────────────────

# Дни недели: русские сокращения → dateutil константы
_RU_DAYS = {
    "пн": "MO", "понедельник": "MO",
    "вт": "TU", "вторник": "TU",
    "ср": "WE", "среда": "WE", "среду": "WE",
    "чт": "TH", "четверг": "TH",
    "пт": "FR", "пятница": "FR", "пятницу": "FR",
    "сб": "SA", "суббота": "SA", "субботу": "SA",
    "вс": "SU", "воскресенье": "SU",
}


def parse_recurrence_nl(text: str) -> str:
    """Парсит русскоязычное описание повторения → RRULE строку.

    Поддерживает:
      «каждый день»          → FREQ=DAILY
      «по будням»            → FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR
      «по выходным»          → FREQ=WEEKLY;BYDAY=SA,SU
      «каждую неделю»        → FREQ=WEEKLY
      «еженедельно»          → FREQ=WEEKLY
      «каждый пн, ср, пт»   → FREQ=WEEKLY;BYDAY=MO,WE,FR
      «ежемесячно»           → FREQ=MONTHLY
      «каждый месяц 15»      → FREQ=MONTHLY;BYMONTHDAY=15
      «ежегодно»             → FREQ=YEARLY
      «N раз»                → добавляет COUNT=N
    """
    t = text.lower().strip()

    # Извлекаем COUNT если указано количество раз
    count = None
    count_m = re.search(r"(\d+)\s*раз", t)
    if count_m:
        count = int(count_m.group(1))
        t = t[:count_m.start()] + t[count_m.end():]

    rule_parts = []

    # Ежедневно
    if re.search(r"кажд\w*\s+день|ежедневно|каждодневно", t):
        rule_parts.append("FREQ=DAILY")

    # По будням
    elif re.search(r"будн[яи]|рабоч\w+\s+дн", t):
        rule_parts.append("FREQ=WEEKLY")
        rule_parts.append("BYDAY=MO,TU,WE,TH,FR")

    # По выходным
    elif re.search(r"выходн", t):
        rule_parts.append("FREQ=WEEKLY")
        rule_parts.append("BYDAY=SA,SU")

    # Конкретные дни недели: «каждый пн, ср, пт» или «по пн, ср»
    elif re.search(r"кажд\w+|по\s+", t):
        # Ищем перечисление дней
        found_days = []
        for ru_day, en_day in _RU_DAYS.items():
            if ru_day in t and en_day not in found_days:
                found_days.append(en_day)
        if found_days:
            rule_parts.append("FREQ=WEEKLY")
            rule_parts.append(f"BYDAY={','.join(found_days)}")
        elif re.search(r"кажд\w*\s*(недел|семидн)|еженедельно", t):
            rule_parts.append("FREQ=WEEKLY")
        elif re.search(r"кажд\w*\s*месяц|ежемесячно", t):
            rule_parts.append("FREQ=MONTHLY")
            # Ищем число месяца
            day_m = re.search(r"(\d{1,2})\s*(?:числ|го)?", t)
            if day_m:
                rule_parts.append(f"BYMONTHDAY={day_m.group(1)}")
        elif re.search(r"кажд\w*\s*год|ежегодно", t):
            rule_parts.append("FREQ=YEARLY")
        else:
            # Фолбэк: «каждый» без конкретики → ежедневно
            rule_parts.append("FREQ=DAILY")

    # Еженедельно (без «кажд»)
    elif re.search(r"еженедельно|раз в недел", t):
        rule_parts.append("FREQ=WEEKLY")

    # Ежемесячно (без «кажд»)
    elif re.search(r"ежемесячно|раз в месяц", t):
        rule_parts.append("FREQ=MONTHLY")
        day_m = re.search(r"(\d{1,2})\s*(?:числ|го)?", t)
        if day_m:
            rule_parts.append(f"BYMONTHDAY={day_m.group(1)}")

    # Ежегодно (без «кажд»)
    elif re.search(r"ежегодно|раз в год", t):
        rule_parts.append("FREQ=YEARLY")

    # Фолбэк — пробуем чистые дни недели
    else:
        found_days = []
        for ru_day, en_day in _RU_DAYS.items():
            if ru_day in t and en_day not in found_days:
                found_days.append(en_day)
        if found_days:
            rule_parts.append("FREQ=WEEKLY")
            rule_parts.append(f"BYDAY={','.join(found_days)}")
        else:
            # Не удалось распознать — возвращаем пусто
            return ""

    # Добавляем COUNT если указано
    if count:
        rule_parts.append(f"COUNT={count}")

    return ";".join(rule_parts)


def expand_occurrences(
    rrule_str: str,
    dtstart: datetime,
    horizon_days: int = 30,
    existing_dates: set[str] | None = None,
) -> list[datetime]:
    """Генерирует даты экземпляров по RRULE строке.

    Args:
        rrule_str: RRULE строка (без префикса RRULE:), например 'FREQ=DAILY'
        dtstart: дата начала
        horizon_days: горизонт генерации в днях
        existing_dates: множество уже существующих дат (ISO без TZ) для исключения дубликатов

    Returns:
        Список datetime для новых экземпляров.
    """
    if not rrule_str:
        return []

    existing = existing_dates or set()
    until = dtstart + timedelta(days=horizon_days)

    # dateutil.rrulestr ожидает формат "RRULE:FREQ=..."
    full_rule = f"RRULE:{rrule_str}"
    try:
        rule = rrulestr(full_rule, dtstart=dtstart)
    except (ValueError, KeyError):
        return []

    # Генерируем даты в диапазоне [dtstart, until]
    results = []
    for dt in rule:
        if dt > until:
            break
        # Не пропускаем dtstart — шаблон скрыт из списков,
        # для первой даты нужен отдельный экземпляр
        # Пропускаем уже существующие
        dt_key = dt.strftime("%Y-%m-%d %H:%M")
        if dt_key in existing:
            continue
        results.append(dt)

    return results


def generate_occurrence_dicts(
    template: dict,
    horizon_days: int = 30,
    existing_dates: set[str] | None = None,
) -> list[dict]:
    """Создаёт словари для экземпляров на основе шаблона.

    Каждый экземпляр наследует: title, description, event_type, priority,
    calendar_id, is_all_day. Получает свои due_datetime/start_at/end_at.

    Args:
        template: словарь задачи-шаблона (из _task_to_dict)
        horizon_days: горизонт генерации
        existing_dates: множество дат уже существующих экземпляров

    Returns:
        Список словарей для создания новых Task.
    """
    rrule_str = template.get("recurrence_rule")
    if not rrule_str:
        return []

    # Определяем базовую дату: start_at (для событий) или due_datetime (для задач)
    base_iso = template.get("start_at") or template.get("due_datetime")
    if not base_iso:
        return []

    try:
        dtstart = datetime.fromisoformat(base_iso)
    except (ValueError, TypeError):
        return []

    # Вычисляем длительность события (если есть end_at)
    duration = None
    if template.get("start_at") and template.get("end_at"):
        try:
            start_dt = datetime.fromisoformat(template["start_at"])
            end_dt = datetime.fromisoformat(template["end_at"])
            duration = end_dt - start_dt
        except (ValueError, TypeError):
            pass

    # Генерируем даты экземпляров
    dates = expand_occurrences(rrule_str, dtstart, horizon_days, existing_dates)

    occurrences = []
    for occ_dt in dates:
        occ = {
            "user_id": template["user_id"],
            "title": template["title"],
            "description": template.get("description", ""),
            "event_type": template.get("event_type", "task"),
            "priority": template.get("priority", 2),
            "calendar_id": template.get("calendar_id"),
            "is_all_day": template.get("is_all_day", False),
            "parent_task_id": template["id"],
            "recurrence_rule": None,  # Экземпляры не имеют своего RRULE
        }
        # Расставляем даты в зависимости от типа
        if template.get("event_type") == "event" or template.get("start_at"):
            occ["start_at"] = occ_dt.isoformat()
            if duration:
                occ["end_at"] = (occ_dt + duration).isoformat()
            occ["due_datetime"] = None
        else:
            occ["due_datetime"] = occ_dt.isoformat()
            occ["start_at"] = None
            occ["end_at"] = None

        occurrences.append(occ)

    return occurrences
