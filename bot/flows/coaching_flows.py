"""
Coaching Flows — вспомогательные функции для многошаговых диалогов.
Работают напрямую через DB, сохраняют промежуточное в coaching_dialog_drafts.
"""
from __future__ import annotations
import logging
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from db.session import get_async_session
from db import coaching_storage as cs
from bot.states import (
    CoachingGoalCreation, CoachingHabitCreation,
    CoachingCheckIn, CoachingWeeklyReview,
)
from bot.keyboards.coaching_keyboards import (
    goal_card_kb, goal_after_create_kb, habit_daily_kb, skip_cancel_kb, cancel_flow_kb,
    goal_area_kb, habit_area_kb, checkin_progress_kb, checkin_mood_kb,
    checkin_after_mood_kb, review_done_kb,
)
logger = logging.getLogger(__name__)

# ─── GOAL CREATION FLOW ───────────────────────────────────────────────────────

async def start_goal_creation(message: Message, state: FSMContext) -> None:
    """Шаг 0: запускаем flow создания цели — выбор области."""
    await state.set_state(CoachingGoalCreation.waiting_area)
    await state.update_data(goal_draft={})
    async with get_async_session() as session:
        await cs.upsert_draft(session, message.from_user.id, "goal_creation", {}, 0)
        await session.commit()
    await message.answer(
        "🎯 *Создаём новую цель*\n\nШаг 1/5 — В какой области жизни прорыв?\n_Выбери или пропусти:_",
        reply_markup=goal_area_kb(), parse_mode="Markdown",
    )


async def handle_goal_area(cb_or_msg, state: FSMContext, area: str) -> None:
    """Шаг 1: область получена → спрашиваем название цели."""
    labels = {"health": "💚 Здоровье", "finance": "💰 Финансы",
               "career": "💼 Карьера", "personal": "🧘 Личное",
               "relationships": "❤️ Отношения", "skip": ""}
    area_val = "" if area == "skip" else area
    area_label = labels.get(area, "")
    await state.update_data(goal_draft={"area": area_val})
    await state.set_state(CoachingGoalCreation.waiting_title)
    txt = (f"Область: {area_label}\n\n" if area_label else "") + \
          "📝 Шаг 2/5 — Опиши цель конкретно.\nНе «похудеть», а «сбросить 5 кг к маю».\n\n_Введи цель:_"
    if isinstance(cb_or_msg, CallbackQuery):
        await cb_or_msg.message.edit_text(txt, reply_markup=cancel_flow_kb(), parse_mode="Markdown")
        await cb_or_msg.answer()
    else:
        await cb_or_msg.answer(txt, reply_markup=cancel_flow_kb(), parse_mode="Markdown")


async def handle_goal_title(message: Message, state: FSMContext) -> None:
    """Шаг 2: название → спрашиваем «зачем»."""
    title = message.text.strip()
    data = await state.get_data(); draft = data.get("goal_draft", {}); draft["title"] = title
    await state.update_data(goal_draft=draft)
    await state.set_state(CoachingGoalCreation.waiting_why)
    async with get_async_session() as session:
        await cs.upsert_draft(session, message.from_user.id, "goal_creation", draft, 2)
        await session.commit()
    await message.answer(
        f"💡 Цель: *{title}*\n\n🔍 Шаг 3/5 — Зачем тебе это? Что изменится в жизни?\n_Ответь честно или пропусти:_",
        reply_markup=skip_cancel_kb("cg_flow_skip_why"), parse_mode="Markdown",
    )


async def handle_goal_why(message: Message, state: FSMContext) -> None:
    """Шаг 3: мотивация → спрашиваем первый шаг."""
    data = await state.get_data(); draft = data.get("goal_draft", {})
    draft["why_statement"] = message.text.strip()
    await state.update_data(goal_draft=draft)
    await state.set_state(CoachingGoalCreation.waiting_first_step)
    await message.answer(
        "⚡ Шаг 4/5 — Какое *одно конкретное действие* прямо сейчас?\nНе «заниматься спортом», а «найти зал».\n\n_Введи первый шаг или пропусти:_",
        reply_markup=skip_cancel_kb("cg_flow_skip_step"), parse_mode="Markdown",
    )


