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
)
from bot.keyboards.coaching_keyboards import (
    coaching_main_kb, goal_card_kb, goal_list_item_kb,
    habit_list_item_kb, habit_daily_kb, habit_missed_kb,
    goal_stuck_kb, goal_achieved_kb, weekly_review_kb,
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
        await callback.message.edit_text(
            f"🏆 *ЦЕЛЬ ДОСТИГНУТА!*\n\n🎉 «{goal.title}»\n\nПоздравляю! Это большая победа! 💪\n\n_Что дальше?_",
            reply_markup=goal_achieved_kb(),
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
