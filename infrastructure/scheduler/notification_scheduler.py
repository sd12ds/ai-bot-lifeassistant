"""
Фоновый планировщик уведомлений (asyncio-петля, каждые N секунд).
Выбирает просроченные reminders и отправляет сообщения через Telegram-бота.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from db import reminders as rdb

logger = logging.getLogger(__name__)


async def _build_message(rem: dict) -> tuple[str, "InlineKeyboardMarkup | None"]:
    """Формирует текст уведомления по типу сущности."""
    if rem["entity_type"] == "task":
        task = await rdb.get_task(rem["entity_id"], rem["user_id"])
        if not task:
            return "⏰ Напоминание (задача не найдена)", None
        title = task.get("title", "Задача")
        due = task.get("due_datetime", "")
        # Форматируем дедлайн с учётом TZ пользователя
        if due:
            try:
                us = await rdb.get_user_settings(rem["user_id"])
                from zoneinfo import ZoneInfo
                dt = datetime.fromisoformat(due).astimezone(ZoneInfo(us["timezone"]))
                due = dt.strftime("%d.%m.%Y %H:%M")
            except Exception:
                pass
        due_str = f"\n🕐 Дедлайн: {due}" if due else ""
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(
                text="✅ Выполнено",
                callback_data=f"task_done:{task.get('id')}",
            )]]
        )
        return f"⏰ Напоминание о задаче\n📋 {title}{due_str}", kb
    # Зарезервировано на Фазу 2 (события)
    return "⏰ Напоминание", None


async def check_and_send_reminders(bot: Bot, batch_limit: int = 200) -> None:
    """
    Выбирает все pending-напоминания до текущего момента (UTC)
    и отправляет каждому пользователю сообщение.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    items = await rdb.get_pending_reminders(now_iso, limit=batch_limit)
    if not items:
        return
    logger.info("Scheduler: отправляю %d напоминаний", len(items))
    for rem in items:
        try:
            text, kb = await _build_message(rem)
            msg = await bot.send_message(rem["user_id"], text, reply_markup=kb)
            await rdb.mark_reminder_sent(rem["id"], telegram_message_id=msg.message_id)
            logger.info("Reminder id=%s отправлено user=%s", rem["id"], rem["user_id"])
        except Exception as e:
            logger.error("Ошибка отправки reminder id=%s user=%s: %s",
                         rem["id"], rem["user_id"], e, exc_info=True)


async def regenerate_recurring_tasks() -> None:
    """Регенерирует экземпляры повторяющихся задач на горизонт 30 дней.
    Вызывается раз в сутки из scheduler loop.
    """
    try:
        from db.storage import get_all_recurring_templates, regenerate_occurrences
        templates = await get_all_recurring_templates()
        total = 0
        for tmpl in templates:
            count = await regenerate_occurrences(
                template_id=tmpl["id"],
                user_id=tmpl["user_id"],
                horizon_days=30,
            )
            total += count
        if total:
            logger.info("Регенерация: создано %d экземпляров для %d шаблонов", total, len(templates))
    except Exception:
        logger.exception("Ошибка регенерации повторяющихся задач")


def start_notification_scheduler(bot: Bot, interval_seconds: int = 60) -> asyncio.Task:
    """
    Запускает фоновую asyncio-задачу планировщика.
    Возвращает Task — живёт до завершения event loop.
    """
    async def _loop() -> None:
        # Применяем миграции Фазы 1 при старте
        await rdb.ensure_schema()
        logger.info("Scheduler запущен, интервал=%ds", interval_seconds)
        while True:
            try:
                await check_and_send_reminders(bot)
            except Exception as e:
                logger.error("Scheduler: ошибка итерации: %s", e, exc_info=True)
            await asyncio.sleep(interval_seconds)
            # Раз в сутки запускаем регенерацию повторяющихся задач
            # (проверяем по счётчику итераций: 1440 итераций × 60с = 24ч)
            _loop._tick_count = getattr(_loop, '_tick_count', 0) + 1
            if _loop._tick_count % (86400 // interval_seconds) == 0:
                await regenerate_recurring_tasks()

    task = asyncio.create_task(_loop(), name="notification_scheduler")
    return task
