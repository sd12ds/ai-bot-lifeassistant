"""
CRUD-операции для фитнес-модуля.
Работает через SQLAlchemy async (PostgreSQL).
"""
from __future__ import annotations

import json
from datetime import datetime, date, timedelta, time
from typing import Optional

from sqlalchemy import select, and_, func, or_, delete, update, desc, cast, String, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import DEFAULT_TZ
from db.models import (
    ExerciseLibrary, WorkoutSession, WorkoutSet, BodyMetric,
    FitnessGoal, PersonalRecord, ActivityLog,
)
from db.session import AsyncSessionLocal


# ── Вспомогательные конвертеры ────────────────────────────────────────────────

def _exercise_to_dict(e: ExerciseLibrary) -> dict:
    """Конвертирует ExerciseLibrary ORM → dict."""
    return {
        "id": e.id,
        "name": e.name,
        "category": e.category,
        "muscle_group": e.muscle_group,
        "equipment": e.equipment,
        "difficulty": e.difficulty,
        "is_compound": e.is_compound,
        "instructions": e.instructions,
        "aliases": e.aliases or [],
    }


def _set_to_dict(s: WorkoutSet) -> dict:
    """Конвертирует WorkoutSet ORM → dict с названием упражнения."""
    return {
        "id": s.id,
        "exercise_id": s.exercise_id,
        "exercise_name": s.exercise.name if s.exercise else None,  # название упражнения из справочника
        "set_num": s.set_num,
        "reps": s.reps,
        "weight_kg": s.weight_kg,
        "duration_sec": s.duration_sec,
        "distance_m": s.distance_m,
        "pace_sec_per_km": s.pace_sec_per_km,
        "set_type": s.set_type,
        "is_personal_record": s.is_personal_record,
    }


def _session_to_dict(ws: WorkoutSession, include_sets: bool = True) -> dict:
    """Конвертирует WorkoutSession ORM → dict с подходами."""
    result = {
        "id": ws.id,
        "name": ws.name,
        "workout_type": ws.workout_type,
        "started_at": ws.started_at.isoformat() if ws.started_at else None,
        "ended_at": ws.ended_at.isoformat() if ws.ended_at else None,
        "total_volume_kg": ws.total_volume_kg,
        "total_duration_sec": ws.total_duration_sec,
        "calories_burned": ws.calories_burned,
        "mood_before": ws.mood_before,
        "mood_after": ws.mood_after,
        "notes": ws.notes,
        "created_at": ws.created_at.isoformat() if ws.created_at else None,
    }
    # Всегда включаем sets (пустой список, если подходов нет)
    if include_sets:
        result["sets"] = [_set_to_dict(s) for s in ws.sets] if ws.sets else []
    return result


def _body_metric_to_dict(bm: BodyMetric) -> dict:
    """Конвертирует BodyMetric ORM → dict."""
    return {
        "id": bm.id,
        "weight_kg": bm.weight_kg,
        "body_fat_pct": bm.body_fat_pct,
        "muscle_mass_kg": bm.muscle_mass_kg,
        "chest_cm": bm.chest_cm,
        "waist_cm": bm.waist_cm,
        "hips_cm": bm.hips_cm,
        "bicep_cm": bm.bicep_cm,
        "thigh_cm": bm.thigh_cm,
        "energy_level": bm.energy_level,
        "sleep_hours": bm.sleep_hours,
        "recovery_rating": bm.recovery_rating,
        "notes": bm.notes,
        "photo_file_id": bm.photo_file_id,
        "logged_at": bm.logged_at.isoformat() if bm.logged_at else None,
    }


def _day_range(target_date: date) -> tuple[datetime, datetime]:
    """Возвращает timezone-aware границы дня для запросов."""
    day_start = datetime.combine(target_date, time.min, tzinfo=DEFAULT_TZ)
    day_end = day_start + timedelta(days=1)
    return day_start, day_end


# ── Поиск упражнений ─────────────────────────────────────────────────────────

async def search_exercises(
    query: str,
    category: str | None = None,
    muscle_group: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    Поиск упражнений по названию и алиасам.
    Ищет по ILIKE в name + проверяет JSONB aliases.
    """
    async with AsyncSessionLocal() as session:
        q_lower = query.lower().strip()
        conditions = []
        # Текстовый фильтр — только при непустом запросе
        if q_lower:
            conditions.append(
                or_(
                    ExerciseLibrary.name.ilike(f"%{q_lower}%"),
                    # Поиск в JSONB aliases: приводим к текстовому виду и ищем подстроку
                    cast(ExerciseLibrary.aliases, String).ilike(f"%{q_lower}%"),
                )
            )
        # Дополнительные фильтры по категории и группе мышц
        if category:
            conditions.append(ExerciseLibrary.category == category)
        if muscle_group:
            conditions.append(ExerciseLibrary.muscle_group == muscle_group)

        stmt = (
            select(ExerciseLibrary)
            .where(and_(*conditions))
            .order_by(ExerciseLibrary.name)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [_exercise_to_dict(e) for e in result.scalars().all()]


async def get_exercise_by_id(exercise_id: int) -> dict | None:
    """Получить упражнение по ID."""
    async with AsyncSessionLocal() as session:
        ex = await session.get(ExerciseLibrary, exercise_id)
        return _exercise_to_dict(ex) if ex else None


# ── Тренировки (sessions) ────────────────────────────────────────────────────

async def start_workout(
    user_id: int,
    name: str = "",
    workout_type: str = "strength",
    mood_before: int | None = None,
) -> dict:
    """Начать новую тренировку (создаёт сессию с started_at = now)."""
    async with AsyncSessionLocal() as session:
        ws = WorkoutSession(
            user_id=user_id,
            name=name or f"Тренировка {datetime.now(DEFAULT_TZ).strftime('%d.%m')}",
            workout_type=workout_type,
            started_at=datetime.now(DEFAULT_TZ),
            mood_before=mood_before,
        )
        session.add(ws)
        await session.commit()
        await session.refresh(ws)
        return _session_to_dict(ws, include_sets=False)


async def finish_workout(
    session_id: int,
    mood_after: int | None = None,
    notes: str = "",
) -> dict | None:
    """Завершить тренировку: ставит ended_at, считает total_volume, duration."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(WorkoutSession)
            .options(selectinload(WorkoutSession.sets).selectinload(WorkoutSet.exercise))
            .where(WorkoutSession.id == session_id)
        )
        result = await session.execute(stmt)
        ws = result.scalar_one_or_none()
        if not ws:
            return None

        now = datetime.now(DEFAULT_TZ)
        ws.ended_at = now
        if mood_after:
            ws.mood_after = mood_after
        if notes:
            ws.notes = notes

        # Считаем суммарный объём (для силовых: повторы × вес)
        total_vol = 0.0
        for s in (ws.sets or []):
            if s.weight_kg and s.reps:
                total_vol += s.weight_kg * s.reps
        ws.total_volume_kg = round(total_vol, 1) if total_vol else None

        # Считаем продолжительность
        if ws.started_at:
            ws.total_duration_sec = int((now - ws.started_at).total_seconds())

        # Авто-генерируем название из упражнений если оставалось дефолтным "Тренировка XX.XX"
        if ws.name and ws.name.startswith("Тренировка ") and ws.sets:
            # Уникальные упражнения в порядке первого появления
            seen_ex: dict[int, str] = {}
            for s in ws.sets:
                if s.exercise_id not in seen_ex and s.exercise:
                    seen_ex[s.exercise_id] = s.exercise.name
            ex_names = list(seen_ex.values())
            if ex_names:
                total_ex = len(ex_names)
                if total_ex == 1:
                    ws.name = ex_names[0]
                elif total_ex == 2:
                    ws.name = f"{ex_names[0]} + {ex_names[1]}"
                else:
                    extra = total_ex - 2
                    ws.name = f"{ex_names[0]} + {ex_names[1]} (+{extra})"

        await session.commit()
        await session.refresh(ws)
        return _session_to_dict(ws)


