"""
REST API роутер для фитнес-модуля (/api/fitness).
Все операции изолированы по user_id текущего пользователя.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, File, status
from pydantic import BaseModel, Field
import os
import uuid
from pathlib import Path

from api.deps import get_current_user
from db.models import User
from db import fitness_storage as fs

router = APIRouter(prefix="/fitness", tags=["fitness"])


# ── Pydantic-схемы ────────────────────────────────────────────────────────────

class ExerciseOut(BaseModel):
    """Упражнение из справочника."""
    id: int
    name: str
    category: Optional[str] = None
    muscle_group: Optional[str] = None
    equipment: Optional[str] = None
    difficulty: str = "intermediate"
    is_compound: bool = False
    instructions: str = ""
    aliases: list = []


class SetData(BaseModel):
    """Данные подхода для создания."""
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    duration_sec: Optional[int] = None
    distance_m: Optional[float] = None
    pace_sec_per_km: Optional[int] = None
    set_type: str = "working"


class ExerciseData(BaseModel):
    """Упражнение с подходами для логирования тренировки."""
    exercise_id: int
    sets: List[SetData]


class WorkoutCreateDto(BaseModel):
    """DTO создания/логирования тренировки."""
    name: str = ""
    workout_type: str = "strength"
    exercises: List[ExerciseData]
    started_at: Optional[str] = None  # ISO-формат с таймзоной


class SetOut(BaseModel):
    """Подход (ответ)."""
    id: int
    exercise_id: int
    exercise_name: Optional[str] = None  # название упражнения из справочника
    set_num: Optional[int] = None
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    duration_sec: Optional[int] = None
    distance_m: Optional[float] = None
    pace_sec_per_km: Optional[int] = None
    set_type: str = "working"
    is_personal_record: bool = False


class WorkoutSessionOut(BaseModel):
    """Тренировка (ответ)."""
    id: int
    name: Optional[str] = None
    workout_type: str = "strength"
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    total_volume_kg: Optional[float] = None
    total_duration_sec: Optional[int] = None
    calories_burned: Optional[float] = None
    mood_before: Optional[int] = None
    mood_after: Optional[int] = None
    notes: str = ""
    created_at: Optional[str] = None
    sets: List[SetOut] = []


class BodyMetricCreateDto(BaseModel):
    """DTO записи замеров тела."""
    weight_kg: Optional[float] = None
    body_fat_pct: Optional[float] = None
    muscle_mass_kg: Optional[float] = None
    chest_cm: Optional[float] = None
    waist_cm: Optional[float] = None
    hips_cm: Optional[float] = None
    bicep_cm: Optional[float] = None
    thigh_cm: Optional[float] = None
    energy_level: Optional[int] = None
    sleep_hours: Optional[float] = None
    recovery_rating: Optional[int] = None
    notes: str = ""


class BodyMetricOut(BaseModel):
    """Замер тела (ответ)."""
    id: int
    weight_kg: Optional[float] = None
    body_fat_pct: Optional[float] = None
    muscle_mass_kg: Optional[float] = None
    chest_cm: Optional[float] = None
    waist_cm: Optional[float] = None
    hips_cm: Optional[float] = None
    bicep_cm: Optional[float] = None
    thigh_cm: Optional[float] = None
    energy_level: Optional[int] = None
    sleep_hours: Optional[float] = None
    recovery_rating: Optional[int] = None
    notes: str = ""
    photo_file_id: Optional[str] = None
    logged_at: Optional[str] = None


class ActivityCreateDto(BaseModel):
    """DTO записи активности."""
    activity_type: str  # run | walk | cycling | swimming | steps | yoga | hiit | stretching | elliptical | rowing | jump_rope | other
    value: float
    unit: str  # km | m | steps | min
    duration_min: Optional[int] = None
    calories_burned: Optional[float] = None
    notes: str = ""
    logged_at: Optional[str] = None  # ISO-формат с таймзоной, например 2026-03-18T11:00:00+03:00


class ActivityOut(BaseModel):
    """Активность (ответ)."""
    id: int
    activity_type: str
    value: float
    unit: str
    duration_min: Optional[int] = None
    calories_burned: Optional[float] = None
    notes: Optional[str] = None
    logged_at: Optional[str] = None


class StatsOut(BaseModel):
    """Статистика тренировок и активностей."""
    period_days: int
    total_sessions: int
    total_volume_kg: float
    total_time_min: float
    total_calories: float
    avg_mood: Optional[float] = None
    top_exercises: list = []
    current_streak_days: int = 0
    # Активности (кардио, растяжка и пр.)
    total_activities: int = 0
    total_activity_time_min: float = 0
    total_activity_calories: float = 0


class RecordOut(BaseModel):
    """Личный рекорд."""
    exercise: str
    record_type: str
    value: float
    achieved_at: Optional[str] = None


class GoalOut(BaseModel):
    """Фитнес-цель."""
    goal_type: str = "maintain"
    workouts_per_week: int = 3
    preferred_duration_min: int = 60
    training_location: str = "gym"
    experience_level: str = "intermediate"
    available_equipment: list = []
    target_weight_kg: Optional[float] = None


class GoalUpdateDto(BaseModel):
    """DTO обновления фитнес-цели."""
    goal_type: Optional[str] = None
    workouts_per_week: Optional[int] = None
    preferred_duration_min: Optional[int] = None
    training_location: Optional[str] = None
    experience_level: Optional[str] = None
    available_equipment: Optional[list] = None
    target_weight_kg: Optional[float] = None


# ── Упражнения ────────────────────────────────────────────────────────────────

@router.get("/exercises/search", response_model=List[ExerciseOut])
async def search_exercises(
    q: str = Query(""),
    category: Optional[str] = None,
    muscle_group: Optional[str] = None,
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
):
    """Поиск упражнений по названию/алиасам."""
    return await fs.search_exercises(query=q, category=category, muscle_group=muscle_group, limit=limit)


@router.get("/exercises/{exercise_id}", response_model=ExerciseOut)
async def get_exercise(exercise_id: int, user: User = Depends(get_current_user)):
    """Детали упражнения по ID."""
    ex = await fs.get_exercise_by_id(exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Упражнение не найдено")
    return ex


# ── Тренировки ────────────────────────────────────────────────────────────────

@router.post("/sessions", response_model=WorkoutSessionOut)
async def create_session(dto: WorkoutCreateDto, user: User = Depends(get_current_user)):
    """Залогировать тренировку (быстрый лог)."""
    # Конвертируем Pydantic → dict
    exercises = [
        {
            "exercise_id": ex.exercise_id,
            "sets": [s.model_dump() for s in ex.sets],
        }
        for ex in dto.exercises
    ]
    # Парсим started_at если передан
    parsed_started_at = None
    if dto.started_at:
        try:
            from datetime import datetime as _dt
            parsed_started_at = _dt.fromisoformat(dto.started_at)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Некорректный формат started_at")
    result = await fs.quick_log_workout(
        user_id=user.telegram_id,
        exercises=exercises,
        workout_type=dto.workout_type,
        name=dto.name,
        started_at=parsed_started_at,
    )
    return result


@router.get("/sessions", response_model=List[WorkoutSessionOut])
async def list_sessions(
    days: int = Query(7, ge=1, le=365),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
):
    """Список тренировок за последние N дней."""
    return await fs.get_sessions(user_id=user.telegram_id, days=days, limit=limit)


@router.get("/sessions/active", response_model=Optional[WorkoutSessionOut])
async def get_active_session(user: User = Depends(get_current_user)):
    """Текущая незавершённая тренировка."""
    return await fs.get_active_workout(user_id=user.telegram_id)


@router.post("/sessions/{session_id}/repeat", response_model=WorkoutSessionOut)
async def repeat_session(session_id: int, user: User = Depends(get_current_user)):
    """Повторить тренировку."""
    result = await fs.repeat_workout(user_id=user.telegram_id, source_session_id=session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Тренировка не найдена")
    return result


# ── Замеры тела ───────────────────────────────────────────────────────────────

@router.post("/body-metrics", response_model=BodyMetricOut)
async def create_body_metric(dto: BodyMetricCreateDto, user: User = Depends(get_current_user)):
    """Записать замер тела."""
    # Собираем только ненулевые значения
    kwargs = {k: v for k, v in dto.model_dump().items() if v is not None and v != "" and v != 0}
    if not kwargs:
        raise HTTPException(status_code=400, detail="Нужно указать хотя бы один показатель")
    return await fs.log_body_metric(user_id=user.telegram_id, **kwargs)


@router.get("/body-metrics", response_model=List[BodyMetricOut])
async def list_body_metrics(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
):
    """История замеров тела."""
    return await fs.get_body_metrics(user_id=user.telegram_id, days=days, limit=limit)


# ── Фото прогресса ────────────────────────────────────────────────────────────

# Директория для хранения фото прогресса
PHOTOS_DIR = Path("/var/www/jarvis/uploads/photos")
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

# Допустимые расширения
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class PhotoOut(BaseModel):
    """Фото прогресса (ответ)."""
    id: int
    filename: str
    url: str
    logged_at: Optional[str] = None
    weight_kg: Optional[float] = None
    notes: str = ""


@router.post("/body-metrics/photos", response_model=PhotoOut)
async def upload_progress_photo(
    file: UploadFile = File(...),
    notes: str = Form(""),
    user: User = Depends(get_current_user),
):
    """Загрузить фото прогресса. Сохраняет файл на диск и создаёт запись BodyMetric."""
    # Валидация расширения
    ext = os.path.splitext(file.filename or "photo.jpg")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Формат {ext} не поддерживается. Допустимы: jpg, png, webp")

    # Читаем файл и проверяем размер
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Файл слишком большой (макс. 10 МБ)")

    # Генерируем уникальное имя файла
    unique_name = f"{user.telegram_id}_{uuid.uuid4().hex[:12]}{ext}"
    file_path = PHOTOS_DIR / unique_name

    # Сохраняем на диск
    with open(file_path, "wb") as f:
        f.write(data)

    # Создаём запись BodyMetric с фото
    bm = await fs.log_body_metric(
        user_id=user.telegram_id,
        photo_file_id=unique_name,
        notes=notes or "Фото прогресса",
    )

    return PhotoOut(
        id=bm["id"],
        filename=unique_name,
        url=f"/uploads/photos/{unique_name}",
        logged_at=bm.get("logged_at"),
        weight_kg=bm.get("weight_kg"),
        notes=bm.get("notes", ""),
    )


@router.get("/body-metrics/photos", response_model=list[PhotoOut])
async def list_progress_photos(
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
):
    """Список фото прогресса пользователя."""
    # Получаем все замеры с фото за последний год
    all_metrics = await fs.get_body_metrics(user_id=user.telegram_id, days=365, limit=limit)
    photos = []
    for m in all_metrics:
        if m.get("photo_file_id"):
            photos.append(PhotoOut(
                id=m["id"],
                filename=m["photo_file_id"],
                url=f"/uploads/photos/{m['photo_file_id']}",
                logged_at=m.get("logged_at"),
                weight_kg=m.get("weight_kg"),
                notes=m.get("notes", ""),
            ))
    return photos


@router.delete("/body-metrics/photos/{photo_id}", status_code=204)
async def delete_progress_photo(photo_id: int, user: User = Depends(get_current_user)):
    """Удалить фото прогресса."""
    # Получаем замер
    all_metrics = await fs.get_body_metrics(user_id=user.telegram_id, days=3650, limit=1000)
    target = None
    for m in all_metrics:
        if m["id"] == photo_id and m.get("photo_file_id"):
            target = m
            break
    if not target:
        raise HTTPException(status_code=404, detail="Фото не найдено")

    # Удаляем файл с диска
    file_path = PHOTOS_DIR / target["photo_file_id"]
    if file_path.exists():
        file_path.unlink()

    # Очищаем photo_file_id в записи (не удаляем запись целиком)
    await fs.update_body_metric_photo(user_id=user.telegram_id, metric_id=photo_id, photo_file_id=None)


# ── Активность ────────────────────────────────────────────────────────────────

@router.post("/activities", response_model=ActivityOut)
async def create_activity(dto: ActivityCreateDto, user: User = Depends(get_current_user)):
    """Записать активность."""
    # Парсим logged_at если передан
    parsed_logged_at = None
    if dto.logged_at:
        try:
            from datetime import datetime as _dt
            parsed_logged_at = _dt.fromisoformat(dto.logged_at)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Некорректный формат logged_at")
    return await fs.log_activity(
        user_id=user.telegram_id,
        activity_type=dto.activity_type,
        value=dto.value,
        unit=dto.unit,
        duration_min=dto.duration_min,
        calories_burned=dto.calories_burned,
        notes=dto.notes,
        logged_at=parsed_logged_at,
    )



@router.get("/activities", response_model=list[ActivityOut])
async def list_activities(
    days: int = Query(7, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
):
    """Получить список активностей (бег, шаги, вело и т.д.) за последние N дней."""
    return await fs.get_activities(user_id=user.telegram_id, days=days, limit=limit)


class WeeklyActivityOut(BaseModel):
    """Активности за неделю."""
    week: str
    count: int
    time_min: float
    calories: float
    value_sum: float = 0  # сумма значений в оригинальных единицах (км/мин/шаги)


@router.get("/activities/weekly", response_model=list[WeeklyActivityOut])
async def get_weekly_activities(
    weeks: int = Query(8, ge=1, le=52),
    activity_type: Optional[str] = Query(None, description="Фильтр по типу: run, walk, stretching..."),
    user: User = Depends(get_current_user),
):
    """Активности по неделям — для графика прогресса."""
    return await fs.get_weekly_activities(
        user_id=user.telegram_id, weeks=weeks, activity_type=activity_type,
    )


@router.patch("/activities/{activity_id}", response_model=ActivityOut)
async def update_activity_endpoint(
    activity_id: int,
    dto: ActivityCreateDto,
    user: User = Depends(get_current_user),
):
    """Обновить активность."""
    kwargs: dict = {}
    if dto.activity_type:
        kwargs["activity_type"] = dto.activity_type
    if dto.value:
        kwargs["value"] = dto.value
    if dto.unit:
        kwargs["unit"] = dto.unit
    if dto.duration_min is not None:
        kwargs["duration_min"] = dto.duration_min
    if dto.calories_burned is not None:
        kwargs["calories_burned"] = dto.calories_burned
    if dto.notes:
        kwargs["notes"] = dto.notes
    if dto.logged_at:
        try:
            from datetime import datetime as _dt
            kwargs["logged_at"] = _dt.fromisoformat(dto.logged_at)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Некорректный формат logged_at")
    result = await fs.update_activity(activity_id=activity_id, user_id=user.telegram_id, **kwargs)
    if not result:
        raise HTTPException(status_code=404, detail="Активность не найдена")
    return result


@router.delete("/activities/{activity_id}")
async def delete_activity_endpoint(activity_id: int, user: User = Depends(get_current_user)):
    """Удалить активность."""
    ok = await fs.delete_activity(activity_id=activity_id, user_id=user.telegram_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Активность не найдена")
    return {"ok": True}


# ── Статистика ────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsOut)
async def get_stats(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
):
    """Статистика тренировок за период."""
    return await fs.get_workout_stats(user_id=user.telegram_id, days=days)


@router.get("/records", response_model=List[RecordOut])
async def get_records(user: User = Depends(get_current_user)):
    """Личные рекорды."""
    return await fs.get_personal_records(user_id=user.telegram_id)


# ── Цели ──────────────────────────────────────────────────────────────────────

@router.get("/goals", response_model=Optional[GoalOut])
async def get_goals(user: User = Depends(get_current_user)):
    """Получить фитнес-цель."""
    return await fs.get_fitness_goal(user_id=user.telegram_id)


@router.put("/goals", response_model=GoalOut)
async def update_goals(dto: GoalUpdateDto, user: User = Depends(get_current_user)):
    """Обновить фитнес-цель."""
    kwargs = {k: v for k, v in dto.model_dump().items() if v is not None}
    return await fs.set_fitness_goal(user_id=user.telegram_id, **kwargs)


# ── Активная тренировка ──────────────────────────────────────────────────────

class SessionStartDto(BaseModel):
    """DTO начала тренировки."""
    name: str = ""
    workout_type: str = "strength"
    mood_before: Optional[int] = None


class AddSetDto(BaseModel):
    """DTO добавления подхода."""
    exercise_id: int
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    duration_sec: Optional[int] = None
    distance_m: Optional[float] = None
    set_type: str = "working"


class FinishDto(BaseModel):
    """DTO завершения тренировки."""
    mood_after: Optional[int] = None
    notes: str = ""


@router.post("/sessions/start", response_model=WorkoutSessionOut)
async def start_session(dto: SessionStartDto, user: User = Depends(get_current_user)):
    """Начать активную тренировку."""
    return await fs.start_workout(
        user_id=user.telegram_id,
        name=dto.name,
        workout_type=dto.workout_type,
        mood_before=dto.mood_before,
    )


@router.post("/sessions/{session_id}/sets", response_model=SetOut)
async def add_set_to_session(session_id: int, dto: AddSetDto, user: User = Depends(get_current_user)):
    """Добавить подход к активной тренировке."""
    return await fs.add_set(
        session_id=session_id,
        exercise_id=dto.exercise_id,
        reps=dto.reps,
        weight_kg=dto.weight_kg,
        duration_sec=dto.duration_sec,
        distance_m=dto.distance_m,
        set_type=dto.set_type,
    )


@router.put("/sessions/{session_id}/finish", response_model=WorkoutSessionOut)
async def finish_session(session_id: int, dto: FinishDto, user: User = Depends(get_current_user)):
    """Завершить активную тренировку и пометить задачу в календаре выполненной."""
    # Проверяем, что сессия принадлежит текущему пользователю (защита от IDOR)
    active = await fs.get_active_workout(user_id=user.telegram_id)
    if not active or active["id"] != session_id:
        # Дополнительно проверяем по истории (сессия может быть уже завершена повторным запросом)
        sessions = await fs.get_sessions(user_id=user.telegram_id, days=1, limit=50)
        if not any(s["id"] == session_id for s in sessions):
            raise HTTPException(status_code=403, detail="Нет доступа к этой тренировке")

    result = await fs.finish_workout(
        session_id=session_id,
        mood_after=dto.mood_after,
        notes=dto.notes,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Тренировка не найдена")

    # Авто-пометка задачи-тренировки из календаря как выполненной
    try:
        await fs.mark_today_workout_done(user_id=user.telegram_id)
    except Exception as e:
        import logging
        logging.warning(f"mark_today_workout_done error: {e}")

    return result


class UpdateSessionDto(BaseModel):
    """Обновление тренировки."""
    name: Optional[str] = None
    workout_type: Optional[str] = None
    notes: Optional[str] = None
    mood_before: Optional[int] = None
    mood_after: Optional[int] = None


@router.patch("/sessions/{session_id}")
async def update_session_endpoint(
    session_id: int,
    dto: UpdateSessionDto,
    user: User = Depends(get_current_user),
):
    """Обновить тренировку (название, тип, заметки, настроение)."""
    kwargs = {k: v for k, v in dto.model_dump().items() if v is not None}
    result = await fs.update_session(session_id=session_id, user_id=user.telegram_id, **kwargs)
    if not result:
        raise HTTPException(status_code=404, detail="Тренировка не найдена")
    return result


@router.delete("/sessions/{session_id}")
async def delete_session_endpoint(session_id: int, user: User = Depends(get_current_user)):
    """Удалить тренировку (с каскадным удалением подходов)."""
    ok = await fs.delete_session(session_id=session_id, user_id=user.telegram_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Тренировка не найдена")
    return {"ok": True}




# -- Подходы (sets): редактирование и удаление --------------------------------

class UpdateSetDto(BaseModel):
    """DTO обновления подхода."""
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    duration_sec: Optional[int] = None
    distance_m: Optional[float] = None
    pace_sec_per_km: Optional[int] = None
    set_type: Optional[str] = None


@router.patch("/sets/{set_id}", response_model=SetOut)
async def update_set_endpoint(
    set_id: int,
    dto: UpdateSetDto,
    user: User = Depends(get_current_user),
):
    """Обновить подход (вес, повторения и т.д.)."""
    kwargs = {k: v for k, v in dto.model_dump().items() if v is not None}
    result = await fs.update_set(set_id=set_id, user_id=user.telegram_id, **kwargs)
    if not result:
        raise HTTPException(status_code=404, detail="Подход не найден")
    return result


@router.delete("/sets/{set_id}")
async def delete_set_endpoint(set_id: int, user: User = Depends(get_current_user)):
    """Удалить подход."""
    ok = await fs.delete_set(set_id=set_id, user_id=user.telegram_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Подход не найден")
    return {"ok": True}

# ── Прогресс по упражнению ────────────────────────────────────────────────────

class ExerciseProgressOut(BaseModel):
    """Точка прогресса по упражнению."""
    date: str
    max_weight: float
    volume: float
    max_reps: int


class WeeklyVolumeOut(BaseModel):
    """Объём за неделю."""
    week: str
    sessions: int
    volume: float
    duration_min: float


@router.get("/exercises/{exercise_id}/progress", response_model=list[ExerciseProgressOut])
async def get_exercise_progress(
    exercise_id: int,
    days: int = Query(90, ge=7, le=365),
    user: User = Depends(get_current_user),
):
    """Прогресс по упражнению — история рабочего веса."""
    return await fs.get_exercise_progress(
        user_id=user.telegram_id,
        exercise_id=exercise_id,
        days=days,
    )


@router.get("/weekly-volume", response_model=list[WeeklyVolumeOut])
async def get_weekly_volume(
    weeks: int = Query(8, ge=1, le=52),
    user: User = Depends(get_current_user),
):
    """Объём тренировок по неделям."""
    return await fs.get_weekly_volume(user_id=user.telegram_id, weeks=weeks)


# ══════════════════════════════════════════════════════════════════════════════
# Программы тренировок
# ══════════════════════════════════════════════════════════════════════════════

class ProgramDayDto(BaseModel):
    """DTO дня программы."""
    day_number: int
    day_name: str = ""
    template_id: Optional[int] = None


class ProgramCreateDto(BaseModel):
    """DTO создания программы."""
    name: str
    goal_type: str = "gain_muscle"
    difficulty: str = "intermediate"
    location: str = "gym"
    days_per_week: int = 3
    duration_weeks: Optional[int] = None
    description: str = ""
    days: list[ProgramDayDto] = []


class ProgramDayOut(BaseModel):
    """День программы (ответ)."""
    id: int
    day_number: int
    day_name: Optional[str] = None
    template_id: Optional[int] = None
    weekday: Optional[int] = None                   # день недели 0-6
    preferred_start_time: Optional[str] = None      # время начала HH:MM
    preferred_end_time: Optional[str] = None        # время окончания HH:MM


class ProgramOut(BaseModel):
    """Программа (ответ)."""
    id: int
    user_id: int
    name: str
    description: str
    goal_type: Optional[str] = None
    duration_weeks: Optional[int] = None
    days_per_week: int
    difficulty: str
    location: str
    is_active: bool
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    days: list[ProgramDayOut] = []


class ProgramGenerateDto(BaseModel):
    """DTO для AI-генерации программы."""
    goal_type: str = "gain_muscle"
    difficulty: str = "intermediate"
    location: str = "gym"
    days_per_week: int = 3
    duration_weeks: int = 4
    equipment: list[str] = []
    notes: str = ""


class NextWorkoutOut(BaseModel):
    is_today: bool = False
    """Следующая тренировка по программе."""
    program_name: str
    day_number: int
    day_name: Optional[str] = None
    template_id: Optional[int] = None
    total_days: int
    completed_workouts: int


@router.get("/programs", response_model=list[ProgramOut])
async def list_programs(user: User = Depends(get_current_user)):
    """Список программ пользователя."""
    return await fs.get_programs(user_id=user.telegram_id)


@router.get("/programs/active", response_model=Optional[ProgramOut])
async def get_active_program(user: User = Depends(get_current_user)):
    """Активная программа."""
    return await fs.get_active_program(user_id=user.telegram_id)


@router.get("/programs/next-workout", response_model=Optional[NextWorkoutOut])
async def get_next_workout(user: User = Depends(get_current_user)):
    """Следующая тренировка по активной программе."""
    return await fs.get_next_workout(user_id=user.telegram_id)


@router.post("/programs", response_model=ProgramOut)
async def create_program(dto: ProgramCreateDto, user: User = Depends(get_current_user)):
    """Создать программу вручную."""
    return await fs.create_program(
        user_id=user.telegram_id,
        name=dto.name,
        goal_type=dto.goal_type,
        difficulty=dto.difficulty,
        location=dto.location,
        days_per_week=dto.days_per_week,
        duration_weeks=dto.duration_weeks,
        description=dto.description,
        days_data=[d.model_dump() for d in dto.days],
    )


@router.post("/programs/generate", response_model=ProgramOut)
async def generate_program(dto: ProgramGenerateDto, user: User = Depends(get_current_user)):
    """AI-генерация программы тренировок v2 — weekday + автосоздание шаблонов."""
    import json
    from langchain_openai import ChatOpenAI
    from config import OPENAI_API_KEY, OPENAI_LLM_MODEL

    # Список упражнений — LLM выберет exercise_id из него
    exercises = await fs.search_exercises(query="", limit=200)
    exercise_names = [f"{e['id']}: {e['name']} ({e['muscle_group']}, {e['equipment']})" for e in exercises]

    # Словари для промпта
    equipment_str = ", ".join(dto.equipment) if dto.equipment else "любое"
    goal_labels = {
        "gain_muscle": "набор мышечной массы", "lose_weight": "похудение",
        "maintain": "поддержание формы", "endurance": "выносливость",
        "strength": "развитие силы", "home_fitness": "домашний фитнес",
        "return_to_form": "возвращение в форму",
    }
    diff_labels = {"beginner": "начинающий", "intermediate": "средний", "advanced": "продвинутый"}
    loc_labels = {"gym": "зал", "home": "дом", "outdoor": "улица", "mixed": "смешанное"}

    prompt = f"""Ты — профессиональный фитнес-тренер. Сгенерируй программу тренировок.

