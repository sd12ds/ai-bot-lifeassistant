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


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


# ══════════════════════════════════════════════════════════════════════════════
# Системные таблицы
# ══════════════════════════════════════════════════════════════════════════════

class User(Base):
    """Пользователь бота — идентифицируется по telegram_id."""
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    mode: Mapped[str] = mapped_column(String(20), default="personal")          # personal | business
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")
    notification_offset_min: Mapped[int] = mapped_column(Integer, default=15)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Связи
    profile: Mapped[Optional["UserProfile"]] = relationship(back_populates="user", uselist=False)
    tasks: Mapped[List["Task"]] = relationship(back_populates="user")
    reminders: Mapped[List["Reminder"]] = relationship(back_populates="user")
    calendars: Mapped[List["Calendar"]] = relationship(back_populates="user")


class UserProfile(Base):
    """Профиль пользователя — дополнительные данные."""
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
    """Задача или событие. event_type='task' — дедлайн, 'event' — временной слот."""
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
    """Справочник продуктов питания. user_id=None — системный справочник."""
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
    """Справочник упражнений. user_id=None — системный справочник."""
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
    activity_type: Mapped[str] = mapped_column(String(30))                     # steps | run | walk | cycling | swimming | other
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