async def add_set(
    session_id: int,
    exercise_id: int,
    reps: int | None = None,
    weight_kg: float | None = None,
    duration_sec: int | None = None,
    distance_m: float | None = None,
    pace_sec_per_km: int | None = None,
    set_type: str = "working",
) -> dict:
    """Добавить подход к тренировке."""
    async with AsyncSessionLocal() as session:
        # Определяем номер подхода
        count_stmt = select(func.count()).where(
            and_(
                WorkoutSet.session_id == session_id,
                WorkoutSet.exercise_id == exercise_id,
            )
        )
        count_res = await session.execute(count_stmt)
        set_num = (count_res.scalar() or 0) + 1

        ws = WorkoutSet(
            session_id=session_id,
            exercise_id=exercise_id,
            set_num=set_num,
            reps=reps,
            weight_kg=weight_kg,
            duration_sec=duration_sec,
            distance_m=distance_m,
            pace_sec_per_km=pace_sec_per_km,
            set_type=set_type,
        )
        session.add(ws)
        await session.commit()
        await session.refresh(ws)
        return _set_to_dict(ws)


async def quick_log_workout(
    user_id: int,
    exercises: list[dict],
    workout_type: str = "strength",
    name: str = "",
    started_at: "datetime | None" = None,
) -> dict:
    """
    Быстрое логирование тренировки одним вызовом.
    exercises: [{"exercise_id": 1, "sets": [{"reps": 8, "weight_kg": 80}, ...]}]
    Создаёт сессию + подходы + сразу завершает.
    """
    async with AsyncSessionLocal() as session:
        now = datetime.now(DEFAULT_TZ)
        # Если передано конкретное время начала — используем его
        effective_start = started_at if started_at is not None else now

        # Генерируем информативное название из первых 2 упражнений если не задано
        auto_name = name
        if not auto_name and exercises:
            # Дедупликация exercise_id с сохранением порядка
            seen_ids: set[int] = set()
            ordered_ids: list[int] = []
            for ex in exercises:
                eid = ex.get("exercise_id")
                if eid and eid not in seen_ids:
                    seen_ids.add(eid)
                    ordered_ids.append(eid)
            if ordered_ids:
                from db.models import ExerciseLibrary
                ex_rows = await session.execute(
                    select(ExerciseLibrary.id, ExerciseLibrary.name)
                    .where(ExerciseLibrary.id.in_(ordered_ids))
                )
                id_to_name = {row[0]: row[1] for row in ex_rows.fetchall()}
                # Имена в порядке как в запросе
                ex_names = [id_to_name[eid] for eid in ordered_ids if eid in id_to_name]
                if ex_names:
                    total_ex = len(ordered_ids)
                    if total_ex == 1:
                        auto_name = ex_names[0]
                    elif total_ex == 2:
                        auto_name = f"{ex_names[0]} + {ex_names[1]}"
                    else:
                        # Первые два + количество оставшихся
                        extra = total_ex - 2
                        auto_name = f"{ex_names[0]} + {ex_names[1]} (+{extra})"

        ws = WorkoutSession(
            user_id=user_id,
            name=auto_name or f"Тренировка {effective_start.strftime('%d.%m')}",
            workout_type=workout_type,
            started_at=effective_start,
            ended_at=effective_start,
        )
        session.add(ws)
        await session.flush()  # Получаем ws.id

        total_vol = 0.0
        for ex_data in exercises:
            ex_id = ex_data["exercise_id"]
            for i, set_data in enumerate(ex_data.get("sets", []), 1):
                wset = WorkoutSet(
                    session_id=ws.id,
                    exercise_id=ex_id,
                    set_num=i,
                    reps=set_data.get("reps"),
                    weight_kg=set_data.get("weight_kg"),
                    duration_sec=set_data.get("duration_sec"),
                    distance_m=set_data.get("distance_m"),
                    pace_sec_per_km=set_data.get("pace_sec_per_km"),
                    set_type=set_data.get("set_type", "working"),
                )
                session.add(wset)
                # Считаем объём
                if wset.weight_kg and wset.reps:
                    total_vol += wset.weight_kg * wset.reps

        ws.total_volume_kg = round(total_vol, 1) if total_vol else None
        await session.commit()

        # Перечитываем с подходами
        stmt = (
            select(WorkoutSession)
            .options(selectinload(WorkoutSession.sets).selectinload(WorkoutSet.exercise))
            .where(WorkoutSession.id == ws.id)
        )
        result = await session.execute(stmt)
        ws = result.scalar_one()
        return _session_to_dict(ws)


async def get_sessions(
    user_id: int,
    days: int = 7,
    limit: int = 10,
) -> list[dict]:
    """Получить тренировки за последние N дней."""
    async with AsyncSessionLocal() as session:
        since = datetime.now(DEFAULT_TZ) - timedelta(days=days)
        stmt = (
            select(WorkoutSession)
            .options(selectinload(WorkoutSession.sets).selectinload(WorkoutSet.exercise))
            .where(and_(
                WorkoutSession.user_id == user_id,
                WorkoutSession.created_at >= since,
            ))
            .order_by(desc(WorkoutSession.created_at))
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [_session_to_dict(ws) for ws in result.scalars().all()]


async def get_active_workout(user_id: int) -> dict | None:
    """Получить текущую незавершённую тренировку пользователя."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(WorkoutSession)
            .options(selectinload(WorkoutSession.sets).selectinload(WorkoutSet.exercise))
            .where(and_(
                WorkoutSession.user_id == user_id,
                WorkoutSession.ended_at.is_(None),
                WorkoutSession.started_at.isnot(None),
            ))
            .order_by(desc(WorkoutSession.created_at))
            .limit(1)
        )
        result = await session.execute(stmt)
        ws = result.scalar_one_or_none()
        return _session_to_dict(ws) if ws else None


# ── Повтор тренировки ────────────────────────────────────────────────────────

async def repeat_workout(user_id: int, source_session_id: int) -> dict | None:
    """Повторить тренировку — создать новую на основе предыдущей."""
    async with AsyncSessionLocal() as session:
        # Загружаем оригинальную сессию с подходами
        stmt = (
            select(WorkoutSession)
            .options(selectinload(WorkoutSession.sets).selectinload(WorkoutSet.exercise))
            .where(WorkoutSession.id == source_session_id)
        )
        result = await session.execute(stmt)
        original = result.scalar_one_or_none()
        if not original:
            return None

        now = datetime.now(DEFAULT_TZ)

        # Используем имя оригинала, но если оно дефолтное — генерируем из упражнений
        repeat_name = original.name
        if not repeat_name or repeat_name.startswith("Тренировка "):
            seen_ex: dict[int, str] = {}
            for s in (original.sets or []):
                if s.exercise_id not in seen_ex and s.exercise:
                    seen_ex[s.exercise_id] = s.exercise.name
            ex_names = list(seen_ex.values())
            if ex_names:
                total_ex = len(ex_names)
                if total_ex == 1:
                    repeat_name = ex_names[0]
                elif total_ex == 2:
                    repeat_name = f"{ex_names[0]} + {ex_names[1]}"
                else:
                    repeat_name = f"{ex_names[0]} + {ex_names[1]} (+{total_ex - 2})"
            else:
                repeat_name = f"Тренировка {now.strftime('%d.%m')}"

        new_ws = WorkoutSession(
            user_id=user_id,
            name=repeat_name,
            workout_type=original.workout_type,
            started_at=now,
            ended_at=now,
        )
        session.add(new_ws)
        await session.flush()

        total_vol = 0.0
        for s in (original.sets or []):
            new_set = WorkoutSet(
                session_id=new_ws.id,
                exercise_id=s.exercise_id,
                set_num=s.set_num,
                reps=s.reps,
                weight_kg=s.weight_kg,
                duration_sec=s.duration_sec,
                distance_m=s.distance_m,
                set_type=s.set_type,
            )
            session.add(new_set)
            if new_set.weight_kg and new_set.reps:
                total_vol += new_set.weight_kg * new_set.reps

        new_ws.total_volume_kg = round(total_vol, 1) if total_vol else None
        await session.commit()

        # Перечитываем
        stmt2 = (
            select(WorkoutSession)
            .options(selectinload(WorkoutSession.sets).selectinload(WorkoutSet.exercise))
            .where(WorkoutSession.id == new_ws.id)
        )
        res2 = await session.execute(stmt2)
        return _session_to_dict(res2.scalar_one())


# ── Замеры тела (body metrics) ────────────────────────────────────────────────

async def log_body_metric(user_id: int, **kwargs) -> dict:
    """
    Записать замер тела.
    kwargs: weight_kg, body_fat_pct, muscle_mass_kg, chest_cm, waist_cm,
            hips_cm, bicep_cm, thigh_cm, energy_level, sleep_hours,
            recovery_rating, notes, photo_file_id
    """
    async with AsyncSessionLocal() as session:
        bm = BodyMetric(user_id=user_id, **kwargs)
        session.add(bm)
        await session.commit()
        await session.refresh(bm)
        return _body_metric_to_dict(bm)


async def get_body_metrics(
    user_id: int,
    days: int = 30,
    limit: int = 20,
) -> list[dict]:
    """Получить замеры тела за последние N дней."""
    async with AsyncSessionLocal() as session:
        since = datetime.now(DEFAULT_TZ) - timedelta(days=days)
        stmt = (
            select(BodyMetric)
            .where(and_(
                BodyMetric.user_id == user_id,
                BodyMetric.logged_at >= since,
            ))
            .order_by(desc(BodyMetric.logged_at))
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [_body_metric_to_dict(bm) for bm in result.scalars().all()]


async def update_body_metric_photo(
    user_id: int, metric_id: int, photo_file_id: str | None
) -> None:
    """Обновить photo_file_id в записи BodyMetric."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(BodyMetric)
            .where(and_(
                BodyMetric.id == metric_id,
                BodyMetric.user_id == user_id,
            ))
        )
        result = await session.execute(stmt)
        bm = result.scalar_one_or_none()
        if bm:
            bm.photo_file_id = photo_file_id
            await session.commit()


