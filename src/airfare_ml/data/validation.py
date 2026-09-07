from unittest import result

import pandas as pd


EXPECTED_ADVANCE_WINDOWS = {1, 7, 15, 30, 45}


def validate_fares(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate airfare observations.

    This function does not delete rows.
    It adds validation flags to the dataset.
    """

    result = df.copy()

    # --------------------------------------------------
    # Ensure datetime columns are correctly parsed
    # --------------------------------------------------

    result["collection_timestamp"] = pd.to_datetime(
        result["collection_timestamp"],
        errors="coerce",
    )

    result["travel_date"] = pd.to_datetime(
        result["travel_date"],
        errors="coerce",
    )

    # --------------------------------------------------
    # 1. Invalid fares
    # --------------------------------------------------

    result["invalid_fare"] = (
        result["total_fare"].isna()
        | (result["total_fare"] <= 0)
        | (
            result["base_fare"].notna()
            & (result["base_fare"] <= 0)
        )
        | (
            result["taxes"].notna()
            & (result["taxes"] < 0)
        )
        | (
            result["fees"].notna()
            & (result["fees"] < 0)
        )
    )

    # --------------------------------------------------
    # 2. Missing important values
    # --------------------------------------------------

    required_for_analysis = [
        "origin",
        "destination",
        "travel_date",
        "airline",
        "advance_days",
        "total_fare",
    ]

    result["missing_required_value"] = (
        result[required_for_analysis]
        .isna()
        .any(axis=1)
    )

    # --------------------------------------------------
    # 3. Invalid routes
    # --------------------------------------------------

    result["invalid_route"] = (
        result["origin"].isna()
        | result["destination"].isna()
        | (result["origin"] == result["destination"])
    )

    # --------------------------------------------------
    # 4. Invalid advance window
    # --------------------------------------------------

    result["invalid_advance_window"] = ~result[
        "advance_days"
    ].isin(EXPECTED_ADVANCE_WINDOWS)

    # --------------------------------------------------
    # 5. Invalid date relationship
    # --------------------------------------------------

    expected_travel_date = (
    result["collection_timestamp"].dt.normalize()
    + pd.to_timedelta(
        result["advance_days"],
        unit="D",
    )
)

    result["invalid_date_relationship"] = (
    result["collection_timestamp"].isna()
    | result["travel_date"].isna()
    | (
        result["travel_date"].dt.normalize()
        != expected_travel_date
    )
)

    # --------------------------------------------------
    # 6. Duplicate observations
    # --------------------------------------------------

    duplicate_columns = [
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
    ]

    result["duplicate_observation"] = result.duplicated(
        subset=duplicate_columns,
        keep=False,
    )

    # --------------------------------------------------
    # 7. Overall validation status
    # --------------------------------------------------

    structural_validation_columns = [
        "invalid_fare",
        "missing_required_value",
        "invalid_route",
        "invalid_advance_window",
        "invalid_date_relationship",
    ]

    result["is_valid"] = ~result[
        structural_validation_columns
    ].any(axis=1)

    return result


def validation_summary(df: pd.DataFrame) -> dict:
    """Generate summary statistics for validation flags."""

    validation_columns = [
        "invalid_fare",
        "missing_required_value",
        "invalid_route",
        "invalid_advance_window",
        "invalid_date_relationship",
        "duplicate_observation",
        "is_valid",
    ]

    return {
        column: int(df[column].sum())
        for column in validation_columns
    }


def print_validation_summary(summary: dict) -> None:
    """Print validation results."""

    print("\n" + "=" * 60)
    print("AIRFARE DATA VALIDATION")
    print("=" * 60)

    for column, count in summary.items():
        label = column.replace("_", " ").title()

        print(f"{label}: {count:,}")

    print("=" * 60)