async def handle_goal_first_step(message: Message, state: FSMContext) -> None:
    """Шаг 4: первый шаг → спрашиваем дедлайн."""
    data = await state.get_data(); draft = data.get("goal_draft", {})
    draft["first_step"] = message.text.strip()
    await state.update_data(goal_draft=draft)
    await state.set_state(CoachingGoalCreation.waiting_deadline)
    await message.answer(
        "🗓 Шаг 5/5 — Есть дедлайн?\n_Формат: 2025-12-31_ или пропусти:",
        reply_markup=skip_cancel_kb("cg_flow_skip_deadline"), parse_mode="Markdown",
    )


async def handle_goal_deadline(msg_or_cb, state: FSMContext, deadline: str = "") -> None:
    """Шаг 5: создаём цель в БД."""
    if isinstance(msg_or_cb, Message):
        user_id = msg_or_cb.from_user.id
        try:
            from datetime import date
            date.fromisoformat(msg_or_cb.text.strip())
            deadline = msg_or_cb.text.strip()
        except Exception:
            deadline = ""
    else:
        user_id = msg_or_cb.from_user.id
    data = await state.get_data(); draft = data.get("goal_draft", {})
    if deadline: draft["target_date"] = deadline
    try:
        async with get_async_session() as session:
            from datetime import date as _date
            goal = await cs.create_goal(
                session, user_id,
                title=draft.get("title", "Моя цель"),
                area=draft.get("area") or None,
                why_statement=draft.get("why_statement") or None,
                first_step=draft.get("first_step") or None,
                target_date=_date.fromisoformat(deadline) if deadline else None,
                priority="medium",
            )
            await cs.delete_draft(session, user_id, "goal_creation")
            await session.commit()
    except Exception as e:
        logger.error("Ошибка создания цели: %s", e)
        await state.clear()
        txt = "❌ Не удалось создать цель. Попробуй ещё раз."
        if isinstance(msg_or_cb, Message): await msg_or_cb.answer(txt)
        else: await msg_or_cb.message.answer(txt); await msg_or_cb.answer()
        return
    await state.clear()
    labels = {"health": "💚 Здоровье", "finance": "💰 Финансы",
              "career": "💼 Карьера", "personal": "🧘 Личное",
              "relationships": "❤️ Отношения"}
    area_s = labels.get(goal.area or "", "") or "—"
    deadline_s = f"\n📅 Дедлайн: {goal.target_date}" if goal.target_date else ""
    txt = (f"✅ *Цель создана!*\n\n🎯 {goal.title}\nОбласть: {area_s}{deadline_s}\n"
           + (f"💡 Зачем: {goal.why_statement}\n" if goal.why_statement else "")
           + (f"⚡ Первый шаг: {goal.first_step}" if goal.first_step else "")
           + "\n\n_Хочешь разбить на конкретные этапы?_")
    # После создания цели показываем кнопки следующих действий (§9.1)
    if isinstance(msg_or_cb, Message):
        await msg_or_cb.answer(txt, reply_markup=goal_after_create_kb(goal.id), parse_mode="Markdown")
    else:
        await msg_or_cb.message.answer(txt, reply_markup=goal_after_create_kb(goal.id), parse_mode="Markdown")
        await msg_or_cb.answer("Цель создана!")


# ─── HABIT CREATION FLOW ─────────────────────────────────────────────────────

async def start_habit_creation(message: Message, state: FSMContext) -> None:
    """Шаг 0: запускаем flow создания привычки."""
    await state.set_state(CoachingHabitCreation.waiting_title)
    await state.update_data(habit_draft={})
    async with get_async_session() as session:
        await cs.upsert_draft(session, message.from_user.id, "habit_creation", {}, 0)
        await session.commit()
    await message.answer(
        "🔁 *Создаём новую привычку*\n\nШаг 1/4 — Как называется?\n"
        "Примеры: «Медитация 10 мин», «Читать 20 страниц», «Стакан воды утром»\n\n_Введи название:_",
        reply_markup=cancel_flow_kb(), parse_mode="Markdown",
    )


