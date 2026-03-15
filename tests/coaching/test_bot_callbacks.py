"""
Тесты Telegram-бот callback handlers для coaching-модуля.

Симулируем нажатие пользователем кнопок в боте:
- Цели: отметить достигнутой, заморозить, возобновить, перезапустить
- Привычки: залогировать, пропустить, поставить на паузу, статистика
- Онбординг: пропустить, тон, время check-in, выбор области
- Управление flow: отмена, skip шагов
- Check-in: прогресс и энергия через кнопки
- Рекомендации: показать
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import User, Goal, Habit, HabitLog, UserCoachingProfile, CoachingOnboardingState


# ─── Хелперы ─────────────────────────────────────────────────────────────────

def make_cb(data: str, user_id: int) -> MagicMock:
    """Мок CallbackQuery с полным набором методов."""
    cb = MagicMock()
    cb.data = data
    cb.from_user = MagicMock()
    cb.from_user.id = user_id
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.message.edit_reply_markup = AsyncMock()
    cb.message.delete = AsyncMock()
    return cb


def make_state(initial_data: dict | None = None) -> MagicMock:
    """Мок FSMContext с аккумулятором данных."""
    state = MagicMock()
    _data: dict = dict(initial_data or {})

    async def _get_data():
        return dict(_data)

    async def _update_data(**kwargs):
        _data.update(kwargs)

    async def _set_state(s):
        state._current_state = s

    state.set_state = AsyncMock(side_effect=_set_state)
    state.get_data = AsyncMock(side_effect=_get_data)
    state.update_data = AsyncMock(side_effect=_update_data)
    state.clear = AsyncMock()
    state._current_state = None
    state._data = _data
    return state


def make_db_cm(session: AsyncSession) -> MagicMock:
    """Async context manager для патча get_async_session."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ══════════════════════════════════════════════════════════════════════════════
#  GOAL CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

class TestGoalCallbacks:
    """Нажатие кнопок в карточке цели."""

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_goal_done_marks_achieved_in_db(
        self, db_session: AsyncSession, test_user: User, one_goal: Goal
    ):
        """
        Пользователь нажимает «Цель достигнута» →
        goal.status == 'achieved', goal.progress_pct == 100, показывает поздравление.
        """
        from bot.handlers.coaching_handler import goal_done

        cb = make_cb(f"cg_g_done_{one_goal.id}", test_user.telegram_id)

        with patch("bot.handlers.coaching_handler.get_async_session", return_value=make_db_cm(db_session)):
            await goal_done(cb)

        # DB: статус изменился
        await db_session.refresh(one_goal)
        assert one_goal.status == "achieved"
        assert one_goal.progress_pct == 100

        # UX: поздравление показано
        cb.message.edit_text.assert_awaited_once()
        sent = cb.message.edit_text.call_args[0][0]
        assert "ДОСТИГНУТА" in sent or "🏆" in sent
        cb.answer.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_goal_freeze_sets_frozen(
        self, db_session: AsyncSession, test_user: User, one_goal: Goal
    ):
        """Пользователь замораживает цель → goal.is_frozen == True."""
        from bot.handlers.coaching_handler import goal_freeze

        cb = make_cb(f"cg_g_freeze_{one_goal.id}", test_user.telegram_id)

        with patch("bot.handlers.coaching_handler.get_async_session", return_value=make_db_cm(db_session)):
            await goal_freeze(cb)

        await db_session.refresh(one_goal)
        assert one_goal.is_frozen is True
        cb.answer.assert_awaited_once()
        # Текст ответа содержит 🧊 и название цели
        assert "🧊" in cb.answer.call_args[0][0]

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_goal_resume_unfreeze(
        self, db_session: AsyncSession, test_user: User, one_goal: Goal
    ):
        """Пользователь возобновляет замороженную цель → goal.is_frozen == False."""
        from bot.handlers.coaching_handler import goal_resume

        # Предварительно заморозим
        one_goal.is_frozen = True
        await db_session.commit()

        cb = make_cb(f"cg_g_resume_{one_goal.id}", test_user.telegram_id)

        with patch("bot.handlers.coaching_handler.get_async_session", return_value=make_db_cm(db_session)):
            await goal_resume(cb)

        await db_session.refresh(one_goal)
        assert one_goal.is_frozen is False
        assert "▶️" in cb.answer.call_args[0][0]

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_goal_restart_resets_progress(
        self, db_session: AsyncSession, test_user: User, one_goal: Goal
    ):
        """Пользователь перезапускает цель → progress_pct = 0, status = active."""
        from bot.handlers.coaching_handler import goal_restart

        one_goal.progress_pct = 75
        one_goal.status = "paused"
        await db_session.commit()

        cb = make_cb(f"cg_g_restart_{one_goal.id}", test_user.telegram_id)

        with patch("bot.handlers.coaching_handler.get_async_session", return_value=make_db_cm(db_session)):
            await goal_restart(cb)

        await db_session.refresh(one_goal)
        assert one_goal.progress_pct == 0
        assert one_goal.status == "active"
        assert "🔄" in cb.answer.call_args[0][0]

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_goal_done_not_found_no_crash(
        self, db_session: AsyncSession, test_user: User
    ):
        """Кнопка для несуществующей цели → нет crash (None goal)."""
        from bot.handlers.coaching_handler import goal_done

        cb = make_cb("cg_g_done_99999", test_user.telegram_id)

        with patch("bot.handlers.coaching_handler.get_async_session", return_value=make_db_cm(db_session)):
            # Не должно выбрасывать исключение
            await goal_done(cb)


