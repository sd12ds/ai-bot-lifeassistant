"""
Phase 5: Тесты cross-module сервисов.
Тестируем generate_cross_module_inferences (чистая функция) и select_top_nudge.
"""
import pytest
from services.coaching_cross_module import generate_cross_module_inferences
from services.coaching_proactive import (
    select_top_nudge, NudgeCandidate,
    PRIORITY_CRITICAL, PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW,
)


def make_nudge(nudge_type: str, priority: int) -> NudgeCandidate:
    """Хелпер: создаёт NudgeCandidate для тестов."""
    return NudgeCandidate(nudge_type=nudge_type, priority=priority, text="тестовое сообщение")


# ══════════════════════════════════════════════════════════════════════════════
# generate_cross_module_inferences — чистая функция
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.coaching
def test_inferences_empty_signals_returns_list():
    # Пустые сигналы — функция возвращает список (пустой или с выводами)
    result = generate_cross_module_inferences({})
    assert isinstance(result, list)


@pytest.mark.unit
@pytest.mark.coaching
def test_inferences_overload_critical():
    # Сигналы перегруза: много задач + целей + привычек → overload с severity critical
    signals = {
        "tasks_active_total": 25,   # > 20 → +2
        "tasks_overdue": 8,          # > 5 → +2
        "goals_active_count": 6,     # > 5 → +1
        "habits_active_count": 7,    # > 6 → +1
    }
    result = generate_cross_module_inferences(signals)
    overload = [r for r in result if r["type"] == "overload"]
    assert len(overload) == 1
    assert overload[0]["severity"] == "critical"


@pytest.mark.unit
@pytest.mark.coaching
def test_inferences_overload_high():
    # Средний перегруз → severity high
    signals = {
        "tasks_active_total": 22,
        "tasks_overdue": 6,
        "goals_active_count": 3,
        "habits_active_count": 5,
    }
    result = generate_cross_module_inferences(signals)
    overload = [r for r in result if r["type"] == "overload"]
    assert len(overload) == 1
    assert overload[0]["severity"] == "high"


@pytest.mark.unit
@pytest.mark.coaching
def test_inferences_fitness_imbalance():
    # Фитнес-цель + нет тренировок → imbalance
    signals = {
        "has_fitness_goal": True,
        "last_workout_days_ago": 10,  # > 7
    }
    result = generate_cross_module_inferences(signals)
    imbalance = [r for r in result if r["type"] == "imbalance"]
    assert len(imbalance) >= 1
    assert imbalance[0]["severity"] == "high"


@pytest.mark.unit
@pytest.mark.coaching
def test_inferences_structure():
    # Каждый вывод имеет обязательные поля
    signals = {"has_fitness_goal": True, "last_workout_days_ago": 14}
    result = generate_cross_module_inferences(signals)
    for inference in result:
        assert "type" in inference
        assert "title" in inference
        assert "description" in inference
        assert "severity" in inference
        assert "modules_affected" in inference


@pytest.mark.unit
@pytest.mark.coaching
def test_inferences_no_overload_below_threshold():
    # Мало задач — нет перегруза
    signals = {"tasks_active_total": 3, "goals_active_count": 2}
    result = generate_cross_module_inferences(signals)
    overload = [r for r in result if r["type"] == "overload"]
    assert len(overload) == 0


# ══════════════════════════════════════════════════════════════════════════════
# select_top_nudge — приоритизация nudge-кандидатов
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.coaching
def test_select_top_nudge_empty_returns_none():
    # Пустой список кандидатов → None
    result = select_top_nudge([], set())
    assert result is None


@pytest.mark.unit
@pytest.mark.coaching
def test_select_top_nudge_prefers_critical():
    # CRITICAL имеет приоритет над HIGH и MEDIUM
    candidates = [
        make_nudge("medium_nudge", PRIORITY_MEDIUM),
        make_nudge("critical_nudge", PRIORITY_CRITICAL),
        make_nudge("high_nudge", PRIORITY_HIGH),
    ]
    result = select_top_nudge(candidates, set())
    assert result is not None
    assert result.nudge_type == "critical_nudge"


@pytest.mark.unit
@pytest.mark.coaching
def test_select_top_nudge_skips_already_sent():
    # Уже отправленные типы пропускаются
    candidates = [
        make_nudge("critical_nudge", PRIORITY_CRITICAL),
        make_nudge("high_nudge", PRIORITY_HIGH),
    ]
    result = select_top_nudge(candidates, already_sent_types={"critical_nudge"})
    assert result is not None
    assert result.nudge_type == "high_nudge"


@pytest.mark.unit
@pytest.mark.coaching
def test_select_top_nudge_all_sent_returns_none():
    # Все типы уже отправлены → None
    candidates = [
        make_nudge("nudge_a", PRIORITY_HIGH),
        make_nudge("nudge_b", PRIORITY_MEDIUM),
    ]
    result = select_top_nudge(candidates, already_sent_types={"nudge_a", "nudge_b"})
    assert result is None


@pytest.mark.unit
@pytest.mark.coaching
def test_select_top_nudge_low_priority_fallback():
    # LOW выбирается если нет более важных кандидатов
    candidates = [make_nudge("low_nudge", PRIORITY_LOW)]
    result = select_top_nudge(candidates, set())
    assert result is not None
    assert result.nudge_type == "low_nudge"
