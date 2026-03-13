"""
CRUD-операции для модуля питания.
Работает через SQLAlchemy async (PostgreSQL).
"""
from __future__ import annotations

from datetime import datetime, date, timedelta, time
from typing import Optional

from sqlalchemy import select, and_, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import DEFAULT_TZ
from db.models import FoodItem, Meal, MealItem, WaterLog, NutritionGoal
from db.session import AsyncSessionLocal


# ── Вспомогательные конвертеры ────────────────────────────────────────────────

def _food_item_to_dict(f: FoodItem) -> dict:
    """Конвертирует FoodItem ORM → dict."""
    return {
        "id": f.id,
        "user_id": f.user_id,
        "name": f.name,
        "calories": f.calories,      # ккал на 100г
        "protein_g": f.protein_g,
        "fat_g": f.fat_g,
        "carbs_g": f.carbs_g,
        "fiber_g": f.fiber_g,
        "barcode": f.barcode,
        "serving_size_g": f.serving_size_g,  # размер порции по умолчанию
    }


def _meal_item_to_dict(mi: MealItem) -> dict:
    """Конвертирует MealItem ORM → dict с расчётом КБЖУ по граммовке."""
    food = mi.food_item
    # Рассчитываем КБЖУ пропорционально граммовке (данные в FoodItem на 100г)
    ratio = mi.amount_g / 100.0 if mi.amount_g else 0
    return {
        "id": mi.id,
        "food_item_id": mi.food_item_id,
        "name": food.name if food else "Неизвестно",
        "amount_g": mi.amount_g,
        "calories": round((food.calories or 0) * ratio, 1),
        "protein_g": round((food.protein_g or 0) * ratio, 1),
        "fat_g": round((food.fat_g or 0) * ratio, 1),
        "carbs_g": round((food.carbs_g or 0) * ratio, 1),
    }


