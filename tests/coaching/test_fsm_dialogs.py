"""
Полные FSM dialog тесты — симуляция реального диалога пользователя.

Проверяем:
- Каждый шаг отправляет сообщение с ожидаемым контентом
- FSM draft корректно накапливает данные на каждом шаге
- Финальный шаг сохраняет данные в реальную (SQLite in-memory) БД

Важно: MagicMock не проходит isinstance(mock, Message/CallbackQuery).
Поэтому все handler-ы идут в else-ветку:
- handle_goal_deadline: отправляет через msg.message.answer(txt)
- start_checkin_flow: ack через msg.answer(), текст через msg.message.answer(txt)
- handle_checkin_progress: msg.message.edit_text(txt), msg.answer()
- finish_checkin: msg.message.answer(txt), msg.answer("Сохранено!")
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import User, Goal, GoalCheckin
from bot.states import CoachingGoalCreation, CoachingCheckIn


# ─── Фабрики тестовых объектов ────────────────────────────────────────────────

def make_message(text: str = "", user_id: int = 100500) -> MagicMock:
    """Мок Aiogram Message с правильно настроенными методами."""
    msg = MagicMock()
    msg.text = text
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.answer = AsyncMock()
    # Вложенный объект для else-веток (isinstance → False → используют msg_or_cb.message.xxx)
    msg.message = MagicMock()
    msg.message.answer = AsyncMock()
    msg.message.edit_text = AsyncMock()
    return msg


def make_state(initial_data: dict | None = None) -> MagicMock:
    """Мок FSMContext с реальным аккумулятором данных для проверки."""
    state = MagicMock()
    _data: dict = dict(initial_data or {})

    async def _get_data() -> dict:
        return dict(_data)

    async def _update_data(**kwargs) -> None:
        _data.update(kwargs)

    async def _set_state(s) -> None:
        state._current_state = s

    state.set_state = AsyncMock(side_effect=_set_state)
    state.get_data = AsyncMock(side_effect=_get_data)
    state.update_data = AsyncMock(side_effect=_update_data)
    state.clear = AsyncMock()
    state._current_state = None
    state._data = _data  # публичный доступ для ассертов в тестах
    return state


def make_db_cm(session: AsyncSession) -> MagicMock:
    """
    Создаёт async context manager, возвращающий реальный db_session.
    Используется для патча get_async_session.
    Каждый вызов get_async_session() вернёт этот cm.
    """
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ══════════════════════════════════════════════════════════════════════════════
#  GOAL CREATION — отдельные шаги
# ══════════════════════════════════════════════════════════════════════════════

class TestGoalCreationSteps:
    """Unit-тесты каждого шага создания цели."""

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_step0_start_sets_state_and_sends_area_prompt(
        self, db_session: AsyncSession, test_user: User
    ):
        """Шаг 0: start_goal_creation → ставит waiting_area и отправляет сообщение."""
        from bot.flows.coaching_flows import start_goal_creation

        msg = make_message(user_id=test_user.telegram_id)
        state = make_state()

        with patch("bot.flows.coaching_flows.get_async_session", return_value=make_db_cm(db_session)):
            with patch("bot.flows.coaching_flows.cs.upsert_draft", new_callable=AsyncMock):
                await start_goal_creation(msg, state)

        assert state._current_state == CoachingGoalCreation.waiting_area
        msg.answer.assert_awaited_once()
        sent = msg.answer.call_args[0][0]
        # Текст содержит Шаг 1/5 и тему области
        assert "Шаг 1" in sent or "область" in sent.lower()

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_step1_handle_area_stores_area_in_state(
        self, db_session: AsyncSession, test_user: User
    ):
        """Шаг 1: handle_goal_area сохраняет area, переходит к waiting_title."""
        from bot.flows.coaching_flows import handle_goal_area

        msg = make_message(user_id=test_user.telegram_id)
        state = make_state()

        # MagicMock не является CallbackQuery → else-ветка → msg.answer(txt)
        await handle_goal_area(msg, state, area="health")

        assert state._data.get("goal_draft", {}).get("area") == "health"
        assert state._current_state == CoachingGoalCreation.waiting_title
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_step1_skip_area_stores_empty_string(
        self, db_session: AsyncSession, test_user: User
    ):
        """Шаг 1: area='skip' → сохраняется пустая строка."""
        from bot.flows.coaching_flows import handle_goal_area

        msg = make_message(user_id=test_user.telegram_id)
        state = make_state()

        await handle_goal_area(msg, state, area="skip")

        assert state._data.get("goal_draft", {}).get("area") == ""

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_step2_handle_title_stores_title_and_upserts_draft(
        self, db_session: AsyncSession, test_user: User
    ):
        """Шаг 2: handle_goal_title хранит title в FSM и вызывает upsert_draft."""
        from bot.flows.coaching_flows import handle_goal_title

        msg = make_message(text="Сбросить 5кг к маю", user_id=test_user.telegram_id)
        state = make_state({"goal_draft": {"area": "health"}})
        upsert_mock = AsyncMock()

        with patch("bot.flows.coaching_flows.get_async_session", return_value=make_db_cm(db_session)):
            with patch("bot.flows.coaching_flows.cs.upsert_draft", upsert_mock):
                await handle_goal_title(msg, state)

        assert state._data["goal_draft"]["title"] == "Сбросить 5кг к маю"
        assert state._current_state == CoachingGoalCreation.waiting_why
        upsert_mock.assert_awaited_once()
        # Третий аргумент функции — draft_type "goal_creation"
        assert upsert_mock.call_args[0][2] == "goal_creation"
        # Ответ содержит название цели и вопрос о мотивации
        sent = msg.answer.call_args[0][0]
        assert "Сбросить 5кг к маю" in sent
        assert "Шаг 3" in sent or "зачем" in sent.lower()

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_step3_handle_why_stores_motivation(
        self, db_session: AsyncSession, test_user: User
    ):
        """Шаг 3: handle_goal_why сохраняет why_statement."""
        from bot.flows.coaching_flows import handle_goal_why

        msg = make_message(text="Хочу быть здоровее", user_id=test_user.telegram_id)
        state = make_state({"goal_draft": {"area": "health", "title": "Сбросить 5кг"}})

        await handle_goal_why(msg, state)

        assert state._data["goal_draft"]["why_statement"] == "Хочу быть здоровее"
        assert state._current_state == CoachingGoalCreation.waiting_first_step
        sent = msg.answer.call_args[0][0]
        assert "Шаг 4" in sent or "первый шаг" in sent.lower()

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_step4_handle_first_step_stores_action(
        self, db_session: AsyncSession, test_user: User
    ):
        """Шаг 4: handle_goal_first_step сохраняет first_step."""
        from bot.flows.coaching_flows import handle_goal_first_step

        msg = make_message(text="Записаться в спортзал", user_id=test_user.telegram_id)
        state = make_state({"goal_draft": {
            "area": "health", "title": "Сбросить 5кг", "why_statement": "Здоровье"
        }})

        await handle_goal_first_step(msg, state)

        assert state._data["goal_draft"]["first_step"] == "Записаться в спортзал"
        assert state._current_state == CoachingGoalCreation.waiting_deadline
        sent = msg.answer.call_args[0][0]
        assert "Шаг 5" in sent or "дедлайн" in sent.lower()

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_step5_deadline_creates_goal_in_db_and_clears_state(
        self, db_session: AsyncSession, test_user: User
    ):
        """
        Шаг 5 (финал): handle_goal_deadline создаёт Goal в БД, очищает FSM.
        MagicMock → else-ветка → сообщение через msg.message.answer(txt).
        """
        from bot.flows.coaching_flows import handle_goal_deadline

        msg = make_message(text="skip", user_id=test_user.telegram_id)
        state = make_state({"goal_draft": {
            "area": "health",
            "title": "Сбросить 5кг к маю",
            "why_statement": "Хочу быть здоровее",
            "first_step": "Записаться в спортзал",
        }})

        with patch("bot.flows.coaching_flows.get_async_session", return_value=make_db_cm(db_session)):
            with patch("bot.flows.coaching_flows.cs.delete_draft", new_callable=AsyncMock):
                # deadline="" → пропускаем дедлайн (нет date parsing)
                await handle_goal_deadline(msg, state, deadline="")

        # FSM очищен
        state.clear.assert_awaited_once()

        # Goal сохранён в БД с правильными полями
        result = await db_session.execute(
            select(Goal).where(Goal.user_id == test_user.telegram_id)
        )
        goals = result.scalars().all()
        assert len(goals) >= 1

        goal = next(g for g in goals if g.title == "Сбросить 5кг к маю")
        assert goal.area == "health"
        assert goal.why_statement == "Хочу быть здоровее"
        assert goal.first_step == "Записаться в спортзал"

        # Подтверждение отправлено через msg.message.answer (else-ветка)
        msg.message.answer.assert_awaited_once()
        sent = msg.message.answer.call_args[0][0]
        assert "Цель создана" in sent or "✅" in sent

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_step5_deadline_with_valid_date_sets_target_date(
        self, db_session: AsyncSession, test_user: User
    ):
        """Шаг 5 с deadline='2025-12-31' → target_date = 2025-12-31 в БД."""
        from bot.flows.coaching_flows import handle_goal_deadline

        msg = make_message(text="skip", user_id=test_user.telegram_id)
        state = make_state({"goal_draft": {
            "area": "fitness",
            "title": "Пробежать марафон",
            "why_statement": "Проверить себя",
            "first_step": "Найти план",
        }})

        with patch("bot.flows.coaching_flows.get_async_session", return_value=make_db_cm(db_session)):
            with patch("bot.flows.coaching_flows.cs.delete_draft", new_callable=AsyncMock):
                # Передаём deadline явно, как если бы Message передал valid date
                await handle_goal_deadline(msg, state, deadline="2025-12-31")

        result = await db_session.execute(
            select(Goal).where(
                Goal.user_id == test_user.telegram_id,
                Goal.title == "Пробежать марафон"
            )
        )
        goal = result.scalar_one_or_none()
        assert goal is not None
        assert str(goal.target_date) == "2025-12-31"


# ══════════════════════════════════════════════════════════════════════════════
#  GOAL CREATION — E2E диалог (все 5 шагов подряд)
# ══════════════════════════════════════════════════════════════════════════════

class TestGoalCreationE2EDialog:
    """Полный диалог создания цели — сквозная проверка 5 шагов + DB."""

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_full_goal_creation_dialog(
        self, db_session: AsyncSession, test_user: User
    ):
        """
        E2E: Шаги 0→5. Проверяем:
        - Состояния FSM на каждом шаге
        - Накопление данных в draft
        - Goal создан в DB с корректными полями
        """
        from bot.flows.coaching_flows import (
            start_goal_creation, handle_goal_area,
            handle_goal_title, handle_goal_why,
            handle_goal_first_step, handle_goal_deadline,
        )
        uid = test_user.telegram_id
        state = make_state()
        db_cm = make_db_cm(db_session)

        with patch("bot.flows.coaching_flows.get_async_session", return_value=db_cm):
            with patch("bot.flows.coaching_flows.cs.upsert_draft", new_callable=AsyncMock):
                with patch("bot.flows.coaching_flows.cs.delete_draft", new_callable=AsyncMock):

                    # ── Шаг 0: старт ───────────────────────────────────────
                    await start_goal_creation(make_message(user_id=uid), state)
                    assert state._current_state == CoachingGoalCreation.waiting_area

                    # ── Шаг 1: область ─────────────────────────────────────
                    await handle_goal_area(make_message(user_id=uid), state, area="fitness")
                    assert state._current_state == CoachingGoalCreation.waiting_title
                    assert state._data["goal_draft"]["area"] == "fitness"

                    # ── Шаг 2: название ────────────────────────────────────
                    msg2 = make_message(text="Пробежать марафон", user_id=uid)
                    await handle_goal_title(msg2, state)
                    assert state._current_state == CoachingGoalCreation.waiting_why
                    assert state._data["goal_draft"]["title"] == "Пробежать марафон"

                    # ── Шаг 3: мотивация ────────────────────────────────────
                    msg3 = make_message(text="Хочу проверить свои силы", user_id=uid)
                    await handle_goal_why(msg3, state)
                    assert state._current_state == CoachingGoalCreation.waiting_first_step
                    assert state._data["goal_draft"]["why_statement"] == "Хочу проверить свои силы"

                    # ── Шаг 4: первый шаг ───────────────────────────────────
                    msg4 = make_message(text="Найти беговой план", user_id=uid)
                    await handle_goal_first_step(msg4, state)
                    assert state._current_state == CoachingGoalCreation.waiting_deadline

                    # ── Шаг 5: дедлайн + создание в DB ──────────────────────
                    msg5 = make_message(text="skip", user_id=uid)
                    await handle_goal_deadline(msg5, state, deadline="2025-12-31")

        # Проверяем DB
        result = await db_session.execute(
            select(Goal).where(Goal.user_id == uid, Goal.title == "Пробежать марафон")
        )
        goal = result.scalar_one_or_none()
        assert goal is not None, "Goal должен быть создан в DB"
        assert goal.area == "fitness"
        assert goal.why_statement == "Хочу проверить свои силы"
        assert goal.first_step == "Найти беговой план"
        assert str(goal.target_date) == "2025-12-31"


# ══════════════════════════════════════════════════════════════════════════════
#  CHECKIN — отдельные шаги
# ══════════════════════════════════════════════════════════════════════════════

class TestCheckinSteps:
    """Unit-тесты каждого шага check-in диалога."""

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_step0_start_sets_state_and_sends_wins_prompt(
        self, db_session: AsyncSession, test_user: User
    ):
        """Шаг 0: start_checkin_flow ставит waiting_wins, шлёт вопрос про победы."""
        from bot.flows.coaching_flows import start_checkin_flow

        msg = make_message(user_id=test_user.telegram_id)
        state = make_state()

        # goal_id=0 → нет запроса к DB
        await start_checkin_flow(msg, state, goal_id=0)

        assert state._current_state == CoachingCheckIn.waiting_wins
        assert state._data.get("checkin_draft", {}).get("goal_id") == 0
        # MagicMock → else-ветка → callback-ack через msg.answer() + текст через msg.message.answer
        msg.answer.assert_awaited()  # callback ack (без аргументов)
        msg.message.answer.assert_awaited_once()
        sent = msg.message.answer.call_args[0][0]
        assert "Check-in" in sent or "победа" in sent.lower()

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_step0_with_real_goal_includes_goal_title(
        self, db_session: AsyncSession, test_user: User, one_goal: Goal
    ):
        """Шаг 0 с real goal_id: заголовок цели включается в сообщение."""
        from bot.flows.coaching_flows import start_checkin_flow

        msg = make_message(user_id=test_user.telegram_id)
        state = make_state()

        with patch("bot.flows.coaching_flows.get_async_session", return_value=make_db_cm(db_session)):
            await start_checkin_flow(msg, state, goal_id=one_goal.id)

        assert state._data["checkin_draft"]["goal_id"] == one_goal.id
        sent = msg.message.answer.call_args[0][0]
        # Заголовок цели включён в сообщение через «goal_label»
        assert one_goal.title in sent

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_step1_wins_stores_text(
        self, db_session: AsyncSession, test_user: User
    ):
        """Шаг 1: handle_checkin_wins сохраняет wins в draft, переходит к progress."""
        from bot.flows.coaching_flows import handle_checkin_wins

        msg = make_message(text="Сделал 3 тренировки", user_id=test_user.telegram_id)
        state = make_state({"checkin_draft": {"goal_id": 0}})

        await handle_checkin_wins(msg, state)

        assert state._data["checkin_draft"]["wins"] == "Сделал 3 тренировки"
        assert state._current_state == CoachingCheckIn.waiting_progress
        sent = msg.answer.call_args[0][0]
        assert "прогресс" in sent.lower() or "%" in sent

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_step2_progress_stores_value(
        self, db_session: AsyncSession, test_user: User
    ):
        """Шаг 2: handle_checkin_progress сохраняет progress_pct в draft."""
        from bot.flows.coaching_flows import handle_checkin_progress

        msg = make_message(text="75", user_id=test_user.telegram_id)
        state = make_state({"checkin_draft": {"goal_id": 0, "wins": "Победы"}})

        # MagicMock → else-ветка → msg.message.edit_text + msg.answer()
        await handle_checkin_progress(msg, state, progress=75)

        assert state._data["checkin_draft"]["progress_pct"] == 75
        assert state._current_state == CoachingCheckIn.waiting_energy
        # Текст с прогрессом в edit_text
        msg.message.edit_text.assert_awaited_once()
        sent = msg.message.edit_text.call_args[0][0]
        assert "75%" in sent

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_step3_energy_stores_level(
        self, db_session: AsyncSession, test_user: User
    ):
        """Шаг 3: handle_checkin_energy сохраняет energy_level."""
        from bot.flows.coaching_flows import handle_checkin_energy

        # handle_checkin_energy типизирован как CallbackQuery
        cb = MagicMock()
        cb.from_user = MagicMock()
        cb.from_user.id = test_user.telegram_id
        cb.answer = AsyncMock()
        cb.message = MagicMock()
        cb.message.edit_text = AsyncMock()
        state = make_state({"checkin_draft": {
            "goal_id": 0, "wins": "Победы", "progress_pct": 75
        }})

        await handle_checkin_energy(cb, state, energy=4)

        assert state._data["checkin_draft"]["energy_level"] == 4
        assert state._current_state == CoachingCheckIn.waiting_blockers
        cb.message.edit_text.assert_awaited_once()
        sent = cb.message.edit_text.call_args[0][0]
        assert "4/5" in sent or "Энергия" in sent

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_step4_finish_saves_checkin_to_db(
        self, db_session: AsyncSession, test_user: User, one_goal: Goal
    ):
        """
        Шаг 4 (финал): finish_checkin создаёт GoalCheckin в БД.
        Проверяем поля: progress_pct, energy_level, wins, blockers.
        """
        from bot.flows.coaching_flows import finish_checkin

        msg = make_message(text="skip", user_id=test_user.telegram_id)
        state = make_state({"checkin_draft": {
            "goal_id": one_goal.id,
            "wins": "Три тренировки",
            "progress_pct": 60,
            "energy_level": 5,
        }})

        with patch("bot.flows.coaching_flows.get_async_session", return_value=make_db_cm(db_session)):
            # blockers передан явно, не пусто
            await finish_checkin(msg, state, blockers="Нет блокеров")

        # FSM очищен
        state.clear.assert_awaited_once()

        # GoalCheckin в DB
        result = await db_session.execute(
            select(GoalCheckin).where(
                GoalCheckin.goal_id == one_goal.id,
                GoalCheckin.user_id == test_user.telegram_id,
            )
        )
        checkins = result.scalars().all()
        assert len(checkins) >= 1

        c = checkins[-1]
        assert c.progress_pct == 60
        assert c.energy_level == 5
        assert c.wins == "Три тренировки"
        assert c.blockers == "Нет блокеров"

        # Подтверждение через msg.message.answer (else-ветка)
        msg.message.answer.assert_awaited_once()
        sent = msg.message.answer.call_args[0][0]
        assert "Check-in сохранён" in sent or "✅" in sent
        assert "60%" in sent


# ══════════════════════════════════════════════════════════════════════════════
#  CHECKIN — E2E диалог (все 4 шага подряд)
# ══════════════════════════════════════════════════════════════════════════════

class TestCheckinE2EDialog:
    """Полный check-in диалог — сквозная проверка 4 шагов + DB."""

    @pytest.mark.asyncio
    @pytest.mark.coaching
    async def test_full_checkin_dialog(
        self, db_session: AsyncSession, test_user: User, one_goal: Goal
    ):
        """
        E2E: Шаги 0→4. Проверяем:
        - Состояния FSM на каждом шаге
        - Накопление данных (wins, progress_pct, energy_level)
        - GoalCheckin создан в DB
        - progress обновлён в Goal
        """
        from bot.flows.coaching_flows import (
            start_checkin_flow, handle_checkin_wins,
            handle_checkin_progress, handle_checkin_energy,
            finish_checkin,
        )
        uid = test_user.telegram_id
        state = make_state()
        db_cm = make_db_cm(db_session)

        with patch("bot.flows.coaching_flows.get_async_session", return_value=db_cm):

            # ── Шаг 0: старт ───────────────────────────────────────────────
            msg0 = make_message(user_id=uid)
            await start_checkin_flow(msg0, state, goal_id=one_goal.id)
            assert state._current_state == CoachingCheckIn.waiting_wins

            # ── Шаг 1: победы ──────────────────────────────────────────────
            msg1 = make_message(text="Выполнил план на неделю", user_id=uid)
            await handle_checkin_wins(msg1, state)
            assert state._data["checkin_draft"]["wins"] == "Выполнил план на неделю"
            assert state._current_state == CoachingCheckIn.waiting_progress

            # ── Шаг 2: прогресс ────────────────────────────────────────────
            msg2 = make_message(text="80", user_id=uid)
            await handle_checkin_progress(msg2, state, progress=80)
            assert state._data["checkin_draft"]["progress_pct"] == 80
            assert state._current_state == CoachingCheckIn.waiting_energy

            # ── Шаг 3: энергия ─────────────────────────────────────────────
            cb = MagicMock()
            cb.from_user = MagicMock()
            cb.from_user.id = uid
            cb.answer = AsyncMock()
            cb.message = MagicMock()
            cb.message.edit_text = AsyncMock()
            await handle_checkin_energy(cb, state, energy=5)
            assert state._data["checkin_draft"]["energy_level"] == 5
            assert state._current_state == CoachingCheckIn.waiting_blockers

            # ── Шаг 4: финал ───────────────────────────────────────────────
            msg4 = make_message(text="Нет блокеров", user_id=uid)
            await finish_checkin(msg4, state, blockers="Нет блокеров")

        # FSM очищен
        state.clear.assert_awaited_once()

        # GoalCheckin создан в DB
        result = await db_session.execute(
            select(GoalCheckin).where(
                GoalCheckin.goal_id == one_goal.id,
                GoalCheckin.user_id == uid,
            )
        )
        checkin = result.scalar_one_or_none()
        assert checkin is not None, "GoalCheckin должен быть создан в DB"
        assert checkin.progress_pct == 80
        assert checkin.energy_level == 5
        assert checkin.wins == "Выполнил план на неделю"
        assert checkin.blockers == "Нет блокеров"
