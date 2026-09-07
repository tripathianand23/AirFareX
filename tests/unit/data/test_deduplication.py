import pandas as pd
import pytest

from src.airfare_ml.data.deduplication import (
    build_deduplication_key,
    deduplicate_airfare_observations,
)


def make_dataframe():
    return pd.DataFrame(
        [
            {
                "collection_timestamp": "2026-09-02 15:17:21",
                "source": "EaseMyTrip",
                "origin": "DEL",
                "destination": "BOM",
                "travel_date": "2026-09-09",
                "airline": "SpiceJet",
                "advance_days": 7,
                "base_fare": 5446.80,
                "taxes": 961.20,
                "fees": 0.0,
                "total_fare": 6408.0,
                "currency": "INR",
            },
            {
                "collection_timestamp": "2026-09-02 15:17:21",
                "source": "EaseMyTrip",
                "origin": "DEL",
                "destination": "BOM",
                "travel_date": "2026-09-09",
                "airline": "SpiceJet",
                "advance_days": 7,
                "base_fare": 5446.80,
                "taxes": 961.20,
                "fees": 0.0,
                "total_fare": 6408.0,
                "currency": "INR",
            },
            {
                "collection_timestamp": "2026-09-02 15:17:21",
                "source": "EaseMyTrip",
                "origin": "DEL",
                "destination": "BOM",
                "travel_date": "2026-09-09",
                "airline": "IndiGo",
                "advance_days": 7,
                "base_fare": 5176.50,
                "taxes": 913.50,
                "fees": 0.0,
                "total_fare": 6090.0,
                "currency": "INR",
            },
        ]
    )


def test_business_duplicate_is_removed():
    df = make_dataframe()

    dedup_df, summary = deduplicate_airfare_observations(df)

    assert len(dedup_df) == 2
    assert summary["original_rows"] == 3
    assert summary["duplicate_rows"] == 1
    assert summary["deduplicated_rows"] == 2


def test_different_airlines_are_not_deduplicated():
    df = make_dataframe()

    dedup_df, _ = deduplicate_airfare_observations(df)

    assert set(dedup_df["airline"]) == {
        "SpiceJet",
        "IndiGo",
    }


def test_different_fares_are_not_deduplicated():
    df = make_dataframe()

    modified = df.copy()

    modified.loc[1, "total_fare"] = 6500.0

    dedup_df, summary = deduplicate_airfare_observations(
        modified
    )

    assert len(dedup_df) == 3
    assert summary["duplicate_rows"] == 0


def test_empty_dataframe():
    df = pd.DataFrame()

    result, summary = deduplicate_airfare_observations(df)

    assert result.empty
    assert summary["original_rows"] == 0
    assert summary["duplicate_rows"] == 0


def test_missing_required_column_raises():
    df = make_dataframe().drop(
        columns=["total_fare"]
    )

    with pytest.raises(ValueError):
        build_deduplication_key(df)


def test_deduplication_does_not_modify_input():
    df = make_dataframe()

    original_columns = df.columns.tolist()

    deduplicate_airfare_observations(df)

    assert df.columns.tolist() == original_columns
    assert "_deduplication_key" not in df.columns
