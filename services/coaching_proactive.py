"""
CoachingProactive — движок proactive-сообщений для coaching-модуля.

Реализует §5 (§5.1-§5.5), §18, §20 архитектурного документа.

Основные функции:
  evaluate_triggers(session, user_id, snapshot)  — 17 триггеров + 4 multi-signal
  evaluate_rituals(session, user_id, profile)     — ежедневные/еженедельные/месячные ритуалы
  check_quiet_hours(profile)                      — тихие часы 23:00-08:00
  select_top_nudge(candidates)                    — выбор max 1 HIGH + 1 MEDIUM
  build_nudge_message(nudge_type, context, state) — формат §5.4
  run_proactive_for_user(session, bot, user_id)   — полный pipeline для одного пользователя
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

import db.coaching_storage as cs
from services.coaching_engine import (
    compute_user_state,
    compute_risk_scores,
    update_daily_snapshot,
)
from bot.keyboards.coaching_keyboards import (
    goal_card_kb, habit_daily_kb, habit_missed_kb,
    weekly_review_kb, recovery_kb, momentum_kb, overload_kb,
    checkin_mood_kb, onboarding_kb,
)

logger = logging.getLogger(__name__)

# ─── Константы приоритетов ────────────────────────────────────────────────────
PRIORITY_CRITICAL = 1
PRIORITY_HIGH     = 2
PRIORITY_MEDIUM   = 3
PRIORITY_LOW      = 4

# Временная зона по умолчанию (МСК)
DEFAULT_TZ = ZoneInfo("Europe/Moscow")


# ─── DTO для кандидата на отправку ───────────────────────────────────────────
@dataclass
class NudgeCandidate:
    """Кандидат на proactive-сообщение."""
    nudge_type: str                     # идентификатор типа
    priority: int                       # 1=CRITICAL, 2=HIGH, 3=MEDIUM, 4=LOW
    text: str                           # готовый текст сообщения
    keyboard: Any = None                # InlineKeyboardMarkup или None
    context: dict = field(default_factory=dict)  # вспомогательные данные


# ════════════════════════════════════════════════════════════════════════════════
# ТИХИЕ ЧАСЫ
# ════════════════════════════════════════════════════════════════════════════════

def check_quiet_hours(profile=None) -> bool:
    """
    Проверяет, находимся ли мы в тихих часах (23:00–08:00 МСК).
    Возвращает True если сейчас тихие часы (отправку блокировать).
    """
    now_msk = datetime.now(DEFAULT_TZ)
    hour = now_msk.hour
    # Тихие часы: 23, 0, 1, 2, 3, 4, 5, 6, 7
    return hour >= 23 or hour < 8


# ════════════════════════════════════════════════════════════════════════════════
# 17 ТРИГГЕРОВ
# ════════════════════════════════════════════════════════════════════════════════

async def evaluate_triggers(
    session: AsyncSession,
    user_id: int,
    snapshot,        # CoachingContextSnapshot
    risks: dict,
    state: str,      # "momentum" | "stable" | "overload" | "recovery" | "risk"
) -> list[NudgeCandidate]:
    """
    Оценивает все 17 триггеров по приоритету.

    Возвращает список NudgeCandidate, отсортированный по priority asc.
    """
    candidates: list[NudgeCandidate] = []
    now = datetime.utcnow()

    goals = await cs.get_goals(session, user_id, status="active")
    habits = await cs.get_habits(session, user_id, is_active=True)
    at_risk_habits = await cs.get_habits_at_risk(session, user_id, days_no_log=3)
    stuck_goals = await cs.get_stuck_goals(session, user_id, days_no_progress=7)
    recent_checkins = await cs.get_recent_goal_checkins(session, user_id, limit=1)

    # Вычисляем дни без check-in
    days_no_checkin = 999
    if recent_checkins:
        last_ci = recent_checkins[0].created_at
        days_no_checkin = (now - last_ci).days

    # Дни без активности (сессии)
    recent_sessions = await cs.get_recent_sessions(session, user_id, limit=1)
    days_no_activity = 999
    if recent_sessions:
        days_no_activity = (now - recent_sessions[0].created_at).days

    tasks_overdue = snapshot.tasks_overdue if snapshot else 0
    habits_done_today = snapshot.habits_done_today if snapshot else 0
    streak_at_risk = snapshot.streak_at_risk if snapshot else False

    # ── CRITICAL триггеры ────────────────────────────────────────────────────

    # C1: no_checkin_3days — 3+ дня без check-in
    if days_no_checkin >= 3:
        first_goal = goals[0] if goals else None
        candidates.append(NudgeCandidate(
            nudge_type="no_checkin_3days",
            priority=PRIORITY_CRITICAL,
            text=(
                f"👋 Ты не делал check-in уже *{days_no_checkin} дня(-ей)*.\n\n"
                "Как дела с целями? Даже 30 секунд помогут мне понять, как тебе помочь.\n\n"
                "_Как ты сейчас?_"
            ),
            keyboard=checkin_mood_kb(first_goal.id if first_goal else 0),
            context={"days": days_no_checkin},
        ))

    # C2: goal_achieved — есть достигнутые цели (не зафиксированные)
    achieved_goals = await cs.get_goals(session, user_id, status="achieved")
    if achieved_goals:
        g = achieved_goals[0]
        candidates.append(NudgeCandidate(
            nudge_type="goal_achieved",
            priority=PRIORITY_CRITICAL,
            text=(
                f"🏆 *Поздравляю!* Кажется, ты достиг цели «{g.title}»!\n\n"
                "Зафиксируем победу? Это важно для твоей истории прогресса.\n\n"
                "_Подтверди достижение:_"
            ),
            keyboard=goal_card_kb(g.id, is_frozen=False),
            context={"goal_id": g.id},
        ))

    # C3: reactivation — 5+ дней без активности
    if days_no_activity >= 5 and not (days_no_checkin >= 3):  # не дублируем
        candidates.append(NudgeCandidate(
            nudge_type="reactivation",
            priority=PRIORITY_CRITICAL,
            text=(
                f"😌 Привет! Я соскучился. Тебя не было {days_no_activity} дней.\n\n"
                "Не буду давить — просто хочу спросить: всё ок?\n\n"
                "Один маленький шаг — и мы снова в ритме 💪",
            ),
            keyboard=recovery_kb(),
            context={"days": days_no_activity},
        ))

    # ── HIGH триггеры ────────────────────────────────────────────────────────

    # H1: goal_no_progress — активная цель без прогресса >7 дней
    if stuck_goals:
        g = stuck_goals[0]
        candidates.append(NudgeCandidate(
            nudge_type="goal_no_progress",
            priority=PRIORITY_HIGH,
            text=(
                f"🎯 Цель «*{g.title}*» буксует уже несколько дней.\n\n"
                "Что мешает? Иногда маленький шаг разблокирует всё остальное.\n\n"
                "_Что мешает прямо сейчас?_"
            ),
            keyboard=goal_card_kb(g.id, is_frozen=g.is_frozen),
            context={"goal_id": g.id},
        ))

    # H2: habit_dying — привычка в зоне риска (3+ дня без лога)
    if at_risk_habits:
        h = at_risk_habits[0]
        days_since = (now - h.last_logged_at).days if h.last_logged_at else 3
        candidates.append(NudgeCandidate(
            nudge_type="habit_dying",
            priority=PRIORITY_HIGH,
            text=(
                f"⚠️ Привычка «*{h.title}*» под угрозой — {days_since} дн. без выполнения.\n\n"
                "Серия оборвётся... Успеешь сделать сегодня?\n\n"
                "_Выполнить или отметить пропуск:_"
            ),
            keyboard=habit_missed_kb(h.id),
            context={"habit_id": h.id, "days": days_since},
        ))

    # H3: goal_no_first_step — цель без первого шага
    for g in goals:
        if not g.first_step and not g.is_frozen:
            candidates.append(NudgeCandidate(
                nudge_type="goal_no_first_step",
                priority=PRIORITY_HIGH,
                text=(
                    f"⚡ У цели «*{g.title}*» нет первого шага.\n\n"
                    "Цель без первого шага — просто мечта. Что сделаешь *сегодня*?\n\n"
                    "_Напиши первый конкретный шаг:_"
                ),
                keyboard=goal_card_kb(g.id, is_frozen=False),
                context={"goal_id": g.id},
            ))
            break  # только одна цель за раз

    # H4: goal_deadline_near — дедлайн через <14 дней
    for g in goals:
        if g.target_date and not g.is_frozen:
            days_left = (g.target_date - now.date()).days
            if 0 < days_left <= 14:
                candidates.append(NudgeCandidate(
                    nudge_type="goal_deadline_near",
                    priority=PRIORITY_HIGH,
                    text=(
                        f"⏰ Дедлайн цели «*{g.title}*» — через *{days_left} дн.*\n\n"
                        f"Текущий прогресс: {g.progress_pct}%\n\n"
                        "_Что сделаешь сегодня?_"
                    ),
                    keyboard=goal_card_kb(g.id, is_frozen=False),
                    context={"goal_id": g.id, "days_left": days_left},
                ))
                break

    # H5: discipline_drop — резкое падение completion rate
    if risks.get("dropout", 0) >= 0.6:
        candidates.append(NudgeCandidate(
            nudge_type="discipline_drop",
            priority=PRIORITY_HIGH,
            text=(
                "📉 Вижу снижение дисциплины за последнюю неделю.\n\n"
                "Это нормально — бывает у всех. Давай разберёмся что мешает?\n\n"
                "_Как ты сейчас?_"
            ),
            keyboard=recovery_kb(),
            context={"dropout_risk": risks.get("dropout", 0)},
        ))

    # ── MEDIUM триггеры ──────────────────────────────────────────────────────

    # M1: goal_no_milestones — цель без этапов
    for g in goals:
        if not g.is_frozen and g.progress_pct < 10:
            milestones = await cs.get_milestones(session, g.id, user_id)
            if not milestones:
                candidates.append(NudgeCandidate(
                    nudge_type="goal_no_milestones",
                    priority=PRIORITY_MEDIUM,
                    text=(
                        f"📋 Цель «*{g.title}*» без этапов — сложно отслеживать прогресс.\n\n"
                        "Разбей её на 3-5 конкретных шага — и путь станет яснее.\n\n"
                        "_Попросить AI разбить на этапы?_"
                    ),
                    keyboard=goal_card_kb(g.id, is_frozen=False),
                    context={"goal_id": g.id},
                ))
                break

    # M2: overdue_tasks_spike — >5 просроченных задач
    if tasks_overdue > 5:
        candidates.append(NudgeCandidate(
            nudge_type="overdue_tasks_spike",
            priority=PRIORITY_MEDIUM,
            text=(
                f"📋 У тебя *{tasks_overdue} просроченных задач*.\n\n"
                "Это создаёт фоновое давление и снижает фокус на целях.\n\n"
                "_Может, разгрузим список?_"
            ),
            keyboard=overload_kb(),
            context={"overdue": tasks_overdue},
        ))

    # M3: new_week_no_plan — понедельник, нет обзора
    now_msk = datetime.now(DEFAULT_TZ)
    if now_msk.weekday() == 0 and now_msk.hour >= 8:  # понедельник
        sessions_this_week = await cs.count_sessions_this_week(session, user_id)
        if sessions_this_week == 0:
            candidates.append(NudgeCandidate(
                nudge_type="new_week_no_plan",
                priority=PRIORITY_MEDIUM,
                text=(
                    "🌅 *Начало недели!*\n\n"
                    "У тебя есть минута расставить приоритеты на 7 дней?\n\n"
                    "_3 фокуса недели → ясность и контроль_"
                ),
                keyboard=weekly_review_kb(),
                context={},
            ))

    # M4: sunday_no_review — воскресенье, нет weekly review
    if now_msk.weekday() == 6 and now_msk.hour >= 18:  # воскресенье вечер
        latest_review = await cs.get_latest_review(session, user_id)
        if not latest_review or (now - latest_review.created_at).days >= 6:
            candidates.append(NudgeCandidate(
                nudge_type="sunday_no_review",
                priority=PRIORITY_MEDIUM,
                text=(
                    "📊 *Неделя позади!*\n\n"
                    "5 минут рефлексии сейчас сэкономят 5 часов разброса на следующей неделе.\n\n"
                    "_Сделаем быстрый обзор?_"
                ),
                keyboard=weekly_review_kb(),
                context={},
            ))

    # M5: habit_perfect_week — идеальная неделя привычек!
    if habits and habits_done_today >= len(habits) and len(habits) > 0:
        # Проверяем что все привычки выполнены все 7 дней
        has_perfect = all(h.current_streak >= 7 for h in habits)
        if has_perfect:
            candidates.append(NudgeCandidate(
                nudge_type="habit_perfect_week",
                priority=PRIORITY_MEDIUM,
                text=(
                    "🔥 *Невероятно!* Идеальная неделя по привычкам!\n\n"
                    f"{len(habits)} из {len(habits)} привычек — 7 дней подряд!\n\n"
                    "Хочешь усилить одну из них? 💪"
                ),
                keyboard=momentum_kb(),
                context={},
            ))

    # M6: goal_conflict — >5 активных целей
    if len(goals) > 5:
        candidates.append(NudgeCandidate(
            nudge_type="goal_conflict",
            priority=PRIORITY_MEDIUM,
            text=(
                f"⚖️ У тебя *{len(goals)} активных целей* — это много для параллельной работы.\n\n"
                "Исследования показывают: >3 цели снижают completion rate.\n\n"
                "_Может, заморозить несколько?_"
            ),
            keyboard=overload_kb(),
            context={"goals_count": len(goals)},
        ))

    # ── LOW триггеры ─────────────────────────────────────────────────────────

    # L1: calendar_overload
    if snapshot and snapshot.calendar_events_today > 8:
        candidates.append(NudgeCandidate(
            nudge_type="calendar_overload",
            priority=PRIORITY_LOW,
            text=(
                f"📅 Сегодня у тебя *{snapshot.calendar_events_today} событий* в календаре.\n\n"
                "При таком загрузе сложно думать о долгосрочных целях.\n\n"
                "_Что можно перенести?_"
            ),
            keyboard=overload_kb(),
            context={},
        ))

    # L2: no_fitness_7days
    if snapshot and getattr(snapshot, 'no_fitness_days', 0) >= 7:
        candidates.append(NudgeCandidate(
            nudge_type="no_fitness_7days",
            priority=PRIORITY_LOW,
            text=(
                "🏃 *7 дней без тренировок.*\n\n"
                "Физическая активность напрямую влияет на energy level и продуктивность.\n\n"
                "_Даже 15 минут — это уже движение вперёд!_"
            ),
            keyboard=recovery_kb(),
            context={},
        ))

    # L3: nutrition_unstable
    if snapshot and getattr(snapshot, 'nutrition_streak', 99) < 3:
        candidates.append(NudgeCandidate(
            nudge_type="nutrition_unstable",
            priority=PRIORITY_LOW,
            text=(
                "🥗 Ты не отслеживал питание последние дни.\n\n"
                "Это ок! Просто напоминаю — данные помогают мне давать более точные советы.\n\n"
                "_Залогировать сегодняшний приём пищи?_"
            ),
            keyboard=recovery_kb(),
            context={},
        ))

    return sorted(candidates, key=lambda c: c.priority)


# ════════════════════════════════════════════════════════════════════════════════
# 4 MULTI-SIGNAL ТРИГГЕРА
# ════════════════════════════════════════════════════════════════════════════════

async def evaluate_multi_signal_triggers(
    session: AsyncSession,
    user_id: int,
    snapshot,
    risks: dict,
    state: str,
) -> list[NudgeCandidate]:
    """
    Мульти-сигнальные триггеры §18.1 — срабатывают только при совпадении
    нескольких условий одновременно.
    """
    candidates: list[NudgeCandidate] = []
    now = datetime.utcnow()

    goals = await cs.get_goals(session, user_id, status="active")
    habits = await cs.get_habits(session, user_id, is_active=True)
    tasks_overdue = snapshot.tasks_overdue if snapshot else 0
    calendar_events = snapshot.calendar_events_today if snapshot else 0
    habits_done_today = snapshot.habits_done_today if snapshot else 0
    habits_total = len(habits)

    recent_sessions = await cs.get_recent_sessions(session, user_id, limit=1)
    days_no_activity = 999
    if recent_sessions:
        days_no_activity = (now - recent_sessions[0].created_at).days

    at_risk_habits = await cs.get_habits_at_risk(session, user_id, days_no_log=3)

    # MS1: overload_intervention
    # Условие: overdue>5 AND calendar_high AND habits_completion<50%
    habits_completion = (habits_done_today / habits_total) if habits_total > 0 else 1.0
    if tasks_overdue > 5 and calendar_events >= 6 and habits_completion < 0.5:
        candidates.append(NudgeCandidate(
            nudge_type="overload_intervention",
            priority=PRIORITY_CRITICAL,
            text=(
                "🚨 *Вижу признаки перегруза.*\n\n"
                f"• {tasks_overdue} задач просрочено\n"
                f"• {calendar_events} событий сегодня\n"
                f"• Привычки выполнены на {int(habits_completion*100)}%\n\n"
                "Это слишком много для одного человека. Давай разгрузимся?\n\n"
                "_Хочу помочь расставить приоритеты:_"
            ),
            keyboard=overload_kb(),
            context={"overdue": tasks_overdue, "calendar": calendar_events},
        ))

    # MS2: recovery_mode_trigger
    # Условие: no_activity>3d AND streak_broken>2
    broken_streaks = len([h for h in habits if h.current_streak == 0])
    if days_no_activity >= 3 and broken_streaks >= 2:
        candidates.append(NudgeCandidate(
            nudge_type="recovery_mode_trigger",
            priority=PRIORITY_CRITICAL,
            text=(
                "💙 Привет. Несколько дней без активности — это нормально.\n\n"
                "Не буду требовать многого. Просто один маленький шаг?\n\n"
                "_Выбери что-то совсем простое:_"
            ),
            keyboard=recovery_kb(),
            context={"days": days_no_activity, "broken_streaks": broken_streaks},
        ))

    # MS3: momentum_boost
    # Условие: 7/7 habits AND goal_progress_positive AND tasks_rate>70%
    all_habits_streak = all(h.current_streak >= 7 for h in habits) if habits else False
    any_goal_progress = any(g.progress_pct > 0 and g.progress_pct < 100 for g in goals)
    tasks_rate = getattr(snapshot, 'task_completion_rate', 0.0) if snapshot else 0.0
    if all_habits_streak and any_goal_progress and tasks_rate >= 0.7:
        candidates.append(NudgeCandidate(
            nudge_type="momentum_boost",
            priority=PRIORITY_HIGH,
            text=(
                "🚀 *Ты в потоке!*\n\n"
                "• Все привычки — 7+ дней\n"
                "• Цели движутся\n"
                "• Задачи выполняются\n\n"
                "Отличный момент чтобы поднять планку или добавить новую цель!\n\n"
                "_Что дальше?_"
            ),
            keyboard=momentum_kb(),
            context={},
        ))

    # MS4: silent_goal — цель без задач и check-ins >7 дней
    now_utc = datetime.utcnow()
    for g in goals:
        if not g.is_frozen:
            checkins = await cs.get_recent_goal_checkins(session, user_id, limit=1)
            goal_checkins = [c for c in checkins if getattr(c, 'goal_id', None) == g.id]
            days_since_ci = 999
            if goal_checkins:
                days_since_ci = (now_utc - goal_checkins[0].created_at).days
            if days_since_ci >= 7 and not snapshot.stick_at_risk if snapshot else True:
                candidates.append(NudgeCandidate(
                    nudge_type="silent_goal",
                    priority=PRIORITY_HIGH,
                    text=(
                        f"🔕 Цель «*{g.title}*» тихо лежит уже {days_since_ci} дней.\n\n"
                        "Она ещё актуальна? Продолжаем или заморозим?\n\n"
                        "_Выбери:_"
                    ),
                    keyboard=goal_card_kb(g.id, is_frozen=False),
                    context={"goal_id": g.id, "days": days_since_ci},
                ))
                break  # только одна за раз

    return sorted(candidates, key=lambda c: c.priority)


# ════════════════════════════════════════════════════════════════════════════════
# РИТУАЛЫ §20
# ════════════════════════════════════════════════════════════════════════════════

async def evaluate_rituals(
    session: AsyncSession,
    user_id: int,
    profile,    # UserCoachingProfile
    snapshot,
) -> list[NudgeCandidate]:
    """
    Ритуалы по расписанию §20.1-§20.3.

    Проверяются временны́е окна в МСК и не дублируются (cooldown через check_antispam).
    """
    candidates: list[NudgeCandidate] = []
    now_msk = datetime.now(DEFAULT_TZ)
    hour = now_msk.hour
    weekday = now_msk.weekday()  # 0=пн, 6=вс
    day_of_month = now_msk.day

    goals = await cs.get_goals(session, user_id, status="active")
    habits = await cs.get_habits(session, user_id, is_active=True)
    habits_done_today = snapshot.habits_done_today if snapshot else 0

    # Окно morning brief: 07:00-09:00 по профилю (или дефолт)
    # Парсим предпочтительное время из профиля
    checkin_hour = 20  # дефолт
    if profile and profile.preferred_checkin_time:
        try:
            checkin_hour = int(profile.preferred_checkin_time.split(":")[0])
        except (ValueError, AttributeError):
            pass

    # ── MORNING BRIEF (07:00-09:00) ──────────────────────────────────────────
    morning_enabled = profile.morning_brief_enabled if profile else True
    if morning_enabled and 7 <= hour <= 9:
        focus_goal = next((g for g in goals if not g.is_frozen), None)
        habits_pending = [h for h in habits if h.current_streak == 0 or True][:3]
        brief_text = "🌅 *Доброе утро!*\n\n"
        if focus_goal:
            brief_text += f"🎯 Фокус дня: «{focus_goal.title}» ({focus_goal.progress_pct}%)\n"
        if habits_pending:
            names = ", ".join(h.title[:20] for h in habits_pending[:3])
            brief_text += f"🔁 Привычки сегодня: {names}\n"
        brief_text += "\n_Хорошего дня! Ты справишься 💪_"
        candidates.append(NudgeCandidate(
            nudge_type="morning_brief",
            priority=PRIORITY_MEDIUM,
            text=brief_text,
            keyboard=checkin_mood_kb(focus_goal.id if focus_goal else 0),
            context={},
        ))

    # ── EVENING CHECK-IN (20:00-22:00) ───────────────────────────────────────
    evening_enabled = profile.evening_reflection_enabled if profile else True
    if evening_enabled and checkin_hour <= hour <= checkin_hour + 2:
        focus_goal = next((g for g in goals if not g.is_frozen), None)
        candidates.append(NudgeCandidate(
            nudge_type="evening_checkin",
            priority=PRIORITY_MEDIUM,
            text=(
                "🌙 *Вечерний check-in.*\n\n"
                f"Привычки сегодня: {habits_done_today}/{len(habits)} ✅\n\n"
                "_Как прошёл день? Что удалось?_"
            ),
            keyboard=checkin_mood_kb(focus_goal.id if focus_goal else 0),
            context={},
        ))

    # ── SUNDAY WEEKLY REVIEW (18:00, воскресенье) ────────────────────────────
    if weekday == 6 and 18 <= hour <= 20:
        latest_review = await cs.get_latest_review(session, user_id)
        now_utc = datetime.utcnow()
        if not latest_review or (now_utc - latest_review.created_at).days >= 5:
            candidates.append(NudgeCandidate(
                nudge_type="sunday_weekly_review",
                priority=PRIORITY_HIGH,
                text=(
                    "📊 *Воскресный обзор недели.*\n\n"
                    "10 минут рефлексии — и следующая неделя уже не случайная.\n\n"
                    "_Начнём?_"
                ),
                keyboard=weekly_review_kb(),
                context={},
            ))

    # ── MONDAY MORNING FOCUS (08:00, понедельник) ────────────────────────────
    if weekday == 0 and 8 <= hour <= 10:
        focus_goals = goals[:3]
        text = "📌 *Понедельник! Топ-3 фокуса недели:*\n\n"
        for i, g in enumerate(focus_goals, 1):
            text += f"{i}. {g.title} — {g.progress_pct}%\n"
        if not focus_goals:
            text += "_Нет активных целей — создать первую?_\n"
        text += "\n_Какая цель — главная на эту неделю?_"
        candidates.append(NudgeCandidate(
            nudge_type="monday_morning_focus",
            priority=PRIORITY_HIGH,
            text=text,
            keyboard=weekly_review_kb(),
            context={},
        ))

    # ── MONTHLY RESET (1-е число месяца, 09:00) ──────────────────────────────
    if day_of_month == 1 and 9 <= hour <= 11:
        month_name = now_msk.strftime("%B")
        candidates.append(NudgeCandidate(
            nudge_type="monthly_reset",
            priority=PRIORITY_HIGH,
            text=(
                f"📅 *Новый месяц — {month_name}!*\n\n"
                "Отличный момент пересмотреть цели и зафиксировать победы прошлого месяца.\n\n"
                "_Сделаем месячный обзор?_"
            ),
            keyboard=weekly_review_kb(),
            context={},
        ))

    # ── ANTI-DROPOUT (3/5/10 дней без активности) ────────────────────────────
    recent_sessions = await cs.get_recent_sessions(session, user_id, limit=1)
    now_utc = datetime.utcnow()
    days_inactive = 999
    if recent_sessions:
        days_inactive = (now_utc - recent_sessions[0].created_at).days

    if days_inactive == 3:
        candidates.append(NudgeCandidate(
            nudge_type="anti_dropout_3d",
            priority=PRIORITY_HIGH,
            text=(
                "👋 Привет! 3 дня не виделись.\n\n"
                "Всё в порядке? Просто один check-in — и мы снова на связи.\n\n"
                "_Как дела?_"
            ),
            keyboard=recovery_kb(),
            context={"days": 3},
        ))
    elif days_inactive == 5:
        candidates.append(NudgeCandidate(
            nudge_type="anti_dropout_5d",
            priority=PRIORITY_CRITICAL,
            text=(
                "😌 5 дней без активности...\n\n"
                "Я не буду давить. Но один маленький шаг сейчас — это уже возвращение.\n\n"
                "Что у тебя изменилось? Давай скорректируем план под реальность.\n\n"
                "_Просто напиши что происходит._"
            ),
            keyboard=recovery_kb(),
            context={"days": 5},
        ))
    elif days_inactive >= 10:
        candidates.append(NudgeCandidate(
            nudge_type="anti_dropout_10d",
            priority=PRIORITY_CRITICAL,
            text=(
                "💌 Последняя попытка.\n\n"
                "Прошло 10 дней. Я понимаю — жизнь случается.\n\n"
                "Если сложно — давай упростим всё до одного крошечного шага.\n\n"
                "_Готов к лёгкому старту?_"
            ),
            keyboard=recovery_kb(),
            context={"days": days_inactive},
        ))

    return candidates


# ════════════════════════════════════════════════════════════════════════════════
# ВЫБОР ТОПОВОГО NUDGE (не более 1 HIGH + 1 MEDIUM в день)
# ════════════════════════════════════════════════════════════════════════════════

def select_top_nudge(
    candidates: list[NudgeCandidate],
    already_sent_types: set[str],
) -> Optional[NudgeCandidate]:
    """
    Выбирает одного кандидата для отправки.

    Правила §5.3:
    - Уже отправленные типы исключаются
    - CRITICAL: первый доступный
    - HIGH: первый доступный (не более 1 за сеанс)
    - MEDIUM: первый доступный (не более 1 за сеанс)
    - LOW: если нет более важных
    """
    available = [c for c in candidates if c.nudge_type not in already_sent_types]

    # Сначала CRITICAL
    for c in available:
        if c.priority == PRIORITY_CRITICAL:
            return c

    # Потом HIGH
    for c in available:
        if c.priority == PRIORITY_HIGH:
            return c

    # Потом MEDIUM
    for c in available:
        if c.priority == PRIORITY_MEDIUM:
            return c

    # LOW — только если список небольшой
    for c in available:
        if c.priority == PRIORITY_LOW:
            return c

    return None


# ════════════════════════════════════════════════════════════════════════════════
# ПОЛНЫЙ PIPELINE ДЛЯ ОДНОГО ПОЛЬЗОВАТЕЛЯ
# ════════════════════════════════════════════════════════════════════════════════

async def run_proactive_for_user(
    session: AsyncSession,
    bot: Bot,
    user_id: int,
) -> bool:
    """
    Полный proactive pipeline для одного пользователя.

    1. Проверяет тихие часы
    2. Получает профиль и snapshot
    3. Обновляет snapshot (compute_user_state + compute_risk_scores)
    4. Оценивает ритуалы + триггеры
    5. Выбирает top nudge через select_top_nudge
    6. Проверяет antispam через check_antispam
    7. Отправляет сообщение и логирует

    Возвращает True если сообщение отправлено.
    """
    # 1. Тихие часы — ничего не отправляем
    if check_quiet_hours():
        return False

    try:
        # 2. Получаем профиль и snapshot
        profile = await cs.get_or_create_profile(session, user_id)
        snapshot = await cs.get_latest_snapshot(session, user_id)

        # 3. Обновляем snapshot и риски (не чаще раза в час)
        now = datetime.utcnow()
        snapshot_stale = (
            not snapshot
            or (now - snapshot.created_at).total_seconds() > 3600
        )
        if snapshot_stale:
            snapshot = await update_daily_snapshot(session, user_id)
            await session.commit()

        risks = await compute_risk_scores(session, user_id)
        state_data = await compute_user_state(session, user_id)
        state = state_data["state"]

        # Проверяем режим уведомлений профиля
        notification_mode = getattr(profile, 'coaching_mode', 'standard')

        # 4. Оцениваем кандидатов
        all_candidates: list[NudgeCandidate] = []

        # Ритуалы — всегда (если включены)
        ritual_candidates = await evaluate_rituals(session, user_id, profile, snapshot)
        all_candidates.extend(ritual_candidates)

        # Триггеры: soft = нет; standard = HIGH+CRITICAL; active = все
        if notification_mode != "soft":
            trigger_candidates = await evaluate_triggers(
                session, user_id, snapshot, risks, state
            )
            multi_candidates = await evaluate_multi_signal_triggers(
                session, user_id, snapshot, risks, state
            )
            if notification_mode == "active":
                all_candidates.extend(trigger_candidates)
                all_candidates.extend(multi_candidates)
            else:  # standard
                high_and_critical = [
                    c for c in (trigger_candidates + multi_candidates)
                    if c.priority <= PRIORITY_HIGH
                ]
                all_candidates.extend(high_and_critical)

        # Re-engagement: мягкий nudge если функция не используется >14 дней
        reeng_candidates = await evaluate_reengagement_nudge(session, user_id, snapshot)
        all_candidates.extend(reeng_candidates)

        if not all_candidates:
            return False

        # 5. Выбираем top nudge
        nudge = select_top_nudge(all_candidates, already_sent_types=set())
        if not nudge:
            return False

        # 6. Antispam проверка
        max_nudges = getattr(profile, 'max_daily_nudges', 3)
        allowed = await cs.check_antispam(
            session, user_id, nudge.nudge_type,
            cooldown_hours_same_type=48,
            cooldown_hours_any=4,
            max_per_day=max_nudges,
        )
        if not allowed:
            logger.debug("Proactive blocked by antispam: user=%s type=%s", user_id, nudge.nudge_type)
            return False

        # 7. Отправляем сообщение
        await bot.send_message(
            chat_id=user_id,
            text=nudge.text,
            parse_mode="Markdown",
            reply_markup=nudge.keyboard,
        )

        # 8. Логируем отправку
        await cs.log_nudge_sent(session, user_id, nudge.nudge_type)
        await session.commit()

        logger.info(
            "Proactive sent: user=%s type=%s priority=%s state=%s",
            user_id, nudge.nudge_type, nudge.priority, state,
        )
        return True

    except Exception as exc:
        logger.error("Proactive error for user=%s: %s", user_id, exc, exc_info=True)
        return False

async def evaluate_reengagement_nudge(
    session,
    user_id: int,
    snapshot,
) -> list:
    """
    Re-engagement триггер: если функция (цели/привычки/чекин) не использовалась >14 дней.
    Приоритет: MEDIUM (3). Генерирует мягкое напоминание.
    """
    from datetime import datetime, timedelta, timezone
    candidates = []
    now = datetime.now(timezone.utc)
    threshold = timedelta(days=14)

    checks = {
        "reengagement_goals":   ("goals",   "goal_last_action"),
        "reengagement_habits":  ("habits",  "habit_last_log"),
        "reengagement_checkin": ("checkin", "last_checkin_at"),
    }

    for nudge_type, (feature, attr) in checks.items():
        last_ts = getattr(snapshot, attr, None) if snapshot else None
        # Нормализуем timezone
        if last_ts and last_ts.tzinfo is None:
            from datetime import timezone as tz
            last_ts = last_ts.replace(tzinfo=tz.utc)
        if last_ts is None or (now - last_ts) > threshold:
            days_ago = int((now - last_ts).days) if last_ts else 14
            days_ago = min(days_ago, 99)

            messages = {
                "goals":   (
                    f"\U0001f3af \u0423\u0436\u0435 {days_ago} \u0434\u043d\u0435\u0439 \u0431\u0435\u0437 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f \u0446\u0435\u043b\u0435\u0439 \u2014 \u043e\u043d\u0438 \u043f\u043e\u043c\u043d\u044f\u0442 \u043e \u0442\u0435\u0431\u0435!\n\n"
                    "\u0414\u0430\u0436\u0435 \u043e\u0434\u0438\u043d \u043c\u0430\u043b\u0435\u043d\u044c\u043a\u0438\u0439 \u0448\u0430\u0433 \u0432\u043f\u0435\u0440\u0451\u0434 \u0441\u0435\u0433\u043e\u0434\u043d\u044f \u043d\u0435 \u0434\u0430\u0441\u0442 \u043f\u043e\u0442\u0435\u0440\u044f\u0442\u044c \u0438\u043c\u043f\u0443\u043b\u044c\u0441. \u041f\u0440\u043e\u0432\u0435\u0440\u0438\u043c?"
                ),
                "habits":  (
                    f"\U0001f501 \u041f\u0440\u0438\u0432\u044b\u0447\u043a\u0438 \u0436\u0434\u0443\u0442 {days_ago} \u0434\u043d\u0435\u0439.\n\n"
                    "\u041f\u0440\u043e\u043f\u0443\u0441\u043a \u043d\u0435 \u043e\u0431\u043d\u0443\u043b\u044f\u0435\u0442 \u0441\u0435\u0440\u0438\u044e \u2014 \u0433\u043b\u0430\u0432\u043d\u043e\u0435 \u0432\u043e\u0437\u043e\u0431\u043d\u043e\u0432\u0438\u0442\u044c. "
                    "\u0417\u0430\u043b\u043e\u0433\u0438\u0440\u0443\u0435\u043c \u0445\u043e\u0442\u044f \u0431\u044b \u043e\u0434\u043d\u0443 \u0441\u0435\u0433\u043e\u0434\u043d\u044f?"
                ),
                "checkin": (
                    f"\u2705 {days_ago} \u0434\u043d\u0435\u0439 \u0431\u0435\u0437 check-in \u2014 \u043c\u043d\u0435 \u043d\u0435 \u0445\u0432\u0430\u0442\u0430\u0435\u0442 \u0434\u0430\u043d\u043d\u044b\u0445 \u043e \u0442\u0435\u0431\u0435.\n\n"
                    "\u0414\u0430\u0436\u0435 \u043f\u0430\u0440\u0430 \u0441\u0442\u0440\u043e\u043a \u043f\u043e\u043c\u043e\u0436\u0435\u0442 \u043c\u043d\u0435 \u0434\u0430\u0442\u044c \u0442\u043e\u0447\u043d\u044b\u0435 \u0441\u043e\u0432\u0435\u0442\u044b. \u041a\u0430\u043a \u0442\u044b \u0441\u0435\u0439\u0447\u0430\u0441?"
                ),
            }
            text = messages[feature]
            candidates.append(NudgeCandidate(
                nudge_type=nudge_type,
                priority=PRIORITY_MEDIUM,
                text=text,
                keyboard=None,
            ))

    return candidates