# ══════════════════════════════════════════════════════════════════════════════
#  HABIT CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

class TestHabitCallbacks:
    """Нажатие кнопок в карточке привычки."""

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_habit_log_increments_streak_and_creates_log(
        self, db_session: AsyncSession, test_user: User, one_habit: Habit
    ):
        """
        Пользователь нажимает ✅ (выполнено) →
        current_streak++, HabitLog создаётся в DB.
        """
        from bot.handlers.coaching_handler import habit_log

        initial_streak = one_habit.current_streak
        cb = make_cb(f"cg_h_log_{one_habit.id}", test_user.telegram_id)

        with patch("bot.handlers.coaching_handler.get_async_session", return_value=make_db_cm(db_session)):
            await habit_log(cb)

        await db_session.refresh(one_habit)
        assert one_habit.current_streak == initial_streak + 1

        # HabitLog создан
        result = await db_session.execute(
            select(HabitLog).where(
                HabitLog.habit_id == one_habit.id,
                HabitLog.user_id == test_user.telegram_id,
            )
        )
        logs = result.scalars().all()
        assert len(logs) >= 1
        cb.answer.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_habit_log_new_record_sends_message(
        self, db_session: AsyncSession, test_user: User, one_habit: Habit
    ):
        """
        Когда current_streak == longest_streak → новый рекорд!
        Отправляется сообщение (не только ответ на колбэк).
        """
        from bot.handlers.coaching_handler import habit_log

        # Настраиваем: текущий стрик = рекорд → при инкременте будет новый рекорд
        one_habit.current_streak = 10
        one_habit.longest_streak = 10
        await db_session.commit()

        cb = make_cb(f"cg_h_log_{one_habit.id}", test_user.telegram_id)

        with patch("bot.handlers.coaching_handler.get_async_session", return_value=make_db_cm(db_session)):
            await habit_log(cb)

        await db_session.refresh(one_habit)
        assert one_habit.current_streak == 11
        assert one_habit.longest_streak == 11
        # Сообщение о рекорде отправлено
        cb.message.answer.assert_awaited_once()
        sent = cb.message.answer.call_args[0][0]
        assert "рекорд" in sent.lower() or "🏆" in sent

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_habit_miss_resets_streak(
        self, db_session: AsyncSession, test_user: User, one_habit: Habit
    ):
        """
        Пользователь нажимает «Пропуск» →
        streak сбрасывается до 0, отправляется сообщение поддержки.
        """
        from bot.handlers.coaching_handler import habit_miss

        one_habit.current_streak = 7
        await db_session.commit()

        cb = make_cb(f"cg_h_miss_{one_habit.id}", test_user.telegram_id)

        with patch("bot.handlers.coaching_handler.get_async_session", return_value=make_db_cm(db_session)):
            await habit_miss(cb)

        await db_session.refresh(one_habit)
        assert one_habit.current_streak == 0
        cb.message.answer.assert_awaited_once()
        sent = cb.message.answer.call_args[0][0]
        assert "пропуск" in sent.lower() or "Пропуск" in sent

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_habit_pause_deactivates(
        self, db_session: AsyncSession, test_user: User, one_habit: Habit
    ):
        """Пауза привычки → is_active = False в DB."""
        from bot.handlers.coaching_handler import habit_pause

        cb = make_cb(f"cg_h_pause_{one_habit.id}", test_user.telegram_id)

        with patch("bot.handlers.coaching_handler.get_async_session", return_value=make_db_cm(db_session)):
            await habit_pause(cb)

        await db_session.refresh(one_habit)
        assert one_habit.is_active is False
        cb.answer.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_habit_stats_shows_streak_info(
        self, db_session: AsyncSession, test_user: User, one_habit: Habit
    ):
        """Статистика привычки показывает streak, рекорд, выполнения."""
        from bot.handlers.coaching_handler import habit_stats

        one_habit.current_streak = 7
        one_habit.longest_streak = 15
        one_habit.total_completions = 42
        await db_session.commit()

        cb = make_cb(f"cg_h_stats_{one_habit.id}", test_user.telegram_id)

        with patch("bot.handlers.coaching_handler.get_async_session", return_value=make_db_cm(db_session)):
            await habit_stats(cb)

        cb.message.answer.assert_awaited_once()
        sent = cb.message.answer.call_args[0][0]
        assert "7" in sent   # current streak
        assert "15" in sent  # record
        assert "42" in sent  # completions