async def handle_habit_title(message: Message, state: FSMContext) -> None:
    """Шаг 1: название → выбор области."""
    title = message.text.strip()
    await state.update_data(habit_draft={"title": title})
    await state.set_state(CoachingHabitCreation.waiting_area)
    async with get_async_session() as session:
        await cs.upsert_draft(session, message.from_user.id, "habit_creation", {"title": title}, 1)
        await session.commit()
    await message.answer(
        f"*{title}*\n\nШаг 2/4 — В какой области?\n_Выбери или пропусти:_",
        reply_markup=habit_area_kb(), parse_mode="Markdown",
    )


async def handle_habit_area(callback: CallbackQuery, state: FSMContext, area: str) -> None:
    """Шаг 2: область → спрашиваем триггер."""
    data = await state.get_data(); draft = data.get("habit_draft", {})
    draft["area"] = "" if area == "skip" else area
    await state.update_data(habit_draft=draft)
    await state.set_state(CoachingHabitCreation.waiting_cue)
    await callback.message.edit_text(
        "⚡ Шаг 3/4 — Когда/после чего будешь делать?\n"
        "Триггер помогает не забыть. Напр: «После кофе» | «Перед сном»\n\n_Введи триггер или пропусти:_",
        reply_markup=skip_cancel_kb("cg_flow_skip_cue"), parse_mode="Markdown",
    )
    await callback.answer()


async def handle_habit_cue(message: Message, state: FSMContext) -> None:
    """Шаг 3: триггер → спрашиваем награду."""
    data = await state.get_data(); draft = data.get("habit_draft", {})
    draft["cue"] = message.text.strip()
    await state.update_data(habit_draft=draft)
    await state.set_state(CoachingHabitCreation.waiting_reward)
    await message.answer(
        "🎁 Шаг 4/4 — Что получишь/почувствуешь после?\n"
        "«Заряд бодрости» | «Удовлетворение» | «Чашка кофе»\n\n_Введи награду или пропусти:_",
        reply_markup=skip_cancel_kb("cg_flow_skip_reward"), parse_mode="Markdown",
    )


async def _finish_habit(msg_or_cb, state: FSMContext, reward: str = "") -> None:
    """Создаём привычку в БД."""
    user_id = msg_or_cb.from_user.id
    data = await state.get_data(); draft = data.get("habit_draft", {})
    if reward: draft["reward"] = reward
    try:
        from db.models import Habit
        async with get_async_session() as session:
            habit = Habit(user_id=user_id, title=draft.get("title", "Моя привычка"),
                          area=draft.get("area") or None, cue=draft.get("cue") or None,
                          reward=draft.get("reward") or None, frequency="daily", difficulty="medium")
            session.add(habit)
            await session.flush(); await session.refresh(habit)
            await cs.delete_draft(session, user_id, "habit_creation")
            await session.commit()
    except Exception as e:
        logger.error("Ошибка создания привычки: %s", e)
        await state.clear()
        txt = "❌ Не удалось создать привычку."
        if isinstance(msg_or_cb, Message): await msg_or_cb.answer(txt)
        else: await msg_or_cb.message.answer(txt); await msg_or_cb.answer()
        return
    await state.clear()
    txt = (f"✅ *Привычка создана!*\n\n🔁 {habit.title}\n"
           + (f"⚡ Триггер: {habit.cue}\n" if habit.cue else "")
           + (f"🎁 Награда: {habit.reward}\n" if habit.reward else "")
           + "\n🔥 Начинаем серию! Первый день — сегодня.")
    if isinstance(msg_or_cb, Message):
        await msg_or_cb.answer(txt, reply_markup=habit_daily_kb(habit.id), parse_mode="Markdown")
    else:
        await msg_or_cb.message.answer(txt, reply_markup=habit_daily_kb(habit.id), parse_mode="Markdown")
        await msg_or_cb.answer("Привычка создана!")


async def handle_habit_reward(message: Message, state: FSMContext) -> None:
    await _finish_habit(message, state, reward=message.text.strip())

async def finish_habit_creation(msg_or_cb, state: FSMContext) -> None:
    await _finish_habit(msg_or_cb, state, reward="")


# ─── CHECK-IN FLOW ────────────────────────────────────────────────────────────

