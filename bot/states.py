"""
Состояния FSM (Finite State Machine) для многошаговых диалогов бота.
"""
from aiogram.fsm.state import State, StatesGroup


class EditTaskStates(StatesGroup):
    """Состояния редактирования задачи."""
    # Ожидаем ввод нового текста задачи от пользователя
    waiting_for_text = State()
