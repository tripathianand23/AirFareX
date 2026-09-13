import json
import sqlite3
from pathlib import Path
from datetime import datetime


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = PROJECT_ROOT / "SIH26" / "airfare_index.db"
JSON_PATH = PROJECT_ROOT / "data" / "raw" / "airfare_index.json"


def normalize_value(value):
    if value is None:
        return None

    if isinstance(value, float):
        return round(value, 2)

    return value


def observation_key(record):
    """
    Exact observation identity.

    A different fare or different collection timestamp is treated
    as a new observation.
    """

    return (
        record.get("timestamp"),
        record.get("airline"),
        record.get("route"),
        record.get("advance_window_days"),
        record.get("base_fare"),
        record.get("taxes_fees"),
        record.get("total_fare"),
        record.get("ota_source"),
    )


def load_existing_json():
    if not JSON_PATH.exists():
        return []

    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            # Support older AirfareX JSON structure
            if isinstance(data.get("raw_fares"), list):
                return data["raw_fares"]

            return []

        return []

    except json.JSONDecodeError:
        print("⚠️ Existing JSON is invalid. Stopping to protect existing data.")
        raise


def load_database_records():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()

        cursor.execute("""
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
            ORDER BY timestamp ASC, id ASC
        """)

        return [dict(row) for row in cursor.fetchall()]


def normalize_record(row):
    timestamp = row.get("timestamp")

    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp)
            collection_date = dt.date().isoformat()
        except ValueError:
            collection_date = str(timestamp)[:10]
    else:
        collection_date = None

    return {
        "timestamp": timestamp,
        "collection_date": collection_date,
        "airline": row.get("airline"),
        "route": row.get("route"),
        "advance_window_days": row.get("advance_window_days"),
        "base_fare": normalize_value(row.get("base_fare")),
        "taxes_fees": normalize_value(row.get("taxes_fees")),
        "total_fare": normalize_value(row.get("total_fare")),
        "ota_source": row.get("ota_source") or "Unknown",
    }


def main():
    print("=" * 60)
    print("AirfareX DB → RAW JSON Synchronizer")
    print("=" * 60)

    existing = load_existing_json()
    db_records = load_database_records()

    print(f"Existing JSON records : {len(existing):,}")
    print(f"Database records      : {len(db_records):,}")

    # Normalize existing JSON
    normalized_existing = []

    for record in existing:
        if isinstance(record, dict):
            normalized_existing.append(record)

    # Build duplicate index
    existing_keys = set()

    for record in normalized_existing:
        existing_keys.add(observation_key(record))

    new_records = []
    duplicate_count = 0

    for row in db_records:
        record = normalize_record(row)

        key = observation_key(record)

        if key in existing_keys:
            duplicate_count += 1
            continue

        existing_keys.add(key)
        new_records.append(record)

    combined = normalized_existing + new_records

    # Final exact duplicate protection
    final_records = []
    final_keys = set()

    for record in combined:
        key = observation_key(record)

        if key in final_keys:
            continue

        final_keys.add(key)
        final_records.append(record)

    # Sort chronologically
    final_records.sort(
        key=lambda x: (
            x.get("timestamp") or "",
            x.get("airline") or "",
            x.get("route") or "",
        )
    )

    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Write safely
    temp_path = JSON_PATH.with_suffix(".json.tmp")

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(
            final_records,
            f,
            indent=2,
            ensure_ascii=False,
        )

    temp_path.replace(JSON_PATH)

    print()
    print("✅ Synchronization complete")
    print(f"   Previous JSON records : {len(existing):,}")
    print(f"   New records added     : {len(new_records):,}")
    print(f"   Duplicate records     : {duplicate_count:,}")
    print(f"   Final JSON records     : {len(final_records):,}")
    print()
    print(f"📁 {JSON_PATH}")


if __name__ == "__main__":
    main()
