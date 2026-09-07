from __future__ import annotations

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