# ══════════════════════════════════════════════════════════════════════════════
#  ONBOARDING CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

class TestOnboardingCallbacks:
    """Шаги онбординга пользователя."""

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_ob_skip_marks_done(
        self, db_session: AsyncSession, test_user: User
    ):
        """
        Пользователь нажимает «Пропустить» онбординг →
        BotOnboardingState.bot_onboarding_done = True.
        """
        from bot.handlers.coaching_handler import ob_skip

        cb = make_cb("cg_ob_skip", test_user.telegram_id)

        with patch("bot.handlers.coaching_handler.get_async_session", return_value=make_db_cm(db_session)):
            await ob_skip(cb)

        # Проверяем что onboarding помечен как пройденный
        result = await db_session.execute(
            select(CoachingOnboardingState).where(
                CoachingOnboardingState.user_id == test_user.telegram_id
            )
        )
        ob = result.scalar_one_or_none()
        assert ob is not None
        assert ob.bot_onboarding_done is True

        cb.message.edit_text.assert_awaited_once()
        sent = cb.message.edit_text.call_args[0][0]
        assert "/coaching" in sent or "готов" in sent.lower()

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_ob_set_tone_saves_profile(
        self, db_session: AsyncSession, test_user: User
    ):
        """Выбор тона → coach_tone сохраняется в профиле, переходит к выбору времени."""
        from bot.handlers.coaching_handler import ob_set_tone

        cb = make_cb("cg_ob_tone_motivational", test_user.telegram_id)

        with patch("bot.handlers.coaching_handler.get_async_session", return_value=make_db_cm(db_session)):
            await ob_set_tone(cb)

        # Профиль обновлён
        result = await db_session.execute(
            select(UserCoachingProfile).where(
                UserCoachingProfile.user_id == test_user.telegram_id
            )
        )
        profile = result.scalar_one_or_none()
        assert profile is not None
        assert profile.coach_tone == "motivational"

        # Следующий шаг — выбор времени
        sent = cb.message.edit_text.call_args[0][0]
        assert "Мотивационный" in sent or "check-in" in sent.lower() or "напоминать" in sent.lower()

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_ob_set_time_completes_onboarding(
        self, db_session: AsyncSession, test_user: User
    ):
        """
        Выбор времени check-in → onboarding_completed = True,
        bot_onboarding_done = True, показывает финальное сообщение.
        """
        from bot.handlers.coaching_handler import ob_set_time

        cb = make_cb("cg_ob_time_20:00", test_user.telegram_id)

        with patch("bot.handlers.coaching_handler.get_async_session", return_value=make_db_cm(db_session)):
            await ob_set_time(cb)

        # Профиль помечен
        profile_r = await db_session.execute(
            select(UserCoachingProfile).where(
                UserCoachingProfile.user_id == test_user.telegram_id
            )
        )
        profile = profile_r.scalar_one_or_none()
        assert profile is not None
        assert profile.onboarding_completed is True
        assert profile.preferred_checkin_time == "20:00"

        # Онбординг в боте помечен
        ob_r = await db_session.execute(
            select(CoachingOnboardingState).where(
                CoachingOnboardingState.user_id == test_user.telegram_id
            )
        )
        ob = ob_r.scalar_one_or_none()
        assert ob is not None
        assert ob.bot_onboarding_done is True

        # Показана финальная страница
        sent = cb.message.edit_text.call_args[0][0]
        assert "Готово" in sent or "🎉" in sent

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_ob_toggle_focus_adds_area(
        self, db_session: AsyncSession, test_user: User
    ):
        """Выбор области health → добавляется в ob_focus_areas."""
        from bot.handlers.coaching_handler import ob_toggle_focus

        state = make_state({"ob_focus_areas": []})
        cb = make_cb("cg_ob_focus_health", test_user.telegram_id)

        await ob_toggle_focus(cb, state)

        assert "health" in state._data["ob_focus_areas"]
        cb.message.edit_reply_markup.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_ob_toggle_focus_removes_if_already_selected(
        self, db_session: AsyncSession, test_user: User
    ):
        """Повторный выбор области → убирает из списка (toggle)."""
        from bot.handlers.coaching_handler import ob_toggle_focus

        state = make_state({"ob_focus_areas": ["health", "finance"]})
        cb = make_cb("cg_ob_focus_health", test_user.telegram_id)

        await ob_toggle_focus(cb, state)

        assert "health" not in state._data["ob_focus_areas"]
        assert "finance" in state._data["ob_focus_areas"]

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_ob_focus_done_saves_areas(
        self, db_session: AsyncSession, test_user: User
    ):
        """ob_focus_done → сохраняет области в профиле, переходит к выбору тона."""
        from bot.handlers.coaching_handler import ob_focus_done

        state = make_state({"ob_focus_areas": ["health", "career"]})
        cb = make_cb("cg_ob_focus_done", test_user.telegram_id)

        with patch("bot.handlers.coaching_handler.get_async_session", return_value=make_db_cm(db_session)):
            await ob_focus_done(cb, state)

        # Профиль обновлён с focus_areas
        profile_r = await db_session.execute(
            select(UserCoachingProfile).where(
                UserCoachingProfile.user_id == test_user.telegram_id
            )
        )
        profile = profile_r.scalar_one_or_none()
        assert profile is not None
        assert "health" in (profile.focus_areas or [])

        # Переход к выбору тона
        sent = cb.message.edit_text.call_args[0][0]
        assert "тон" in sent.lower() or "общаться" in sent.lower()


