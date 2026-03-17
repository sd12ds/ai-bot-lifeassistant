"""
Bot coaching — FSM text message handlers и Voice Checkin (VCI) flow.

Регистрирует:
  --- Goal Creation FSM ---
  fsm_goal_title, fsm_goal_why, fsm_goal_first_step, fsm_goal_deadline

  --- Habit Creation FSM ---
  fsm_habit_title, fsm_habit_cue, fsm_habit_reward

  --- Check-In FSM ---
  fsm_checkin_wins, fsm_checkin_progress, fsm_checkin_blockers

  --- Weekly Review FSM ---
  fsm_review_summary, fsm_review_highlights, fsm_review_blockers, fsm_review_next_actions

  --- Evening Reflection FSM ---
  evening_day_result_text_handler, evening_notes_text_handler,
  evening_blockers_text_handler, evening_wins_text_handler

  --- Voice Checkin (VCI) ---
  vci_save_handler, vci_edit_handler, vci_cancel_handler, vci_edit_text_handler
"""
from __future__ import annotations

import json as _json
from datetime import date as _date

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.states import (
    CoachingGoalCreation, CoachingHabitCreation,
    CoachingCheckIn, CoachingWeeklyReview,
    DailyEveningReflection, VoiceCheckinFlow,
)
from bot.flows.coaching_flows import (
    handle_goal_title, handle_goal_why, handle_goal_first_step, handle_goal_deadline,
    handle_habit_title, handle_habit_cue, handle_habit_reward, finish_habit_creation,
    handle_checkin_wins, handle_checkin_progress, finish_checkin,
    handle_review_summary, handle_review_highlights, handle_review_blockers, finish_weekly_review,
    handle_evening_day_result, handle_evening_notes, handle_evening_blockers, finish_evening_reflection,
)
from db.session import get_async_session
from db import coaching_storage as cs
from services.voice_checkin_parser import (
    detect_slot, detect_date, parse_checkin_fields,
    format_checkin_card,
)
from bot.keyboards.voice_checkin_kb import voice_checkin_confirm_kb

router = Router()


# ══════════════════════════════════════════════════════════════════════════════
# GOAL CREATION FSM
# ══════════════════════════════════════════════════════════════════════════════

@router.message(StateFilter(CoachingGoalCreation.waiting_title), F.text)
async def fsm_goal_title(message: Message, state: FSMContext) -> None:
    """Ввод названия цели в FSM."""
    await handle_goal_title(message, state)


@router.message(StateFilter(CoachingGoalCreation.waiting_why), F.text)
async def fsm_goal_why(message: Message, state: FSMContext) -> None:
    """Ввод «зачем» цели в FSM."""
    await handle_goal_why(message, state)


@router.message(StateFilter(CoachingGoalCreation.waiting_first_step), F.text)
async def fsm_goal_first_step(message: Message, state: FSMContext) -> None:
    """Ввод первого шага цели в FSM."""
    await handle_goal_first_step(message, state)


@router.message(StateFilter(CoachingGoalCreation.waiting_deadline), F.text)
async def fsm_goal_deadline(message: Message, state: FSMContext) -> None:
    """Ввод дедлайна цели в FSM."""
    await handle_goal_deadline(message, state)


# ══════════════════════════════════════════════════════════════════════════════
# HABIT CREATION FSM
# ══════════════════════════════════════════════════════════════════════════════

@router.message(StateFilter(CoachingHabitCreation.waiting_title), F.text)
async def fsm_habit_title(message: Message, state: FSMContext) -> None:
    """Ввод названия привычки в FSM."""
    await handle_habit_title(message, state)


@router.message(StateFilter(CoachingHabitCreation.waiting_cue), F.text)
async def fsm_habit_cue(message: Message, state: FSMContext) -> None:
    """Ввод триггера привычки в FSM."""
    await handle_habit_cue(message, state)


@router.message(StateFilter(CoachingHabitCreation.waiting_reward), F.text)
async def fsm_habit_reward(message: Message, state: FSMContext) -> None:
    """Ввод награды привычки в FSM."""
    await handle_habit_reward(message, state)


# ══════════════════════════════════════════════════════════════════════════════
# CHECK-IN FSM
# ══════════════════════════════════════════════════════════════════════════════

@router.message(StateFilter(CoachingCheckIn.waiting_wins), F.text)
async def fsm_checkin_wins(message: Message, state: FSMContext) -> None:
    """Ввод побед в FSM check-in."""
    await handle_checkin_wins(message, state)


@router.message(StateFilter(CoachingCheckIn.waiting_progress), F.text)
async def fsm_checkin_progress(message: Message, state: FSMContext) -> None:
    """Ввод прогресса вручную (число)."""
    try:
        # Ограничиваем значение диапазоном 0-100
        progress = max(0, min(100, int(message.text.strip())))
    except ValueError:
        await message.answer("Введи число от 0 до 100:")
        return
    await handle_checkin_progress(message, state, progress=progress)


@router.message(StateFilter(CoachingCheckIn.waiting_blockers), F.text)
async def fsm_checkin_blockers(message: Message, state: FSMContext) -> None:
    """Ввод блокеров в FSM check-in."""
    await finish_checkin(message, state)


# ══════════════════════════════════════════════════════════════════════════════
# WEEKLY REVIEW FSM
# ══════════════════════════════════════════════════════════════════════════════

@router.message(StateFilter(CoachingWeeklyReview.waiting_summary), F.text)
async def fsm_review_summary(message: Message, state: FSMContext) -> None:
    """Ввод итогов недели в FSM review."""
    await handle_review_summary(message, state)


@router.message(StateFilter(CoachingWeeklyReview.waiting_highlights), F.text)
async def fsm_review_highlights(message: Message, state: FSMContext) -> None:
    """Ввод достижений в FSM review."""
    await handle_review_highlights(message, state)


