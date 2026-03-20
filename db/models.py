"""
SQLAlchemy 2.x ORM-модели для всех доменов продукта.
Используются ботом (через async session) и FastAPI.
Схема соответствует docs/product-architecture.md.
"""
from __future__ import annotations

from datetime import datetime, date, time
from typing import Optional, List

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Float, ForeignKey,
    Integer, String, Text, Time, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

import uuid
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


# ══════════════════════════════════════════════════════════════════════════════
# Системные таблицы
# ══════════════════════════════════════════════════════════════════════════════

class User(Base):
    """Пользователь бота - идентифицируется по telegram_id."""
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    mode: Mapped[str] = mapped_column(String(20), default="personal")          # personal | business
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")
    notification_offset_min: Mapped[int] = mapped_column(Integer, default=15)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    auth_provider: Mapped[str] = mapped_column(String(20), server_default="telegram")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Связи
    profile: Mapped[Optional["UserProfile"]] = relationship(back_populates="user", uselist=False)
    memberships: Mapped[List["Membership"]] = relationship(back_populates="user")
    external_identities: Mapped[List["ExternalIdentity"]] = relationship(back_populates="user")
    tasks: Mapped[List["Task"]] = relationship(back_populates="user")
    reminders: Mapped[List["Reminder"]] = relationship(back_populates="user")
    calendars: Mapped[List["Calendar"]] = relationship(back_populates="user")


class UserProfile(Base):
    """Профиль пользователя - дополнительные данные."""
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    bio: Mapped[Optional[str]] = mapped_column(Text)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    # Параметры тела для расчёта КБЖУ
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)       # вес в кг
    height_cm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)       # рост в см
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)             # возраст
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)       # male / female
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


    user: Mapped["User"] = relationship(back_populates="profile")


class Reminder(Base):
    """Универсальные напоминания для любых сущностей (task, event, habit, appointment)."""
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    entity_type: Mapped[str] = mapped_column(String(30))                       # task | event | habit | appointment
    entity_id: Mapped[int] = mapped_column(Integer)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    telegram_message_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="reminders")


class NotificationLog(Base):
    """Лог отправленных уведомлений."""
    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reminder_id: Mapped[int] = mapped_column(Integer, ForeignKey("reminders.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    message_text: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ══════════════════════════════════════════════════════════════════════════════
# Домен: Tasks & Calendar
# ══════════════════════════════════════════════════════════════════════════════

class Calendar(Base):
    """Календарь пользователя (Личное, Работа, Здоровье и т.п.)."""
    __tablename__ = "calendars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    name: Mapped[str] = mapped_column(String(100))
    color: Mapped[str] = mapped_column(String(20), default="#5B8CFF")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="calendars")
    tasks: Mapped[List["Task"]] = relationship(back_populates="calendar")


class Task(Base):
    """Задача или событие. event_type='task' - дедлайн, 'event' - временной слот."""
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    calendar_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("calendars.id"))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    event_type: Mapped[str] = mapped_column(String(10), default="task")        # task | event
    status: Mapped[str] = mapped_column(String(20), default="todo")            # todo | in_progress | done | cancelled
    priority: Mapped[int] = mapped_column(Integer, default=2)                  # 1 высокий, 2 обычный, 3 низкий
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    due_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))   # дедлайн для task
    start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))       # начало для event
    end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))         # конец для event
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    remind_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    recurrence_rule: Mapped[Optional[str]] = mapped_column(String(500))        # RFC 5545 RRULE
    parent_task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tasks.id"))
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="tasks")
    calendar: Mapped[Optional["Calendar"]] = relationship(back_populates="tasks")
    subtasks: Mapped[List["Task"]] = relationship()


# ══════════════════════════════════════════════════════════════════════════════
# Домен: Nutrition
# ══════════════════════════════════════════════════════════════════════════════

class FoodItem(Base):
    """Справочник продуктов питания. user_id=None - системный справочник."""
    __tablename__ = "food_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    name: Mapped[str] = mapped_column(String(200))
    calories: Mapped[Optional[float]] = mapped_column(Float)                   # ккал на 100г
    protein_g: Mapped[Optional[float]] = mapped_column(Float)
    fat_g: Mapped[Optional[float]] = mapped_column(Float)
    carbs_g: Mapped[Optional[float]] = mapped_column(Float)
    fiber_g: Mapped[Optional[float]] = mapped_column(Float)
    barcode: Mapped[Optional[str]] = mapped_column(String(50))
    serving_size_g: Mapped[Optional[float]] = mapped_column(Float)              # размер порции по умолчанию, г
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Meal(Base):
    """Приём пищи пользователя."""
    __tablename__ = "meals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    meal_type: Mapped[str] = mapped_column(String(20))                         # breakfast | lunch | dinner | snack
    eaten_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str] = mapped_column(Text, default="")
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Telegram file_id фото еды
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[List["MealItem"]] = relationship(back_populates="meal", cascade="all, delete-orphan")