# ══════════════════════════════════════════════════════════════════════════════
#  FLOW MANAGEMENT CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

class TestFlowCallbacks:
    """Управление flow (отмена, skip шагов)."""

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_cancel_flow_clears_state_and_drafts(
        self, db_session: AsyncSession, test_user: User
    ):
        """Отмена flow → state очищается, черновики удалены."""
        from bot.handlers.coaching_handler import cancel_flow

        state = make_state({"goal_draft": {"area": "health", "title": "Тест"}})
        cb = make_cb("cg_flow_cancel", test_user.telegram_id)

        with patch("bot.handlers.coaching_handler.get_async_session", return_value=make_db_cm(db_session)):
            with patch("bot.handlers.coaching_handler.cs.delete_draft", new_callable=AsyncMock):
                await cancel_flow(cb, state)

        state.clear.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()
        sent = cb.message.edit_text.call_args[0][0]
        assert "Отменено" in sent or "❌" in sent
        cb.answer.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_skip_goal_why_advances_to_first_step(
        self, db_session: AsyncSession, test_user: User
    ):
        """Пропуск шага 'зачем' → состояние → waiting_first_step."""
        from bot.handlers.coaching_handler import skip_goal_why
        from bot.states import CoachingGoalCreation

        state = make_state()
        cb = make_cb("cg_flow_skip_why", test_user.telegram_id)

        await skip_goal_why(cb, state)

        assert state._current_state == CoachingGoalCreation.waiting_first_step
        cb.message.edit_text.assert_awaited_once()
        sent = cb.message.edit_text.call_args[0][0]
        assert "Шаг 4" in sent or "первый шаг" in sent.lower()

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_skip_goal_deadline_creates_goal(
        self, db_session: AsyncSession, test_user: User
    ):
        """
        Пропуск шага дедлайна → goal создаётся без target_date.
        """
        from bot.handlers.coaching_handler import skip_goal_deadline

        state = make_state({"goal_draft": {
            "area": "fitness", "title": "Пробежать 5км",
            "why_statement": "Здоровье", "first_step": "Найти маршрут"
        }})
        cb = make_cb("cg_flow_skip_deadline", test_user.telegram_id)

        db_cm = make_db_cm(db_session)
        with patch("bot.handlers.coaching_handler.get_async_session", return_value=db_cm):
            with patch("bot.flows.coaching_flows.get_async_session", return_value=db_cm):
                with patch("bot.flows.coaching_flows.cs.delete_draft", new_callable=AsyncMock):
                    await skip_goal_deadline(cb, state)

        # Goal создан без дедлайна
        result = await db_session.execute(
            select(Goal).where(
                Goal.user_id == test_user.telegram_id,
                Goal.title == "Пробежать 5км"
            )
        )
        goal = result.scalar_one_or_none()
        assert goal is not None
        assert goal.target_date is None

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_skip_checkin_wins_advances_to_progress(
        self, db_session: AsyncSession, test_user: User
    ):
        """Пропуск ввода побед → переход к шагу прогресса."""
        from bot.handlers.coaching_handler import skip_checkin_wins
        from bot.states import CoachingCheckIn

        state = make_state({"checkin_draft": {"goal_id": 0}})
        cb = make_cb("cg_flow_skip_wins", test_user.telegram_id)

        await skip_checkin_wins(cb, state)

        assert state._current_state == CoachingCheckIn.waiting_progress
        cb.message.edit_text.assert_awaited_once()
        sent = cb.message.edit_text.call_args[0][0]
        assert "Прогресс" in sent or "%" in sent