# ── Лог активности ───────────────────────────────────────────────────────────

async def log_activity(
    user_id: int,
    activity_type: str,
    value: float,
    unit: str,
    duration_min: int | None = None,
    calories_burned: float | None = None,
    notes: str = "",
    logged_at: "datetime | None" = None,
) -> dict:
    """Записать активность (бег, шаги, вело и т.д.).
    logged_at — если передан, используется вместо NOW() (для указания времени вручную).
    """
    async with AsyncSessionLocal() as session:
        al = ActivityLog(
            user_id=user_id,
            activity_type=activity_type,
            value=value,
            unit=unit,
            duration_min=duration_min,
            calories_burned=calories_burned,
            notes=notes,
        )
        # Если передано конкретное время — ставим его явно
        if logged_at is not None:
            al.logged_at = logged_at
        session.add(al)
        await session.commit()
        await session.refresh(al)
        return {
            "id": al.id,
            "activity_type": al.activity_type,
            "value": al.value,
            "unit": al.unit,
            "duration_min": al.duration_min,
            "calories_burned": al.calories_burned,
            "logged_at": al.logged_at.isoformat() if al.logged_at else None,
        }


async def get_activities(
    user_id: int,
    days: int = 7,
    limit: int = 20,
) -> list[dict]:
    """Получить список активностей пользователя за последние N дней."""
    from datetime import datetime, timedelta, timezone
    async with AsyncSessionLocal() as session:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await session.execute(
            select(ActivityLog)
            .where(ActivityLog.user_id == user_id, ActivityLog.logged_at >= cutoff)
            .order_by(ActivityLog.logged_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "activity_type": r.activity_type,
                "value": r.value,
                "unit": r.unit,
                "duration_min": r.duration_min,
                "calories_burned": r.calories_burned,
                "notes": r.notes,
                "logged_at": r.logged_at.isoformat() if r.logged_at else None,
            }
            for r in rows
        ]


async def update_activity(
    activity_id: int,
    user_id: int,
    **kwargs,
) -> dict | None:
    """Обновить активность по id. Обновляет только переданные поля.
    Допустимые поля: activity_type, value, unit, duration_min, calories_burned, notes, logged_at.
    Возвращает обновлённый dict или None если не найдено.
    """
    # Фильтруем допустимые поля
    allowed = {"activity_type", "value", "unit", "duration_min", "calories_burned", "notes", "logged_at"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return None
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ActivityLog).where(
                ActivityLog.id == activity_id,
                ActivityLog.user_id == user_id,  # Защита от чужих записей
            )
        )
        al = result.scalar_one_or_none()
        if not al:
            return None
        # Применяем обновления
        for field, val in updates.items():
            setattr(al, field, val)
        await session.commit()
        await session.refresh(al)
        return {
            "id": al.id,
            "activity_type": al.activity_type,
            "value": al.value,
            "unit": al.unit,
            "duration_min": al.duration_min,
            "calories_burned": al.calories_burned,
            "notes": al.notes,
            "logged_at": al.logged_at.isoformat() if al.logged_at else None,
        }


async def delete_activity(activity_id: int, user_id: int) -> bool:
    """Удалить активность по id. Проверяет user_id. Возвращает True/False."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ActivityLog).where(
                ActivityLog.id == activity_id,
                ActivityLog.user_id == user_id,
            )
        )
        al = result.scalar_one_or_none()
        if not al:
            return False
        await session.delete(al)
        await session.commit()
        return True


# ── Статистика ────────────────────────────────────────────────────────────────

async def get_workout_stats(user_id: int, days: int = 30) -> dict:
    """
    Сводная статистика за период:
    - количество тренировок
    - общий объём (кг)
    - общее время
    - среднее настроение
    - любимые упражнения
    - текущий streak (дни подряд)
    """
    async with AsyncSessionLocal() as session:
        since = datetime.now(DEFAULT_TZ) - timedelta(days=days)

        # Количество тренировок и суммы
        stats_stmt = select(
            func.count(WorkoutSession.id).label("total_sessions"),
            func.sum(WorkoutSession.total_volume_kg).label("total_volume"),
            func.sum(WorkoutSession.total_duration_sec).label("total_time"),
            func.avg(WorkoutSession.mood_after).label("avg_mood"),
            func.sum(WorkoutSession.calories_burned).label("total_calories"),
        ).where(and_(
            WorkoutSession.user_id == user_id,
            WorkoutSession.created_at >= since,
        ))
        stats_res = await session.execute(stats_stmt)
        row = stats_res.one()

        # Самые частые упражнения (top-5)
        top_stmt = (
            select(
                WorkoutSet.exercise_id,
                ExerciseLibrary.name,
                func.count().label("cnt"),
            )
            .join(WorkoutSession, WorkoutSet.session_id == WorkoutSession.id)
            .join(ExerciseLibrary, WorkoutSet.exercise_id == ExerciseLibrary.id)
            .where(and_(
                WorkoutSession.user_id == user_id,
                WorkoutSession.created_at >= since,
            ))
            .group_by(WorkoutSet.exercise_id, ExerciseLibrary.name)
            .order_by(desc("cnt"))
            .limit(5)
        )
        top_res = await session.execute(top_stmt)
        top_exercises = [
            {"exercise_id": r[0], "name": r[1], "sets_count": r[2]}
            for r in top_res.all()
        ]

        # Активности (кардио, растяжка, шаги и пр.) из activity_logs
        act_stmt = select(
            func.count(ActivityLog.id).label("total_activities"),
            # Время: если unit='min' берём value, иначе duration_min
            func.sum(
                case(
                    (ActivityLog.unit == "min", ActivityLog.value),
                    else_=func.coalesce(ActivityLog.duration_min, 0),
                )
            ).label("activity_time"),
            func.sum(func.coalesce(ActivityLog.calories_burned, 0)).label("activity_calories"),
        ).where(and_(
            ActivityLog.user_id == user_id,
            ActivityLog.logged_at >= since,
        ))
        act_res = await session.execute(act_stmt)
        act_row = act_res.one()

        # Streak: подряд дни с тренировками И активностями
        streak = await _calc_streak(session, user_id)

        return {
            "period_days": days,
            "total_sessions": row.total_sessions or 0,
            "total_volume_kg": round(row.total_volume or 0, 1),
            "total_time_min": round((row.total_time or 0) / 60, 0),
            "total_calories": round(row.total_calories or 0, 0),
            "avg_mood": round(row.avg_mood or 0, 1) if row.avg_mood else None,
            "top_exercises": top_exercises,
            "current_streak_days": streak,
            "total_activities": act_row.total_activities or 0,
            "total_activity_time_min": round(float(act_row.activity_time or 0), 0),
            "total_activity_calories": round(float(act_row.activity_calories or 0), 0),
        }


async def _calc_streak(session: AsyncSession, user_id: int) -> int:
    """Вычисляет текущий streak — дни подряд с тренировками ИЛИ активностями."""
    # Получаем уникальные даты тренировок (последние 60 дней)
    since = datetime.now(DEFAULT_TZ) - timedelta(days=60)
    # Даты тренировок
    ws_stmt = (
        select(func.date(WorkoutSession.created_at))
        .where(and_(
            WorkoutSession.user_id == user_id,
            WorkoutSession.created_at >= since,
        ))
        .distinct()
    )
    ws_result = await session.execute(ws_stmt)
    ws_dates = {r[0] for r in ws_result.all()}

    # Даты активностей из activity_logs
    al_stmt = (
        select(func.date(ActivityLog.logged_at))
        .where(and_(
            ActivityLog.user_id == user_id,
            ActivityLog.logged_at >= since,
        ))
        .distinct()
    )
    al_result = await session.execute(al_stmt)
    al_dates = {r[0] for r in al_result.all()}

    # Объединяем даты тренировок и активностей
    dates = sorted(ws_dates | al_dates, reverse=True)

    if not dates:
        return 0

    today = date.today()
    # Если последняя тренировка не сегодня и не вчера — streak = 0
    if dates[0] < today - timedelta(days=1):
        return 0

    streak = 1
    for i in range(1, len(dates)):
        if dates[i] == dates[i - 1] - timedelta(days=1):
            streak += 1
        else:
            break
    return streak


# ── Личные рекорды ────────────────────────────────────────────────────────────

async def check_and_update_pr(
    user_id: int,
    exercise_id: int,
    weight_kg: float | None = None,
    reps: int | None = None,
    session_id: int | None = None,
) -> dict | None:
    """
    Проверяет, является ли текущий результат личным рекордом.
    Если да — обновляет таблицу personal_records и возвращает запись.
    """
    if not weight_kg:
        return None

    async with AsyncSessionLocal() as session:
        # Ищем текущий рекорд по весу
        stmt = select(PersonalRecord).where(and_(
            PersonalRecord.user_id == user_id,
            PersonalRecord.exercise_id == exercise_id,
            PersonalRecord.record_type == "max_weight",
        ))
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing and existing.value >= weight_kg:
            return None  # Не рекорд

        if existing:
            existing.value = weight_kg
            existing.achieved_at = datetime.now(DEFAULT_TZ)
            existing.session_id = session_id
        else:
            pr = PersonalRecord(
                user_id=user_id,
                exercise_id=exercise_id,
                record_type="max_weight",
                value=weight_kg,
                session_id=session_id,
            )
            session.add(pr)

        await session.commit()
        return {
            "exercise_id": exercise_id,
            "record_type": "max_weight",
            "value": weight_kg,
            "is_new_record": True,
        }


async def get_personal_records(user_id: int) -> list[dict]:
    """Получить все личные рекорды пользователя."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(PersonalRecord, ExerciseLibrary.name)
            .join(ExerciseLibrary, PersonalRecord.exercise_id == ExerciseLibrary.id)
            .where(PersonalRecord.user_id == user_id)
            .order_by(ExerciseLibrary.name)
        )
        result = await session.execute(stmt)
        return [
            {
                "exercise": name,
                "record_type": pr.record_type,
                "value": pr.value,
                "achieved_at": pr.achieved_at.isoformat() if pr.achieved_at else None,
            }
            for pr, name in result.all()
        ]


