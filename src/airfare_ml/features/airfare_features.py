import pandas as pd


def create_airfare_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create ML-ready features from cleaned airfare observations.

    The original DataFrame is not modified.
    """

    features = df.copy()

    # ---------------------------------------------------------
    # 1. Ensure datetime columns are properly parsed
    # ---------------------------------------------------------
    features["collection_timestamp"] = pd.to_datetime(
        features["collection_timestamp"],
        errors="coerce",
    )

    features["travel_date"] = pd.to_datetime(
        features["travel_date"],
        errors="coerce",
    )

    # ---------------------------------------------------------
    # 2. Calendar features
    # ---------------------------------------------------------
    features["collection_day_of_week"] = (
        features["collection_timestamp"].dt.dayofweek
    )

    features["travel_day_of_week"] = (
        features["travel_date"].dt.dayofweek
    )

    features["travel_month"] = (
        features["travel_date"].dt.month
    )

    features["is_weekend"] = (
        features["travel_day_of_week"] >= 5
    ).astype(int)

    # ---------------------------------------------------------
    # 3. Route feature
    # ---------------------------------------------------------
    features["route"] = (
        features["origin"].astype(str)
        + "_"
        + features["destination"].astype(str)
    )

    # ---------------------------------------------------------
    # 4. Fare composition features
    # ---------------------------------------------------------
    features["tax_fee_ratio"] = (
        features["taxes"].fillna(0)
        + features["fees"].fillna(0)
    ) / features["total_fare"]

    features["base_fare_ratio"] = (
        features["base_fare"]
        / features["total_fare"]
    )

    # ---------------------------------------------------------
    # 5. Route-level fare statistics
    #
    # These provide context to the anomaly detector.
    # ---------------------------------------------------------
    route_median = (
        features
        .groupby("route")["total_fare"]
        .transform("median")
    )

    route_mean = (
        features
        .groupby("route")["total_fare"]
        .transform("mean")
    )

    route_std = (
        features
        .groupby("route")["total_fare"]
        .transform("std")
    )

    features["route_median_fare"] = route_median

    features["route_mean_fare"] = route_mean

    features["route_fare_deviation"] = (
        features["total_fare"] - route_median
    )

    features["route_fare_zscore"] = (
        (features["total_fare"] - route_mean)
        / route_std.replace(0, pd.NA)
    )

    # ---------------------------------------------------------
    # 6. Lead-time contextual features
    # ---------------------------------------------------------
    lead_time_median = (
        features
        .groupby(["route", "advance_days"])["total_fare"]
        .transform("median")
    )

    features["lead_time_median_fare"] = (
        lead_time_median
    )

    features["lead_time_fare_deviation"] = (
        features["total_fare"]
        - features["lead_time_median_fare"]
    )

    features["lead_time_fare_ratio"] = (
        features["total_fare"]
        / features["lead_time_median_fare"]
    )

    # ---------------------------------------------------------
    # 7. Airline-route contextual features
    # ---------------------------------------------------------
    airline_route_median = (
        features
        .groupby(
            ["route", "airline"]
        )["total_fare"]
        .transform("median")
    )

    features["airline_route_median_fare"] = (
        airline_route_median
    )

    features["airline_route_deviation"] = (
        features["total_fare"]
        - features["airline_route_median_fare"]
    )

    # ---------------------------------------------------------
    # 8. Fare class encoding
    # ---------------------------------------------------------
    features["fare_class_encoded"] = (
        features["fare_class"]
        .astype("category")
        .cat.codes
    )

    # ---------------------------------------------------------
    # 9. Source encoding
    # ---------------------------------------------------------
    features["source_encoded"] = (
        features["source"]
        .astype("category")
        .cat.codes
    )

    # ---------------------------------------------------------
    # 10. Airline encoding
    # ---------------------------------------------------------
    features["airline_encoded"] = (
        features["airline"]
        .astype("category")
        .cat.codes
    )

    return features


def get_model_features(df: pd.DataFrame) -> list[str]:
    """
    Return numerical features suitable for ML models.
    """

    model_features = [
        "advance_days",
        "base_fare",
        "taxes",
        "fees",
        "total_fare",
        "collection_day_of_week",
        "travel_day_of_week",
        "travel_month",
        "is_weekend",
        "tax_fee_ratio",
        "base_fare_ratio",
        "route_median_fare",
        "route_fare_deviation",
        "route_fare_zscore",
        "lead_time_median_fare",
        "lead_time_fare_deviation",
        "lead_time_fare_ratio",
        "airline_route_median_fare",
        "airline_route_deviation",
        "fare_class_encoded",
        "source_encoded",
        "airline_encoded",
    ]

    return model_features