class MealItem(Base):
    """Позиция (продукт + количество) в приёме пищи."""
    __tablename__ = "meal_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meal_id: Mapped[int] = mapped_column(Integer, ForeignKey("meals.id", ondelete="CASCADE"))
    food_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("food_items.id"))
    amount_g: Mapped[float] = mapped_column(Float)
    # Snapshot КБЖУ на момент логирования (кеш, чтобы данные не терялись при изменении продукта)
    calories_snapshot: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    protein_snapshot: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fat_snapshot: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    carbs_snapshot: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    meal: Mapped["Meal"] = relationship(back_populates="items")
    food_item: Mapped["FoodItem"] = relationship()


class WaterLog(Base):
    """Лог потребления воды."""
    __tablename__ = "water_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    amount_ml: Mapped[int] = mapped_column(Integer)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NutritionGoal(Base):
    """Суточные цели по питанию пользователя."""
    __tablename__ = "nutrition_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), unique=True)
    calories: Mapped[Optional[int]] = mapped_column(Integer)
    protein_g: Mapped[Optional[int]] = mapped_column(Integer)
    fat_g: Mapped[Optional[int]] = mapped_column(Integer)
    carbs_g: Mapped[Optional[int]] = mapped_column(Integer)
    water_ml: Mapped[int] = mapped_column(Integer, default=2000)
    # Тип цели и уровень активности для авто-расчёта
    goal_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)    # lose / maintain / gain
    activity_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # sedentary / light / moderate / active / very_active
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ══════════════════════════════════════════════════════════════════════════════
# Домен: Fitness
# ══════════════════════════════════════════════════════════════════════════════

class ExerciseLibrary(Base):
    """Справочник упражнений. user_id=None - системный справочник."""
    __tablename__ = "exercise_library"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[Optional[str]] = mapped_column(String(30))                # strength | cardio | flexibility | home
    muscle_group: Mapped[Optional[str]] = mapped_column(String(50))            # chest | back | legs | shoulders | biceps | triceps | core | full_body
    description: Mapped[str] = mapped_column(Text, default="")
    equipment: Mapped[Optional[str]] = mapped_column(String(50))               # штанга | гантели | тренажёр | без оборудования | турник
    difficulty: Mapped[str] = mapped_column(String(20), default="intermediate") # beginner | intermediate | advanced
    is_compound: Mapped[bool] = mapped_column(Boolean, default=False)          # базовое или изолирующее
    instructions: Mapped[str] = mapped_column(Text, default="")                # описание техники
    aliases: Mapped[list] = mapped_column(JSONB, default=list)                 # варианты названий для голосового поиска
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkoutTemplate(Base):
    """Шаблон тренировки (план)."""
    __tablename__ = "workout_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    exercises: Mapped[List["WorkoutTemplateExercise"]] = relationship(back_populates="template", cascade="all, delete-orphan")


class WorkoutTemplateExercise(Base):
    """Упражнение внутри шаблона тренировки."""
    __tablename__ = "workout_template_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("workout_templates.id", ondelete="CASCADE"))
    exercise_id: Mapped[int] = mapped_column(Integer, ForeignKey("exercise_library.id"))
    sets: Mapped[int] = mapped_column(Integer, default=3)
    reps: Mapped[Optional[int]] = mapped_column(Integer)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    duration_sec: Mapped[Optional[int]] = mapped_column(Integer)               # для кардио
    rest_sec: Mapped[int] = mapped_column(Integer, default=60)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    template: Mapped["WorkoutTemplate"] = relationship(back_populates="exercises")


