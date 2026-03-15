"""
Тесты proactive-подсказок и генератора рекомендаций.

Проверяем:
1. check_quiet_hours()    — тихие часы (23:00-08:00 МСК)
2. select_top_nudge()     — приоритетный выбор NudgeCandidate
3. evaluate_triggers()    — ключевые триггеры C1, C2, H4 (streak risk)
4. generate_recommendations() — создание рекомендаций по рискам
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    User, Goal, Habit, GoalCheckin,
    CoachingRiskScore,
)

MSK = ZoneInfo("Europe/Moscow")


# ============================================================================
#  ТИХИЕ ЧАСЫ
# ============================================================================

class TestQuietHours:
    """check_quiet_hours() — тихие часы 23:00-08:00 МСК."""

    @pytest.mark.coaching
    def test_quiet_hours_at_night_returns_true(self):
        """02:00 МСК -> тихие часы."""
        from services.coaching_proactive import check_quiet_hours
        fake_now = datetime(2025, 3, 15, 2, 0, tzinfo=MSK)
        with patch("services.coaching_proactive.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.utcnow.return_value = datetime(2025, 3, 15, 23, 0)
            assert check_quiet_hours() is True

    @pytest.mark.coaching
    def test_quiet_hours_at_23_returns_true(self):
        """23:30 МСК -> тихие часы."""
        from services.coaching_proactive import check_quiet_hours
        fake_now = datetime(2025, 3, 15, 23, 30, tzinfo=MSK)
        with patch("services.coaching_proactive.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.utcnow.return_value = datetime(2025, 3, 15, 20, 30)
            assert check_quiet_hours() is True

    @pytest.mark.coaching
    def test_active_hours_at_noon_returns_false(self):
        """12:00 МСК -> активные часы."""
        from services.coaching_proactive import check_quiet_hours
        fake_now = datetime(2025, 3, 15, 12, 0, tzinfo=MSK)
        with patch("services.coaching_proactive.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.utcnow.return_value = datetime(2025, 3, 15, 9, 0)
            assert check_quiet_hours() is False

    @pytest.mark.coaching
    def test_active_hours_at_evening_returns_false(self):
        """20:00 МСК -> активные часы."""
        from services.coaching_proactive import check_quiet_hours
        fake_now = datetime(2025, 3, 15, 20, 0, tzinfo=MSK)
        with patch("services.coaching_proactive.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.utcnow.return_value = datetime(2025, 3, 15, 17, 0)
            assert check_quiet_hours() is False

    @pytest.mark.coaching
    def test_boundary_8am_is_active(self):
        """08:00 МСК — граница тихих часов, уже активные."""
        from services.coaching_proactive import check_quiet_hours
        fake_now = datetime(2025, 3, 15, 8, 0, tzinfo=MSK)
        with patch("services.coaching_proactive.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.utcnow.return_value = datetime(2025, 3, 15, 5, 0)
            assert check_quiet_hours() is False

    @pytest.mark.coaching
    def test_check_quiet_hours_returns_bool(self):
        """check_quiet_hours без патча возвращает bool без исключений."""
        from services.coaching_proactive import check_quiet_hours
        result = check_quiet_hours()
        assert isinstance(result, bool)


# ============================================================================
#  SELECT TOP NUDGE
# ============================================================================

class TestSelectTopNudge:
    """select_top_nudge() — приоритетный выбор NudgeCandidate из списка."""

    @pytest.mark.coaching
    def test_returns_critical_over_high(self):
        """CRITICAL выбирается раньше HIGH независимо от порядка."""
        from services.coaching_proactive import (
            select_top_nudge, NudgeCandidate, PRIORITY_CRITICAL, PRIORITY_HIGH,
        )
        candidates = [
            NudgeCandidate("high_nudge", PRIORITY_HIGH, "High text"),
            NudgeCandidate("critical_nudge", PRIORITY_CRITICAL, "Critical text"),
        ]
        result = select_top_nudge(candidates, already_sent_types=set())
        assert result is not None
        assert result.nudge_type == "critical_nudge"

    @pytest.mark.coaching
    def test_returns_high_over_medium(self):
        """HIGH выбирается раньше MEDIUM."""
        from services.coaching_proactive import (
            select_top_nudge, NudgeCandidate, PRIORITY_HIGH, PRIORITY_MEDIUM,
        )
        candidates = [
            NudgeCandidate("medium_nudge", PRIORITY_MEDIUM, "Medium"),
            NudgeCandidate("high_nudge", PRIORITY_HIGH, "High"),
        ]
        result = select_top_nudge(candidates, already_sent_types=set())
        assert result.nudge_type == "high_nudge"

    @pytest.mark.coaching
    def test_returns_medium_over_low(self):
        """MEDIUM выбирается раньше LOW."""
        from services.coaching_proactive import (
            select_top_nudge, NudgeCandidate, PRIORITY_MEDIUM, PRIORITY_LOW,
        )
        candidates = [
            NudgeCandidate("low_nudge", PRIORITY_LOW, "Low"),
            NudgeCandidate("medium_nudge", PRIORITY_MEDIUM, "Medium"),
        ]
        result = select_top_nudge(candidates, already_sent_types=set())
        assert result.nudge_type == "medium_nudge"

    @pytest.mark.coaching
    def test_skips_already_sent_types(self):
        """Уже отправленные типы исключаются из выбора."""
        from services.coaching_proactive import (
            select_top_nudge, NudgeCandidate, PRIORITY_HIGH, PRIORITY_MEDIUM,
        )
        candidates = [
            NudgeCandidate("already_sent", PRIORITY_HIGH, "High text"),
            NudgeCandidate("fresh_nudge", PRIORITY_MEDIUM, "Medium text"),
        ]
        result = select_top_nudge(candidates, already_sent_types={"already_sent"})
        assert result is not None
        assert result.nudge_type == "fresh_nudge"

    @pytest.mark.coaching
    def test_returns_none_if_all_sent(self):
        """Все кандидаты уже отправлены -> None."""
        from services.coaching_proactive import (
            select_top_nudge, NudgeCandidate, PRIORITY_HIGH,
        )
        candidates = [
            NudgeCandidate("a", PRIORITY_HIGH, "Text A"),
            NudgeCandidate("b", PRIORITY_HIGH, "Text B"),
        ]
        result = select_top_nudge(candidates, already_sent_types={"a", "b"})
        assert result is None

    @pytest.mark.coaching
    def test_returns_none_for_empty_candidates(self):
        """Пустой список кандидатов -> None."""
        from services.coaching_proactive import select_top_nudge
        result = select_top_nudge([], already_sent_types=set())
        assert result is None

    @pytest.mark.coaching
    def test_low_priority_selected_if_only_option(self):
        """LOW выбирается если нет более приоритетных."""
        from services.coaching_proactive import (
            select_top_nudge, NudgeCandidate, PRIORITY_LOW,
        )
        candidates = [NudgeCandidate("low_nudge", PRIORITY_LOW, "Low text")]
        result = select_top_nudge(candidates, already_sent_types=set())
        assert result.nudge_type == "low_nudge"

    @pytest.mark.coaching
    def test_first_critical_wins_among_criticals(self):
        """Среди нескольких CRITICAL берётся первый в списке."""
        from services.coaching_proactive import (
            select_top_nudge, NudgeCandidate, PRIORITY_CRITICAL,
        )
        candidates = [
            NudgeCandidate("c1", PRIORITY_CRITICAL, "First"),
            NudgeCandidate("c2", PRIORITY_CRITICAL, "Second"),
        ]
        result = select_top_nudge(candidates, already_sent_types=set())
        assert result.nudge_type == "c1"


# ============================================================================
#  EVALUATE TRIGGERS
# ============================================================================

class TestEvaluateTriggers:
    """evaluate_triggers() — проверка ключевых proactive-триггеров."""

    def _make_snapshot(self, **kwargs):
        """Создаёт мок CoachingContextSnapshot со всеми числовыми полями."""
        snap = MagicMock()
        snap.tasks_overdue = kwargs.get("tasks_overdue", 0)
        snap.habits_done_today = kwargs.get("habits_done_today", 0)
        snap.streak_at_risk = kwargs.get("streak_at_risk", 0)
        snap.stick_at_risk = kwargs.get("stick_at_risk", False)
        # Все числовые поля, используемые в evaluate_triggers сравнениях
        snap.calendar_events_today = kwargs.get("calendar_events_today", 0)
        snap.free_slots_today = kwargs.get("free_slots_today", 5)
        snap.stuck_goals = kwargs.get("stuck_goals", 0)
        snap.score = kwargs.get("score", 70)
        # Поля с getattr-доступом — нужно задать явно, иначе getattr вернёт MagicMock
        snap.no_fitness_days = kwargs.get("no_fitness_days", 0)
        snap.nutrition_streak = kwargs.get("nutrition_streak", 99)  # <3 не триггерить
        snap.task_completion_rate = kwargs.get("task_completion_rate", 0.5)
        return snap

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_c1_fires_when_no_checkins_exist(
        self, db_session: AsyncSession, test_user: User, one_goal: Goal
    ):
        """
        C1 (no_checkin_3days): пользователь с активной целью, без check-in
        -> триггер CRITICAL no_checkin_3days.
        """
        from services.coaching_proactive import evaluate_triggers, PRIORITY_CRITICAL

        candidates = await evaluate_triggers(
            session=db_session,
            user_id=test_user.telegram_id,
            snapshot=self._make_snapshot(),
            risks={"dropout": 0.3},
            state="stable",
        )

        types = [c.nudge_type for c in candidates]
        assert "no_checkin_3days" in types

        c1 = next(c for c in candidates if c.nudge_type == "no_checkin_3days")
        assert c1.priority == PRIORITY_CRITICAL

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_c1_not_fired_when_recent_checkin(
        self, db_session: AsyncSession, test_user: User, one_goal: Goal
    ):
        """
        C1: check-in 12 часов назад -> days_no_checkin = 0 -> нет триггера.
        """
        from services.coaching_proactive import evaluate_triggers

        checkin = GoalCheckin(
            goal_id=one_goal.id,
            user_id=test_user.telegram_id,
            progress_pct=50,
            energy_level=4,
            created_at=datetime.utcnow() - timedelta(hours=12),
        )
        db_session.add(checkin)
        await db_session.commit()

        candidates = await evaluate_triggers(
            session=db_session,
            user_id=test_user.telegram_id,
            snapshot=self._make_snapshot(),
            risks={},
            state="stable",
        )

        types = [c.nudge_type for c in candidates]
        assert "no_checkin_3days" not in types

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_c2_goal_achieved_fires(
        self, db_session: AsyncSession, test_user: User
    ):
        """
        C2 (goal_achieved): есть достигнутая цель -> триггер CRITICAL.
        """
        from services.coaching_proactive import evaluate_triggers, PRIORITY_CRITICAL
        from tests.factories import GoalFactory

        achieved_goal = GoalFactory.build(
            user_id=test_user.telegram_id,
            title="Achieved goal",
            status="achieved",
            progress_pct=100,
        )
        db_session.add(achieved_goal)
        await db_session.commit()

        candidates = await evaluate_triggers(
            session=db_session,
            user_id=test_user.telegram_id,
            snapshot=self._make_snapshot(),
            risks={},
            state="stable",
        )

        types = [c.nudge_type for c in candidates]
        assert "goal_achieved" in types

        c2 = next(c for c in candidates if c.nudge_type == "goal_achieved")
        assert c2.priority == PRIORITY_CRITICAL

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_habit_at_risk_fires_when_no_log_4_days(
        self, db_session: AsyncSession, test_user: User, one_habit: Habit
    ):
        """
        H4: привычка без лога 4 дня, стрик > 0 -> habit-related nudge.
        """
        from services.coaching_proactive import evaluate_triggers

        one_habit.last_logged_at = datetime.utcnow() - timedelta(days=4)
        one_habit.current_streak = 10
        await db_session.commit()

        candidates = await evaluate_triggers(
            session=db_session,
            user_id=test_user.telegram_id,
            snapshot=self._make_snapshot(streak_at_risk=1),
            risks={},
            state="stable",
        )

        types = [c.nudge_type for c in candidates]
        habit_nudges = [t for t in types if "habit" in t or "streak" in t]
        assert len(habit_nudges) > 0

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_no_c1_for_disciplined_user(
        self, db_session: AsyncSession, persona_disciplined: dict
    ):
        """
        Дисциплинированный пользователь (check-in вчера) -> нет C1.
        """
        from services.coaching_proactive import evaluate_triggers

        user = persona_disciplined["user"]

        candidates = await evaluate_triggers(
            session=db_session,
            user_id=user.telegram_id,
            snapshot=self._make_snapshot(),
            risks={"dropout": 0.1},
            state="momentum",
        )

        types = [c.nudge_type for c in candidates]
        assert "no_checkin_3days" not in types

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_many_triggers_for_dropout_user(
        self, db_session: AsyncSession, persona_dropout: dict
    ):
        """
        Дропаут-пользователь (нет check-in 14+ дней) -> C1 + другие триггеры.
        """
        from services.coaching_proactive import evaluate_triggers

        user = persona_dropout["user"]

        candidates = await evaluate_triggers(
            session=db_session,
            user_id=user.telegram_id,
            snapshot=self._make_snapshot(),
            risks={"dropout": 0.85},
            state="risk",
        )

        types = [c.nudge_type for c in candidates]
        assert "no_checkin_3days" in types
        assert len(candidates) >= 2


# ============================================================================
#  GENERATE RECOMMENDATIONS
# ============================================================================

class TestGenerateRecommendations:
    """generate_recommendations() — создание рекомендаций из риск-скоров."""

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_high_dropout_score_creates_rec(
        self, db_session: AsyncSession, test_user: User
    ):
        """
        dropout_score > 0.7 -> создаётся рекомендация dropout_reactivation.
        """
        from services.coaching_recommendations import generate_recommendations

        risk = CoachingRiskScore(
            user_id=test_user.telegram_id,
            risk_type="dropout",
            score=0.85,
        )
        db_session.add(risk)
        await db_session.commit()

        result = await generate_recommendations(db_session, test_user.telegram_id)

        assert len(result) >= 1
        rec_types = [r["rec_type"] for r in result]
        assert "dropout_reactivation" in rec_types

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_already_2_active_recs_skips_generation(
        self,
        db_session: AsyncSession,
        test_user: User,
        active_recommendations,
    ):
        """
        Уже есть 2 активные рекомендации -> возвращает [] (§17.2).
        """
        from services.coaching_recommendations import generate_recommendations

        result = await generate_recommendations(db_session, test_user.telegram_id)
        assert result == []

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_low_dropout_score_no_dropout_rec(
        self, db_session: AsyncSession, test_user: User
    ):
        """
        dropout_score < 0.7 -> НЕТ рекомендации dropout_reactivation.
        """
        from services.coaching_recommendations import generate_recommendations

        risk = CoachingRiskScore(
            user_id=test_user.telegram_id,
            risk_type="dropout",
            score=0.3,
        )
        db_session.add(risk)
        await db_session.commit()

        result = await generate_recommendations(db_session, test_user.telegram_id)

        rec_types = [r["rec_type"] for r in result]
        assert "dropout_reactivation" not in rec_types

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_no_risks_no_critical_recs(
        self, db_session: AsyncSession, test_user: User
    ):
        """
        Без риск-скоров -> нет критических рекомендаций.
        """
        from services.coaching_recommendations import generate_recommendations

        result = await generate_recommendations(db_session, test_user.telegram_id)

        rec_types = [r["rec_type"] for r in result]
        assert "dropout_reactivation" not in rec_types

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_recommendations_saved_to_db(
        self, db_session: AsyncSession, test_user: User
    ):
        """
        Созданные рекомендации сохраняются в БД.
        """
        from services.coaching_recommendations import generate_recommendations
        from db import coaching_storage as cs

        risk = CoachingRiskScore(
            user_id=test_user.telegram_id,
            risk_type="dropout",
            score=0.9,
        )
        db_session.add(risk)
        await db_session.commit()

        await generate_recommendations(db_session, test_user.telegram_id)

        saved = await cs.get_active_recommendations(db_session, test_user.telegram_id)
        assert len(saved) >= 1

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_overload_risk_creates_workload_rec(
        self, db_session: AsyncSession, test_user: User, daily_snapshot
    ):
        """
        overload_score > 0.6 + snapshot.tasks_overdue > 5 -> workload_reduce.
        """
        from services.coaching_recommendations import generate_recommendations
        from db import coaching_storage as cs
        from datetime import date

        await cs.upsert_snapshot(
            session=db_session,
            user_id=test_user.telegram_id,
            snapshot_date=date.today(),
            tasks_overdue=8,
            tasks_completed_today=1,
            calendar_events_today=0,
            free_slots_today=0,
            habits_done_today=0,
            habits_total_today=3,
            stuck_goals=2,
            streak_at_risk=0,
            overall_state="overload",
            score=30,
        )

        risk = CoachingRiskScore(
            user_id=test_user.telegram_id,
            risk_type="overload",
            score=0.8,
        )
        db_session.add(risk)
        await db_session.commit()

        result = await generate_recommendations(db_session, test_user.telegram_id)

        rec_types = [r["rec_type"] for r in result]
        assert "workload_reduce" in rec_types
