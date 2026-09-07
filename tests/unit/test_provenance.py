import pandas as pd
import pytest

from src.airfare_ml.data.provenance import (
    ProvenanceMetadata,
    attach_provenance,
    get_raw_record_ids,
    validate_provenance,
)


def make_observations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "origin": ["DEL", "DEL"],
            "destination": ["BOM", "BLR"],
            "airline": ["AI", "6E"],
            "total_fare": [5200.0, 6100.0],
        }
    )


def make_metadata() -> ProvenanceMetadata:
    return ProvenanceMetadata(
        raw_record_id="raw123",
        source="sample",
        collection_timestamp="2026-09-03T10:00:00+00:00",
        ingestion_timestamp="2026-09-03T10:01:00+00:00",
    )


def test_attach_provenance():
    df = make_observations()

    result = attach_provenance(
        df,
        make_metadata(),
    )

    assert len(result) == 2
    assert result["raw_record_id"].tolist() == [
        "raw123",
        "raw123",
    ]
    assert result["source"].tolist() == [
        "sample",
        "sample",
    ]


def test_provenance_metadata_is_preserved():
    df = make_observations()

    result = attach_provenance(
        df,
        make_metadata(),
    )

    assert (
        result["collection_timestamp"].iloc[0]
        == "2026-09-03T10:00:00+00:00"
    )

    assert (
        result["ingestion_timestamp"].iloc[0]
        == "2026-09-03T10:01:00+00:00"
    )


def test_validate_provenance_passes():
    df = attach_provenance(
        make_observations(),
        make_metadata(),
    )

    validate_provenance(df)


def test_validate_provenance_rejects_missing_column():
    df = make_observations()

    with pytest.raises(ValueError, match="Missing provenance columns"):
        validate_provenance(df)


def test_validate_provenance_rejects_missing_value():
    df = attach_provenance(
        make_observations(),
        make_metadata(),
    )

    df.loc[0, "raw_record_id"] = None

    with pytest.raises(
        ValueError,
        match="contains missing values",
    ):
        validate_provenance(df)


def test_get_raw_record_ids():
    df = attach_provenance(
        make_observations(),
        make_metadata(),
    )

    assert get_raw_record_ids(df) == ["raw123"]