class WorkoutSession(Base):
    """Фактически проведённая тренировка."""
    __tablename__ = "workout_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    template_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("workout_templates.id"))
    name: Mapped[Optional[str]] = mapped_column(String(200))
    workout_type: Mapped[str] = mapped_column(String(20), default="strength")  # strength | cardio | home | functional | stretching
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    total_volume_kg: Mapped[Optional[float]] = mapped_column(Float)            # суммарный объём (подходы × повторы × вес)
    total_duration_sec: Mapped[Optional[int]] = mapped_column(Integer)         # общее время тренировки
    calories_burned: Mapped[Optional[float]] = mapped_column(Float)            # оценка сожжённых калорий
    mood_before: Mapped[Optional[int]] = mapped_column(Integer)                # настроение до (1-5)
    mood_after: Mapped[Optional[int]] = mapped_column(Integer)                 # настроение после (1-5)
    notes: Mapped[str] = mapped_column(Text, default="")
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sets: Mapped[List["WorkoutSet"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class WorkoutSet(Base):
    """Подход в тренировке."""
    __tablename__ = "workout_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("workout_sessions.id", ondelete="CASCADE"))
    exercise_id: Mapped[int] = mapped_column(Integer, ForeignKey("exercise_library.id"))
    set_num: Mapped[Optional[int]] = mapped_column(Integer)
    reps: Mapped[Optional[int]] = mapped_column(Integer)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    duration_sec: Mapped[Optional[int]] = mapped_column(Integer)
    distance_m: Mapped[Optional[float]] = mapped_column(Float)                # дистанция для кардио (метры)
    pace_sec_per_km: Mapped[Optional[int]] = mapped_column(Integer)            # темп бега
    set_type: Mapped[str] = mapped_column(String(20), default="working")       # warmup | working | drop | failure
    is_personal_record: Mapped[bool] = mapped_column(Boolean, default=False)

    session: Mapped["WorkoutSession"] = relationship(back_populates="sets")
    # Связь с упражнением для получения названия
    exercise: Mapped["ExerciseLibrary"] = relationship(lazy="joined")


class BodyMetric(Base):
    """Замеры тела пользователя."""
    __tablename__ = "body_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    body_fat_pct: Mapped[Optional[float]] = mapped_column(Float)
    muscle_mass_kg: Mapped[Optional[float]] = mapped_column(Float)
    chest_cm: Mapped[Optional[float]] = mapped_column(Float)
    waist_cm: Mapped[Optional[float]] = mapped_column(Float)
    hips_cm: Mapped[Optional[float]] = mapped_column(Float)
    bicep_cm: Mapped[Optional[float]] = mapped_column(Float)                   # бицепс
    thigh_cm: Mapped[Optional[float]] = mapped_column(Float)                   # бедро
    energy_level: Mapped[Optional[int]] = mapped_column(Integer)               # уровень энергии (1-5)
    sleep_hours: Mapped[Optional[float]] = mapped_column(Float)                # часы сна
    recovery_rating: Mapped[Optional[int]] = mapped_column(Integer)            # восстановление (1-5)
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(200))          # фото прогресса
    notes: Mapped[str] = mapped_column(Text, default="")                       # заметки
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())




class FitnessGoal(Base):
    """Фитнес-цели пользователя."""
    __tablename__ = "fitness_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), unique=True)
    goal_type: Mapped[str] = mapped_column(String(30), default="maintain")     # lose_weight | gain_muscle | maintain | endurance | strength
    workouts_per_week: Mapped[int] = mapped_column(Integer, default=3)
    preferred_duration_min: Mapped[int] = mapped_column(Integer, default=60)
    training_location: Mapped[str] = mapped_column(String(20), default="gym")  # gym | home | outdoor | mixed
    available_equipment: Mapped[list] = mapped_column(JSONB, default=list)     # доступный инвентарь
    experience_level: Mapped[str] = mapped_column(String(20), default="intermediate")
    target_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # целевой вес для графика
    current_program_id: Mapped[Optional[int]] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class WorkoutProgram(Base):
    """Программа тренировок."""
    __tablename__ = "workout_programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    goal_type: Mapped[Optional[str]] = mapped_column(String(30))
    duration_weeks: Mapped[Optional[int]] = mapped_column(Integer)
    days_per_week: Mapped[int] = mapped_column(Integer, default=3)
    difficulty: Mapped[str] = mapped_column(String(20), default="intermediate")
    location: Mapped[str] = mapped_column(String(20), default="gym")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    days: Mapped[List["WorkoutProgramDay"]] = relationship(back_populates="program", cascade="all, delete-orphan")


class WorkoutProgramDay(Base):
    """День в программе тренировок."""
    __tablename__ = "workout_program_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("workout_programs.id", ondelete="CASCADE"))
    day_number: Mapped[int] = mapped_column(Integer)
    day_name: Mapped[Optional[str]] = mapped_column(String(200))
    weekday: Mapped[Optional[int]] = mapped_column(Integer)                     # 0=Пн, 1=Вт, ... 6=Вс
    preferred_start_time: Mapped[Optional[str]] = mapped_column(String(5))      # HH:MM формат, время начала тренировки
    preferred_end_time: Mapped[Optional[str]] = mapped_column(String(5))        # HH:MM формат, время окончания тренировки
    template_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("workout_templates.id"))

    program: Mapped["WorkoutProgram"] = relationship(back_populates="days")