async def start_checkin_flow(msg_or_cb, state: FSMContext, goal_id: int = 0) -> None:
    """Шаг 0: запускаем check-in flow."""
    await state.set_state(CoachingCheckIn.waiting_wins)
    await state.update_data(checkin_draft={"goal_id": goal_id})
    if isinstance(msg_or_cb, Message):
        user_id = msg_or_cb.from_user.id; send = msg_or_cb.answer
    else:
        user_id = msg_or_cb.from_user.id; await msg_or_cb.answer()
        send = msg_or_cb.message.answer
    goal_label = ""
    if goal_id > 0:
        async with get_async_session() as session:
            g = await cs.get_goal(session, goal_id, user_id)
            if g: goal_label = f" по цели «{g.title}»"
    await send(
        f"✅ *Check-in{goal_label}*\n\n🏆 Шаг 1/4 — Что удалось?\n_Любая победа считается:_",
        reply_markup=skip_cancel_kb("cg_flow_skip_wins"), parse_mode="Markdown",
    )


async def handle_checkin_wins(message: Message, state: FSMContext) -> None:
    """Шаг 1: победы → запрашиваем прогресс."""
    data = await state.get_data(); draft = data.get("checkin_draft", {})
    draft["wins"] = message.text.strip()
    await state.update_data(checkin_draft=draft)
    await state.set_state(CoachingCheckIn.waiting_progress)
    await message.answer(
        "📊 Шаг 2/4 — Прогресс по цели (0-100%)?\n_Выбери или введи число:_",
        reply_markup=checkin_progress_kb(draft.get("goal_id", 0)), parse_mode="Markdown",
    )


async def handle_checkin_progress(msg_or_cb, state: FSMContext, progress: int) -> None:
    """Шаг 2: прогресс → запрашиваем энергию."""
    data = await state.get_data(); draft = data.get("checkin_draft", {})
    draft["progress_pct"] = progress
    await state.update_data(checkin_draft=draft)
    await state.set_state(CoachingCheckIn.waiting_energy)
    txt = f"⚡ Прогресс: {progress}%\n\nШаг 3/4 — Как твоя энергия?"
    gid = draft.get("goal_id", 0)
    if isinstance(msg_or_cb, Message):
        await msg_or_cb.answer(txt, reply_markup=checkin_mood_kb(gid), parse_mode="Markdown")
    else:
        await msg_or_cb.message.edit_text(txt, reply_markup=checkin_mood_kb(gid), parse_mode="Markdown")
        await msg_or_cb.answer()


async def handle_checkin_energy(callback: CallbackQuery, state: FSMContext, energy: int) -> None:
    """Шаг 3: настроение → показываем follow-up кнопки (§9.3)."""
    data = await state.get_data(); draft = data.get("checkin_draft", {})
    draft["energy_level"] = energy
    await state.update_data(checkin_draft=draft)
    # Не меняем FSM-состояние — ждём выбора через cg_ci_fb_* callbacks
    mood_labels = {1: "💀 Провал", 2: "😔 Тяжело", 3: "😐 Так себе", 4: "👍 Норм", 5: "🔥 Отлично"}
    label = mood_labels.get(energy, str(energy))
    await callback.message.edit_text(
        f"Настроение: {label}\n\n_Что делаем дальше?_",
        reply_markup=checkin_after_mood_kb(), parse_mode="Markdown",
    )
    await callback.answer()