def _meal_to_dict(m: Meal) -> dict:
    """Конвертирует Meal ORM → dict с вложенными items и итогами."""
    items = [_meal_item_to_dict(mi) for mi in (m.items or [])]
    # Суммируем КБЖУ по всем позициям
    total_cal = sum(i["calories"] for i in items)
    total_p = sum(i["protein_g"] for i in items)
    total_f = sum(i["fat_g"] for i in items)
    total_c = sum(i["carbs_g"] for i in items)
    return {
        "id": m.id,
        "user_id": m.user_id,
        "meal_type": m.meal_type,
        "eaten_at": m.eaten_at.isoformat() if m.eaten_at else None,
        "notes": m.notes or "",
        "items": items,
        "total_calories": round(total_cal, 1),
        "total_protein": round(total_p, 1),
        "total_fat": round(total_f, 1),
        "total_carbs": round(total_c, 1),
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _to_per_100g(value: float, amount_g: float) -> float:
    """Конвертирует значение КБЖУ с порции на 100г."""
    if amount_g <= 0:
        return value  # если граммовка невалидная — возвращаем как есть
    return round(value / amount_g * 100, 2)


def _day_range(target_date: date) -> tuple[datetime, datetime]:
    """Возвращает timezone-aware границы дня (начало, конец) для PG-запросов."""
    day_start = datetime.combine(target_date, time.min, tzinfo=DEFAULT_TZ)
    day_end = day_start + timedelta(days=1)
    return day_start, day_end


# ── FoodItem — справочник продуктов ───────────────────────────────────────────

async def search_food(query: str, user_id: int | None = None, limit: int = 10) -> list[dict]:
    """Поиск продуктов по названию (системные + пользовательские)."""
    async with AsyncSessionLocal() as session:
        # Ищем по ILIKE (регистронезависимый поиск)
        conditions = [FoodItem.name.ilike(f"%{query}%")]
        # Системные (user_id IS NULL) + принадлежащие пользователю
        user_filter = FoodItem.user_id.is_(None)
        if user_id:
            user_filter = user_filter | (FoodItem.user_id == user_id)
        conditions.append(user_filter)

        stmt = (
            select(FoodItem)
            .where(and_(*conditions))
            .order_by(FoodItem.name)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [_food_item_to_dict(f) for f in result.scalars().all()]


async def _get_or_create_food_item_in_session(
    session: AsyncSession,
    name: str,
    calories_per100: float = 0,
    protein_per100: float = 0,
    fat_per100: float = 0,
    carbs_per100: float = 0,
    user_id: int | None = None,
) -> int:
    """Находит продукт по имени или создаёт. Работает внутри переданной сессии.
    КБЖУ должны быть уже пересчитаны на 100г.
    """
    # Сначала ищем точное совпадение (без учёта регистра)
    stmt = select(FoodItem).where(
        func.lower(FoodItem.name) == name.lower()
    ).limit(1)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        return existing.id

    # Создаём пользовательский продукт
    food = FoodItem(
        user_id=user_id,
        name=name,
        calories=calories_per100,
        protein_g=protein_per100,
        fat_g=fat_per100,
        carbs_g=carbs_per100,
    )
    session.add(food)
    await session.flush()  # Получаем id без коммита
    return food.id


async def get_or_create_food_item(
    name: str,
    calories: float = 0,
    protein_g: float = 0,
    fat_g: float = 0,
    carbs_g: float = 0,
    user_id: int | None = None,
) -> int:
    """Публичная обёртка: открывает свою сессию. КБЖУ — на 100г."""
    async with AsyncSessionLocal() as session:
        food_id = await _get_or_create_food_item_in_session(
            session, name, calories, protein_g, fat_g, carbs_g, user_id,
        )
        await session.commit()
        return food_id


# ── Meal — приёмы пищи ────────────────────────────────────────────────────────

async def add_meal(
    user_id: int,
    meal_type: str,
    eaten_at: datetime,
    items: list[dict],
    notes: str = "",
) -> dict:
    """
    Создаёт приём пищи с позициями. Все операции в одной транзакции.
    items: [{"name": str, "amount_g": float, "calories": float,
             "protein_g": float, "fat_g": float, "carbs_g": float}, ...]
    ВАЖНО: calories/protein/fat/carbs — на ПОРЦИЮ (не на 100г).
    Функция сама пересчитывает на 100г для хранения в FoodItem.
    """
    async with AsyncSessionLocal() as session:
        # Создаём Meal
        meal = Meal(
            user_id=user_id,
            meal_type=meal_type,
            eaten_at=eaten_at,
            notes=notes,
        )
        session.add(meal)
        await session.flush()  # Получаем meal.id

        # Создаём MealItem для каждой позиции (одна транзакция)
        for item_data in items:
            amount_g = item_data.get("amount_g", 100)
            # Пересчитываем КБЖУ с порции на 100г для хранения в FoodItem
            food_id = await _get_or_create_food_item_in_session(
                session=session,
                name=item_data["name"],
                calories_per100=_to_per_100g(item_data.get("calories", 0), amount_g),
                protein_per100=_to_per_100g(item_data.get("protein_g", 0), amount_g),
                fat_per100=_to_per_100g(item_data.get("fat_g", 0), amount_g),
                carbs_per100=_to_per_100g(item_data.get("carbs_g", 0), amount_g),
                user_id=user_id,
            )
            meal_item = MealItem(
                meal_id=meal.id,
                food_item_id=food_id,
                amount_g=amount_g,
            )
            session.add(meal_item)

        await session.commit()

        # Перезагружаем с items для полного ответа
        stmt = (
            select(Meal)
            .options(selectinload(Meal.items).selectinload(MealItem.food_item))
            .where(Meal.id == meal.id)
        )
        result = await session.execute(stmt)
        return _meal_to_dict(result.scalar_one())


async def get_meals_by_date(
    user_id: int,
    date_from: datetime,
    date_to: datetime,
) -> list[dict]:
    """Возвращает все приёмы пищи за указанный период."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Meal)
            .options(selectinload(Meal.items).selectinload(MealItem.food_item))
            .where(
                and_(
                    Meal.user_id == user_id,
                    Meal.eaten_at >= date_from,
                    Meal.eaten_at < date_to,
                )
            )
            .order_by(Meal.eaten_at)
        )
        result = await session.execute(stmt)
        return [_meal_to_dict(m) for m in result.scalars().all()]


async def get_meal(meal_id: int, user_id: int) -> dict | None:
    """Возвращает приём пищи по ID (проверяет принадлежность пользователю)."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Meal)
            .options(selectinload(Meal.items).selectinload(MealItem.food_item))
            .where(and_(Meal.id == meal_id, Meal.user_id == user_id))
        )
        result = await session.execute(stmt)
        meal = result.scalar_one_or_none()
        return _meal_to_dict(meal) if meal else None


async def delete_meal(meal_id: int, user_id: int) -> bool:
    """Удаляет приём пищи. Возвращает True если удалён."""
    async with AsyncSessionLocal() as session:
        stmt = delete(Meal).where(
            and_(Meal.id == meal_id, Meal.user_id == user_id)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def update_meal_items(
    meal_id: int,
    user_id: int,
    items: list[dict],
) -> dict | None:
    """Заменяет позиции приёма пищи на новые. Одна транзакция."""
    async with AsyncSessionLocal() as session:
        # Проверяем что meal принадлежит пользователю
        stmt = select(Meal).where(and_(Meal.id == meal_id, Meal.user_id == user_id))
        result = await session.execute(stmt)
        meal = result.scalar_one_or_none()
        if not meal:
            return None

        # Удаляем старые позиции
        await session.execute(
            delete(MealItem).where(MealItem.meal_id == meal_id)
        )

        # Добавляем новые (одна транзакция)
        for item_data in items:
            amount_g = item_data.get("amount_g", 100)
            food_id = await _get_or_create_food_item_in_session(
                session=session,
                name=item_data["name"],
                calories_per100=_to_per_100g(item_data.get("calories", 0), amount_g),
                protein_per100=_to_per_100g(item_data.get("protein_g", 0), amount_g),
                fat_per100=_to_per_100g(item_data.get("fat_g", 0), amount_g),
                carbs_per100=_to_per_100g(item_data.get("carbs_g", 0), amount_g),
                user_id=user_id,
            )
            mi = MealItem(
                meal_id=meal_id,
                food_item_id=food_id,
                amount_g=amount_g,
            )
            session.add(mi)

        await session.commit()

        # Возвращаем обновлённый meal
        stmt = (
            select(Meal)
            .options(selectinload(Meal.items).selectinload(MealItem.food_item))
            .where(Meal.id == meal_id)
        )
        result = await session.execute(stmt)
        return _meal_to_dict(result.scalar_one())


# ── WaterLog — вода ───────────────────────────────────────────────────────────

async def add_water(user_id: int, amount_ml: int, logged_at: datetime | None = None) -> dict:
    """Логирует потребление воды."""
    async with AsyncSessionLocal() as session:
        entry = WaterLog(
            user_id=user_id,
            amount_ml=amount_ml,
        )
        # logged_at устанавливается через server_default=func.now()
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        return {
            "id": entry.id,
            "amount_ml": entry.amount_ml,
            "logged_at": entry.logged_at.isoformat() if entry.logged_at else None,
        }


async def get_water_for_date(user_id: int, target_date: date) -> int:
    """Возвращает суммарное потребление воды за день (мл)."""
    async with AsyncSessionLocal() as session:
        # Используем timezone-aware границы дня
        day_start, day_end = _day_range(target_date)
        stmt = select(func.coalesce(func.sum(WaterLog.amount_ml), 0)).where(
            and_(
                WaterLog.user_id == user_id,
                WaterLog.logged_at >= day_start,
                WaterLog.logged_at < day_end,
            )
        )
        result = await session.execute(stmt)
        return result.scalar() or 0


# ── NutritionGoal — цели ──────────────────────────────────────────────────────

async def get_goals(user_id: int) -> dict | None:
    """Возвращает цели пользователя или None если не заданы."""
    async with AsyncSessionLocal() as session:
        stmt = select(NutritionGoal).where(NutritionGoal.user_id == user_id)
        result = await session.execute(stmt)
        goal = result.scalar_one_or_none()
        if not goal:
            return None
        return {
            "calories": goal.calories,
            "protein_g": goal.protein_g,
            "fat_g": goal.fat_g,
            "carbs_g": goal.carbs_g,
            "water_ml": goal.water_ml,
            "goal_type": goal.goal_type,
            "activity_level": goal.activity_level,
        }


async def set_goals(
    user_id: int,
    calories: int | None = None,
    protein_g: int | None = None,
    fat_g: int | None = None,
    carbs_g: int | None = None,
    water_ml: int | None = None,
    goal_type: str | None = None,
    activity_level: str | None = None,
) -> dict:
    """Создаёт или обновляет цели по питанию."""
    async with AsyncSessionLocal() as session:
        stmt = select(NutritionGoal).where(NutritionGoal.user_id == user_id)
        result = await session.execute(stmt)
        goal = result.scalar_one_or_none()

        if goal:
            # Обновляем только переданные значения
            if calories is not None:
                goal.calories = calories
            if protein_g is not None:
                goal.protein_g = protein_g
            if fat_g is not None:
                goal.fat_g = fat_g
            if carbs_g is not None:
                goal.carbs_g = carbs_g
            if water_ml is not None:
                goal.water_ml = water_ml
            if goal_type is not None:
                goal.goal_type = goal_type
            if activity_level is not None:
                goal.activity_level = activity_level
        else:
            # Создаём новую запись с дефолтами
            goal = NutritionGoal(
                user_id=user_id,
                calories=calories or 2000,
                protein_g=protein_g or 120,
                fat_g=fat_g or 65,
                carbs_g=carbs_g or 250,
                water_ml=water_ml or 2000,
                goal_type=goal_type,
                activity_level=activity_level,
            )
            session.add(goal)

        await session.commit()
        await session.refresh(goal)
        return {
            "calories": goal.calories,
            "protein_g": goal.protein_g,
            "fat_g": goal.fat_g,
            "carbs_g": goal.carbs_g,
            "water_ml": goal.water_ml,
            "goal_type": goal.goal_type,
            "activity_level": goal.activity_level,
        }


# ── Статистика ────────────────────────────────────────────────────────────────

async def get_nutrition_summary(user_id: int, target_date: date) -> dict:
    """Полная сводка за день: meals + totals + water + goals."""
    # Timezone-aware границы дня
    day_start, day_end = _day_range(target_date)

    # Получаем приёмы пищи за день
    meals = await get_meals_by_date(user_id, day_start, day_end)

    # Суммируем КБЖУ по всем приёмам
    totals = {
        "calories": round(sum(m["total_calories"] for m in meals), 1),
        "protein_g": round(sum(m["total_protein"] for m in meals), 1),
        "fat_g": round(sum(m["total_fat"] for m in meals), 1),
        "carbs_g": round(sum(m["total_carbs"] for m in meals), 1),
    }

    # Вода за день
    water_ml = await get_water_for_date(user_id, target_date)

    # Цели
    goals = await get_goals(user_id)

    return {
        "date": target_date.isoformat(),
        "goals": goals,
        "totals": totals,
        "water_ml": water_ml,
        "meals": meals,
    }


# ── Профиль (параметры тела) ──────────────────────────────────────────────────

async def get_profile(user_id: int) -> dict | None:
    """Получить параметры тела пользователя из UserProfile."""
    from db.models import UserProfile  # ленивый импорт, чтобы не менять шапку
    async with AsyncSessionLocal() as session:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await session.execute(stmt)
        p = result.scalar_one_or_none()
        if not p:
            return None
        return {
            "weight_kg": p.weight_kg,
            "height_cm": p.height_cm,
            "age": p.age,
            "gender": p.gender,
        }


async def update_profile(
    user_id: int,
    weight_kg: float | None = None,
    height_cm: float | None = None,
    age: int | None = None,
    gender: str | None = None,
) -> dict:
    """Создать / обновить параметры тела пользователя."""
    from db.models import UserProfile  # ленивый импорт
    async with AsyncSessionLocal() as session:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await session.execute(stmt)
        p = result.scalar_one_or_none()

        if p:
            # Обновляем только переданные поля
            if weight_kg is not None:
                p.weight_kg = weight_kg
            if height_cm is not None:
                p.height_cm = height_cm
            if age is not None:
                p.age = age
            if gender is not None:
                p.gender = gender
        else:
            # Создаём новый профиль
            p = UserProfile(
                user_id=user_id,
                weight_kg=weight_kg,
                height_cm=height_cm,
                age=age,
                gender=gender,
            )
            session.add(p)

        await session.commit()
        await session.refresh(p)
        return {
            "weight_kg": p.weight_kg,
            "height_cm": p.height_cm,
            "age": p.age,
            "gender": p.gender,
        }


# ── Избранные продукты ────────────────────────────────────────────────────────

async def toggle_favorite(user_id: int, food_item_id: int) -> bool:
    """Добавить/убрать продукт из избранного. Возвращает True если добавлен, False если убран."""
    from db.models import FavoriteFood
    async with AsyncSessionLocal() as session:
        stmt = select(FavoriteFood).where(
            FavoriteFood.user_id == user_id,
            FavoriteFood.food_item_id == food_item_id,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Убираем из избранного
            await session.delete(existing)
            await session.commit()
            return False
        else:
            # Добавляем в избранное
            fav = FavoriteFood(user_id=user_id, food_item_id=food_item_id)
            session.add(fav)
            await session.commit()
            return True


async def list_favorites(user_id: int) -> list[dict]:
    """Список избранных продуктов пользователя с КБЖУ."""
    from db.models import FavoriteFood
    async with AsyncSessionLocal() as session:
        stmt = (
            select(FavoriteFood, FoodItem)
            .join(FoodItem, FavoriteFood.food_item_id == FoodItem.id)
            .where(FavoriteFood.user_id == user_id)
            .order_by(FavoriteFood.created_at.desc())
        )
        result = await session.execute(stmt)
        rows = result.all()
        return [
            {
                **_food_item_to_dict(food),
                "is_favorite": True,
            }
            for _fav, food in rows
        ]


async def get_favorite_ids(user_id: int) -> set[int]:
    """Множество food_item_id, которые в избранном у пользователя."""
    from db.models import FavoriteFood
    async with AsyncSessionLocal() as session:
        stmt = select(FavoriteFood.food_item_id).where(FavoriteFood.user_id == user_id)
        result = await session.execute(stmt)
        return {row[0] for row in result.all()}


# ── Смарт-повтор (частые продукты и последние приёмы) ─────────────────────────

async def get_frequent_foods(user_id: int, meal_type: str | None = None, limit: int = 10) -> list[dict]:
    """Топ продуктов по частоте использования пользователем."""
    async with AsyncSessionLocal() as session:
        # Базовый запрос: считаем сколько раз каждый food_item встречался в meal_items
        query = (
            select(
                MealItem.food_item_id,
                func.count().label("cnt"),
            )
            .join(Meal, MealItem.meal_id == Meal.id)
            .where(Meal.user_id == user_id)
        )
        # Фильтр по типу приёма
        if meal_type:
            query = query.where(Meal.meal_type == meal_type)

        query = query.group_by(MealItem.food_item_id).order_by(func.count().desc()).limit(limit)
        result = await session.execute(query)
        rows = result.all()

        if not rows:
            return []

        # Загружаем FoodItem для каждого id
        food_ids = [r[0] for r in rows]
        foods_q = select(FoodItem).where(FoodItem.id.in_(food_ids))
        foods_result = await session.execute(foods_q)
        foods_map = {f.id: f for f in foods_result.scalars().all()}

        # Собираем результат в порядке частоты
        out = []
        for food_id, cnt in rows:
            f = foods_map.get(food_id)
            if f:
                out.append({**_food_item_to_dict(f), "use_count": cnt})
        return out


async def get_recent_meals(user_id: int, meal_type: str | None = None, limit: int = 5) -> list[dict]:
    """Последние приёмы пищи пользователя (для 'повторить')."""
    async with AsyncSessionLocal() as session:
        query = (
            select(Meal)
            .options(selectinload(Meal.items).selectinload(MealItem.food_item))
            .where(Meal.user_id == user_id)
        )
        if meal_type:
            query = query.where(Meal.meal_type == meal_type)

        query = query.order_by(Meal.eaten_at.desc()).limit(limit)
        result = await session.execute(query)
        meals = result.scalars().all()
        return [_meal_to_dict(m) for m in meals]


# ── Шаблоны приёмов пищи ─────────────────────────────────────────────────────

async def create_template(user_id: int, name: str, meal_type: str, items: list[dict]) -> dict:
    """Создать шаблон из списка продуктов: [{food_item_id, amount_g}, ...]."""
    from db.models import MealTemplate, MealTemplateItem
    async with AsyncSessionLocal() as session:
        tmpl = MealTemplate(user_id=user_id, name=name, meal_type=meal_type)
        session.add(tmpl)
        await session.flush()  # получаем tmpl.id

        for item in items:
            ti = MealTemplateItem(
                template_id=tmpl.id,
                food_item_id=item["food_item_id"],
                amount_g=item["amount_g"],
            )
            session.add(ti)

        await session.commit()
        await session.refresh(tmpl)
        return await _template_to_dict(session, tmpl)


async def create_template_from_meal(user_id: int, meal_id: int, name: str) -> dict | None:
    """Создать шаблон из существующего приёма пищи."""
    from db.models import MealTemplate, MealTemplateItem
    async with AsyncSessionLocal() as session:
        # Загружаем приём пищи
        meal_q = (
            select(Meal)
            .options(selectinload(Meal.items))
            .where(Meal.id == meal_id, Meal.user_id == user_id)
        )
        result = await session.execute(meal_q)
        meal = result.scalar_one_or_none()
        if not meal or not meal.items:
            return None

        # Создаём шаблон
        tmpl = MealTemplate(user_id=user_id, name=name, meal_type=meal.meal_type)
        session.add(tmpl)
        await session.flush()

        for mi in meal.items:
            ti = MealTemplateItem(
                template_id=tmpl.id,
                food_item_id=mi.food_item_id,
                amount_g=mi.amount_g,
            )
            session.add(ti)

        await session.commit()
        await session.refresh(tmpl)
        return await _template_to_dict(session, tmpl)


async def list_templates(user_id: int) -> list[dict]:
    """Список шаблонов пользователя."""
    from db.models import MealTemplate
    async with AsyncSessionLocal() as session:
        stmt = (
            select(MealTemplate)
            .where(MealTemplate.user_id == user_id)
            .order_by(MealTemplate.created_at.desc())
        )
        result = await session.execute(stmt)
        templates = result.scalars().all()
        return [await _template_to_dict(session, t) for t in templates]


async def get_template(template_id: int, user_id: int) -> dict | None:
    """Получить шаблон с items."""
    from db.models import MealTemplate
    async with AsyncSessionLocal() as session:
        stmt = select(MealTemplate).where(
            MealTemplate.id == template_id,
            MealTemplate.user_id == user_id,
        )
        result = await session.execute(stmt)
        tmpl = result.scalar_one_or_none()
        if not tmpl:
            return None
        return await _template_to_dict(session, tmpl)


async def delete_template(template_id: int, user_id: int) -> bool:
    """Удалить шаблон. Возвращает True если удалён."""
    from db.models import MealTemplate
    async with AsyncSessionLocal() as session:
        stmt = select(MealTemplate).where(
            MealTemplate.id == template_id,
            MealTemplate.user_id == user_id,
        )
        result = await session.execute(stmt)
        tmpl = result.scalar_one_or_none()
        if not tmpl:
            return False
        await session.delete(tmpl)
        await session.commit()
        return True


async def apply_template(template_id: int, user_id: int, eaten_at=None) -> dict | None:
    """Создать Meal из шаблона (копирует items). Возвращает dict нового Meal."""
    from db.models import MealTemplate
    async with AsyncSessionLocal() as session:
        # Загружаем шаблон с items и food_item внутри сессии
        stmt = select(MealTemplate).where(
            MealTemplate.id == template_id,
            MealTemplate.user_id == user_id,
        )
        result = await session.execute(stmt)
        tmpl = result.scalar_one_or_none()
        if not tmpl:
            return None

        # Формируем items для add_meal внутри сессии (доступ к lazy-связям)
        items_for_meal = []
        for ti in tmpl.items:
            fi = ti.food_item
            # Рассчитываем КБЖУ на порцию
            ratio = ti.amount_g / 100
            items_for_meal.append({
                "name": fi.name if fi else "Неизвестно",
                "amount_g": ti.amount_g,
                "calories": round((fi.calories or 0) * ratio, 1),
                "protein_g": round((fi.protein_g or 0) * ratio, 1),
                "fat_g": round((fi.fat_g or 0) * ratio, 1),
                "carbs_g": round((fi.carbs_g or 0) * ratio, 1),
                "food_item_id": ti.food_item_id,
            })
        # Сохраняем meal_type до закрытия сессии
        meal_type = tmpl.meal_type

    # Если eaten_at не передан — используем текущее время (UTC)
    if eaten_at is None:
        from datetime import timezone as tz
        eaten_at = datetime.now(tz.utc)

    return await add_meal(
        user_id=user_id,
        meal_type=meal_type,
        items=items_for_meal,
        eaten_at=eaten_at,
    )


async def find_template_by_name(user_id: int, name: str) -> dict | None:
    """Найти шаблон по имени (нечёткий поиск через ILIKE)."""
    from db.models import MealTemplate
    async with AsyncSessionLocal() as session:
        stmt = select(MealTemplate).where(
            MealTemplate.user_id == user_id,
            MealTemplate.name.ilike(f"%{name}%"),
        )
        result = await session.execute(stmt)
        tmpl = result.scalar_one_or_none()
        if not tmpl:
            return None
        return await _template_to_dict(session, tmpl)


async def _template_to_dict(session, tmpl) -> dict:
    """Конвертация MealTemplate + items в dict."""
    # items уже загружены через lazy="selectin"
    items_out = []
    total_cal = 0
    for ti in tmpl.items:
        fi = ti.food_item
        ratio = ti.amount_g / 100
        cal = round((fi.calories or 0) * ratio, 1) if fi else 0
        items_out.append({
            "id": ti.id,
            "food_item_id": ti.food_item_id,
            "name": fi.name if fi else "Неизвестно",
            "amount_g": ti.amount_g,
            "calories": cal,
            "protein_g": round((fi.protein_g or 0) * ratio, 1) if fi else 0,
            "fat_g": round((fi.fat_g or 0) * ratio, 1) if fi else 0,
            "carbs_g": round((fi.carbs_g or 0) * ratio, 1) if fi else 0,
        })
        total_cal += cal

    return {
        "id": tmpl.id,
        "name": tmpl.name,
        "meal_type": tmpl.meal_type,
        "items": items_out,
        "total_calories": round(total_cal, 1),
        "created_at": tmpl.created_at.isoformat() if tmpl.created_at else None,
    }