class PersonalRecord(Base):
    """Личный рекорд пользователя в упражнении."""
    __tablename__ = "personal_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    exercise_id: Mapped[int] = mapped_column(Integer, ForeignKey("exercise_library.id"))
    record_type: Mapped[str] = mapped_column(String(30))                       # max_weight | max_reps | max_volume | best_time | max_distance
    value: Mapped[float] = mapped_column(Float)
    achieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    session_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("workout_sessions.id"))


class ActivityLog(Base):
    """Лог активности (шаги, бег, вело и т.д.)."""
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    activity_type: Mapped[str] = mapped_column(String(30))                     # steps | run | walk | cycling | swimming | yoga | hiit | stretching | elliptical | rowing | jump_rope | other
    value: Mapped[float] = mapped_column(Float)                                # количество (шаги, км, минуты)
    unit: Mapped[str] = mapped_column(String(10))                              # steps | km | min | m
    duration_min: Mapped[Optional[int]] = mapped_column(Integer)
    calories_burned: Mapped[Optional[float]] = mapped_column(Float)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[str] = mapped_column(Text, default="")


# ══════════════════════════════════════════════════════════════════════════════
# Домен: Coaching
# ══════════════════════════════════════════════════════════════════════════════

class Goal(Base):
    """Цель пользователя."""
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    area: Mapped[Optional[str]] = mapped_column(String(30))                    # health | finance | career | personal | relationships
    target_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")          # active | achieved | cancelled
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # ── Coaching-расширения (§4.1) ──────────────────────────────────────────
    priority: Mapped[str] = mapped_column(String(20), default="medium")         # high | medium | low
    is_frozen: Mapped[bool] = mapped_column(Boolean, default=False)             # цель на паузе
    frozen_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # причина заморозки
    parent_goal_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("goals.id"), nullable=True)  # вложенная цель
    linked_habit_ids: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)   # list[int] id привычек
    first_step: Mapped[Optional[str]] = mapped_column(Text, nullable=True)      # первый конкретный шаг
    why_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # глубинная мотивация
    coaching_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # заметки коуча по цели
    last_coaching_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Отношения к coaching-таблицам ──────────────────────────────────────
    milestones: Mapped[List["GoalMilestone"]] = relationship(back_populates="goal", cascade="all, delete-orphan")
    checkins: Mapped[List["GoalCheckin"]] = relationship(back_populates="goal", cascade="all, delete-orphan")
    reviews: Mapped[List["GoalReview"]] = relationship(back_populates="goal", cascade="all, delete-orphan")


class Habit(Base):
    """Привычка для трекинга."""
    __tablename__ = "habits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    area: Mapped[Optional[str]] = mapped_column(String(30))                    # health | productivity | mindset | sport
    frequency: Mapped[str] = mapped_column(String(20), default="daily")        # daily | weekly | custom
    target_count: Mapped[int] = mapped_column(Integer, default=1)
    color: Mapped[str] = mapped_column(String(20), default="#5B8CFF")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # ── Coaching-расширения (§4.1) ──────────────────────────────────────────
    goal_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("goals.id"), nullable=True)  # привязка к цели
    cue: Mapped[Optional[str]] = mapped_column(Text, nullable=True)            # триггер привычки
    reward: Mapped[Optional[str]] = mapped_column(Text, nullable=True)         # награда после выполнения
    best_time: Mapped[Optional[str]] = mapped_column(String(20), nullable=True) # morning | afternoon | evening | anytime
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")      # easy | medium | hard
    current_streak: Mapped[int] = mapped_column(Integer, default=0)            # текущая серия дней
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)            # рекорд серии
    total_completions: Mapped[int] = mapped_column(Integer, default=0)         # всего выполнений
    last_logged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    logs: Mapped[List["HabitLog"]] = relationship(back_populates="habit", cascade="all, delete-orphan")


class HabitLog(Base):
    """Запись о выполнении привычки."""
    __tablename__ = "habit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    habit_id: Mapped[int] = mapped_column(Integer, ForeignKey("habits.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    value: Mapped[int] = mapped_column(Integer, default=1)                     # стаканы воды, повторения и т.п.
    notes: Mapped[str] = mapped_column(Text, default="")
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Telegram file_id фото еды

    habit: Mapped["Habit"] = relationship(back_populates="logs")


# ══════════════════════════════════════════════════════════════════════════════
# Домен: CRM
# ══════════════════════════════════════════════════════════════════════════════