# ══════════════════════════════════════════════════════════════════════════════
#  CHECK-IN QUICK BUTTONS
# ══════════════════════════════════════════════════════════════════════════════

class TestCheckinCallbacks:
    """Быстрые кнопки прогресса и энергии в check-in."""

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_checkin_progress_cb_25(
        self, db_session: AsyncSession, test_user: User
    ):
        """Нажатие кнопки 25% → draft.progress_pct = 25."""
        from bot.handlers.coaching_handler import checkin_progress_cb
        from bot.states import CoachingCheckIn

        state = make_state({"checkin_draft": {"goal_id": 0, "wins": "Победы"}})
        cb = make_cb("cg_ci_p25_0", test_user.telegram_id)

        await checkin_progress_cb(cb, state)

        assert state._data["checkin_draft"]["progress_pct"] == 25
        assert state._current_state == CoachingCheckIn.waiting_energy

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_checkin_progress_cb_100(
        self, db_session: AsyncSession, test_user: User
    ):
        """Нажатие кнопки 100% → draft.progress_pct = 100."""
        from bot.handlers.coaching_handler import checkin_progress_cb

        state = make_state({"checkin_draft": {"goal_id": 0}})
        cb = make_cb("cg_ci_p100_0", test_user.telegram_id)

        await checkin_progress_cb(cb, state)

        assert state._data["checkin_draft"]["progress_pct"] == 100

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_checkin_energy_cb_5(
        self, db_session: AsyncSession, test_user: User
    ):
        """Нажатие кнопки энергии 5 → draft.energy_level = 5, переход к blockers."""
        from bot.handlers.coaching_handler import checkin_energy_cb
        from bot.states import CoachingCheckIn

        state = make_state({"checkin_draft": {"goal_id": 0, "progress_pct": 70}})
        cb = make_cb("cg_ci_e5_0", test_user.telegram_id)

        await checkin_energy_cb(cb, state)

        assert state._data["checkin_draft"]["energy_level"] == 5
        assert state._current_state == CoachingCheckIn.waiting_blockers

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_checkin_progress_manual_input_mode(
        self, db_session: AsyncSession, test_user: User
    ):
        """
        Кнопка «Ввести вручную» (cg_ci_pman_0) →
        переводит в состояние ожидания числа.
        """
        from bot.handlers.coaching_handler import checkin_progress_cb
        from bot.states import CoachingCheckIn

        state = make_state({"checkin_draft": {"goal_id": 0}})
        cb = make_cb("cg_ci_pman_0", test_user.telegram_id)

        await checkin_progress_cb(cb, state)

        # Ожидаем ручной ввод
        assert state._current_state == CoachingCheckIn.waiting_progress
        cb.message.edit_text.assert_awaited_once()


