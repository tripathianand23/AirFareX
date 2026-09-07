import pandas as pd

from .methodology import (
    DEFAULT_INDEX_METHODOLOGY,
    IndexMethodology,
)


def build_overall_index(
    advance_window_indices: pd.DataFrame,
    methodology: IndexMethodology | None = None,
) -> pd.DataFrame:
    """
    Combine advance-window indices into one overall
    Airfare Price Index.

    The current methodology uses equal weighting across
    advance windows.
    """
    if methodology is None:
        methodology = DEFAULT_INDEX_METHODOLOGY

    required = {
        "collection_date",
        "advance_days",
        "airfare_index",
    }

    missing = required - set(
        advance_window_indices.columns
    )

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    data = advance_window_indices.copy()

    data = data[
        data["advance_days"].isin(
            methodology.advance_windows
        )
    ].copy()

    if (
        methodology.lead_time_weighting
        == "equal"
    ):
        result = (
            data.groupby("collection_date")[
                "airfare_index"
            ]
            .mean()
            .rename("overall_airfare_index")
            .reset_index()
        )

    else:
        raise ValueError(
            "Unsupported lead-time weighting: "
            f"{methodology.lead_time_weighting}"
        )

    return result.sort_values(
        "collection_date"
    ).reset_index(drop=True)


def build_index_series(
    advance_window_indices: pd.DataFrame,
    methodology: IndexMethodology | None = None,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """
    Produce daily, weekly and monthly index series.
    """
    if methodology is None:
        methodology = DEFAULT_INDEX_METHODOLOGY

    daily = build_overall_index(
        advance_window_indices,
        methodology=methodology,
    )

    daily["week"] = (
        daily["collection_date"]
        .dt.to_period("W")
        .astype(str)
    )

    daily["month"] = (
        daily["collection_date"]
        .dt.to_period("M")
        .astype(str)
    )

    weekly = (
        daily.groupby("week")
        .agg(
            period_index=(
                "overall_airfare_index",
                "mean",
            )
        )
        .reset_index()
    )

    monthly = (
        daily.groupby("month")
        .agg(
            period_index=(
                "overall_airfare_index",
                "mean",
            )
        )
        .reset_index()
    )

    return daily, weekly, monthly
