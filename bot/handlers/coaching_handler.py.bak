"""
CoachingHandler — Aiogram Router для всего Coaching модуля.

Регистрирует:
  /coaching                  — главное меню коуча
  cg_g_*                     — действия с целями
  cg_h_*                     — действия с привычками
  cg_ci_*                    — check-in (прогресс, энергия)
  cg_wr_*                    — weekly review
  cg_ob_*                    — onboarding
  cg_area_*, cg_harea_*      — выбор области в flow
  cg_flow_*                  — управление flow (skip/cancel)
  cg_s_*                     — контекстные состояния
  cg_recs, cg_memory         — рекомендации, память
  FSM handlers               — текстовые ответы внутри flow
"""
from __future__ import annotations
import logging
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.states import (
    CoachingGoalCreation, CoachingHabitCreation,
    CoachingCheckIn, CoachingWeeklyReview,
    DailyEveningReflection, VoiceCheckinFlow,
)
from bot.keyboards.coaching_keyboards import (
    coaching_main_kb, goal_card_kb, goal_after_create_kb, goal_list_item_kb,
    habit_list_item_kb, habit_daily_kb, habit_missed_kb,
    goal_stuck_kb, goal_achieved_kb, weekly_review_kb,
    checkin_after_mood_kb, review_goal_status_kb, motivational_kb,
    momentum_kb, overload_kb, recovery_kb,
    onboarding_kb, onboarding_done_kb,
    onboarding_profile_intro_kb, onboarding_focus_area_kb, onboarding_tone_kb,
    onboarding_checkin_time_kb, onboarding_first_action_kb,
)
from bot.flows.coaching_flows import (
    start_goal_creation, handle_goal_area, handle_goal_title,
    handle_goal_why, handle_goal_first_step, handle_goal_deadline,
    start_habit_creation, handle_habit_title, handle_habit_area,
    handle_habit_cue, handle_habit_reward, finish_habit_creation,
    start_checkin_flow, handle_checkin_wins, handle_checkin_progress,
    handle_checkin_energy, finish_checkin,
    start_weekly_review, handle_review_summary, handle_review_highlights,
    handle_review_blockers, finish_weekly_review,
    save_morning_checkin, save_midday_checkin,
    start_evening_reflection, handle_evening_day_result,
    handle_evening_notes, handle_evening_blockers, finish_evening_reflection,
)
from db.session import get_async_session
from db import coaching_storage as cs
from services.coaching_personalization import reset_personalization
from services.coaching_cross_module import execute_orchestration_action

logger = logging.getLogger(__name__)
router = Router()


# ══════════════════════════════════════════════════════════════════════════════
# /coaching — главное меню
# ══════════════════════════════════════════════════════════════════════════════

@router.message(Command("coaching"))
async def coaching_main(message: Message, state: FSMContext) -> None:
    """Открывает главное меню коуча с текущим статусом."""
    await state.clear()
    user_id = message.from_user.id
    # Открываем единственный session-контекст для всех DB-запросов
    async with get_async_session() as session:
        goals = await cs.get_goals(session, user_id, status="active")
        habits = await cs.get_habits(session, user_id, is_active=True)
        onboarding = await cs.get_or_create_onboarding(session, user_id)

        # Онбординг Шаг 1 — знакомство + приглашение к профилированию
        # ВАЖНО: profile-запрос должен быть внутри async with, иначе session закрыта
        if not onboarding.bot_onboarding_done:
            profile = await cs.get_or_create_profile(session, user_id)
            await session.commit()
            if profile.onboarding_completed:
                # Профиль уже настроен — сразу к первому действию
                await message.answer(
                    "👋 *Привет снова!*\n\nГотов работать над твоими целями. С чего начнём?",
                    reply_markup=onboarding_first_action_kb(),
                    parse_mode="Markdown",
                )
            else:
                # Впервые — полный онбординг
                await message.answer(
                    "👋 *Привет! Я твой AI-коуч.*\n\n"
                    "Помогу ставить и достигать цели, формировать привычки и двигаться вперёд системно.\n\n"
                    "*Как работаю:*\n"
                    "🎯 *Цели* — конкретные, с этапами и дедлайнами\n"
                    "🔁 *Привычки* — ежедневный трекинг с серией (стрик)\n"
                    "✅ *Check-in* — фиксируем прогресс и энергию\n"
                    "📊 *Обзор недели* — рефлексия и план\n\n"
                    "Чтобы я давал точные советы — настрою коуча под тебя за 30 секунд.",
                    reply_markup=onboarding_profile_intro_kb(),
                    parse_mode="Markdown",
                )
            return

        await session.commit()

    goals_count = len(goals)
    habits_count = len(habits)

    # Обычное меню коуча с кнопками
    status_text = ""
    if goals_count > 0:
        active_goals = [f"• {g.title} — {g.progress_pct}%" for g in goals[:3]]
        status_text += f"\n🎯 *Цели ({goals_count}):*\n" + "\n".join(active_goals)
    if habits_count > 0:
        streaks = [f"• {h.title} 🔥{h.current_streak}" for h in habits[:3]]
        status_text += f"\n\n🔁 *Привычки ({habits_count}):*\n" + "\n".join(streaks)
    if not status_text:
        status_text = "\n\n_Пока нет целей и привычек — создадим?_"

    await message.answer(
        f"🤖 *Твой коуч*{status_text}",
        reply_markup=coaching_main_kb(),
        parse_mode="Markdown",
    )


