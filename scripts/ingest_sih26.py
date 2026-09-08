import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SIH26_DB = PROJECT_ROOT / "SIH26" / "airfare_index.db"
AIRFARE_JSON = PROJECT_ROOT / "data" / "raw" / "airfare_index.json"


def load_existing_json():
    if not AIRFARE_JSON.exists():
        return []

    with AIRFARE_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        return data.get("raw_fares", [])

    if isinstance(data, list):
        return data

    return []


def load_sih26_records():
    if not SIH26_DB.exists():
        raise FileNotFoundError(
            f"SIH26 database not found: {SIH26_DB}"
        )

    conn = sqlite3.connect(SIH26_DB)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute("""
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
        """).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


def normalize_record(record):
    return {
        "id": record.get("id"),
        "timestamp": record.get("timestamp"),
        "airline": record.get("airline"),
        "route": record.get("route"),
        "advance_window_days": record.get("advance_window_days"),
        "base_fare": record.get("base_fare"),
        "taxes_fees": record.get("taxes_fees"),
        "total_fare": record.get("total_fare"),
        "ota_source": record.get("ota_source"),
    }


def merge_records(existing, new_records):

    merged = {}

    for record in existing:
        record = normalize_record(record)

        if record["id"] is not None:
            key = ("id", str(record["id"]))
        else:
            key = (
                "fallback",
                str((
                    record["timestamp"],
                    record["airline"],
                    record["route"],
                    record["advance_window_days"],
                    record["base_fare"],
                    record["taxes_fees"],
                    record["total_fare"],
                    record["ota_source"],
                ))
            )

        merged[key] = record

    added = 0
    updated = 0

    for record in new_records:
        record = normalize_record(record)

        if record["id"] is not None:
            key = ("id", str(record["id"]))

            if key in merged:
                updated += 1
            else:
                added += 1

            merged[key] = record

        else:
            key = (
                "fallback",
                str((
                    record["timestamp"],
                    record["airline"],
                    record["route"],
                    record["advance_window_days"],
                    record["base_fare"],
                    record["taxes_fees"],
                    record["total_fare"],
                    record["ota_source"],
                ))
            )

            if key not in merged:
                merged[key] = record
                added += 1

    return list(merged.values()), added, updated


def save_json(records):

    AIRFARE_JSON.parent.mkdir(parents=True, exist_ok=True)

    with AIRFARE_JSON.open("w", encoding="utf-8") as f:
        json.dump(
            {"raw_fares": records},
            f,
            indent=2,
            ensure_ascii=False
        )


def main():

    print("=" * 70)
    print("AIRFAREX - SIH26 DATA INGESTION")
    print("=" * 70)

    print("\nSIH26 database:")
    print(SIH26_DB)

    print("\nAirfareX raw JSON:")
    print(AIRFARE_JSON)

    print("\n[1/4] Loading existing AirfareX JSON...")
    existing = load_existing_json()
    print(f"Existing records: {len(existing):,}")

    print("\n[2/4] Loading SIH26 SQLite...")
    sih26_records = load_sih26_records()
    print(f"SIH26 records: {len(sih26_records):,}")

    print("\n[3/4] Merging...")
    merged, added, updated = merge_records(
        existing,
        sih26_records
    )

    print(f"Added: {added:,}")
    print(f"Updated: {updated:,}")
    print(f"Final records: {len(merged):,}")

    print("\n[4/4] Writing JSON...")
    save_json(merged)

    print("\nSUCCESS!")
    print(f"Written to:\n{AIRFARE_JSON}")

    print("=" * 70)


if __name__ == "__main__":
    main()
