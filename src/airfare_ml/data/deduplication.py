from __future__ import annotations

import pandas as pd


# Fields that define the same observed airfare quote.
#
# flight_number / fare_class are included when available.
# Since the current real scraper does not provide them, they are
# handled gracefully by the implementation below.
BASE_DEDUPLICATION_COLUMNS = [
    "collection_timestamp",
    "source",
    "origin",
    "destination",
    "travel_date",
    "airline",
    "advance_days",
    "base_fare",
    "taxes",
    "fees",
    "total_fare",
    "currency",
]


def build_deduplication_key(
    df: pd.DataFrame,
) -> pd.Series:
    """
    Build a deterministic business key for airfare observations.

    This is intentionally different from exact row duplication.

    Two records can contain different technical metadata while
    representing the same observed airfare quote.
    """

    required = [
        "collection_timestamp",
        "source",
        "origin",
        "destination",
        "travel_date",
        "airline",
        "advance_days",
        "total_fare",
    ]

    missing = [column for column in required if column not in df.columns]

    if missing:
        raise ValueError(
            f"Missing columns required for deduplication: {missing}"
        )

    columns = [
        column
        for column in BASE_DEDUPLICATION_COLUMNS
        if column in df.columns
    ]

    normalized = df[columns].copy()

    # Normalize timestamps.
    for column in ["collection_timestamp", "travel_date"]:
        if column in normalized.columns:
            normalized[column] = pd.to_datetime(
                normalized[column],
                errors="coerce",
            ).astype("string")

    # Normalize strings.
    for column in [
        "source",
        "origin",
        "destination",
        "airline",
        "currency",
    ]:
        if column in normalized.columns:
            normalized[column] = (
                normalized[column]
                .astype("string")
                .str.strip()
                .str.upper()
            )

    # Normalize numeric fields.
    for column in [
        "advance_days",
        "base_fare",
        "taxes",
        "fees",
        "total_fare",
    ]:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(
                normalized[column],
                errors="coerce",
            )

    return normalized.astype("string").fillna("<NA>").agg(
        "|".join,
        axis=1,
    )


def deduplicate_airfare_observations(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """
    Deduplicate airfare observations using a business-level quote key.

    The original DataFrame is not modified.

    Returns
    -------
    deduplicated_df:
        One representative record per unique airfare observation.

    summary:
        Statistics describing the deduplication operation.
    """

    if df.empty:
        return df.copy(), {
            "original_rows": 0,
            "duplicate_rows": 0,
            "deduplicated_rows": 0,
            "retention_rate_percent": 0.0,
            "duplicate_groups": 0,
        }

    result = df.copy()

    result["_deduplication_key"] = build_deduplication_key(result)

    duplicate_mask = result["_deduplication_key"].duplicated(
        keep="first"
    )

    duplicate_rows = int(duplicate_mask.sum())

    duplicate_groups = int(
        result.loc[
            result["_deduplication_key"].duplicated(keep=False),
            "_deduplication_key",
        ].nunique()
    )

    result = result.loc[~duplicate_mask].copy()

    result = result.drop(
        columns=["_deduplication_key"]
    )

    result = result.reset_index(drop=True)

    original_rows = len(df)
    deduplicated_rows = len(result)

    retention_rate = (
        deduplicated_rows / original_rows * 100
        if original_rows > 0
        else 0.0
    )

    summary = {
        "original_rows": original_rows,
        "duplicate_rows": duplicate_rows,
        "deduplicated_rows": deduplicated_rows,
        "retention_rate_percent": round(
            retention_rate,
            2,
        ),
        "duplicate_groups": duplicate_groups,
    }

    return result, summary


def print_deduplication_summary(summary: dict) -> None:
    """Print a human-readable deduplication report."""

    print("\n" + "=" * 60)
    print("AIRFARE QUOTE DEDUPLICATION")
    print("=" * 60)

    print(
        f"Original Rows: "
        f"{summary['original_rows']:,}"
    )

    print(
        f"Duplicate Rows Removed: "
        f"{summary['duplicate_rows']:,}"
    )

    print(
        f"Duplicate Groups: "
        f"{summary['duplicate_groups']:,}"
    )

    print(
        f"Deduplicated Rows: "
        f"{summary['deduplicated_rows']:,}"
    )

    print(
        f"Retention Rate: "
        f"{summary['retention_rate_percent']:.2f}%"
    )

    print("=" * 60)
