import pandas as pd


CRITICAL_COLUMNS = [
    "collection_timestamp",
    "source",
    "origin",
    "destination",
    "travel_date",
    "airline",
    "advance_days",
    "total_fare",
]

DUPLICATE_COLUMNS = [
    "collection_timestamp",
    "source",
    "origin",
    "destination",
    "travel_date",
    "airline",
    "flight_number",
    "fare_class",
    "advance_days",
    "base_fare",
    "taxes",
    "fees",
    "total_fare",
    "currency",
    "availability",
]


def clean_airfare_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean airfare observations for downstream ML and index calculation.

    The original DataFrame is not modified.

    Cleaning steps:
    1. Remove exact duplicate observations.
    2. Remove rows missing critical fields.
    3. Remove rows with invalid fare values.
    4. Remove rows with invalid routes.
    5. Remove rows with invalid advance windows.
    6. Remove rows with inconsistent collection/travel dates.
    7. Exclude sold-out observations from price modeling.
    """

    clean_df = df.copy()

    # ---------------------------------------------------------
    # 1. Parse timestamps
    # ---------------------------------------------------------
    clean_df["collection_timestamp"] = pd.to_datetime(
        clean_df["collection_timestamp"],
        errors="coerce",
    )

    clean_df["travel_date"] = pd.to_datetime(
        clean_df["travel_date"],
        errors="coerce",
    )

    # ---------------------------------------------------------
    # 2. Remove exact duplicate observations
    # ---------------------------------------------------------
    clean_df = clean_df.drop_duplicates(
        subset=DUPLICATE_COLUMNS,
        keep="first",
    )

    # ---------------------------------------------------------
    # 3. Remove rows missing critical fields
    # ---------------------------------------------------------
    clean_df = clean_df.dropna(
        subset=CRITICAL_COLUMNS
    )

    # ---------------------------------------------------------
    # 4. Remove invalid fare values
    # ---------------------------------------------------------
    clean_df = clean_df[
        clean_df["total_fare"] > 0
    ]

    if "base_fare" in clean_df.columns:
        clean_df = clean_df[
            clean_df["base_fare"].isna()
            | (clean_df["base_fare"] > 0)
        ]

    if "taxes" in clean_df.columns:
        clean_df = clean_df[
            clean_df["taxes"].isna()
            | (clean_df["taxes"] >= 0)
        ]

    if "fees" in clean_df.columns:
        clean_df = clean_df[
            clean_df["fees"].isna()
            | (clean_df["fees"] >= 0)
        ]

    # ---------------------------------------------------------
    # 5. Remove invalid routes
    # ---------------------------------------------------------
    clean_df = clean_df[
        clean_df["origin"] != clean_df["destination"]
    ]

    # ---------------------------------------------------------
    # 6. Keep only official advance windows
    # ---------------------------------------------------------
    valid_advance_windows = {1, 7, 15, 30, 45}

    clean_df = clean_df[
        clean_df["advance_days"].isin(valid_advance_windows)
    ]

    # ---------------------------------------------------------
    # 7. Validate collection date vs travel date
    # ---------------------------------------------------------
    expected_travel_date = (
    clean_df["collection_timestamp"].dt.normalize()
    + pd.to_timedelta(
        clean_df["advance_days"],
        unit="D",
    )
)

    clean_df = clean_df[
    clean_df["travel_date"].dt.normalize()
    == expected_travel_date
]

    # ---------------------------------------------------------
    # 8. Exclude sold-out observations
    # ---------------------------------------------------------
    clean_df = clean_df[
        clean_df["availability"].str.lower() == "available"
    ]

    # ---------------------------------------------------------
    # 9. Sort chronologically
    # ---------------------------------------------------------
    clean_df = clean_df.sort_values(
        by=[
            "collection_timestamp",
            "origin",
            "destination",
            "advance_days",
        ]
    ).reset_index(drop=True)

    return clean_df


def cleaning_summary(
    original_df: pd.DataFrame,
    clean_df: pd.DataFrame,
) -> dict:
    """
    Generate a high-level summary of the cleaning operation.
    """

    original_rows = len(original_df)
    clean_rows = len(clean_df)

    removed_rows = original_rows - clean_rows

    retention_rate = (
        clean_rows / original_rows * 100
        if original_rows > 0
        else 0.0
    )

    return {
        "original_rows": original_rows,
        "clean_rows": clean_rows,
        "removed_rows": removed_rows,
        "retention_rate_percent": round(retention_rate, 2),
    }


def print_cleaning_summary(summary: dict) -> None:
    """
    Print cleaning statistics.
    """

    print("=" * 60)
    print("AIRFARE DATA CLEANING")
    print("=" * 60)

    print(f"Original Rows: {summary['original_rows']:,}")
    print(f"Clean Rows: {summary['clean_rows']:,}")
    print(f"Removed Rows: {summary['removed_rows']:,}")
    print(
        f"Retention Rate: "
        f"{summary['retention_rate_percent']:.2f}%"
    )

    print("=" * 60)