class CrmCompany(Base):
    """Компания в CRM."""
    __tablename__ = "crm_companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    name: Mapped[str] = mapped_column(String(300))
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    website: Mapped[Optional[str]] = mapped_column(String(300))
    notes: Mapped[str] = mapped_column(Text, default="")
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Telegram file_id фото еды
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CrmContact(Base):
    """Контакт в CRM (расширенная версия текущей таблицы)."""
    __tablename__ = "crm_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    company_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("crm_companies.id"))
    name: Mapped[str] = mapped_column(String(300))
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    position: Mapped[str] = mapped_column(String(200), default="")
    telegram: Mapped[str] = mapped_column(String(100), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Telegram file_id фото еды
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CrmPipeline(Base):
    """Воронка продаж."""
    __tablename__ = "crm_pipelines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    name: Mapped[str] = mapped_column(String(200))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    stages: Mapped[List["CrmPipelineStage"]] = relationship(back_populates="pipeline", cascade="all, delete-orphan")


class CrmPipelineStage(Base):
    """Стадия воронки продаж."""
    __tablename__ = "crm_pipeline_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipeline_id: Mapped[int] = mapped_column(Integer, ForeignKey("crm_pipelines.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[Optional[str]] = mapped_column(String(20))

    pipeline: Mapped["CrmPipeline"] = relationship(back_populates="stages")


class CrmDeal(Base):
    """Сделка в CRM (расширенная версия текущей таблицы)."""
    __tablename__ = "crm_deals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    pipeline_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("crm_pipelines.id"))
    stage_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("crm_pipeline_stages.id"))
    contact_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("crm_contacts.id"))
    company_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("crm_companies.id"))
    title: Mapped[str] = mapped_column(String(300))
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="RUB")
    status: Mapped[str] = mapped_column(String(20), default="open")            # open | won | lost
    expected_close: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Telegram file_id фото еды
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CrmActivity(Base):
    """Активность по контакту или сделке (звонок, встреча, заметка и т.п.)."""
    __tablename__ = "crm_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    contact_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("crm_contacts.id"))
    deal_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("crm_deals.id"))
    type: Mapped[str] = mapped_column(String(20))                              # call | meeting | email | note | task
    description: Mapped[str] = mapped_column(Text)
    happened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ══════════════════════════════════════════════════════════════════════════════
# Домен: Team
# ══════════════════════════════════════════════════════════════════════════════

class Team(Base):
    """Команда."""
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    members: Mapped[List["TeamMember"]] = relationship(back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    """Участник команды."""
    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    role: Mapped[str] = mapped_column(String(20), default="member")            # owner | admin | member
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    team: Mapped["Team"] = relationship(back_populates="members")


class TeamTask(Base):
    """Задача команды."""
    __tablename__ = "team_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"))
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    assignee_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="todo")
    priority: Mapped[int] = mapped_column(Integer, default=2)
    due_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ══════════════════════════════════════════════════════════════════════════════
# Домен: Scheduler
# ══════════════════════════════════════════════════════════════════════════════

class AvailabilitySlot(Base):
    """Слот доступности пользователя (рабочие часы)."""
    __tablename__ = "availability_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    day_of_week: Mapped[int] = mapped_column(Integer)                          # 0=пн ... 6=вс
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Appointment(Base):
    """Встреча / созвон."""
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    contact_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("crm_contacts.id"))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    location: Mapped[str] = mapped_column(String(500), default="")             # ссылка на Zoom, адрес
    status: Mapped[str] = mapped_column(String(20), default="scheduled")       # scheduled | done | cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Избранные продукты ────────────────────────────────────────────────────────

