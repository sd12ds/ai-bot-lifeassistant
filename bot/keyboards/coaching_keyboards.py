"""
Клавиатуры для Coaching модуля (Inline + Reply).

Формат callback_data: cg_{type}_{action}_{id}
Макс 64 байта — используем сокращённые форматы.

Контексты (§9.1-9.7 архитектурного документа):
  9.1 — цели: goal_card_kb, goal_stuck_kb, goal_achieved_kb
  9.2 — привычки: habit_daily_kb, habit_streak_kb
  9.3 — check-in: checkin_mood_kb, checkin_progress_kb
  9.4 — weekly review: weekly_review_kb
  9.5 — мотивационные: momentum_kb, recovery_kb
  9.6 — onboarding: onboarding_kb, goal_area_kb, habit_area_kb
  9.7 — контекстные по состоянию: overload_kb

Flow-вспомогательные: skip_kb, cancel_flow_kb
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# ══════════════════════════════════════════════════════════════════════════════
# 9.1 — Кнопки управления целями
# ══════════════════════════════════════════════════════════════════════════════

def goal_card_kb(goal_id: int, is_frozen: bool = False) -> InlineKeyboardMarkup:
    """
    Карточка активной цели: check-in, этапы, прогресс, заморозить/возобновить.
    """
    btn_freeze = (
        InlineKeyboardButton(text="▶️ Возобновить", callback_data=f"cg_g_resume_{goal_id}")
        if is_frozen else
        InlineKeyboardButton(text="🧊 Заморозить", callback_data=f"cg_g_freeze_{goal_id}")
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Check-in", callback_data=f"cg_g_checkin_{goal_id}"),
            InlineKeyboardButton(text="📊 Прогресс", callback_data=f"cg_g_progress_{goal_id}"),
        ],
        [
            InlineKeyboardButton(text="📋 Этапы", callback_data=f"cg_g_milestones_{goal_id}"),
            InlineKeyboardButton(text="🗓 Обзор", callback_data=f"cg_wr_goal_{goal_id}"),
        ],
        [
            btn_freeze,
            InlineKeyboardButton(text="🏆 Достиг!", callback_data=f"cg_g_done_{goal_id}"),
        ],
    ])


def goal_stuck_kb(goal_id: int) -> InlineKeyboardMarkup:
    """
    Зависшая цель (нет прогресса >7 дней).
    Три варианта действий: сделать шаг, заморозить, перезапустить.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💪 Сделаю шаг сейчас", callback_data=f"cg_g_checkin_{goal_id}"),
        ],
        [
            InlineKeyboardButton(text="🧊 Заморозить на время", callback_data=f"cg_g_freeze_{goal_id}"),
            InlineKeyboardButton(text="🔄 Перезапустить", callback_data=f"cg_g_restart_{goal_id}"),
        ],
        [
            InlineKeyboardButton(text="📋 Разбить на шаги", callback_data=f"cg_g_plan_{goal_id}"),
        ],
    ])


def goal_achieved_kb() -> InlineKeyboardMarkup:
    """Цель достигнута — предлагаем действия дальше."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Поставить новую цель", callback_data="cg_flow_goal_new"),
        ],
        [
            InlineKeyboardButton(text="📊 Посмотреть все цели", callback_data="cg_g_list"),
        ],
    ])


def goal_list_item_kb(goal_id: int) -> InlineKeyboardMarkup:
    """Мини-кнопки под каждой целью в списке."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Check-in", callback_data=f"cg_g_checkin_{goal_id}"),
        InlineKeyboardButton(text="📊 +Прогресс", callback_data=f"cg_g_progress_{goal_id}"),
        InlineKeyboardButton(text="📋 Этапы", callback_data=f"cg_g_milestones_{goal_id}"),
    ]])


# ══════════════════════════════════════════════════════════════════════════════
# 9.2 — Кнопки привычек
# ══════════════════════════════════════════════════════════════════════════════

