"""
REST API роутер для модуля питания (/api/nutrition).
Все операции изолированы по user_id текущего пользователя.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.models import User
from db import nutrition_storage as ns

router = APIRouter(prefix="/nutrition", tags=["nutrition"])


# ── Pydantic-схемы ────────────────────────────────────────────────────────────

class FoodItemOut(BaseModel):
    """Продукт из справочника (КБЖУ на 100г)."""
    id: int
    name: str
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carbs_g: Optional[float] = None
    serving_size_g: Optional[float] = None


class MealItemOut(BaseModel):
    """Позиция в приёме пищи (КБЖУ рассчитаны на порцию)."""
    id: int
    food_item_id: int
    name: str
    amount_g: float
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float


class MealOut(BaseModel):
    """Приём пищи с позициями и итогами."""
    id: int
    meal_type: str
    eaten_at: Optional[str] = None
    notes: str = ""
    items: List[MealItemOut] = []
    total_calories: float = 0
    total_protein: float = 0
    total_fat: float = 0
    total_carbs: float = 0
    created_at: Optional[str] = None


class MealItemCreate(BaseModel):
    """Позиция для создания приёма пищи (КБЖУ на порцию)."""
    name: str
    amount_g: float = 100
    calories: float = 0
    protein_g: float = 0
    fat_g: float = 0
    carbs_g: float = 0


class MealCreateDto(BaseModel):
    """DTO создания приёма пищи."""
    meal_type: str = Field(..., pattern="^(breakfast|lunch|dinner|snack)$")
    eaten_at: Optional[datetime] = None  # если не указано — текущее время
    items: List[MealItemCreate]
    notes: str = ""


class MealUpdateDto(BaseModel):
    """DTO обновления позиций приёма пищи."""
    items: List[MealItemCreate]


class WaterLogDto(BaseModel):
    """DTO логирования воды."""
    amount_ml: int = Field(..., gt=0, le=5000)


class WaterOut(BaseModel):
    """Ответ при логировании воды."""
    id: int
    amount_ml: int
    logged_at: Optional[str] = None


class NutritionGoalOut(BaseModel):
    """Текущие цели по питанию."""
    calories: Optional[int] = None
    protein_g: Optional[int] = None
    fat_g: Optional[int] = None
    carbs_g: Optional[int] = None
    water_ml: int = 2000
    goal_type: Optional[str] = None         # lose / maintain / gain
    activity_level: Optional[str] = None    # sedentary / light / moderate / active / very_active


class NutritionGoalUpdate(BaseModel):
    """DTO обновления целей (передаются только изменяемые поля)."""
    calories: Optional[int] = None
    protein_g: Optional[int] = None
    fat_g: Optional[int] = None
    carbs_g: Optional[int] = None
    water_ml: Optional[int] = None
    goal_type: Optional[str] = None         # lose / maintain / gain
    activity_level: Optional[str] = None    # sedentary / light / moderate / active / very_active


class FoodItemWithFav(BaseModel):
    """Продукт с флагом избранного."""
    id: int
    name: str
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carbs_g: Optional[float] = None
    serving_size_g: Optional[float] = None
    is_favorite: bool = False


class ProfileOut(BaseModel):
    """Параметры тела пользователя."""
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    age: Optional[int] = None
    gender: Optional[str] = None    # male / female


class ProfileUpdate(BaseModel):
    """DTO обновления параметров тела."""
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    age: Optional[int] = None
    gender: Optional[str] = None


class GoalsCalculateRequest(BaseModel):
    """Запрос на авто-расчёт целей по профилю."""
    goal_type: str = Field(..., description="lose / maintain / gain")
    activity_level: str = Field(..., description="sedentary / light / moderate / active / very_active")
    weight_kg: float = Field(..., gt=0)
    height_cm: float = Field(..., gt=0)
    age: int = Field(..., gt=0, le=120)
    gender: str = Field(..., description="male / female")
    water_ml: int = Field(default=2000, ge=0)


class TemplateItemDto(BaseModel):
    """Позиция шаблона для создания."""
    food_item_id: int
    amount_g: float


class TemplateCreateDto(BaseModel):
    """DTO создания шаблона."""
    name: str = Field(..., min_length=1, max_length=200)
    meal_type: str = "snack"
    items: list[TemplateItemDto]


class TemplateFromMealDto(BaseModel):
    """DTO создания шаблона из существующего приёма пищи."""
    meal_id: int
    name: str = Field(..., min_length=1, max_length=200)


class GoalsCalculateResponse(BaseModel):
    """Рассчитанные целевые КБЖУ."""
    calories: int
    protein_g: int
    fat_g: int
    carbs_g: int
    water_ml: int


class TotalsOut(BaseModel):
    """Суммарные КБЖУ за день."""
    calories: float = 0
    protein_g: float = 0
    fat_g: float = 0
    carbs_g: float = 0


class DaySummaryOut(BaseModel):
    """Полная сводка за день."""
    date: str
    goals: Optional[NutritionGoalOut] = None
    totals: TotalsOut
    water_ml: int = 0
    meals: List[MealOut] = []


class StatsOut(BaseModel):
    """Агрегированная статистика за период."""
    period: str
    days: int
    avg_calories: float
    avg_protein: float
    avg_fat: float
    avg_carbs: float
    avg_water: float
    daily: List[DaySummaryOut] = []


# ── Эндпоинты ─────────────────────────────────────────────────────────────────

@router.get("/today", response_model=DaySummaryOut)
async def get_today_summary(user: User = Depends(get_current_user)):
    """Сводка по питанию за сегодня."""
    today = date.today()
    # Делегируем в storage — возвращает готовый dict
    return await ns.get_nutrition_summary(user.telegram_id, today)


@router.get("/meals", response_model=List[MealOut])
async def get_meals(
    date_from: date = Query(..., description="Начало периода (YYYY-MM-DD)"),
    date_to: date = Query(..., description="Конец периода (YYYY-MM-DD)"),
    user: User = Depends(get_current_user),
):
    """Список приёмов пищи за период."""
    # Конвертируем date → datetime (начало/конец дня) с UTC
    dt_from = datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc)
    dt_to = datetime.combine(date_to, datetime.max.time(), tzinfo=timezone.utc)
    return await ns.get_meals_by_date(user.telegram_id, dt_from, dt_to)


@router.get("/meal/{meal_id}", response_model=MealOut)
async def get_meal(meal_id: int, user: User = Depends(get_current_user)):
    """Приём пищи по ID."""
    result = await ns.get_meal(meal_id, user.telegram_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Приём пищи не найден")
    return result


@router.post("/meal", response_model=MealOut, status_code=status.HTTP_201_CREATED)
async def create_meal(dto: MealCreateDto, user: User = Depends(get_current_user)):
    """Создание приёма пищи (ручное из MiniApp)."""
    # Используем текущее время если не указано
    eaten_at = dto.eaten_at or datetime.now(timezone.utc)
    # Конвертируем Pydantic-модели в dict для storage
    items = [item.model_dump() for item in dto.items]
    return await ns.add_meal(
        user_id=user.telegram_id,
        meal_type=dto.meal_type,
        eaten_at=eaten_at,
        items=items,
        notes=dto.notes,
    )


@router.put("/meal/{meal_id}", response_model=MealOut)
async def update_meal(
    meal_id: int,
    dto: MealUpdateDto,
    user: User = Depends(get_current_user),
):
    """Обновление позиций приёма пищи."""
    items = [item.model_dump() for item in dto.items]
    result = await ns.update_meal_items(meal_id, user.telegram_id, items)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Приём пищи не найден")
    return result


@router.delete("/meal/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal(meal_id: int, user: User = Depends(get_current_user)):
    """Удаление приёма пищи."""
    deleted = await ns.delete_meal(meal_id, user.telegram_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Приём пищи не найден")


@router.post("/water", response_model=WaterOut)
async def log_water(dto: WaterLogDto, user: User = Depends(get_current_user)):
    """Логирование потребления воды."""
    return await ns.add_water(user.telegram_id, dto.amount_ml)


@router.get("/water")
async def get_water(
    date: date = Query(default=None, description="Дата (YYYY-MM-DD), по умолчанию сегодня"),
    user: User = Depends(get_current_user),
):
    """Потребление воды за день."""
    target = date or __import__("datetime").date.today()
    total_ml = await ns.get_water_for_date(user.telegram_id, target)
    return {"date": target.isoformat(), "total_ml": total_ml}


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    period: str = Query("week", pattern="^(week|month)$"),
    user: User = Depends(get_current_user),
):
    """Агрегированная статистика за неделю или месяц."""
    from datetime import timedelta
    today = date.today()
    # Определяем количество дней для агрегации
    days_count = 7 if period == "week" else 30

    # Собираем сводку за каждый день
    daily = []
    total_cal, total_p, total_f, total_c, total_w = 0, 0, 0, 0, 0
    for i in range(days_count):
        d = today - timedelta(days=i)
        summary = await ns.get_nutrition_summary(user.telegram_id, d)
        daily.append(summary)
        # Суммируем для средних
        total_cal += summary["totals"]["calories"]
        total_p += summary["totals"]["protein_g"]
        total_f += summary["totals"]["fat_g"]
        total_c += summary["totals"]["carbs_g"]
        total_w += summary["water_ml"]

    # Считаем средние
    return StatsOut(
        period=period,
        days=days_count,
        avg_calories=round(total_cal / days_count, 1),
        avg_protein=round(total_p / days_count, 1),
        avg_fat=round(total_f / days_count, 1),
        avg_carbs=round(total_c / days_count, 1),
        avg_water=round(total_w / days_count, 1),
        daily=daily,
    )


@router.get("/goals", response_model=NutritionGoalOut)
async def get_goals(user: User = Depends(get_current_user)):
    """Текущие цели по питанию."""
    goals = await ns.get_goals(user.telegram_id)
    if not goals:
        # Возвращаем дефолтные цели
        return NutritionGoalOut(calories=2000, protein_g=120, fat_g=65, carbs_g=250, water_ml=2000)
    return goals


@router.put("/goals", response_model=NutritionGoalOut)
async def update_goals(dto: NutritionGoalUpdate, user: User = Depends(get_current_user)):
    """Обновление целей по питанию."""
    return await ns.set_goals(
        user_id=user.telegram_id,
        calories=dto.calories,
        protein_g=dto.protein_g,
        fat_g=dto.fat_g,
        carbs_g=dto.carbs_g,
        water_ml=dto.water_ml,
        goal_type=dto.goal_type,
        activity_level=dto.activity_level,
    )


# ── Шаблоны приёмов пищи ───────────────────────────────────────────────────


@router.get("/templates")
async def get_templates(user: User = Depends(get_current_user)):
    """Список шаблонов пользователя."""
    return await ns.list_templates(user.telegram_id)


@router.post("/templates", status_code=status.HTTP_201_CREATED)
async def create_template(dto: TemplateCreateDto, user: User = Depends(get_current_user)):
    """Создать шаблон из списка продуктов."""
    items = [{"food_item_id": i.food_item_id, "amount_g": i.amount_g} for i in dto.items]
    return await ns.create_template(user.telegram_id, dto.name, dto.meal_type, items)


@router.post("/templates/from-meal", status_code=status.HTTP_201_CREATED)
async def create_template_from_meal(dto: TemplateFromMealDto, user: User = Depends(get_current_user)):
    """Создать шаблон из существующего приёма пищи."""
    result = await ns.create_template_from_meal(user.telegram_id, dto.meal_id, dto.name)
    if not result:
        raise HTTPException(status_code=404, detail="Приём пищи не найден")
    return result


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(template_id: int, user: User = Depends(get_current_user)):
    """Удалить шаблон."""
    deleted = await ns.delete_template(template_id, user.telegram_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Шаблон не найден")


@router.post("/templates/{template_id}/apply")
async def apply_template(template_id: int, user: User = Depends(get_current_user)):
    """Применить шаблон — создать приём пищи из шаблона."""
    result = await ns.apply_template(template_id, user.telegram_id)
    if not result:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    return result


# ── Смарт-повтор (предложения) ─────────────────────────────────────────────


@router.get("/suggestions")
async def get_suggestions(
    meal_type: Optional[str] = Query(None, description="breakfast/lunch/dinner/snack"),
    user: User = Depends(get_current_user),
):
    """Частые продукты и последние приёмы пищи для предложений.
    Если для конкретного meal_type данных нет — возвращаем общие (без фильтра)."""
    # Сначала ищем по конкретному типу приёма
    frequent = await ns.get_frequent_foods(user.telegram_id, meal_type=meal_type, limit=5)
    recent = await ns.get_recent_meals(user.telegram_id, meal_type=meal_type, limit=3)
    # Если по типу пусто — fallback на общие данные без фильтра
    if not frequent and meal_type:
        frequent = await ns.get_frequent_foods(user.telegram_id, meal_type=None, limit=5)
    if not recent and meal_type:
        recent = await ns.get_recent_meals(user.telegram_id, meal_type=None, limit=3)
    return {"frequent_foods": frequent, "recent_meals": recent}


# ── Избранные продукты ─────────────────────────────────────────────────────


@router.get("/favorites", response_model=List[FoodItemWithFav])
async def get_favorites(user: User = Depends(get_current_user)):
    """Список избранных продуктов пользователя."""
    return await ns.list_favorites(user.telegram_id)


@router.post("/favorites/{food_item_id}")
async def toggle_favorite(food_item_id: int, user: User = Depends(get_current_user)):
    """Добавить/убрать продукт из избранного (toggle)."""
    added = await ns.toggle_favorite(user.telegram_id, food_item_id)
    return {"food_item_id": food_item_id, "is_favorite": added}


# ── Профиль (параметры тела) ───────────────────────────────────────────────


@router.get("/profile", response_model=ProfileOut)
async def get_profile(user: User = Depends(get_current_user)):
    """Получить параметры тела пользователя."""
    profile = await ns.get_profile(user.telegram_id)
    if not profile:
        return ProfileOut()  # пустой профиль
    return profile


@router.put("/profile", response_model=ProfileOut)
async def update_profile(dto: ProfileUpdate, user: User = Depends(get_current_user)):
    """Обновить параметры тела пользователя."""
    return await ns.update_profile(
        user_id=user.telegram_id,
        weight_kg=dto.weight_kg,
        height_cm=dto.height_cm,
        age=dto.age,
        gender=dto.gender,
    )


@router.post("/goals/calculate", response_model=GoalsCalculateResponse)
async def calculate_goals(dto: GoalsCalculateRequest, user: User = Depends(get_current_user)):
    """
    Авто-расчёт целевых КБЖУ по параметрам тела и цели.
    НЕ сохраняет — возвращает рассчитанные значения для предпросмотра.
    """
    from services.nutrition_calc import calculate_full
    targets = calculate_full(
        weight_kg=dto.weight_kg,
        height_cm=dto.height_cm,
        age=dto.age,
        gender=dto.gender,
        activity_level=dto.activity_level,
        goal_type=dto.goal_type,
        water_ml=dto.water_ml,
    )
    return GoalsCalculateResponse(
        calories=targets.calories,
        protein_g=targets.protein_g,
        fat_g=targets.fat_g,
        carbs_g=targets.carbs_g,
        water_ml=targets.water_ml,
    )


@router.get("/food/search", response_model=List[FoodItemWithFav])
async def search_food(
    q: str = Query(..., min_length=1, max_length=100, description="Поисковый запрос"),
    user: User = Depends(get_current_user),
):
    """Поиск продуктов по названию."""
    results = await ns.search_food(q, user_id=user.telegram_id)
    # Добавляем флаг is_favorite к результатам
    fav_ids = await ns.get_favorite_ids(user.telegram_id)
    return [
        {**r, "is_favorite": r["id"] in fav_ids}
        for r in results
    ]


# ── Score / Remaining / Weekly Summary ────────────────────────────────────────

@router.get("/score")
async def get_daily_score(
    target_date: Optional[date] = Query(None, description="Дата в формате YYYY-MM-DD (по умолчанию — сегодня)"),
    user: User = Depends(get_current_user),
):
    """Оценка дня по питанию (score 0-100) с разбивкой по компонентам."""
    from services.nutrition_score import calculate_daily_score
    d = target_date or date.today()
    return await calculate_daily_score(user.telegram_id, d)


@router.get("/remaining")
async def get_remaining_today(
    user: User = Depends(get_current_user),
):
    """Остаток КБЖУ на сегодня (разница между целями и съеденным)."""
    today = date.today()
    summary = await ns.get_nutrition_summary(user.telegram_id, today)
    goals = summary.get("goals") or {}
    totals = summary.get("totals", {})
    water_ml = summary.get("water_ml", 0)

    if not goals or not goals.get("calories"):
        raise HTTPException(status_code=400, detail="Цели по КБЖУ не установлены.")

    return {
        "date": str(today),
        "remaining": {
            "calories": max(0, goals["calories"] - totals.get("calories", 0)),
            "protein_g": max(0, (goals.get("protein_g") or 0) - totals.get("protein_g", 0)),
            "fat_g": max(0, (goals.get("fat_g") or 0) - totals.get("fat_g", 0)),
            "carbs_g": max(0, (goals.get("carbs_g") or 0) - totals.get("carbs_g", 0)),
            "water_ml": max(0, (goals.get("water_ml") or 0) - water_ml),
        },
        "eaten": totals,
        "goals": goals,
        "progress_pct": round(totals.get("calories", 0) / goals["calories"] * 100) if goals["calories"] else 0,
    }


@router.get("/weekly-summary")
async def get_weekly_summary(
    user: User = Depends(get_current_user),
):
    """Недельный AI-обзор питания с рекомендациями."""
    from services.nutrition_weekly_summary import generate_weekly_summary
    return await generate_weekly_summary(user.telegram_id)
