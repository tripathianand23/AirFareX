import pandas as pd

from src.airfare_ml.data.validation import validate_fares


def test_negative_fare_is_invalid():

    df = pd.DataFrame({
        "collection_timestamp": [
            "2026-08-01 10:00:00"
        ],
        "source": ["makemytrip"],
        "origin": ["DEL"],
        "destination": ["BOM"],
        "travel_date": [
            "2026-08-08 10:00:00"
        ],
        "airline": ["IndiGo"],
        "flight_number": ["6E123"],
        "fare_class": ["Economy"],
        "advance_days": [7],
        "base_fare": [5000],
        "taxes": [1000],
        "fees": [300],
        "total_fare": [-100],
        "currency": ["INR"],
        "availability": ["available"],
    })

    result = validate_fares(df)

    assert result.loc[0, "invalid_fare"]
    assert not result.loc[0, "is_valid"]


def test_valid_observation_is_valid():

    df = pd.DataFrame({
        "collection_timestamp": [
            "2026-08-01 10:00:00"
        ],
        "source": ["makemytrip"],
        "origin": ["DEL"],
        "destination": ["BOM"],
        "travel_date": [
            "2026-08-08 10:00:00"
        ],
        "airline": ["IndiGo"],
        "flight_number": ["6E123"],
        "fare_class": ["Economy"],
        "advance_days": [7],
        "base_fare": [5000],
        "taxes": [1000],
        "fees": [300],
        "total_fare": [6300],
        "currency": ["INR"],
        "availability": ["available"],
    })

    result = validate_fares(df)

    assert result.loc[0, "is_valid"]


def test_invalid_advance_window():

    df = pd.DataFrame({
        "collection_timestamp": [
            "2026-08-01 10:00:00"
        ],
        "source": ["makemytrip"],
        "origin": ["DEL"],
        "destination": ["BOM"],
        "travel_date": [
            "2026-08-03 10:00:00"
        ],
        "airline": ["IndiGo"],
        "flight_number": ["6E123"],
        "fare_class": ["Economy"],
        "advance_days": [2],
        "base_fare": [5000],
        "taxes": [1000],
        "fees": [300],
        "total_fare": [6300],
        "currency": ["INR"],
        "availability": ["available"],
    })

    result = validate_fares(df)

    assert result.loc[0, "invalid_advance_window"]
    assert not result.loc[0, "is_valid"]