def habit_daily_kb(habit_id: int) -> InlineKeyboardMarkup:
    """Ежедневный трекер привычки: сделал / пропустил."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Сделал!", callback_data=f"cg_h_log_{habit_id}"),
            InlineKeyboardButton(text="❌ Пропустил", callback_data=f"cg_h_miss_{habit_id}"),
        ],
        [
            InlineKeyboardButton(text="⏸ Пауза", callback_data=f"cg_h_pause_{habit_id}"),
            InlineKeyboardButton(text="📊 Статистика", callback_data=f"cg_h_stats_{habit_id}"),
        ],
    ])


def habit_streak_kb(habit_id: int, streak: int) -> InlineKeyboardMarkup:
    """
    Серия привычки — предлагаем усилить или скорректировать.
    Показывается когда streak достигает нового рекорда.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"🔥 Продолжить серию!", callback_data=f"cg_h_log_{habit_id}"),
        ],
        [
            InlineKeyboardButton(text="⚡ Усилить привычку", callback_data=f"cg_h_upgrade_{habit_id}"),
            InlineKeyboardButton(text="🎯 Привязать к цели", callback_data=f"cg_h_link_{habit_id}"),
        ],
    ])


def habit_missed_kb(habit_id: int) -> InlineKeyboardMarkup:
    """Пропуск привычки — контекстные действия."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💪 Наверстаю завтра!", callback_data=f"cg_h_log_{habit_id}"),
        ],
        [
            InlineKeyboardButton(text="📉 Снизить частоту", callback_data=f"cg_h_adjust_{habit_id}"),
            InlineKeyboardButton(text="⏸ Пауза", callback_data=f"cg_h_pause_{habit_id}"),
        ],
    ])


def habit_list_item_kb(habit_id: int) -> InlineKeyboardMarkup:
    """Мини-кнопки под каждой привычкой в списке."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅", callback_data=f"cg_h_log_{habit_id}"),
        InlineKeyboardButton(text="❌", callback_data=f"cg_h_miss_{habit_id}"),
        InlineKeyboardButton(text="⏸", callback_data=f"cg_h_pause_{habit_id}"),
    ]])


# ══════════════════════════════════════════════════════════════════════════════
# 9.3 — Check-in кнопки
# ══════════════════════════════════════════════════════════════════════════════

def checkin_mood_kb(goal_id: int) -> InlineKeyboardMarkup:
    """5 кнопок настроения/энергии для check-in."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="😴 1", callback_data=f"cg_ci_e1_{goal_id}"),
            InlineKeyboardButton(text="😕 2", callback_data=f"cg_ci_e2_{goal_id}"),
            InlineKeyboardButton(text="😐 3", callback_data=f"cg_ci_e3_{goal_id}"),
            InlineKeyboardButton(text="😊 4", callback_data=f"cg_ci_e4_{goal_id}"),
            InlineKeyboardButton(text="🔥 5", callback_data=f"cg_ci_e5_{goal_id}"),
        ],
    ])


def checkin_progress_kb(goal_id: int) -> InlineKeyboardMarkup:
    """Быстрый выбор прогресса — quick-кнопки %."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="25%", callback_data=f"cg_ci_p25_{goal_id}"),
            InlineKeyboardButton(text="50%", callback_data=f"cg_ci_p50_{goal_id}"),
            InlineKeyboardButton(text="75%", callback_data=f"cg_ci_p75_{goal_id}"),
            InlineKeyboardButton(text="100%", callback_data=f"cg_ci_p100_{goal_id}"),
        ],
        [
            InlineKeyboardButton(text="✏️ Введу вручную", callback_data=f"cg_ci_pman_{goal_id}"),
        ],
    ])


# ══════════════════════════════════════════════════════════════════════════════
# 9.4 — Weekly review
# ══════════════════════════════════════════════════════════════════════════════

