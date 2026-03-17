"""
Bot coaching — check-in callbacks, weekly review, flow control, daily proactive.

Регистрирует:
  cg_ci_p*, cg_ci_e*          — прогресс и энергия чекина
  cg_wr_quick_*, cg_wr_full_* — weekly review
  cg_flow_goal_new/habit_new  — старт flow (уже в goals/habits)
  cg_area_*, cg_harea_*       — выбор области в FSM
  cg_flow_skip_*              — пропуск шагов в flow
  cg_flow_cancel              — отмена flow
  cg_ci_fb_*                  — follow-up после выбора настроения
  cg_wr_gs_*, cg_wr_after_*   — статус цели в review + действия после
  cg_daily_morning_*, midday_*, evening_* — дневные проактивные чекины
"""
from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.states import (
    CoachingGoalCreation, CoachingHabitCreation,
    CoachingCheckIn, CoachingWeeklyReview,
    DailyEveningReflection,
)
from bot.keyboards.coaching_keyboards import (
    coaching_main_kb, goal_stuck_kb, momentum_kb, overload_kb,
)
from bot.flows.coaching_flows import (
    handle_goal_area, handle_goal_deadline,
    handle_habit_area,
    start_checkin_flow, handle_checkin_progress, handle_checkin_energy, finish_checkin,
    start_weekly_review, finish_weekly_review,
    save_morning_checkin, save_midday_checkin,
    start_evening_reflection, handle_evening_day_result,
    handle_evening_notes, handle_evening_blockers, finish_evening_reflection,
)
from db.session import get_async_session
from db import coaching_storage as cs

logger = logging.getLogger(__name__)
router = Router()


# ══════════════════════════════════════════════════════════════════════════════
# CHECK-IN CALLBACKS (прогресс и энергия)
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("cg_ci_p"))
async def checkin_progress_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор прогресса через quick-кнопки.

    Формат: cg_ci_p{pct}_{goal_id}, где pct = 25/50/75/100/man.
    Пример: cg_ci_p25_42 → split -> ["cg","ci","p25","42"] → parts[2]="p25".
    """
    parts = callback.data.split("_")  # ["cg","ci","p25","42"]
    pct_str = parts[2][1:] if len(parts) >= 3 else ""  # убираем 'p' → "25" или "man"
    if pct_str == "man":
        # Ручной ввод числа — переходим в FSM-состояние ожидания текста
        await state.set_state(CoachingCheckIn.waiting_progress)
        await callback.message.edit_text("📊 Введи прогресс числом от 0 до 100:")
        await callback.answer()
        return
    try:
        progress = int(pct_str)
    except ValueError:
        await callback.answer("Ошибка формата"); return
    await handle_checkin_progress(callback, state, progress=progress)


@router.callback_query(F.data.startswith("cg_ci_e"))
async def checkin_energy_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор уровня энергии 1–5.

    Формат: cg_ci_e{1-5}_{goal_id}.
    Пример: cg_ci_e3_42 → split -> ["cg","ci","e3","42"] → parts[2]="e3".
    """
    parts = callback.data.split("_")  # ["cg","ci","e3","42"]
    e_str = parts[2][1:] if len(parts) >= 3 else ""  # убираем 'e' → "3"
    try:
        energy = int(e_str)
    except ValueError:
        await callback.answer("Ошибка формата"); return
    await handle_checkin_energy(callback, state, energy=energy)


