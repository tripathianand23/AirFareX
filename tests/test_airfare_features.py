import pandas as pd

from src.airfare_ml.features.airfare_features import (
    create_airfare_features,
    get_model_features,
)


def create_sample_data():

    rows = []

    for i in range(4):
        rows.append({
            "collection_timestamp": "2026-08-01 10:00:00",
            "source": "makemytrip",
            "origin": "DEL",
            "destination": "BOM",
            "travel_date": "2026-08-08 10:00:00",
            "airline": "IndiGo",
            "flight_number": f"6E12{i}",
            "fare_class": "Economy",
            "advance_days": 7,
            "base_fare": 5000 + i * 100,
            "taxes": 1000,
            "fees": 300,
            "total_fare": 6300 + i * 100,
            "currency": "INR",
            "availability": "available",
        })

    return pd.DataFrame(rows)


def test_feature_creation():

    df = create_sample_data()

    result = create_airfare_features(df)

    assert len(result) == len(df)

    assert "route" in result.columns
    assert "is_weekend" in result.columns
    assert "route_median_fare" in result.columns
    assert "lead_time_median_fare" in result.columns


def test_route_feature():

    df = create_sample_data()

    result = create_airfare_features(df)

    assert result.loc[0, "route"] == "DEL_BOM"


def test_weekend_feature():

    df = create_sample_data()

    result = create_airfare_features(df)

    assert result["is_weekend"].isin([0, 1]).all()


def test_model_feature_list():

    df = create_sample_data()

    result = create_airfare_features(df)

    model_features = get_model_features(result)

    for feature in model_features:
        assert feature in result.columns