class FavoriteFood(Base):
    """Избранный продукт пользователя (⭐ в FoodSearch)."""
    __tablename__ = "favorite_foods"
    __table_args__ = (
        UniqueConstraint("user_id", "food_item_id", name="uq_favorite_user_food"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    food_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("food_items.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Шаблоны приёмов пищи ─────────────────────────────────────────────────────

class MealTemplate(Base):
    """Шаблон приёма пищи (например 'Мой завтрак')."""
    __tablename__ = "meal_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    name: Mapped[str] = mapped_column(String(200))                               # название шаблона
    meal_type: Mapped[str] = mapped_column(String(20), default="snack")          # breakfast / lunch / dinner / snack
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["MealTemplateItem"]] = relationship(
        back_populates="template", cascade="all, delete-orphan", lazy="selectin"
    )


class MealTemplateItem(Base):
    """Позиция в шаблоне приёма пищи."""
    __tablename__ = "meal_template_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("meal_templates.id", ondelete="CASCADE"))
    food_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("food_items.id"))
    amount_g: Mapped[float] = mapped_column(Float)                                # порция в граммах

    template: Mapped["MealTemplate"] = relationship(back_populates="items")
    food_item: Mapped["FoodItem"] = relationship(lazy="joined")


# ══════════════════════════════════════════════════════════════════════════════
# Домен: Coaching  (§4 docs/coaching-architecture.md)
# ══════════════════════════════════════════════════════════════════════════════

class GoalMilestone(Base):
    """Этап (промежуточная точка) для цели."""
    __tablename__ = "goal_milestones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(Integer, ForeignKey("goals.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")          # pending | done | skipped
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    goal: Mapped["Goal"] = relationship(back_populates="milestones")


class GoalCheckin(Base):
    """Дневной чекин пользователя (утро / день / вечер / manual)."""
    __tablename__ = "goal_checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("goals.id", ondelete="SET NULL"), nullable=True)  # опционально - привязка к цели
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)              # 0-100
    energy_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True) # 1-5
    mood: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)      # great|good|ok|tired|bad
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)           # рефлексия / ответ на «как прошёл день»
    blockers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)        # что мешало
    wins: Mapped[Optional[str]] = mapped_column(Text, nullable=True)            # победы дня
    time_slot: Mapped[str] = mapped_column(String(10), default="manual")        # morning|midday|evening|manual
    check_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)     # явная дата чекина
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    goal: Mapped[Optional["Goal"]] = relationship(back_populates="checkins")


class GoalReview(Base):
    """Недельный или месячный review по цели."""
    __tablename__ = "goal_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(Integer, ForeignKey("goals.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    review_type: Mapped[str] = mapped_column(String(20), default="weekly")     # weekly | monthly
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    highlights: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)   # list[str]
    blockers: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)     # list[str]
    next_actions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True) # list[str]
    ai_assessment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # оценка коуча
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)        # 0-100
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    goal: Mapped["Goal"] = relationship(back_populates="reviews")


class HabitStreak(Base):
    """История стриков привычки."""
    __tablename__ = "habit_streaks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    habit_id: Mapped[int] = mapped_column(Integer, ForeignKey("habits.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    length: Mapped[int] = mapped_column(Integer, default=0)                    # длина серии в днях
    break_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # причина прерывания
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)            # текущий стрик


class HabitTemplate(Base):
    """Библиотека готовых шаблонов привычек."""
    __tablename__ = "habit_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    area: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)     # health | productivity | mindset | sport
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")
    cue: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reward: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True)             # системный шаблон vs пользовательский
    tags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)         # list[str]
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CoachingSession(Base):
    """Лог coaching-диалогов (сессии с ИИ-коучем)."""
    __tablename__ = "coaching_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    session_type: Mapped[str] = mapped_column(String(30))                      # checkin | review | goal_creation | free | onboarding
    intent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)   # detected intent
    outcome: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # goal_created | habit_logged | review_done | etc
    entities: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)     # извлечённые сущности
    user_satisfaction: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5 (если указал)
    duration_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CoachingInsight(Base):
    """AI-инсайт по пользователю (наблюдение, риск, паттерн)."""
    __tablename__ = "coaching_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    insight_type: Mapped[str] = mapped_column(String(30))                      # risk | pattern | achievement | recommendation
    severity: Mapped[str] = mapped_column(String(20), default="info")          # critical | high | medium | low | info
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_modules: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True) # list[str] модулей-источников
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_actioned: Mapped[bool] = mapped_column(Boolean, default=False)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserCoachingProfile(Base):
    """Настройки пользователя для коуча (1 запись на пользователя)."""
    __tablename__ = "user_coaching_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), unique=True)
    coach_tone: Mapped[str] = mapped_column(String(20), default="friendly")    # strict | friendly | motivational | soft
    coaching_mode: Mapped[str] = mapped_column(String(20), default="standard") # soft | standard | active
    preferred_checkin_time: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # "20:00"
    preferred_review_day: Mapped[str] = mapped_column(String(10), default="sunday")
    morning_brief_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    evening_reflection_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    max_daily_nudges: Mapped[int] = mapped_column(Integer, default=3)          # антиспам: макс nudges в день
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    focus_areas: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # list[str] приоритетных областей
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CoachingRecommendation(Base):
    """Очередь персональных рекомендаций коуча."""
    __tablename__ = "coaching_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    rec_type: Mapped[str] = mapped_column(String(50))                          # schedule_fix | goal_decompose | workload_reduce | etc
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)                  # 1=наивысший, 5=низший
    action_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True) # тип действия для клиента
    action_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # payload для action
    source_modules: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # list[str]
    acted_on: Mapped[bool] = mapped_column(Boolean, default=False)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CoachingMemory(Base):
    """Долгосрочная память коуча о пользователе."""
    __tablename__ = "coaching_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    memory_type: Mapped[str] = mapped_column(String(30))                       # preference | pattern | fact | correction
    key: Mapped[str] = mapped_column(String(100))                              # morning_person | best_engagement_time | etc
    value: Mapped[str] = mapped_column(Text)                                   # значение в текстовом виде
    confidence: Mapped[float] = mapped_column(Float, default=0.5)             # 0.0-1.0
    evidence_count: Mapped[int] = mapped_column(Integer, default=1)            # сколько раз подтверждено
    is_explicit: Mapped[bool] = mapped_column(Boolean, default=False)          # явно указал пользователь
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_coaching_memory_user_key"),)


