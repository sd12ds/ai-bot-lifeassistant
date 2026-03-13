import re
import sqlite3
import psycopg2
from datetime import datetime

SQLITE_PATH = "/root/ai-assistant/db/app.db"
PG_DSN = "dbname=aiassistant user=aiuser password=changeme host=localhost port=5432"


def parse_dt(s):
    if not s:
        return None
    s_clean = re.sub(r'[+-]\d{2}:\d{2}$', '', s.strip())
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s_clean, fmt)
        except ValueError:
            continue
    return None


def main():
    lite = sqlite3.connect(SQLITE_PATH)
    lite.row_factory = sqlite3.Row
    pg = psycopg2.connect(PG_DSN)
    pgc = pg.cursor()

    pgc.execute("SELECT telegram_id FROM users")
    pg_users = {row[0] for row in pgc.fetchall()}

    pgc.execute("SELECT id, user_id, title, event_type, start_at FROM tasks")
    pg_task_keys = {}
    for row in pgc.fetchall():
        start = str(row[4])[:19] if row[4] else ""
        key = (str(row[1]), row[2], row[3], start)
        pg_task_keys[key] = row[0]

    sqlite_tasks = lite.execute(
        "SELECT id, user_id, title, description, event_type, status, priority,"
        " tags, due_datetime, start_at, end_at, is_all_day,"
        " remind_at, recurrence_rule, is_done, created_at, updated_at"
        " FROM tasks ORDER BY id"
    ).fetchall()

    id_map = {}
    inserted_tasks = 0
    skipped = 0

    for st in sqlite_tasks:
        st = dict(st)
        if st["user_id"] not in pg_users:
            continue
        start_str = str(st["start_at"])[:19] if st["start_at"] else ""
        key = (str(st["user_id"]), st["title"], st["event_type"] or "task", start_str)
        if key in pg_task_keys:
            id_map[st["id"]] = pg_task_keys[key]
            skipped += 1
            continue
        pgc.execute(
            "INSERT INTO tasks (user_id, title, description, event_type, status,"
            " priority, tags, due_datetime, start_at, end_at, is_all_day,"
            " remind_at, recurrence_rule, is_done, created_at, updated_at)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (st["user_id"], st["title"], st["description"] or "",
             st["event_type"] or "task", st["status"] or "todo",
             st["priority"] or 2, st["tags"] or "[]",
             parse_dt(st["due_datetime"]), parse_dt(st["start_at"]),
             parse_dt(st["end_at"]), bool(st["is_all_day"]),
             parse_dt(st["remind_at"]), st["recurrence_rule"] or None,
             bool(st["is_done"]),
             parse_dt(st["created_at"]) or datetime.now(),
             parse_dt(st.get("updated_at") or st["created_at"]) or datetime.now()))
        new_id = pgc.fetchone()[0]
        id_map[st["id"]] = new_id
        inserted_tasks += 1

    pg.commit()
    print(f"Tasks: inserted={inserted_tasks}, skipped={skipped}")

    # Reminders
    pgc.execute("SELECT user_id, entity_type, entity_id, remind_at FROM reminders")
    pg_rem_keys = set()
    for row in pgc.fetchall():
        remind = str(row[3])[:19] if row[3] else ""
        pg_rem_keys.add((str(row[0]), row[1], str(row[2]), remind))

    sqlite_reminders = lite.execute(
        "SELECT id, user_id, entity_type, entity_id, remind_at,"
        " is_sent, sent_at, telegram_message_id, created_at"
        " FROM reminders ORDER BY id"
    ).fetchall()

    inserted_rem = 0
    skipped_rem = 0
    no_entity = 0

    for sr in sqlite_reminders:
        sr = dict(sr)
        if sr["user_id"] not in pg_users:
            skipped_rem += 1
            continue
        new_entity_id = id_map.get(sr["entity_id"])
        if new_entity_id is None:
            no_entity += 1
            continue
        remind_dt = parse_dt(sr["remind_at"])
        if remind_dt is None:
            no_entity += 1
            continue
        remind_str = str(remind_dt)[:19]
        check_key = (str(sr["user_id"]), sr["entity_type"], str(new_entity_id), remind_str)
        if check_key in pg_rem_keys:
            skipped_rem += 1
            continue
        pgc.execute(
            "INSERT INTO reminders (user_id, entity_type, entity_id, remind_at,"
            " is_sent, sent_at, telegram_message_id, created_at)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (sr["user_id"], sr["entity_type"], new_entity_id, remind_dt,
             bool(sr["is_sent"]), parse_dt(sr["sent_at"]),
             sr["telegram_message_id"],
             parse_dt(sr["created_at"]) or datetime.now()))
        inserted_rem += 1
        pg_rem_keys.add(check_key)

    pg.commit()
    print(f"Reminders: inserted={inserted_rem}, skipped={skipped_rem}, no_entity={no_entity}")
    lite.close()
    pg.close()


if __name__ == "__main__":
    main()
