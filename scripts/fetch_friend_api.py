import json
import sys
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]

API_URL = "https://mospi-apix-api.onrender.com/api/fares/raw"
RAW_PATH = PROJECT_ROOT / "data/raw/airfare_index.json"


def fetch_api_data(hours_back=24):
    print(f"Fetching API data for last {hours_back} hours...")

    response = requests.get(
        API_URL,
        params={"hours_back": hours_back},
        timeout=120,
    )

    response.raise_for_status()

    payload = response.json()

    if payload.get("status") != "ok":
        raise RuntimeError(f"API returned error: {payload}")

    records = payload.get("data", [])

    print(f"API returned {len(records):,} records")

    return records


def load_existing_records():
    if not RAW_PATH.exists():
        return []

    with open(RAW_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, dict):
        return payload.get("raw_fares", [])

    if isinstance(payload, list):
        return payload

    raise ValueError("Existing raw airfare JSON has invalid structure.")


def record_key(record):
    """
    Idempotent observation identity, robust across all API and
    scraper payload schemas seen during this project.

    Missing fields resolve to "" so records written by older
    schema versions deduplicate correctly against newer ones.

    T-slot (departure_time) is preserved when present so
    flight-level multiplicity is NOT collapsed.
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


def merge_records(existing, new_records):
    existing_keys = {record_key(row) for row in existing}

    added = 0

    for record in new_records:
        key = record_key(record)

        if key in existing_keys:
            continue

        existing.append(record)
        existing_keys.add(key)
        added += 1

    return existing, added


def save_raw_data(records):
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "raw_fares": records
    }

    temp_path = RAW_PATH.with_suffix(".tmp")

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    temp_path.replace(RAW_PATH)


def main():
    new_records = fetch_api_data(hours_back=24)

    if not new_records:
        print("API returned zero records. Nothing new to ingest.")
        # Exit code 2 = "nothing to do" (distinct from real errors).
        # The daily shell wrapper treats this as a non-error and
        # skips the pipeline/index rebuild while still pushing any
        # pending local changes.
        sys.exit(2)

    existing_records = load_existing_records()

    print(f"Existing raw records: {len(existing_records):,}")

    merged_records, added = merge_records(
        existing_records,
        new_records,
    )

    save_raw_data(merged_records)

    print(f"New unique records: {added:,}")
    print(f"Total raw records: {len(merged_records):,}")
    print(f"Saved to: {RAW_PATH}")

    print("\nIncremental API fetch completed successfully.")


if __name__ == "__main__":
    main()