@router.message(StateFilter(CoachingWeeklyReview.waiting_blockers), F.text)
async def fsm_review_blockers(message: Message, state: FSMContext) -> None:
    """Ввод блокеров в FSM review."""
    await handle_review_blockers(message, state)


@router.message(StateFilter(CoachingWeeklyReview.waiting_next_actions), F.text)
async def fsm_review_next_actions(message: Message, state: FSMContext) -> None:
    """Ввод следующих действий — завершение FSM review."""
    await finish_weekly_review(message, state)


# ══════════════════════════════════════════════════════════════════════════════
# EVENING REFLECTION FSM text handlers
# ══════════════════════════════════════════════════════════════════════════════

@router.message(StateFilter(DailyEveningReflection.waiting_day_result))
async def evening_day_result_text_handler(message: Message, state: FSMContext) -> None:
    """Текстовый ввод итога дня (когда выбрал 'напишу сам')."""
    await handle_evening_day_result(message, state, day_result=message.text.strip())


@router.message(StateFilter(DailyEveningReflection.waiting_notes))
async def evening_notes_text_handler(message: Message, state: FSMContext) -> None:
    """Текстовый ввод заметок о дне (шаг 2 вечерней рефлексии)."""
    await handle_evening_notes(message, state, notes=message.text.strip())


@router.message(StateFilter(DailyEveningReflection.waiting_blockers))
async def evening_blockers_text_handler(message: Message, state: FSMContext) -> None:
    """Текстовый ввод блокеров (шаг 3 вечерней рефлексии)."""
    await handle_evening_blockers(message, state, blockers=message.text.strip())


@router.message(StateFilter(DailyEveningReflection.waiting_wins))
async def evening_wins_text_handler(message: Message, state: FSMContext) -> None:
    """Текстовый ввод побед дня (шаг 4 — финал вечерней рефлексии)."""
    await finish_evening_reflection(message, state, wins=message.text.strip())


# ══════════════════════════════════════════════════════════════════════════════
# VOICE CHECKIN FLOW — подтверждение и правка голосового чекина
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("vci_save:"))
async def vci_save_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохраняет голосовой чекин из FSM data в БД."""
    data = await state.get_data()
    slot = data.get("slot", "manual")
    check_date_str = data.get("check_date", "")
    fields_raw = data.get("fields", "{}")

    try:
        fields = _json.loads(fields_raw)
    except Exception:
        fields = {}

    # Определяем дату — из FSM или сегодня
    if check_date_str:
        try:
            check_date = _date.fromisoformat(check_date_str)
        except ValueError:
            check_date = _date.today()
    else:
        check_date = _date.today()

    user_id = callback.from_user.id

    async with get_async_session() as session:
        await cs.create_goal_checkin(
            session,
            goal_id=None,  # Голосовой чекин не привязан к конкретной цели
            user_id=user_id,
            energy_level=fields.get("energy_level") or None,
            mood=fields.get("mood") or None,
            notes=fields.get("notes") or None,
            wins=fields.get("wins") or None,
            blockers=fields.get("blockers") or None,
            time_slot=slot,
            check_date=check_date,
        )
        await session.commit()

    # Очищаем FSM state после сохранения
    await state.clear()

    slot_labels = {"morning": "🌅 Утро", "midday": "☀️ День", "evening": "🌙 Вечер", "manual": "📝"}
    slot_label = slot_labels.get(slot, slot)

    await callback.message.edit_text(
        f"✅ Чекин сохранён! {slot_label}\n"
        f"Дата: {check_date.strftime('%d.%m.%Y')}\n\n"
        f"Данные добавлены в твою историю.",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("vci_edit:"))
async def vci_edit_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Переходит в режим правки: ждёт текстового/голосового уточнения."""
    await state.set_state(VoiceCheckinFlow.waiting_edit)
    await callback.message.edit_text(
        "✏️ Напиши или надиктуй, что хочешь изменить.\n\n"
        "_Например: «Энергия была 4» или «Победы: доделал проект»_",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "vci_cancel")
async def vci_cancel_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Отменяет голосовой чекин."""
    await state.clear()
    await callback.message.edit_text("❌ Чекин отменён.")
    await callback.answer()


@router.message(StateFilter(VoiceCheckinFlow.waiting_edit))
async def vci_edit_text_handler(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает текстовую правку чекина.
    Повторно парсит поля и показывает обновлённую карточку.
    """
    data = await state.get_data()
    slot = data.get("slot", "manual")
    check_date_str = data.get("check_date", _date.today().isoformat())
    old_fields_raw = data.get("fields", "{}")

    try:
        old_fields = _json.loads(old_fields_raw)
    except Exception:
        old_fields = {}

    # Повторный LLM-парсинг правки
    edit_text = message.text or ""
    new_fields = await parse_checkin_fields(edit_text, slot)

    # Мержим: новые значения перезаписывают старые (только непустые)
    merged = {**old_fields}
    for k, v in new_fields.items():
        if v is not None:
            merged[k] = v

    try:
        check_date = _date.fromisoformat(check_date_str)
    except ValueError:
        check_date = _date.today()

    card_text = format_checkin_card(
        slot=slot,
        check_date=check_date,
        fields=merged,
        transcribed_text=edit_text,
    )

    # Сохраняем обновлённые данные в FSM и переключаемся на ожидание подтверждения
    await state.update_data(fields=_json.dumps(merged, ensure_ascii=False))
    await state.set_state(VoiceCheckinFlow.waiting_confirmation)

    await message.answer(
        card_text,
        parse_mode="Markdown",
        reply_markup=voice_checkin_confirm_kb(slot, check_date_str),
    )
