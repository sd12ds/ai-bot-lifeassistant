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
from bot.nutrition_context import (
    get_context, get_or_create_context, create_draft, clear_draft,
    format_draft_card,
)
from services.nutrition_score import calculate_daily_score, format_score_card
from services.nutrition_followup import generate_followup, format_followup
from services.nutrition_weekly_summary import generate_weekly_summary


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


    @tool
    async def meal_draft_create(
        items_json: str,
        meal_type: str = "snack",
        source: str = "agent",
    ) -> str:
        """Создать черновик приёма пищи (НЕ сохраняет в БД — только draft).
        items_json — JSON-массив: [{"name": "...", "amount_g": N, "calories": N, "protein_g": N, "fat_g": N, "carbs_g": N}]
        meal_type — breakfast | lunch | dinner | snack
        source — откуда данные: photo | text | agent
        Используй этот инструмент вместо meal_log, если нужно дать пользователю возможность проверить/отредактировать перед сохранением.
        """
        try:
            items = json.loads(items_json)
            if not isinstance(items, list) or len(items) == 0:
                return "Ошибка: нужен непустой JSON-массив продуктов."

            # Создаём draft в контексте сессии
            draft = create_draft(user_id, items=items, meal_type=meal_type, source=source)
            card = format_draft_card(draft)
            return f"📋 Черновик создан:\n{card}\nПопроси пользователя подтвердить или внести правки."
        except json.JSONDecodeError:
            return "Ошибка: некорректный JSON в items_json."
        except Exception as e:
            return f"Ошибка при создании черновика: {e}"

    @tool
    async def meal_draft_update(
        items_json: str,
        meal_type: str = "",
    ) -> str:
        """Обновить текущий черновик приёма пищи (заменяет items и/или meal_type).
        items_json — ПОЛНЫЙ обновлённый JSON-массив продуктов (все позиции).
        meal_type — новый тип (если нужно изменить, иначе пустая строка).
        """
        ctx = get_context(user_id)
        if not ctx or not ctx.draft:
            return "Нет активного черновика для обновления."

        try:
            items = json.loads(items_json)
            if not isinstance(items, list) or len(items) == 0:
                return "Ошибка: нужен непустой JSON-массив продуктов."

            # Обновляем items в draft
            ctx.draft.items = items
            if meal_type:
                ctx.draft.meal_type = meal_type
            # Пересчитываем total
            ctx.draft.total_calories = round(sum(i.get("calories", 0) for i in items), 1)
            ctx.draft.total_protein = round(sum(i.get("protein_g", 0) for i in items), 1)
            ctx.draft.total_fat = round(sum(i.get("fat_g", 0) for i in items), 1)
            ctx.draft.total_carbs = round(sum(i.get("carbs_g", 0) for i in items), 1)
            ctx.draft.version += 1

            card = format_draft_card(ctx.draft)
            return f"📋 Черновик обновлён (v{ctx.draft.version}):\n{card}\nПопроси пользователя подтвердить."
        except json.JSONDecodeError:
            return "Ошибка: некорректный JSON в items_json."
        except Exception as e:
            return f"Ошибка при обновлении черновика: {e}"

    @tool
    async def meal_draft_confirm() -> str:
        """Подтвердить и сохранить черновик в базу данных.
        Вызывай когда пользователь подтвердил ('да', 'ок', 'сохрани', 'верно').
        """
        ctx = get_context(user_id)
        if not ctx or not ctx.draft:
            return "Нет активного черновика для сохранения."

        draft = ctx.draft
        try:
            # Время приёма — сейчас
            eaten_at = datetime.now(DEFAULT_TZ)

            # Сохраняем через nutrition_storage
            result = await ns.add_meal(
                user_id=user_id,
                meal_type=draft.meal_type,
                eaten_at=eaten_at,
                items=draft.items,
                notes=f"source:{draft.source_type}",
            )

            # Сохраняем last_saved_entity — чтобы можно было редактировать после confirm
            from bot.core.session_context import set_last_saved
            set_last_saved(user_id, result)
            # Очищаем draft после успешного сохранения
            clear_draft(user_id)

            # Формируем ответ
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
            # Генерируем follow-up подсказки после сохранения
            try:
                tips = await generate_followup(user_id)
                followup_text = format_followup(tips)
                if followup_text:
                    lines.append(followup_text)
            except Exception:
                pass  # не ломаем сохранение если follow-up не сработал

            return "\n".join(lines)
        except Exception as e:
            return f"Ошибка при сохранении: {e}"

    @tool
    async def meal_draft_discard() -> str:
        """Отменить текущий черновик приёма пищи.
        Вызывай когда пользователь отменил ('нет', 'отмена', 'не надо').
        """
        ctx = get_context(user_id)
        if not ctx or not ctx.draft:
            return "Нет активного черновика."
        clear_draft(user_id)
        return "🗑 Черновик отменён."

    @tool
    async def meal_check_pending() -> str:
        """Проверить, есть ли активный черновик приёма пищи.
        Используй в начале разговора, чтобы напомнить пользователю о незавершённом вводе.
        """
        ctx = get_context(user_id)
        if not ctx or not ctx.draft:
            return "Нет активного черновика."
        card = format_draft_card(ctx.draft)
        return f"📋 Есть незавершённый черновик:\n{card}"

    @tool
    async def nutrition_remaining_today() -> str:
        """Показать сколько КБЖУ осталось на сегодня (остаток от целей).
        Вызывай когда пользователь спрашивает 'сколько осталось', 'что ещё можно', 'остаток' и т.п.
        """
        today = date.today()
        summary = await ns.get_nutrition_summary(user_id, today)
        goals = summary.get("goals") or {}
        totals = summary.get("totals", {})
        water_ml = summary.get("water_ml", 0)

        # Если целей нет — не можем считать остаток
        if not goals or not goals.get("calories"):
            return "⚠️ Цели по КБЖУ не установлены. Установи цели, чтобы видеть остаток."

        # Считаем остаток по каждому параметру
        cal_left = max(0, goals["calories"] - totals.get("calories", 0))
        prot_left = max(0, (goals.get("protein_g") or 0) - totals.get("protein_g", 0))
        fat_left = max(0, (goals.get("fat_g") or 0) - totals.get("fat_g", 0))
        carbs_left = max(0, (goals.get("carbs_g") or 0) - totals.get("carbs_g", 0))
        water_left = max(0, (goals.get("water_ml") or 0) - water_ml)

        # Прогресс в процентах
        cal_pct = round(totals.get("calories", 0) / goals["calories"] * 100) if goals["calories"] else 0

        lines = [
            f"📊 **Остаток на сегодня** (съедено {cal_pct}%)\n",
            f"🔥 Калории: {int(cal_left)} ккал",
            f"🥩 Белок: {int(prot_left)}г",
            f"🧈 Жиры: {int(fat_left)}г",
            f"🍞 Углеводы: {int(carbs_left)}г",
            f"💧 Вода: {int(water_left)} мл",
        ]

        # Проверяем перебор
        if totals.get("calories", 0) > goals["calories"]:
            over = int(totals["calories"] - goals["calories"])
            lines[1] = f"🔥 Калории: ⚠️ перебор на {over} ккал"

        return "\n".join(lines)

    @tool
    async def meal_clone_recent(
        meal_type: str = "",
        days_back: int = 1,
    ) -> str:
        """Клонировать недавний приём пищи в черновик.
        meal_type — breakfast | lunch | dinner | snack (если пусто — любой)
        days_back — сколько дней назад искать (1 = вчера, 0 = сегодня)
        Используй когда пользователь говорит 'как вчера', 'повтори завтрак', 'то же что вчера на обед'.
        """
        mt = meal_type if meal_type else None
        recent = await ns.get_recent_meals(user_id, meal_type=mt, limit=5)

        if not recent:
            return "Не нашёл недавних приёмов пищи для клонирования."

        # Ищем подходящий приём по days_back
        target_date = date.today() - timedelta(days=days_back)
        target_meal = None

        for m in recent:
            eaten_str = m.get("eaten_at", "")
            if eaten_str:
                try:
                    eaten_date = datetime.fromisoformat(eaten_str).date()
                    if eaten_date == target_date:
                        target_meal = m
                        break
                except (ValueError, AttributeError):
                    continue

        # Если не нашли за конкретный день — берём первый из недавних
        if not target_meal:
            target_meal = recent[0]

        # Создаём draft из найденного приёма
        items = [
            {
                "name": item["name"],
                "amount_g": item["amount_g"],
                "calories": item["calories"],
                "protein_g": item["protein_g"],
                "fat_g": item["fat_g"],
                "carbs_g": item["carbs_g"],
            }
            for item in target_meal.get("items", [])
        ]

        if not items:
            return "Не удалось клонировать — в найденном приёме нет продуктов."

        m_type = target_meal.get("meal_type", "snack")
        draft = create_draft(user_id, items=items, meal_type=m_type, source="clone")
        card = format_draft_card(draft)
        src_date = target_meal.get("eaten_at", "")[:10]

        return f"📋 Клонирован {_meal_type_ru(m_type)} от {src_date}:\n{card}\nПодтверди или внеси правки."

    @tool
    async def meal_template_save(
        name: str,
        meal_id: int = 0,
    ) -> str:
        """Сохранить приём пищи как шаблон.
        name — название шаблона (например 'Мой завтрак')
        meal_id — ID приёма (если 0, сохранит последний подтверждённый приём)
        Используй когда пользователь говорит 'сохрани как шаблон', 'запомни этот приём'.
        """
        if meal_id > 0:
            result = await ns.create_template_from_meal(user_id, meal_id, name)
            if result:
                return f"✅ Шаблон «{name}» сохранён (ID: {result['id']}, {len(result.get('items', []))} продуктов)."
            return "Не удалось создать шаблон — приём пищи не найден."

        # Если meal_id не указан — берём последний приём
        recent = await ns.get_recent_meals(user_id, meal_type=None, limit=1)
        if not recent:
            return "Нет недавних приёмов пищи для сохранения как шаблон."

        last_meal = recent[0]
        result = await ns.create_template_from_meal(user_id, last_meal["id"], name)
        if result:
            return (
                f"✅ Шаблон «{name}» сохранён из последнего приёма "
                f"({_meal_type_ru(last_meal['meal_type'])} · {len(result.get('items', []))} продуктов)."
            )
        return "Не удалось создать шаблон."

    @tool
    async def nutrition_daily_score(
        target_date: str = "",
    ) -> str:
        """Показать оценку дня по питанию (score 0-100).
        target_date — дата в формате YYYY-MM-DD (если пусто — сегодня)
        Вызывай когда пользователь спрашивает 'оценка за день', 'как у меня сегодня', 'score'.
        """
        if target_date:
            try:
                d = date.fromisoformat(target_date)
            except ValueError:
                return "Некорректный формат даты. Используй YYYY-MM-DD."
        else:
            d = date.today()

        result = await calculate_daily_score(user_id, d)
        return format_score_card(result)

    @tool
    async def nutrition_weekly_summary_tool() -> str:
        """Показать итоги за неделю — LLM-обзор с рекомендациями.
        Вызывай когда пользователь спрашивает 'итоги за неделю', 'обзор', 'weekly summary'.
        """
        result = await generate_weekly_summary(user_id)
        return result["text"]

    @tool
    async def meal_reload_last() -> str:
        """Загрузить последний сохранённый приём пищи обратно в черновик для редактирования.
        Вызывай когда пользователь хочет изменить/отредактировать/поменять что-то 
        в УЖЕ СОХРАНЁННОМ приёме (не в draft). Признаки: 'поменяй', 'измени', 'исправь' 
        + контекст [LAST_SAVED].
        """
        ctx = get_context(user_id)
        if not ctx or not ctx.last_saved_entity:
            # Пробуем взять из БД последний приём
            recent = await ns.get_recent_meals(user_id, meal_type=None, limit=1)
            if not recent:
                return "Нет недавних приёмов пищи для редактирования."
            last_meal = recent[0]
        else:
            last_meal = ctx.last_saved_entity

        # Конвертируем сохранённый meal обратно в draft
        items = [
            {
                "name": item["name"],
                "amount_g": item["amount_g"],
                "calories": item["calories"],
                "protein_g": item["protein_g"],
                "fat_g": item["fat_g"],
                "carbs_g": item["carbs_g"],
            }
            for item in last_meal.get("items", [])
        ]
        if not items:
            return "Не удалось загрузить — в приёме нет продуктов."

        m_type = last_meal.get("meal_type", "snack")
        draft = create_draft(user_id, items=items, meal_type=m_type, source="edit")
        # Сохраняем ID оригинального meal для последующего удаления/замены
        draft.meta = {"original_meal_id": last_meal.get("id")}
        card = format_draft_card(draft)

        return (
            f"📋 Загружен для редактирования (ID: {last_meal.get('id', '?')}):\n{card}\n"
            f"Теперь можно вносить правки. После подтверждения — старый приём будет заменён."
        )

    return [meal_log, meal_delete, water_log, nutrition_stats, nutrition_goals_set, meal_from_template, food_search, ewa_product_info, meal_draft_create, meal_draft_update, meal_draft_confirm, meal_draft_discard, meal_check_pending, nutrition_remaining_today, meal_clone_recent, meal_template_save, nutrition_daily_score, nutrition_weekly_summary_tool, meal_reload_last]


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