# ══════════════════════════════════════════════════════════════════════════════
# ONBOARDING CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "cg_ob_goal")
async def ob_start_goal(callback: CallbackQuery, state: FSMContext) -> None:
    """Онбординг → создать первую цель."""
    user_id = callback.from_user.id
    async with get_async_session() as session:
        await cs.advance_onboarding_step(session, user_id, "intro")
        await session.commit()
    await callback.message.delete()
    await start_goal_creation(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "cg_ob_habit")
async def ob_start_habit(callback: CallbackQuery, state: FSMContext) -> None:
    """Онбординг → создать первую привычку."""
    user_id = callback.from_user.id
    async with get_async_session() as session:
        await cs.advance_onboarding_step(session, user_id, "intro")
        await session.commit()
    await callback.message.delete()
    await start_habit_creation(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "cg_ob_examples")
async def ob_examples(callback: CallbackQuery) -> None:
    """Онбординг → примеры."""
    await callback.message.edit_text(
        "📖 *Примеры целей:*\n"
        "• Сбросить 5 кг к 1 июня\n"
        "• Читать 1 книгу в месяц\n"
        "• Зарабатывать 200 тыс/мес к концу года\n\n"
        "📖 *Примеры привычек:*\n"
        "• Медитация 10 мин — после кофе\n"
        "• Читать 20 страниц — перед сном\n"
        "• Зарядка 15 мин — сразу после подъёма\n\n"
        "_С чего начнём?_",
        reply_markup=onboarding_kb(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_ob_skip")
async def ob_skip(callback: CallbackQuery) -> None:
    """Онбординг → пропустить."""
    user_id = callback.from_user.id
    async with get_async_session() as session:
        state_obj = await cs.get_or_create_onboarding(session, user_id)
        state_obj.bot_onboarding_done = True
        await session.commit()
    await callback.message.edit_text(
        "OK, заходи когда будешь готов! Используй /coaching чтобы открыть меню коуча.",
        reply_markup=None,
    )
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# ОНБОРДИНГ — ШАГ 2: ПРОФИЛИРОВАНИЕ
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "cg_ob_profile_start")
async def ob_profile_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало профилирования — выбор фокусных областей."""
    await state.update_data(ob_focus_areas=[])
    await callback.message.edit_text(
        "🎯 *Какие сферы жизни хочешь прокачать?*\n\n"
        "Можно выбрать несколько. Нажми ✅ Готово когда закончишь.",
        reply_markup=onboarding_focus_area_kb([]),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_ob_profile_skip")
async def ob_profile_skip(callback: CallbackQuery) -> None:
    """Пропуск профилирования — сразу к первому действию."""
    user_id = callback.from_user.id
    async with get_async_session() as session:
        await cs.update_profile(session, user_id, onboarding_completed=True)
        ob = await cs.get_or_create_onboarding(session, user_id)
        ob.bot_onboarding_done = True
        await session.commit()
    await callback.message.edit_text(
        "OK! Давай создадим что-нибудь первое.",
        reply_markup=onboarding_first_action_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cg_ob_focus_") & ~F.data.endswith("_done"))
async def ob_toggle_focus(callback: CallbackQuery, state: FSMContext) -> None:
    """Переключение фокусной области (toggle)."""
    area = callback.data.replace("cg_ob_focus_", "")
    data = await state.get_data()
    selected: list = data.get("ob_focus_areas", [])
    if area in selected:
        selected.remove(area)
    else:
        selected.append(area)
    await state.update_data(ob_focus_areas=selected)
    await callback.message.edit_reply_markup(reply_markup=onboarding_focus_area_kb(selected))
    await callback.answer()


@router.callback_query(F.data == "cg_ob_focus_done")
async def ob_focus_done(callback: CallbackQuery, state: FSMContext) -> None:
    """Зафиксировать выбор областей → выбор тона."""
    data = await state.get_data()
    selected = data.get("ob_focus_areas", [])
    user_id = callback.from_user.id
    if selected:
        async with get_async_session() as session:
            await cs.update_profile(session, user_id, focus_areas=selected)
            await session.commit()
    await callback.message.edit_text(
        "✅ *Записал!*\n\n🎙️ *Как тебе удобнее общаться с коучем?*",
        reply_markup=onboarding_tone_kb(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cg_ob_tone_"))
async def ob_set_tone(callback: CallbackQuery) -> None:
    """Выбор тона коуча → выбор времени чекина."""
    tone = callback.data.replace("cg_ob_tone_", "")
    user_id = callback.from_user.id
    async with get_async_session() as session:
        await cs.update_profile(session, user_id, coach_tone=tone)
        await session.commit()
    tone_labels = {
        "friendly": "😊 Дружелюбный",
        "motivational": "🚀 Мотивационный",
        "strict": "💪 Требовательный",
        "soft": "🕊️ Мягкий",
    }
    label = tone_labels.get(tone, tone)
    await callback.message.edit_text(
        f"✅ Тон коуча: *{label}*\n\n"
        "⏰ *Когда лучше всего напоминать о check-in?*",
        reply_markup=onboarding_checkin_time_kb(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cg_ob_time_"))
async def ob_set_time(callback: CallbackQuery) -> None:
    """Выбор времени чекина → завершение профилирования."""
    time_val = callback.data.replace("cg_ob_time_", "")
    user_id = callback.from_user.id
    async with get_async_session() as session:
        updates = {"onboarding_completed": True}
        if time_val != "skip":
            updates["preferred_checkin_time"] = time_val
        await cs.update_profile(session, user_id, **updates)
        ob = await cs.get_or_create_onboarding(session, user_id)
        ob.bot_onboarding_done = True
        await session.commit()
    await callback.message.edit_text(
        "🎉 *Готово! Профиль коуча настроен.*\n\n"
        "Теперь я смогу давать персональные советы.\n"
        "С чего начнём?",
        reply_markup=onboarding_first_action_kb(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_ob_done_main")
async def ob_done_main(callback: CallbackQuery) -> None:
    """Завершение онбординга → главное меню."""
    user_id = callback.from_user.id
    async with get_async_session() as session:
        ob = await cs.get_or_create_onboarding(session, user_id)
        ob.bot_onboarding_done = True
        await cs.update_profile(session, user_id, onboarding_completed=True)
        await session.commit()
    await callback.message.edit_text(
        "Используй /coaching для доступа к меню коуча.",
        reply_markup=None,
    )
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# GOAL LIST
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "cg_g_list")
async def goals_list(callback: CallbackQuery) -> None:
    """Показать список активных целей."""
    user_id = callback.from_user.id
    async with get_async_session() as session:
        goals = await cs.get_goals(session, user_id, status="active")
    if not goals:
        await callback.message.edit_text(
            "🎯 У тебя пока нет активных целей.\n\n_Создать первую?_",
            reply_markup=coaching_main_kb(),
        )
        await callback.answer()
        return
    # Отправляем по одной карточке
    await callback.message.delete()
    for goal in goals:
        frozen_mark = " 🧊" if goal.is_frozen else ""
        deadline_mark = f" (до {goal.target_date})" if goal.target_date else ""
        txt = (f"🎯 *{goal.title}*{frozen_mark}\n"
               f"Прогресс: {goal.progress_pct}%{deadline_mark}\n"
               + (f"💡 {goal.why_statement[:60]}..." if goal.why_statement and len(goal.why_statement) > 60
                  else (f"💡 {goal.why_statement}" if goal.why_statement else "")))
        await callback.message.answer(txt, reply_markup=goal_card_kb(goal.id, goal.is_frozen), parse_mode="Markdown")
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# GOAL ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("cg_g_checkin_"))
async def goal_checkin(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать check-in по цели."""
    goal_id = int(callback.data.split("_")[-1])
    await start_checkin_flow(callback, state, goal_id=goal_id)


@router.callback_query(F.data.startswith("cg_g_progress_"))
async def goal_progress(callback: CallbackQuery, state: FSMContext) -> None:
    """Быстрое обновление прогресса цели."""
    goal_id = int(callback.data.split("_")[-1])
    await start_checkin_flow(callback, state, goal_id=goal_id)


@router.callback_query(F.data.startswith("cg_g_freeze_"))
async def goal_freeze(callback: CallbackQuery) -> None:
    """Заморозить цель."""
    goal_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    async with get_async_session() as session:
        goal = await cs.update_goal(session, goal_id, user_id, is_frozen=True, frozen_reason="Поставлена на паузу")
        await session.commit()
    if goal:
        await callback.message.edit_reply_markup(reply_markup=goal_card_kb(goal.id, is_frozen=True))
        await callback.answer(f"🧊 «{goal.title}» заморожена")
    else:
        await callback.answer("Цель не найдена")


@router.callback_query(F.data.startswith("cg_g_resume_"))
async def goal_resume(callback: CallbackQuery) -> None:
    """Возобновить замороженную цель."""
    goal_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    async with get_async_session() as session:
        goal = await cs.update_goal(session, goal_id, user_id, is_frozen=False, frozen_reason=None)
        await session.commit()
    if goal:
        await callback.message.edit_reply_markup(reply_markup=goal_card_kb(goal.id, is_frozen=False))
        await callback.answer(f"▶️ «{goal.title}» возобновлена!")
    else:
        await callback.answer("Цель не найдена")


@router.callback_query(F.data.startswith("cg_g_restart_"))
async def goal_restart(callback: CallbackQuery) -> None:
    """Перезапустить цель (сброс прогресса)."""
    goal_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    async with get_async_session() as session:
        goal = await cs.update_goal(session, goal_id, user_id, status="active", progress_pct=0, is_frozen=False)
        await session.commit()
    if goal:
        await callback.answer(f"🔄 «{goal.title}» перезапущена! С нуля.")
    else:
        await callback.answer("Цель не найдена")


@router.callback_query(F.data.startswith("cg_g_done_"))
async def goal_done(callback: CallbackQuery) -> None:
    """Отметить цель как достигнутую."""
    goal_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    async with get_async_session() as session:
        goal = await cs.update_goal(session, goal_id, user_id, status="achieved", progress_pct=100)
        await session.commit()
    if goal:
        # Передаём goal_id чтобы кнопка рефлексии знала о какой цели речь
        await callback.message.edit_text(
            f"🏆 *ЦЕЛЬ ДОСТИГНУТА!*\n\n🎉 «{goal.title}»\n\nПоздравляю! Это большая победа! 💪\n\n_Что дальше?_",
            reply_markup=goal_achieved_kb(goal_id),
            parse_mode="Markdown",
        )
    await callback.answer("🏆 Отличная работа!")


@router.callback_query(F.data.startswith("cg_g_milestones_"))
async def goal_milestones(callback: CallbackQuery) -> None:
    """Показать этапы цели."""
    goal_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    async with get_async_session() as session:
        goal = await cs.get_goal(session, goal_id, user_id)
        milestones = await cs.get_milestones(session, goal_id, user_id)
    if not goal:
        await callback.answer("Цель не найдена"); return
    if not milestones:
        await callback.answer(f"У цели «{goal.title}» пока нет этапов.\nДобавь через /coaching")
        return
    done = sum(1 for m in milestones if m.status == "done")
    lines = [f"📋 *Этапы «{goal.title}»* ({done}/{len(milestones)}):"]
    for m in milestones:
        s = "✅" if m.status == "done" else ("⏭️" if m.status == "skipped" else "⬜")
        lines.append(f"{s} {m.title}")
    await callback.message.answer("\n".join(lines), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("cg_g_plan_"))
async def goal_plan(callback: CallbackQuery) -> None:
    """Предложить создать план — переадресуем в коуча."""
    goal_id = int(callback.data.split("_")[-1])
    await callback.message.answer(
        "💬 Напиши мне в чат что-то вроде:\n"
        f"«Разбей цель #{goal_id} на конкретные этапы»\n\n"
        "И я помогу составить план! 🎯",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cg_wr_goal_"))
async def goal_review_start(callback: CallbackQuery) -> None:
    """Выбор типа review для цели."""
    goal_id = int(callback.data.split("_")[-1])
    await callback.message.edit_text(
        "📊 *Выбери тип обзора:*",
        reply_markup=weekly_review_kb(goal_id),
        parse_mode="Markdown",
    )
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# HABIT LIST & ACTIONS
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
    await callback.message.delete()
    for h in habits:
        txt = (f"🔁 *{h.title}*\n"
               f"🔥 Серия: {h.current_streak} дн. | Рекорд: {h.longest_streak}\n"
               + (f"⚡ Триггер: {h.cue}" if h.cue else ""))
        await callback.message.answer(txt, reply_markup=habit_list_item_kb(h.id), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("cg_h_log_"))
async def habit_log(callback: CallbackQuery) -> None:
    """Залогировать выполнение привычки."""
    habit_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    async with get_async_session() as session:
        habit = await cs.increment_habit_streak(session, habit_id, user_id)
        if habit:
            from db.models import HabitLog
            session.add(HabitLog(habit_id=habit_id, user_id=user_id))
        await session.commit()
    if not habit:
        await callback.answer("Привычка не найдена"); return
    # Проверяем новый рекорд
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
        # Ручной ввод числа
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
# FLOW START CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "cg_flow_goal_new")
async def flow_new_goal(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать создание новой цели."""
    await callback.message.delete()
    await start_goal_creation(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "cg_flow_habit_new")
async def flow_new_habit(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать создание новой привычки."""
    await callback.message.delete()
    await start_habit_creation(callback.message, state)
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
    await finish_habit_creation(callback, state)


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
    # Эмулируем пустой текст
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
    # Удаляем черновики если есть
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
# RECOMMENDATIONS & MEMORY
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "cg_recs")
async def show_recommendations(callback: CallbackQuery) -> None:
    """Показать текущие рекомендации коуча."""
    user_id = callback.from_user.id
    async with get_async_session() as session:
        recs = await cs.get_active_recommendations(session, user_id, limit=5)
    if not recs:
        await callback.answer("Рекомендаций пока нет — продолжай в том же духе! 💪")
        return
    lines = ["📌 *Твои рекомендации:*"]
    for r in recs:
        lines.append(f"\n• [{r.rec_type}] {r.title}")
        if r.body:
            lines.append(f"  _{r.body[:80]}_")
    await callback.message.answer("\n".join(lines), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "cg_memory")
async def show_memory(callback: CallbackQuery) -> None:
    """Показать что коуч знает о пользователе + кнопка сброса персонализации."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    user_id = callback.from_user.id
    async with get_async_session() as session:
        memories = await cs.get_memory(session, user_id, top_n=10)
    if not memories:
        await callback.answer("Память пока пуста — начни общаться с коучем!")
        return
    lines = ["🧠 *Что я знаю о тебе:*"]
    for m in memories:
        # Отмечаем явно заданные пользователем настройки
        mark = " _(ты сказал)_" if m.is_explicit else ""
        lines.append(f"• {m.key}: {m.value}{mark}")

    # Клавиатура с кнопкой сброса персонализации
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🗑 Сбросить настройки", callback_data="cg_reset_confirm")
    ]])
    await callback.message.answer("\n".join(lines), parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "cg_reset_confirm")
async def confirm_reset_personalization(callback: CallbackQuery) -> None:
    """Показать подтверждение сброса персонализации."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, сбросить", callback_data="cg_reset_do"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cg_reset_cancel"),
    ]])
    await callback.message.answer(
        "⚠️ Сбросить всё что коуч узнал о тебе?\nЭто удалит память и поведенческие паттерны. Отменить нельзя.",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data == "cg_reset_do")
