"""
Phase 4: Тесты session_context — SessionContext, get_context, set_draft, etc.
Тестируем in-memory хранилище сессий и TTL-логику.
"""
import pytest
from datetime import datetime, timedelta
from bot.core.session_context import (
    SessionContext, get_context, get_or_create_context,
    set_draft, clear_draft, _contexts,
)


def _clear_contexts():
    """Очищаем глобальное хранилище перед каждым тестом."""
    _contexts.clear()


@pytest.mark.unit
@pytest.mark.coaching
def test_get_or_create_context_creates_new():
    # Создаёт новый контекст для нового user_id
    _clear_contexts()
    ctx = get_or_create_context(user_id=111)
    assert ctx is not None
    assert ctx.user_id == 111


@pytest.mark.unit
@pytest.mark.coaching
def test_get_or_create_context_returns_existing():
    # Повторный вызов возвращает тот же объект
    _clear_contexts()
    ctx1 = get_or_create_context(user_id=222)
    ctx2 = get_or_create_context(user_id=222)
    assert ctx1 is ctx2


@pytest.mark.unit
@pytest.mark.coaching
def test_get_context_returns_none_for_unknown_user():
    # Для неизвестного пользователя возвращает None
    _clear_contexts()
    ctx = get_context(user_id=99999)
    assert ctx is None


@pytest.mark.unit
@pytest.mark.coaching
def test_get_or_create_context_sets_domain():
    # domain передаётся при создании контекста
    _clear_contexts()
    ctx = get_or_create_context(user_id=333, domain="coaching")
    assert ctx.active_domain == "coaching"


@pytest.mark.unit
@pytest.mark.coaching
def test_session_context_is_domain_sticky_false_by_default():
    # По умолчанию sticky-режим отключён
    ctx = SessionContext(user_id=444)
    assert ctx.is_domain_sticky() is False


@pytest.mark.unit
@pytest.mark.coaching
def test_activate_sticky_makes_domain_sticky():
    # activate_sticky включает sticky-режим
    ctx = SessionContext(user_id=555, active_domain="nutrition")
    ctx.activate_sticky(minutes=10)
    assert ctx.is_domain_sticky() is True


@pytest.mark.unit
@pytest.mark.coaching
def test_clear_sticky_disables_sticky():
    # clear_sticky отключает sticky-режим
    ctx = SessionContext(user_id=666, active_domain="fitness")
    ctx.activate_sticky(minutes=5)
    assert ctx.is_domain_sticky() is True
    ctx.clear_sticky()
    assert ctx.is_domain_sticky() is False


@pytest.mark.unit
@pytest.mark.coaching
def test_session_context_pending_confirmation_default_false():
    # pending_confirmation по умолчанию False
    ctx = SessionContext(user_id=777)
    assert ctx.pending_confirmation is False
