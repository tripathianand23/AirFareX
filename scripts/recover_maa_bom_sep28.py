import json
from pathlib import Path
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]

API_URL = "https://mospi-apix-api.onrender.com/api/fares/raw"
RAW_PATH = PROJECT_ROOT / "data/raw/airfare_index.json"

TARGET_DATE = "2026-09-28"
TARGET_ROUTE = "MAA-BOM"
TARGET_WINDOWS = {7, 15, 30, 45}

BATCH_SIZE = 50000


def record_key(record):
    """
    Same observation identity used by fetch_friend_api.py.
    """
    return (
        str(record.get("timestamp", "")),
        str(record.get("airline", "")),
        str(record.get("route", "")),
        str(record.get("advance_window_days", "")),
        str(record.get("base_fare", "")),
        str(record.get("taxes_fees", "")),
        str(record.get("total_fare", "")),
        str(record.get("ota_source", "")),
        str(record.get("departure_time", "")),
        str(record.get("id", "")),
        str(record.get("flight_number", "")),
        str(record.get("arrival_time", "")),
        str(record.get("travel_date", "")),
    )


def load_existing_records():
    with open(RAW_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, dict):
        raise ValueError("Expected raw JSON root to be a dictionary.")

    records = payload.get("raw_fares")

    if not isinstance(records, list):
        raise ValueError("Expected raw_fares to be a list.")

    return records


def fetch_date():
    print(f"Fetching upstream API for {TARGET_DATE}...")

    response = requests.get(
        API_URL,
        params={
            "page": 1,
            "size": BATCH_SIZE,
            "date": TARGET_DATE,
        },
        timeout=180,
    )

    response.raise_for_status()

    payload = response.json()

    if payload.get("status") != "ok":
        raise RuntimeError(f"API returned error: {payload}")

    records = payload.get("data", [])

    print(f"Upstream records received: {len(records):,}")

    return records


def save_records(records):
    output = {
        "raw_fares": records
    }

    temp_path = RAW_PATH.with_suffix(".tmp")

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    temp_path.replace(RAW_PATH)


def main():
    existing = load_existing_records()

    print(f"Existing local records: {len(existing):,}")

    upstream = fetch_date()

    # Filter ONLY the four missing strata.
    candidates = [
        r
        for r in upstream
        if str(r.get("route", "")).upper() == TARGET_ROUTE
        and r.get("advance_window_days") in TARGET_WINDOWS
    ]

    print(
        f"Matching upstream {TARGET_ROUTE} "
        f"T+7/T+15/T+30/T+45 records: {len(candidates):,}"
    )

    print("\nUpstream candidate distribution:")

    for window in sorted(TARGET_WINDOWS):
        count = sum(
            r.get("advance_window_days") == window
            for r in candidates
        )
        print(f"  T+{window}: {count}")

    existing_keys = {
        record_key(r)
        for r in existing
    }

    new_records = []

    for record in candidates:
        key = record_key(record)

        if key in existing_keys:
            continue

        existing_keys.add(key)
        new_records.append(record)

    print("\nNew records to append:")

    for window in sorted(TARGET_WINDOWS):
        count = sum(
            r.get("advance_window_days") == window
            for r in new_records
        )
        print(f"  T+{window}: {count}")

    print(f"\nTotal new records: {len(new_records):,}")

    if not new_records:
        print("\nNothing to add. Raw JSON was not changed.")
        return

    updated = existing + new_records

    save_records(updated)

    print("\n========================================")
    print("RECOVERY COMPLETE")
    print("========================================")
    print(f"Previous total: {len(existing):,}")
    print(f"Added:          {len(new_records):,}")
    print(f"New total:      {len(updated):,}")
    print(f"Saved to:       {RAW_PATH}")
    print("========================================")


if __name__ == "__main__":
    main()
