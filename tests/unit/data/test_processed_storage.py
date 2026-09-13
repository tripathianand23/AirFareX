from pathlib import Path

import pandas as pd
import pytest

from src.airfare_ml.data.processed_storage import (
    ProcessedStorageError,
    load_processed_observations,
    prepare_observations_for_storage,
    save_processed_observations,
)


def sample_observations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "collection_timestamp": [
                "2026-09-04T10:00:00+00:00",
                "2026-09-04T10:05:00+00:00",
            ],
            "source": ["sample", "sample"],
            "origin": ["DEL", "DEL"],
            "destination": ["BOM", "BOM"],
            "travel_date": ["2026-09-10", "2026-09-10"],
            "airline": ["AI", "6E"],
            "flight_number": ["AI101", "6E201"],
            "advance_days": [6, 6],
            "base_fare": [4500.0, 4700.0],
            "total_fare": [5000.0, 5200.0],
            "currency": ["INR", "INR"],
            "ingestion_timestamp": [
                "2026-09-04T10:01:00+00:00",
                "2026-09-04T10:06:00+00:00",
            ],
            "raw_record_id": ["raw-1", "raw-2"],
        }
    )


def test_prepare_adds_collection_date():
    prepared = prepare_observations_for_storage(sample_observations())
    assert prepared["collection_date"].tolist() == ["2026-09-04", "2026-09-04"]


def test_save_and_load_round_trip(tmp_path: Path):
    path = save_processed_observations(sample_observations(), root_dir=tmp_path)
    assert path.exists()
    assert "source=sample" in str(path)
    assert "collection_date=2026-09-04" in str(path)

    loaded = load_processed_observations(path)
    assert len(loaded) == 2
    assert loaded["total_fare"].tolist() == [5000.0, 5200.0]


def test_multi_source_partition_is_rejected(tmp_path: Path):
    df = sample_observations()
    df.loc[1, "source"] = "other"

    with pytest.raises(ProcessedStorageError, match="one source per partition"):
        save_processed_observations(df, root_dir=tmp_path)


def test_multi_date_partition_is_rejected(tmp_path: Path):
    df = sample_observations()
    df.loc[1, "collection_timestamp"] = "2026-09-05T10:05:00+00:00"

    with pytest.raises(ProcessedStorageError, match="one collection date per partition"):
        save_processed_observations(df, root_dir=tmp_path)