# ── Фитнес-цели ──────────────────────────────────────────────────────────────

async def set_fitness_goal(user_id: int, **kwargs) -> dict:
    """
    Установить / обновить фитнес-цель.
    kwargs: goal_type, workouts_per_week, preferred_duration_min,
            training_location, experience_level, available_equipment
    """
    async with AsyncSessionLocal() as session:
        stmt = select(FitnessGoal).where(FitnessGoal.user_id == user_id)
        result = await session.execute(stmt)
        goal = result.scalar_one_or_none()

        if goal:
            for k, v in kwargs.items():
                if hasattr(goal, k) and v is not None:
                    setattr(goal, k, v)
        else:
            goal = FitnessGoal(user_id=user_id, **kwargs)
            session.add(goal)

        await session.commit()
        await session.refresh(goal)
        return {
            "goal_type": goal.goal_type,
            "workouts_per_week": goal.workouts_per_week,
            "preferred_duration_min": goal.preferred_duration_min,
            "training_location": goal.training_location,
            "experience_level": goal.experience_level,
            "available_equipment": goal.available_equipment or [],
            "target_weight_kg": goal.target_weight_kg,
        }


async def get_fitness_goal(user_id: int) -> dict | None:
    """Получить фитнес-цель пользователя."""
    async with AsyncSessionLocal() as session:
        stmt = select(FitnessGoal).where(FitnessGoal.user_id == user_id)
        result = await session.execute(stmt)
        goal = result.scalar_one_or_none()
        if not goal:
            return None
        return {
            "goal_type": goal.goal_type,
            "workouts_per_week": goal.workouts_per_week,
            "preferred_duration_min": goal.preferred_duration_min,
            "training_location": goal.training_location,
            "experience_level": goal.experience_level,
            "available_equipment": goal.available_equipment or [],
            "target_weight_kg": goal.target_weight_kg,
        }


# ── Прогресс по упражнению ────────────────────────────────────────────────────

async def get_exercise_progress(
    user_id: int,
    exercise_id: int,
    days: int = 90,
) -> list[dict]:
    """
    История рабочего веса/повторений по упражнению за период.
    Возвращает список записей с датой, макс весом и объёмом за сессию.
    """
    async with AsyncSessionLocal() as session:
        since = datetime.now(DEFAULT_TZ) - timedelta(days=days)
        # Получаем сеты для этого упражнения, группируем по сессиям
        stmt = (
            select(
                WorkoutSession.id.label("session_id"),
                func.date(WorkoutSession.created_at).label("dt"),
                func.max(WorkoutSet.weight_kg).label("max_weight"),
                func.sum(WorkoutSet.weight_kg * WorkoutSet.reps).label("volume"),
                func.max(WorkoutSet.reps).label("max_reps"),
            )
            .join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
            .where(and_(
                WorkoutSession.user_id == user_id,
                WorkoutSet.exercise_id == exercise_id,
                WorkoutSession.created_at >= since,
            ))
            .group_by(WorkoutSession.id, func.date(WorkoutSession.created_at))
            .order_by(func.date(WorkoutSession.created_at))
        )
        result = await session.execute(stmt)
        return [
            {
                "date": str(r.dt),
                "max_weight": round(r.max_weight or 0, 1),
                "volume": round(r.volume or 0, 1),
                "max_reps": r.max_reps or 0,
            }
            for r in result.all()
        ]


async def get_weekly_volume(user_id: int, weeks: int = 8) -> list[dict]:
    """Объём тренировок по неделям за последние N недель."""
    async with AsyncSessionLocal() as session:
        since = datetime.now(DEFAULT_TZ) - timedelta(weeks=weeks)
        # Используем единый label для GROUP BY / ORDER BY (фикс GroupingError)
        week_col = func.date_trunc('week', WorkoutSession.created_at).label("week")
        stmt = (
            select(
                week_col,
                func.count(WorkoutSession.id).label("sessions"),
                func.sum(WorkoutSession.total_volume_kg).label("volume"),
                func.sum(WorkoutSession.total_duration_sec).label("duration"),
            )
            .where(and_(
                WorkoutSession.user_id == user_id,
                WorkoutSession.created_at >= since,
            ))
            .group_by(week_col)
            .order_by(week_col)
        )
        result = await session.execute(stmt)
        return [
            {
                "week": str(r.week.date()) if r.week else "",
                "sessions": r.sessions or 0,
                "volume": round(r.volume or 0, 1),
                "duration_min": round((r.duration or 0) / 60, 0),
            }
            for r in result.all()
        ]


async def get_weekly_activities(user_id: int, weeks: int = 8) -> list[dict]:
    """Активности по неделям за последние N недель.
    Возвращает [{week, count, time_min, calories}].
    """
    async with AsyncSessionLocal() as session:
        since = datetime.now(DEFAULT_TZ) - timedelta(weeks=weeks)
        week_col = func.date_trunc('week', ActivityLog.logged_at).label("week")
        # Время: если unit='min' берём value, иначе duration_min
        time_expr = case(
            (ActivityLog.unit == "min", ActivityLog.value),
            else_=func.coalesce(ActivityLog.duration_min, 0),
        )
        stmt = (
            select(
                week_col,
                func.count(ActivityLog.id).label("count"),
                func.sum(time_expr).label("time_min"),
                func.sum(func.coalesce(ActivityLog.calories_burned, 0)).label("calories"),
            )
            .where(and_(
                ActivityLog.user_id == user_id,
                ActivityLog.logged_at >= since,
            ))
            .group_by(week_col)
            .order_by(week_col)
        )
        result = await session.execute(stmt)
        return [
            {
                "week": str(r.week.date()) if r.week else "",
                "count": r.count or 0,
                "time_min": round(float(r.time_min or 0), 0),
                "calories": round(float(r.calories or 0), 0),
            }
            for r in result.all()
        ]


