import pandas as pd


REQUIRED_COLUMNS = [
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


def load_dataset(path: str) -> pd.DataFrame:
    """Load airfare observations from CSV."""
    df = pd.read_csv(path)

    # Convert date columns
    df["collection_timestamp"] = pd.to_datetime(
        df["collection_timestamp"],
        errors="coerce",
    )

    df["travel_date"] = pd.to_datetime(
        df["travel_date"],
        errors="coerce",
    )

    return df


def check_schema(df: pd.DataFrame) -> dict:
    """Check whether all required columns exist."""

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    extra_columns = [
        column
        for column in df.columns
        if column not in REQUIRED_COLUMNS
    ]

    return {
        "valid": len(missing_columns) == 0,
        "missing_columns": missing_columns,
        "extra_columns": extra_columns,
    }


def profile_dataset(df: pd.DataFrame) -> dict:
    """Generate a high-level profile of the airfare dataset."""

    profile = {
        "rows": len(df),
        "columns": len(df.columns),
        "missing_values": df.isna().sum().to_dict(),
        "duplicate_rows": int(df.duplicated().sum()),
        "unique_routes": int(
            df[["origin", "destination"]]
            .drop_duplicates()
            .shape[0]
        ),
        "unique_airlines": int(df["airline"].nunique()),
        "unique_sources": int(df["source"].nunique()),
        "unique_fare_classes": int(df["fare_class"].nunique()),
        "advance_windows": sorted(
            df["advance_days"]
            .dropna()
            .unique()
            .tolist()
        ),
        "availability_distribution": (
            df["availability"]
            .value_counts(dropna=False)
            .to_dict()
        ),
        "fare_statistics": (
            df["total_fare"]
            .describe()
            .to_dict()
        ),
        "collection_date_range": {
            "min": df["collection_timestamp"].min(),
            "max": df["collection_timestamp"].max(),
        },
        "travel_date_range": {
            "min": df["travel_date"].min(),
            "max": df["travel_date"].max(),
        },
    }

    return profile


def print_profile(profile: dict) -> None:
    """Print the dataset profile in a readable format."""

    print("\n" + "=" * 60)
    print("AIRFARE DATASET PROFILE")
    print("=" * 60)

    print(f"\nRows: {profile['rows']:,}")
    print(f"Columns: {profile['columns']}")
    print(f"Unique routes: {profile['unique_routes']}")
    print(f"Unique airlines: {profile['unique_airlines']}")
    print(f"Unique sources: {profile['unique_sources']}")
    print(f"Unique fare classes: {profile['unique_fare_classes']}")

    print("\nAdvance Windows:")
    print(profile["advance_windows"])

    print("\nAvailability:")
    for key, value in profile["availability_distribution"].items():
        print(f"  {key}: {value:,}")

    print("\nDuplicate Rows:")
    print(profile["duplicate_rows"])

    print("\nMissing Values:")
    for column, count in profile["missing_values"].items():
        if count > 0:
            print(f"  {column}: {count:,}")

    print("\nFare Statistics:")
    for key, value in profile["fare_statistics"].items():
        print(f"  {key}: {value:,.2f}")

    print("\nCollection Date Range:")
    print(
        f"  {profile['collection_date_range']['min']} "
        f"→ {profile['collection_date_range']['max']}"
    )

    print("\nTravel Date Range:")
    print(
        f"  {profile['travel_date_range']['min']} "
        f"→ {profile['travel_date_range']['max']}"
    )

    print("\n" + "=" * 60)