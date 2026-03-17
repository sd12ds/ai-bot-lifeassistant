"""
Bot coaching — callbacks для целей (Goals).

Регистрирует:
  cg_g_list                   — список целей
  cg_g_*                      — действия с целями (checkin, progress, freeze, resume, restart,
                                done, milestones, plan, review)
  cg_g_steps/firstnow/openapp/reflect/wstatus — post-create actions
  cg_flow_goal_new            — начало создания новой цели
"""
from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.keyboards.coaching_keyboards import (
    coaching_main_kb,
    goal_card_kb, goal_achieved_kb, goal_stuck_kb,
    review_goal_status_kb, weekly_review_kb,
)
from bot.flows.coaching_flows import start_goal_creation, start_checkin_flow
from db.session import get_async_session
from db import coaching_storage as cs

logger = logging.getLogger(__name__)
router = Router()


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
    # Отправляем по одной карточке на каждую цель
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
        # Статус этапа: done / skipped / pending
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
# FLOW STARTS
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "cg_flow_goal_new")
async def flow_new_goal(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать создание новой цели."""
    await callback.message.delete()
    await start_goal_creation(callback.message, state)
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# POST-CREATE ACTIONS (после создания цели)
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
    # JWT на 5 минут с purpose=magic для одноразового входа
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
