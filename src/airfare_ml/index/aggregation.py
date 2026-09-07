import pandas as pd

from .methodology import (
    DEFAULT_INDEX_METHODOLOGY,
    IndexMethodology,
)


REQUIRED_COLUMNS = {
    "collection_timestamp",
    "origin",
    "destination",
    "advance_days",
    "total_fare",
}


def prepare_index_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare cleaned airfare observations for index aggregation.
    """
    missing = REQUIRED_COLUMNS - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    data = df.copy()

    data["collection_timestamp"] = pd.to_datetime(
        data["collection_timestamp"],
        errors="coerce",
    )

    data["route"] = (
        data["origin"].astype(str)
        + "_"
        + data["destination"].astype(str)
    )

    data["collection_date"] = (
        data["collection_timestamp"].dt.normalize()
    )

    data["total_fare"] = pd.to_numeric(
        data["total_fare"],
        errors="coerce",
    )

    data = data.dropna(
        subset=[
            "collection_date",
            "route",
            "advance_days",
            "total_fare",
        ]
    )

    data = data[data["total_fare"] > 0]

    return data


def _representative_fare_aggregation(
    method: str,
) -> str:
    """
    Map the configured representative-fare method
    to the corresponding pandas aggregation.
    """
    if method == "median":
        return "median"

    if method == "trimmed_mean":
        raise NotImplementedError(
            "trimmed_mean is reserved for a future methodology "
            "implementation."
        )

    raise ValueError(
        f"Unsupported representative fare method: {method}"
    )


def aggregate_daily_route_fares(
    df: pd.DataFrame,
    methodology: IndexMethodology | None = None,
) -> pd.DataFrame:
    """
    Calculate the representative daily fare for
    every route and advance window.

    The representative-fare estimator is controlled
    by the index methodology configuration.
    """
    if methodology is None:
        methodology = DEFAULT_INDEX_METHODOLOGY

    data = prepare_index_data(df)

    data = data[
        data["advance_days"].isin(
            methodology.advance_windows
        )
    ].copy()

    aggregation_method = _representative_fare_aggregation(
        methodology.representative_fare_method
    )

    grouped = (
        data.groupby(
            [
                "collection_date",
                "route",
                "advance_days",
            ],
            as_index=False,
        )
        .agg(
            representative_fare=(
                "total_fare",
                aggregation_method,
            ),
            observation_count=(
                "total_fare",
                "count",
            ),
        )
    )

    return grouped.sort_values(
        [
            "collection_date",
            "advance_days",
            "route",
        ]
    ).reset_index(drop=True)
