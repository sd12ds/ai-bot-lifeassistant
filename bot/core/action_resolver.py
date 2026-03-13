"""
Chat Action Resolver — определяет намерение пользователя
относительно текущего контекста сессии.

Rule-based (regex + эвристики), без LLM. Быстро и предсказуемо.
Работает с любым доменом — не содержит nutrition/fitness-специфичного кода.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from bot.core.session_context import SessionContext

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Типы действий пользователя."""
    NEW_ENTITY = "new"          # Создать новую сущность
    EDIT_DRAFT = "edit"         # Правка текущего черновика
    CONFIRM = "confirm"         # Подтверждение («да», «ок», «сохрани»)
    DISCARD = "discard"         # Отмена («нет», «отмена», «не надо»)
    STATUS_CHECK = "status"     # Проверка статуса («записал?», «сохранил?»)
    QUERY = "query"             # Вопрос/статистика (не action)
    UNKNOWN = "unknown"         # Не определено — пусть агент решает


@dataclass
class ResolvedAction:
    """Результат определения намерения."""
    action: ActionType
    confidence: float = 0.5     # 0.0 - 1.0
    domain: str = ""            # "nutrition" | "fitness" | "tasks" | ""
    details: dict[str, Any] = field(default_factory=dict)


# ── Паттерны для определения намерений ──────────────────────────────────────

# Подтверждение
_CONFIRM_PATTERNS = re.compile(
    r"^(да|ок|окей|ok|yes|верно|правильно|сохрани|сохраняй|"
    r"записывай|записи|запиши|подтверждаю|всё верно|все верно|"
    r"точно|именно|ага|угу|давай|го|лан|ладно|принято|"
    r"✅|👍|сохранить|подтвердить)\.?!?$",
    re.IGNORECASE,
)

# Отмена
_DISCARD_PATTERNS = re.compile(
    r"^(нет|не надо|не нужно|отмена|отменяй|отмени|удали|"
    r"убери|не сохраняй|не записывай|забудь|забей|"
    r"❌|👎|отменить|cancel|нене)\.?!?$",
    re.IGNORECASE,
)

# Проверка статуса
_STATUS_CHECK_PATTERNS = re.compile(
    r"(записал[аи]?|сохранил[аи]?|занес|занёс|занесла|"
    r"зафиксировал|запомнил|сохранено|записано)\s*\??$",
    re.IGNORECASE,
)

# Вопрос / запрос информации
_QUERY_PATTERNS = re.compile(
    r"^(сколько|что|какой|какая|какие|покажи|статистика|"
    r"итоги|обзор|оценка|score|остаток|осталось|"
    r"сколько осталось|что ещё можно|что еще можно)\b",
    re.IGNORECASE,
)


def resolve_action(
    text: str,
    ctx: SessionContext | None,
) -> ResolvedAction:
    """
    Определяет намерение пользователя на основе текста и контекста.

    Args:
        text: текстовое сообщение пользователя
        ctx: текущий контекст сессии (может быть None)

    Returns:
        ResolvedAction с типом действия и уверенностью
    """
    text_stripped = text.strip()
    text_lower = text_stripped.lower()
    has_draft = ctx is not None and ctx.draft is not None
    domain = ctx.active_domain if ctx else ""

    # 1. Подтверждение
    if _CONFIRM_PATTERNS.match(text_stripped):
        if has_draft:
            return ResolvedAction(
                action=ActionType.CONFIRM,
                confidence=0.95,
                domain=domain,
            )
        # Нет draft — возможно подтверждение чего-то другого
        return ResolvedAction(
            action=ActionType.CONFIRM,
            confidence=0.6,
            domain=domain,
        )

    # 2. Отмена
    if _DISCARD_PATTERNS.match(text_stripped):
        if has_draft:
            return ResolvedAction(
                action=ActionType.DISCARD,
                confidence=0.95,
                domain=domain,
            )
        return ResolvedAction(
            action=ActionType.DISCARD,
            confidence=0.5,
            domain=domain,
        )

    # 3. Проверка статуса
    if _STATUS_CHECK_PATTERNS.search(text_stripped):
        return ResolvedAction(
            action=ActionType.STATUS_CHECK,
            confidence=0.9,
            domain=domain,
        )

    # 4. Вопрос / запрос аналитики
    if _QUERY_PATTERNS.match(text_stripped):
        return ResolvedAction(
            action=ActionType.QUERY,
            confidence=0.8,
            domain=domain,
        )

    # 5. Есть активный draft + короткое сообщение → вероятно правка
    if has_draft and len(text_stripped) < 60:
        # Короткие фразы при активном draft — скорее всего правка
        # Примеры: «сыра 30г», «убери хлеб», «это обед», «добавь кофе»
        return ResolvedAction(
            action=ActionType.EDIT_DRAFT,
            confidence=0.7,
            domain=domain,
            details={"reason": "short_message_with_active_draft"},
        )

    # 6. Есть draft + длинное сообщение → неоднозначно
    if has_draft:
        return ResolvedAction(
            action=ActionType.UNKNOWN,
            confidence=0.4,
            domain=domain,
            details={"reason": "long_message_with_active_draft"},
        )

    # 7. Нет draft — скорее всего новая сущность или запрос
    return ResolvedAction(
        action=ActionType.UNKNOWN,
        confidence=0.3,
        domain="",
        details={"reason": "no_draft_context"},
    )
