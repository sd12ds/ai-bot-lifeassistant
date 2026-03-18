"""
Rule-based pre-classifier намерений.

Быстрая keyword/regex проверка ПЕРЕД вызовом LLM.
Если домен определяется однозначно — возвращаем его без траты токенов.
Если неоднозначно — возвращаем None, и далее работает LLM-классификатор.
"""
from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)

# ── Словари ключевых слов по доменам ─────────────────────────────────────────

# Сильные маркеры — одного достаточно для однозначной классификации
_NUTRITION_STRONG = {
    # Приёмы пищи
    "завтрак", "обед", "ужин", "перекус",
    # Действия с едой
    "съел", "съела", "поел", "поела", "выпил", "выпила",
    "перекусил", "перекусила",
    # КБЖУ и нутриенты
    "калори", "ккал", "кбжу", "белок", "белка", "белков",
    "углевод", "жиров", "жиры",
    # Инструменты
    "граммовк", "порци", " грамм ",  # пробелы вокруг "грамм" чтобы не ловить "программ упражнений"
    # Draft-команды
    "черновик", "сохрани приём", "сохрани прием",
    # Продукты EWA
    "бодибокс", "боди бокс", "зерозефир", "зеро зефир",
    "bodybox", "zerozefir", "протеин ева", "протеин эва",
    # Вода
    "выпил воды", "стакан воды", "воды выпил",
    # Score/итоги
    "оценка за день", "итоги за неделю", "weekly summary",
    "nutrition", "score питани",
}

# Обычные маркеры — нужно >= 2 совпадения или 1 + контекст
_NUTRITION_NORMAL = {
    # Продукты питания (частые)
    "сыр", "каша", "овсянк", "рис", "курин", "куриц",
    "яйц", "хлеб", "масл", "молок", "творог", "йогурт",
    "банан", "яблок", "салат", "суп", "макарон", "гречк",
    "картошк", "картофел", "мяс", "рыб", "лосось", "тунец",
    "кофе", "чай", "сок", "кефир", "сметан", "орех",
    "шоколад", "конфет", "печень", "торт", "пирог",
    "батончик", "вафл", "зефир", "какао", "протеин",
    "сгущёнк", "сгущенк", "хлебц", "рисов",
    # Действия с порцией
    " грамм", "граммов", "порция", "порцию", "кусок", "кусочек",
    "ложка", "ложку", "тарелк", "стакан",
    # Контекст питания
    "еда", "еду", "пищ", "питани", "диет", "рацион",
    "продукт", "блюд", "рецепт", "приём пищи", "прием пищи",
    # Действия редактирования еды
    "поменяй", "измени", "убери", "добавь",
    "как вчера", "повтори", "шаблон",
    "сколько осталось", "остаток",
    # Вода
    "воды", "воду", "водичк",
}

_FITNESS_STRONG = {
    # Кардио/бег — пробелы защищают от ложных срабатываний (бегемот, пресса)
    "бег ", "бегал", "пробежал", "пробежк", "пробежа",
    # Кардио/общее
    "кардио", "hiit", "табата", "интервальн",
    # Кардио/аппараты
    "эллипс", "эллипсоид", "скакалк", "гребл",
    # Плавание
    "плавал", "плаван", "проплыл",
    # Велосипед
    "велосипед", "вело ", "велотрен",
    # Силовые/упражнения
    "жим", "присед", "тяга", "подтягиван", "отжиман",
    "пресс ", "становая", "румынская тяга",
    "разгибание бедр", "сгибание голен", "болгарск", "ягодичный мост",
    # Силовые/снаряды
    "штанг", "гантел", "тренажёр", "тренажер",
    "гриф", "блин на", "в смите", "кроссовер", "гравитрон",
    # Общая тренировка
    "тренировк", "тренировался", "потренировал",
    "силовая", "силовую", "силовой",
    "качалк", "фитнес", "workout",
    # Восстановление/гибкость
    "растяжк", "стретчинг", "йога", "йогу", "йогой", "мобилити",
    # Замеры
    "замер", "взвесил", "упражнен", "streak тренир",
    # Программа тренировок
    "программа тренир", "тренировочная программ", "тренировочный план",
    "план тренир", "шаблон тренир",
    "день 1", "день 2", "день 3", "сплит",
    # Шаги/ходьба
    "шагов", "прогулк", "прошёл ", "прошел ", "походил",
}

