from pathlib import Path

import numpy as np
import pandas as pd

from src.airfare_ml.index.aggregation import aggregate_daily_route_fares
from src.airfare_ml.index.calculation import (
    calculate_route_indices,
    calculate_weighted_index,
)
from src.airfare_ml.index.methodology import IndexMethodology
from src.airfare_ml.index.series import build_overall_index


INPUT_PATH = Path(
    "data/processed/clean_airfare_observations.csv"
)

OUTPUT_DIR = Path(
    "data/processed/index/base_period_comparison"
)

REFERENCE_MONTH = "2026-07"


def load_clean_data() -> pd.DataFrame:
    df = pd.read_csv(INPUT_PATH)

    df["collection_timestamp"] = pd.to_datetime(
        df["collection_timestamp"]
    )

    df["collection_date"] = (
        df["collection_timestamp"]
        .dt.normalize()
    )

    return df


def calculate_methodology_index(
    df: pd.DataFrame,
    methodology: IndexMethodology,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:

    daily_route_fares = aggregate_daily_route_fares(
        df,
        methodology=methodology,
    )

    route_indices = calculate_route_indices(
        daily_route_fares,
        methodology=methodology,
    )

    weighted_indices = calculate_weighted_index(
        route_indices,
        methodology=methodology,
    )

    overall_index = build_overall_index(
        weighted_indices,
        methodology=methodology,
    )

    return (
        daily_route_fares,
        route_indices,
        overall_index,
    )


def compare_daily_indices(
    first_index: pd.DataFrame,
    calendar_index: pd.DataFrame,
) -> pd.DataFrame:

    first = first_index.rename(
        columns={
            "overall_airfare_index": "first_observation_index"
        }
    )

    calendar = calendar_index.rename(
        columns={
            "overall_airfare_index": "calendar_month_index"
        }
    )

    merged = first.merge(
        calendar,
        on="collection_date",
        how="inner",
    )

    merged["absolute_difference"] = (
        merged["calendar_month_index"]
        - merged["first_observation_index"]
    )

    merged["relative_difference_pct"] = (
        merged["absolute_difference"]
        / merged["first_observation_index"]
        * 100.0
    )

    return merged
    return merged


def calculate_summary(
    comparison: pd.DataFrame,
) -> pd.DataFrame:

    first = comparison[
        "first_observation_index"
    ]

    calendar = comparison[
        "calendar_month_index"
    ]

    difference = comparison[
        "absolute_difference"
    ]

    summary = pd.DataFrame(
        {
            "metric": [
                "observations",
                "correlation",
                "mae",
                "rmse",
                "mean_absolute_difference",
                "mean_relative_difference_pct",
                "max_absolute_difference",
            ],
            "value": [
                len(comparison),
                first.corr(calendar),
                np.mean(np.abs(difference)),
                np.sqrt(np.mean(difference**2)),
                difference.mean(),
                comparison[
                    "relative_difference_pct"
                ].mean(),
                np.max(np.abs(difference)),
            ],
        }
    )

    return summary


def main() -> None:

    print("=" * 70)
    print("AIRFARE INDEX BASE-PERIOD COMPARISON")
    print("=" * 70)

    print(f"\nInput: {INPUT_PATH}")
    print(f"Reference month: {REFERENCE_MONTH}")

    df = load_clean_data()

    print(
        f"\nLoaded {len(df):,} cleaned observations."
    )

    first_methodology = IndexMethodology(
        base_period_method="first_observation",
    )

    calendar_methodology = IndexMethodology(
        base_period_method="calendar_month",
        base_period=REFERENCE_MONTH,
    )

    print("\nCalculating first-observation methodology...")

    (
        first_daily_fares,
        first_route_indices,
        first_overall,
    ) = calculate_methodology_index(
        df,
        first_methodology,
    )

    print("Calculating calendar-month methodology...")

    (
        calendar_daily_fares,
        calendar_route_indices,
        calendar_overall,
    ) = calculate_methodology_index(
        df,
        calendar_methodology,
    )

    comparison = compare_daily_indices(
        first_overall,
        calendar_overall,
    )

    summary = calculate_summary(
        comparison
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    comparison_path = (
        OUTPUT_DIR
        / "daily_index_comparison.csv"
    )

    summary_path = (
        OUTPUT_DIR
        / "comparison_summary.csv"
    )

    route_comparison = (
        first_route_indices[
            [
                "collection_date",
                "route",
                "advance_days",
                "representative_fare",
                "base_fare",
                "route_index",
            ]
        ]
        .rename(
            columns={
                "base_fare": "first_base_fare",
                "route_index": "first_route_index",
            }
        )
        .merge(
            calendar_route_indices[
                [
                    "collection_date",
                    "route",
                    "advance_days",
                    "base_fare",
                    "route_index",
                ]
            ].rename(
                columns={
                    "base_fare": "calendar_base_fare",
                    "route_index": "calendar_route_index",
                }
            ),
            on=[
                "collection_date",
                "route",
                "advance_days",
            ],
            how="inner",
        )
    )

    route_comparison[
        "index_difference"
    ] = (
        route_comparison["calendar_route_index"]
        - route_comparison["first_route_index"]
    )

    route_path = (
        OUTPUT_DIR
        / "route_index_comparison.csv"
    )

    comparison.to_csv(
        comparison_path,
        index=False,
    )

    summary.to_csv(
        summary_path,
        index=False,
    )

    route_comparison.to_csv(
        route_path,
        index=False,
    )

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(summary.to_string(index=False))

    print("\nDaily index comparison:")
    print(
        comparison[
            [
                "collection_date",
                "first_observation_index",
                "calendar_month_index",
                "absolute_difference",
            ]
        ].head(10).to_string(index=False)
    )

    print("\nOutput files:")
    print(comparison_path)
    print(summary_path)
    print(route_path)

    print("\nComparison complete.")


if __name__ == "__main__":
    main()