async def finish_checkin(msg_or_cb, state: FSMContext, blockers: str = "") -> None:
    """Финальный шаг check-in — сохраняем."""
    if isinstance(msg_or_cb, Message):
        user_id = msg_or_cb.from_user.id
        if not blockers: blockers = msg_or_cb.text.strip()
    else:
        user_id = msg_or_cb.from_user.id
    data = await state.get_data(); draft = data.get("checkin_draft", {})
    if blockers: draft["blockers"] = blockers
    goal_id = draft.get("goal_id", 0); progress_pct = draft.get("progress_pct", 0)
    try:
        async with get_async_session() as session:
            if goal_id > 0:
                await cs.create_goal_checkin(session, goal_id, user_id,
                    progress_pct=progress_pct, energy_level=draft.get("energy_level", 3),
                    wins=draft.get("wins") or None, blockers=draft.get("blockers") or None)
                await cs.update_goal(session, goal_id, user_id, progress_pct=progress_pct)
            await session.commit()
    except Exception as e:
        logger.error("Ошибка check-in: %s", e)
        await state.clear()
        txt = "❌ Не удалось сохранить check-in."
        if isinstance(msg_or_cb, Message): await msg_or_cb.answer(txt)
        else: await msg_or_cb.message.answer(txt); await msg_or_cb.answer()
        return
    await state.clear()
    emojis = {1: "😴", 2: "😕", 3: "😐", 4: "😊", 5: "🔥"}
    e = draft.get("energy_level", 3)
    txt = (f"✅ *Check-in сохранён!*\n📊 Прогресс: {progress_pct}%\n"
           f"⚡ Энергия: {emojis.get(e, '')} {e}/5"
           + (f"\n🏆 Победы: {draft['wins']}" if draft.get("wins") else "")
           + (f"\n🚧 Блокеры: {draft['blockers']}" if draft.get("blockers") else "")
           + "\n\n💡 Следующий шаг: одно конкретное действие до следующего check-in.")
    kb = goal_card_kb(goal_id) if goal_id > 0 else None
    if isinstance(msg_or_cb, Message):
        await msg_or_cb.answer(txt, reply_markup=kb, parse_mode="Markdown")
    else:
        await msg_or_cb.message.answer(txt, reply_markup=kb, parse_mode="Markdown")
        await msg_or_cb.answer("Сохранено!")


# ─── WEEKLY REVIEW FLOW ───────────────────────────────────────────────────────

async def start_weekly_review(msg_or_cb, state: FSMContext, goal_id: int = 0, quick: bool = True) -> None:
    """Шаг 0: запускаем weekly review flow."""
    await state.set_state(CoachingWeeklyReview.waiting_summary)
    await state.update_data(review_draft={"goal_id": goal_id, "quick": quick})
    if isinstance(msg_or_cb, Message):
        send = msg_or_cb.answer
    else:
        await msg_or_cb.answer(); send = msg_or_cb.message.answer
    prefix = "⚡ Быстрый" if quick else "📊 Полный"
    await send(
        f"📊 *{prefix} обзор недели*\n\nШаг 1 — Как прошла неделя?\n_Опиши в 1-2 предложениях:_",
        reply_markup=cancel_flow_kb(), parse_mode="Markdown",
    )


async def handle_review_summary(message: Message, state: FSMContext) -> None:
    data = await state.get_data(); draft = data.get("review_draft", {})
    draft["summary"] = message.text.strip()
    await state.update_data(review_draft=draft)
    await state.set_state(CoachingWeeklyReview.waiting_highlights)
    await message.answer(
        "🏆 Шаг 2 — Главные достижения?\n_Перечисли через запятую или пропусти:_",
        reply_markup=skip_cancel_kb("cg_flow_skip_hl"), parse_mode="Markdown",
    )


async def handle_review_highlights(message: Message, state: FSMContext) -> None:
    data = await state.get_data(); draft = data.get("review_draft", {})
    draft["highlights"] = message.text.strip()
    await state.update_data(review_draft=draft)
    quick = draft.get("quick", True)
    if quick:
        await state.set_state(CoachingWeeklyReview.waiting_next_actions)
        await message.answer(
            "🚀 Шаг 3 — Топ-3 фокуса на следующую неделю?\n_Через запятую или пропусти:_",
            reply_markup=skip_cancel_kb("cg_flow_skip_na"), parse_mode="Markdown",
        )
    else:
        await state.set_state(CoachingWeeklyReview.waiting_blockers)
        await message.answer(
            "🚧 Шаг 3 — Что мешало?\n_Перечисли через запятую или пропусти:_",
            reply_markup=skip_cancel_kb("cg_flow_skip_bl"), parse_mode="Markdown",
        )


async def handle_review_blockers(message: Message, state: FSMContext) -> None:
    data = await state.get_data(); draft = data.get("review_draft", {})
    draft["blockers"] = message.text.strip()
    await state.update_data(review_draft=draft)
    await state.set_state(CoachingWeeklyReview.waiting_next_actions)
    await message.answer(
        "🚀 Шаг 4 — Топ-3 фокуса на следующую неделю?\n_Через запятую или пропусти:_",
        reply_markup=skip_cancel_kb("cg_flow_skip_na"), parse_mode="Markdown",
    )


