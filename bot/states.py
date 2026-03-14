"""
Состояния FSM (Finite State Machine) для многошаговых диалогов бота.
"""
from aiogram.fsm.state import State, StatesGroup


class EditTaskStates(StatesGroup):
    """Состояния редактирования задачи."""
    # Ожидаем ввод нового текста задачи от пользователя
    waiting_for_text = State()


# ══════════════════════════════════════════════════════════════════════════════
# Coaching FSM — многошаговые диалоги
# ══════════════════════════════════════════════════════════════════════════════

class CoachingGoalCreation(StatesGroup):
    """
    5-шаговый flow создания цели.
    Данные накапливаются через coaching_dialog_drafts.
    """
    waiting_area       = State()  # Шаг 1: область жизни (через кнопки)
    waiting_title      = State()  # Шаг 2: конкретная цель (текст)
    waiting_why        = State()  # Шаг 3: зачем / почему важно (текст или skip)
    waiting_first_step = State()  # Шаг 4: первый конкретный шаг (текст или skip)
    waiting_deadline   = State()  # Шаг 5: дедлайн YYYY-MM-DD (текст или skip)


class CoachingHabitCreation(StatesGroup):
    """
    4-шаговый flow создания привычки.
    """
    waiting_title = State()  # Шаг 1: название привычки (текст)
    waiting_area  = State()  # Шаг 2: область (через кнопки или skip)
    waiting_cue   = State()  # Шаг 3: триггер (текст или skip)
    waiting_reward = State()  # Шаг 4: награда (текст или skip)


class CoachingCheckIn(StatesGroup):
    """
    4-шаговый check-in flow по цели.
    goal_id сохраняется в FSM data.
    """
    waiting_wins     = State()  # Шаг 1: победы (текст или skip)
    waiting_progress = State()  # Шаг 2: прогресс 0-100% (текст или quick-кнопки)
    waiting_energy   = State()  # Шаг 3: энергия 1-5 (кнопки)
    waiting_blockers = State()  # Шаг 4: блокеры (текст или skip)


class CoachingWeeklyReview(StatesGroup):
    """
    4-шаговый weekly review flow.
    goal_id сохраняется в FSM data.
    """
    waiting_summary      = State()  # Шаг 1: итог недели (текст)
    waiting_highlights   = State()  # Шаг 2: главные достижения (текст или skip)
    waiting_blockers     = State()  # Шаг 3: трудности (текст или skip)
    waiting_next_actions = State()  # Шаг 4: план на следующую неделю (текст или skip)
