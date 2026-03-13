"""
LangChain @tool для фитнес-модуля.
user_id передаётся через замыкание при создании инструментов.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from langchain.tools import tool

from config import DEFAULT_TZ
from db import fitness_storage as fs


def make_fitness_tools(user_id: int) -> list:
    """Создаёт набор фитнес-инструментов, привязанных к user_id."""

    # ── Поиск упражнений ─────────────────────────────────────────────────

    @tool
    async def exercise_search(
        query: str,
        category: str = "",
        muscle_group: str = "",
    ) -> str:
        """Найти упражнение в базе по названию или алиасу.
        query — текст поиска (например 'жим', 'присед', 'бег')
        category — фильтр: strength | cardio | flexibility | home (необязательно)
        muscle_group — фильтр: chest | back | legs | shoulders | biceps | triceps | core | full_body (необязательно)
        """
        results = await fs.search_exercises(
            query=query,
            category=category or None,
            muscle_group=muscle_group or None,
            limit=8,
        )
        if not results:
            return f"Упражнение '{query}' не найдено в базе."

        # Формируем компактный список
        lines = [f"Найдено {len(results)} упражнений:"]
        for ex in results:
            lines.append(
                f"  #{ex['id']} {ex['name']} ({ex['muscle_group']}, {ex['equipment']})"
            )
        return "\n".join(lines)

    # ── Быстрое логирование тренировки ───────────────────────────────────

    @tool
    async def workout_log(
        exercises_json: str,
        workout_type: str = "strength",
        name: str = "",
    ) -> str:
        """Залогировать тренировку целиком одним вызовом.
        exercises_json — JSON-массив:
        [{"exercise_id": 1, "sets": [{"reps": 8, "weight_kg": 80}, {"reps": 8, "weight_kg": 80}]}]
        Для кардио: [{"exercise_id": 55, "sets": [{"duration_sec": 1800, "distance_m": 5000}]}]
        workout_type — strength | cardio | home | functional | stretching
        name — название тренировки (необязательно)
        """
        try:
            exercises = json.loads(exercises_json)
            if not isinstance(exercises, list) or len(exercises) == 0:
                return "Ошибка: нужен непустой JSON-массив упражнений."

            result = await fs.quick_log_workout(
                user_id=user_id,
                exercises=exercises,
                workout_type=workout_type,
                name=name,
            )

            # Формируем ответ
            lines = [f"✅ Тренировка записана (ID: {result['id']})"]
            if result.get("name"):
                lines[0] += f" — {result['name']}"

            # Считаем подходы
            sets_count = len(result.get("sets", []))
            lines.append(f"📊 Подходов: {sets_count}")
            if result.get("total_volume_kg"):
                lines.append(f"💪 Объём: {result['total_volume_kg']} кг")

            # Проверяем ЛР для каждого упражнения
            pr_messages = []
            for ex_data in exercises:
                ex_id = ex_data["exercise_id"]
                for set_data in ex_data.get("sets", []):
                    wt = set_data.get("weight_kg")
                    reps = set_data.get("reps")
                    if wt:
                        pr = await fs.check_and_update_pr(
                            user_id=user_id,
                            exercise_id=ex_id,
                            weight_kg=wt,
                            reps=reps,
                            session_id=result["id"],
                        )
                        if pr:
                            pr_messages.append(f"🏆 Новый рекорд! {wt} кг")
            if pr_messages:
                lines.extend(pr_messages)

            return "\n".join(lines)
        except json.JSONDecodeError:
            return "Ошибка: некорректный JSON в exercises_json."
        except Exception as e:
            return f"Ошибка при сохранении тренировки: {e}"

    # ── Повтор тренировки ────────────────────────────────────────────────

    @tool
    async def workout_repeat(session_id: int) -> str:
        """Повторить предыдущую тренировку по ID сессии.
        session_id — ID тренировки для повторения
        """
        result = await fs.repeat_workout(user_id=user_id, source_session_id=session_id)
        if not result:
            return f"Тренировка #{session_id} не найдена."

        sets_count = len(result.get("sets", []))
        vol = result.get("total_volume_kg", 0)
        return (
            f"✅ Тренировка повторена (ID: {result['id']})\n"
            f"📊 Подходов: {sets_count}"
            + (f" · Объём: {vol} кг" if vol else "")
        )

    # ── Статистика тренировок ────────────────────────────────────────────

    @tool
    async def workout_stats(days: int = 30) -> str:
        """Показать статистику тренировок за указанный период.
        days — за сколько дней показать статистику (по умолчанию 30)
        """
        stats = await fs.get_workout_stats(user_id=user_id, days=days)

        lines = [f"📈 Статистика за {stats['period_days']} дней:"]
        lines.append(f"  🏋 Тренировок: {stats['total_sessions']}")
        if stats["total_volume_kg"]:
            lines.append(f"  💪 Общий объём: {stats['total_volume_kg']} кг")
        if stats["total_time_min"]:
            lines.append(f"  ⏱ Общее время: {int(stats['total_time_min'])} мин")
        if stats["total_calories"]:
            lines.append(f"  🔥 Сожжено: {int(stats['total_calories'])} ккал")
        if stats["avg_mood"]:
            lines.append(f"  😊 Среднее настроение: {stats['avg_mood']}/5")
        if stats["current_streak_days"]:
            lines.append(f"  🔥 Streak: {stats['current_streak_days']} дней подряд")

        if stats["top_exercises"]:
            lines.append("  📌 Топ упражнений:")
            for ex in stats["top_exercises"]:
                lines.append(f"    {ex['name']} — {ex['sets_count']} подходов")

        return "\n".join(lines)

    # ── История тренировок ───────────────────────────────────────────────

    @tool
    async def workout_history(days: int = 7) -> str:
        """Показать список тренировок за последние дни.
        days — за сколько дней показать историю (по умолчанию 7)
        """
        sessions = await fs.get_sessions(user_id=user_id, days=days, limit=10)
        if not sessions:
            return f"За последние {days} дней тренировок не найдено."

        lines = [f"📋 Тренировки за {days} дней:"]
        for s in sessions:
            dt = s["started_at"][:10] if s.get("started_at") else "?"
            name = s.get("name") or s.get("workout_type", "")
            vol = s.get("total_volume_kg")
            sets_count = len(s.get("sets", []))
            line = f"  #{s['id']} {dt} — {name}"
            if sets_count:
                line += f" ({sets_count} подходов"
                if vol:
                    line += f", {vol} кг"
                line += ")"
            lines.append(line)
        return "\n".join(lines)

    # ── Замеры тела ──────────────────────────────────────────────────────

    @tool
    async def body_metric_log(
        weight_kg: float = 0,
        body_fat_pct: float = 0,
        chest_cm: float = 0,
        waist_cm: float = 0,
        hips_cm: float = 0,
        bicep_cm: float = 0,
        thigh_cm: float = 0,
        energy_level: int = 0,
        sleep_hours: float = 0,
        notes: str = "",
    ) -> str:
        """Записать замер тела / показатели самочувствия.
        Все параметры необязательные — передавай только то, что сказал пользователь.
        weight_kg — вес в кг
        body_fat_pct — процент жира
        chest_cm, waist_cm, hips_cm, bicep_cm, thigh_cm — обхваты в см
        energy_level — уровень энергии 1-5
        sleep_hours — часы сна
        notes — заметки
        """
        # Собираем только ненулевые значения
        kwargs = {}
        if weight_kg: kwargs["weight_kg"] = weight_kg
        if body_fat_pct: kwargs["body_fat_pct"] = body_fat_pct
        if chest_cm: kwargs["chest_cm"] = chest_cm
        if waist_cm: kwargs["waist_cm"] = waist_cm
        if hips_cm: kwargs["hips_cm"] = hips_cm
        if bicep_cm: kwargs["bicep_cm"] = bicep_cm
        if thigh_cm: kwargs["thigh_cm"] = thigh_cm
        if energy_level: kwargs["energy_level"] = energy_level
        if sleep_hours: kwargs["sleep_hours"] = sleep_hours
        if notes: kwargs["notes"] = notes

        if not kwargs:
            return "Нужно указать хотя бы один показатель."

        result = await fs.log_body_metric(user_id=user_id, **kwargs)

        lines = ["✅ Замер записан:"]
        if result.get("weight_kg"):
            lines.append(f"  ⚖️ Вес: {result['weight_kg']} кг")
        if result.get("body_fat_pct"):
            lines.append(f"  📉 Жир: {result['body_fat_pct']}%")
        if result.get("waist_cm"):
            lines.append(f"  📏 Талия: {result['waist_cm']} см")
        if result.get("energy_level"):
            lines.append(f"  ⚡ Энергия: {result['energy_level']}/5")
        if result.get("sleep_hours"):
            lines.append(f"  😴 Сон: {result['sleep_hours']} ч")
        return "\n".join(lines)

    # ── Лог активности ───────────────────────────────────────────────────

    @tool
    async def activity_log(
        activity_type: str,
        value: float,
        unit: str,
        duration_min: int = 0,
        calories_burned: float = 0,
        notes: str = "",
    ) -> str:
        """Записать физическую активность (бег, шаги, вело, плавание).
        activity_type — тип: run | walk | cycling | swimming | steps | other
        value — значение (км, шаги, минуты)
        unit — единица: km | m | steps | min
        duration_min — продолжительность в минутах (необязательно)
        calories_burned — сожжённые калории (необязательно)
        """
        result = await fs.log_activity(
            user_id=user_id,
            activity_type=activity_type,
            value=value,
            unit=unit,
            duration_min=duration_min or None,
            calories_burned=calories_burned or None,
            notes=notes,
        )

        # Формируем сообщение
        type_emoji = {
            "run": "🏃", "walk": "🚶", "cycling": "🚴",
            "swimming": "🏊", "steps": "👣",
        }
        emoji = type_emoji.get(activity_type, "🏃")
        line = f"✅ {emoji} {activity_type}: {value} {unit}"
        if result.get("duration_min"):
            line += f" за {result['duration_min']} мин"
        if result.get("calories_burned"):
            line += f" · {int(result['calories_burned'])} ккал"
        return line

    # ── Фитнес-цель ──────────────────────────────────────────────────────

    @tool
    async def fitness_goal_set(
        goal_type: str = "maintain",
        workouts_per_week: int = 3,
        preferred_duration_min: int = 60,
        training_location: str = "gym",
        experience_level: str = "intermediate",
    ) -> str:
        """Установить фитнес-цель пользователя.
        goal_type — цель: lose_weight | gain_muscle | maintain | endurance | strength
        workouts_per_week — тренировок в неделю
        preferred_duration_min — длительность тренировки в минутах
        training_location — где: gym | home | outdoor | mixed
        experience_level — уровень: beginner | intermediate | advanced
        """
        result = await fs.set_fitness_goal(
            user_id=user_id,
            goal_type=goal_type,
            workouts_per_week=workouts_per_week,
            preferred_duration_min=preferred_duration_min,
            training_location=training_location,
            experience_level=experience_level,
        )

        goal_names = {
            "lose_weight": "Похудение",
            "gain_muscle": "Набор массы",
            "maintain": "Поддержание формы",
            "endurance": "Выносливость",
            "strength": "Сила",
        }
        return (
            f"✅ Цель обновлена:\n"
            f"  🎯 {goal_names.get(result['goal_type'], result['goal_type'])}\n"
            f"  📅 {result['workouts_per_week']}x в неделю по {result['preferred_duration_min']} мин\n"
            f"  📍 {result['training_location']}\n"
            f"  💪 Уровень: {result['experience_level']}"
        )


    @tool
    async def program_info() -> str:
        """Показать активную программу тренировок и следующую тренировку.
        Вызывай, когда пользователь спрашивает о программе, что тренировать, какая следующая тренировка."""
        from db import fitness_storage as fs_mod
        # Активная программа
        program = await fs_mod.get_active_program(user_id)
        if not program:
            return "📋 У тебя нет активной программы тренировок. Хочешь сгенерировать?"

        # Следующая тренировка
        next_w = await fs_mod.get_next_workout(user_id)

        lines = [
            f"📋 Программа: {program['name']}",
            f"  🎯 {program.get('goal_type', '')} | {program['difficulty']} | {program['location']}",
            f"  📅 {program['days_per_week']} дней/нед",
            "",
        ]
        # Дни программы
        for day in program.get("days", []):
            lines.append(f"  День {day['day_number']}: {day['day_name']}")

        if next_w:
            lines.append("")
            lines.append(f"▶️ Следующая: День {next_w['day_number']} — {next_w['day_name']}")
            lines.append(f"  Выполнено тренировок: {next_w['completed_workouts']}")

        return "\n".join(lines)

    @tool
    async def next_workout_tool() -> str:
        """Показать следующую тренировку по активной программе.
        Вызывай, когда пользователь спрашивает что тренировать сегодня, какая следующая тренировка."""
        from db import fitness_storage as fs_mod
        result = await fs_mod.get_next_workout(user_id)
        if not result:
            return "📋 Нет активной программы. Хочешь сгенерировать программу тренировок?"

        return (
            f"▶️ Следующая тренировка:\n"
            f"  📋 Программа: {result['program_name']}\n"
            f"  📅 День {result['day_number']}/{result['total_days']}: {result['day_name']}\n"
            f"  ✅ Выполнено тренировок: {result['completed_workouts']}"
        )

    # Возвращаем все инструменты
    return [
        exercise_search,
        workout_log,
        workout_repeat,
        workout_stats,
        workout_history,
        body_metric_log,
        activity_log,
        fitness_goal_set,
        program_info,
        next_workout_tool,
    ]