# ══════════════════════════════════════════════════════════════════════════════
# WEEKLY REVIEW CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("cg_wr_quick_"))
async def wr_quick(callback: CallbackQuery, state: FSMContext) -> None:
    """Быстрый weekly review.

    Обрабатывает все варианты в одном хендлере (порядок регистрации aiogram):
    - cg_wr_quick_0_go  → общий review без привязки к цели
    - cg_wr_quick_0     → показать список целей для выбора (или общий review если нет целей)
    - cg_wr_quick_{id}  → review по конкретной цели
    """
    raw = callback.data[len("cg_wr_quick_"):]  # "42", "0", "0_go"
    if raw == "0_go":
        # Пользователь нажал «Общий обзор» в меню выбора цели
        await start_weekly_review(callback, state, goal_id=0, quick=True)
        return
    try:
        goal_id = int(raw)
    except ValueError:
        await callback.answer("Ошибка"); return
    if goal_id == 0:
        # Показываем выбор цели, если они есть
        user_id = callback.from_user.id
        async with get_async_session() as session:
            goals = await cs.get_goals(session, user_id, status="active")
        if not goals:
            await start_weekly_review(callback, state, goal_id=0, quick=True)
            return
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🎯 {g.title[:30]}", callback_data=f"cg_wr_quick_{g.id}")]
            for g in goals[:5]
        ] + [[InlineKeyboardButton(text="📋 Общий обзор", callback_data="cg_wr_quick_0_go")]])
        await callback.message.edit_text("📊 По какой цели обзор?", reply_markup=kb)
        await callback.answer()
        return
    await start_weekly_review(callback, state, goal_id=goal_id, quick=True)


@router.callback_query(F.data.startswith("cg_wr_full_"))
async def wr_full(callback: CallbackQuery, state: FSMContext) -> None:
    """Полный weekly review по конкретной цели."""
    goal_id = int(callback.data.split("_")[-1])
    await start_weekly_review(callback, state, goal_id=goal_id, quick=False)


@router.callback_query(F.data == "cg_wr_skip")
async def wr_skip(callback: CallbackQuery) -> None:
    await callback.message.edit_text("OK, обзор пропущен. Не забудь вернуться на следующей неделе! 📅")
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# GOAL AREA SELECTION (flow step 1)
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("cg_area_"), StateFilter(CoachingGoalCreation.waiting_area))
async def goal_area_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор области жизни в flow создания цели."""
    area = callback.data.replace("cg_area_", "")
    await handle_goal_area(callback, state, area=area)


# ══════════════════════════════════════════════════════════════════════════════
# HABIT AREA SELECTION (flow step 2)
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("cg_harea_"), StateFilter(CoachingHabitCreation.waiting_area))
async def habit_area_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор области в flow создания привычки."""
    area = callback.data.replace("cg_harea_", "")
    await handle_habit_area(callback, state, area=area)


