"""
Phase 5: Тесты resilience — устойчивость сервисов к граничным случаям.
Тестируем get_tone_for_state, get_personalized_tone_instruction и coaching_recommendations.
"""
import pytest
from services.coaching_engine import get_tone_for_state
from services.coaching_personalization import get_personalized_tone_instruction


# ══════════════════════════════════════════════════════════════════════════════
# get_tone_for_state — устойчивость к разным состояниям
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.coaching
def test_tone_for_unknown_state_returns_string():
    # Неизвестное состояние — не падает, возвращает строку
    result = get_tone_for_state("unknown_state_xyz")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.unit
@pytest.mark.coaching
def test_tone_for_empty_state():
    # Пустая строка — не падает
    result = get_tone_for_state("")
    assert isinstance(result, str)


@pytest.mark.unit
@pytest.mark.coaching
def test_tone_known_states_return_non_empty():
    # Все известные состояния возвращают непустую строку
    states = ["momentum", "active", "risk", "recovery", "overload", "new_user"]
    for state in states:
        result = get_tone_for_state(state)
        assert isinstance(result, str), f"Non-string for state={state}"
        assert len(result) > 5, f"Too short for state={state}"


# ══════════════════════════════════════════════════════════════════════════════
# get_personalized_tone_instruction — чистая функция
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.coaching
def test_personalized_tone_overload_returns_warning():
    # Перегруженный пользователь — мягкий тон
    result = get_personalized_tone_instruction(state="overload")
    assert "ПЕРЕГРУЖЕН" in result or "перегруж" in result.lower()


@pytest.mark.unit
@pytest.mark.coaching
def test_personalized_tone_risk_returns_dropout_warning():
    # Риск дропаута — прямой заботливый тон
    result = get_personalized_tone_instruction(state="risk")
    assert "DROPOUT" in result or "риск" in result.lower() or "РИСК" in result


@pytest.mark.unit
@pytest.mark.coaching
def test_personalized_tone_recovery_returns_gentle():
    # Возврат после паузы — мягкий тон без упрёков
    result = get_personalized_tone_instruction(state="recovery")
    assert "ВОЗВРАЩАЕТСЯ" in result or "возвращ" in result.lower()


@pytest.mark.unit
@pytest.mark.coaching
def test_personalized_tone_unknown_state_no_crash():
    # Неизвестное состояние — не падает
    result = get_personalized_tone_instruction(state="unknown")
    assert isinstance(result, str)


@pytest.mark.unit
@pytest.mark.coaching
def test_personalized_tone_with_patterns():
    # Паттерны передаются без ошибок
    result = get_personalized_tone_instruction(
        state="active",
        coach_tone="strict",
        patterns=["evening_person", "skips_mondays"],
    )
    assert isinstance(result, str)


@pytest.mark.unit
@pytest.mark.coaching
def test_personalized_tone_empty_patterns():
    # Пустые паттерны — не падает
    result = get_personalized_tone_instruction(state="momentum", patterns=[])
    assert isinstance(result, str)


# ══════════════════════════════════════════════════════════════════════════════
# Импорты ключевых модулей — smoke tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.coaching
def test_coaching_recommendations_import():
    # Модуль рекомендаций импортируется без ошибок
    from services.coaching_recommendations import generate_recommendations
    assert generate_recommendations is not None


@pytest.mark.unit
@pytest.mark.coaching
def test_coaching_engine_import_all():
    # Все ключевые функции engine импортируются
    from services.coaching_engine import (
        compute_user_state, compute_risk_scores,
        compute_weekly_score, update_daily_snapshot,
        get_tone_for_state,
    )
    assert all([
        compute_user_state, compute_risk_scores,
        compute_weekly_score, update_daily_snapshot,
        get_tone_for_state,
    ])