_FITNESS_NORMAL = {
    # Место/контекст
    "спорт", "зал", "мышц", "вес тела", "набор масс", "похуден", "сушк",
    # Метрики
    "подход", "повторен", "км ", "дистанц", "темп ", "пульс",
    "нагрузк", "активност", "занимался",
    # Разминка/заминка
    "разминк", "заминк",
    # Шаблоны
    "шаблон",  # шаблоны тренировок (есть и в nutrition — при конфликте уйдёт в LLM)
    "замени упражнен", "добавь упражнен", "убери упражнен",
    "поменяй местами день", "покажи программ",
}

_REMINDER_STRONG = {
    "напомни", "напоминан", "задач", "дедлайн",
    "перенеси", "запланиру", "расписан",
    "встреч", "созвон", "событи",
    "к врачу", "на приём", "на прием",
    "запись к", "бронь", "билет",
}

# Антимаркеры — слова которые ИСКЛЮЧАЮТ домен при конфликте
_NUTRITION_ANTI = {
    "напомни", "задач", "встреч", "созвон", "перенеси",
    "тренировк", "подход", "повторен", "жим", "присед",
}

_REMINDER_ANTI = {
    "съел", "съела", "поел", "калори", "ккал", " грамм",
    "завтрак", "обед", "ужин", "перекус", "кбжу",
}




_COACHING_STRONG = {
    # Коучинг и цели
    'коучинг', 'коуч',
    'поставить цель', 'поставь цель', 'новая цель', 'моя цель',
    'прогресс по цели', 'достиг цели', 'выполнил цель',
    # Привычки
    'завести привычку', 'создать привычку', 'новая привычка',
    'стрик', 'серия дней', 'трекер привычек',
    # Check-in и обзоры
    'чекин', 'check-in', 'checkin', 'ежедневный обзор',
    'недельный обзор', 'review цел',
    # Явные коучинговые запросы
    'план достижений', 'этапы цели', 'milestone',
    'заморозить цель', 'возобновить цель',
    'habit tracker', 'goal tracker',
}

_COACHING_NORMAL = {
    'цель', 'цели', 'привычк', 'мотивация', 'мотивацию',
    'достижен', 'прогресс',
    'пропустил привычку', 'пропустила привычку',
    'выполнил привычку', 'выполнила привычку',
    'отметить привычку',
}

_COACHING_ANTI = {
    'напомни', 'задач', 'тренировк', 'упражнен',
    'съел', 'калори', 'завтрак', 'обед', 'ужин',
}

def classify_by_rules(text: str) -> str | None:
    """Определяет домен по ключевым словам.
    
    Возвращает имя агента ('nutrition', 'fitness', 'reminder') 
    или None если определить однозначно не удалось.
    """
    low = text.lower().strip()
    
    # Подсчитываем совпадения по доменам
    nutr_strong = _count_matches(low, _NUTRITION_STRONG)
    nutr_normal = _count_matches(low, _NUTRITION_NORMAL)
    nutr_anti = _count_matches(low, _NUTRITION_ANTI)
    
    fit_strong = _count_matches(low, _FITNESS_STRONG)
    fit_normal = _count_matches(low, _FITNESS_NORMAL)
    
    rem_strong = _count_matches(low, _REMINDER_STRONG)
    rem_anti = _count_matches(low, _REMINDER_ANTI)

    # Coaching-счётчики
    coach_strong = _count_matches(low, _COACHING_STRONG)
    coach_normal = _count_matches(low, _COACHING_NORMAL)
    coach_anti = _count_matches(low, _COACHING_ANTI)
    
    # Приоритет 1: сильные маркеры без антимаркеров
    if nutr_strong > 0 and nutr_anti == 0:
        logger.info("PRE-CLASSIFY → nutrition (strong=%d)", nutr_strong)
        return "nutrition"
    
    if fit_strong > 0:
        logger.info("PRE-CLASSIFY → fitness (strong=%d)", fit_strong)
        return "fitness"
    
    if rem_strong > 0 and rem_anti == 0:
        logger.info("PRE-CLASSIFY → reminder (strong=%d)", rem_strong)
        return "reminder"

    if coach_strong > 0 and coach_anti == 0:
        logger.info("PRE-CLASSIFY → coaching (strong=%d)", coach_strong)
        return "coaching"
    
    # Приоритет 2: >= 2 обычных маркера без конфликтов
    if nutr_normal >= 2 and nutr_anti == 0 and rem_strong == 0 and fit_strong == 0:
        logger.info("PRE-CLASSIFY → nutrition (normal=%d)", nutr_normal)
        return "nutrition"
    
    if fit_normal >= 2 and nutr_strong == 0 and rem_strong == 0:
        logger.info("PRE-CLASSIFY → fitness (normal=%d)", fit_normal)
        return "fitness"

    if coach_normal >= 2 and coach_anti == 0 and fit_strong == 0 and nutr_strong == 0 and rem_strong == 0:
        logger.info("PRE-CLASSIFY → coaching (normal=%d)", coach_normal)
        return "coaching"
    
    # Приоритет 3: один сильный маркер с антимаркерами — конфликт, отдаём LLM
    logger.debug(
        "PRE-CLASSIFY → None (nutr_s=%d nutr_n=%d fit_s=%d rem_s=%d)",
        nutr_strong, nutr_normal, fit_strong, rem_strong,
    )
    return None


