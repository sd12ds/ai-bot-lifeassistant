"""
Фоновый планировщик контекстных советов по питанию.

Расписание (по часовому поясу DEFAULT_TZ):
  - ~14:00 — дневные советы (прогресс за первую половину дня)
  - ~21:00 — вечерний итог дня + еженедельная сводка (по воскресеньям)

Антиспам: не отправляем если уже отправляли за текущий таймслот.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, date

from aiogram import Bot
from sqlalchemy import select

from config import DEFAULT_TZ
from db.models import NutritionGoal
from db.session import AsyncSessionLocal
from services.nutrition_insights import (
    generate_daily_tips,
    generate_evening_summary,
    generate_weekly_tips,
)

logger = logging.getLogger(__name__)

# Хранилище отправленных таймслотов: {user_id: {date_str: set(slot)}}
# Антиспам — не отправляем повторно за один таймслот
_sent_slots: dict[int, dict[str, set[str]]] = {}


def _already_sent(user_id: int, slot: str) -> bool:
    """Проверяем, отправляли ли совет за текущий таймслот сегодня."""
    today_str = date.today().isoformat()
    user_slots = _sent_slots.get(user_id, {})
    return slot in user_slots.get(today_str, set())


def _mark_sent(user_id: int, slot: str) -> None:
    """Помечаем таймслот как отправленный."""
    today_str = date.today().isoformat()
    if user_id not in _sent_slots:
        _sent_slots[user_id] = {}
    if today_str not in _sent_slots[user_id]:
        # Очищаем старые дни
        _sent_slots[user_id] = {today_str: set()}
    _sent_slots[user_id][today_str].add(slot)


async def _get_users_with_goals() -> list[int]:
    """Возвращает список user_id у которых есть цели по питанию."""
    async with AsyncSessionLocal() as session:
        stmt = select(NutritionGoal.user_id)
        result = await session.execute(stmt)
        return [row[0] for row in result.all()]


async def _send_afternoon_tips(bot: Bot) -> None:
    """Дневные советы (~14:00): проверка прогресса за первую половину дня."""
    users = await _get_users_with_goals()
    now = datetime.now(DEFAULT_TZ)
    slot = "afternoon"

    for user_id in users:
        if _already_sent(user_id, slot):
            continue
        try:
            tips = await generate_daily_tips(user_id, current_hour=now.hour)
            if tips:
                text = "\n".join(tips)
                await bot.send_message(user_id, text)
                logger.info("Nutrition tips (afternoon) отправлены user=%s", user_id)
            _mark_sent(user_id, slot)
        except Exception as e:
            logger.error("Ошибка отправки nutrition tips user=%s: %s", user_id, e)


async def _send_evening_summary(bot: Bot) -> None:
    """Вечерний итог (~21:00): сводка дня + еженедельные советы по воскресеньям."""
    users = await _get_users_with_goals()
    now = datetime.now(DEFAULT_TZ)
    slot = "evening"
    is_sunday = now.weekday() == 6  # 0=пн, 6=вс

    for user_id in users:
        if _already_sent(user_id, slot):
            continue
        try:
            parts: list[str] = []

            # Итог дня
            summary = await generate_evening_summary(user_id)
            if summary:
                parts.append(summary)

            # Еженедельные советы (по воскресеньям)
            if is_sunday:
                weekly = await generate_weekly_tips(user_id)
                if weekly:
                    parts.append("\n📈 Неделя:")
                    parts.extend(weekly)

            # Дневные советы к вечеру
            tips = await generate_daily_tips(user_id, current_hour=now.hour)
            if tips:
                parts.extend(tips)

            if parts:
                text = "\n".join(parts)
                await bot.send_message(user_id, text)
                logger.info("Nutrition summary (evening) отправлен user=%s", user_id)

            _mark_sent(user_id, slot)
        except Exception as e:
            logger.error("Ошибка отправки evening summary user=%s: %s", user_id, e)


def start_nutrition_tips_scheduler(bot: Bot, check_interval: int = 60) -> asyncio.Task:
    """
    Запускает фоновую asyncio-задачу для отправки советов по питанию.

    Каждые check_interval секунд проверяет текущее время (DEFAULT_TZ)
    и отправляет советы в нужные таймслоты.
    """
    async def _loop() -> None:
        logger.info("Nutrition tips scheduler запущен")
        while True:
            try:
                now = datetime.now(DEFAULT_TZ)
                hour = now.hour

                # Дневной таймслот: 14:00–14:59
                if hour == 14:
                    await _send_afternoon_tips(bot)

                # Вечерний таймслот: 21:00–21:59
                if hour == 21:
                    await _send_evening_summary(bot)

            except Exception as e:
                logger.error("Nutrition tips scheduler ошибка: %s", e, exc_info=True)

            await asyncio.sleep(check_interval)

    task = asyncio.create_task(_loop(), name="nutrition_tips_scheduler")
    return task
