import pandas as pd
import pytest

from src.airfare_ml.data.adapters.sample_adapter import (
    SampleSourceAdapter,
)
from src.airfare_ml.data.schema import CANONICAL_COLUMNS


def test_sample_adapter_returns_canonical_schema():

    raw_data = [
        {
            "collected_at": "2026-09-03 10:00:00",
            "from": "DEL",
            "to": "BOM",
            "flight_date": "2026-09-04",
            "carrier": "IndiGo",
            "flight_no": "6E123",
            "price": 5500.0,
            "advance_days": 1,
        }
    ]

    adapter = SampleSourceAdapter()

    result = adapter.transform(raw_data)

    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == CANONICAL_COLUMNS
    assert len(result) == 1


def test_sample_adapter_maps_fields_correctly():

    raw_data = [
        {
            "collected_at": "2026-09-03 10:00:00",
            "from": "DEL",
            "to": "BOM",
            "flight_date": "2026-09-04",
            "carrier": "IndiGo",
            "flight_no": "6E123",
            "price": 5500.0,
            "advance_days": 1,
        }
    ]

    adapter = SampleSourceAdapter()

    result = adapter.transform(raw_data)

    row = result.iloc[0]

    assert row["origin"] == "DEL"
    assert row["destination"] == "BOM"
    assert row["airline"] == "IndiGo"
    assert row["flight_number"] == "6E123"
    assert row["total_fare"] == 5500.0
    assert row["currency"] == "INR"


def test_sample_adapter_rejects_invalid_input():

    adapter = SampleSourceAdapter()

    with pytest.raises(TypeError):
        adapter.transform({"invalid": "input"})