def weekly_review_kb(goal_id: int = 0) -> InlineKeyboardMarkup:
    """Выбор типа обзора: быстрый (3 вопроса) или полный (6 секций)."""
    gid = goal_id or 0
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Быстрый (3 мин)", callback_data=f"cg_wr_quick_{gid}"),
            InlineKeyboardButton(text="📊 Полный (10 мин)", callback_data=f"cg_wr_full_{gid}"),
        ],
        [
            InlineKeyboardButton(text="⏭ Пропустить на этой неделе", callback_data="cg_wr_skip"),
        ],
    ])


def review_done_kb(goal_id: int = 0) -> InlineKeyboardMarkup:
    """После сохранения review — предложить следующий шаг."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 К целям", callback_data="cg_g_list"),
            InlineKeyboardButton(text="🔁 К привычкам", callback_data="cg_h_list"),
        ],
    ])


# ══════════════════════════════════════════════════════════════════════════════
# 9.5 — Мотивационные / контекстные по состоянию
# ══════════════════════════════════════════════════════════════════════════════

def momentum_kb() -> InlineKeyboardMarkup:
    """Momentum state — предлагаем поднять планку."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚀 Добавить новую цель", callback_data="cg_flow_goal_new"),
            InlineKeyboardButton(text="💪 Добавить привычку", callback_data="cg_flow_habit_new"),
        ],
        [
            InlineKeyboardButton(text="📋 Добавить этап к цели", callback_data="cg_g_list_milestone"),
        ],
    ])


def recovery_kb(goal_id: int = 0) -> InlineKeyboardMarkup:
    """Recovery mode — мягкие варианты после паузы."""
    gid = goal_id or 0
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💪 Сделаю маленький шаг", callback_data=f"cg_s_step_{gid}"),
        ],
        [
            InlineKeyboardButton(text="📝 Что пошло не так?", callback_data=f"cg_s_reflect_{gid}"),
            InlineKeyboardButton(text="🧊 Заморозить цели", callback_data="cg_s_freeze_all"),
        ],
    ])


def overload_kb() -> InlineKeyboardMarkup:
    """Overload state — помочь разгрузиться."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Показать всё", callback_data="cg_s_overview"),
        ],
        [
            InlineKeyboardButton(text="🧊 Заморозить часть целей", callback_data="cg_s_freeze_select"),
            InlineKeyboardButton(text="⏸ Паузировать привычки", callback_data="cg_s_pause_habits"),
        ],
    ])


def crisis_kb(goal_id: int = 0) -> InlineKeyboardMarkup:
    """Crisis mode (высокий риск dropout) — один простой выбор."""
    gid = goal_id or 0
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="▶️ Один маленький шаг", callback_data=f"cg_s_step_{gid}"),
        ],
        [
            InlineKeyboardButton(text="🧊 Заморозить цели на 2 недели", callback_data="cg_s_freeze_all"),
        ],
    ])


# ══════════════════════════════════════════════════════════════════════════════
# 9.6 — Onboarding кнопки
# ══════════════════════════════════════════════════════════════════════════════

def onboarding_kb() -> InlineKeyboardMarkup:
    """Стартовый онбординг — 3 варианта первого шага."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Поставить первую цель", callback_data="cg_ob_goal"),
        ],
        [
            InlineKeyboardButton(text="🔁 Создать привычку", callback_data="cg_ob_habit"),
        ],
        [
            InlineKeyboardButton(text="👀 Посмотреть примеры", callback_data="cg_ob_examples"),
        ],
        [
            InlineKeyboardButton(text="⏭ Пропустить пока", callback_data="cg_ob_skip"),
        ],
    ])


