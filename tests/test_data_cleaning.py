import pandas as pd

from src.airfare_ml.data.cleaning import clean_airfare_data


def create_valid_observation():
    return {
        "collection_timestamp": "2026-08-01 10:00:00",
        "source": "makemytrip",
        "origin": "DEL",
        "destination": "BOM",
        "travel_date": "2026-08-08 10:00:00",
        "airline": "IndiGo",
        "flight_number": "6E123",
        "fare_class": "Economy",
        "advance_days": 7,
        "base_fare": 5000,
        "taxes": 1000,
        "fees": 300,
        "total_fare": 6300,
        "currency": "INR",
        "availability": "available",
    }


def test_valid_observation_is_kept():

    df = pd.DataFrame([
        create_valid_observation()
    ])

    result = clean_airfare_data(df)

    assert len(result) == 1


def test_negative_fare_is_removed():

    observation = create_valid_observation()
    observation["total_fare"] = -100

    df = pd.DataFrame([observation])

    result = clean_airfare_data(df)

    assert len(result) == 0


def test_invalid_advance_window_is_removed():

    observation = create_valid_observation()
    observation["advance_days"] = 2
    observation["travel_date"] = "2026-08-03 10:00:00"

    df = pd.DataFrame([observation])

    result = clean_airfare_data(df)

    assert len(result) == 0


def test_sold_out_observation_is_removed():

    observation = create_valid_observation()
    observation["availability"] = "sold_out"

    df = pd.DataFrame([observation])

    result = clean_airfare_data(df)

    assert len(result) == 0


def test_duplicate_observation_is_removed():

    observation = create_valid_observation()

    df = pd.DataFrame([
        observation,
        observation.copy(),
    ])

    result = clean_airfare_data(df)

    assert len(result) == 1