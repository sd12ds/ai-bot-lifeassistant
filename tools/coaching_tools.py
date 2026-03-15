"""
Coaching Tools — 30+ инструментов для LangGraph coaching-агента.

Паттерн: make_coaching_tools(user_id) → list[tool]
Все инструменты работают асинхронно через get_async_session().

Группы: Goals, Milestones, Habits, Check-ins, Reviews,
         Insights, Memory, Drafts, Recommendations, Onboarding, Orchestration
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from langchain.tools import tool

from db.session import get_async_session
from db import coaching_storage as cs


def make_coaching_tools(user_id: int) -> list:
    """Создаёт 30+ coaching-инструментов, привязанных к user_id."""

    # ═══════════════════════════════════════════════════════════════════════
    # GOALS — управление целями
    # ═══════════════════════════════════════════════════════════════════════

    @tool
    async def goal_list(status: str = "active", area: str = "") -> str:
        """
        Показать список целей пользователя.
        status — фильтр: active | achieved | cancelled (пусто = все активные)
        area — фильтр по области: health | finance | career | personal | relationships
        """
        async with get_async_session() as session:
            goals = await cs.get_goals(
                session, user_id,
                status=status or "active",
                area=area or None
            )
            if not goals:
                return "Целей не найдено."
            lines = [f"📋 Целей: {len(goals)}"]
            for g in goals:
                frozen = " 🧊" if g.is_frozen else ""
                lines.append(
                    f"• #{g.id} [{g.priority}] {g.title}{frozen} — {g.progress_pct}% "
                    f"({'до ' + str(g.target_date) if g.target_date else 'без дедлайна'})"
                )
            return "\n".join(lines)

    @tool
    async def goal_create(
        title: str,
        area: str = "",
        why_statement: str = "",
        first_step: str = "",
        target_date: str = "",
        priority: str = "medium",
    ) -> str:
        """
        Создать новую цель.
        title — название цели
        area — область: health | finance | career | personal | relationships
        why_statement — глубинная мотивация «зачем мне это»
        first_step — первый конкретный шаг
        target_date — дедлайн в формате YYYY-MM-DD (необязательно)
        priority — high | medium | low
        """
        async with get_async_session() as session:
            kwargs = {
                "title": title,
                "priority": priority,
            }
            if area:
                kwargs["area"] = area
            if why_statement:
                kwargs["why_statement"] = why_statement
            if first_step:
                kwargs["first_step"] = first_step
            if target_date:
                from datetime import date
                try:
                    kwargs["target_date"] = date.fromisoformat(target_date)
                except ValueError:
                    pass

            goal = await cs.create_goal(session, user_id, **kwargs)
            await session.commit()
            return (
                f"✅ Цель создана: #{goal.id} «{goal.title}»\n"
                f"Область: {goal.area or '—'} | Приоритет: {goal.priority}\n"
                + (f"Почему важно: {goal.why_statement}\n" if goal.why_statement else "")
                + (f"Первый шаг: {goal.first_step}" if goal.first_step else "")
            )

    @tool
    async def goal_update(
        goal_id: int,
        title: str = "",
        progress_pct: int = -1,
        why_statement: str = "",
        first_step: str = "",
        priority: str = "",
        area: str = "",
    ) -> str:
        """
        Обновить поля цели.
        goal_id — ID цели
        progress_pct — прогресс 0-100 (-1 = не обновлять)
        Остальные поля — опциональны.
        """
        async with get_async_session() as session:
            kwargs = {}
            if title:
                kwargs["title"] = title
            if progress_pct >= 0:
                kwargs["progress_pct"] = min(100, max(0, progress_pct))
            if why_statement:
                kwargs["why_statement"] = why_statement
            if first_step:
                kwargs["first_step"] = first_step
            if priority:
                kwargs["priority"] = priority
            if area:
                kwargs["area"] = area
            if not kwargs:
                return "Нет полей для обновления."
            goal = await cs.update_goal(session, goal_id, user_id, **kwargs)
            await session.commit()
            if not goal:
                return f"Цель #{goal_id} не найдена."
            return f"✅ Цель #{goal_id} обновлена: {goal.title} — {goal.progress_pct}%"

    @tool
    async def goal_update_progress(goal_id: int, progress_pct: int) -> str:
        """
        Быстро обновить прогресс цели.
        goal_id — ID цели
        progress_pct — прогресс 0-100
        """
        async with get_async_session() as session:
            goal = await cs.update_goal(
                session, goal_id, user_id,
                progress_pct=min(100, max(0, progress_pct))
            )
            await session.commit()
            if not goal:
                return f"Цель #{goal_id} не найдена."
            if goal.progress_pct == 100:
                return f"🎉 ЦЕЛЬ ДОСТИГНУТА! «{goal.title}» — 100%! Поздравляю!"
            return f"✅ Прогресс обновлён: «{goal.title}» — {goal.progress_pct}%"

    @tool
    async def goal_freeze(goal_id: int, reason: str = "") -> str:
        """
        Заморозить цель (поставить на паузу).
        goal_id — ID цели
        reason — причина заморозки
        """
        async with get_async_session() as session:
            goal = await cs.update_goal(
                session, goal_id, user_id,
                is_frozen=True,
                frozen_reason=reason or "Нет причины"
            )
            await session.commit()
            if not goal:
                return f"Цель #{goal_id} не найдена."
            return f"🧊 Цель «{goal.title}» заморожена. Причина: {goal.frozen_reason}"

    @tool
    async def goal_resume(goal_id: int) -> str:
        """
        Возобновить замороженную цель.
        goal_id — ID цели
        """
        async with get_async_session() as session:
            goal = await cs.update_goal(
                session, goal_id, user_id,
                is_frozen=False,
                frozen_reason=None
            )
            await session.commit()
            if not goal:
                return f"Цель #{goal_id} не найдена."
            return f"▶️ Цель «{goal.title}» возобновлена! Продолжаем."

    @tool
    async def goal_archive(goal_id: int, achieved: bool = False) -> str:
        """
        Архивировать цель (завершить или отменить).
        goal_id — ID цели
        achieved — True если цель достигнута, False если отменяется
        """
        async with get_async_session() as session:
            new_status = "achieved" if achieved else "cancelled"
            goal = await cs.update_goal(session, goal_id, user_id, status=new_status)
            await session.commit()
            if not goal:
                return f"Цель #{goal_id} не найдена."
            emoji = "🏆" if achieved else "📦"
            return f"{emoji} Цель «{goal.title}» {'достигнута! Отличная работа!' if achieved else 'отменена.'}"

    @tool
    async def goal_restart(goal_id: int) -> str:
        """
        Перезапустить цель (сбросить прогресс, вернуть в active).
        Используй когда пользователь хочет начать заново.
        """
        async with get_async_session() as session:
            goal = await cs.update_goal(
                session, goal_id, user_id,
                status="active",
                progress_pct=0,
                is_frozen=False,
            )
            await session.commit()
            if not goal:
                return f"Цель #{goal_id} не найдена."
            return f"🔄 Цель «{goal.title}» перезапущена! Начинаем заново с чистого листа."

    @tool
    async def goal_generate_plan(goal_id: int) -> str:
        """
        Сгенерировать план достижения цели (список этапов/шагов).
        Агент самостоятельно придумывает этапы и создаёт их через goal_add_milestone.
        goal_id — ID цели
        """
        async with get_async_session() as session:
            goal = await cs.get_goal(session, goal_id, user_id)
            if not goal:
                return f"Цель #{goal_id} не найдена."
            milestones = await cs.get_milestones(session, goal_id, user_id)
            if milestones:
                lines = [f"📋 Этапы для цели «{goal.title}»:"]
                for m in milestones:
                    status_emoji = "✅" if m.status == "done" else ("⏭️" if m.status == "skipped" else "⬜")
                    lines.append(f"  {status_emoji} {m.title}")
                return "\n".join(lines)
            return (
                f"Цель «{goal.title}» пока без этапов.\n"
                f"Описание: {goal.why_statement or '—'}\n"
                f"Давай разобьём на конкретные шаги!"
            )

    # ═══════════════════════════════════════════════════════════════════════
    # MILESTONES — этапы цели
    # ═══════════════════════════════════════════════════════════════════════

    @tool
    async def goal_add_milestone(
        goal_id: int,
        title: str,
        due_date: str = "",
        sort_order: int = 0,
    ) -> str:
        """
        Добавить этап (промежуточную точку) к цели.
        goal_id — ID цели
        title — название этапа
        due_date — дедлайн этапа YYYY-MM-DD (необязательно)
        sort_order — порядок этапа (0 = в конец)
        """
        async with get_async_session() as session:
            kwargs = {"title": title, "sort_order": sort_order}
            if due_date:
                from datetime import date
                try:
                    kwargs["due_date"] = date.fromisoformat(due_date)
                except ValueError:
                    pass
            milestone = await cs.create_milestone(session, goal_id, user_id, **kwargs)
            await session.commit()
            return f"✅ Этап добавлен: «{milestone.title}» к цели #{goal_id}"

    @tool
    async def goal_complete_milestone(milestone_id: int) -> str:
        """
        Отметить этап цели как выполненный.
        milestone_id — ID этапа
        """
        async with get_async_session() as session:
            milestone = await cs.complete_milestone(session, milestone_id, user_id)
            await session.commit()
            if not milestone:
                return f"Этап #{milestone_id} не найден."
            return f"✅ Этап «{milestone.title}» выполнен! Отлично!"

    @tool
    async def goal_show_milestones(goal_id: int) -> str:
        """
        Показать все этапы цели с их статусами.
        goal_id — ID цели
        """
        async with get_async_session() as session:
            goal = await cs.get_goal(session, goal_id, user_id)
            if not goal:
                return f"Цель #{goal_id} не найдена."
            milestones = await cs.get_milestones(session, goal_id, user_id)
            if not milestones:
                return f"У цели «{goal.title}» пока нет этапов."
            lines = [f"📋 Этапы «{goal.title}»:"]
            done = sum(1 for m in milestones if m.status == "done")
            lines.append(f"Выполнено: {done}/{len(milestones)}")
            for m in milestones:
                s = "✅" if m.status == "done" else ("⏭️" if m.status == "skipped" else "⬜")
                deadline = f" (до {m.due_date})" if m.due_date else ""
                lines.append(f"  {s} #{m.id} {m.title}{deadline}")
            return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════════════════
    # HABITS — управление привычками
    # ═══════════════════════════════════════════════════════════════════════

    @tool
    async def habit_list(show_inactive: bool = False) -> str:
        """Показать список привычек пользователя."""
        async with get_async_session() as session:
            habits = await cs.get_habits(
                session, user_id,
                is_active=None if show_inactive else True
            )
            if not habits:
                return "Привычек нет. Хочешь создать первую?"
            lines = [f"🔁 Привычек: {len(habits)}"]
            for h in habits:
                active_mark = "" if h.is_active else " [пауза]"
                lines.append(
                    f"• #{h.id} {h.title}{active_mark} — стрик: {h.current_streak}🔥 "
                    f"(рекорд: {h.longest_streak})"
                )
            return "\n".join(lines)

    @tool
    async def habit_create(
        title: str,
        area: str = "",
        frequency: str = "daily",
        cue: str = "",
        reward: str = "",
        best_time: str = "",
        difficulty: str = "medium",
        goal_id: int = 0,
    ) -> str:
        """
        Создать новую привычку.
        title — название
        area — область: health | productivity | mindset | sport
        frequency — daily | weekly | custom
        cue — триггер (когда/после чего выполнять)
        reward — награда после выполнения
        best_time — morning | afternoon | evening | anytime
        difficulty — easy | medium | hard
        goal_id — привязать к цели (0 = нет привязки)
        """
        async with get_async_session() as session:
            kwargs = {
                "title": title,
                "frequency": frequency,
                "difficulty": difficulty,
            }
            if area:
                kwargs["area"] = area
            if cue:
                kwargs["cue"] = cue
            if reward:
                kwargs["reward"] = reward
            if best_time:
                kwargs["best_time"] = best_time
            if goal_id > 0:
                kwargs["goal_id"] = goal_id

            from db.models import Habit
            habit = Habit(user_id=user_id, **kwargs)
            session.add(habit)
            await session.flush()
            await session.refresh(habit)
            await session.commit()
            return (
                f"✅ Привычка создана: #{habit.id} «{habit.title}»\n"
                + (f"Триггер: {habit.cue}\n" if habit.cue else "")
                + (f"Награда: {habit.reward}\n" if habit.reward else "")
                + (f"Лучшее время: {habit.best_time}" if habit.best_time else "")
            )

    @tool
    async def habit_log(habit_id: int, notes: str = "") -> str:
        """
        Залогировать выполнение привычки (отметить как сделано).
        habit_id — ID привычки
        notes — заметка (необязательно)
        """
        async with get_async_session() as session:
            habit = await cs.increment_habit_streak(session, habit_id, user_id)
            if not habit:
                return f"Привычка #{habit_id} не найдена."

            # Создаём запись в habit_logs
            from db.models import HabitLog
            log = HabitLog(
                habit_id=habit_id,
                user_id=user_id,
                notes=notes,
            )
            session.add(log)
            await session.commit()

            streak_msg = ""
            if habit.current_streak == habit.longest_streak and habit.current_streak > 1:
                streak_msg = f" 🏆 Новый рекорд серии: {habit.current_streak} дней!"
            elif habit.current_streak > 0:
                streak_msg = f" 🔥 Серия: {habit.current_streak} дней"

            return f"✅ «{habit.title}» выполнена!{streak_msg}"

    @tool
    async def habit_log_miss(habit_id: int, reason: str = "") -> str:
        """
        Отметить пропуск привычки.
        habit_id — ID привычки
        reason — причина пропуска (необязательно)
        """
        async with get_async_session() as session:
            habit = await cs.reset_habit_streak(session, habit_id, user_id, reason=reason)
            await session.commit()
            if not habit:
                return f"Привычка #{habit_id} не найдена."
            return (
                f"📝 Пропуск «{habit.title}» зафиксирован.\n"
                "Пропуск не обнуляет всё — главное не пропускать дважды подряд. 💪"
            )

    @tool
    async def habit_pause(habit_id: int) -> str:
        """Поставить привычку на паузу."""
        async with get_async_session() as session:
            from sqlalchemy import update
            from db.models import Habit
            await session.execute(
                update(Habit).where(Habit.id == habit_id, Habit.user_id == user_id).values(is_active=False)
            )
            await session.commit()
            return f"⏸️ Привычка #{habit_id} поставлена на паузу."

    @tool
    async def habit_resume(habit_id: int) -> str:
        """Возобновить привычку с паузы."""
        async with get_async_session() as session:
            from sqlalchemy import update
            from db.models import Habit
            await session.execute(
                update(Habit).where(Habit.id == habit_id, Habit.user_id == user_id).values(is_active=True)
            )
            await session.commit()
            return f"▶️ Привычка #{habit_id} возобновлена!"

    @tool
    async def habit_adjust_frequency(habit_id: int, frequency: str, target_count: int = 1) -> str:
        """
        Изменить частоту привычки.
        frequency — daily | weekly | custom
        target_count — целевое количество раз
        """
        async with get_async_session() as session:
            from sqlalchemy import update
            from db.models import Habit
            await session.execute(
                update(Habit).where(Habit.id == habit_id, Habit.user_id == user_id)
                .values(frequency=frequency, target_count=target_count)
            )
            await session.commit()
            return f"✅ Частота привычки #{habit_id} изменена: {frequency} × {target_count}"

    @tool
    async def habit_archive(habit_id: int) -> str:
        """Архивировать привычку (мягкое удаление)."""
        async with get_async_session() as session:
            from sqlalchemy import update
            from db.models import Habit
            await session.execute(
                update(Habit).where(Habit.id == habit_id, Habit.user_id == user_id)
                .values(is_active=False)
            )
            await session.commit()
            return f"📦 Привычка #{habit_id} архивирована."

    @tool
    async def habit_template_list(area: str = "", difficulty: str = "") -> str:
        """
        Показать библиотеку готовых шаблонов привычек.
        area — фильтр по области
        difficulty — easy | medium | hard
        """
        async with get_async_session() as session:
            templates = await cs.get_habit_templates(
                session,
                area=area or None,
                difficulty=difficulty or None,
                limit=15,
            )
            if not templates:
                return "Шаблонов не найдено."
            lines = ["📚 Шаблоны привычек:"]
            for t in templates:
                lines.append(
                    f"• #{t.id} {t.title} [{t.area or '—'}] [{t.difficulty}]"
                    + (f" — {t.cue}" if t.cue else "")
                )
            return "\n".join(lines)

    @tool
    async def coaching_template_apply(template_id: int, goal_id: int = 0) -> str:
        """
        Создать привычку из шаблона.
        template_id — ID шаблона
        goal_id — привязать к цели (0 = нет)
        """
        async with get_async_session() as session:
            from db.models import HabitTemplate, Habit
            from sqlalchemy import select
            result = await session.execute(
                select(HabitTemplate).where(HabitTemplate.id == template_id)
            )
            tmpl = result.scalar_one_or_none()
            if not tmpl:
                return f"Шаблон #{template_id} не найден."
            kwargs = {
                "title": tmpl.title,
                "area": tmpl.area,
                "cue": tmpl.cue,
                "reward": tmpl.reward,
                "difficulty": tmpl.difficulty,
            }
            if goal_id > 0:
                kwargs["goal_id"] = goal_id
            # Increment use_count
            tmpl.use_count += 1
            habit = Habit(user_id=user_id, **kwargs)
            session.add(habit)
            await session.flush()
            await session.refresh(habit)
            await session.commit()
            return f"✅ Привычка создана из шаблона: #{habit.id} «{habit.title}»"

    # ═══════════════════════════════════════════════════════════════════════
    # CHECK-IN — ежедневный check-in
    # ═══════════════════════════════════════════════════════════════════════

    @tool
    async def coaching_checkin_create(
        goal_id: int = 0,
        progress_pct: int = 0,
        energy_level: int = 0,
        mood: str = "",
        notes: str = "",
        blockers: str = "",
        wins: str = "",
        time_slot: str = "manual",
        check_date: str = "",
    ) -> str:
        """
        Создать ежедневный check-in.
        goal_id — ID цели (0 = без привязки к цели)
        progress_pct — прогресс 0-100 (0 если неизвестен)
        energy_level — энергия 1-5 (0 = не указана)
        mood — настроение: great|good|ok|tired|bad (пусто = не указано)
        notes — заметки / как прошёл день
        blockers — что мешает
        wins — что удалось / победы дня
        time_slot — слот: morning|midday|evening|manual
        check_date — дата в формате YYYY-MM-DD (пусто = сегодня)
        """
        from datetime import date as _date

        # Определяем дату чекина
        if check_date:
            try:
                parsed_date = _date.fromisoformat(check_date)
            except ValueError:
                parsed_date = _date.today()
        else:
            parsed_date = _date.today()

        # Нормализуем goal_id (0 → None)
        gid = goal_id if goal_id and goal_id > 0 else None

        async with get_async_session() as session:
            checkin = await cs.create_goal_checkin(
                session, gid, user_id,
                progress_pct=progress_pct,
                energy_level=energy_level if energy_level > 0 else None,
                mood=mood or None,
                notes=notes or None,
                blockers=blockers or None,
                wins=wins or None,
                time_slot=time_slot or "manual",
                check_date=parsed_date,
            )
            # Обновляем прогресс у цели если она привязана и прогресс указан
            if gid and progress_pct > 0:
                await cs.update_goal(session, gid, user_id, progress_pct=progress_pct)
            await session.commit()

            slot_labels = {"morning": "🌅 Утро", "midday": "☀️ День", "evening": "🌙 Вечер", "manual": "📝"}
            energy_emojis = ["", "😴", "😕", "😐", "😊", "🔥"]
            mood_emojis = {"great": "😄", "good": "😊", "ok": "😐", "tired": "😴", "bad": "😟"}

            slot_label = slot_labels.get(time_slot, time_slot)
            e_str = f" Энергия: {energy_emojis[min(5, energy_level)]}{energy_level}/5" if energy_level > 0 else ""
            m_str = f" Настроение: {mood_emojis.get(mood, mood)}" if mood else ""
            return (
                f"✅ Check-in сохранён! {slot_label}\n"
                f"Дата: {parsed_date}{e_str}{m_str}\n"
                + (f"Победы: {wins}\n" if wins else "")
                + (f"Блокеры: {blockers}" if blockers else "")
            )

    @tool
    async def coaching_review_generate(
        goal_id: int,
        summary: str,
        highlights: str = "",
        blockers: str = "",
        next_actions: str = "",
        review_type: str = "weekly",
    ) -> str:
        """
        Создать недельный или месячный review по цели.
        goal_id — ID цели
        summary — краткое резюме недели
        highlights — ключевые достижения (через запятую)
        blockers — основные трудности
        next_actions — план на следующую неделю
        review_type — weekly | monthly
        """
        async with get_async_session() as session:
            review = await cs.create_goal_review(
                session, goal_id, user_id,
                review_type=review_type,
                summary=summary,
                highlights=[h.strip() for h in highlights.split(",") if h.strip()] if highlights else None,
                blockers=[b.strip() for b in blockers.split(",") if b.strip()] if blockers else None,
                next_actions=[a.strip() for a in next_actions.split(",") if a.strip()] if next_actions else None,
            )
            await session.commit()
            return (
                f"📊 Review сохранён!\n"
                f"Тип: {review_type} | ID: {review.id}\n"
                f"Итог: {summary[:100]}..."
            )

    @tool
    async def coaching_next_step_suggest(goal_id: int) -> str:
        """
        Подсказать следующий шаг для цели.
        Анализирует текущие этапы, прогресс и предлагает конкретное действие.
        goal_id — ID цели
        """
        async with get_async_session() as session:
            goal = await cs.get_goal(session, goal_id, user_id)
            if not goal:
                return f"Цель #{goal_id} не найдена."
            milestones = await cs.get_milestones(session, goal_id, user_id)
            pending = [m for m in milestones if m.status == "pending"]

            if pending:
                next_ms = pending[0]
                return (
                    f"📍 Следующий шаг для «{goal.title}»:\n"
                    f"→ {next_ms.title}"
                    + (f" (до {next_ms.due_date})" if next_ms.due_date else "")
                )
            elif goal.first_step:
                return (
                    f"📍 Первый шаг для «{goal.title}»:\n"
                    f"→ {goal.first_step}"
                )
            return (
                f"Для цели «{goal.title}» нет конкретных этапов. "
                f"Хочешь разбить её на шаги?"
            )

    @tool
    async def coaching_plan_generate(goal_id: int) -> str:
        """
        Запросить создание плана для цели с разбивкой на этапы.
        Агент должен продолжить диалог и уточнить детали для создания плана.
        """
        async with get_async_session() as session:
            goal = await cs.get_goal(session, goal_id, user_id)
            if not goal:
                return f"Цель #{goal_id} не найдена."
            return (
                f"Цель: «{goal.title}»\n"
                f"Прогресс: {goal.progress_pct}%\n"
                f"Почему важно: {goal.why_statement or 'не указано'}\n"
                f"Первый шаг: {goal.first_step or 'не указан'}\n"
                f"Дедлайн: {goal.target_date or 'не задан'}\n\n"
                f"Готов помочь разбить эту цель на конкретные этапы!"
            )

    # ═══════════════════════════════════════════════════════════════════════
    # INSIGHTS — AI-инсайты
    # ═══════════════════════════════════════════════════════════════════════

    @tool
    async def coaching_insight_get(severity: str = "") -> str:
        """
        Получить актуальные AI-инсайты пользователя.
        severity — фильтр: critical | high | medium | low | info (пусто = все)
        """
        async with get_async_session() as session:
            insights = await cs.get_active_insights(
                session, user_id,
                severity=severity or None,
                limit=5
            )
            if not insights:
                return "Актуальных инсайтов нет."
            lines = [f"💡 Инсайты ({len(insights)}):"]
            for i in insights:
                read_mark = "" if i.is_read else " 🆕"
                severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "ℹ️"}
                emoji = severity_emoji.get(i.severity, "ℹ️")
                lines.append(f"{emoji} #{i.id}{read_mark} {i.title}")
                if i.body:
                    lines.append(f"   {i.body[:80]}...")
            return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════════════════
    # MEMORY — долгосрочная память коуча
    # ═══════════════════════════════════════════════════════════════════════

    @tool
    async def coaching_memory_get() -> str:
        """
        Получить ключевые записи долгосрочной памяти коуча о пользователе.
        Используй для персонализации общения.
        """
        async with get_async_session() as session:
            memories = await cs.get_memory(session, user_id, top_n=10)
            if not memories:
                return "Память пока пуста — буду наблюдать и запоминать паттерны."
            lines = ["🧠 Что я знаю о тебе:"]
            for m in memories:
                explicit_mark = " (ты сам сказал)" if m.is_explicit else ""
                lines.append(f"• {m.key}: {m.value} [confidence: {m.confidence:.1f}]{explicit_mark}")
            return "\n".join(lines)

    @tool
    async def coaching_memory_update(
        key: str,
        value: str,
        memory_type: str = "preference",
        is_explicit: bool = True,
    ) -> str:
        """
        Обновить запись в памяти коуча.
        Используй когда пользователь явно указывает предпочтение или корректирует коуча.
        key — ключ (например: morning_person, best_time, motivator)
        value — значение
        memory_type — preference | pattern | fact | correction
        is_explicit — True если пользователь явно сказал это
        """
        async with get_async_session() as session:
            memory = await cs.upsert_memory(
                session, user_id,
                key=key,
                value=value,
                memory_type=memory_type,
                is_explicit=is_explicit,
                confidence=1.0 if is_explicit else 0.6,
            )
            await session.commit()
            return f"✅ Запомнил: {key} = {value}"

    # ═══════════════════════════════════════════════════════════════════════
    # DRAFTS — черновики многошаговых диалогов
    # ═══════════════════════════════════════════════════════════════════════

    @tool
    async def coaching_draft_create(
        draft_type: str,
        payload_json: str,
        step: int = 0,
    ) -> str:
        """
        Создать черновик многошагового диалога (сохранить прогресс flow).
        draft_type — goal_creation | habit_creation | checkin | review
        payload_json — JSON с накопленными данными
        step — текущий шаг flow
        """
        async with get_async_session() as session:
            try:
                payload = json.loads(payload_json)
            except Exception:
                payload = {"raw": payload_json}
            draft = await cs.upsert_draft(
                session, user_id, draft_type, payload, step
            )
            await session.commit()
            return f"💾 Черновик сохранён: {draft_type} (шаг {step})"

    @tool
    async def coaching_draft_update(
        draft_type: str,
        payload_json: str,
        step: int,
    ) -> str:
        """
        Обновить черновик диалога (следующий шаг).
        draft_type — тип черновика
        payload_json — обновлённые данные JSON
        step — новый текущий шаг
        """
        async with get_async_session() as session:
            try:
                payload = json.loads(payload_json)
            except Exception:
                payload = {"raw": payload_json}
            draft = await cs.upsert_draft(
                session, user_id, draft_type, payload, step
            )
            await session.commit()
            return f"💾 Черновик обновлён: {draft_type} (шаг {step})"

    @tool
    async def coaching_draft_get(draft_type: str = "") -> str:
        """
        Получить активный черновик диалога.
        draft_type — тип (пусто = любой)
        """
        async with get_async_session() as session:
            draft = await cs.get_active_draft(session, user_id, draft_type or None)
            if not draft:
                return "Незавершённых диалогов нет."
            return (
                f"📋 Незавершённый диалог: {draft.draft_type}\n"
                f"Шаг: {draft.step}\n"
                f"Данные: {json.dumps(draft.payload, ensure_ascii=False)}"
            )

    @tool
    async def coaching_draft_confirm(draft_type: str) -> str:
        """
        Завершить и удалить черновик диалога (после успешного создания).
        draft_type — тип черновика для удаления
        """
        async with get_async_session() as session:
            await cs.delete_draft(session, user_id, draft_type)
            await session.commit()
            return f"✅ Черновик {draft_type} завершён."

    # ═══════════════════════════════════════════════════════════════════════
    # RECOMMENDATIONS — рекомендации
    # ═══════════════════════════════════════════════════════════════════════

    @tool
    async def coaching_recommendations_get() -> str:
        """Получить текущие персональные рекомендации коуча."""
        async with get_async_session() as session:
            recs = await cs.get_active_recommendations(session, user_id, limit=5)
            if not recs:
                return "Актуальных рекомендаций нет."
            lines = ["📌 Рекомендации:"]
            for r in recs:
                lines.append(f"• #{r.id} [{r.rec_type}] {r.title}")
                if r.body:
                    lines.append(f"  {r.body[:100]}")
            return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════════════════
    # ONBOARDING — состояние онбординга
    # ═══════════════════════════════════════════════════════════════════════

    @tool
    async def coaching_onboarding_get_state() -> str:
        """Получить состояние онбординга пользователя."""
        async with get_async_session() as session:
            state = await cs.get_or_create_onboarding(session, user_id)
            profile = await cs.get_or_create_profile(session, user_id)
            steps = state.steps_completed or []
            return json.dumps({
                "current_step": state.current_step,
                "steps_completed": steps,
                "first_goal_created": state.first_goal_created,
                "first_habit_created": state.first_habit_created,
                "first_checkin_done": state.first_checkin_done,
                "bot_onboarding_done": state.bot_onboarding_done,
                "coach_tone": profile.coach_tone,
                "coaching_mode": profile.coaching_mode,
                "focus_areas": profile.focus_areas,
            }, ensure_ascii=False)

    @tool
    async def coaching_onboarding_complete_step(step_name: str) -> str:
        """
        Отметить шаг онбординга как выполненный.
        step_name — название шага: intro | profile | first_goal | first_habit | first_checkin
        """
        async with get_async_session() as session:
            state = await cs.advance_onboarding_step(session, user_id, step_name)

            # Обновляем специальные флаги
            kwargs = {}
            if step_name == "first_goal":
                kwargs["first_goal_created"] = True
            elif step_name == "first_habit":
                kwargs["first_habit_created"] = True
            elif step_name == "first_checkin":
                kwargs["first_checkin_done"] = True
            elif step_name == "intro":
                kwargs["bot_onboarding_done"] = True
            if kwargs:
                for k, v in kwargs.items():
                    setattr(state, k, v)

            await session.commit()
            return f"✅ Шаг онбординга «{step_name}» выполнен. Прогресс: {state.current_step} шагов."

    @tool
    async def coaching_profile_update(
        coach_tone: str = "",
        coaching_mode: str = "",
        preferred_checkin_time: str = "",
        max_daily_nudges: int = 0,
        focus_areas: str = "",
    ) -> str:
        """
        Обновить профиль коуча (настройки взаимодействия).
        coach_tone — strict | friendly | motivational | soft
        coaching_mode — soft | standard | active
        preferred_checkin_time — время check-in в формате HH:MM
        max_daily_nudges — макс nudges в день (0 = не менять)
        focus_areas — приоритетные области через запятую
        """
        async with get_async_session() as session:
            kwargs = {}
            if coach_tone:
                kwargs["coach_tone"] = coach_tone
            if coaching_mode:
                kwargs["coaching_mode"] = coaching_mode
            if preferred_checkin_time:
                kwargs["preferred_checkin_time"] = preferred_checkin_time
            if max_daily_nudges > 0:
                kwargs["max_daily_nudges"] = max_daily_nudges
            if focus_areas:
                kwargs["focus_areas"] = [a.strip() for a in focus_areas.split(",")]
            if not kwargs:
                return "Нет изменений."
            profile = await cs.update_profile(session, user_id, **kwargs)
            await session.commit()
            return f"✅ Профиль коуча обновлён: {', '.join(f'{k}={v}' for k, v in kwargs.items())}"

    # ═══════════════════════════════════════════════════════════════════════
    # ORCHESTRATION — действия в других модулях
    # ═══════════════════════════════════════════════════════════════════════

    @tool
    async def orchestrate_create_task_from_milestone(
        milestone_id: int,
        due_date: str = "",
    ) -> str:
        """
        Создать задачу в Tasks-модуле из этапа цели.
        Требует подтверждения пользователя.
        milestone_id — ID этапа
        due_date — дедлайн YYYY-MM-DD
        """
        async with get_async_session() as session:
            from sqlalchemy import select
            from db.models import GoalMilestone
            result = await session.execute(
                select(GoalMilestone).where(GoalMilestone.id == milestone_id)
            )
            milestone = result.scalar_one_or_none()
            if not milestone:
                return f"Этап #{milestone_id} не найден."
            action = await cs.create_orchestration_action(
                session, user_id,
                action_type="create_task",
                target_module="tasks",
                payload={
                    "title": milestone.title,
                    "due_date": due_date or str(milestone.due_date) if milestone.due_date else None,
                    "source_milestone_id": milestone_id,
                }
            )
            await session.commit()
            return (
                f"📋 Предлагаю создать задачу из этапа:\n"
                f"«{milestone.title}»\n"
                f"Подтвердить? (action_id: {action.id})"
            )

    @tool
    async def orchestrate_create_calendar_event(
        title: str,
        date_str: str,
        time_str: str = "",
        duration_min: int = 60,
    ) -> str:
        """
        Создать событие в Calendar из coaching-плана.
        Требует подтверждения пользователя.
        title — название события
        date_str — дата YYYY-MM-DD
        time_str — время HH:MM (необязательно)
        duration_min — продолжительность в минутах
        """
        async with get_async_session() as session:
            action = await cs.create_orchestration_action(
                session, user_id,
                action_type="create_event",
                target_module="calendar",
                payload={
                    "title": title,
                    "date": date_str,
                    "time": time_str,
                    "duration_min": duration_min,
                }
            )
            await session.commit()
            time_info = f" в {time_str}" if time_str else ""
            return (
                f"📅 Предлагаю создать событие:\n"
                f"«{title}» — {date_str}{time_info} ({duration_min} мин)\n"
                f"Подтвердить? (action_id: {action.id})"
            )

    @tool
    async def orchestrate_update_reminder(
        title: str,
        time_str: str,
        days_of_week: str = "daily",
    ) -> str:
        """
        Создать/обновить напоминание через Reminders-модуль.
        title — текст напоминания
        time_str — время HH:MM
        days_of_week — daily | weekdays | weekends или конкретные дни через запятую
        """
        async with get_async_session() as session:
            action = await cs.create_orchestration_action(
                session, user_id,
                action_type="update_reminder",
                target_module="reminders",
                payload={
                    "title": title,
                    "time": time_str,
                    "days": days_of_week,
                }
            )
            await session.commit()
            return (
                f"🔔 Предлагаю настроить напоминание:\n"
                f"«{title}» в {time_str} ({days_of_week})\n"
                f"Подтвердить? (action_id: {action.id})"
            )

    return [
        # Goals
        goal_list, goal_create, goal_update, goal_update_progress,
        goal_freeze, goal_resume, goal_archive, goal_restart, goal_generate_plan,
        # Milestones
        goal_add_milestone, goal_complete_milestone, goal_show_milestones,
        # Habits
        habit_list, habit_create, habit_log, habit_log_miss,
        habit_pause, habit_resume, habit_adjust_frequency, habit_archive,
        habit_template_list, coaching_template_apply,
        # Check-in & Review
        coaching_checkin_create, coaching_review_generate,
        coaching_next_step_suggest, coaching_plan_generate,
        # Insights
        coaching_insight_get,
        # Memory
        coaching_memory_get, coaching_memory_update,
        # Drafts
        coaching_draft_create, coaching_draft_update,
        coaching_draft_get, coaching_draft_confirm,
        # Recommendations
        coaching_recommendations_get,
        # Onboarding & Profile
        coaching_onboarding_get_state, coaching_onboarding_complete_step,
        coaching_profile_update,
        # Orchestration
        orchestrate_create_task_from_milestone,
        orchestrate_create_calendar_event,
        orchestrate_update_reminder,
    ]