async def finish_weekly_review(msg_or_cb, state: FSMContext, next_actions: str = "") -> None:
    if isinstance(msg_or_cb, Message):
        user_id = msg_or_cb.from_user.id
        if not next_actions: next_actions = msg_or_cb.text.strip()
    else:
        user_id = msg_or_cb.from_user.id
    data = await state.get_data(); draft = data.get("review_draft", {})
    if next_actions: draft["next_actions"] = next_actions
    goal_id = draft.get("goal_id", 0)
    try:
        async with get_async_session() as session:
            if goal_id > 0:
                await cs.create_goal_review(session, goal_id, user_id,
                    review_type="weekly", summary=draft.get("summary", ""),
                    highlights=[h.strip() for h in draft.get("highlights", "").split(",") if h.strip()] or None,
                    blockers=[b.strip() for b in draft.get("blockers", "").split(",") if b.strip()] or None,
                    next_actions=[a.strip() for a in draft.get("next_actions", "").split(",") if a.strip()] or None)
            await session.commit()
    except Exception as e:
        logger.error("Ошибка weekly review: %s", e)
        await state.clear()
        txt = "❌ Не удалось сохранить обзор."
        if isinstance(msg_or_cb, Message): await msg_or_cb.answer(txt)
        else: await msg_or_cb.message.answer(txt); await msg_or_cb.answer()
        return
    await state.clear()
    na = draft.get("next_actions", "")
    next_txt = ""
    if na:
        acts = [a.strip() for a in na.split(",") if a.strip()]
        next_txt = "\n\n🚀 *Фокус на неделю:*\n" + "\n".join(f"• {a}" for a in acts[:3])
    txt = (f"📊 *Обзор недели сохранён!*\n\n💬 {draft.get('summary', '')[:150]}"
           + next_txt + "\n\n_Молодец! Регулярные обзоры — это и есть система._")
    if isinstance(msg_or_cb, Message):
        await msg_or_cb.answer(txt, reply_markup=review_done_kb(goal_id), parse_mode="Markdown")
    else:
        await msg_or_cb.message.answer(txt, reply_markup=review_done_kb(goal_id), parse_mode="Markdown")
        await msg_or_cb.answer("Сохранено!")


# ════════════════════════════════════════════════════════════════════════════════
# ПРОАКТИВНЫЕ ДНЕВНЫЕ ЧЕКИНЫ: утро / день / вечер
# ════════════════════════════════════════════════════════════════════════════════

from datetime import date as _date
from bot.states import DailyEveningReflection
from bot.keyboards.coaching_keyboards import (
    evening_day_result_kb, skip_step_kb,
)


async def save_morning_checkin(
    callback,
    energy: int,
) -> None:
    """
    Сохраняет утренний чекин (time_slot=morning) после выбора уровня энергии.
    Вызывается из coaching_handler при callback cg_daily_morning_e{1-5}.
    """
    user_id = callback.from_user.id
    today = _date.today().isoformat()
    try:
        async with get_async_session() as session:
            await cs.create_goal_checkin(
                session,
                goal_id=None,
                user_id=user_id,
                progress_pct=0,
                energy_level=energy,
                notes=None,
                blockers=None,
                wins=None,
                mood=None,
                time_slot="morning",
                check_date=today,
            )
            await session.commit()
    except Exception as e:
        logger.error("Ошибка сохранения утреннего чекина: %s", e)
        await callback.message.answer("\u274c Не удалось сохранить. Попробуй позже.")
        await callback.answer()
        return

    # Эмодзи отражает уровень энергии 1-5
    energy_emojis = {1: "\U0001f634", 2: "\U0001f615", 3: "\U0001f610", 4: "\U0001f642", 5: "\U0001f525"}
    emoji = energy_emojis.get(energy, "")
    await callback.message.edit_text(
        "\u2705 *Утренний чекин сохранён!*\n\n"
        f"Энергия: {emoji} {energy}/5\n\n"
        "_Хорошего продуктивного дня! Ты справишься \U0001f4aa_",
        parse_mode="Markdown",
    )
    await callback.answer("\u2705 Сохранено!")