# ══════════════════════════════════════════════════════════════════════════════
# Программы тренировок
# ══════════════════════════════════════════════════════════════════════════════

def _program_to_dict(p, include_days: bool = True) -> dict:
    """Конвертирует WorkoutProgram ORM → dict."""
    d = {
        "id": p.id,
        "user_id": p.user_id,
        "name": p.name,
        "description": p.description,
        "goal_type": p.goal_type,
        "duration_weeks": p.duration_weeks,
        "days_per_week": p.days_per_week,
        "difficulty": p.difficulty,
        "location": p.location,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "started_at": p.started_at.isoformat() if p.started_at else None,
    }
    if include_days and hasattr(p, "days") and p.days:
        d["days"] = sorted(
            [
                {
                    "id": day.id,
                    "day_number": day.day_number,
                    "day_name": day.day_name,
                    "weekday": getattr(day, "weekday", None),
                    "preferred_start_time": getattr(day, "preferred_start_time", None),
                    "preferred_end_time": getattr(day, "preferred_end_time", None),
                    "template_id": day.template_id,
                }
                for day in p.days
            ],
            key=lambda x: x["day_number"],
        )
    else:
        d["days"] = []
    return d


def _template_to_dict(t, include_exercises: bool = True, exercise_info: dict | None = None) -> dict:
    """Конвертирует WorkoutTemplate ORM → dict. exercise_info — {exercise_id: {name, category}}."""
    d = {
        "id": t.id,
        "user_id": t.user_id,
        "name": t.name,
        "description": t.description,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }
    if include_exercises and hasattr(t, "exercises") and t.exercises:
        info = exercise_info or {}
        d["exercises"] = sorted(
            [
                {
                    "id": ex.id,
                    "exercise_id": ex.exercise_id,
                    "exercise_name": info.get(ex.exercise_id, {}).get("name", f"Упражнение #{ex.exercise_id}"),
                    "exercise_category": info.get(ex.exercise_id, {}).get("category", "strength"),
                    "sets": ex.sets,
                    "reps": ex.reps,
                    "weight_kg": ex.weight_kg,
                    "duration_sec": ex.duration_sec,
                    "rest_sec": ex.rest_sec,
                    "sort_order": ex.sort_order,
                }
                for ex in t.exercises
            ],
            key=lambda x: x["sort_order"],
        )
    else:
        d["exercises"] = []
    return d


async def create_program(
    user_id: int,
    name: str,
    goal_type: str = "gain_muscle",
    difficulty: str = "intermediate",
    location: str = "gym",
    days_per_week: int = 3,
    duration_weeks: int | None = None,
    description: str = "",
    days_data: list[dict] | None = None,
) -> dict:
    """
    Создать программу тренировок с днями.
    days_data: [{"day_number": 1, "day_name": "Грудь + Трицепс", "template_id": None}, ...]
    """
    from db.models import WorkoutProgram, WorkoutProgramDay

    async with AsyncSessionLocal() as session:
        # Создаём программу
        program = WorkoutProgram(
            user_id=user_id,
            name=name,
            description=description,
            goal_type=goal_type,
            duration_weeks=duration_weeks,
            days_per_week=days_per_week,
            difficulty=difficulty,
            location=location,
            is_active=True,
            started_at=datetime.now(tz=DEFAULT_TZ),
        )
        session.add(program)
        await session.flush()  # получаем id

        # Деактивируем все старые активные программы пользователя
        await session.execute(
            update(WorkoutProgram)
            .where(
                and_(
                    WorkoutProgram.user_id == user_id,
                    WorkoutProgram.id != program.id,
                    WorkoutProgram.is_active == True,
                )
            )
            .values(is_active=False)
        )

        # Добавляем дни
        if days_data:
            for day_info in days_data:
                day = WorkoutProgramDay(
                    program_id=program.id,
                    day_number=day_info.get("day_number", 1),
                    day_name=day_info.get("day_name", ""),
                    weekday=day_info.get("weekday"),
                    template_id=day_info.get("template_id"),
                )
                session.add(day)

        await session.commit()
        # Перезагружаем с days
        result = await session.execute(
            select(WorkoutProgram)
            .where(WorkoutProgram.id == program.id)
            .options(selectinload(WorkoutProgram.days))
        )
        return _program_to_dict(result.scalar_one())


async def get_programs(user_id: int) -> list[dict]:
    """Список всех программ пользователя."""
    from db.models import WorkoutProgram

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(WorkoutProgram)
            .where(WorkoutProgram.user_id == user_id)
            .options(selectinload(WorkoutProgram.days))
            .order_by(desc(WorkoutProgram.created_at))
        )
        return [_program_to_dict(p) for p in result.scalars().all()]


async def get_active_program(user_id: int) -> dict | None:
    """Активная программа пользователя с днями."""
    from db.models import WorkoutProgram

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(WorkoutProgram)
            .where(
                and_(
                    WorkoutProgram.user_id == user_id,
                    WorkoutProgram.is_active == True,
                )
            )
            .options(selectinload(WorkoutProgram.days))
        )
        p = result.scalar_one_or_none()
        return _program_to_dict(p) if p else None


async def sync_program_calendar(program_id: int, user_id: int, duration_weeks: int = 4) -> int:
    """
    Создаёт workout events в таблице tasks для программы.
    Для каждого дня программы с weekday — создаёт события на duration_weeks вперёд.
    Возвращает количество созданных событий.
    """
    from db.models import WorkoutProgram, Task

    async with AsyncSessionLocal() as session:
        # Загружаем программу с днями
        result = await session.execute(
            select(WorkoutProgram)
            .where(WorkoutProgram.id == program_id)
            .options(selectinload(WorkoutProgram.days))
        )
        program = result.scalar_one_or_none()
        if not program or not program.days:
            return 0

        # Удаляем старые workout events этой программы
        await session.execute(
            delete(Task).where(
                and_(
                    Task.user_id == user_id,
                    Task.event_type == "workout",
                    Task.description.like(f"%program_id:{program_id}%"),
                )
            )
        )

        # Определяем стартовую дату (понедельник текущей недели)
        now = datetime.now(tz=DEFAULT_TZ)
        # Сдвигаемся к началу недели (Пн)
        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=9, minute=0, second=0, microsecond=0)

        weeks = duration_weeks or program.duration_weeks or 4
        created = 0

        for day in program.days:
            wd = getattr(day, "weekday", None)
            if wd is None:
                continue  # пропускаем дни без weekday

            for week_offset in range(weeks):
                # Дата тренировки: начало недели + weekday + week_offset
                event_date = start_of_week + timedelta(weeks=week_offset, days=wd)

                # Не создаём события в прошлом (кроме сегодня)
                if event_date.date() < now.date():
                    continue

                event_start = event_date.replace(hour=9, minute=0)

                # Проверяем, есть ли у дня предпочтительное время
                pst = getattr(day, "preferred_start_time", None)
                pet = getattr(day, "preferred_end_time", None)
                
                if pst and pet:
                    # Есть интервал — создаём событие с конкретным временем
                    try:
                        sh, sm = map(int, pst.split(":"))
                        eh, em = map(int, pet.split(":"))
                        # Валидация: hour 0-23, minute 0-59 (24:xx → 23:59)
                        sh, sm = min(sh, 23), min(sm, 59)
                        eh, em = min(eh, 23), min(em, 59)
                    except (ValueError, IndexError):
                        # Невалидный формат — пропускаем время, создаём all-day
                        sh, sm, eh, em = 9, 0, 10, 0
                    event_start = event_date.replace(hour=sh, minute=sm, second=0, microsecond=0)
                    event_end = event_date.replace(hour=eh, minute=em, second=0, microsecond=0)
                    # Если end <= start — добавляем 1 час
                    if event_end <= event_start:
                        event_end = event_start + timedelta(hours=1)
                    remind_time = event_start - timedelta(minutes=30)
                    task = Task(
                        user_id=user_id,
                        title=f"🏋️ {day.day_name or f'Тренировка #{day.day_number}'}",
                        description=f"program_id:{program_id} day_id:{day.id}",
                        event_type="workout",
                        status="todo",
                        priority=2,
                        tags=["fitness", f"program:{program_id}"],
                        due_datetime=event_start,
                        start_at=event_start,
                        end_at=event_end,
                        remind_at=remind_time,
                        is_all_day=False,
                    )
                else:
                    # Без конкретного времени — is_all_day, напоминание в 9 утра
                    event_day = event_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    remind_time = event_date.replace(hour=9, minute=0, second=0, microsecond=0)
                    task = Task(
                        user_id=user_id,
                        title=f"🏋️ {day.day_name or f'Тренировка #{day.day_number}'}",
                        description=f"program_id:{program_id} day_id:{day.id}",
                        event_type="workout",
                        status="todo",
                        priority=2,
                        tags=["fitness", f"program:{program_id}"],
                        due_datetime=event_day,
                        remind_at=remind_time,
                        is_all_day=True,
                    )
                session.add(task)
                created += 1

        await session.commit()

        # Создаём Reminder-записи для всех фитнес-задач с remind_at.
        # fitness_storage работает напрямую с Task ORM, минуя reminder_tools,
        # поэтому reminders таблица не заполнялась — scheduler их не видел.
        if created > 0:
            try:
                from db.models import Reminder as _Rem
                from datetime import datetime as _dt, timezone as _tz
                _now_utc = _dt.now(_tz.utc)
                # Перечитываем только что созданные задачи для получения их ID
                from sqlalchemy import select as _sel
                _res = await session.execute(
                    _sel(Task).where(
                        Task.user_id == user_id,
                        Task.tags.contains([f"program:{program_id}"]),
                        Task.remind_at.isnot(None),
                        Task.is_done == False,
                    )
                )
                for _t in _res.scalars().all():
                    _rdt = _t.remind_at
                    if _rdt.tzinfo is None:
                        _rdt = _rdt.replace(tzinfo=_tz.utc)
                    if _rdt > _now_utc:
                        session.add(_Rem(
                            user_id=user_id,
                            entity_type="task",
                            entity_id=_t.id,
                            remind_at=_rdt,
                        ))
                await session.commit()
            except Exception:
                pass  # Не ломаем основной флоу
        return created


