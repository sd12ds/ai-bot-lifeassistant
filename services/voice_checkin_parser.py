"""
Парсер голосовых/текстовых чекинов.

Три основных функции:
  - is_checkin_message(text)         → bool     определяет, является ли сообщение чекином
  - detect_slot(text, current_hour)  → str      morning | midday | evening | manual
  - detect_date(text)                → date     дата чекина (сегодня по умолчанию)
  - parse_checkin_fields(text, slot) → dict     структурированные поля по слоту
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta

import dateparser
from openai import AsyncOpenAI

from config import OPENAI_API_KEY, OPENAI_LLM_MODEL, OPENAI_CLASSIFIER_MODEL

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ── Маппинг ключевых слов → слот ──────────────────────────────────────────────
_SLOT_KEYWORDS: dict[str, list[str]] = {
    "morning": [
        "утром", "с утра", "утренний", "утреннего", "с утреннего",
        "утро", "по утрам", "проснулся", "проснулась", "начало дня",
    ],
    "midday": [
        "днём", "днем", "в обед", "в обеде", "обеденный", "полдень",
        "середина дня", "середине дня", "дневной", "в середине",
    ],
    "evening": [
        "вечером", "вечерний", "вечернего", "вечер", "итог дня",
        "за день", "конец дня", "концу дня", "подведу итоги",
        "подвожу итоги", "завершение дня", "засыпаю", "перед сном",
        "ночь", "ночью",
    ],
}

# Ключевые слова, характерные для чекинов (для классификатора)
_CHECKIN_KEYWORDS = [
    "энергия", "энерги", "настроение", "настроени",
    "усталость", "усталост", "самочувствие", "самочувстви",
    "продуктивность", "продуктивност", "день прошёл", "день прошел",
    "утренний чекин", "вечерний чекин", "дневной чекин",
    "победы", "победа", "блокер", "мешало", "помешало",
    "как дела", "как прошло", "как прошёл", "прогресс",
]


# ═══════════════════════════════════════════════════════════════════════════════
# КЛАССИФИКАТОР — является ли сообщение чекином
# ═══════════════════════════════════════════════════════════════════════════════

async def is_checkin_message(text: str) -> bool:
    """
    Определяет, является ли текст чекином (голосовым или текстовым отчётом
    о состоянии/дне/энергии). Сначала rule-based, потом LLM-классификатор.
    """
    text_lower = text.lower()

    # Быстрый rule-based анализ по ключевым словам
    for kw in _CHECKIN_KEYWORDS:
        if kw in text_lower:
            return True
    # Ключевые слова слотов тоже являются индикатором чекина
    for slot_words in _SLOT_KEYWORDS.values():
        for kw in slot_words:
            if kw in text_lower:
                return True

    # LLM-классификатор для неочевидных случаев
    try:
        resp = await _client.chat.completions.create(
            model=OPENAI_CLASSIFIER_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты классификатор. Отвечай ТОЛЬКО одним словом: yes или no.\n"
                        "Определи: является ли сообщение ежедневным чекином пользователя "
                        "(рассказ о самочувствии, энергии, настроении, как прошёл день, "
                        "победах или блокерах), а не вопросом или командой?"
                    ),
                },
                {"role": "user", "content": text[:500]},
            ],
            max_tokens=5,
            temperature=0,
        )
        answer = resp.choices[0].message.content.strip().lower()
        return answer.startswith("yes")
    except Exception as e:
        logger.warning("Классификатор чекина упал: %s", e)
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# ОПРЕДЕЛЕНИЕ СЛОТА
# ═══════════════════════════════════════════════════════════════════════════════

def detect_slot(text: str, current_hour: int) -> str:
    """
    Определяет слот чекина: morning | midday | evening | manual.

    Порядок приоритетов:
      1. Явное числовое время в тексте («в 8 утра», «13:00»)
      2. Ключевые слова слота в тексте
      3. Текущий час (fallback)
    """
    text_lower = text.lower()

    # 1. Числовое время в тексте
    time_match = re.search(
        r"\b(?:в\s+)?(\d{1,2})(?::(\d{2}))?\s*(?:утра|ночи|дня|вечера)?\b",
        text_lower,
    )
    if time_match:
        hour = int(time_match.group(1))
        if 5 <= hour <= 11:
            return "morning"
        if 12 <= hour <= 16:
            return "midday"
        if 17 <= hour <= 23:
            return "evening"

    # 2. Ключевые слова в тексте (приоритет по порядку: утро > день > вечер)
    for slot, keywords in _SLOT_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return slot

    # 3. Текущий час как fallback
    if 5 <= current_hour <= 11:
        return "morning"
    if 12 <= current_hour <= 16:
        return "midday"
    return "evening"


# ═══════════════════════════════════════════════════════════════════════════════
# ОПРЕДЕЛЕНИЕ ДАТЫ
# ═══════════════════════════════════════════════════════════════════════════════

def detect_date(text: str) -> date:
    """
    Извлекает дату чекина из текста.

    Поддерживает: «сегодня», «вчера», «позавчера», «в понедельник»,
    «3 марта», «15.03» и любые форматы, понятные dateparser.
    Fallback: date.today().
    """
    text_lower = text.lower()

    # Явные алиасы
    if "позавчера" in text_lower:
        return date.today() - timedelta(days=2)
    if "вчера" in text_lower:
        return date.today() - timedelta(days=1)
    if "сегодня" in text_lower:
        return date.today()

    # Попытка парсинга через dateparser (поддерживает русский язык)
    try:
        parsed = dateparser.parse(
            text,
            languages=["ru"],
            settings={
                "PREFER_DAY_OF_MONTH": "first",
                "PREFER_DATES_FROM": "past",
                "RETURN_AS_TIMEZONE_AWARE": False,
            },
        )
        if parsed:
            result = parsed.date()
            # Не принимаем даты из будущего (больше чем сегодня)
            if result <= date.today():
                return result
    except Exception as e:
        logger.debug("dateparser не распознал дату: %s", e)

    return date.today()


# ═══════════════════════════════════════════════════════════════════════════════
# LLM-ПАРСИНГ ПОЛЕЙ ЧЕКИНА
# ═══════════════════════════════════════════════════════════════════════════════

# Поля по слоту — что извлекать
_SLOT_FIELDS: dict[str, dict] = {
    "morning": {
        "energy_level": "int 1-5 (1=истощён, 5=в потоке), или null",
        "notes":        "заметки об утреннем состоянии, планы, или null",
    },
    "midday": {
        "energy_level": "int 1-5, текущий уровень энергии, или null",
        "notes":        "заметки о середине дня, или null",
    },
    "evening": {
        "mood":         "строка: great|good|ok|tired|bad, или null",
        "energy_level": "int 1-5, общая энергия за день, или null",
        "notes":        "как прошёл день (свободный текст), или null",
        "wins":         "победы, достижения дня (текст), или null",
        "blockers":     "что мешало, трудности (текст), или null",
    },
    "manual": {
        "energy_level": "int 1-5, или null",
        "mood":         "строка: great|good|ok|tired|bad, или null",
        "notes":        "заметки, или null",
        "wins":         "победы (текст), или null",
        "blockers":     "блокеры (текст), или null",
    },
}

# Описания mood для промпта
_MOOD_MAP = "great=отличное, good=хорошее, ok=нормальное, tired=устал(а), bad=плохое"


async def parse_checkin_fields(text: str, slot: str) -> dict:
    """
    Извлекает структурированные поля чекина из свободного текста с помощью LLM.
    Возвращает словарь с ключами поля → значение (None если не упомянуто).
    """
    fields = _SLOT_FIELDS.get(slot, _SLOT_FIELDS["manual"])
    fields_desc = "\n".join(f'  "{k}": {v}' for k, v in fields.items())

    prompt = (
        f"Ты извлекаешь данные из текста дневного чекина пользователя.\n"
        f"Слот: {slot} (morning=утро, midday=день, evening=вечер).\n"
        f"Настроение mood: {_MOOD_MAP}.\n\n"
        f"Верни ТОЛЬКО JSON-объект со следующими полями:\n"
        f"{fields_desc}\n\n"
        f"Правила:\n"
        f"- Если поле не упомянуто в тексте — верни null\n"
        f"- energy_level: целое число 1-5 или null\n"
        f"- mood: одно из great|good|ok|tired|bad или null\n"
        f"- Текстовые поля — краткое резюме на русском, не длиннее 300 символов\n"
        f"- Не добавляй поля, которых нет в списке выше\n"
        f"- Никаких пояснений, только JSON\n\n"
        f"Текст: {text[:1000]}"
    )

    try:
        resp = await _client.chat.completions.create(
            model=OPENAI_LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        parsed = json.loads(raw)

        # Фильтруем только разрешённые поля, чтобы не получить мусор
        allowed = set(fields.keys())
        return {k: v for k, v in parsed.items() if k in allowed}

    except Exception as e:
        logger.error("Ошибка LLM-парсинга чекина: %s", e)
        # Возвращаем пустой словарь — лучше сохранить пустой чекин, чем упасть
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
# ФОРМАТИРОВАНИЕ КАРТОЧКИ ПОДТВЕРЖДЕНИЯ
# ═══════════════════════════════════════════════════════════════════════════════

_SLOT_LABELS = {"morning": "🌅 Утро", "midday": "☀️ День", "evening": "🌙 Вечер", "manual": "📝 Вручную"}
_MOOD_LABELS = {"great": "😄 Отличное", "good": "😊 Хорошее", "ok": "😐 Нормальное", "tired": "😴 Устал(а)", "bad": "😟 Плохое"}
_ENERGY_LABELS = {1: "😴 1", 2: "😕 2", 3: "😐 3", 4: "😊 4", 5: "🔥 5"}


def format_checkin_card(
    slot: str,
    check_date: date,
    fields: dict,
    transcribed_text: str = "",
) -> str:
    """
    Формирует человекочитаемую карточку чекина для подтверждения пользователем.
    """
    # Форматируем дату
    today = date.today()
    if check_date == today:
        date_label = "сегодня"
    elif check_date == today - timedelta(days=1):
        date_label = "вчера"
    else:
        months = ["", "янв", "фев", "мар", "апр", "май", "июн",
                  "июл", "авг", "сен", "окт", "ноя", "дек"]
        date_label = f"{check_date.day} {months[check_date.month]}"

    lines = [
        f"📋 *Чекин — {_SLOT_LABELS.get(slot, slot)}, {date_label}*",
        "",
    ]

    # Энергия
    if fields.get("energy_level"):
        e = fields["energy_level"]
        lines.append(f"⚡️ Энергия: {_ENERGY_LABELS.get(int(e), str(e))}/5")

    # Настроение
    if fields.get("mood"):
        lines.append(f"💭 Настроение: {_MOOD_LABELS.get(fields['mood'], fields['mood'])}")

    # Заметки
    if fields.get("notes"):
        lines.append(f"📝 День: _{fields['notes']}_")

    # Победы
    if fields.get("wins"):
        lines.append(f"🏆 Победы: _{fields['wins']}_")

    # Блокеры
    if fields.get("blockers"):
        lines.append(f"🚧 Блокеры: _{fields['blockers']}_")

    # Если поля пустые — показываем оригинальный текст
    if not any(fields.get(k) for k in ("energy_level", "mood", "notes", "wins", "blockers")):
        lines.append(f"💬 _{transcribed_text[:300]}_")

    lines += [
        "",
        "Всё верно? Сохраняю чекин.",
    ]
    return "\n".join(lines)
