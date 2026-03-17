"""
Bot coaching — главное меню коуча и онбординг.

Регистрирует:
  /coaching, «🎯 Коучинг»     — главное меню
  cg_ob_*                     — onboarding callbacks (13 штук)
"""
from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.keyboards.coaching_keyboards import (
    coaching_main_kb,
    onboarding_kb, onboarding_done_kb,
    onboarding_profile_intro_kb, onboarding_focus_area_kb, onboarding_tone_kb,
    onboarding_checkin_time_kb, onboarding_first_action_kb,
)
from bot.flows.coaching_flows import start_goal_creation, start_habit_creation
from db.session import get_async_session
from db import coaching_storage as cs

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


@router.message(F.text == "🎯 Коучинг")
async def coaching_button(message: Message, state: FSMContext) -> None:
    """Обработчик кнопки «🎯 Коучинг» из главного ReplyKeyboard-меню."""
    await coaching_main(message, state)


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
    # Добавляем или убираем область из выбранных
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