def onboarding_done_kb() -> InlineKeyboardMarkup:
    """После завершения онбординга."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Поставить цель", callback_data="cg_flow_goal_new"),
            InlineKeyboardButton(text="🔁 Создать привычку", callback_data="cg_flow_habit_new"),
        ],
    ])


def goal_area_kb() -> InlineKeyboardMarkup:
    """Выбор области жизни при создании цели."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💚 Здоровье", callback_data="cg_area_health"),
            InlineKeyboardButton(text="💰 Финансы", callback_data="cg_area_finance"),
        ],
        [
            InlineKeyboardButton(text="💼 Карьера", callback_data="cg_area_career"),
            InlineKeyboardButton(text="🧘 Личное", callback_data="cg_area_personal"),
        ],
        [
            InlineKeyboardButton(text="❤️ Отношения", callback_data="cg_area_relationships"),
            InlineKeyboardButton(text="⏭ Пропустить", callback_data="cg_area_skip"),
        ],
    ])


def habit_area_kb() -> InlineKeyboardMarkup:
    """Выбор области при создании привычки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💚 Здоровье", callback_data="cg_harea_health"),
            InlineKeyboardButton(text="🏃 Спорт", callback_data="cg_harea_sport"),
        ],
        [
            InlineKeyboardButton(text="🧠 Майндсет", callback_data="cg_harea_mindset"),
            InlineKeyboardButton(text="⚡ Продуктивность", callback_data="cg_harea_productivity"),
        ],
        [
            InlineKeyboardButton(text="⏭ Пропустить", callback_data="cg_harea_skip"),
        ],
    ])


def habit_frequency_kb() -> InlineKeyboardMarkup:
    """Выбор частоты привычки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Ежедневно", callback_data="cg_hfreq_daily"),
            InlineKeyboardButton(text="📆 Еженедельно", callback_data="cg_hfreq_weekly"),
        ],
        [
            InlineKeyboardButton(text="🗓 Свой режим", callback_data="cg_hfreq_custom"),
        ],
    ])


# ══════════════════════════════════════════════════════════════════════════════
# Flow-вспомогательные клавиатуры
# ══════════════════════════════════════════════════════════════════════════════

def skip_kb(callback_data: str = "cg_flow_skip") -> InlineKeyboardMarkup:
    """Универсальная кнопка «Пропустить» для необязательных шагов flow."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Пропустить", callback_data=callback_data),
    ]])


def skip_cancel_kb(skip_data: str = "cg_flow_skip") -> InlineKeyboardMarkup:
    """Кнопки «Пропустить» + «Отмена» для необязательных шагов."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Пропустить", callback_data=skip_data),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cg_flow_cancel"),
    ]])


def cancel_flow_kb() -> InlineKeyboardMarkup:
    """Кнопка отмены текущего flow."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data="cg_flow_cancel"),
    ]])


def confirm_kb(confirm_data: str, cancel_data: str = "cg_flow_cancel") -> InlineKeyboardMarkup:
    """Кнопки «Подтвердить» / «Отмена»."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=confirm_data),
        InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_data),
    ]])


# ══════════════════════════════════════════════════════════════════════════════
# Главное coaching меню
# ══════════════════════════════════════════════════════════════════════════════

def coaching_main_kb() -> InlineKeyboardMarkup:
    """Главное меню раздела /coaching."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Мои цели", callback_data="cg_g_list"),
            InlineKeyboardButton(text="🔁 Мои привычки", callback_data="cg_h_list"),
        ],
        [
            InlineKeyboardButton(text="✅ Check-in", callback_data="cg_g_checkin_0"),
            InlineKeyboardButton(text="📊 Обзор недели", callback_data="cg_wr_quick_0"),
        ],
        [
            InlineKeyboardButton(text="➕ Новая цель", callback_data="cg_flow_goal_new"),
            InlineKeyboardButton(text="➕ Новая привычка", callback_data="cg_flow_habit_new"),
        ],
        [
            InlineKeyboardButton(text="💡 Рекомендации", callback_data="cg_recs"),
            InlineKeyboardButton(text="🧠 Память коуча", callback_data="cg_memory"),
        ],
    ])