def _count_matches(text: str, keywords: set[str]) -> int:
    """Считает сколько ключевых слов найдено в тексте."""
    count = 0
    for kw in keywords:
        if kw in text:
            count += 1
    return count


def has_any_signal(text: str, exclude_domain: str) -> str | None:
    """Проверяет есть ли хоть один маркер (strong/normal) для домена КРОМЕ exclude_domain.

    Используется для защиты sticky domain: если сообщение имеет сигнал
    другого домена — sticky нужно пропустить и отдать решение LLM.
    Возвращает имя домена с сигналом или None.
    """
    low = text.lower().strip()

    # Проверяем strong маркеры всех доменов кроме исключённого
    if exclude_domain != "fitness":
        if _count_matches(low, _FITNESS_STRONG) > 0:
            return "fitness"
    if exclude_domain != "nutrition":
        if _count_matches(low, _NUTRITION_STRONG) > 0:
            return "nutrition"
    if exclude_domain != "reminder":
        if _count_matches(low, _REMINDER_STRONG) > 0:
            return "reminder"
    if exclude_domain != "coaching":
        if _count_matches(low, _COACHING_STRONG) > 0:
            return "coaching"

    # Проверяем normal маркеры (>= 1) при условии что у sticky домена 0 маркеров
    sticky_signal = 0
    if exclude_domain == "nutrition":
        sticky_signal = _count_matches(low, _NUTRITION_STRONG) + _count_matches(low, _NUTRITION_NORMAL)
    elif exclude_domain == "fitness":
        sticky_signal = _count_matches(low, _FITNESS_STRONG) + _count_matches(low, _FITNESS_NORMAL)
    elif exclude_domain == "reminder":
        sticky_signal = _count_matches(low, _REMINDER_STRONG)
    elif exclude_domain == "coaching":
        sticky_signal = _count_matches(low, _COACHING_STRONG) + _count_matches(low, _COACHING_NORMAL)

    # Если у sticky домена есть хоть один маркер — не переопределяем
    if sticky_signal > 0:
        return None

    # У sticky 0 маркеров — проверяем normal других доменов
    if exclude_domain != "fitness" and _count_matches(low, _FITNESS_NORMAL) > 0:
        return "fitness"
    if exclude_domain != "nutrition" and _count_matches(low, _NUTRITION_NORMAL) > 0:
        return "nutrition"
    if exclude_domain != "coaching" and _count_matches(low, _COACHING_NORMAL) > 0:
        return "coaching"

    return None

def has_strong_signal(text: str, exclude_domain: str) -> str | None:
    """Проверяет ТОЛЬКО strong-маркеры всех доменов КРОМЕ exclude_domain.

    В отличие от has_any_signal() не проверяет normal-маркеры —
    это снижает ложные срабатывания на коротких сообщениях (≤5 слов).
    Используется в short follow-up guard (L3a).
    """
    low = text.lower().strip()

    if exclude_domain != "fitness" and _count_matches(low, _FITNESS_STRONG) > 0:
        return "fitness"
    if exclude_domain != "nutrition" and _count_matches(low, _NUTRITION_STRONG) > 0:
        return "nutrition"
    if exclude_domain != "reminder" and _count_matches(low, _REMINDER_STRONG) > 0:
        return "reminder"
    if exclude_domain != "coaching" and _count_matches(low, _COACHING_STRONG) > 0:
        return "coaching"

    return None
