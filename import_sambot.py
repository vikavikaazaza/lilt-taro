from pathlib import Path
import csv
import shutil
import sqlite3
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent
DB = BASE / "data" / "bot.sqlite3"
CSV_FILE = BASE / "export.csv"

def now():
    return datetime.now(timezone.utc).isoformat()

def normalize_username(value):
    value = (value or "").strip()
    if value.startswith("@"):
        value = value[1:]
    return value or None

def normalize_name(first_name, last_name):
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()
    return " ".join(x for x in (first_name, last_name) if x).strip() or "Пользователь"

def normalize_date(value):
    value = (value or "").strip()
    if not value:
        return now()
    try:
        # Validate the ISO timestamp but keep the original value.
        datetime.fromisoformat(value)
        return value
    except ValueError:
        return now()

def main():
    if not DB.exists():
        raise SystemExit(f"База не найдена: {DB}")
    if not CSV_FILE.exists():
        raise SystemExit(
            f"Файл {CSV_FILE.name} не найден. "
            f"Положи export.csv рядом с import_sambot.py."
        )

    backup = DB.with_name(
        f"bot.sqlite3.backup_before_sambot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    shutil.copy2(DB, backup)
    print(f"[BACKUP] Создана копия: {backup.name}")

    inserted = 0
    updated = 0
    skipped = 0

    with open(CSV_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {
            "ID", "Имя", "Фамилия", "@username",
            "Дата первого сообщения", "Дата последнего сообщения"
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"В CSV отсутствуют колонки: {', '.join(sorted(missing))}")

        rows = list(reader)

    with sqlite3.connect(DB, timeout=30) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("BEGIN")

        for row in rows:
            raw_id = (row.get("ID") or "").strip()
            try:
                uid = int(raw_id)
                if uid <= 0:
                    raise ValueError
            except ValueError:
                skipped += 1
                continue

            username = normalize_username(row.get("@username"))
            name = normalize_name(row.get("Имя"), row.get("Фамилия"))
            first_seen = normalize_date(row.get("Дата первого сообщения"))
            last_seen = normalize_date(row.get("Дата последнего сообщения"))

            existing = c.execute(
                "SELECT id FROM users WHERE id = ?", (uid,)
            ).fetchone()

            if existing:
                # Existing balances, payments, subscriptions and history are untouched.
                c.execute(
                    """
                    UPDATE users
                    SET username = ?,
                        name = ?,
                        first_seen = CASE
                            WHEN first_seen IS NULL OR first_seen = '' THEN ?
                            WHEN ? < first_seen THEN ?
                            ELSE first_seen
                        END,
                        last_seen = CASE
                            WHEN last_seen IS NULL OR last_seen = '' THEN ?
                            WHEN ? > last_seen THEN ?
                            ELSE last_seen
                        END
                    WHERE id = ?
                    """,
                    (
                        username, name,
                        first_seen, first_seen, first_seen,
                        last_seen, last_seen, last_seen,
                        uid,
                    ),
                )
                updated += 1
            else:
                # Imported Sambot users do NOT receive a new free request.
                c.execute(
                    """
                    INSERT INTO users (
                        id, username, name, requests, paid_requests,
                        first_seen, last_seen, source, referrer_id,
                        free_granted, total_spent
                    )
                    VALUES (?, ?, ?, 0, 0, ?, ?, 'sambot', NULL, 0, 0)
                    """,
                    (uid, username, name, first_seen, last_seen),
                )
                c.execute(
                    """
                    INSERT INTO events(user_id, event, meta, created_at)
                    VALUES (?, 'sambot_import', 'Imported from Sambot', ?)
                    """,
                    (uid, now()),
                )
                inserted += 1

        c.commit()

    print()
    print("=== ИМПОРТ ЗАВЕРШЁН ===")
    print(f"Строк в CSV:      {len(rows)}")
    print(f"Новых пользователей: {inserted}")
    print(f"Обновлено существующих: {updated}")
    print(f"Пропущено некорректных ID: {skipped}")
    print(f"Резервная копия: {backup.name}")
    print()
    print("Важно: импортированные пользователи получили 0 запросов.")
    print("Существующие requests/paid_requests/оплаты/история не изменялись.")

if __name__ == "__main__":
    main()
