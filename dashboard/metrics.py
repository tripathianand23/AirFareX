from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def latest_index(daily_index: pd.DataFrame) -> float:
    if daily_index.empty:
        return float("nan")

    return float(
        daily_index.iloc[-1]["overall_airfare_index"]
    )


def previous_index(daily_index: pd.DataFrame) -> float:
    if len(daily_index) < 2:
        return float("nan")

    return float(
        daily_index.iloc[-2]["overall_airfare_index"]
    )


def index_change_percent(
    current: float,
    previous: float,
) -> float:
    if pd.isna(current) or pd.isna(previous):
        return float("nan")

    if previous == 0:
        return float("nan")

    return ((current - previous) / previous) * 100


def latest_collection_date(
    daily_index: pd.DataFrame,
):
    if daily_index.empty:
        return None

    return daily_index.iloc[-1]["collection_date"]


def observation_count(
    clean_data: pd.DataFrame,
) -> int:
    return int(len(clean_data))


def route_count(
    clean_data: pd.DataFrame,
) -> int:
    if "origin" not in clean_data.columns:
        return 0

    if "destination" not in clean_data.columns:
        return 0

    return int(
        clean_data[
            ["origin", "destination"]
        ].drop_duplicates().shape[0]
    )


def airline_count(
    clean_data: pd.DataFrame,
) -> int:
    if "airline" not in clean_data.columns:
        return 0

    return int(
        clean_data["airline"].nunique()
    )


def source_count(
    clean_data: pd.DataFrame,
) -> int:
    if "source" not in clean_data.columns:
        return 0

    return int(
        clean_data["source"].nunique()
    )


def calculate_before_after_data_quality(
    raw_data: pd.DataFrame,
    clean_data: pd.DataFrame,
) -> dict:
    """
    Compare data quality before and after the normalization/deduplication
    stage.

    Before = raw observation universe.
    After  = cleaned/deduplicated observation universe.

    This is a dashboard diagnostic only and does not alter the
    statistical index methodology.
    """

    def _fare_missing_pct(df: pd.DataFrame) -> float:
        if df.empty:
            return 0.0

        fare_column = None
        for column in ("total_fare", "total", "fare"):
            if column in df.columns:
                fare_column = column
                break

        if fare_column is None:
            return 0.0

        values = pd.to_numeric(df[fare_column], errors="coerce")
        return float(values.isna().mean() * 100)

    def _duplicate_pct(df: pd.DataFrame) -> float:
        if len(df) == 0:
            return 0.0

        columns = [
            column
            for column in [
                "collection_timestamp",
                "source",
                "origin",
                "destination",
                "travel_date",
                "airline",
                "departure_time",
                "advance_days",
                "base_fare",
                "taxes",
                "fees",
                "total_fare",
                "currency",
            ]
            if column in df.columns
        ]

        if not columns:
            return 0.0

        duplicate_count = int(
            df.duplicated(subset=columns, keep=False).sum()
        )

        return float(duplicate_count / len(df) * 100)

    before_count = int(len(raw_data))
    after_count = int(len(clean_data))

    before_missing = _fare_missing_pct(raw_data)
    after_missing = _fare_missing_pct(clean_data)

    before_duplicate = _duplicate_pct(raw_data)
    after_duplicate = _duplicate_pct(clean_data)

    retained_pct = (
        float(after_count / before_count * 100)
        if before_count
        else 0.0
    )

    return {
        "before_count": before_count,
        "after_count": after_count,
        "before_missing_fare_pct": before_missing,
        "after_missing_fare_pct": after_missing,
        "before_duplicate_pct": before_duplicate,
        "after_duplicate_pct": after_duplicate,
        "retained_pct": retained_pct,
        "records_removed": max(before_count - after_count, 0),
    }


PIPELINE_REPORT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "reports"
    / "real"
    / "real_pipeline_report.json"
)


def load_pipeline_stage_report(
    report_path=None,
):
    """
    Load the authoritative AirFareX pipeline-stage report.

    Values are read from:
        data/reports/real/real_pipeline_report.json

    Returns None if the report is missing or unreadable so the
    dashboard can fall back gracefully.

    NOTE: Raw == Normalized because the normalization stage
    preserves every raw observation (see run_real_pipeline.py).
    Validation flags issues without deleting rows.
    """
    path = (
        Path(report_path)
        if report_path is not None
        else PIPELINE_REPORT_PATH
    )

    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as fh:
            report = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None

    dedup = report.get("deduplication") or {}
    cleaning = report.get("cleaning") or {}

    normalized = report.get("normalized_rows")
    deduplicated = dedup.get("deduplicated_rows")
    final_clean = report.get("final_clean_rows")
    dedup_removed = dedup.get("duplicate_rows")
    cleaning_removed = cleaning.get("removed_rows")

    return {
        "raw": normalized,
        "normalized": normalized,
        "deduplicated": deduplicated,
        "final_clean": final_clean,
        "dedup_removed": dedup_removed,
        "cleaning_removed": cleaning_removed,
        "report_path": str(path),
    }