ПАРАМЕТРЫ:
- Цель: {goal_labels.get(dto.goal_type, dto.goal_type)}
- Уровень: {diff_labels.get(dto.difficulty, dto.difficulty)}
- Место: {loc_labels.get(dto.location, dto.location)}
- Дней в неделю: {dto.days_per_week}
- Длительность: {dto.duration_weeks} недель
- Оборудование: {equipment_str}
{f'- Примечания: {dto.notes}' if dto.notes else ''}

ДОСТУПНЫЕ УПРАЖНЕНИЯ (id: название (группа, оборудование)):
{chr(10).join(exercise_names[:100])}

ВАЖНО: привяжи каждый тренировочный день к дню недели (0=Пн, 1=Вт, 2=Ср, 3=Чт, 4=Пт, 5=Сб, 6=Вс).
Распредели дни равномерно с днями отдыха между тяжёлыми группами.
Используй ТОЛЬКО exercise_id из списка.

ОТВЕТЬ СТРОГО JSON (без markdown):
{{
  "name": "Название программы",
  "description": "Краткое описание",
  "days": [
    {{
      "weekday": 0,
      "day_name": "Грудь + Трицепс",
      "exercises": [
        {{"exercise_id": 1, "sets": 4, "reps": 8, "weight_kg": 80, "rest_sec": 90}}
      ]
    }}
  ]
}}

