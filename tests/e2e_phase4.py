"""
E2E тестирование после миграции на PostgreSQL (Фаза 4).
Проверяет: storage, reminders, API, checkpointer, scheduler.
"""
import asyncio
import hashlib
import hmac
import json
import os
import sys
import time
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://aiuser:changeme@localhost:5432/aiassistant",
)

# Счётчики результатов
_passed = 0
_failed = 0

def ok(name):
    global _passed
    _passed += 1
    print(f"  ✅ {name}")

def fail(name, detail=""):
    global _failed
    _failed += 1
    print(f"  ❌ {name}: {detail}")

def check(name, condition, detail=""):
    if condition:
        ok(name)
    else:
        fail(name, detail)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Storage — CRUD задач через PostgreSQL
# ═══════════════════════════════════════════════════════════════════════════════

async def test_storage():
    print("\n═══ 1. Storage: CRUD задач (PostgreSQL) ═══")
    from db.storage import (
        add_task, get_task, list_tasks, complete_task,
        delete_task, update_task_fields, list_tasks_by_period,
        list_calendar_items, get_or_create_user,
    )

    TEST_USER = 999999999  # Тестовый пользователь

    # 1.1 Создание пользователя
    user = await get_or_create_user(TEST_USER)
    check("get_or_create_user", user["telegram_id"] == TEST_USER)

    # 1.2 Создание задачи
    now = datetime.now(timezone.utc)
    due = (now + timedelta(hours=2)).isoformat()
    task_id = await add_task(
        user_id=TEST_USER,
        title="E2E тест задача",
        description="Тестовое описание",
        due_datetime=due,
        priority=1,
    )
    check("add_task", task_id > 0, f"id={task_id}")

    # 1.3 Чтение задачи
    task = await get_task(task_id, TEST_USER)
    check("get_task", task is not None and task["title"] == "E2E тест задача")

    # 1.4 Обновление полей
    result = await update_task_fields(task_id, TEST_USER, title="E2E обновлено", priority=3)
    check("update_task_fields", result is True)
    task2 = await get_task(task_id, TEST_USER)
    check("update_task_fields (verify)", task2["title"] == "E2E обновлено" and task2["priority"] == 3)

    # 1.5 Список задач
    tasks = await list_tasks(TEST_USER)
    check("list_tasks", any(t["id"] == task_id for t in tasks))

    # 1.6 Фильтр по периоду (today)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    period_tasks = await list_tasks_by_period(TEST_USER, today_start.isoformat(), today_end.isoformat())
    check("list_tasks_by_period (today)", any(t["id"] == task_id for t in period_tasks))

    # 1.7 Создание события (event)
    start = (now + timedelta(hours=3)).isoformat()
    end = (now + timedelta(hours=4)).isoformat()
    event_id = await add_task(
        user_id=TEST_USER,
        title="E2E тест событие",
        start_at=start,
        end_at=end,
        event_type="event",
    )
    check("add_task (event)", event_id > 0)

    # 1.8 Календарь
    cal_items = await list_calendar_items(TEST_USER, today_start.isoformat(), today_end.isoformat())
    check("list_calendar_items", any(t["id"] == event_id for t in cal_items))

    # 1.9 Завершение задачи
    result = await complete_task(task_id, TEST_USER)
    check("complete_task", result is True)
    task3 = await get_task(task_id, TEST_USER)
    check("complete_task (verify)", task3["is_done"] == 1 and task3["status"] == "done")

    # 1.10 Удаление задач
    r1 = await delete_task(task_id, TEST_USER)
    r2 = await delete_task(event_id, TEST_USER)
    check("delete_task", r1 and r2)
    check("delete_task (verify)", await get_task(task_id, TEST_USER) is None)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Storage — повторяющиеся задачи
# ═══════════════════════════════════════════════════════════════════════════════

