import json
import sqlite3
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "SIH26" / "airfare_index.db"
JSON_PATH = PROJECT_ROOT / "data" / "raw" / "airfare_index.json"

DRY_RUN = False


def main():
    print("=== DB → RAW JSON EXPORT ===")

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing = data.get("raw_fares", [])

    existing_count = len(existing)

    timestamps = [
        r.get("timestamp")
        for r in existing
        if r.get("timestamp")
    ]

    latest_json_timestamp = max(timestamps) if timestamps else None

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            timestamp,
            airline,
            route,
            advance_window_days,
            base_fare,
            taxes_fees,
            total_fare,
            ota_source
        FROM raw_fares
        ORDER BY id
    """)

    rows = cur.fetchall()
    conn.close()

    latest_db_timestamp = rows[-1][1] if rows else None

    if latest_json_timestamp:
        new_rows = [
            row for row in rows
            if row[1] > latest_json_timestamp
        ]
    else:
        new_rows = rows

    print(f"Existing JSON rows : {existing_count}")
    print(f"DB rows             : {len(rows)}")
    print(f"Latest JSON time    : {latest_json_timestamp}")
    print(f"Latest DB time      : {latest_db_timestamp}")
    print(f"Rows eligible       : {len(new_rows)}")

    if new_rows:
        print("\nFirst 5 rows that WOULD be appended:")
        for row in new_rows[:5]:
            print(row)

    if DRY_RUN:
        print("\nDRY RUN: JSON was NOT modified.")
        return

    appended = []

    next_id = max(
        [int(r.get("id", 0)) for r in existing if str(r.get("id", "")).isdigit()],
        default=0
    ) + 1

    for row in new_rows:
        (
            db_id,
            timestamp,
            airline,
            route,
            advance_window_days,
            base_fare,
            taxes_fees,
            total_fare,
            ota_source,
        ) = row

        appended.append({
            "id": next_id,
            "timestamp": timestamp,
            "airline": airline,
            "route": route,
            "advance_window_days": advance_window_days,
            "base_fare": base_fare,
            "taxes_fees": taxes_fees,
            "total_fare": total_fare,
            "ota_source": ota_source,
            "db_id": db_id,
        })

        next_id += 1

    data["raw_fares"].extend(appended)

    if len(data["raw_fares"]) < existing_count:
        raise RuntimeError("Safety check failed: JSON row count decreased.")

    temp_path = JSON_PATH.with_suffix(".json.tmp")

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    temp_path.replace(JSON_PATH)

    print(f"\nAppended: {len(appended)} rows")
    print(f"New JSON count: {len(data['raw_fares'])}")
    print("JSON export completed safely.")


if __name__ == "__main__":
    main()
