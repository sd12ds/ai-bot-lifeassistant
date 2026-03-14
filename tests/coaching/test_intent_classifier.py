"""
Phase 4: Тесты intent_classifier — classify_by_rules().
Тестируем rule-based классификатор намерений по доменам.
"""
import pytest
from bot.core.intent_classifier import classify_by_rules


@pytest.mark.unit
@pytest.mark.coaching
def test_classify_nutrition_strong():
    # Сильный маркер питания — ожидаем nutrition
    result = classify_by_rules("съел борщ на обед 400 калорий")
    assert result == "nutrition"


@pytest.mark.unit
@pytest.mark.coaching
def test_classify_nutrition_calories():
    # Упоминание калорий — ожидаем nutrition
    result = classify_by_rules("посчитай калории: рис 200г")
    assert result == "nutrition"


@pytest.mark.unit
@pytest.mark.coaching
def test_classify_fitness_strong():
    # Сильный маркер тренировки — ожидаем fitness
    result = classify_by_rules("сделал тренировку: жим лёжа 80кг 3x10")
    assert result == "fitness"


@pytest.mark.unit
@pytest.mark.coaching
def test_classify_fitness_workout():
    # Ключевое слово workout — ожидаем fitness
    result = classify_by_rules("workout сегодня: приседания 100 раз")
    assert result == "fitness"


@pytest.mark.unit
@pytest.mark.coaching
def test_classify_reminder_strong():
    # Сильный маркер напоминания — ожидаем reminder
    result = classify_by_rules("напомни мне завтра в 9 утра позвонить врачу")
    assert result == "reminder"


@pytest.mark.unit
@pytest.mark.coaching
def test_classify_reminder_keyword():
    # Ключевое слово напомни — ожидаем reminder
    result = classify_by_rules("напомни позвонить маме в пятницу")
    assert result == "reminder"


@pytest.mark.unit
@pytest.mark.coaching
def test_classify_coaching_goal():
    # Сильный маркер коучинга — поставить цель — ожидаем coaching
    result = classify_by_rules("хочу поставить цель на месяц")
    assert result == "coaching"


@pytest.mark.unit
@pytest.mark.coaching
def test_classify_coaching_habit():
    # Ключевое слово привычка — ожидаем coaching
    result = classify_by_rules("хочу завести привычку медитировать каждое утро")
    assert result == "coaching"


@pytest.mark.unit
@pytest.mark.coaching
def test_classify_empty_returns_none():
    # Пустая строка — домен не определён
    result = classify_by_rules("")
    assert result is None


@pytest.mark.unit
@pytest.mark.coaching
def test_classify_generic_greeting_returns_none():
    # Общее приветствие — нет явного домена
    result = classify_by_rules("привет как дела")
    assert result is None


@pytest.mark.unit
@pytest.mark.coaching
def test_classify_single_word_returns_none():
    # Одно слово без контекста — нормальных маркеров < 2 → None
    result = classify_by_rules("вода")
    assert result is None


@pytest.mark.unit
@pytest.mark.coaching
def test_classify_always_returns_str_or_none():
    # classify_by_rules всегда возвращает str или None, никогда не падает
    samples = ["съел яблоко", "тренировка ноги", "напомни", "цель", "test", ""]
    for text in samples:
        result = classify_by_rules(text)
        assert result is None or isinstance(result, str)