async def save_midday_checkin(
    callback,
    energy: int,
) -> None:
    """
    Сохраняет дневной пульс (time_slot=midday) после выбора уровня энергии.
    Вызывается из coaching_handler при callback cg_daily_midday_e{1-5}.
    """
    user_id = callback.from_user.id
    today = _date.today().isoformat()
    try:
        async with get_async_session() as session:
            await cs.create_goal_checkin(
                session,
                goal_id=None,
                user_id=user_id,
                progress_pct=0,
                energy_level=energy,
                notes=None,
                blockers=None,
                wins=None,
                mood=None,
                time_slot="midday",
                check_date=today,
            )
            await session.commit()
    except Exception as e:
        logger.error("Ошибка сохранения дневного пульса: %s", e)
        await callback.message.answer("\u274c Не удалось сохранить. Попробуй позже.")
        await callback.answer()
        return

    energy_emojis = {1: "\U0001f634", 2: "\U0001f615", 3: "\U0001f610", 4: "\U0001f642", 5: "\U0001f525"}
    emoji = energy_emojis.get(energy, "")
    await callback.message.edit_text(
        "\u2705 *Дневной пульс сохранён!*\n\n"
        f"Энергия: {emoji} {energy}/5\n\n"
        "_Ещё чуть-чуть — и вечер! Держись \U0001f4aa_",
        parse_mode="Markdown",
    )
    await callback.answer("\u2705 Сохранено!")


async def start_evening_reflection(
    callback,
    state: FSMContext,
    mood: int,
) -> None:
    """
    Шаг 0 вечерней рефлексии: настроение выбрано (cg_daily_evening_m{1-5}).
    Сохраняем mood в FSM data, переходим к шагу 1 — итог дня.
    """
    await state.update_data(mood=mood)
    await state.set_state(DailyEveningReflection.waiting_day_result)

    mood_emojis = {1: "\U0001f622", 2: "\U0001f615", 3: "\U0001f610", 4: "\U0001f642", 5: "\U0001f604"}
    emoji = mood_emojis.get(mood, "")
    await callback.message.edit_text(
        "\U0001f319 *Вечерняя рефлексия*\n\n"
        f"Настроение: {emoji} {mood}/5\n\n"
        "*Как прошёл сегодняшний день?*\n"
        "_Выбери или напиши сам:_",
        parse_mode="Markdown",
        reply_markup=evening_day_result_kb(),
    )
    await callback.answer()


async def handle_evening_day_result(
    callback_or_msg,
    state: FSMContext,
    day_result: str,
) -> None:
    """
    Шаг 1: получен итог дня (quick-кнопка или текст).
    Сохраняем day_result → переходим к шагу 2: как прошёл день подробнее.
    """
    await state.update_data(day_result=day_result)
    await state.set_state(DailyEveningReflection.waiting_notes)

    result_labels = {
        "great": "\U0001f525 Продуктивный",
        "ok": "\U0001f44d Нормально",
        "hard": "\U0001f614 Тяжёлый",
    }
    result_text = result_labels.get(day_result, f"\U0001f4dd {day_result[:50]}")

    text = (
        f"День: {result_text}\n\n"
        "*Как прошёл день подробнее?* Что важного произошло?\n"
        "_Напиши пару строк или пропусти:_"
    )
    kb = skip_step_kb("cg_daily_evening_skip_notes")

    if hasattr(callback_or_msg, 'message'):
        # CallbackQuery — редактируем сообщение
        await callback_or_msg.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
        await callback_or_msg.answer()
    else:
        # Message — текстовый ввод пользователя
        await callback_or_msg.answer(text, parse_mode="Markdown", reply_markup=kb)


