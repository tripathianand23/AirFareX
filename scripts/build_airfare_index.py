from pathlib import Path

import pandas as pd

from src.airfare_ml.index.aggregation import (
    aggregate_daily_route_fares,
)

from src.airfare_ml.index.calculation import (
    calculate_route_indices,
    calculate_weighted_index,
)

from src.airfare_ml.index.series import (
    build_index_series,
)

from src.airfare_ml.index.validation import (
    validate_weights,
    validate_route_indices,
    validate_weighted_index,
    print_validation_report,
)


INPUT_PATH = Path(
    "data/processed/clean_airfare_observations.csv"
)

OUTPUT_DIR = Path(
    "data/processed/index"
)


def main() -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Loading cleaned airfare data...")

    df = pd.read_csv(INPUT_PATH)

    print(f"Input rows: {len(df):,}")

    # -----------------------------------------
    # 1. Aggregate observations
    # -----------------------------------------

    print("Aggregating daily route fares...")

    daily_fares = aggregate_daily_route_fares(df)

    daily_fares.to_csv(
        OUTPUT_DIR / "daily_route_fares.csv",
        index=False,
    )

    print(
        f"Daily route records: "
        f"{len(daily_fares):,}"
    )

    # -----------------------------------------
    # 2. Calculate route indices
    # -----------------------------------------

    print("Calculating route indices...")

    route_indices = calculate_route_indices(
        daily_fares
    )

    route_indices.to_csv(
        OUTPUT_DIR / "route_indices.csv",
        index=False,
    )

    # -----------------------------------------
    # 3. Calculate weighted index
    # -----------------------------------------

    print("Calculating weighted index...")

    weighted_indices = calculate_weighted_index(
        route_indices
    )

   
    # 3.5 Validate index
    # -----------------------------------------

    print("Validating index...")

    weight_checks = validate_weights()

    route_checks = validate_route_indices(
        route_indices
    )

    weighted_checks = validate_weighted_index(
        weighted_indices
    )

    print_validation_report(
        weight_checks,
        route_checks,
        weighted_checks,
    )

    weighted_indices.to_csv(
        OUTPUT_DIR / "advance_window_indices.csv",
        index=False,
    )

    # -----------------------------------------
    # 4. Build overall series
    # -----------------------------------------

    print("Building overall index series...")

    daily, weekly, monthly = build_index_series(
        weighted_indices
    )

    daily.to_csv(
        OUTPUT_DIR / "daily_airfare_index.csv",
        index=False,
    )

    weekly.to_csv(
        OUTPUT_DIR / "weekly_airfare_index.csv",
        index=False,
    )

    monthly.to_csv(
        OUTPUT_DIR / "monthly_airfare_index.csv",
        index=False,
    )

    print("\nIndex construction complete.")

    print("\nLatest daily index:")

    print(
        daily.tail(5).to_string(
            index=False
        )
    )

    print("\nLatest monthly index:")

    print(
        monthly.tail(5).to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()