async def delete_program_events(program_id: int, user_id: int) -> int:
    """Удаляет все workout events связанные с программой."""
    from db.models import Task

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(Task).where(
                and_(
                    Task.user_id == user_id,
                    Task.event_type == "workout",
                    Task.description.like(f"%program_id:{program_id}%"),
                )
            )
        )
        await session.commit()
        return result.rowcount


async def activate_program(program_id: int, user_id: int) -> dict | None:
    """Активировать программу (деактивирует все остальные)."""
    from db.models import WorkoutProgram

    async with AsyncSessionLocal() as session:
        # Деактивируем все
        await session.execute(
            update(WorkoutProgram)
            .where(and_(WorkoutProgram.user_id == user_id, WorkoutProgram.is_active == True))
            .values(is_active=False)
        )
        # Активируем нужную
        await session.execute(
            update(WorkoutProgram)
            .where(and_(WorkoutProgram.id == program_id, WorkoutProgram.user_id == user_id))
            .values(is_active=True, started_at=datetime.now(tz=DEFAULT_TZ))
        )
        await session.commit()
        result = await session.execute(
            select(WorkoutProgram)
            .where(WorkoutProgram.id == program_id)
            .options(selectinload(WorkoutProgram.days))
        )
        p = result.scalar_one_or_none()
        if not p:
            return None

        # Синхронизируем с календарём — создаём workout events
        await sync_program_calendar(
            program_id=program_id,
            user_id=user_id,
            duration_weeks=p.duration_weeks or 4,
        )

        return _program_to_dict(p)


async def delete_program(program_id: int, user_id: int) -> bool:
    """Удалить программу и связанные calendar events."""
    from db.models import WorkoutProgram

    # Сначала удаляем workout events из календаря
    await delete_program_events(program_id=program_id, user_id=user_id)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(WorkoutProgram).where(
                and_(WorkoutProgram.id == program_id, WorkoutProgram.user_id == user_id)
            )
        )
        await session.commit()
        return result.rowcount > 0



async def update_program_day(
    day_id: int, user_id: int,
    day_name: str | None = None, weekday: int | None = -1,
    preferred_start_time: str | None = None,
    preferred_end_time: str | None = None,
    exercises_data: list[dict] | None = None,
) -> dict | None:
    """
    Обновить день программы: имя, weekday, упражнения шаблона.
    weekday=-1 означает 'не менять', None означает 'очистить'.
    Если exercises_data передан — пересоздаём шаблон.
    """
    from db.models import WorkoutProgramDay, WorkoutProgram

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(WorkoutProgramDay).where(WorkoutProgramDay.id == day_id)
        )
        day = result.scalar_one_or_none()
        if not day:
            return None

        # Проверяем принадлежность
        prog_result = await session.execute(
            select(WorkoutProgram).where(
                and_(WorkoutProgram.id == day.program_id, WorkoutProgram.user_id == user_id)
            )
        )
        if not prog_result.scalar_one_or_none():
            return None

        if day_name is not None:
            day.day_name = day_name
        if weekday != -1:
            # Проверяем уникальность weekday в рамках программы
            if weekday is not None:
                conflict = await session.execute(
                    select(WorkoutProgramDay).where(
                        and_(
                            WorkoutProgramDay.program_id == day.program_id,
                            WorkoutProgramDay.weekday == weekday,
                            WorkoutProgramDay.id != day_id,
                        )
                    )
                )
                existing = conflict.scalar_one_or_none()
                if existing:
                    # Снимаем weekday у конфликтующего дня
                    existing.weekday = None
            day.weekday = weekday

        # Сохраняем предпочтительное время тренировки
        if preferred_start_time is not None:
            day.preferred_start_time = preferred_start_time if preferred_start_time else None
        if preferred_end_time is not None:
            day.preferred_end_time = preferred_end_time if preferred_end_time else None

        # Если переданы exercises — пересоздаём шаблон
        if exercises_data is not None and len(exercises_data) > 0:
            # Запоминаем старый template_id для последующего удаления
            old_template_id = day.template_id

            # Создаём новый шаблон с обновлёнными упражнениями
            tpl = await create_template(
                user_id=user_id,
                name=day.day_name or f"День {day.day_number}",
                description="Обновлено из редактора",
                exercises_data=exercises_data,
            )
            day.template_id = tpl["id"]

            # Безопасно удаляем старый шаблон: только если ни одна
            # workout_session не ссылается на него (FK без CASCADE)
            if old_template_id is not None:
                from db.models import WorkoutTemplate, WorkoutSession
                sessions_count_result = await session.execute(
                    select(func.count(WorkoutSession.id)).where(
                        WorkoutSession.template_id == old_template_id
                    )
                )
                sessions_count = sessions_count_result.scalar()
                if sessions_count == 0:
                    # Нет ссылок — безопасно удаляем устаревший шаблон
                    await session.execute(
                        delete(WorkoutTemplate).where(WorkoutTemplate.id == old_template_id)
                    )

        await session.commit()

        return {
            "id": day.id,
            "day_number": day.day_number,
            "day_name": day.day_name,
            "weekday": getattr(day, "weekday", None),
            "preferred_start_time": getattr(day, "preferred_start_time", None),
            "preferred_end_time": getattr(day, "preferred_end_time", None),
            "template_id": day.template_id,
        }


async def add_program_day(
    program_id: int, user_id: int,
    day_name: str, weekday: int | None = None,
    exercises_data: list[dict] | None = None,
) -> dict | None:
    """Добавить новый день в программу."""
    from db.models import WorkoutProgramDay, WorkoutProgram

    async with AsyncSessionLocal() as session:
        # Проверяем программу
        prog_result = await session.execute(
            select(WorkoutProgram).where(
                and_(WorkoutProgram.id == program_id, WorkoutProgram.user_id == user_id)
            ).options(selectinload(WorkoutProgram.days))
        )
        program = prog_result.scalar_one_or_none()
        if not program:
            return None

        # Определяем следующий day_number
        max_num = max((d.day_number for d in program.days), default=0)

        template_id = None
        if exercises_data:
            tpl = await create_template(
                user_id=user_id,
                name=day_name,
                description=f"Программа: {program.name}",
                exercises_data=exercises_data,
            )
            template_id = tpl["id"]

        day = WorkoutProgramDay(
            program_id=program_id,
            day_number=max_num + 1,
            day_name=day_name,
            weekday=weekday,
            template_id=template_id,
        )
        session.add(day)
        await session.commit()

        return {
            "id": day.id,
            "day_number": day.day_number,
            "day_name": day.day_name,
            "weekday": getattr(day, "weekday", None),
            "preferred_start_time": getattr(day, "preferred_start_time", None),
            "preferred_end_time": getattr(day, "preferred_end_time", None),
            "template_id": day.template_id,
        }


