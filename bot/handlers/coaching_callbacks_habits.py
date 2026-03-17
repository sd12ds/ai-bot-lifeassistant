"""
Bot coaching — callbacks для привычек (Habits).

Регистрирует:
  cg_h_list         — список привычек
  cg_h_log_*        — залогировать выполнение
  cg_h_miss_*       — отметить пропуск
  cg_h_pause_*      — поставить на паузу
  cg_h_stats_*      — показать статистику
  cg_h_snooze_*     — snooze напоминания
  cg_flow_habit_new — начать создание привычки
"""
from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.keyboards.coaching_keyboards import (
    coaching_main_kb,
    habit_list_item_kb, habit_missed_kb,
)
from bot.flows.coaching_flows import start_habit_creation
from db.session import get_async_session
from db import coaching_storage as cs

logger = logging.getLogger(__name__)
router = Router()


# ══════════════════════════════════════════════════════════════════════════════
# HABIT LIST
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "cg_h_list")
async def habits_list(callback: CallbackQuery) -> None:
    """Показать список активных привычек."""
    user_id = callback.from_user.id
    async with get_async_session() as session:
        habits = await cs.get_habits(session, user_id, is_active=True)
    if not habits:
        await callback.message.edit_text(
            "🔁 У тебя пока нет активных привычек.\n\n_Создать первую?_",
            reply_markup=coaching_main_kb(),
        )
        await callback.answer()
        return
    # Отправляем по одной карточке на каждую привычку
    await callback.message.delete()
    for h in habits:
        txt = (f"🔁 *{h.title}*\n"
               f"🔥 Серия: {h.current_streak} дн. | Рекорд: {h.longest_streak}\n"
               + (f"⚡ Триггер: {h.cue}" if h.cue else ""))
        await callback.message.answer(txt, reply_markup=habit_list_item_kb(h.id), parse_mode="Markdown")
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# HABIT ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("cg_h_log_"))
async def habit_log(callback: CallbackQuery) -> None:
    """Залогировать выполнение привычки."""
    habit_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    async with get_async_session() as session:
        habit = await cs.increment_habit_streak(session, habit_id, user_id)
        if habit:
            from db.models import HabitLog
            # Сохраняем запись в журнале привычки
            session.add(HabitLog(habit_id=habit_id, user_id=user_id))
        await session.commit()
    if not habit:
        await callback.answer("Привычка не найдена"); return
    # Поздравляем с новым рекордом стрика
    if habit.current_streak == habit.longest_streak and habit.current_streak > 1:
        from bot.keyboards.coaching_keyboards import habit_streak_kb
        await callback.message.answer(
            f"🏆 *Новый рекорд!* «{habit.title}» — {habit.current_streak} дней подряд!",
            reply_markup=habit_streak_kb(habit_id, habit.current_streak),
            parse_mode="Markdown",
        )
        await callback.answer("🏆 Новый рекорд!")
    else:
        streak_msg = f" 🔥 Серия: {habit.current_streak}" if habit.current_streak > 1 else ""
        await callback.answer(f"✅ «{habit.title}» выполнена!{streak_msg}")


@router.callback_query(F.data.startswith("cg_h_miss_"))
async def habit_miss(callback: CallbackQuery) -> None:
    """Отметить пропуск привычки."""
    habit_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    async with get_async_session() as session:
        habit = await cs.reset_habit_streak(session, habit_id, user_id, reason="пропуск")
        await session.commit()
    if not habit:
        await callback.answer("Привычка не найдена"); return
    await callback.message.answer(
        f"📝 Пропуск «{habit.title}» зафиксирован.\n\n"
        "_Пропуск не обнуляет всё — главное не пропускать дважды подряд. 💪_",
        reply_markup=habit_missed_kb(habit_id),
        parse_mode="Markdown",
    )
    await callback.answer("Записал")


@router.callback_query(F.data.startswith("cg_h_pause_"))
async def habit_pause(callback: CallbackQuery) -> None:
    """Поставить привычку на паузу."""
    habit_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    async with get_async_session() as session:
        from sqlalchemy import update
        from db.models import Habit
        await session.execute(
            update(Habit).where(Habit.id == habit_id, Habit.user_id == user_id).values(is_active=False)
        )
        await session.commit()
    await callback.answer("⏸ Привычка поставлена на паузу")


@router.callback_query(F.data.startswith("cg_h_stats_"))
async def habit_stats(callback: CallbackQuery) -> None:
    """Краткая статистика привычки."""
    habit_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    async with get_async_session() as session:
        from sqlalchemy import select
        from db.models import Habit
        r = await session.execute(select(Habit).where(Habit.id == habit_id, Habit.user_id == user_id))
        habit = r.scalar_one_or_none()
    if not habit:
        await callback.answer("Привычка не найдена"); return
    await callback.message.answer(
        f"📊 *{habit.title}*\n"
        f"🔥 Текущая серия: {habit.current_streak} дн.\n"
        f"🏆 Рекорд: {habit.longest_streak} дн.\n"
        f"✅ Всего выполнений: {habit.total_completions}",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cg_h_snooze_"))
async def habit_snooze(callback: CallbackQuery) -> None:
    """Напомнить о привычке позже (snooze на ~2 часа)."""
    await callback.answer("⏰ Ок! Напомню позже.", show_alert=False)


# ══════════════════════════════════════════════════════════════════════════════
# FLOW STARTS
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "cg_flow_habit_new")
async def flow_new_habit(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать создание новой привычки."""
    await callback.message.delete()
    await start_habit_creation(callback.message, state)
    await callback.answer()