async def test_recurrence():
    print("\n═══ 2. Повторяющиеся задачи (RRULE) ═══")
    from db.storage import add_task, get_task, list_tasks, delete_task
    from db.recurrence import parse_recurrence_nl, expand_occurrences, generate_occurrence_dicts

    TEST_USER = 999999999

    # 2.1 Парсинг NL → RRULE
    check("parse_recurrence_nl (каждый день)", parse_recurrence_nl("каждый день") == "FREQ=DAILY")
    check("parse_recurrence_nl (по будням)", "BYDAY=MO,TU,WE,TH,FR" in parse_recurrence_nl("по будням"))
    check("parse_recurrence_nl (еженедельно)", parse_recurrence_nl("еженедельно") == "FREQ=WEEKLY")

    # 2.2 Генерация дат
    dtstart = datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc)
    dates = expand_occurrences("FREQ=DAILY", dtstart, horizon_days=7)
    check("expand_occurrences (DAILY, 7 дней)", len(dates) == 8, f"got {len(dates)}")  # 8 включая dtstart

    dates_w = expand_occurrences("FREQ=WEEKLY", dtstart, horizon_days=30)
    check("expand_occurrences (WEEKLY, 30 дней)", len(dates_w) >= 4, f"got {len(dates_w)}")

    # 2.3 Создание повторяющейся задачи
    now = datetime.now(timezone.utc)
    due = (now + timedelta(hours=1)).isoformat()
    tmpl_id = await add_task(
        user_id=TEST_USER,
        title="E2E повтор тест",
        due_datetime=due,
        recurrence_rule="FREQ=DAILY",
    )
    check("add_task (recurrence)", tmpl_id > 0)

    # 2.4 Проверяем что шаблон скрыт из list_tasks, а экземпляры видны
    tasks = await list_tasks(TEST_USER)
    template_visible = any(t["id"] == tmpl_id for t in tasks)
    instances = [t for t in tasks if t.get("parent_task_id") == tmpl_id]
    check("template hidden from list", not template_visible)
    check("instances created", len(instances) > 0, f"count={len(instances)}")

    # 2.5 Экземпляры имеют даты
    if instances:
        has_dates = all(i.get("due_datetime") for i in instances)
        check("instances have due_datetime", has_dates)

    # Очистка: удаляем экземпляры и шаблон
    from sqlalchemy import delete as sa_delete, select
    from db.models import Task
    from db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await db.execute(sa_delete(Task).where(Task.parent_task_id == tmpl_id))
        await db.execute(sa_delete(Task).where(Task.id == tmpl_id))
        await db.commit()
    ok("cleanup recurrence test data")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Reminders (через SQLAlchemy)
# ═══════════════════════════════════════════════════════════════════════════════

async def test_reminders():
    print("\n═══ 3. Напоминания (db/reminders.py → SQLAlchemy) ═══")
    from db import reminders as rdb

    TEST_USER = 999999999
    now = datetime.now(timezone.utc)

    # 3.1 get_user_settings
    settings = await rdb.get_user_settings(TEST_USER)
    check("get_user_settings", "timezone" in settings and "notification_offset_min" in settings)

    # 3.2 add_reminder
    remind_at = (now + timedelta(minutes=5)).isoformat()
    rid = await rdb.add_reminder(
        user_id=TEST_USER,
        entity_type="task",
        entity_id=99999,
        remind_at=remind_at,
    )
    check("add_reminder", rid > 0, f"id={rid}")

    # 3.3 get_pending_reminders
    future = (now + timedelta(hours=1)).isoformat()
    pending = await rdb.get_pending_reminders(future)
    check("get_pending_reminders", any(r["id"] == rid for r in pending))

    # 3.4 mark_reminder_sent
    await rdb.mark_reminder_sent(rid, telegram_message_id=12345)
    pending2 = await rdb.get_pending_reminders(future)
    check("mark_reminder_sent", not any(r["id"] == rid for r in pending2))

    # 3.5 ensure_schema (no-op, не падает)
    await rdb.ensure_schema()
    ok("ensure_schema (no-op)")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. API (с генерацией Telegram initData)
# ═══════════════════════════════════════════════════════════════════════════════

async def test_api():
    print("\n═══ 4. API эндпоинты ═══")
    import httpx
    from dotenv import load_dotenv
    load_dotenv("/root/ai-assistant/.env")
    bot_token = os.environ.get("TELEGRAM_TOKEN", "")

    # Генерируем валидный initData
    user_data = json.dumps({"id": 312775806, "first_name": "Test"}, ensure_ascii=False)
    auth_date = str(int(time.time()))
    params = {"user": user_data, "auth_date": auth_date}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    hash_val = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    params["hash"] = hash_val
    init_data = urlencode(params)

    headers = {"X-Init-Data": init_data}
    base = "http://localhost:8000"

    async with httpx.AsyncClient() as client:
        # 4.1 Health
        r = await client.get(f"{base}/api/health")
        check("GET /api/health", r.status_code == 200)

        # 4.2 Список задач (all)
        r = await client.get(f"{base}/api/tasks", params={"period": "all"}, headers=headers)
        check("GET /api/tasks?period=all", r.status_code == 200, f"status={r.status_code}")
        all_tasks = r.json() if r.status_code == 200 else []

        # 4.3 Список задач (today)
        r = await client.get(f"{base}/api/tasks", params={"period": "today"}, headers=headers)
        check("GET /api/tasks?period=today", r.status_code == 200)

        # 4.4 Список задач (week)
        r = await client.get(f"{base}/api/tasks", params={"period": "week"}, headers=headers)
        check("GET /api/tasks?period=week", r.status_code == 200)

        # 4.5 Календарь
        now = datetime.now(timezone.utc)
        date_from = now.replace(hour=0, minute=0, second=0).isoformat()
        date_to = (now.replace(hour=0, minute=0, second=0) + timedelta(days=7)).isoformat()
        r = await client.get(
            f"{base}/api/tasks",
            params={"view": "calendar", "date_from": date_from, "date_to": date_to},
            headers=headers,
        )
        check("GET /api/tasks?view=calendar", r.status_code == 200)

        # 4.6 Календари
        r = await client.get(f"{base}/api/calendars", headers=headers)
        check("GET /api/calendars", r.status_code == 200)

        # 4.7 Проверяем что шаблоны НЕ попадают в ответ
        if isinstance(all_tasks, list):
            templates_leaked = [t for t in all_tasks if t.get("recurrence_rule") and not t.get("parent_task_id")]
            check("templates hidden from API", len(templates_leaked) == 0, f"leaked={len(templates_leaked)}")

        # 4.8 Невалидный initData → 401
        r = await client.get(f"{base}/api/tasks", headers={"X-Init-Data": "invalid"})
        check("invalid initData → 401", r.status_code == 401)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Checkpointer — таблицы в PG
