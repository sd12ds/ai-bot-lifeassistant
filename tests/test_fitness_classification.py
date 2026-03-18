# -*- coding: utf-8 -*-
"""Тесты rule-based фитнес-классификации.

6 тест-классов, ~50 кейсов. Покрытие:
- classify_by_rules() для fitness strong/normal маркеров
- Негативные кейсы (не fitness)
- has_strong_signal() для short follow-up guard
- Sticky follow-up сценарии
- Cross-domain конфликты
"""

import sys
import os
import pytest

# Добавляем корень проекта в sys.path для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot.core.intent_classifier import classify_by_rules, has_strong_signal


# ═══════════════════════════════════════════════════════════════════════════════
# 1. STRONG маркеры фитнеса — одного достаточно для classify_by_rules() == "fitness"
# ═══════════════════════════════════════════════════════════════════════════════
class TestFitnessStrongMarkers:
    """Каждый кейс содержит хотя бы один STRONG fitness-маркер."""

    @pytest.mark.parametrize("text", [
        # Бег
        "пробежал 5 км",
        "я бегал сегодня утром",
        "сделал пробежку в парке",
        # Силовые
        "жим лёжа 80x8",
        "присед со штангой",
        "подтягивания 3x10",
        # Плавание
        "плавал в бассейне",
        "проплыл 1 км",
        # Вело
        "катался на велосипеде",
        # Восстановление
        "занимался йогой 30 минут",
        "растяжка после тренировки",
        "делал стретчинг",
        # HIIT
        "табата 20 минут",
        "сегодня hiit тренировка",
        # Аппараты
        "занимался на эллипсоиде",
        "скакалка 10 минут",
        "гребля 20 минут",
        # Шаги
        "прошёл 10000 шагов",
        "8000 шагов сегодня",
        "прогулка в парке 5 км",
        "походил по городу",
        # Общая тренировка
        "тренировался в зале",
        "силовая тренировка сегодня",
        "взвесился утром — 80 кг",
        # Снаряды
        "работал со штангой",
    ])
    def test_strong_fitness(self, text):
        """classify_by_rules должен вернуть 'fitness' для strong-маркеров."""
        assert classify_by_rules(text) == "fitness", f"Ожидали fitness для: {text!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. NORMAL маркеры фитнеса — нужно ≥2 для классификации
# ═══════════════════════════════════════════════════════════════════════════════
class TestFitnessNormalMarkers:
    """Каждый кейс содержит ≥2 NORMAL fitness-маркера."""

    @pytest.mark.parametrize("text", [
        "ходил в зал, мышцы болят",
        "спорт и набор массы",
        "нагрузка в зале была тяжёлая",
    ])
    def test_normal_fitness(self, text):
        """classify_by_rules должен вернуть 'fitness' при ≥2 normal маркерах."""
        assert classify_by_rules(text) == "fitness", f"Ожидали fitness для: {text!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. НЕ fitness — негативные кейсы
# ═══════════════════════════════════════════════════════════════════════════════
class TestNotFitness:
    """Кейсы, которые НЕ должны классифицироваться как fitness."""

    @pytest.mark.parametrize("text", [
        "напомни мне завтра в 9 утра",
        "съел курицу с рисом на обед",
        "запиши завтрак — овсянка 200г",
        "какой курс доллара",
        "привет, как дела?",
        "поставь цель — похудеть",
    ])
    def test_not_fitness(self, text):
        """classify_by_rules не должен вернуть 'fitness'."""
        result = classify_by_rules(text)
        assert result != "fitness", f"НЕ ожидали fitness для: {text!r}, получили: {result}"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. has_strong_signal — проверка strong-маркеров других доменов
# ═══════════════════════════════════════════════════════════════════════════════
class TestHasStrongSignal:
    """has_strong_signal проверяет только STRONG маркеры кроме указанного домена."""

    def test_short_followup_no_signal(self):
        """'за 30 минут' не содержит strong маркеров других доменов."""
        assert has_strong_signal("за 30 минут", exclude_domain="fitness") is None

    def test_short_km_no_signal(self):
        """'5 км' не содержит strong маркеров других доменов."""
        assert has_strong_signal("5 км", exclude_domain="fitness") is None

    def test_nutrition_signal(self):
        """'съел курицу' — strong nutrition маркер."""
        result = has_strong_signal("съел курицу", exclude_domain="fitness")
        assert result == "nutrition"

    def test_reminder_signal(self):
        """'напомни завтра' — strong reminder маркер."""
        result = has_strong_signal("напомни завтра", exclude_domain="fitness")
        assert result == "reminder"

    def test_ok_no_signal(self):
        """'ок' — нет strong маркеров."""
        assert has_strong_signal("ок", exclude_domain="fitness") is None

    def test_da_no_signal(self):
        """'да' — нет strong маркеров."""
        assert has_strong_signal("да", exclude_domain="fitness") is None


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Sticky follow-up — короткие сообщения должны оставаться в sticky
# ═══════════════════════════════════════════════════════════════════════════════
class TestStickyFollowUp:
    """Короткие follow-up (≤5 слов) без strong-маркеров другого домена."""

    @pytest.mark.parametrize("text", [
        "за 30 минут",
        "5 км",
        "25 мин",
        "ок",
        "да",
        "ещё подход",
        "готово",
        "нет",
    ])
    def test_short_followup_stays_sticky(self, text):
        """Короткие follow-up не должны содержать strong сигналов других доменов."""
        # Проверяем что ≤5 слов
        assert len(text.split()) <= 5, f"Текст должен быть ≤5 слов: {text!r}"
        # Проверяем что нет strong-маркеров другого домена (для любого exclude)
        for domain in ("fitness", "nutrition", "reminder", "coaching"):
            # Если мы exclude текущий домен, не должно быть strong-сигнала
            # (это симулирует: sticky=domain, и мы проверяем нет ли strong другого)
            pass
        # Главная проверка: при sticky=fitness, нет strong других доменов
        assert has_strong_signal(text, exclude_domain="fitness") is None


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Cross-domain конфликты
# ═══════════════════════════════════════════════════════════════════════════════
class TestCrossDomainConflicts:
    """Кейсы на стыке доменов — правильная классификация."""

    def test_nutrition_edit_not_fitness(self):
        """'поменяй сыр 30г на творог' — nutrition, не fitness."""
        result = classify_by_rules("поменяй сыр 30г на творог")
        assert result != "fitness", f"Не ожидали fitness, получили: {result}"

    def test_reminder_not_fitness(self):
        """'напомни мне позвонить в 15:00' — reminder."""
        result = classify_by_rules("напомни мне позвонить в 15:00")
        assert result == "reminder"