Каждый день — 4-6 упражнений для указанного уровня и места."""

    # Вызов LLM
    llm = ChatOpenAI(model=OPENAI_LLM_MODEL, api_key=OPENAI_API_KEY, temperature=0.7)
    response = await llm.ainvoke(prompt)
    raw = response.content.strip()
    # Убираем markdown-обёртки
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        raw = raw.rsplit("```", 1)[0]

    program_data = json.loads(raw)

    # Для каждого дня создаём Template с упражнениями и привязываем
    days_data = []
    for idx, day in enumerate(program_data.get("days", [])):
        day_exercises = day.get("exercises", [])
        template_id = None

        # Создаём шаблон если есть структурированные упражнения
        if day_exercises and isinstance(day_exercises, list) and len(day_exercises) > 0 and isinstance(day_exercises[0], dict):
            tpl = await fs.create_template(
                user_id=user.telegram_id,
                name=day.get("day_name", f"День {idx + 1}"),
                description=f"Программа: {program_data.get('name', 'AI')}",
                exercises_data=[
                    {
                        "exercise_id": ex.get("exercise_id"),
                        "sets": ex.get("sets", 3),
                        "reps": ex.get("reps"),
                        "weight_kg": ex.get("weight_kg"),
                        "rest_sec": ex.get("rest_sec", 60),
                    }
                    for ex in day_exercises
                ],
            )
            template_id = tpl["id"]

        days_data.append({
            "day_number": idx + 1,
            "day_name": day.get("day_name", f"День {idx + 1}"),
            "weekday": day.get("weekday"),
            "template_id": template_id,
        })

    return await fs.create_program(
        user_id=user.telegram_id,
        name=program_data.get("name", "AI-программа"),
        goal_type=dto.goal_type,
        difficulty=dto.difficulty,
        location=dto.location,
        days_per_week=dto.days_per_week,
        duration_weeks=dto.duration_weeks,
        description=program_data.get("description", ""),
        days_data=days_data,
    )


@router.put("/programs/{program_id}/activate", response_model=Optional[ProgramOut])
async def activate_program(program_id: int, user: User = Depends(get_current_user)):
    """Активировать программу."""
    result = await fs.activate_program(program_id=program_id, user_id=user.telegram_id)
    if not result:
        raise HTTPException(status_code=404, detail="Программа не найдена")
    return result


@router.delete("/programs/{program_id}")
async def delete_program(program_id: int, user: User = Depends(get_current_user)):
    """Удалить программу пользователя. Удаляет только свои программы (проверка user_id)."""
    ok = await fs.delete_program(program_id=program_id, user_id=user.telegram_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Программа не найдена")
    return {"ok": True}


# ── CRUD дней программы + sync-calendar ──────────────────────────────────────

class ProgramDayUpdateDto(BaseModel):
    """DTO обновления дня программы."""
    day_name: str | None = None
    weekday: int | None = Field(None, ge=0, le=6, description="0=Пн..6=Вс, null — убрать привязку")
    preferred_start_time: str | None = Field(None, description="Время начала HH:MM")
    preferred_end_time: str | None = Field(None, description="Время окончания HH:MM")
    exercises: list[dict] | None = None

class ProgramDayAddDto(BaseModel):
    """DTO добавления дня программы."""
    day_name: str
    weekday: int | None = Field(None, ge=0, le=6)
    preferred_start_time: str | None = None
    preferred_end_time: str | None = None
    exercises: list[dict] | None = None


@router.put("/programs/{program_id}/days/{day_id}")
async def update_program_day(
    program_id: int, day_id: int,
    dto: ProgramDayUpdateDto,
    user: User = Depends(get_current_user),
):
    """Обновить день программы (имя, weekday, упражнения)."""
    import logging
    logging.warning(f"UPDATE DAY dto: day_name={dto.day_name} weekday={dto.weekday} start={dto.preferred_start_time} end={dto.preferred_end_time} ex_count={len(dto.exercises) if dto.exercises else 0}")
    # Передаём weekday как есть (None = очистить, число = установить)
    weekday_val = dto.weekday  # None, 0-6
    result = await fs.update_program_day(
        day_id=day_id,
        user_id=user.telegram_id,
        day_name=dto.day_name,
        weekday=weekday_val if weekday_val is not None else -1,
        preferred_start_time=dto.preferred_start_time,
        preferred_end_time=dto.preferred_end_time,
        exercises_data=dto.exercises,
    )
    if not result:
        raise HTTPException(status_code=404, detail="День не найден")

    # Авто-синхронизация с календарём
    program = await fs.get_active_program(user_id=user.telegram_id)
    if program and program["id"] == program_id:
        await fs.sync_program_calendar(program_id=program_id, user_id=user.telegram_id)

    return result


@router.post("/programs/{program_id}/days")
async def add_program_day(
    program_id: int,
    dto: ProgramDayAddDto,
    user: User = Depends(get_current_user),
):
    """Добавить день в программу."""
    result = await fs.add_program_day(
        program_id=program_id,
        user_id=user.telegram_id,
        day_name=dto.day_name,
        weekday=dto.weekday,
        exercises_data=dto.exercises,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Программа не найдена")

    # Авто-синхронизация
    program = await fs.get_active_program(user_id=user.telegram_id)
    if program and program["id"] == program_id:
        await fs.sync_program_calendar(program_id=program_id, user_id=user.telegram_id)

    return result


@router.delete("/programs/{program_id}/days/{day_id}")
async def remove_program_day(
    program_id: int, day_id: int,
    user: User = Depends(get_current_user),
):
    """Удалить день из программы."""
    ok = await fs.remove_program_day(day_id=day_id, user_id=user.telegram_id)
    if not ok:
        raise HTTPException(status_code=404, detail="День не найден")

    # Авто-синхронизация
    program = await fs.get_active_program(user_id=user.telegram_id)
    if program and program["id"] == program_id:
        await fs.sync_program_calendar(program_id=program_id, user_id=user.telegram_id)

    return {"ok": True}


@router.post("/programs/{program_id}/sync-calendar")
async def sync_calendar(program_id: int, user: User = Depends(get_current_user)):
    """Пересоздать calendar events для программы."""
    program = await fs.get_active_program(user_id=user.telegram_id)
    if not program or program["id"] != program_id:
        raise HTTPException(status_code=404, detail="Активная программа не найдена")

    count = await fs.sync_program_calendar(
        program_id=program_id,
        user_id=user.telegram_id,
        duration_weeks=program.get("duration_weeks") or 4,
    )
    return {"synced_events": count}


# ══════════════════════════════════════════════════════════════════════════════
# Шаблоны тренировок
# ══════════════════════════════════════════════════════════════════════════════

class TemplateExerciseDto(BaseModel):
    """DTO упражнения в шаблоне."""
    exercise_id: int
    sets: int = 3
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    duration_sec: Optional[int] = None
    rest_sec: int = 60


class TemplateCreateDto(BaseModel):
    """DTO создания шаблона."""
    name: str
    description: str = ""
    exercises: list[TemplateExerciseDto] = []


class TemplateExerciseOut(BaseModel):
    """Упражнение шаблона (ответ)."""
    id: int
    exercise_id: int
    exercise_name: str = ""          # Название упражнения из справочника
    exercise_category: str = ""      # Категория (strength/cardio/flexibility)
    sets: int
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    duration_sec: Optional[int] = None
    rest_sec: int
    sort_order: int


class TemplateOut(BaseModel):
    """Шаблон (ответ)."""
    id: int
    user_id: int
    name: str
    description: str
    created_at: Optional[str] = None
    exercises: list[TemplateExerciseOut] = []


@router.get("/templates", response_model=list[TemplateOut])
async def get_templates(user: User = Depends(get_current_user)):
    """Список шаблонов."""
    return await fs.list_templates(user_id=user.telegram_id)


@router.post("/templates", response_model=TemplateOut)
async def create_template(dto: TemplateCreateDto, user: User = Depends(get_current_user)):
    """Создать шаблон."""
    return await fs.create_template(
        user_id=user.telegram_id,
        name=dto.name,
        description=dto.description,
        exercises_data=[e.model_dump() for e in dto.exercises],
    )


@router.post("/templates/{template_id}/apply", response_model=WorkoutSessionOut)
async def apply_template(template_id: int, user: User = Depends(get_current_user)):
    """Применить шаблон — создать тренировку из шаблона."""
    result = await fs.apply_template(template_id=template_id, user_id=user.telegram_id)
    if not result:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    return result


@router.delete("/templates/{template_id}")
async def delete_template_endpoint(template_id: int, user: User = Depends(get_current_user)):
    """Удалить шаблон."""
    ok = await fs.delete_template(template_id=template_id, user_id=user.telegram_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════════
# Insights
# ══════════════════════════════════════════════════════════════════════════════

class PostWorkoutTipsOut(BaseModel):
    """Советы после тренировки."""
    tips: list[str]


class WeeklySummaryOut(BaseModel):
    """Еженедельная сводка."""
    sessions: int
    sessions_goal: int
    sessions_prev: int
    volume_kg: int
    volume_prev_kg: int
    volume_change_pct: int
    time_min: int
    calories: int
    streak: int
    new_records: int
    records: list[dict] = []
    top_exercises: list[dict] = []


@router.get("/insights/post-workout/{session_id}", response_model=PostWorkoutTipsOut)
async def get_post_workout_tips(session_id: int, user: User = Depends(get_current_user)):
    """Советы после тренировки (связка с питанием)."""
    from services.fitness_insights import post_workout_tips

    # Получаем данные сессии
    sessions = await fs.get_sessions(user_id=user.telegram_id, days=7, limit=50)
    session_data = next((s for s in sessions if s["id"] == session_id), {})
    tips = await post_workout_tips(user_id=user.telegram_id, session_data=session_data)
    return {"tips": tips}


@router.get("/insights/weekly", response_model=WeeklySummaryOut)
async def get_weekly_summary(user: User = Depends(get_current_user)):
    """Еженедельная фитнес-сводка."""
    from services.fitness_insights import weekly_fitness_summary
    return await weekly_fitness_summary(user_id=user.telegram_id)
