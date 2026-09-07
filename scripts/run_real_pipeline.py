from __future__ import annotations

from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.airfare_ml.data.adapters.real_json_adapter import (
    RealAirfareJsonAdapter,
)
from src.airfare_ml.data.deduplication import (
    deduplicate_airfare_observations,
)
from src.airfare_ml.data.validation import (
    validate_fares,
    validation_summary,
)
from src.airfare_ml.data.cleaning import (
    clean_airfare_data,
    cleaning_summary,
)


RAW_PATH = Path("data/raw/airfare_index.json")

REAL_DIR = Path("data/processed/real")

NORMALIZED_DIR = REAL_DIR / "normalized"
VALIDATED_DIR = REAL_DIR / "validated"
DEDUPLICATED_DIR = REAL_DIR / "deduplicated"

REPORT_DIR = Path("data/reports/real")


def main() -> None:
    for directory in [
        NORMALIZED_DIR,
        VALIDATED_DIR,
        DEDUPLICATED_DIR,
        REPORT_DIR,
    ]:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    print("=" * 80)
    print("REAL AIRFARE DATA PIPELINE")
    print("=" * 80)

    # ---------------------------------------------------------
    # 1. RAW → NORMALIZED
    # ---------------------------------------------------------

    print("\n[1/5] Loading and normalizing raw data...")

    adapter = RealAirfareJsonAdapter()

    normalized = adapter.parse_file(
        RAW_PATH
    )

    normalized_path = (
        NORMALIZED_DIR
        / "normalized_airfare_observations.csv"
    )

    normalized.to_csv(
        normalized_path,
        index=False,
    )

    print(
        f"Normalized observations: "
        f"{len(normalized):,}"
    )

    # ---------------------------------------------------------
    # 2. VALIDATION
    # ---------------------------------------------------------

    print("\n[2/5] Validating observations...")

    validated = validate_fares(
        normalized
    )

    validated_path = (
        VALIDATED_DIR
        / "validated_airfare_observations.csv"
    )

    validated.to_csv(
        validated_path,
        index=False,
    )

    validation_stats = validation_summary(
        validated
    )

    print("\nValidation summary:")

    for key, value in validation_stats.items():
        print(
            f"  {key}: {value:,}"
        )

    # ---------------------------------------------------------
    # 3. DEDUPLICATION
    # ---------------------------------------------------------

    print("\n[3/5] Deduplicating observations...")

    deduplicated, dedup_stats = (
        deduplicate_airfare_observations(
            normalized
        )
    )

    deduplicated_path = (
        DEDUPLICATED_DIR
        / "deduplicated_airfare_observations.csv"
    )

    deduplicated.to_csv(
        deduplicated_path,
        index=False,
    )

    print("\nDeduplication summary:")

    for key, value in dedup_stats.items():
        print(
            f"  {key}: {value:,}"
            if isinstance(value, int)
            else f"  {key}: {value}"
        )

    # ---------------------------------------------------------
    # 4. CLEANING
    # ---------------------------------------------------------

    print("\n[4/5] Cleaning deduplicated observations...")

    cleaned = clean_airfare_data(
        deduplicated
    )

    cleaning_stats = cleaning_summary(
        deduplicated,
        cleaned,
    )

    cleaned_path = (
        REAL_DIR
        / "clean_airfare_observations.csv"
    )

    cleaned.to_csv(
        cleaned_path,
        index=False,
    )

    print("\nCleaning summary:")

    for key, value in cleaning_stats.items():
        print(
            f"  {key}: {value:,}"
            if isinstance(value, int)
            else f"  {key}: {value}"
        )

    # ---------------------------------------------------------
    # 5. FINAL REPORT
    # ---------------------------------------------------------

    print("\n[5/5] Writing pipeline report...")

    report = {
        "raw_input": str(RAW_PATH),
        "normalized_rows": len(normalized),
        "validation": validation_stats,
        "deduplication": dedup_stats,
        "cleaning": cleaning_stats,
        "final_clean_rows": len(cleaned),
        "output_files": {
            "normalized": str(normalized_path),
            "validated": str(validated_path),
            "deduplicated": str(deduplicated_path),
            "cleaned": str(cleaned_path),
        },
    }

    report_path = (
        REPORT_DIR
        / "real_pipeline_report.json"
    )

    with report_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
            default=str,
        )

    print("\n" + "=" * 80)
    print("REAL DATA PIPELINE COMPLETE")
    print("=" * 80)

    print(
        f"\nFinal clean observations: "
        f"{len(cleaned):,}"
    )

    print(
        f"Report: {report_path}"
    )


if __name__ == "__main__":
    main()
