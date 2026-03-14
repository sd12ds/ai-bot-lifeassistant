"""
Phase 4: Тесты coaching flows — FSM flow-функции.
Используем моки Aiogram (Message, FSMContext, CallbackQuery).
DB-сессия мокается через patch('bot.flows.coaching_flows.get_async_session').
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from bot.states import CoachingGoalCreation, CoachingHabitCreation, CoachingCheckIn


def make_message(text: str = "тест", user_id: int = 100500) -> MagicMock:
    """Создаёт мок Aiogram Message."""
    msg = MagicMock()
    msg.text = text
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.answer = AsyncMock()
    return msg


def make_state() -> MagicMock:
    """Создаёт мок Aiogram FSMContext."""
    state = MagicMock()
    state.set_state = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    state.update_data = AsyncMock()
    state.clear = AsyncMock()
    return state


def make_callback(data: str = "area:health", user_id: int = 100500) -> MagicMock:
    """Создаёт мок Aiogram CallbackQuery."""
    cb = MagicMock()
    cb.data = data
    cb.from_user = MagicMock()
    cb.from_user.id = user_id
    cb.answer = AsyncMock()
    cb.message = make_message(user_id=user_id)
    return cb


def make_mock_session():
    """Создаёт мок AsyncSession для DB."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


def make_mock_context_manager(session):
    """Создаёт контекстный менеджер для get_async_session()."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ══════════════════════════════════════════════════════════════════════════════
# GOAL CREATION FLOW
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.coaching
async def test_start_goal_creation_sets_state():
    """start_goal_creation устанавливает CoachingGoalCreation.waiting_area."""
    from bot.flows.coaching_flows import start_goal_creation
    msg = make_message()
    state = make_state()
    session = make_mock_session()
    # Мокируем cs.upsert_draft чтобы не падало
    with patch("bot.flows.coaching_flows.get_async_session", return_value=make_mock_context_manager(session)):
        with patch("bot.flows.coaching_flows.cs.upsert_draft", new_callable=AsyncMock):
            await start_goal_creation(msg, state)
    state.set_state.assert_awaited_once_with(CoachingGoalCreation.waiting_area)


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.coaching
async def test_start_goal_creation_sends_message():
    """start_goal_creation отправляет сообщение пользователю."""
    from bot.flows.coaching_flows import start_goal_creation
    msg = make_message()
    state = make_state()
    session = make_mock_session()
    with patch("bot.flows.coaching_flows.get_async_session", return_value=make_mock_context_manager(session)):
        with patch("bot.flows.coaching_flows.cs.upsert_draft", new_callable=AsyncMock):
            await start_goal_creation(msg, state)
    msg.answer.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.coaching
async def test_handle_goal_area_sets_title_state():
    """handle_goal_area переходит к CoachingGoalCreation.waiting_title."""
    from bot.flows.coaching_flows import handle_goal_area
    msg = make_message()
    state = make_state()
    state.get_data = AsyncMock(return_value={"draft": {}})
    session = make_mock_session()
    with patch("bot.flows.coaching_flows.get_async_session", return_value=make_mock_context_manager(session)):
        with patch("bot.flows.coaching_flows.cs.upsert_draft", new_callable=AsyncMock):
            await handle_goal_area(msg, state, area="health")
    state.set_state.assert_awaited_once_with(CoachingGoalCreation.waiting_title)


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.coaching
async def test_handle_goal_title_sets_why_state():
    """handle_goal_title переходит к CoachingGoalCreation.waiting_why."""
    from bot.flows.coaching_flows import handle_goal_title
    msg = make_message(text="Похудеть на 5кг")
    state = make_state()
    state.get_data = AsyncMock(return_value={"draft": {"area": "health"}})
    session = make_mock_session()
    with patch("bot.flows.coaching_flows.get_async_session", return_value=make_mock_context_manager(session)):
        with patch("bot.flows.coaching_flows.cs.upsert_draft", new_callable=AsyncMock):
            await handle_goal_title(msg, state)
    state.set_state.assert_awaited_once_with(CoachingGoalCreation.waiting_why)


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.coaching
async def test_handle_goal_why_sets_first_step_state():
    """handle_goal_why переходит к CoachingGoalCreation.waiting_first_step."""
    from bot.flows.coaching_flows import handle_goal_why
    msg = make_message(text="Хочу быть здоровее")
    state = make_state()
    state.get_data = AsyncMock(return_value={"draft": {"area": "health", "title": "Похудеть"}})
    session = make_mock_session()
    with patch("bot.flows.coaching_flows.get_async_session", return_value=make_mock_context_manager(session)):
        with patch("bot.flows.coaching_flows.cs.upsert_draft", new_callable=AsyncMock):
            await handle_goal_why(msg, state)
    state.set_state.assert_awaited_once_with(CoachingGoalCreation.waiting_first_step)


# ══════════════════════════════════════════════════════════════════════════════
# HABIT CREATION FLOW
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.coaching
async def test_start_habit_creation_sets_state():
    """start_habit_creation устанавливает CoachingHabitCreation.waiting_title."""
    from bot.flows.coaching_flows import start_habit_creation
    msg = make_message()
    state = make_state()
    session = make_mock_session()
    with patch("bot.flows.coaching_flows.get_async_session", return_value=make_mock_context_manager(session)):
        with patch("bot.flows.coaching_flows.cs.upsert_draft", new_callable=AsyncMock):
            await start_habit_creation(msg, state)
    state.set_state.assert_awaited_once_with(CoachingHabitCreation.waiting_title)


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.coaching
async def test_start_habit_creation_sends_message():
    """start_habit_creation отправляет сообщение пользователю."""
    from bot.flows.coaching_flows import start_habit_creation
    msg = make_message()
    state = make_state()
    session = make_mock_session()
    with patch("bot.flows.coaching_flows.get_async_session", return_value=make_mock_context_manager(session)):
        with patch("bot.flows.coaching_flows.cs.upsert_draft", new_callable=AsyncMock):
            await start_habit_creation(msg, state)
    msg.answer.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.coaching
async def test_handle_habit_title_sets_area_state():
    """handle_habit_title переходит к CoachingHabitCreation.waiting_area."""
    from bot.flows.coaching_flows import handle_habit_title
    msg = make_message(text="Медитация")
    state = make_state()
    state.get_data = AsyncMock(return_value={"draft": {}})
    session = make_mock_session()
    with patch("bot.flows.coaching_flows.get_async_session", return_value=make_mock_context_manager(session)):
        with patch("bot.flows.coaching_flows.cs.upsert_draft", new_callable=AsyncMock):
            await handle_habit_title(msg, state)
    state.set_state.assert_awaited_once_with(CoachingHabitCreation.waiting_area)


# ══════════════════════════════════════════════════════════════════════════════
# CHECKIN FLOW
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.coaching
async def test_start_checkin_flow_sets_wins_state():
    """start_checkin_flow устанавливает CoachingCheckIn.waiting_wins."""
    from bot.flows.coaching_flows import start_checkin_flow
    msg = make_message()
    state = make_state()
    msg.message = make_message()  # else-ветка: send = msg_or_cb.message.answer
    await start_checkin_flow(msg, state, goal_id=0)
    state.set_state.assert_awaited_once_with(CoachingCheckIn.waiting_wins)


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.coaching
async def test_start_checkin_flow_stores_goal_id():
    """start_checkin_flow сохраняет goal_id в FSM data."""
    from bot.flows.coaching_flows import start_checkin_flow
    msg = make_message()
    state = make_state()
    msg.message = make_message()  # else-ветка: send = msg_or_cb.message.answer
    await start_checkin_flow(msg, state, goal_id=0)
    state.update_data.assert_awaited_once_with(checkin_draft={"goal_id": 0})


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.coaching
async def test_handle_checkin_wins_sets_progress_state():
    """handle_checkin_wins переходит к CoachingCheckIn.waiting_progress."""
    from bot.flows.coaching_flows import handle_checkin_wins
    msg = make_message(text="Сделал 3 тренировки")
    state = make_state()
    state.get_data = AsyncMock(return_value={"goal_id": 1})
    await handle_checkin_wins(msg, state)
    state.set_state.assert_awaited_once_with(CoachingCheckIn.waiting_progress)


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.coaching
async def test_handle_checkin_progress_sets_energy_state():
    """handle_checkin_progress переходит к CoachingCheckIn.waiting_energy."""
    from bot.flows.coaching_flows import handle_checkin_progress
    msg = make_message(text="75")
    msg.message = MagicMock()
    msg.message.edit_text = AsyncMock()  # нужно для callback-пути
    state = make_state()
    state.get_data = AsyncMock(return_value={"checkin_draft": {"goal_id": 1, "wins": "победы"}})
    await handle_checkin_progress(msg, state, progress=75)
    state.set_state.assert_awaited_once_with(CoachingCheckIn.waiting_energy)
