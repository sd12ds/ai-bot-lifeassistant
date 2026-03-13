"""
BaseDraft — абстрактный черновик сущности.

Универсальная основа для MealDraft, WorkoutDraft, TaskDraft и др.
Каждый домен наследует BaseDraft и добавляет свои поля.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from config import DEFAULT_TZ


class DraftStatus(str, Enum):
    """Статусы жизненного цикла черновика."""
    DRAFT = "draft"                             # Создан, ещё не показан пользователю
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # Ждёт подтверждения
    CONFIRMED = "confirmed"                     # Подтверждён, но ещё не сохранён
    SAVED = "saved"                             # Сохранён в БД
    DISCARDED = "discarded"                     # Отменён пользователем


@dataclass
class BaseDraft:
    """Универсальный черновик сущности."""
    draft_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    domain: str = ""                            # "nutrition" | "fitness" | "tasks"
    items: list[dict] = field(default_factory=list)  # Список элементов (продукты, упражнения, подзадачи)
    status: DraftStatus = DraftStatus.DRAFT
    source_type: str = "text"                   # photo | text | voice | mixed | clone
    meta: dict[str, Any] = field(default_factory=dict)  # Доменные данные (meal_type, workout_type...)
    version: int = 1                            # Номер версии (инкрементируется при update)
    created_at: datetime = field(default_factory=lambda: datetime.now(DEFAULT_TZ))
    updated_at: datetime = field(default_factory=lambda: datetime.now(DEFAULT_TZ))

    def recalc(self) -> None:
        """Пересчёт агрегатов — переопределяется в доменных наследниках."""
        self.updated_at = datetime.now(DEFAULT_TZ)

    def touch(self) -> None:
        """Обновить время последнего изменения."""
        self.updated_at = datetime.now(DEFAULT_TZ)
        self.version += 1
