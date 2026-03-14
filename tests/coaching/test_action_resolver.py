"""
Phase 4: Тесты action_resolver — resolve_action().
Тестируем определение намерений пользователя относительно контекста сессии.
"""
import pytest
from bot.core.action_resolver import resolve_action, ActionType
from bot.core.session_context import SessionContext


def make_ctx(domain: str = "", has_draft: bool = False, pending: bool = False) -> SessionContext:
    """Хелпер: создаёт SessionContext для тестов."""
    ctx = SessionContext(user_id=123456, active_domain=domain)
    ctx.pending_confirmation = pending
    return ctx


@pytest.mark.unit
@pytest.mark.coaching
def test_resolve_confirm_da():
    # "да" — подтверждение действия
    action = resolve_action("да", make_ctx(pending=True))
    assert action.action == ActionType.CONFIRM


@pytest.mark.unit
@pytest.mark.coaching
def test_resolve_confirm_ok():
    # "ок" — подтверждение действия
    action = resolve_action("ок", make_ctx(pending=True))
    assert action.action == ActionType.CONFIRM


@pytest.mark.unit
@pytest.mark.coaching
def test_resolve_confirm_yes():
    # "yes" — подтверждение
    action = resolve_action("yes", make_ctx(pending=True))
    assert action.action == ActionType.CONFIRM


@pytest.mark.unit
@pytest.mark.coaching
def test_resolve_discard_net():
    # "нет" — отказ/отмена
    action = resolve_action("нет", make_ctx(pending=True))
    assert action.action == ActionType.DISCARD


@pytest.mark.unit
@pytest.mark.coaching
def test_resolve_discard_cancel():
    # "отмена" — отмена действия
    action = resolve_action("отмена", make_ctx())
    assert action.action == ActionType.DISCARD


@pytest.mark.unit
@pytest.mark.coaching
def test_resolve_status_check():
    # Запрос статуса
    action = resolve_action("записал?", make_ctx())
    assert action.action == ActionType.STATUS_CHECK


@pytest.mark.unit
@pytest.mark.coaching
def test_resolve_query():
    # Запрос информации
    action = resolve_action("покажи мои цели", make_ctx())
    assert action.action == ActionType.QUERY


@pytest.mark.unit
@pytest.mark.coaching
def test_resolve_no_context_returns_action():
    # Без контекста — должны получить ResolvedAction (не None)
    action = resolve_action("привет", None)
    assert action is not None
    assert hasattr(action, "action")
    assert hasattr(action, "confidence")


@pytest.mark.unit
@pytest.mark.coaching
def test_resolve_confidence_range():
    # confidence всегда в диапазоне 0.0–1.0
    for text in ["да", "нет", "ок", "отмена", "покажи", "что там", "привет"]:
        action = resolve_action(text, make_ctx())
        assert 0.0 <= action.confidence <= 1.0


@pytest.mark.unit
@pytest.mark.coaching
def test_resolve_returns_resolved_action():
    # resolve_action всегда возвращает ResolvedAction с полем action
    action = resolve_action("непонятная фраза", make_ctx())
    assert action.action in list(ActionType)
