"""
Умный скрипт слияния данных SQLite → PostgreSQL.

Стратегия для задач (tasks):
  - ID не в PG                   → INSERT с тем же ID
  - ID в PG, заголовок совпадает → пропустить (уже есть)
  - ID в PG, заголовок отличается → INSERT без ID (новый автоинкремент)

Для users — ON CONFLICT DO UPDATE (актуальные настройки из SQLite).
Для reminders, crm_contacts — ON CONFLICT DO NOTHING.
"""
import asyncio
import os
import sqlite3
from datetime import datetime, timezone

import asyncpg

SQLITE_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'app.db')

PG_DSN = os.environ.get(
    'DATABASE_URL',
    'postgresql://aiuser:changeme@localhost:5432/aiassistant'
).replace('postgresql+asyncpg://', 'postgresql://')


def sqlite_rows(query: str) -> list:
    """Читает строки из SQLite."""
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(query)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def parse_dt(val):
    """Парсит ISO-строку в timezone-aware datetime."""
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(str(val))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


async def merge():
    print(f'Подключаемся к: {PG_DSN}')
    pg = await asyncpg.connect(PG_DSN)

    # ── Текущее состояние PostgreSQL ──────────────────────────────────────────
    pg_tasks = {row['id']: row['title'] for row in await pg.fetch('SELECT id, title FROM tasks')}
    print(f'PostgreSQL задач: {len(pg_tasks)}')

    # ── Users — обновляем актуальные настройки из SQLite ─────────────────────
    users = sqlite_rows('SELECT * FROM users')
    print(f'SQLite пользователей: {len(users)}')
    for u in users:
        await pg.execute(
            '''
            INSERT INTO users (telegram_id, mode, timezone, notification_offset_min, created_at)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (telegram_id) DO UPDATE
              SET mode = EXCLUDED.mode,
                  timezone = EXCLUDED.timezone,
                  notification_offset_min = EXCLUDED.notification_offset_min
            ''',
            u['telegram_id'],
            u.get('mode', 'personal'),
            u.get('timezone', 'Europe/Moscow'),
            u.get('notification_offset_min', 15),
            parse_dt(u.get('created_at')) or datetime.now(timezone.utc),
        )
    print('  ✓ users обновлены')

    # ── Tasks — умное слияние ────────────────────────────────────────────────
    # Допустимые user_id — только существующие в таблице users
    valid_user_ids = {u['telegram_id'] for u in users}
    all_tasks = sqlite_rows('SELECT * FROM tasks')
    tasks = [t for t in all_tasks if t['user_id'] in valid_user_ids]
    skipped_invalid = len(all_tasks) - len(tasks)
    print(f'SQLite задач: {len(all_tasks)} (пропущено невалидных user_id: {skipped_invalid})')

    added_same_id = 0
    added_new_id = 0
    skipped = 0

    for t in tasks:
        tid = t['id']
        ttitle = t.get('title', '')

        if tid not in pg_tasks:
            # ID нет в PG — добавляем с тем же ID
            await pg.execute(
                '''
                INSERT INTO tasks (
                    id, user_id, title, description,
                    event_type, status, priority, tags,
                    due_datetime, start_at, end_at, is_all_day, remind_at,
                    recurrence_rule, parent_task_id, is_done,
                    created_at, updated_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
                ON CONFLICT (id) DO NOTHING
                ''',
                tid, t['user_id'], ttitle,
                t.get('description', ''),
                t.get('event_type', 'task'),
                t.get('status', 'todo'),
                t.get('priority', 2),
                t.get('tags', '[]'),
                parse_dt(t.get('due_datetime')),
                parse_dt(t.get('start_at')),
                parse_dt(t.get('end_at')),
                bool(t.get('is_all_day', 0)),
                parse_dt(t.get('remind_at')),
                t.get('recurrence_rule'),
                t.get('parent_task_id'),
                bool(t.get('is_done', 0)),
                parse_dt(t.get('created_at')) or datetime.now(timezone.utc),
                parse_dt(t.get('created_at')) or datetime.now(timezone.utc),
            )
            added_same_id += 1
            print(f'  + [{tid}] {ttitle!r} (тот же ID)')

        elif pg_tasks[tid] == ttitle:
            # ID есть, заголовки совпадают — пропускаем
            skipped += 1

        else:
            # Конфликт: тот же ID, разный заголовок — добавляем с новым ID
            new_id = await pg.fetchval(
                '''
                INSERT INTO tasks (
                    user_id, title, description,
                    event_type, status, priority, tags,
                    due_datetime, start_at, end_at, is_all_day, remind_at,
                    recurrence_rule, parent_task_id, is_done,
                    created_at, updated_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
                RETURNING id
                ''',
                t['user_id'], ttitle,
                t.get('description', ''),
                t.get('event_type', 'task'),
                t.get('status', 'todo'),
                t.get('priority', 2),
                t.get('tags', '[]'),
                parse_dt(t.get('due_datetime')),
                parse_dt(t.get('start_at')),
                parse_dt(t.get('end_at')),
                bool(t.get('is_all_day', 0)),
                parse_dt(t.get('remind_at')),
                t.get('recurrence_rule'),
                t.get('parent_task_id'),
                bool(t.get('is_done', 0)),
                parse_dt(t.get('created_at')) or datetime.now(timezone.utc),
                parse_dt(t.get('created_at')) or datetime.now(timezone.utc),
            )
            added_new_id += 1
            print(f'  ~ [{tid}->{new_id}] {ttitle!r} (конфликт ID, новый ID={new_id})')

    # Сбрасываем sequence на реальный максимум
    await pg.execute("SELECT setval('tasks_id_seq', (SELECT MAX(id) FROM tasks))")
    print(f'  ✓ tasks: +{added_same_id} (тот же ID), +{added_new_id} (новый ID), {skipped} пропущено')

    # ── Reminders ────────────────────────────────────────────────────────────
    reminders = sqlite_rows('SELECT * FROM reminders')
    print(f'SQLite reminders: {len(reminders)}')
    added_r = 0
    for r in reminders:
        remind_at = parse_dt(r.get('remind_at'))
        if not remind_at:
            continue
        result = await pg.execute(
            '''
            INSERT INTO reminders (
                id, user_id, entity_type, entity_id,
                remind_at, is_sent, sent_at, telegram_message_id, created_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            ON CONFLICT (id) DO NOTHING
            ''',
            r['id'], r['user_id'],
            r.get('entity_type', 'task'),
            r.get('entity_id', 0),
            remind_at,
            bool(r.get('is_sent', 0)),
            parse_dt(r.get('sent_at')),
            r.get('telegram_message_id'),
            parse_dt(r.get('created_at')) or datetime.now(timezone.utc),
        )
        if result != 'INSERT 0 0':
            added_r += 1
    if reminders:
        await pg.execute(
            "SELECT setval('reminders_id_seq', GREATEST((SELECT MAX(id) FROM reminders), 1))"
        )
    print(f'  ✓ reminders: +{added_r}')

    # ── CRM contacts ─────────────────────────────────────────────────────────
    contacts = sqlite_rows('SELECT * FROM crm_contacts')
    print(f'SQLite crm_contacts: {len(contacts)}')
    for c in contacts:
        await pg.execute(
            '''
            INSERT INTO crm_contacts (id, user_id, name, phone, email, notes, tags, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8)
            ON CONFLICT (id) DO NOTHING
            ''',
            c['id'], c['user_id'], c['name'],
            c.get('phone', ''), c.get('email', ''),
            c.get('notes', ''), '[]',
            parse_dt(c.get('created_at')) or datetime.now(timezone.utc),
        )
    print('  ✓ crm_contacts')

    await pg.close()
    print()
    print('✅ Слияние завершено успешно!')

    # Итоговая статистика
    pg2 = await asyncpg.connect(PG_DSN)
    stats = await pg2.fetchrow(
        'SELECT (SELECT count(*) FROM users) as u, (SELECT count(*) FROM tasks) as t'
    )
    print(f'PostgreSQL итого: {stats["u"]} пользователей, {stats["t"]} задач')
    await pg2.close()


if __name__ == '__main__':
    asyncio.run(merge())
