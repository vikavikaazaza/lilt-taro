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

def clean(s):
    return (s or "").replace("\ufeff", "").strip()

def read_csv_rows():
    # Try several common encodings. csv.DictReader is used after normalizing
    # the header names, so harmless BOM/whitespace differences do not matter.
    encodings = ["utf-8-sig", "utf-8", "cp1251"]
    last_error = None

    for enc in encodings:
        try:
            with open(CSV_FILE, "r", encoding=enc, newline="") as f:
                sample = f.read(8192)
                f.seek(0)

                # Detect comma/semicolon/tab automatically.
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
                except csv.Error:
                    dialect = csv.excel
                    dialect.delimiter = ","

                reader = csv.DictReader(f, dialect=dialect)

                raw_fields = reader.fieldnames or []
                fields = [clean(x) for x in raw_fields]

                if len(fields) >= 4:
                    rows = []
                    for row in reader:
                        normalized = {}
                        for key, value in row.items():
                            normalized[clean(key)] = clean(value)
                        rows.append(normalized)
                    return fields, rows, enc

        except (UnicodeDecodeError, UnicodeError) as e:
            last_error = e

    raise RuntimeError(f"Не удалось прочитать CSV: {last_error}")

def find_col(fields, candidates):
    lower = {clean(x).lower(): x for x in fields}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None

def normalize_username(value):
    value = clean(value)
    if value.startswith("@"):
        value = value[1:]
    return value or None

def normalize_name(first_name, last_name):
    first_name = clean(first_name)
    last_name = clean(last_name)
    result = " ".join(x for x in (first_name, last_name) if x)
    return result or "Пользователь"

def normalize_date(value):
    value = clean(value)
    if not value:
        return now()
    # Keep the source value if it is a valid ISO date/time.
    try:
        datetime.fromisoformat(value)
        return value
    except ValueError:
        return now()

def main():
    if not DB.exists():
        raise SystemExit(f"База не найдена: {DB}")
    if not CSV_FILE.exists():
        raise SystemExit(f"Файл {CSV_FILE.name} не найден рядом со скриптом.")

    fields, rows, encoding = read_csv_rows()

    id_col = find_col(fields, ["ID", "id", "Telegram ID", "telegram_id", "user_id"])
    first_col = find_col(fields, ["Имя", "First Name", "first_name", "Name", "name"])
    last_col = find_col(fields, ["Фамилия", "Last Name", "last_name", "Surname", "surname"])
    username_col = find_col(fields, ["@username", "username", "Username", "Telegram Username"])
    first_seen_col = find_col(fields, [
        "Дата первого сообщения", "First message date",
        "first_message_date", "First seen", "first_seen"
    ])
    last_seen_col = find_col(fields, [
        "Дата последнего сообщения", "Last message date",
        "last_message_date", "Last seen", "last_seen"
    ])

    missing = []
    if not id_col: missing.append("ID")
    if not first_col: missing.append("Имя")
    if not last_col: missing.append("Фамилия")
    if not username_col: missing.append("@username")
    if not first_seen_col: missing.append("Дата первого сообщения")
    if not last_seen_col: missing.append("Дата последнего сообщения")

    print(f"[CSV] Кодировка: {encoding}")
    print(f"[CSV] Разделитель распознан автоматически")
    print(f"[CSV] Колонки: {fields}")
    print(f"[CSV] Строк найдено: {len(rows)}")

    if missing:
        raise SystemExit(
            "Не удалось определить обязательные колонки: "
            + ", ".join(missing)
            + "\nВерхняя строка файла должна содержать ID, Имя, Фамилия, @username "
              "и даты первого/последнего сообщения."
        )

    # Validate all IDs BEFORE touching the database.
    valid = []
    bad = []
    seen_ids = set()

    for line_no, row in enumerate(rows, start=2):
        raw_id = clean(row.get(id_col))
        try:
            uid = int(raw_id)
            if uid <= 0:
                raise ValueError
        except ValueError:
            bad.append((line_no, raw_id))
            continue

        if uid in seen_ids:
            continue
        seen_ids.add(uid)

        valid.append((
            uid,
            normalize_username(row.get(username_col)),
            normalize_name(row.get(first_col), row.get(last_col)),
            normalize_date(row.get(first_seen_col)),
            normalize_date(row.get(last_seen_col)),
        ))

    print(f"[CSV] Корректных пользователей: {len(valid)}")
    print(f"[CSV] Некорректных ID: {len(bad)}")

    if not valid:
        raise SystemExit("Нет ни одного корректного Telegram ID. Импорт отменён.")

    # Backup ONLY after the CSV has passed validation.
    backup = DB.with_name(
        f"bot.sqlite3.backup_before_sambot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    shutil.copy2(DB, backup)
    print(f"[BACKUP] Создана копия: {backup.name}")

    inserted = 0
    updated = 0

    with sqlite3.connect(DB, timeout=30) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("BEGIN")

        for uid, username, name, first_seen, last_seen in valid:
            existing = c.execute(
                "SELECT id FROM users WHERE id=?", (uid,)
            ).fetchone()

            if existing:
                # Do not touch balances, payments, total_spent or history.
                c.execute(
                    """
                    UPDATE users
                    SET username=?,
                        name=?,
                        first_seen=CASE
                            WHEN first_seen IS NULL OR first_seen='' THEN ?
                            WHEN ? < first_seen THEN ?
                            ELSE first_seen
                        END,
                        last_seen=CASE
                            WHEN last_seen IS NULL OR last_seen='' THEN ?
                            WHEN ? > last_seen THEN ?
                            ELSE last_seen
                        END
                    WHERE id=?
                    """,
                    (
                        username, name,
                        first_seen, first_seen, first_seen,
                        last_seen, last_seen, last_seen,
                        uid
                    )
                )
                updated += 1
            else:
                # Sambot users are imported with ZERO requests.
                # free_granted=0 prevents the normal first-registration free request.
                c.execute(
                    """
                    INSERT INTO users(
                        id, username, name, requests, paid_requests,
                        first_seen, last_seen, source, referrer_id,
                        free_granted, total_spent
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        uid, username, name, 0, 0,
                        first_seen, last_seen, "sambot", None,
                        0, 0
                    )
                )
                c.execute(
                    """
                    INSERT INTO events(user_id,event,meta,created_at)
                    VALUES(?,?,?,?)
                    """,
                    (uid, "sambot_import", "Imported from Sambot", now())
                )
                inserted += 1

        c.commit()

    print()
    print("=== ИМПОРТ ЗАВЕРШЁН ===")
    print(f"Пользователей в CSV:        {len(rows)}")
    print(f"Новых добавлено:            {inserted}")
    print(f"Существующих обновлено:     {updated}")
    print(f"Некорректных ID:             {len(bad)}")
    print(f"Резервная копия:             {backup.name}")
    print()
    print("Импортированные пользователи получили 0 запросов.")
    print("Баланс, оплаты и история существующих пользователей не изменены.")

if __name__ == "__main__":
    main()