async def remove_program_day(day_id: int, user_id: int) -> bool:
    """Удалить день из программы."""
    from db.models import WorkoutProgramDay, WorkoutProgram

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(WorkoutProgramDay).where(WorkoutProgramDay.id == day_id)
        )
        day = result.scalar_one_or_none()
        if not day:
            return False

        # Проверяем принадлежность
        prog_result = await session.execute(
            select(WorkoutProgram).where(
                and_(WorkoutProgram.id == day.program_id, WorkoutProgram.user_id == user_id)
            )
        )
        if not prog_result.scalar_one_or_none():
            return False

        await session.delete(day)
        await session.commit()
        return True


async def mark_today_workout_done(user_id: int) -> int:
    """
    Помечает ближайшую невыполненную тренировку-задачу из активной программы как выполненную.
    Вызывается при завершении workout session.
    """
    from db.models import Task, WorkoutProgram

    async with AsyncSessionLocal() as session:
        # Находим активную программу
        prog = await session.execute(
            select(WorkoutProgram).where(
                and_(WorkoutProgram.user_id == user_id, WorkoutProgram.is_active == True)
            )
        )
        program = prog.scalar_one_or_none()
        if not program:
            return 0

        now = datetime.now(tz=DEFAULT_TZ)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Ищем ближайшую невыполненную тренировку этой программы
        result = await session.execute(
            select(Task).where(
                and_(
                    Task.user_id == user_id,
                    Task.event_type == "workout",
                    Task.is_done == False,
                    Task.description.like(f"%program_id:{program.id}%"),
                    Task.due_datetime >= today_start,
                )
            )
            .order_by(Task.due_datetime.asc())
            .limit(1)
        )
        task = result.scalar_one_or_none()
        if task:
            task.is_done = True
            task.status = "done"
            await session.commit()
            return 1
        return 0


async def get_next_workout(user_id: int) -> dict | None:
    """
    Определить следующую тренировку из активной программы.
    Логика v3: ищем ближайшую НЕВЫПОЛНЕННУЮ задачу-тренировку из календаря.
    Показывает текущую тренировку, пока она не выполнена (is_done=True).
    """
    from db.models import WorkoutProgram, Task

    async with AsyncSessionLocal() as session:
        # Получаем активную программу с днями
        result = await session.execute(
            select(WorkoutProgram)
            .where(
                and_(
                    WorkoutProgram.user_id == user_id,
                    WorkoutProgram.is_active == True,
                )
            )
            .options(selectinload(WorkoutProgram.days))
        )
        program = result.scalar_one_or_none()
        if not program or not program.days:
            return None

        days_sorted = sorted(program.days, key=lambda d: d.day_number)
        weekday_names = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}

        # Считаем завершённые тренировки (только с ended_at — исключаем зомби-сессии)
        since = program.started_at or program.created_at
        count_result = await session.execute(
            select(func.count(WorkoutSession.id)).where(
                and_(
                    WorkoutSession.user_id == user_id,
                    WorkoutSession.started_at >= since,
                    WorkoutSession.ended_at.isnot(None),  # только реально завершённые
                )
            )
        )
        done_count = count_result.scalar() or 0

        # Ищем ближайшую невыполненную задачу-тренировку этой программы
        now = datetime.now(tz=DEFAULT_TZ)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        next_task = await session.execute(
            select(Task)
            .where(
                and_(
                    Task.user_id == user_id,
                    Task.event_type == "workout",
                    Task.is_done == False,
                    Task.description.like(f"%program_id:{program.id}%"),
                    Task.due_datetime >= today_start,
                )
            )
            .order_by(Task.due_datetime.asc())
            .limit(1)
        )
        task = next_task.scalar_one_or_none()

        if task and task.description:
            # Парсим day_id из описания задачи
            import re
            m = re.search(r"day_id:(\d+)", task.description)
            if m:
                day_id = int(m.group(1))
                # Ищем этот день в программе
                next_day = next((d for d in days_sorted if d.id == day_id), None)
                if next_day:
                    wd = getattr(next_day, "weekday", None)
                    today_wd = now.weekday()
                    is_today = (wd == today_wd) if wd is not None else False
                    return {
                        "program_name": program.name,
                        "day_number": next_day.day_number,
                        "day_name": next_day.day_name,
                        "weekday": wd,
                        "weekday_name": weekday_names.get(wd, "") if wd is not None else None,
                        "template_id": next_day.template_id,
                        "total_days": len(days_sorted),
                        "completed_workouts": done_count,
                        "is_today": is_today,
                    }

        # Fallback: если нет задач в календаре — используем weekday-логику
        today_wd = now.weekday()
        has_weekdays = any(getattr(d, "weekday", None) is not None for d in days_sorted)

        if has_weekdays:
            weekday_days = [(d, d.weekday) for d in days_sorted if getattr(d, "weekday", None) is not None]
            next_day = None
            # Ищем сегодня или ближайший
            for offset in range(0, 8):
                check_wd = (today_wd + offset) % 7
                for d, wd in weekday_days:
                    if wd == check_wd:
                        next_day = d
                        break
                if next_day is not None:
                    break
            if next_day is None:
                next_day = weekday_days[0][0]
        else:
            next_idx = done_count % len(days_sorted)
            next_day = days_sorted[next_idx]

        wd = getattr(next_day, "weekday", None)
        return {
            "program_name": program.name,
            "day_number": next_day.day_number,
            "day_name": next_day.day_name,
            "weekday": wd,
            "weekday_name": weekday_names.get(wd, "") if wd is not None else None,
            "template_id": next_day.template_id,
            "total_days": len(days_sorted),
            "completed_workouts": done_count,
            "is_today": (wd == today_wd) if wd is not None else False,
        }

# ══════════════════════════════════════════════════════════════════════════════
# Шаблоны тренировок
# ══════════════════════════════════════════════════════════════════════════════

async def create_template(
    user_id: int,
    name: str,
    description: str = "",
    exercises_data: list[dict] | None = None,
) -> dict:
    """
    Создать шаблон тренировки.
    exercises_data: [{"exercise_id": 1, "sets": 3, "reps": 10, "weight_kg": 50, "rest_sec": 90}, ...]
    """
    from db.models import WorkoutTemplate, WorkoutTemplateExercise

    async with AsyncSessionLocal() as session:
        template = WorkoutTemplate(
            user_id=user_id,
            name=name,
            description=description,
        )
        session.add(template)
        await session.flush()

        # Добавляем упражнения
        if exercises_data:
            for idx, ex_info in enumerate(exercises_data):
                tex = WorkoutTemplateExercise(
                    template_id=template.id,
                    exercise_id=ex_info["exercise_id"],
                    sets=ex_info.get("sets", 3),
                    reps=ex_info.get("reps"),
                    weight_kg=ex_info.get("weight_kg"),
                    duration_sec=ex_info.get("duration_sec"),
                    rest_sec=ex_info.get("rest_sec", 60),
                    sort_order=idx,
                )
                session.add(tex)

        await session.commit()
        result = await session.execute(
            select(WorkoutTemplate)
            .where(WorkoutTemplate.id == template.id)
            .options(selectinload(WorkoutTemplate.exercises))
        )
        return _template_to_dict(result.scalar_one())