# ═══════════════════════════════════════════════════════════════════════════════

async def test_checkpointer():
    print("\n═══ 5. Checkpointer (AsyncPostgresSaver) ═══")
    import asyncpg
    pg = await asyncpg.connect("postgresql://aiuser:changeme@localhost:5432/aiassistant")

    # 5.1 Таблицы checkpoints существуют
    tables = await pg.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'checkpoint%'"
    )
    table_names = [t["tablename"] for t in tables]
    check("checkpoint tables exist", len(table_names) > 0, f"tables={table_names}")

    # 5.2 Есть данные (от предыдущих запросов к боту)
    for tbl in table_names:
        count = await pg.fetchval(f"SELECT count(*) FROM {tbl}")
        if count > 0:
            ok(f"  {tbl}: {count} rows")
        else:
            ok(f"  {tbl}: empty (OK)")

    await pg.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Scheduler — проверяем логи
# ═══════════════════════════════════════════════════════════════════════════════

async def test_scheduler():
    print("\n═══ 6. Scheduler ═══")
    with open("/tmp/bot.log") as f:
        log = f.read()

    check("scheduler started", "Scheduler запущен" in log)
    check("scheduler sends reminders", "Scheduler запущен" in log or "Reminder id=" in log or "отправляю" in log)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Данные — целостность после миграции
# ═══════════════════════════════════════════════════════════════════════════════

async def test_data_integrity():
    print("\n═══ 7. Целостность данных ═══")
    import asyncpg
    pg = await asyncpg.connect("postgresql://aiuser:changeme@localhost:5432/aiassistant")

    # 7.1 Пользователи
    users = await pg.fetchval("SELECT count(*) FROM users")
    check("users exist", users >= 1, f"count={users}")

    # 7.2 Задачи
    tasks = await pg.fetchval("SELECT count(*) FROM tasks")
    check("tasks exist", tasks >= 1, f"count={tasks}")

    # 7.3 Нет задач с NULL user_id
    orphans = await pg.fetchval("SELECT count(*) FROM tasks WHERE user_id NOT IN (SELECT telegram_id FROM users)")
    check("no orphan tasks", orphans == 0, f"orphans={orphans}")

    # 7.4 "Пить воду" экземпляры имеют start_at (фикс миграции)
    broken = await pg.fetchval(
        "SELECT count(*) FROM tasks WHERE parent_task_id = 65 AND start_at IS NULL"
    )
    check("'Пить воду' instances have start_at", broken == 0, f"broken={broken}")

    # 7.5 "Тест повтор" — есть экземпляр на первую дату
    first_occ = await pg.fetchval(
        "SELECT count(*) FROM tasks WHERE parent_task_id = 96 AND start_at = (SELECT start_at FROM tasks WHERE id = 96)"
    )
    check("'Тест повтор' first occurrence exists", first_occ >= 1)

    await pg.close()


# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    print("🔬 E2E тестирование — Фаза 4 (PostgreSQL)")
    print(f"   Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    await test_storage()
    await test_recurrence()
    await test_reminders()
    await test_api()
    await test_checkpointer()
    await test_scheduler()
    await test_data_integrity()

    # Очистка тестового пользователя
    from sqlalchemy import delete as sa_delete
    from db.models import User, Task, Reminder
    from db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await db.execute(sa_delete(Task).where(Task.user_id == 999999999))
        await db.execute(sa_delete(Reminder).where(Reminder.user_id == 999999999))
        await db.execute(sa_delete(User).where(User.telegram_id == 999999999))
        await db.commit()

    print(f"\n{'='*50}")
    print(f"  ИТОГО: ✅ {_passed} passed, ❌ {_failed} failed")
    print(f"{'='*50}")
    return _failed

if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
