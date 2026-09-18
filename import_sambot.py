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

def clean(v):
    return (v or "").replace("\ufeff", "").strip()

def parse_csv():
    # The Sambot export has a fixed 6-column order:
    # ID, Имя, Фамилия, @username, first message date, last message date.
    # We deliberately use column positions instead of relying on Cyrillic
    # header decoding, because some CSV exports contain mixed/invalid bytes.
    raw = CSV_FILE.read_bytes()

    encodings = ["utf-8-sig", "utf-8", "cp1251", "cp1252", "latin-1"]
    text = None
    used = None

    for enc in encodings:
        try:
            text = raw.decode(enc)
            used = enc
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        text = raw.decode("utf-8", errors="replace")
        used = "utf-8 (errors=replace)"

    try:
        dialect = csv.Sniffer().sniff(text[:10000], delimiters=",;\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    rows = list(csv.reader(text.splitlines(), delimiter=delimiter))

    if not rows:
        raise SystemExit("CSV пустой.")

    # Find the first row that looks like the header.
    header_index = 0
    for i, row in enumerate(rows[:10]):
        if len(row) >= 4:
            first = clean(row[0]).lower()
            if first in ("id", "telegram id", "telegram_id", "user_id") or first.isdigit() is False:
                header_index = i
                break

    data_rows = rows[header_index + 1:]

    print(f"[CSV] Кодировка: {used}")
    print(f"[CSV] Разделитель: {repr(delimiter)}")
    print(f"[CSV] Заголовок: {rows[header_index]}")
    print(f"[CSV] Строк данных: {len(data_rows)}")

    return data_rows

def normalize_username(v):
    v = clean(v)
    return v[1:] if v.startswith("@") else (v or None)

def normalize_name(first, last):
    result = " ".join(x for x in (clean(first), clean(last)) if x)
    return result or "Пользователь"

def normalize_date(v):
    v = clean(v)
    return v or now()

def main():
    if not DB.exists():
        raise SystemExit(f"База не найдена: {DB}")
    if not CSV_FILE.exists():
        raise SystemExit("export.csv не найден рядом с import_sambot.py")

    rows = parse_csv()

    valid = []
    bad = 0
    seen = set()

    for row in rows:
        if len(row) < 6:
            bad += 1
            continue

        try:
            uid = int(clean(row[0]))
            if uid <= 0:
                raise ValueError
        except ValueError:
            # Ignore empty/summary/footer rows.
            bad += 1
            continue

        if uid in seen:
            continue
        seen.add(uid)

        valid.append((
            uid,
            normalize_username(row[3]),
            normalize_name(row[1], row[2]),
            normalize_date(row[4]),
            normalize_date(row[5]),
        ))

    print(f"[CSV] Корректных пользователей: {len(valid)}")
    print(f"[CSV] Пропущено строк: {bad}")

    if not valid:
        raise SystemExit("Не найдено ни одного корректного Telegram ID. Импорт отменён.")

    # Backup only after CSV validation.
    backup = DB.with_name(
        f"bot.sqlite3.backup_before_sambot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    shutil.copy2(DB, backup)
    print(f"[BACKUP] {backup.name}")

    inserted = 0
    updated = 0

    with sqlite3.connect(DB, timeout=30) as c:
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("BEGIN")

        for uid, username, name, first_seen, last_seen in valid:
            existing = c.execute(
                "SELECT id FROM users WHERE id=?", (uid,)
            ).fetchone()

            if existing:
                # Existing balance/payment/history is preserved.
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
                # Imported Sambot users get zero requests.
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
    print(f"Пользователей в CSV:    {len(rows)}")
    print(f"Новых добавлено:        {inserted}")
    print(f"Обновлено существующих: {updated}")
    print(f"Пропущено строк:        {bad}")
    print(f"Резервная копия:        {backup.name}")
    print()
    print("Импортированные пользователи получили 0 запросов.")
    print("Баланс, оплаты и история существующих пользователей не изменены.")

if __name__ == "__main__":
    main()