async def list_templates(user_id: int) -> list[dict]:
    """Список шаблонов тренировок пользователя с именами упражнений."""
    from db.models import WorkoutTemplate, ExerciseLibrary

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(WorkoutTemplate)
            .where(WorkoutTemplate.user_id == user_id)
            .options(selectinload(WorkoutTemplate.exercises))
            .order_by(desc(WorkoutTemplate.created_at))
        )
        templates = result.scalars().all()

        # Собираем все exercise_id для подгрузки имён
        all_ex_ids = set()
        for t in templates:
            if t.exercises:
                for ex in t.exercises:
                    all_ex_ids.add(ex.exercise_id)

        # Подгружаем имена и категории упражнений из справочника
        exercise_info: dict = {}
        if all_ex_ids:
            ex_result = await session.execute(
                select(ExerciseLibrary.id, ExerciseLibrary.name, ExerciseLibrary.category)
                .where(ExerciseLibrary.id.in_(all_ex_ids))
            )
            for row in ex_result:
                exercise_info[row.id] = {"name": row.name, "category": row.category}

        return [_template_to_dict(t, exercise_info=exercise_info) for t in templates]


async def apply_template(template_id: int, user_id: int) -> dict | None:
    """Применить шаблон — создать и сразу завершить тренировку из шаблона.

    Создаёт WorkoutSession с подходами по данным шаблона (вес, повторения).
    Сессия сразу завершается (ended_at, total_volume_kg) — это быстрый лог
    тренировки «как запланировано». Для трекинга в реальном времени
    использовать start_workout + add_set + finish_workout.
    """
    from db.models import WorkoutTemplate

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(WorkoutTemplate)
            .where(
                and_(WorkoutTemplate.id == template_id, WorkoutTemplate.user_id == user_id)
            )
            .options(selectinload(WorkoutTemplate.exercises))
        )
        template = result.scalar_one_or_none()
        if not template:
            return None

    # Создаём активную сессию
    new_session = await start_workout(
        user_id=user_id,
        name=template.name,
        workout_type="strength",
    )
    session_id = new_session["id"]

    # Добавляем подходы из шаблона (плановые веса и повторения)
    for tex in sorted(template.exercises, key=lambda x: x.sort_order):
        for _set_num in range(tex.sets):
            await add_set(
                session_id=session_id,
                exercise_id=tex.exercise_id,
                reps=tex.reps,
                weight_kg=tex.weight_kg,
                duration_sec=tex.duration_sec,
                set_type="working",
            )

    # Завершаем сессию: устанавливает ended_at и считает total_volume_kg
    finished = await finish_workout(session_id=session_id)
    return finished


async def delete_template(template_id: int, user_id: int) -> bool:
    """Удалить шаблон."""
    from db.models import WorkoutTemplate

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(WorkoutTemplate).where(
                and_(WorkoutTemplate.id == template_id, WorkoutTemplate.user_id == user_id)
            )
        )
        await session.commit()
        return result.rowcount > 0


# ── Программа тренировок: расширенные функции ─────────────────────────────────

async def get_or_create_exercise(
    user_id: int,
    name: str,
    category: str = "strength",
    muscle_group: str | None = None,
    equipment: str | None = None,
) -> dict:
    """
    Ищет упражнение по имени (ILIKE). Если не найдено — создаёт пользовательское.
    Возвращает dict с данными упражнения (id, name, ...).
    """
    async with AsyncSessionLocal() as session:
        # Поиск: точное совпадение по имени (регистронезависимое)
        result = await session.execute(
            select(ExerciseLibrary)
            .where(ExerciseLibrary.name.ilike(name.strip()))
            .limit(1)
        )
        ex = result.scalar_one_or_none()
        if ex:
            return _exercise_to_dict(ex)

        # Поиск: подстрока в name или aliases
        q_lower = name.lower().strip()
        result = await session.execute(
            select(ExerciseLibrary)
            .where(
                or_(
                    ExerciseLibrary.name.ilike(f"%{q_lower}%"),
                    cast(ExerciseLibrary.aliases, String).ilike(f"%{q_lower}%"),
                )
            )
            .limit(5)
        )
        candidates = result.scalars().all()

        if len(candidates) == 1:
            # Единственный результат — считаем совпадением
            return _exercise_to_dict(candidates[0])

        if len(candidates) > 1:
            # Несколько кандидатов — ищем наиболее точное совпадение по длине имени
            best = min(candidates, key=lambda c: abs(len(c.name) - len(name)))
            return _exercise_to_dict(best)

        # Не найдено — создаём пользовательское упражнение
        new_ex = ExerciseLibrary(
            user_id=user_id,
            name=name.strip(),
            category=category,
            muscle_group=muscle_group,
            equipment=equipment,
            difficulty="intermediate",
            is_compound=False,
            aliases=[],
        )
        session.add(new_ex)
        await session.commit()
        await session.refresh(new_ex)
        return _exercise_to_dict(new_ex)


async def get_program_with_exercises(user_id: int, program_id: int | None = None) -> dict | None:
    """
    Загружает программу со всеми днями, шаблонами и упражнениями.
    Если program_id=None — берёт активную программу.
    Возвращает расширенный dict с полными данными упражнений в каждом дне.
    """
    from db.models import WorkoutProgram, WorkoutTemplate, WorkoutTemplateExercise

    async with AsyncSessionLocal() as session:
        # Получаем программу
        if program_id:
            q = select(WorkoutProgram).where(
                and_(WorkoutProgram.id == program_id, WorkoutProgram.user_id == user_id)
            )
        else:
            q = select(WorkoutProgram).where(
                and_(WorkoutProgram.user_id == user_id, WorkoutProgram.is_active == True)
            )
        q = q.options(selectinload(WorkoutProgram.days))

        result = await session.execute(q)
        program = result.scalar_one_or_none()
        if not program:
            return None

        # Собираем все template_id из дней
        template_ids = [d.template_id for d in program.days if d.template_id]

        # Загружаем шаблоны с упражнениями
        templates_map: dict[int, list[dict]] = {}
        if template_ids:
            tpl_result = await session.execute(
                select(WorkoutTemplate)
                .where(WorkoutTemplate.id.in_(template_ids))
                .options(selectinload(WorkoutTemplate.exercises))
            )
            templates = tpl_result.scalars().all()

            # Собираем все exercise_id для подгрузки имён
            all_ex_ids = set()
            for t in templates:
                for ex in (t.exercises or []):
                    all_ex_ids.add(ex.exercise_id)

            # Подгружаем данные упражнений из справочника
            exercise_info: dict[int, dict] = {}
            if all_ex_ids:
                ex_result = await session.execute(
                    select(ExerciseLibrary).where(ExerciseLibrary.id.in_(all_ex_ids))
                )
                for ex in ex_result.scalars():
                    exercise_info[ex.id] = _exercise_to_dict(ex)

            # Формируем маппинг template_id → список упражнений
            for t in templates:
                exercises = []
                for tex in sorted(t.exercises or [], key=lambda x: x.sort_order):
                    ex_data = exercise_info.get(tex.exercise_id, {})
                    exercises.append({
                        "id": tex.id,
                        "exercise_id": tex.exercise_id,
                        "exercise_name": ex_data.get("name", f"#{tex.exercise_id}"),
                        "muscle_group": ex_data.get("muscle_group", ""),
                        "equipment": ex_data.get("equipment", ""),
                        "sets": tex.sets,
                        "reps": tex.reps,
                        "weight_kg": tex.weight_kg,
                        "rest_sec": tex.rest_sec,
                        "sort_order": tex.sort_order,
                    })
                templates_map[t.id] = exercises

        # Формируем результат
        prog_dict = _program_to_dict(program)
        for day in prog_dict["days"]:
            day["exercises"] = templates_map.get(day.get("template_id"), [])

        return prog_dict


async def delete_all_templates(user_id: int) -> int:
    """Удалить все шаблоны тренировок пользователя. Возвращает количество удалённых.

    Перед удалением обнуляет template_id в workout_program_days,
    чтобы не нарушать FK constraint.
    """
    from db.models import WorkoutTemplate, WorkoutProgramDay, WorkoutProgram

    async with AsyncSessionLocal() as session:
        # Получаем ID шаблонов пользователя
        tpl_ids_result = await session.execute(
            select(WorkoutTemplate.id).where(WorkoutTemplate.user_id == user_id)
        )
        tpl_ids = [row[0] for row in tpl_ids_result.all()]

        if not tpl_ids:
            return 0

        # Обнуляем ссылки на шаблоны в днях программ (FK без CASCADE)
        await session.execute(
            update(WorkoutProgramDay)
            .where(WorkoutProgramDay.template_id.in_(tpl_ids))
            .values(template_id=None)
        )

        # Удаляем сами шаблоны
        result = await session.execute(
            delete(WorkoutTemplate).where(WorkoutTemplate.user_id == user_id)
        )
        await session.commit()
        return result.rowcount