class BehaviorPattern(Base):
    """Поведенческие паттерны пользователя (выводы коуча)."""
    __tablename__ = "behavior_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    pattern_type: Mapped[str] = mapped_column(String(50))                      # overcommits | morning_person | streak_dependent | etc
    description: Mapped[str] = mapped_column(Text)
    frequency: Mapped[str] = mapped_column(String(20), default="sometimes")    # always | often | sometimes | rarely
    affected_areas: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True) # list[str]
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CoachingNudgeLog(Base):
    """Лог отправленных proactive-сообщений (для антиспама и аналитики)."""
    __tablename__ = "coaching_nudges_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    nudge_type: Mapped[str] = mapped_column(String(50))                        # no_checkin_3days | goal_achieved | etc
    channel: Mapped[str] = mapped_column(String(20), default="telegram")       # telegram | push
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    opened: Mapped[bool] = mapped_column(Boolean, default=False)
    acted_on: Mapped[bool] = mapped_column(Boolean, default=False)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    response_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # positive | negative | ignored


class CoachingOnboardingState(Base):
    """Прогресс онбординга пользователя (1 запись на пользователя)."""
    __tablename__ = "coaching_onboarding_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), unique=True)
    current_step: Mapped[int] = mapped_column(Integer, default=0)              # текущий шаг
    steps_completed: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # list[str]
    first_goal_created: Mapped[bool] = mapped_column(Boolean, default=False)
    first_habit_created: Mapped[bool] = mapped_column(Boolean, default=False)
    first_checkin_done: Mapped[bool] = mapped_column(Boolean, default=False)
    bot_onboarding_done: Mapped[bool] = mapped_column(Boolean, default=False)
    mini_app_onboarding_done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CoachingDialogDraft(Base):
    """Черновик многошагового диалога (незавершённый flow)."""
    __tablename__ = "coaching_dialog_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    draft_type: Mapped[str] = mapped_column(String(50))                        # goal_creation | habit_creation | checkin | review
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)      # накопленные данные диалога
    step: Mapped[int] = mapped_column(Integer, default=0)                      # текущий шаг flow
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CoachingContextSnapshot(Base):
    """Ежедневный снимок контекста пользователя для proactive-логики."""
    __tablename__ = "coaching_context_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    snapshot_date: Mapped[date] = mapped_column(Date)
    tasks_overdue: Mapped[int] = mapped_column(Integer, default=0)
    tasks_completed_today: Mapped[int] = mapped_column(Integer, default=0)
    calendar_events_today: Mapped[int] = mapped_column(Integer, default=0)
    free_slots_today: Mapped[int] = mapped_column(Integer, default=0)          # кол-во свободных слотов >30мин
    habits_done_today: Mapped[int] = mapped_column(Integer, default=0)
    habits_total_today: Mapped[int] = mapped_column(Integer, default=0)
    stuck_goals: Mapped[int] = mapped_column(Integer, default=0)               # целей без прогресса >7 дней
    streak_at_risk: Mapped[int] = mapped_column(Integer, default=0)            # привычек, где стрик под угрозой
    overall_state: Mapped[str] = mapped_column(String(20), default="stable")   # momentum | stable | overload | recovery | risk
    score: Mapped[int] = mapped_column(Integer, default=75)                    # итоговый скор 0-100
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "snapshot_date", name="uq_snapshot_user_date"),)


class CoachingRiskScore(Base):
    """Оценка рисков для пользователя по типам."""
    __tablename__ = "coaching_risk_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    risk_type: Mapped[str] = mapped_column(String(30))                         # dropout | overload | goal_failure | habit_death
    score: Mapped[float] = mapped_column(Float, default=0.0)                   # 0.0-1.0
    factors: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)      # dict с компонентами скора
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "risk_type", name="uq_risk_user_type"),)