async def do_reset_personalization(callback: CallbackQuery) -> None:
    """Выполнить сброс персонализации по подтверждению пользователя."""
    user_id = callback.from_user.id
    async with get_async_session() as session:
        await reset_personalization(session, user_id)
        await session.commit()
    await callback.message.answer(
        "✅ Персонализация сброшена. Коуч начнёт узнавать тебя заново.",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_reset_cancel")
async def cancel_reset_personalization(callback: CallbackQuery) -> None:
    """Отмена сброса персонализации."""
    await callback.answer("Отменено — ничего не изменилось.")


@router.message(Command("reset_coach"))
async def cmd_reset_coach(message: Message) -> None:
    """
    Команда /reset_coach — сброс поведенческих паттернов и памяти коуча.
    Выводит запрос подтверждения перед удалением.
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, сбросить", callback_data="cg_reset_do"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cg_reset_cancel"),
    ]])
    await message.answer(
        "⚠️ *Сбросить персонализацию?*\n\n"
        "Коуч забудет всё что узнал о твоих привычках, предпочтениях и паттернах.\n"
        "Профиль и цели останутся. Память и адаптации — удалятся.",
        parse_mode="Markdown",
        reply_markup=kb,
    )



# ══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATION ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("cg_orc_confirm_"))
async def confirm_orchestration(callback: CallbackQuery) -> None:
    """Подтвердить orchestration-действие и выполнить его в соответствующем модуле."""
    from db.models import CoachingOrchestrationAction
    from sqlalchemy import select as sa_select
    try:
        action_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("Некорректный ID действия")
        return

    user_id = callback.from_user.id
    async with get_async_session() as session:
        result = await session.execute(
            sa_select(CoachingOrchestrationAction).where(
                CoachingOrchestrationAction.id == action_id,
                CoachingOrchestrationAction.user_id == user_id,
            )
        )
        action = result.scalar_one_or_none()

        if not action:
            await callback.answer("Действие не найдено")
            return
        if action.status != "pending":
            await callback.answer(f"Действие уже в статусе: {action.status}")
            return

        # Подтверждаем действие и выполняем его
        await cs.confirm_orchestration_action(session, action_id, user_id)
        success, message = await execute_orchestration_action(session, action)
        await session.commit()

    if success:
        await callback.message.answer(message)
    else:
        await callback.message.answer(f"Что-то пошло не так: {message}")
    await callback.answer()


@router.callback_query(F.data.startswith("cg_orc_reject_"))
async def reject_orchestration(callback: CallbackQuery) -> None:
    """Отклонить orchestration-действие."""
    from db.models import CoachingOrchestrationAction
    from sqlalchemy import update as sa_update
    try:
        action_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("Некорректный ID действия")
        return

    user_id = callback.from_user.id
    async with get_async_session() as session:
        await session.execute(
            sa_update(CoachingOrchestrationAction)
            .where(
                CoachingOrchestrationAction.id == action_id,
                CoachingOrchestrationAction.user_id == user_id,
            )
            .values(status="rejected")
        )
        await session.commit()

    await callback.message.answer("Действие отменено — ничего не создано.")
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# КНОПКА «🎯 КОУЧИНГ» ИЗ ГЛАВНОГО МЕНЮ
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "🎯 Коучинг")
async def coaching_button(message: Message, state: FSMContext) -> None:
    """Обработчик кнопки «🎯 Коучинг» из главного ReplyKeyboard-меню."""
    await coaching_main(message, state)


# ══════════════════════════════════════════════════════════════════════════════
# 9.1 — ПОСЛЕ СОЗДАНИЯ ЦЕЛИ
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("cg_g_steps_"))
async def goal_steps(callback: CallbackQuery) -> None:
    """Разбить цель на этапы — направляем в чат-коуча."""
    goal_id = int(callback.data.split("_")[-1])
    await callback.message.answer(
        "💬 Напиши мне:\n"
        f"«Разбей цель #{goal_id} на конкретные этапы»\n\n"
        "Я помогу составить план! 🎯",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cg_g_firstnow_"))
async def goal_first_now(callback: CallbackQuery, state: FSMContext) -> None:
    """Первый шаг прямо сейчас — запускаем check-in по цели."""
    goal_id = int(callback.data.split("_")[-1])
    await start_checkin_flow(callback, state, goal_id=goal_id)


@router.callback_query(F.data.startswith("cg_g_openapp_"))
async def goal_open_app(callback: CallbackQuery) -> None:
    """Открыть цель в Mini App — генерируем magic link."""
    import os
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from api.deps import create_jwt
    user_id = callback.from_user.id
    miniapp_url = os.environ.get("MINIAPP_URL", "https://77-238-235-171.sslip.io")
    magic_token = create_jwt(telegram_id=user_id, expires_in=300, purpose="magic")
    link = f"{miniapp_url}/auth?token={magic_token}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Открыть приложение", url=link)]
    ])
    await callback.message.answer("🌐 Открой цель в приложении:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("cg_g_reflect_"))
async def goal_reflect(callback: CallbackQuery) -> None:
    """Написать рефлексию после достижения или застрявшей цели."""
    await callback.message.answer(
        "📝 *Рефлексия:*\n\n"
        "Напиши в свободной форме:\n"
        "• Что получилось лучше всего?\n"
        "• Что было самым сложным?\n"
        "• Что бы сделал иначе?\n\n"
        "_Я запомню это и учту при следующих целях._",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cg_g_wstatus_"))
async def goal_week_status(callback: CallbackQuery) -> None:
    """Показать клавиатуру статуса цели на неделю (§9.4)."""
    goal_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    async with get_async_session() as session:
        goal = await cs.get_goal(session, goal_id, user_id)
    if not goal:
        await callback.answer("Цель не найдена"); return
    await callback.message.answer(
        f"📊 *{goal.title}*\n\nКак идут дела по этой цели на этой неделе?",
        reply_markup=review_goal_status_kb(goal_id),
        parse_mode="Markdown",
    )
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# 9.2 — ПРИВЫЧКИ: SNOOZE
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("cg_h_snooze_"))
async def habit_snooze(callback: CallbackQuery) -> None:
    """Напомнить о привычке позже (snooze на ~2 часа)."""
    await callback.answer("⏰ Ок! Напомню позже.", show_alert=False)


# ══════════════════════════════════════════════════════════════════════════════
# 9.3 — CHECK-IN FOLLOW-UP ПОСЛЕ ВЫБОРА НАСТРОЕНИЯ
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
# 9.4 — WEEKLY REVIEW: СТАТУС ЦЕЛЕЙ И ДЕЙСТВИЯ ПОСЛЕ
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
        async with get_async_session() as session:
            await cs.update_goal(session, goal_id, user_id, is_frozen=True, frozen_reason="Заморожена по итогам review")
            await session.commit()
        await callback.answer(f"{label} — цель заморожена")
    elif status == "stuck":
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


# ══════════════════════════════════════════════════════════════════════════════
# 9.5 — МОТИВАЦИОННЫЕ КНОПКИ
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "cg_mot_menu")
async def motivational_menu(callback: CallbackQuery) -> None:
    """Открыть мотивационное меню (§9.5)."""
    await callback.message.edit_text(
        "💪 *Мотивация — выбери формат:*",
        reply_markup=motivational_kb(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_mot_inspire")
async def mot_inspire(callback: CallbackQuery) -> None:
    """Подбодрить пользователя."""
    await callback.message.answer(
        "💪 *Ты уже делаешь больше, чем большинство!*\n\n"
        "Каждый маленький шаг — это победа. Не сравнивай себя с другими, "
        "сравнивай с собой вчерашним. Ты уже в пути — это главное! 🔥",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_mot_strict")
async def mot_strict(callback: CallbackQuery) -> None:
    """Жёсткий разбор целей — показываем отстающие."""
    user_id = callback.from_user.id
    async with get_async_session() as session:
        goals = await cs.get_goals(session, user_id, status="active")
    if not goals:
        await callback.answer("Нет активных целей для разбора"); return
    stuck = [g for g in goals if g.progress_pct < 30]
    if not stuck:
        await callback.message.answer(
            "🔥 *Честно?* Всё идёт неплохо!\n\nПрогресс по целям есть. Продолжай в том же темпе.",
            parse_mode="Markdown",
        )
    else:
        lines = ["🔥 *Жёсткий разбор:*\n"]
        for g in stuck[:3]:
            lines.append(f"❗ *{g.title}* — {g.progress_pct}%. Что конкретно сделал за последнюю неделю?")
        lines.append("\n_Напиши в чат что мешает — разберёмся вместе._")
        await callback.message.answer("\n".join(lines), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "cg_mot_nextstep")
async def mot_nextstep(callback: CallbackQuery) -> None:
    """Показать следующий шаг по самой отстающей цели."""
    user_id = callback.from_user.id
    async with get_async_session() as session:
        goals = await cs.get_goals(session, user_id, status="active")
    if not goals:
        await callback.answer("Сначала создай цель!"); return
    # Берём цель с наименьшим прогрессом
    focus = min(goals, key=lambda g: g.progress_pct)
    first_step = focus.first_step or "Определи один конкретный шаг к этой цели"
    await callback.message.answer(
        f"🗺️ *Следующий шаг для «{focus.title}»:*\n\n"
        f"➡️ {first_step}\n\n"
        "_Сделай это прямо сейчас или запланируй на сегодня._",
        reply_markup=goal_card_kb(focus.id, focus.is_frozen),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_mot_simplify")
async def mot_simplify(callback: CallbackQuery) -> None:
    """Упростить маршрут — фокус на одном."""
    await callback.message.answer(
        "🎯 *Упрости маршрут:*\n\n"
        "Выбери ОДНУ главную цель на эту неделю и сосредоточься только на ней.\n\n"
        "Остальное — заморозь. Фокус бьёт распределение!\n\n"
        "_Какая цель для тебя сейчас самая важная?_",
        reply_markup=coaching_main_kb(),
        parse_mode="Markdown",
    )
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# 9.7 — КОНТЕКСТНЫЕ СОСТОЯНИЯ
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "cg_s_reduce_load")
async def state_reduce_load(callback: CallbackQuery) -> None:
    """Снизить нагрузку — список целей для заморозки."""
    user_id = callback.from_user.id
    async with get_async_session() as session:
        goals = await cs.get_goals(session, user_id, status="active")
    if not goals:
        await callback.answer("Активных целей нет"); return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"❄️ {g.title[:30]}", callback_data=f"cg_g_freeze_{g.id}")]
        for g in goals[:5]
    ] + [[InlineKeyboardButton(text="↩️ Назад", callback_data="cg_g_list")]])
    await callback.message.answer(
        "📉 *Снижаем нагрузку*\n\nВыбери что заморозить:",
        reply_markup=kb, parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_s_rebuild_plan")
async def state_rebuild_plan(callback: CallbackQuery) -> None:
    """Пересобрать план — предлагаем описать проблему в чат."""
    await callback.message.answer(
        "🔄 *Пересобрать план:*\n\n"
        "Напиши мне что сейчас перегружает тебя больше всего — "
        "и мы разберём что можно убрать или перенести.",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_s_freeze_extra")
async def state_freeze_extra(callback: CallbackQuery) -> None:
    """Заморозить лишнее — переиспользует логику reduce_load."""
    await state_reduce_load(callback)


@router.callback_query(F.data == "cg_s_restart")
async def state_restart(callback: CallbackQuery) -> None:
    """Начать заново — главное меню."""
    await callback.message.answer(
        "🔄 *Начнём заново!*\n\n"
        "Иногда перезапуск — это не поражение, а мудрость.\n\nС чего начнём?",
        reply_markup=coaching_main_kb(), parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_s_tell_story")
async def state_tell_story(callback: CallbackQuery) -> None:
    """Рассказать что случилось."""
    await callback.message.answer(
        "📝 *Расскажи что случилось:*\n\n"
        "Напиши в свободной форме — я выслушаю и помогу разобраться.",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_s_simple_plan")
async def state_simple_plan(callback: CallbackQuery) -> None:
    """Простой план — один шаг на неделю."""
    await callback.message.answer(
        "🆕 *Простой план:*\n\n"
        "Выбери одну цель и один маленький шаг на эту неделю.\n"
        "Больше ничего — только это.",
        reply_markup=coaching_main_kb(), parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_s_add_challenge")
async def state_add_challenge(callback: CallbackQuery) -> None:
    """Добавить вызов — предлагаем поднять планку."""
    await callback.message.answer(
        "📈 *Добавить вызов:*\n\n"
        "Отлично, ты в потоке! Давай поднимем планку.\n\n"
        "Создай новую цель или усиль существующую:",
        reply_markup=coaching_main_kb(), parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cg_s_achievements")
async def state_achievements(callback: CallbackQuery) -> None:
    """Показать достигнутые цели."""
    user_id = callback.from_user.id
    async with get_async_session() as session:
        achieved = await cs.get_goals(session, user_id, status="achieved")
    if not achieved:
        await callback.answer("Пока нет завершённых целей — всё впереди! 🚀"); return
    lines = ["🏆 *Мои достижения:*\n"]
    for g in achieved[:10]:
        lines.append(f"✅ {g.title}")
    await callback.message.answer("\n".join(lines), parse_mode="Markdown")
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# FSM TEXT MESSAGE HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

# --- Goal Creation ---
@router.message(StateFilter(CoachingGoalCreation.waiting_title), F.text)
async def fsm_goal_title(message: Message, state: FSMContext) -> None:
    await handle_goal_title(message, state)

@router.message(StateFilter(CoachingGoalCreation.waiting_why), F.text)
async def fsm_goal_why(message: Message, state: FSMContext) -> None:
    await handle_goal_why(message, state)

@router.message(StateFilter(CoachingGoalCreation.waiting_first_step), F.text)
async def fsm_goal_first_step(message: Message, state: FSMContext) -> None:
    await handle_goal_first_step(message, state)

@router.message(StateFilter(CoachingGoalCreation.waiting_deadline), F.text)
async def fsm_goal_deadline(message: Message, state: FSMContext) -> None:
    await handle_goal_deadline(message, state)


# --- Habit Creation ---
@router.message(StateFilter(CoachingHabitCreation.waiting_title), F.text)
async def fsm_habit_title(message: Message, state: FSMContext) -> None:
    await handle_habit_title(message, state)

@router.message(StateFilter(CoachingHabitCreation.waiting_cue), F.text)
async def fsm_habit_cue(message: Message, state: FSMContext) -> None:
    await handle_habit_cue(message, state)

@router.message(StateFilter(CoachingHabitCreation.waiting_reward), F.text)
async def fsm_habit_reward(message: Message, state: FSMContext) -> None:
    await handle_habit_reward(message, state)


# --- Check-In ---
@router.message(StateFilter(CoachingCheckIn.waiting_wins), F.text)
async def fsm_checkin_wins(message: Message, state: FSMContext) -> None:
    await handle_checkin_wins(message, state)

@router.message(StateFilter(CoachingCheckIn.waiting_progress), F.text)
async def fsm_checkin_progress(message: Message, state: FSMContext) -> None:
    """Ввод прогресса вручную (число)."""
    try:
        progress = max(0, min(100, int(message.text.strip())))
    except ValueError:
        await message.answer("Введи число от 0 до 100:")
        return
    await handle_checkin_progress(message, state, progress=progress)

@router.message(StateFilter(CoachingCheckIn.waiting_blockers), F.text)
async def fsm_checkin_blockers(message: Message, state: FSMContext) -> None:
    await finish_checkin(message, state)


# --- Weekly Review ---
@router.message(StateFilter(CoachingWeeklyReview.waiting_summary), F.text)
async def fsm_review_summary(message: Message, state: FSMContext) -> None:
    await handle_review_summary(message, state)

@router.message(StateFilter(CoachingWeeklyReview.waiting_highlights), F.text)
async def fsm_review_highlights(message: Message, state: FSMContext) -> None:
    await handle_review_highlights(message, state)

@router.message(StateFilter(CoachingWeeklyReview.waiting_blockers), F.text)
async def fsm_review_blockers(message: Message, state: FSMContext) -> None:
    await handle_review_blockers(message, state)

@router.message(StateFilter(CoachingWeeklyReview.waiting_next_actions), F.text)
async def fsm_review_next_actions(message: Message, state: FSMContext) -> None:
    await finish_weekly_review(message, state)


# ════════════════════════════════════════════════════════════════════════════════
# ПРОАКТИВНЫЕ ДНЕВНЫЕ ЧЕКИНЫ: callback handlers
# Обрабатывают нажатия кнопок из утренних/дневных/вечерних проактивных сообщений
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("cg_daily_morning_e"))
async def daily_morning_energy_cb(callback: CallbackQuery) -> None:
    """
    Обработчик утреннего чекина энергии.
    Формат: cg_daily_morning_e{1-5}.
    Сохраняет energy в time_slot=morning через save_morning_checkin.
    """
    # Извлекаем цифру уровня энергии из конца callback_data
    e_str = callback.data.replace("cg_daily_morning_e", "")
    try:
        energy = int(e_str)
        if energy < 1 or energy > 5:
            raise ValueError
    except ValueError:
        await callback.answer("\u26a0\ufe0f Неверный формат")
        return
    await save_morning_checkin(callback, energy=energy)


@router.callback_query(F.data.startswith("cg_daily_midday_e"))
async def daily_midday_energy_cb(callback: CallbackQuery) -> None:
    """
    Обработчик дневного пульса энергии.
    Формат: cg_daily_midday_e{1-5}.
    Сохраняет energy в time_slot=midday через save_midday_checkin.
    """
    e_str = callback.data.replace("cg_daily_midday_e", "")
    try:
        energy = int(e_str)
        if energy < 1 or energy > 5:
            raise ValueError
    except ValueError:
        await callback.answer("\u26a0\ufe0f Неверный формат")
        return
    await save_midday_checkin(callback, energy=energy)


@router.callback_query(F.data.startswith("cg_daily_evening_m"))
async def daily_evening_mood_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик выбора настроения вечернего чекина.
    Формат: cg_daily_evening_m{1-5}.
    Запускает FSM вечерней рефлексии через start_evening_reflection.
    """
    m_str = callback.data.replace("cg_daily_evening_m", "")
    try:
        mood = int(m_str)
        if mood < 1 or mood > 5:
            raise ValueError
    except ValueError:
        await callback.answer("\u26a0\ufe0f Неверный формат")
        return
    await start_evening_reflection(callback, state, mood=mood)


@router.callback_query(F.data.startswith("cg_daily_evening_day_"))
async def daily_evening_day_result_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик выбора итога дня (quick-кнопки).
    Формат: cg_daily_evening_day_{great|ok|hard|text}.
    При text — ожидаем FSM текстовый ввод (уже в состоянии waiting_day_result).
    """
    result = callback.data.replace("cg_daily_evening_day_", "")
    if result == "text":
        # Пользователь выбрал «напишу сам» — остаёмся в состоянии, ждём текст
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


# -- FSM text handlers для вечерней рефлексии ----------------------------------

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

import json as _json
from datetime import date as _date

from services.voice_checkin_parser import (
    detect_slot, detect_date, parse_checkin_fields,
    format_checkin_card,
)
from bot.keyboards.voice_checkin_kb import voice_checkin_confirm_kb


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

    # Определяем дату
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

    # Очищаем FSM state
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

    # Сохраняем обновлённые данные в FSM
    await state.update_data(fields=_json.dumps(merged, ensure_ascii=False))
    await state.set_state(VoiceCheckinFlow.waiting_confirmation)

    await message.answer(
        card_text,
        parse_mode="Markdown",
        reply_markup=voice_checkin_confirm_kb(slot, check_date_str),
    )
