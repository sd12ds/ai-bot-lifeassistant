"""
Bot coaching — проактивные callbacks: рекомендации, память, сброс,
orchestration-действия, мотивация, контекстные состояния.

Регистрирует:
  cg_recs, cg_memory          — рекомендации и память
  cg_reset_confirm/do/cancel  — подтверждение сброса персонализации
  /reset_coach                — команда сброса
  cg_orc_confirm_*, cg_orc_reject_* — orchestration actions
  cg_mot_*                    — мотивационные кнопки
  cg_s_*                      — контекстные состояния (overload/recovery/momentum)
"""
from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.keyboards.coaching_keyboards import (
    coaching_main_kb,
    goal_card_kb,
    motivational_kb, momentum_kb, overload_kb,
)
from db.session import get_async_session
from db import coaching_storage as cs
from services.coaching_personalization import reset_personalization
from services.coaching_cross_module import execute_orchestration_action

logger = logging.getLogger(__name__)
router = Router()


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

    # Кнопка сброса персонализации
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
# МОТИВАЦИОННЫЕ КНОПКИ
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
    # Фильтруем застрявшие цели (прогресс < 30%)
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
    # Берём цель с наименьшим прогрессом — на неё и фокусируемся
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
# КОНТЕКСТНЫЕ СОСТОЯНИЯ (cg_s_*)
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
    # Строим список кнопок для заморозки каждой цели
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
