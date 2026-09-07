from __future__ import annotations

import pandas as pd
import plotly.express as px


def create_overall_index_chart(
    daily_index: pd.DataFrame,
):
    return px.line(
        daily_index,
        x="collection_date",
        y="overall_airfare_index",
        markers=True,
        title="Overall Airfare Price Index",
        labels={
            "collection_date": "Collection Date",
            "overall_airfare_index": "Index",
        },
    )


def create_route_index_chart(
    route_indices: pd.DataFrame,
):
    return px.line(
        route_indices,
        x="collection_date",
        y="route_index",
        color="route",
        title="Route-level Airfare Indices",
        labels={
            "collection_date": "Collection Date",
            "route_index": "Route Index",
            "route": "Route",
        },
    )


def create_lead_time_chart(
    advance_indices: pd.DataFrame,
):
    return px.line(
        advance_indices,
        x="collection_date",
        y="airfare_index",
        color="advance_days",
        markers=False,
        title="Airfare Index by Advance Purchase Window",
        labels={
            "collection_date": "Collection Date",
            "airfare_index": "Index",
            "advance_days": "Advance Days",
        },
    )


def create_airline_fare_chart(
    clean_data: pd.DataFrame,
):
    airline_fares = (
        clean_data
        .groupby("airline", as_index=False)["total_fare"]
        .median()
        .sort_values("total_fare", ascending=False)
    )

    return px.bar(
        airline_fares,
        x="airline",
        y="total_fare",
        title="Median Fare by Airline",
        labels={
            "airline": "Airline",
            "total_fare": "Median Fare (INR)",
        },
    )


def create_source_chart(
    clean_data: pd.DataFrame,
):
    source_counts = (
        clean_data["source"]
        .value_counts()
        .rename_axis("source")
        .reset_index(name="observations")
    )

    return px.bar(
        source_counts,
        x="source",
        y="observations",
        title="Observations by Data Source",
        labels={
            "source": "Source",
            "observations": "Observations",
        },
    )