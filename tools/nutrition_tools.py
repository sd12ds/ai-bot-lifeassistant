"""
LangChain @tool для модуля питания.
user_id передаётся через замыкание при создании инструментов.
"""
from __future__ import annotations

import json
from datetime import datetime, date, timedelta
from typing import Optional

from langchain.tools import tool

from config import DEFAULT_TZ
from db import nutrition_storage as ns


def make_nutrition_tools(user_id: int) -> list:
    """Создаёт набор инструментов питания, привязанных к user_id."""

    @tool
    async def meal_log(
        items_json: str,
        meal_type: str = "snack",
        notes: str = "",
    ) -> str:
        """Залогировать приём пищи из текста.
        items_json — JSON-массив: [{"name": "Куриная грудка", "amount_g": 150,
        "calories": 165, "protein_g": 31, "fat_g": 3.6, "carbs_g": 0}]
        meal_type — breakfast | lunch | dinner | snack
        """
        try:
            # Парсим JSON с продуктами
            items = json.loads(items_json)
            if not isinstance(items, list) or len(items) == 0:
                return "Ошибка: нужен непустой JSON-массив продуктов."

            # Время приёма — сейчас
            eaten_at = datetime.now(DEFAULT_TZ)

            result = await ns.add_meal(
                user_id=user_id,
                meal_type=meal_type,
                eaten_at=eaten_at,
                items=items,
                notes=notes,
            )

            # Формируем читабельный ответ
            lines = [f"✅ {_meal_type_ru(result['meal_type'])} сохранён (ID: {result['id']})"]
            for item in result["items"]:
                lines.append(
                    f"  🔸 {item['name']} — {item['amount_g']}г "
                    f"({item['calories']} ккал)"
                )
            lines.append(
                f"📊 Итого: {result['total_calories']} ккал "
                f"· Б {result['total_protein']} · Ж {result['total_fat']} · У {result['total_carbs']}"
            )
            return "\n".join(lines)
        except json.JSONDecodeError:
            return "Ошибка: некорректный JSON в items_json."
        except Exception as e:
            return f"Ошибка при сохранении: {e}"

    @tool
    async def meal_delete(meal_id: int) -> str:
        """Удалить приём пищи по ID."""
        deleted = await ns.delete_meal(meal_id=meal_id, user_id=user_id)
        if deleted:
            return f"✅ Приём пищи #{meal_id} удалён."
        return f"❌ Приём пищи #{meal_id} не найден."

    @tool
    async def water_log(amount_ml: int = 250) -> str:
        """Залогировать потребление воды. amount_ml — количество мл (по умолчанию 250 мл = стакан)."""
        result = await ns.add_water(user_id=user_id, amount_ml=amount_ml)

        # Показываем прогресс за день
        today = date.today()
        total_water = await ns.get_water_for_date(user_id, today)
        goals = await ns.get_goals(user_id)
        goal_ml = goals["water_ml"] if goals and goals["water_ml"] else 2000

        return (
            f"💧 +{amount_ml} мл воды\n"
            f"📊 За сегодня: {total_water} / {goal_ml} мл "
            f"({round(total_water / goal_ml * 100)}%)"
        )

    @tool
    async def nutrition_stats(period: str = "today") -> str:
        """Статистика КБЖУ за период. period: today | week | month"""
        today = date.today()

        if period == "today":
            summary = await ns.get_nutrition_summary(user_id, today)
            result = _format_day_summary(summary)
            # Добавляем контекстные советы к дневной статистике
            try:
                from datetime import datetime as _dt
                from config import DEFAULT_TZ
                from services.nutrition_insights import generate_daily_tips
                now_hour = _dt.now(DEFAULT_TZ).hour
                tips = await generate_daily_tips(user_id, current_hour=now_hour)
                if tips:
                    result += "\n\n💡 Советы:\n" + "\n".join(tips)
            except Exception:
                pass  # не ломаем статистику если советы не сработали
            return result

        elif period == "week":
            # Суммируем за 7 дней
            lines = ["📊 Статистика за неделю:\n"]
            total_cal = 0
            for i in range(7):
                d = today - timedelta(days=6 - i)
                summary = await ns.get_nutrition_summary(user_id, d)
                cal = summary["totals"]["calories"]
                total_cal += cal
                day_name = d.strftime("%a %d.%m")
                lines.append(f"  {day_name}: {cal} ккал")
            avg = round(total_cal / 7)
            lines.append(f"\n📈 Среднее: {avg} ккал/день")
            return "\n".join(lines)

        elif period == "month":
            lines = ["📊 Статистика за 30 дней:\n"]
            total_cal = 0
            days_with_data = 0
            for i in range(30):
                d = today - timedelta(days=29 - i)
                summary = await ns.get_nutrition_summary(user_id, d)
                cal = summary["totals"]["calories"]
                if cal > 0:
                    days_with_data += 1
                    total_cal += cal
            avg = round(total_cal / days_with_data) if days_with_data else 0
            lines.append(f"📈 Среднее: {avg} ккал/день (за {days_with_data} дней с данными)")
            lines.append(f"🔥 Всего: {round(total_cal)} ккал")
            return "\n".join(lines)

        return "Неизвестный период. Используй: today, week, month."

    @tool
    async def nutrition_goals_set(
        calories: int = 0,
        protein_g: int = 0,
        fat_g: int = 0,
        carbs_g: int = 0,
        water_ml: int = 0,
        goal_type: str = "",
        weight_kg: float = 0,
        height_cm: float = 0,
        age: int = 0,
        gender: str = "",
        activity_level: str = "",
    ) -> str:
        """Установить/обновить цели по питанию.
        Два режима:
        1) Авто-расчёт: передай goal_type (lose/maintain/gain), weight_kg, height_cm, age, gender (male/female), activity_level (sedentary/light/moderate/active/very_active). Система рассчитает КБЖУ автоматически.
        2) Ручной: передай calories, protein_g, fat_g, carbs_g, water_ml — только те, что нужно изменить.
        """
        # Режим авто-расчёта: если указан goal_type и параметры тела
        if goal_type and weight_kg > 0 and height_cm > 0 and age > 0 and gender:
            from services.nutrition_calc import calculate_full
            # Уровень активности по умолчанию — moderate
            act = activity_level if activity_level else "moderate"
            targets = calculate_full(
                weight_kg=weight_kg,
                height_cm=height_cm,
                age=age,
                gender=gender,
                activity_level=act,
                goal_type=goal_type,
            )
            # Сохраняем профиль
            await ns.update_profile(
                user_id=user_id,
                weight_kg=weight_kg,
                height_cm=height_cm,
                age=age,
                gender=gender,
            )
            # Сохраняем цели
            result = await ns.set_goals(
                user_id=user_id,
                calories=targets.calories,
                protein_g=targets.protein_g,
                fat_g=targets.fat_g,
                carbs_g=targets.carbs_g,
                water_ml=targets.water_ml,
                goal_type=goal_type,
                activity_level=act,
            )
            goal_labels = {"lose": "Похудение", "maintain": "Удержание", "gain": "Набор массы"}
            return (
                f"🎯 Цели рассчитаны ({goal_labels.get(goal_type, goal_type)}):\n"
                f"  🔥 Калории: {result['calories']} ккал\n"
                f"  🥩 Белки: {result['protein_g']} г\n"
                f"  🧈 Жиры: {result['fat_g']} г\n"
                f"  🍞 Углеводы: {result['carbs_g']} г\n"
                f"  💧 Вода: {result['water_ml']} мл"
            )

        # Ручной режим — передаём только ненулевые значения
        kwargs = {}
        if calories > 0:
            kwargs["calories"] = calories
        if protein_g > 0:
            kwargs["protein_g"] = protein_g
        if fat_g > 0:
            kwargs["fat_g"] = fat_g
        if carbs_g > 0:
            kwargs["carbs_g"] = carbs_g
        if water_ml > 0:
            kwargs["water_ml"] = water_ml
        if goal_type:
            kwargs["goal_type"] = goal_type
        if activity_level:
            kwargs["activity_level"] = activity_level

        if not kwargs:
            return "Укажи хотя бы один параметр (calories, protein_g, fat_g, carbs_g, water_ml) или параметры тела для авто-расчёта."

        result = await ns.set_goals(user_id=user_id, **kwargs)
        return (
            f"🎯 Цели обновлены:\n"
            f"  🔥 Калории: {result['calories']} ккал\n"
            f"  🥩 Белки: {result['protein_g']} г\n"
            f"  🧈 Жиры: {result['fat_g']} г\n"
            f"  🍞 Углеводы: {result['carbs_g']} г\n"
            f"  💧 Вода: {result['water_ml']} мл"
        )

    @tool
    async def meal_from_template(template_name: str) -> str:
        """Создать приём пищи из сохранённого шаблона по имени. Примеры: 'мой завтрак', 'протеин', 'обед как обычно'."""
        # Поиск шаблона по имени
        tmpl = await ns.find_template_by_name(user_id, template_name)
        if not tmpl:
            # Показать доступные шаблоны
            all_tmpls = await ns.list_templates(user_id)
            if not all_tmpls:
                return "У тебя пока нет сохранённых шаблонов. Создай шаблон в MiniApp."
            names = ", ".join(f"«{t['name']}»" for t in all_tmpls)
            return f"Шаблон «{template_name}» не найден. Доступные: {names}"

        # Применяем шаблон
        meal = await ns.apply_template(tmpl["id"], user_id)
        if not meal:
            return "Ошибка при применении шаблона."

        items_str = ", ".join(
            f"{it['name']} ({it['amount_g']}г)"
            for it in meal.get("items", [])
        )
        return (
            f"✅ Шаблон «{tmpl['name']}» применён!\n"
            f"🍽 {items_str}\n"
            f"🔥 Итого: {meal.get('total_calories', 0)} ккал"
        )

    @tool
    async def food_search(query: str) -> str:
        """Поиск продукта в справочнике по названию. Возвращает КБЖУ на 100г."""
        results = await ns.search_food(query=query, user_id=user_id, limit=5)
        if not results:
            return f"Продукт «{query}» не найден в справочнике."

        lines = [f"🔍 Найдено по «{query}»:"]
        for f in results:
            lines.append(
                f"  • {f['name']} — "
                f"{f['calories']} ккал · Б {f['protein_g']} · Ж {f['fat_g']} · У {f['carbs_g']} (на 100г)"
            )
        return "\n".join(lines)

    @tool
    async def ewa_product_info(query: str) -> str:
        """Поиск информации о продуктах EWA Product (здоровое питание).
        Ищет по названию, типу или ключевым словам.
        Возвращает: описание, ключевые преимущества, КБЖУ, цену, применение, ссылки.
        Примеры: 'bodybox', 'батончик', 'зефир', 'какао', 'суп', 'протеин'.
        """
        import json as _json
        import os
        dataset_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "ewa_products_dataset.json"
        )
        try:
            with open(dataset_path, "r") as _f:
                products = _json.load(_f)
        except FileNotFoundError:
            return "Датасет EWA продуктов не найден."

        q = query.lower().strip()
        q_words = q.split()

        # Поиск со скорингом: чем больше слов запроса совпало, тем выше ранг
        scored = []
        for p in products:
            score = 0
            # Основные поля для поиска
            searchable = " ".join([
                p["name"], p["product_type"], p.get("subtitle", ""),
                p.get("long_description", ""), p.get("composition", ""),
                " ".join(p.get("tags", []))
            ]).lower()
            # Алиасы — русские транслитерации, вариации голосового ввода
            aliases = [a.lower() for a in p.get("aliases", [])]

            # Точное совпадение запроса с алиасом — высший приоритет
            if q in aliases:
                score += 100
            # Полное совпадение запроса в основных полях
            if q in searchable:
                score += 50
            # Совпадение отдельных алиасов (многословных) с запросом
            for alias in aliases:
                # Алиас целиком содержится в запросе или наоборот
                alias_words = alias.split()
                if len(alias_words) >= 2 and alias in q:
                    score += 30  # Многословный алиас в запросе
                elif len(alias_words) >= 2 and q in alias:
                    score += 20
            # Подсчёт совпавших слов запроса в алиасах и основных полях
            all_text = searchable + " " + " ".join(aliases)
            matched_words = sum(1 for w in q_words if w in all_text)
            score += matched_words * 10

            if score > 0:
                scored.append((score, p))

        # Сортируем по убыванию скора
        scored.sort(key=lambda x: -x[0])
        matches = [p for _, p in scored]

        # Фолбэк — все слова запроса в полях + алиасах
        if not matches:
            for p in products:
                searchable = " ".join([
                    p["name"], p["product_type"], p.get("subtitle", ""),
                    p.get("long_description", ""),
                    " ".join(p.get("aliases", []))
                ]).lower()
                if all(w in searchable for w in q_words):
                    matches.append(p)

        if not matches:
            types = sorted(set(p["product_type"] for p in products))
            return (
                f"По запросу '{query}' не найдено. "
                f"Категории EWA: {', '.join(types)}"
            )

        # Формируем ответ (до 3 продуктов)
        parts = []
        for p in matches[:3]:
            ps = p["per_serving"]
            lines = [f"\n--- {p['name']} ---"]
            if p.get("subtitle"):
                lines.append(p["subtitle"])
            lines.append(f"Тип: {p['product_type']}")
            lines.append(
                f"Порция {p['serving_g']}г: "
                f"{ps['calories']} ккал, Б{ps['protein_g']}г, "
                f"Ж{ps['fat_g']}г, У{ps['carbs_g']}г"
            )
            if p.get("price_rub"):
                line = f"Цена: {p['price_rub']:.0f} руб."
                if p.get("bonus_price"):
                    line += f" ({p['bonus_price']} бонусов)"
                lines.append(line)
            if p.get("packaging"):
                lines.append(f"Упаковка: {p['packaging']}")
            if p.get("long_description"):
                lines.append(f"Описание: {p['long_description'][:400]}")
            if p.get("key_features"):
                lines.append(f"Ключевые преимущества: {p['key_features'][:500]}")
            if p.get("tech_specs"):
                lines.append(f"Применение: {p['tech_specs'][:300]}")
            if p.get("url"):
                lines.append(f"Страница: {p['url']}")
            if p.get("pdf_review"):
                lines.append(f"Презентация PDF: {p['pdf_review']}")
            parts.append("\n".join(lines))

        header = f"Найдено {len(matches)} продукт(ов) EWA."
        if len(matches) > 3:
            extra = ", ".join(m["name"] for m in matches[3:6])
            header += f" Показаны 3. Также: {extra}"
            if len(matches) > 6:
                header += f" и ещё {len(matches) - 6}"

        return header + "\n" + "\n".join(parts)

    return [meal_log, meal_delete, water_log, nutrition_stats, nutrition_goals_set, meal_from_template, food_search, ewa_product_info]


