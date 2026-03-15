"""
Клавиатуры для Coaching модуля (Inline + Reply).

Формат callback_data: cg_{type}_{action}_{id}
Макс 64 байта — используем сокращённые форматы.

Контексты (§9.1-9.7 архитектурного документа):
  9.1 — цели: goal_card_kb, goal_stuck_kb, goal_achieved_kb, goal_after_create_kb
  9.2 — привычки: habit_daily_kb, habit_streak_kb
  9.3 — check-in: checkin_mood_kb, checkin_after_mood_kb, checkin_progress_kb
  9.4 — weekly review: weekly_review_kb, review_goal_status_kb, review_done_kb
  9.5 — мотивационные: motivational_kb
  9.6 — onboarding: onboarding_kb, goal_area_kb, habit_area_kb
  9.7 — контекстные по состоянию: overload_kb, recovery_kb, momentum_kb

Flow-вспомогательные: skip_kb, cancel_flow_kb
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# =============================================================================
# 9.1 — Кнопки управления целями
# =============================================================================

def goal_card_kb(goal_id: int, is_frozen: bool = False) -> InlineKeyboardMarkup:
    """Карточка активной цели: check-in, этапы, прогресс, заморозить/возобновить."""
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
        [
            # Быстрый статус цели для weekly review (§9.4)
            InlineKeyboardButton(text="📊 Статус недели", callback_data=f"cg_g_wstatus_{goal_id}"),
        ],
    ])


def goal_after_create_kb(goal_id: int) -> InlineKeyboardMarkup:
    """После создания цели — следующие действия (§9.1)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📌 Разбить на этапы", callback_data=f"cg_g_steps_{goal_id}"),
            InlineKeyboardButton(text="✅ Первый шаг", callback_data=f"cg_g_firstnow_{goal_id}"),
        ],
        [
            InlineKeyboardButton(text="📊 Открыть в App", callback_data=f"cg_g_openapp_{goal_id}"),
            InlineKeyboardButton(text="🎯 Все цели", callback_data="cg_g_list"),
        ],
    ])


def goal_stuck_kb(goal_id: int) -> InlineKeyboardMarkup:
    """Зависшая цель (нет прогресса >7 дней) — 4 варианта действий (§9.1)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Продолжаю", callback_data=f"cg_g_checkin_{goal_id}"),
            InlineKeyboardButton(text="🔄 Скорректировать", callback_data=f"cg_g_plan_{goal_id}"),
        ],
        [
            InlineKeyboardButton(text="🧊 Заморозить", callback_data=f"cg_g_freeze_{goal_id}"),
            InlineKeyboardButton(text="📝 Объясню", callback_data=f"cg_g_reflect_{goal_id}"),
        ],
    ])


def goal_achieved_kb(goal_id: int = 0) -> InlineKeyboardMarkup:
    """Цель достигнута — предлагаем действия дальше (§9.1)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎉 Ура! Что дальше?", callback_data="cg_flow_goal_new"),
        ],
        [
            InlineKeyboardButton(text="📝 Написать рефлексию", callback_data=f"cg_g_reflect_{goal_id}"),
            InlineKeyboardButton(text="📊 Все цели", callback_data="cg_g_list"),
        ],
    ])


def goal_list_item_kb(goal_id: int) -> InlineKeyboardMarkup:
    """Мини-кнопки под каждой целью в списке."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Check-in", callback_data=f"cg_g_checkin_{goal_id}"),
        InlineKeyboardButton(text="📊 +Прогресс", callback_data=f"cg_g_progress_{goal_id}"),
        InlineKeyboardButton(text="📋 Этапы", callback_data=f"cg_g_milestones_{goal_id}"),
    ]])


# =============================================================================
# 9.2 — Кнопки привычек
# =============================================================================

def habit_daily_kb(habit_id: int) -> InlineKeyboardMarkup:
    """Ежедневный трекер привычки (§9.2): сделал / пропустил / напомни позже."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Сделал!", callback_data=f"cg_h_log_{habit_id}"),
            InlineKeyboardButton(text="❌ Пропустил", callback_data=f"cg_h_miss_{habit_id}"),
            InlineKeyboardButton(text="⏰ Позже", callback_data=f"cg_h_snooze_{habit_id}"),
        ],
        [
            InlineKeyboardButton(text="⏸ Пауза", callback_data=f"cg_h_pause_{habit_id}"),
            InlineKeyboardButton(text="📊 Статистика", callback_data=f"cg_h_stats_{habit_id}"),
        ],
    ])


def habit_streak_kb(habit_id: int, streak: int) -> InlineKeyboardMarkup:
    """Серия привычки — кнопки после нового рекорда (§9.2)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"🔥 Продолжить серию!", callback_data=f"cg_h_log_{habit_id}"),
        ],
        [
            InlineKeyboardButton(text="📈 Поделиться", callback_data=f"cg_h_share_{habit_id}"),
            InlineKeyboardButton(text="📊 Посмотреть прогресс", callback_data=f"cg_h_stats_{habit_id}"),
        ],
    ])


def habit_missed_kb(habit_id: int) -> InlineKeyboardMarkup:
    """Пропуск привычки — контекстные действия."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💪 Наверстаю завтра!", callback_data=f"cg_h_log_{habit_id}"),
        ],
        [
            InlineKeyboardButton(text="🔄 Изменить частоту", callback_data=f"cg_h_adjust_{habit_id}"),
            InlineKeyboardButton(text="⏸ Пауза", callback_data=f"cg_h_pause_{habit_id}"),
        ],
    ])