# ══════════════════════════════════════════════════════════════════════════════
#  RECOMMENDATIONS CALLBACK
# ══════════════════════════════════════════════════════════════════════════════

class TestRecommendationsCallback:

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_show_recs_empty_state_gives_positive_ack(
        self, db_session: AsyncSession, test_user: User
    ):
        """Нет рекомендаций → отвечает на callback с позитивным текстом."""
        from bot.handlers.coaching_handler import show_recommendations

        cb = make_cb("cg_recs", test_user.telegram_id)

        with patch("bot.handlers.coaching_handler.get_async_session", return_value=make_db_cm(db_session)):
            await show_recommendations(cb)

        cb.answer.assert_awaited_once()
        ack_text = cb.answer.call_args[0][0]
        assert "💪" in ack_text or "пока нет" in ack_text.lower()

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_show_recs_with_data_sends_message(
        self, db_session: AsyncSession, test_user: User, active_recommendations
    ):
        """Есть рекомендации → отправляет сообщение со списком."""
        from bot.handlers.coaching_handler import show_recommendations

        cb = make_cb("cg_recs", test_user.telegram_id)

        with patch("bot.handlers.coaching_handler.get_async_session", return_value=make_db_cm(db_session)):
            await show_recommendations(cb)

        cb.message.answer.assert_awaited_once()
        sent = cb.message.answer.call_args[0][0]
        assert "рекомендац" in sent.lower() or "📌" in sent
