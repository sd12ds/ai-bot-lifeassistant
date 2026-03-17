"""
LangChain @tool для управления задачами и напоминаниями.
Хранилище — SQLite через db/storage.py.
user_id передаётся через замыкание при создании инструментов.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo

import dateparser
from langchain.tools import tool

from config import DEFAULT_TIMEZONE_STR, DEFAULT_TZ
from db import storage
from db.recurrence import parse_recurrence_nl
from db import reminders as rdb


def _parse_remind_before(text: str) -> timedelta | None:
    """Парсит 'за X' в timedelta.

    Принимает: '5 минут', '30 мин', '1 час', '2 часа', '1 день' и т.п.
    """
    import re
    if not text:
        return None
    t = text.lower().strip()
    # Убираем предлог 'за' если есть
    t = re.sub(r'^\s*за\s+', '', t)
    m = re.match(r'^(\d+)\s*(мин|минут|час|часа|часов|день|дня|дней)', t)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    if unit.startswith('мин'):
        return timedelta(minutes=n)
    if unit.startswith('час'):
        return timedelta(hours=n)
    if unit.startswith('д'):
        return timedelta(days=n)
    return None


def _parse_period(period_text: str) -> tuple[str, str, str]:
    """
    Парсит текстовое описание периода и возвращает (label, date_from_iso, date_to_iso).
    Примеры: «сегодня», «завтра», «на этой неделе», «на неделю», «в марте».
    """
    now = datetime.now(DEFAULT_TZ)
    text = period_text.lower().strip()

    if any(w in text for w in ["сегодня", "today"]):
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        return "сегодня", day_start.isoformat(), day_end.isoformat()

    if any(w in text for w in ["завтра", "tomorrow"]):
        day_start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        return "завтра", day_start.isoformat(), day_end.isoformat()

    if any(w in text for w in ["недел", "week", "7 дн"]):
        week_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)
        return "на неделю", week_start.isoformat(), week_end.isoformat()

    if any(w in text for w in ["месяц", "month", "30 дн"]):
        month_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_end = month_start + timedelta(days=30)
        return "на месяц", month_start.isoformat(), month_end.isoformat()

    # Пытаемся распарсить произвольную дату
    parsed = dateparser.parse(
        period_text,
        languages=["ru", "uk"],
        settings={"TIMEZONE": DEFAULT_TIMEZONE_STR, "RETURN_AS_TIMEZONE_AWARE": True},
    )
    if parsed:
        day_start = parsed.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        return parsed.strftime("%d.%m.%Y"), day_start.isoformat(), day_end.isoformat()

    # Дефолт — вся неделя
    week_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)
    return "на неделю", week_start.isoformat(), week_end.isoformat()


def _format_tasks(tasks: list[dict]) -> str:
    """Форматирует список задач для отображения пользователю."""
    lines = []
    for t in tasks:
        status = "✅" if t["is_done"] else "⬜"
        time_info = ""
        # Событие с start_at
        if t.get("start_at"):
            try:
                s = datetime.fromisoformat(t["start_at"]).astimezone(DEFAULT_TZ)
                time_info = f" | {s.strftime('%d.%m %H:%M')}"
                # Если есть end_at — показываем диапазон
                if t.get("end_at"):
                    e = datetime.fromisoformat(t["end_at"]).astimezone(DEFAULT_TZ)
                    time_info = f" | {s.strftime('%d.%m %H:%M')}–{e.strftime('%H:%M')}"
            except Exception:
                time_info = f" | {t['start_at']}"
        # Задача с дедлайном
        elif t.get("due_datetime"):
            try:
                dt = datetime.fromisoformat(t["due_datetime"]).astimezone(DEFAULT_TZ)
                time_info = f" | до {dt.strftime('%d.%m %H:%M')}"
            except Exception:
                time_info = f" | до {t['due_datetime']}"
        # Иконка типа
        icon = "📅" if t.get("event_type") == "event" else ""
        desc = f" — {t['description']}" if t.get("description") else ""
        lines.append(f"{status} {icon}[{t['id']}] {t['title']}{time_info}{desc}")
    return "\n".join(lines)


def make_reminder_tools(user_id: int) -> list:
    """Создаёт reminder tools, привязанные к конкретному user_id."""

    @tool
    async def parse_due_nl(text: str) -> str:
        """
        Парсит естественное русскоязычное описание срока (например: "завтра в 13:00",
        "через 2 часа", "в пятницу в 9") и возвращает ISO 8601 с таймзоной пользователя.

        Используй ЭТОТ инструмент всегда, когда пользователь задаёт срок словами.
        Не пытайся вычислять дату самостоятельно — сначала вызови parse_due_nl, затем
        передай результат в аргументе due инструмента task_add.

        Args:
            text: исходный пользовательский текст с описанием срока.

        Returns:
            Строка ISO 8601 (например, "2026-03-08T13:00:00+03:00") или пустая строка,
            если распознать срок не удалось.
        """
        # Берём таймзону пользователя из настроек
        us = await rdb.get_user_settings(user_id)
        tz_name = us.get("timezone", DEFAULT_TIMEZONE_STR) or DEFAULT_TIMEZONE_STR
        tz = ZoneInfo(tz_name)

        # Базовое время для относительных выражений — текущее в TZ пользователя
        now = datetime.now(tz)

        # -- Нормализация текста: словари и вспомогательные паттерны -----------
        _RU_NUMS = {
            "один": 1, "одну": 1, "одного": 1, "два": 2, "две": 2, "двух": 2,
            "три": 3, "трёх": 3, "четыре": 4, "четырёх": 4,
            "пять": 5, "шесть": 6, "семь": 7, "восемь": 8,
            "девять": 9, "десять": 10, "одиннадцать": 11, "двенадцать": 12,
            "тринадцать": 13, "четырнадцать": 14, "пятнадцать": 15,
            "шестнадцать": 16, "семнадцать": 17, "восемнадцать": 18,
            "девятнадцать": 19, "двадцать": 20, "тридцать": 30,
            "сорок": 40, "пятьдесят": 50,
        }
        _NUMS_PAT = "|".join(sorted(_RU_NUMS, key=len, reverse=True))
        _MONTH_NAMES = {
            1: "января", 2: "февраля", 3: "марта", 4: "апреля",
            5: "мая", 6: "июня", 7: "июля", 8: "августа",
            9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
        }
        _WD_INNER = (
            r"понедельник[еу]?|вторник[ае]?|среду?|четверг[еу]?"
            r"|пятниц[ыеу]?|суббот[ыеу]?|воскресень[еюя]?"
        )
        _MONTHS_RE = (
            r"(?:января|февраля|марта|апреля|мая|июня|июля"
            r"|августа|сентября|октября|ноября|декабря)"
        )
        # Словарь минут для составных времён ("час тридцать", "два двадцать пять")
        _MIN_WORDS = {
            "ноль ноль": 0, "ноль": 0, "нуль": 0,
            "пять": 5, "десять": 10, "пятнадцать": 15,
            "двадцать пять": 25, "двадцать": 20,
            "тридцать пять": 35, "тридцать": 30,
            "сорок пять": 45, "сорок": 40,
            "пятьдесят пять": 55, "пятьдесят": 50,
        }
        _MIN_PAT = "|".join(sorted(_MIN_WORDS, key=len, reverse=True))


        norm = text.lower().strip()

        # -- Разговорные замены -----------------------------------------------
        for _old, _new in [
            ("в час дня",        "в 13:00"),
            ("на час дня",       "в 13:00"),
            ("в час ночи",       "в 01:00"),  # 'час ночи' — всегда 01:00
            ("на час ночи",      "в 01:00"),
            ("в час утра",       "в 01:00"),  # час утра = 01:00
            ("в полдень",        "в 12:00"),
            ("в полночь",        "в 00:00"),
            ("полчаса",          "30 минут"),
            ("пол часа",         "30 минут"),
            ("через час",        "через 1 час"),
            ("через полчаса",    "через 30 минут"),
            ("сегодняшний день", "сегодня"),
            ("сегодняшнего дня", "сегодня"),
            ("через полтора часа", "через 90 минут"),
            ("полтора часа",       "90 минут"),
            ("до полудня",         "до 12:00"),
            ("в ноль часов",       "в 00:00"),
            ("в нуль часов",       "в 00:00"),
        ]:
            norm = norm.replace(_old, _new)

        # -- "через N (слово) часов/минут" -> "через N (цифра) часов/минут" ---
        def _через(m):
            n = _RU_NUMS.get(m.group(1))
            return f"через {n} {m.group(2)}" if n else m.group(0)
        norm = re.sub(
            rf"\bчерез\s+({_NUMS_PAT})\s+(час[аов]?|минут[аы]?|мин)\b",
            _через, norm,
        )

        # -- "ЧЧ ММ утра/вечера/дня/ночи" -> "в ЧЧ:ММ" (до _tod, чтоб не съело минуты) --
        # -- "[в/на] ЧАСОВОЕ_СЛОВО МИНУТ_СЛОВО/ЦИФРЫ" -> "в HH:MM" -----------
        # Обрабатывает "час тридцать"->13:30, "два двадцать пять"->02:25 и т.п.
        def _ctime(m):
            h_w = m.group(2).strip()
            m_w = m.group(3).strip()
            # "час" без числа = 13 (час дня)
            h = 13 if h_w == "час" else _RU_NUMS.get(h_w, 0)
            if m_w.isdigit():
                mi = int(m_w)
            else:
                mi = _MIN_WORDS.get(m_w, -1)
            if not (0 < h <= 23) or not (0 <= mi <= 59):
                return m.group(0)
            return f"в {h:02d}:{mi:02d}"
        norm = re.sub(
            rf"\b(в|на)\s+(час|{_NUMS_PAT})\s+({_MIN_PAT}|\d{{1,2}})\b(?![:\d])",
            _ctime, norm,
        )

        def _hm_tod(m):
            h, mi, suf = int(m.group(1)), int(m.group(2)), m.group(3)
            if "вечер" in suf:
                h = h + 12 if h <= 11 else h
            elif suf == "ночи":
                # "3 ночи" = 03:00, "12 ночи" = 00:00 (не добавляем 12!)
                h = 0 if h == 12 else h
            elif suf in ("дня", "дне"):
                h = h + 12 if 1 <= h < 12 else h
            return f"в {h:02d}:{mi:02d}"
        norm = re.sub(
            r"(?<![:\d])\b(?:(?:в|на)\s+)?(\d{1,2})\s+(\d{2})\s+(утра|вечера|дня|ночи)\b",
            _hm_tod, norm,
        )

        # -- "[в/на] N утра/вечера/дня/ночи" -> "в HH:00" --------------------
        def _tod(m):
            h, suf = int(m.group(1)), m.group(2)
            if "вечер" in suf:
                h = h + 12 if h <= 11 else h
            elif suf == "ночи":
                # "3 ночи" = 03:00, "12 ночи" = 00:00 (не +12!)
                h = 0 if h == 12 else h
            elif suf in ("дня", "дне"):
                h = h + 12 if 1 <= h < 12 else h
            return f"в {h:02d}:00"
        # (?<![:\d]) — не захватывать минуты из "08:30 утра" (иначе "30" захватит как час)
        norm = re.sub(
            r"(?<![:\d])\b(?:(?:в|на)\s+)?(\d{1,2})\s+(утра|вечера|дня|ночи)\b", _tod, norm
        )

        # -- "[в/около/после/с] N часов/часа" -> "в N:00" --------------------
        norm = re.sub(
            r"\b(?:в|около|после|с)\s+(\d{1,2})\s+час[аов]{0,2}\b",
            lambda m: f"в {int(m.group(1)):02d}:00", norm,
        )

        # -- "в (слово-число) [часов/утра/вечера/...]" -> "в HH:00" ----------
        def _word_hour(m):
            n = _RU_NUMS.get(m.group(1))
            if not n:
                return m.group(0)
            suf = (m.group(2) or "").strip()
            if "вечер" in suf:
                n = n + 12 if n <= 11 else n
            elif suf == "ночи":
                # "три ночи" = 03:00, "двенадцать ночи" = 00:00 (не +12!)
                n = 0 if n == 12 else n
            elif suf in ("дня", "дне"):
                n = n + 12 if 1 <= n < 12 else n
            return f"в {n:02d}:00"
        norm = re.sub(
            rf"\bв\s+({_NUMS_PAT})\s*(?:час[аов]*)?\s*(утра|вечера|дня|ночи|часов|часа|час)?\b",
            _word_hour, norm,
        )

        # -- "HH.MM" -> "HH:MM" только если MM > 12 или "00" (иначе DD.MM) ---
        norm = re.sub(
            r"\b(\d{1,2})\.(\d{2})\b(?!\.\d)",
            lambda m: f"{m.group(1)}:{m.group(2)}"
                if (int(m.group(2)) > 12 or m.group(2) == "00") else m.group(0),
            norm,
        )

        # -- "в/на/к ЧЧ ММ" (пробел) -> "в ЧЧ:ММ" ---------------------------
        norm = re.sub(
            r"\b(в|на|к|до)\s+(\d{1,2})\s+(\d{2})\b",
            lambda m: f"в {m.group(2)}:{m.group(3)}" if int(m.group(3)) <= 59 else m.group(0),
            norm,
        )

        # -- "ЧЧ ММ" (без предлога) -> "в ЧЧ:ММ" если похоже на время ---------
        # Например: "23 30" -> "в 23:30"; исключаем «15 марта» и т.п.
        norm = re.sub(
            r"(?<![/.:,\d])\b((?:2[0-3]|[01]?\d))\s+((?:[0-5]\d))\b"
            r"(?![/.:,\d])(?!\s*(?:январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр))",
            lambda m: f"в {m.group(1)}:{m.group(2)}",
            norm,
        )

        # -- "около ЧЧ" (без слова часов) -> "в ЧЧ:00" -----------------------
        norm = re.sub(
            r"\bоколо\s+(\d{1,2})\b(?![:\d])",
            lambda m: f"в {int(m.group(1)):02d}:00", norm,
        )

        # -- "на/к сегодня/завтра/..." -> "сегодня/завтра/..." ----------------
        norm = re.sub(
            r"\b(?:на|к)\s+(сегодня|завтра|послезавтра|вчера)\b", r"\1", norm
        )

        # -- "на (день недели)" -> "в (день недели)" --------------------------
        norm = re.sub(rf"\b(?:на|к)\s+({_WD_INNER})\b", r"в \1", norm)
        # Нормализуем дательный падеж дней недели → винительный (для dateparser)
        for _dat, _acc in [
            ("в пятнице", "в пятницу"), ("в среде", "в среду"),
            ("в субботе", "в субботу"), ("в понедельнике", "в понедельник"),
            ("в вторнике", "в вторник"), ("в четверге", "в четверг"),
            ("в воскресенье", "в воскресенье"),  # одинаково
        ]:
            norm = norm.replace(_dat, _acc)

        # -- "на HH:MM" -> "в HH:MM" ------------------------------------------
        norm = re.sub(r"\bна\s+(\d{1,2}:\d{2})\b", r"в \1", norm)

        # -- Убираем пунктуацию между словом и цифрой: "завтра. 8" -> "завтра 8"
        norm = re.sub(r"([а-яё])[:.,]\s+(\d)", r"\1 \2", norm)

        # -- "в/на HH" (одиночный час без минут) -> "в HH:00" ----------------
        norm = re.sub(
            r"\b(?:в|на|до)\s+(\d{1,2})\b(?![:\d./])(?!\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря))",
            lambda m: f"в {int(m.group(1)):02d}:00" if int(m.group(1)) <= 23 else m.group(0),
            norm,
        )

        # -- "дата_слово ЧЧ ММ" без предлога -> "дата в ЧЧ:ММ" ---------------
        norm = re.sub(
            r"\b(сегодня|завтра|послезавтра|вчера)\s+(\d{1,2})\s+(\d{2})\b",
            lambda m: f"{m.group(1)} в {m.group(2)}:{m.group(3)}"
                if int(m.group(3)) <= 59 else m.group(0),
            norm,
        )

        # -- "ЧЧ ММ сегодня/завтра" (без двоеточия, обратный порядок) --------
        norm = re.sub(
            r"\b(\d{1,2})\s+(\d{2})\s+(сегодня|завтра|послезавтра|вчера)\b",
            lambda m: f"{m.group(3)} в {m.group(1)}:{m.group(2)}"
                if int(m.group(2)) <= 59 else m.group(0),
            norm,
        )

        # -- "HH:MM сегодня/завтра" -> "сегодня/завтра в HH:MM" --------------
        norm = re.sub(
            r"(?:в\s+)?(\d{1,2}:\d{2})\s+(сегодня|завтра|послезавтра|вчера)\b",
            r"\2 в \1", norm,
        )

        # -- Умный комбинатор: извлекаем минимальный datetime-фрагмент --------
        _day_m  = re.search(r"\b(сегодня|завтра|послезавтра|вчера)\b", norm)
        _time_m = re.search(r"\bв\s+\d{1,2}:\d{2}", norm)
        _bare_t = re.search(r"\b(\d{1,2}:\d{2})\b", norm)
        _week_m = re.search(rf"\b(?:в\s+)?({_WD_INNER})\b", norm)
        _nm_m   = re.search(rf"\b(\d{{1,2}}\s+{_MONTHS_RE})\b", norm)
        _dot_m  = re.search(r"\b(\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?)\b", norm)
        _rel_m  = re.search(
            r"\bчерез\s+\d+\s+(?:час[аов]?|минут[аы]?|мин)\b", norm
        )

        # Эффективное время: "в HH:MM" или добавляем "в" к bare HH:MM
        _eff_t = _time_m.group(0) if _time_m else (
            f"в {_bare_t.group(1)}" if _bare_t else None
        )

        def _dot_to_month(dot_str: str) -> str:
            # Конвертирует "15.03" -> "15 марта" для надёжного парсинга
            parts = dot_str.replace("/", ".").split(".")
            if len(parts) >= 2:
                try:
                    mn = int(parts[1])
                    if 1 <= mn <= 12:
                        return f"{parts[0]} {_MONTH_NAMES[mn]}"
                except (ValueError, KeyError):
                    pass
            return dot_str

        parse_input = norm
        if _day_m and _eff_t:
            parse_input = f"{_day_m.group(1)} {_eff_t}"
        elif _week_m and _eff_t:
            parse_input = f"в {_week_m.group(1)} {_eff_t}"
        elif _nm_m and _eff_t:
            parse_input = f"{_nm_m.group(1)} {_eff_t}"
        elif _dot_m and _eff_t:
            parse_input = f"{_dot_to_month(_dot_m.group(1))} {_eff_t}"
        elif _rel_m:
            parse_input = _rel_m.group(0)
        elif _day_m:
            parse_input = _day_m.group(1)
        elif _week_m:
            parse_input = f"в {_week_m.group(1)}"
        elif _nm_m:
            parse_input = _nm_m.group(1)
        elif _dot_m:
            parse_input = _dot_to_month(_dot_m.group(1))
        elif _eff_t:
            # dateparser не умеет парсить чистое "ЧЧ:ММ" без контекста дня — делаем вручную
            time_str = re.sub(r"^в\s+", "", _eff_t).strip()
            _tm = re.match(r"^(\d{1,2}):(\d{2})$", time_str)
            if _tm:
                _h, _mi = int(_tm.group(1)), int(_tm.group(2))
                candidate = now.replace(hour=_h, minute=_mi, second=0, microsecond=0)
                # Если время уже прошло — переносим на завтра
                if candidate <= now:
                    candidate = candidate + timedelta(days=1)
                return candidate.isoformat()
            parse_input = time_str

        dt = dateparser.parse(
            parse_input,
            languages=["ru", "uk", "en"],
            settings={
                "TIMEZONE": tz_name,
                "RETURN_AS_TIMEZONE_AWARE": True,
                "RELATIVE_BASE": now,
                "PREFER_DATES_FROM": "future",
                "DATE_ORDER": "DMY",
            },
        )
        if not dt:
            return ""
        # Если пользователь не указал время явно — подставляем дефолт 13:00,
        # чтобы задача попала в выборку «Завтра» и имела предсказуемый дедлайн.
        has_hhmm = bool(re.search(r"\b\d{1,2}[:.]\d{2}\b", norm))
        has_v_hh = bool(re.search(r"\bв\s*\d{1,2}\b", norm))
        has_tod = any(w in norm for w in ("утра", "вечера", "ночи", "полдень", "полуночь"))
        has_rel_hours = bool(re.search(r"\bчерез\s+\d+\s*(час|часа|часов|мин|минут[ыу]?)\b", norm))
        if not (has_hhmm or has_v_hh or has_tod or has_rel_hours):
            dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
        # Приводим к TZ пользователя (dateparser уже вернёт aware)
        try:
            dt = dt.astimezone(tz)
        except Exception:
            pass
        return dt.isoformat()

    @tool
    async def task_add(
        title: str,
        description: str = "",
        due: str = "",
        due_text: str = "",
        start_text: str = "",
        duration_minutes: int = 60,
        remind_before: str = "",
        repeat: str = "",
    ) -> str:
        """
        Добавляет задачу ИЛИ событие в личный список.

        Задача (task) — действие с дедлайном. Используй due/due_text.
        Событие (event) — временной слот. Используй start_text.

        Если пользователь говорит «встреча», «созвон», «приём», «событие»,
        «занятие», «тренировка» и указывает ВРЕМЯ НАЧАЛА — это событие,
        передай start_text.

        Если пользователь говорит «сделать ДО», «дедлайн», «нужно успеть» — задача,
        передай due/due_text.

        Args:
            title: Название (обязательно).
            description: Подробное описание (необязательно).
            due: Дедлайн ISO 8601. Пустая строка если не указан.
            due_text: Срок в свободной форме ('завтра в 15:00', 'через 2 часа').
            start_text: Время начала события в свободной форме
                ('завтра в 14:00', 'в пятницу в 10'). Если передан —
                создаётся СОБЫТИЕ (event), а не задача.
            duration_minutes: Продолжительность события в минутах (по умолчанию 60).
                Используется только вместе с start_text.
            remind_before: Время до начала для напоминания ('5 минут', '1 час').
            repeat: Периодичность повторения в свободной форме.
                Примеры: 'каждый день', 'по будням', 'еженедельно',
                'каждый пн, ср, пт', 'ежемесячно 15 числа'.
                Если передан — создаётся повторяющаяся задача/событие.
        """
        # Определяем тип: если start_text — событие, иначе задача
        is_event = bool(start_text)

        # Парсим время начала для событий
        start_at_iso = ""
        end_at_iso = ""
        if is_event and start_text:
            start_at_iso = await parse_due_nl.ainvoke({"text": start_text})
            if start_at_iso:
                # Вычисляем end_at на основе duration_minutes
                try:
                    s_dt = datetime.fromisoformat(start_at_iso)
                    e_dt = s_dt + timedelta(minutes=duration_minutes)
                    end_at_iso = e_dt.isoformat()
                except Exception:
                    pass

        # Fallback: если due пуст, но due_text задан — парсим дату автоматически
        if not due and due_text:
            due = await parse_due_nl.ainvoke({"text": due_text})

        # Парсим повторение если указано
        rrule_str = parse_recurrence_nl(repeat) if repeat else None

        task_id = await storage.add_task(
            user_id=user_id,
            title=title,
            description=description,
            due_datetime=due or None,
            start_at=start_at_iso or None,
            end_at=end_at_iso or None,
            event_type="event" if is_event else "task",
            recurrence_rule=rrule_str,
        )
        # Создаём напоминание: для событий — по start_at, для задач — по due
        anchor_iso = start_at_iso if is_event else due
        if anchor_iso:
            try:
                from datetime import datetime, timedelta, timezone
                anchor_dt = datetime.fromisoformat(anchor_iso)
                us = await rdb.get_user_settings(user_id)

                # Определяем offset: индивидуальный remind_before имеет приоритет
                individual_delta = _parse_remind_before(remind_before)
                if individual_delta is not None:
                    remind_dt = anchor_dt - individual_delta
                else:
                    offset_min = int(us.get("notification_offset_min", 15))
                    remind_dt = anchor_dt - timedelta(minutes=offset_min)

                remind_dt_utc = (remind_dt.astimezone(timezone.utc)
                                 if remind_dt.tzinfo else remind_dt.replace(tzinfo=timezone.utc))
                now_utc = datetime.now(timezone.utc)
                safe_remind_at = remind_dt_utc if remind_dt_utc > now_utc else now_utc
                await rdb.add_reminder(
                    user_id=user_id,
                    entity_type="task",
                    entity_id=task_id,
                    remind_at=safe_remind_at.isoformat(),
                )
                # Синхронизируем task.remind_at — чтобы мини-апп видел напоминание
                # и не удалял его при редактировании задачи (иначе editTask.remind_at=null
                # → форма выставляет preset=-1 (отключено) → PATCH отправляет remind_at:null
                # → _sync_reminder удаляет reminder из БД)
                await storage.update_task_fields(
                    task_id=task_id,
                    user_id=user_id,
                    remind_at=safe_remind_at.isoformat(),
                )
                # Для повторяющихся задач — создаём reminders для всех экземпляров.
                # Экземпляры уже созданы в storage.add_task() без remind_at/reminders,
                # поэтому проставляем их здесь, зная offset.
                if rrule_str:
                    offset_sec = int(
                        (anchor_dt - safe_remind_at).total_seconds()
                    )
                    if offset_sec > 0:
                        await storage.create_occurrence_reminders(
                            template_id=task_id,
                            user_id=user_id,
                            offset_seconds=offset_sec,
                        )
            except Exception:
                pass  # Не ломаем основной флоу если reminder не создался
        # Формируем ответ
        repeat_str = f" 🔄 {repeat}" if repeat else ""
        if is_event:
            time_str = f" (начало: {start_at_iso})" if start_at_iso else ""
            return f"📅 Событие добавлено: [{task_id}] {title}{time_str}{repeat_str}"
        due_str = f" (дедлайн: {due})" if due else ""
        return f"✅ Задача добавлена: [{task_id}] {title}{due_str}{repeat_str}"

    @tool
    async def task_list(include_done: bool = False) -> str:
        """
        Показывает ВСЕ задачи из личного списка дел без фильтрации по дате.
        Используй когда пользователь говорит «покажи все задачи», «весь список дел».

        Args:
            include_done: True — показать в том числе выполненные задачи.
        """
        tasks = await storage.list_tasks(user_id=user_id, include_done=include_done)
        if not tasks:
            return "Список задач пуст. Добавь задачи командой «добавь задачу [название]»."
        header = f"Все задачи ({len(tasks)}):"
        return header + "\n" + _format_tasks(tasks)

    @tool
    async def task_list_period(period: str = "на неделю", include_done: bool = False) -> str:
        """
        Показывает задачи за указанный период: сегодня, завтра, на неделю, на месяц.
        Используй когда пользователь говорит «задачи на неделю», «что нужно сделать сегодня»,
        «задачи на завтра», «покажи задачи на этой неделе».

        Args:
            period: Период на русском: «сегодня», «завтра», «на неделю», «на месяц» или конкретная дата.
            include_done: True — показать в том числе выполненные задачи.
        """
        label, date_from, date_to = _parse_period(period)
        tasks = await storage.list_tasks_by_period(
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
            include_done=include_done,
        )
        if not tasks:
            return (
                f"Задач {label} нет.\n"
                f"Добавь задачу: «добавь задачу [название] до [дата]»"
            )
        header = f"Задачи {label} ({len(tasks)}):"
        return header + "\n" + _format_tasks(tasks)

    @tool
    async def task_done(task_id: int) -> str:
        """
        Отмечает задачу как выполненную.
        Используй когда пользователь говорит «выполнил задачу», «сделал», «отметь как готово».

        Args:
            task_id: ID задачи (число в квадратных скобках из списка).
        """
        ok = await storage.complete_task(task_id=task_id, user_id=user_id)
        return f"✅ Задача [{task_id}] выполнена." if ok else f"Задача [{task_id}] не найдена."

    @tool
    async def task_delete(task_id: int) -> str:
        """
        Удаляет задачу из списка.
        Используй когда пользователь говорит «удали задачу», «убери из списка».

        Args:
            task_id: ID задачи (число в квадратных скобках из списка).
        """
        ok = await storage.delete_task(task_id=task_id, user_id=user_id)
        return f"🗑 Задача [{task_id}] удалена." if ok else f"Задача [{task_id}] не найдена."

    @tool
    async def task_skip(task_id: int) -> str:
        """
        Пропускает (удаляет) конкретный экземпляр повторяющейся задачи.
        Используй когда пользователь говорит «пропустить», «скипнуть»,
        «не буду делать сегодня эту повторяющуюся задачу».

        Args:
            task_id: ID экземпляра повторяющейся задачи.
        """
        ok = await storage.skip_occurrence(task_id=task_id, user_id=user_id)
        if ok:
            return f"⏭ Экземпляр [{task_id}] пропущен."
        return f"Запись [{task_id}] не найдена или не является экземпляром повторяющейся задачи."

    @tool
    async def event_list(period: str = "на неделю", include_done: bool = False) -> str:
        """
        Показывает ВСЕ записи календаря (задачи + события) за указанный период.
        Используй когда пользователь спрашивает «что у меня в календаре»,
        «какие встречи», «расписание на неделю», «планы на завтра».

        Args:
            period: Период: «сегодня», «завтра», «на неделю», «на месяц».
            include_done: True — включить выполненные.
        """
        label, date_from, date_to = _parse_period(period)
        items = await storage.list_calendar_items(
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
            include_done=include_done,
        )
        if not items:
            return f"Календарь {label} пуст."
        header = f"📅 Календарь {label} ({len(items)}):"
        return header + "\n" + _format_tasks(items)

    @tool
    async def event_move(task_id: int, new_start_text: str) -> str:
        """
        Переносит событие или задачу на новое время.
        Используй когда пользователь говорит «перенеси встречу»,
        «сдвинь задачу», «перенеси на завтра».

        Args:
            task_id: ID записи (число в квадратных скобках из списка).
            new_start_text: Новое время в свободной форме ('завтра в 14:00').
        """
        new_iso = await parse_due_nl.ainvoke({"text": new_start_text})
        if not new_iso:
            return f"Не удалось распознать дату: {new_start_text}"
        # Получаем текущую запись, чтобы понять тип
        task = await storage.get_task(task_id=task_id, user_id=user_id)
        if not task:
            return f"Запись [{task_id}] не найдена."
        fields = {}
        if task.get("event_type") == "event" or task.get("start_at"):
            # Событие: переносим start_at и пересчитываем end_at
            fields["start_at"] = new_iso
            if task.get("start_at") and task.get("end_at"):
                try:
                    old_s = datetime.fromisoformat(task["start_at"])
                    old_e = datetime.fromisoformat(task["end_at"])
                    duration = old_e - old_s
                    new_s = datetime.fromisoformat(new_iso)
                    fields["end_at"] = (new_s + duration).isoformat()
                except Exception:
                    pass
        else:
            # Задача: переносим дедлайн
            fields["due_datetime"] = new_iso
        ok = await storage.update_task_fields(task_id=task_id, user_id=user_id, **fields)
        if not ok:
            return f"Не удалось обновить [{task_id}]."
        # Пересоздаём напоминание
        try:
            from datetime import datetime as dt_cls, timedelta as td, timezone as tz_cls
            anchor_dt = dt_cls.fromisoformat(new_iso)
            us = await rdb.get_user_settings(user_id)
            offset_min = int(us.get("notification_offset_min", 15))
            remind_dt = anchor_dt - td(minutes=offset_min)
            remind_dt_utc = (remind_dt.astimezone(tz_cls.utc)
                             if remind_dt.tzinfo else remind_dt.replace(tzinfo=tz_cls.utc))
            now_utc = dt_cls.now(tz_cls.utc)
            safe_remind_at = remind_dt_utc if remind_dt_utc > now_utc else now_utc
            # Удаляем старое напоминание и создаём новое
            await rdb.cancel_pending_reminders_for_task(user_id=user_id, task_id=task_id)
            await rdb.add_reminder(
                user_id=user_id,
                entity_type="task",
                entity_id=task_id,
                remind_at=safe_remind_at.isoformat(),
            )
            # Синхронизируем task.remind_at чтобы мини-апп видел актуальное время
            await storage.update_task_fields(
                task_id=task_id,
                user_id=user_id,
                remind_at=safe_remind_at.isoformat(),
            )
        except Exception:
            pass
        return f"🔄 Запись [{task_id}] перенесена на {new_iso}"

    return [parse_due_nl, task_add, task_list, task_list_period, task_done, task_delete, task_skip, event_list, event_move]