def habit_list_item_kb(habit_id: int) -> InlineKeyboardMarkup:
    """Мини-кнопки под каждой привычкой в списке — включая snooze (§9.2)."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅", callback_data=f"cg_h_log_{habit_id}"),
        InlineKeyboardButton(text="❌", callback_data=f"cg_h_miss_{habit_id}"),
        InlineKeyboardButton(text="⏸", callback_data=f"cg_h_pause_{habit_id}"),
        InlineKeyboardButton(text="⏰", callback_data=f"cg_h_snooze_{habit_id}"),
    ]])


# =============================================================================
# 9.3 — Check-in кнопки
# =============================================================================

def checkin_mood_kb(goal_id: int) -> InlineKeyboardMarkup:
    """5 кнопок настроения для check-in (§9.3) — mood-labels вместо цифр."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔥 Отлично", callback_data=f"cg_ci_e5_{goal_id}"),
            InlineKeyboardButton(text="👍 Норм", callback_data=f"cg_ci_e4_{goal_id}"),
        ],
        [
            InlineKeyboardButton(text="😐 Так себе", callback_data=f"cg_ci_e3_{goal_id}"),
            InlineKeyboardButton(text="😔 Тяжело", callback_data=f"cg_ci_e2_{goal_id}"),
        ],
        [
            InlineKeyboardButton(text="💀 Провал", callback_data=f"cg_ci_e1_{goal_id}"),
        ],
    ])


def checkin_after_mood_kb() -> InlineKeyboardMarkup:
    """Кнопки после выбора настроения — что делаем дальше (§9.3)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗣 Расскажу что мешало", callback_data="cg_ci_fb_block")],
        [InlineKeyboardButton(text="🗺️ Дай следующий шаг", callback_data="cg_ci_fb_step")],
        [InlineKeyboardButton(text="✅ Всё ок, спасибо", callback_data="cg_ci_fb_ok")],
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


# =============================================================================
# 9.4 — Weekly review
# =============================================================================

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


def review_goal_status_kb(goal_id: int) -> InlineKeyboardMarkup:
    """Статус цели в рамках weekly review — быстрая оценка (§9.4)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Двигаюсь", callback_data=f"cg_wr_gs_{goal_id}_ok"),
            InlineKeyboardButton(text="🟡 Медленно", callback_data=f"cg_wr_gs_{goal_id}_slow"),
        ],
        [
            InlineKeyboardButton(text="🔴 Буксую", callback_data=f"cg_wr_gs_{goal_id}_stuck"),
            InlineKeyboardButton(text="❄️ Заморожена", callback_data=f"cg_wr_gs_{goal_id}_freeze"),
        ],
    ])


def review_done_kb(goal_id: int = 0) -> InlineKeyboardMarkup:
    """После завершения review — действия по результатам (§9.4)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔧 Скорректировать план", callback_data="cg_wr_after_adjust"),
            InlineKeyboardButton(text="📉 Снизить нагрузку", callback_data="cg_wr_after_reduce"),
        ],
        [
            InlineKeyboardButton(text="📈 Усилить темп", callback_data="cg_wr_after_boost"),
            InlineKeyboardButton(text="✅ Всё устраивает", callback_data="cg_wr_after_ok"),
        ],
    ])


# =============================================================================
# 9.5 — Мотивационные кнопки
# =============================================================================

def motivational_kb() -> InlineKeyboardMarkup:
    """Мотивационное меню — 4 варианта поддержки (§9.5)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💪 Подбодри", callback_data="cg_mot_inspire"),
            InlineKeyboardButton(text="🔥 Жёсткий разбор", callback_data="cg_mot_strict"),
        ],
        [
            InlineKeyboardButton(text="🗺️ Следующий шаг", callback_data="cg_mot_nextstep"),
            InlineKeyboardButton(text="🎯 Упрости маршрут", callback_data="cg_mot_simplify"),
        ],
    ])


# =============================================================================
# 9.7 — Контекстные кнопки по состоянию
# =============================================================================

def momentum_kb() -> InlineKeyboardMarkup:
    """Momentum state (§9.7) — предлагаем поднять планку."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📈 Добавить вызов", callback_data="cg_s_add_challenge"),
            InlineKeyboardButton(text="🆕 Новая цель", callback_data="cg_flow_goal_new"),
        ],
        [
            InlineKeyboardButton(text="🏆 Мои достижения", callback_data="cg_s_achievements"),
        ],
    ])


def recovery_kb(goal_id: int = 0) -> InlineKeyboardMarkup:
    """Recovery mode (§9.7) — мягкие варианты после паузы."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Начать заново", callback_data="cg_s_restart"),
        ],
        [
            InlineKeyboardButton(text="📝 Рассказать что случилось", callback_data="cg_s_tell_story"),
            InlineKeyboardButton(text="🆕 Простой план", callback_data="cg_s_simple_plan"),
        ],
    ])