# ══════════════════════════════════════════════════════════════════════════════
# SKIP CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "cg_flow_skip_why", StateFilter(CoachingGoalCreation.waiting_why))
async def skip_goal_why(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CoachingGoalCreation.waiting_first_step)
    await callback.message.edit_text(
        "⚡ Шаг 4/5 — Какое *одно конкретное действие* прямо сейчас?\n\n_Введи первый шаг или пропусти:_",
        reply_markup=__import__('bot.keyboards.coaching_keyboards', fromlist=['skip_cancel_kb']).skip_cancel_kb("cg_flow_skip_step"),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_flow_skip_step", StateFilter(CoachingGoalCreation.waiting_first_step))
async def skip_goal_step(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CoachingGoalCreation.waiting_deadline)
    from bot.keyboards.coaching_keyboards import skip_cancel_kb
    await callback.message.edit_text(
        "🗓 Шаг 5/5 — Есть дедлайн?\n_Формат: 2025-12-31_ или пропусти:",
        reply_markup=skip_cancel_kb("cg_flow_skip_deadline"), parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_flow_skip_deadline", StateFilter(CoachingGoalCreation.waiting_deadline))
async def skip_goal_deadline(callback: CallbackQuery, state: FSMContext) -> None:
    await handle_goal_deadline(callback, state, deadline="")


@router.callback_query(F.data == "cg_flow_skip_cue", StateFilter(CoachingHabitCreation.waiting_cue))
async def skip_habit_cue(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CoachingHabitCreation.waiting_reward)
    from bot.keyboards.coaching_keyboards import skip_cancel_kb
    await callback.message.edit_text(
        "🎁 Шаг 4/4 — Что получишь после?\n_Введи награду или пропусти:_",
        reply_markup=skip_cancel_kb("cg_flow_skip_reward"), parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_flow_skip_reward", StateFilter(CoachingHabitCreation.waiting_reward))
async def skip_habit_reward(callback: CallbackQuery, state: FSMContext) -> None:
    await finish_weekly_review(callback, state)


@router.callback_query(F.data == "cg_flow_skip_wins", StateFilter(CoachingCheckIn.waiting_wins))
async def skip_checkin_wins(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data(); draft = data.get("checkin_draft", {})
    await state.set_state(CoachingCheckIn.waiting_progress)
    from bot.keyboards.coaching_keyboards import checkin_progress_kb
    await callback.message.edit_text(
        "📊 Шаг 2/4 — Прогресс по цели (0-100%)?\n_Выбери или введи число:_",
        reply_markup=checkin_progress_kb(draft.get("goal_id", 0)), parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_flow_skip_blockers", StateFilter(CoachingCheckIn.waiting_blockers))
async def skip_checkin_blockers(callback: CallbackQuery, state: FSMContext) -> None:
    await finish_checkin(callback, state, blockers="")


@router.callback_query(F.data == "cg_flow_skip_hl", StateFilter(CoachingWeeklyReview.waiting_highlights))
async def skip_review_hl(callback: CallbackQuery, state: FSMContext) -> None:
    # Эмулируем пустой текст в черновике
    data = await state.get_data(); draft = data.get("review_draft", {}); draft["highlights"] = ""
    await state.update_data(review_draft=draft)
    quick = draft.get("quick", True)
    from bot.keyboards.coaching_keyboards import skip_cancel_kb
    if quick:
        await state.set_state(CoachingWeeklyReview.waiting_next_actions)
        await callback.message.edit_text(
            "🚀 Топ-3 фокуса на следующую неделю?\n_Через запятую или пропусти:_",
            reply_markup=skip_cancel_kb("cg_flow_skip_na"), parse_mode="Markdown",
        )
    else:
        await state.set_state(CoachingWeeklyReview.waiting_blockers)
        await callback.message.edit_text(
            "🚧 Что мешало?\n_Через запятую или пропусти:_",
            reply_markup=skip_cancel_kb("cg_flow_skip_bl"), parse_mode="Markdown",
        )
    await callback.answer()


@router.callback_query(F.data == "cg_flow_skip_bl", StateFilter(CoachingWeeklyReview.waiting_blockers))
async def skip_review_bl(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data(); draft = data.get("review_draft", {}); draft["blockers"] = ""
    await state.update_data(review_draft=draft)
    await state.set_state(CoachingWeeklyReview.waiting_next_actions)
    from bot.keyboards.coaching_keyboards import skip_cancel_kb
    await callback.message.edit_text(
        "🚀 Топ-3 фокуса на следующую неделю?\n_Через запятую или пропусти:_",
        reply_markup=skip_cancel_kb("cg_flow_skip_na"), parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_flow_skip_na", StateFilter(CoachingWeeklyReview.waiting_next_actions))
async def skip_review_na(callback: CallbackQuery, state: FSMContext) -> None:
    await finish_weekly_review(callback, state, next_actions="")


# ══════════════════════════════════════════════════════════════════════════════
# CANCEL FLOW
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "cg_flow_cancel")
async def cancel_flow(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена любого текущего flow."""
    user_id = callback.from_user.id
    # Удаляем черновики всех типов если есть
    async with get_async_session() as session:
        for dtype in ("goal_creation", "habit_creation", "checkin", "review"):
            try:
                await cs.delete_draft(session, user_id, dtype)
            except Exception:
                pass
        await session.commit()
    await state.clear()
    await callback.message.edit_text(
        "❌ Отменено. Возвращайся когда будешь готов! /coaching",
        reply_markup=None,
    )
    await callback.answer("Отменено")


# ══════════════════════════════════════════════════════════════════════════════
# CHECK-IN FOLLOW-UP ПОСЛЕ ВЫБОРА НАСТРОЕНИЯ
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "cg_ci_fb_block")
async def checkin_followup_block(callback: CallbackQuery, state: FSMContext) -> None:
    """Follow-up: рассказать что мешало → переходим к блокерам."""
    from bot.keyboards.coaching_keyboards import skip_cancel_kb
    await state.set_state(CoachingCheckIn.waiting_blockers)
    await callback.message.edit_text(
        "🚧 *Что мешало?*\n_Напиши или пропусти:_",
        reply_markup=skip_cancel_kb("cg_flow_skip_blockers"),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_ci_fb_step")
async def checkin_followup_step(callback: CallbackQuery, state: FSMContext) -> None:
    """Follow-up: дай следующий шаг → завершаем check-in и даём совет."""
    await finish_checkin(callback, state, blockers="")


@router.callback_query(F.data == "cg_ci_fb_ok")
async def checkin_followup_ok(callback: CallbackQuery, state: FSMContext) -> None:
    """Follow-up: всё ок → завершаем check-in без блокеров."""
    await finish_checkin(callback, state, blockers="")


# ══════════════════════════════════════════════════════════════════════════════
# WEEKLY REVIEW: СТАТУС ЦЕЛЕЙ И ДЕЙСТВИЯ ПОСЛЕ
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("cg_wr_gs_"))
async def wr_goal_status(callback: CallbackQuery) -> None:
    """Статус цели в рамках weekly review — формат cg_wr_gs_{id}_{status}."""
    # Разбираем: cg_wr_gs_{goal_id}_{status}
    parts = callback.data.split("_")  # ["cg","wr","gs","{id}","{status}"]
    if len(parts) < 5:
        await callback.answer("Ошибка"); return
    try:
        goal_id = int(parts[3])
    except ValueError:
        await callback.answer("Ошибка"); return
    status = parts[4]  # ok, slow, stuck, freeze
    user_id = callback.from_user.id
    status_labels = {"ok": "🟢 Двигаюсь", "slow": "🟡 Медленно", "stuck": "🔴 Буксую", "freeze": "❄️ Заморожена"}
    label = status_labels.get(status, status)
    if status == "freeze":
        # Помечаем цель как замороженную
        async with get_async_session() as session:
            await cs.update_goal(session, goal_id, user_id, is_frozen=True, frozen_reason="Заморожена по итогам review")
            await session.commit()
        await callback.answer(f"{label} — цель заморожена")
    elif status == "stuck":
        # Показываем карточку с вариантами для застрявшей цели
        async with get_async_session() as session:
            goal = await cs.get_goal(session, goal_id, user_id)
        if goal:
            await callback.message.answer(
                f"🔴 *{goal.title}* буксует.\n\nЧто поможет сдвинуться?",
                reply_markup=goal_stuck_kb(goal_id),
                parse_mode="Markdown",
            )
        await callback.answer()
    else:
        await callback.answer(f"Записано: {label}")


@router.callback_query(F.data == "cg_wr_after_adjust")
async def wr_after_adjust(callback: CallbackQuery) -> None:
    """После review: скорректировать план → список целей."""
    await callback.message.answer(
        "📝 *Корректируем план:*\n\nВыбери цель для изменения:",
        reply_markup=coaching_main_kb(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_wr_after_reduce")
async def wr_after_reduce(callback: CallbackQuery) -> None:
    """После review: снизить нагрузку → overload-меню."""
    await callback.message.edit_text(
        "📉 *Снижаем нагрузку:*\n\nЧто заморозим или упростим?",
        reply_markup=overload_kb(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_wr_after_boost")
async def wr_after_boost(callback: CallbackQuery) -> None:
    """После review: усилить темп → momentum-меню."""
    await callback.message.edit_text(
        "📈 *Усиляем темп!*\n\nОтлично, давай добавим ещё:",
        reply_markup=momentum_kb(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_wr_after_ok")
async def wr_after_ok(callback: CallbackQuery) -> None:
    """После review: всё устраивает → главное меню."""
    await callback.message.edit_text(
        "✅ *Отлично!* Продолжай в том же духе.\n\nДо следующего обзора! 💪",
        reply_markup=coaching_main_kb(),
        parse_mode="Markdown",
    )
    await callback.answer()


# ════════════════════════════════════════════════════════════════════════════════
# ПРОАКТИВНЫЕ ДНЕВНЫЕ ЧЕКИНЫ: callback handlers
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("cg_daily_morning_e"))
async def daily_morning_energy_cb(callback: CallbackQuery) -> None:
    """
    Утренний чекин энергии.
    Формат: cg_daily_morning_e{1-5}.
    """
    e_str = callback.data.replace("cg_daily_morning_e", "")
    try:
        energy = int(e_str)
        if energy < 1 or energy > 5:
            raise ValueError
    except ValueError:
        await callback.answer("⚠️ Неверный формат")
        return
    await save_morning_checkin(callback, energy=energy)


@router.callback_query(F.data.startswith("cg_daily_midday_e"))
async def daily_midday_energy_cb(callback: CallbackQuery) -> None:
    """
    Дневной пульс энергии.
    Формат: cg_daily_midday_e{1-5}.
    """
    e_str = callback.data.replace("cg_daily_midday_e", "")
    try:
        energy = int(e_str)
        if energy < 1 or energy > 5:
            raise ValueError
    except ValueError:
        await callback.answer("⚠️ Неверный формат")
        return
    await save_midday_checkin(callback, energy=energy)


@router.callback_query(F.data.startswith("cg_daily_evening_m"))
async def daily_evening_mood_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Вечерний чекин — выбор настроения.
    Формат: cg_daily_evening_m{1-5}.
    """
    m_str = callback.data.replace("cg_daily_evening_m", "")
    try:
        mood = int(m_str)
        if mood < 1 or mood > 5:
            raise ValueError
    except ValueError:
        await callback.answer("⚠️ Неверный формат")
        return
    await start_evening_reflection(callback, state, mood=mood)


@router.callback_query(F.data.startswith("cg_daily_evening_day_"))
async def daily_evening_day_result_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Выбор итога дня (quick-кнопки).
    Формат: cg_daily_evening_day_{great|ok|hard|text}.
    """
    result = callback.data.replace("cg_daily_evening_day_", "")
    if result == "text":
        # Пользователь выбрал «напишу сам» — ждём текстовый ввод в FSM
        await callback.message.edit_text(
            "*Как прошёл день?* Напиши своими словами:\n"
            "_Например: «Продуктивно, закрыл 3 задачи, но устал к вечеру»_",
            parse_mode="Markdown",
        )
        await callback.answer()
        return
    await handle_evening_day_result(callback, state, day_result=result)


@router.callback_query(F.data == "cg_daily_evening_skip_notes")
async def daily_evening_skip_notes_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Пропуск шага 'заметки о дне' — переходим к блокерам."""
    await handle_evening_notes(callback, state, notes="")


@router.callback_query(F.data == "cg_daily_evening_skip_blockers")
async def daily_evening_skip_blockers_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Пропуск шага 'блокеры' — переходим к победам."""
    await handle_evening_blockers(callback, state, blockers="")


@router.callback_query(F.data == "cg_daily_evening_skip_wins")
async def daily_evening_skip_wins_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Пропуск шага 'победы' — завершаем вечернюю рефлексию."""
    await finish_evening_reflection(callback, state, wins="")