# ── Вспомогательные ──────────────────────────────────────────────────────────

_MEAL_TYPE_RU = {
    "breakfast": "🌅 Завтрак",
    "lunch": "🍽 Обед",
    "dinner": "🌙 Ужин",
    "snack": "🍎 Перекус",
}


def _meal_type_ru(mt: str) -> str:
    """Переводит meal_type в читабельное название."""
    return _MEAL_TYPE_RU.get(mt, mt)


def _format_day_summary(summary: dict) -> str:
    """Форматирует дневную сводку в читабельный текст."""
    totals = summary["totals"]
    goals = summary.get("goals")
    water = summary["water_ml"]

    lines = [f"📊 Питание за {summary['date']}:\n"]

    # Приёмы пищи
    if summary["meals"]:
        for m in summary["meals"]:
            mt = _meal_type_ru(m["meal_type"])
            time_str = ""
            if m["eaten_at"]:
                try:
                    t = datetime.fromisoformat(m["eaten_at"])
                    time_str = f" · {t.strftime('%H:%M')}"
                except ValueError:
                    pass
            lines.append(f"{mt}{time_str} — {m['total_calories']} ккал")
            for item in m["items"]:
                lines.append(f"    {item['name']} {item['amount_g']}г")
    else:
        lines.append("  Приёмов пищи пока нет.")

    # Итоги
    lines.append(f"\n📈 Итого: {totals['calories']} ккал")
    lines.append(f"  🥩 Б: {totals['protein_g']}г · 🧈 Ж: {totals['fat_g']}г · 🍞 У: {totals['carbs_g']}г")

    # Вода
    lines.append(f"  💧 Вода: {water} мл")

    # Прогресс к целям
    if goals:
        cal_pct = round(totals["calories"] / goals["calories"] * 100) if goals["calories"] else 0
        water_pct = round(water / goals["water_ml"] * 100) if goals["water_ml"] else 0
        lines.append(f"\n🎯 Прогресс: калории {cal_pct}% · вода {water_pct}%")

    return "\n".join(lines)