class CoachingOrchestrationAction(Base):
    """Лог действий коуча в других модулях (с подтверждением пользователя)."""
    __tablename__ = "coaching_orchestration_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    action_type: Mapped[str] = mapped_column(String(50))                       # create_task | create_event | update_reminder
    target_module: Mapped[str] = mapped_column(String(30))                     # tasks | calendar | reminders
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)      # данные для создания/обновления
    status: Mapped[str] = mapped_column(String(20), default="pending")         # pending | confirmed | executed | rejected
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())





# ==============================================================================
# Auth / Multi-user - Workspace, Membership, ExternalIdentity
# ==============================================================================

class Workspace(Base):
    """Рабочее пространство - изолированное пространство для данных."""
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    owner_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    memberships: Mapped[List["Membership"]] = relationship(back_populates="workspace")


class Membership(Base):
    """Членство пользователя в workspace с ролью."""
    __tablename__ = "memberships"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), index=True)
    workspace_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), ForeignKey("workspaces.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    status: Mapped[str] = mapped_column(String(20), default="active")
    invited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="memberships")
    workspace: Mapped["Workspace"] = relationship(back_populates="memberships")

    __table_args__ = (UniqueConstraint("user_id", "workspace_id", name="uq_membership_user_workspace"),)


class ExternalIdentity(Base):
    """Внешняя идентичность - связь Telegram/email/google с пользователем."""
    __tablename__ = "external_identities"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    provider_id: Mapped[str] = mapped_column(String(255))
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    user: Mapped["User"] = relationship(back_populates="external_identities")

    __table_args__ = (UniqueConstraint("provider", "provider_id", name="uq_external_identity"),)

# ==============================================================================
# Research домен - сбор, парсинг и анализ данных из интернета
# ==============================================================================



class ResearchJob(Base):
    """Задача исследования - основная сущность Research домена."""
    __tablename__ = "research_jobs"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[Optional[str]] = mapped_column(PG_UUID(as_uuid=False), nullable=True, index=True)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    original_request: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    normalized_spec: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    job_type: Mapped[str] = mapped_column(String(20), default="search")
    provider: Mapped[str] = mapped_column(String(30), default="firecrawl")
    config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), default="private")
    origin: Mapped[str] = mapped_column(String(10), default="chat")
    usage_estimate: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    tags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    runs: Mapped[List["ResearchJobRun"]] = relationship(back_populates="job")
    results: Mapped[List["ResearchResultItem"]] = relationship(back_populates="job")
    sources: Mapped[List["ResearchSource"]] = relationship(back_populates="job")
    message_logs: Mapped[List["ResearchMessageLog"]] = relationship(back_populates="job")
    status_events: Mapped[List["ResearchStatusEvent"]] = relationship(back_populates="job")


class ResearchJobRun(Base):
    """Запуск задачи - каждый run фиксирует одну попытку выполнения."""
    __tablename__ = "research_job_runs"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), ForeignKey("research_jobs.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metrics: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    usage_actual: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped["ResearchJob"] = relationship(back_populates="runs")
    results: Mapped[List["ResearchResultItem"]] = relationship(back_populates="run")


class ResearchResultItem(Base):
    """Отдельный найденный элемент - строка результата задачи."""
    __tablename__ = "research_result_items"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), ForeignKey("research_jobs.id"), index=True)
    run_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), ForeignKey("research_job_runs.id"), index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_fields: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    dedupe_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped["ResearchJob"] = relationship(back_populates="results")
    run: Mapped["ResearchJobRun"] = relationship(back_populates="results")


class ResearchSource(Base):
    """Источник данных для задачи - seed URL, найденный URL или результат поиска."""
    __tablename__ = "research_sources"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), ForeignKey("research_jobs.id"), index=True)
    url: Mapped[str] = mapped_column(String(2048))
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), default="seed")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    job: Mapped["ResearchJob"] = relationship(back_populates="sources")


class ResearchMessageLog(Base):
    """Лог сообщений агента по задаче - история диалога."""
    __tablename__ = "research_message_logs"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), ForeignKey("research_jobs.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped["ResearchJob"] = relationship(back_populates="message_logs")


class ResearchStatusEvent(Base):
    """Событие смены статуса задачи - для аудита и timeline."""
    __tablename__ = "research_status_events"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), ForeignKey("research_jobs.id"), index=True)
    run_id: Mapped[Optional[str]] = mapped_column(PG_UUID(as_uuid=False), ForeignKey("research_job_runs.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(30))
    old_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    actor_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped["ResearchJob"] = relationship(back_populates="status_events")