async def handle_evening_notes(msg_or_cb, state: FSMContext, notes: str) -> None:
    """
    Шаг 2: получены заметки о дне (или пропуск).
    Переходим к шагу 3: что мешало.
    """
    await state.update_data(notes=notes)
    await state.set_state(DailyEveningReflection.waiting_blockers)

    text = (
        "*Что мешало сегодня?* Блокеры, трудности, отвлечения...\n"
        "_Напиши или пропусти:_"
    )
    kb = skip_step_kb("cg_daily_evening_skip_blockers")

    if hasattr(msg_or_cb, 'message'):
        await msg_or_cb.message.answer(text, parse_mode="Markdown", reply_markup=kb)
        await msg_or_cb.answer()
    else:
        await msg_or_cb.answer(text, parse_mode="Markdown", reply_markup=kb)


async def handle_evening_blockers(msg_or_cb, state: FSMContext, blockers: str) -> None:
    """
    Шаг 3: получены блокеры (или пропуск).
    Переходим к шагу 4: победы дня.
    """
    await state.update_data(blockers=blockers)
    await state.set_state(DailyEveningReflection.waiting_wins)

    text = (
        "*Победы дня!* \U0001f3c6 Что удалось, пусть даже маленькое?\n"
        "_Напиши или пропусти:_"
    )
    kb = skip_step_kb("cg_daily_evening_skip_wins")

    if hasattr(msg_or_cb, 'message'):
        await msg_or_cb.message.answer(text, parse_mode="Markdown", reply_markup=kb)
        await msg_or_cb.answer()
    else:
        await msg_or_cb.answer(text, parse_mode="Markdown", reply_markup=kb)


async def finish_evening_reflection(msg_or_cb, state: FSMContext, wins: str) -> None:
    """
    Шаг 4 (финал): сохраняем весь вечерний чекин в БД.
    Собирает данные из FSM data: mood, day_result, notes, blockers + wins из аргумента.
    """
    data = await state.get_data()
    await state.clear()

    # Определяем user_id из обоих типов входящего объекта
    user_id = msg_or_cb.from_user.id
    today = _date.today().isoformat()
    mood = data.get("mood", 3)
    day_result = data.get("day_result", "")
    notes = data.get("notes") or None
    blockers = data.get("blockers") or None

    # Объединяем итог дня + заметки в поле notes
    full_notes_parts = [p for p in [day_result, notes] if p]
    full_notes = "\n".join(full_notes_parts) if full_notes_parts else None

    try:
        async with get_async_session() as session:
            await cs.create_goal_checkin(
                session,
                goal_id=None,
                user_id=user_id,
                progress_pct=0,
                energy_level=None,
                notes=full_notes,
                blockers=blockers,
                wins=wins if wins else None,
                mood=str(mood),
                time_slot="evening",
                check_date=today,
            )
            await session.commit()
    except Exception as e:
        logger.error("Ошибка сохранения вечернего чекина: %s", e)
        text = "\u274c Не удалось сохранить рефлексию. Попробуй позже."
        if hasattr(msg_or_cb, 'message'):
            await msg_or_cb.message.answer(text)
        else:
            await msg_or_cb.answer(text)
        return

    # Формируем итоговое сообщение со summary рефлексии
    mood_emojis = {1: "\U0001f622", 2: "\U0001f615", 3: "\U0001f610", 4: "\U0001f642", 5: "\U0001f604"}
    mood_emoji = mood_emojis.get(mood, "")
    result_labels = {"great": "\U0001f525 Продуктивный", "ok": "\U0001f44d Нормально", "hard": "\U0001f614 Тяжёлый"}

    summary_parts = [
        "\u2705 *Вечерняя рефлексия сохранена!*\n",
        f"Настроение: {mood_emoji} {mood}/5",
    ]
    if day_result:
        summary_parts.append(f"День: {result_labels.get(day_result, day_result)}")
    if wins:
        summary_parts.append(f"\n\U0001f3c6 *Победы:* {wins[:100]}")
    if blockers:
        summary_parts.append(f"\u26a0\ufe0f *Что мешало:* {blockers[:100]}")
    summary_parts.append("\n_Отличная рефлексия! До завтра \U0001f319_")

    summary = "\n".join(summary_parts)

    if hasattr(msg_or_cb, 'message'):
        await msg_or_cb.message.answer(summary, parse_mode="Markdown")
        await msg_or_cb.answer("\u2705 Сохранено!")
    else:
        await msg_or_cb.answer(summary, parse_mode="Markdown")