def overload_kb() -> InlineKeyboardMarkup:
    """Overload state (§9.7) — помочь разгрузиться."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📉 Снизить нагрузку", callback_data="cg_s_reduce_load"),
        ],
        [
            InlineKeyboardButton(text="🔄 Пересобрать план", callback_data="cg_s_rebuild_plan"),
            InlineKeyboardButton(text="❄️ Заморозить лишнее", callback_data="cg_s_freeze_extra"),
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


# =============================================================================
# 9.6 — Onboarding кнопки
# =============================================================================

def onboarding_kb() -> InlineKeyboardMarkup:
    """Стартовый онбординг — 3 варианта первого шага (§9.6)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Поставить первую цель", callback_data="cg_ob_goal")],
        [InlineKeyboardButton(text="🔁 Создать привычку", callback_data="cg_ob_habit")],
        [InlineKeyboardButton(text="👀 Посмотреть примеры", callback_data="cg_ob_examples")],
        [InlineKeyboardButton(text="⏭ Пропустить пока", callback_data="cg_ob_skip")],
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
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="cg_harea_skip")],
    ])


def habit_frequency_kb() -> InlineKeyboardMarkup:
    """Выбор частоты привычки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Ежедневно", callback_data="cg_hfreq_daily"),
            InlineKeyboardButton(text="📆 Еженедельно", callback_data="cg_hfreq_weekly"),
        ],
        [InlineKeyboardButton(text="🗓 Свой режим", callback_data="cg_hfreq_custom")],
    ])


# =============================================================================
# Flow-вспомогательные клавиатуры
# =============================================================================

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


# =============================================================================
# Главное coaching меню
# =============================================================================

def coaching_main_kb() -> InlineKeyboardMarkup:
    """Главное меню раздела /coaching — включает кнопку Мотивации (§9.5)."""
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
            InlineKeyboardButton(text="💪 Мотивация", callback_data="cg_mot_menu"),
            InlineKeyboardButton(text="💡 Рекомендации", callback_data="cg_recs"),
        ],
        [
            InlineKeyboardButton(text="🧠 Память коуча", callback_data="cg_memory"),
        ],
    ])


# =============================================================================
# Онбординг — Шаг 2: Профилирование
# =============================================================================

def onboarding_profile_intro_kb() -> InlineKeyboardMarkup:
    """Переход к шагу профилирования после intro."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Настроить за 30 секунд", callback_data="cg_ob_profile_start")],
        [InlineKeyboardButton(text="⏭ Пропустить настройку", callback_data="cg_ob_profile_skip")],
    ])


def onboarding_focus_area_kb(selected: list[str] | None = None) -> InlineKeyboardMarkup:
    """Выбор приоритетной области жизни (toggle-кнопки, отображает ✅)."""
    selected = selected or []
    areas = [
        ("💚 Здоровье", "health"),
        ("💰 Финансы", "finance"),
        ("💼 Карьера", "career"),
        ("🧘 Личное развитие", "personal"),
        ("❤️ Отношения", "relationships"),
    ]
    rows = []
    for label, key in areas:
        mark = "✅ " if key in selected else ""
        rows.append([InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"cg_ob_focus_{key}")])
    rows.append([InlineKeyboardButton(text="✅ Готово", callback_data="cg_ob_focus_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def onboarding_tone_kb() -> InlineKeyboardMarkup:
    """Выбор стиля общения коуча."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😊 Дружелюбный", callback_data="cg_ob_tone_friendly")],
        [InlineKeyboardButton(text="🚀 Мотивационный", callback_data="cg_ob_tone_motivational")],
        [InlineKeyboardButton(text="💪 Требовательный", callback_data="cg_ob_tone_strict")],
        [InlineKeyboardButton(text="🕊️ Мягкий", callback_data="cg_ob_tone_soft")],
    ])


def onboarding_checkin_time_kb() -> InlineKeyboardMarkup:
    """Выбор предпочтительного времени чекина."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌅 Утро (09:00)", callback_data="cg_ob_time_09:00"),
            InlineKeyboardButton(text="☀️ День (13:00)", callback_data="cg_ob_time_13:00"),
        ],
        [
            InlineKeyboardButton(text="🌆 Вечер (20:00)", callback_data="cg_ob_time_20:00"),
            InlineKeyboardButton(text="🌙 Ночь (22:00)", callback_data="cg_ob_time_22:00"),
        ],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="cg_ob_time_skip")],
    ])


def onboarding_first_action_kb() -> InlineKeyboardMarkup:
    """Шаг 3 — первое действие после профилирования."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Поставить первую цель", callback_data="cg_ob_goal")],
        [InlineKeyboardButton(text="🔁 Создать привычку", callback_data="cg_ob_habit")],
        [InlineKeyboardButton(text="👀 Посмотреть примеры", callback_data="cg_ob_examples")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="cg_ob_done_main")],
    ])
