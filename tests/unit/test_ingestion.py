import pandas as pd
import pytest

from src.airfare_ml.data.adapters.sample_adapter import (
    SampleSourceAdapter,
)
from src.airfare_ml.data.ingestion import ingest_source
from src.airfare_ml.data.source_config import SourceConfig

from src.airfare_ml.data.ingestion import (
    ingest_configured_source,
    ingest_source,
)

def test_ingest_configured_source_resolves_adapter(tmp_path):
    result = ingest_configured_source(
        config=make_config(),
        payload=sample_payload(),
        collection_timestamp="2026-09-03T10:00:00+00:00",
        root_dir=tmp_path,
    )

    assert isinstance(result.observations, pd.DataFrame)
    assert len(result.observations) == 1
    assert result.raw_record.source == "sample"


def test_ingest_configured_source_preserves_provenance(tmp_path):
    result = ingest_configured_source(
        config=make_config(),
        payload=sample_payload(),
        collection_timestamp="2026-09-03T10:00:00+00:00",
        root_dir=tmp_path,
    )

    observation = result.observations.iloc[0]

    assert (
        observation["raw_record_id"]
        == result.raw_record.raw_record_id
    )

    assert observation["source"] == "sample"


def sample_payload():
    return [
        {
            "collected_at": "2026-09-03T10:00:00+00:00",
            "from": "DEL",
            "to": "BOM",
            "flight_date": "2026-09-10",
            "carrier": "AI",
            "flight_no": "AI101",
            "advance_days": 7,
            "price": 5200.0,
            "currency": "INR",
        }
    ]


def make_config():
    return SourceConfig(
        name="sample",
        adapter="sample",
    )


def test_ingest_source_creates_raw_record(tmp_path):
    result = ingest_source(
        adapter=SampleSourceAdapter(),
        config=make_config(),
        payload=sample_payload(),
        collection_timestamp="2026-09-03T10:00:00+00:00",
        root_dir=tmp_path,
    )

    assert result.raw_record.source == "sample"
    assert result.raw_record.payload == sample_payload()


def test_ingest_source_saves_raw_response(tmp_path):
    result = ingest_source(
        adapter=SampleSourceAdapter(),
        config=make_config(),
        payload=sample_payload(),
        collection_timestamp="2026-09-03T10:00:00+00:00",
        root_dir=tmp_path,
    )

    assert result.raw_path.exists()
    assert result.raw_path.is_file()


def test_ingest_source_returns_canonical_observations(tmp_path):
    result = ingest_source(
        adapter=SampleSourceAdapter(),
        config=make_config(),
        payload=sample_payload(),
        collection_timestamp="2026-09-03T10:00:00+00:00",
        root_dir=tmp_path,
    )

    assert isinstance(result.observations, pd.DataFrame)
    assert len(result.observations) == 1

    assert "origin" in result.observations.columns
    assert "destination" in result.observations.columns
    assert "total_fare" in result.observations.columns


def test_ingest_source_attaches_provenance(tmp_path):
    result = ingest_source(
        adapter=SampleSourceAdapter(),
        config=make_config(),
        payload=sample_payload(),
        collection_timestamp="2026-09-03T10:00:00+00:00",
        root_dir=tmp_path,
    )

    observations = result.observations

    assert (
        observations["raw_record_id"].iloc[0]
        == result.raw_record.raw_record_id
    )

    assert observations["source"].iloc[0] == "sample"

    assert (
        observations["collection_timestamp"].iloc[0]
        == "2026-09-03T10:00:00+00:00"
    )


def test_ingest_source_preserves_multiple_observations(tmp_path):
    payload = sample_payload() + [
        {
            "collected_at": "2026-09-03T10:00:00+00:00",
            "from": "DEL",
            "to": "BLR",
            "flight_date": "2026-09-10",
            "carrier": "6E",
            "flight_no": "6E201",
            "advance_days": 7,
            "price": 6100.0,
            "currency": "INR",
        }
    ]

    result = ingest_source(
        adapter=SampleSourceAdapter(),
        config=make_config(),
        payload=payload,
        collection_timestamp="2026-09-03T10:00:00+00:00",
        root_dir=tmp_path,
    )

    assert len(result.observations) == 2

    assert (
        result.observations["raw_record_id"]
        .nunique()
        == 1
    )


def test_disabled_source_is_rejected(tmp_path):
    config = SourceConfig(
        name="sample",
        adapter="sample",
        enabled=False,
    )

    with pytest.raises(
        ValueError,
        match="disabled",
    ):
        ingest_source(
            adapter=SampleSourceAdapter(),
            config=config,
            payload=sample_payload(),
            collection_timestamp="2026-09-03T10:00:00+00:00",
            root_dir=tmp_path,
        )