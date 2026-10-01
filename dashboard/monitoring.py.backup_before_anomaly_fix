from __future__ import annotations

import pandas as pd


def calculate_data_quality(
    df: pd.DataFrame,
) -> dict[str, float | int]:
    """
    Calculate high-level data-quality indicators.

    These metrics describe the observed dataset and do not alter
    the underlying statistical index.
    """

    total_rows = len(df)

    if total_rows == 0:
        return {
            "total_observations": 0,
            "missing_total_fare": 0,
            "duplicate_rows": 0,
            "missing_fare_pct": 0.0,
            "duplicate_pct": 0.0,
        }

    missing_total_fare = int(
        df["total_fare"].isna().sum()
    )

    duplicate_rows = int(
        df.duplicated().sum()
    )

    return {
        "total_observations": total_rows,
        "missing_total_fare": missing_total_fare,
        "duplicate_rows": duplicate_rows,
        "missing_fare_pct": (
            missing_total_fare / total_rows * 100
        ),
        "duplicate_pct": (
            duplicate_rows / total_rows * 100
        ),
    }


def calculate_source_coverage(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Summarize observations contributed by each source.
    """

    if df.empty or "source" not in df.columns:
        return pd.DataFrame(
            columns=["source", "observations", "share_pct"]
        )

    coverage = (
        df.groupby("source")
        .size()
        .reset_index(name="observations")
    )

    total = coverage["observations"].sum()

    coverage["share_pct"] = (
        coverage["observations"] / total * 100
    )

    return coverage.sort_values(
        "observations",
        ascending=False,
    )


def calculate_route_coverage(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate observation coverage by route.
    """

    if df.empty:
        return pd.DataFrame(
            columns=[
                "route",
                "observations",
            ]
        )

    route_coverage = (
        df.assign(
            route=df["origin"] + "_" + df["destination"]
        )
        .groupby("route")
        .size()
        .reset_index(name="observations")
    )

    return route_coverage.sort_values(
        "observations",
        ascending=False,
    )


def detect_fare_anomalies(
    df: pd.DataFrame,
    *,
    multiplier: float = 1.5,
) -> pd.DataFrame:
    """
    Detect potentially anomalous fares using an IQR rule.

    This is a monitoring flag only.

    Genuine high fares must NOT automatically be deleted from
    the statistical dataset.
    """

    if df.empty:
        return pd.DataFrame()

    required_columns = {
        "origin",
        "destination",
        "total_fare",
    }

    if not required_columns.issubset(df.columns):
        return pd.DataFrame()

    result = df.copy()

    result["route"] = (
        result["origin"]
        + "_"
        + result["destination"]
    )

    

    # Calculate quartiles explicitly because groupby.agg
    # with quantile requires separate handling.
    q1 = (
        result.groupby("route")["total_fare"]
        .quantile(0.25)
        .rename("q1")
    )

    q3 = (
        result.groupby("route")["total_fare"]
        .quantile(0.75)
        .rename("q3")
    )

    bounds = pd.concat(
        [q1, q3],
        axis=1,
    )

    bounds["iqr"] = (
        bounds["q3"] - bounds["q1"]
    )

    bounds["lower_bound"] = (
        bounds["q1"]
        - multiplier * bounds["iqr"]
    )

    bounds["upper_bound"] = (
        bounds["q3"]
        + multiplier * bounds["iqr"]
    )

    result = result.join(
        bounds[
            [
                "lower_bound",
                "upper_bound",
            ]
        ],
        on="route",
    )

    result["anomaly_flag"] = (
        (result["total_fare"] < result["lower_bound"])
        | (result["total_fare"] > result["upper_bound"])
    )

    return result