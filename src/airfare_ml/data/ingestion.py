from __future__ import annotations

from pathlib import Path
from typing import Any

from src.airfare_ml.data.adapters.registry import create_adapter

import pandas as pd

def ingest_configured_source(
    *,
    config: SourceConfig,
    payload: Any,
    collection_timestamp: str,
    request_id: str | None = None,
    source_url: str | None = None,
    root_dir: str | Path = "data/raw",
    ingestion_timestamp: str | None = None,
) -> IngestionResult:
    """
    Ingest a source using the adapter declared in SourceConfig.

    Adapter resolution is handled by the adapter registry.
    """

    adapter = create_adapter(config.adapter)

    return ingest_source(
        adapter=adapter,
        config=config,
        payload=payload,
        collection_timestamp=collection_timestamp,
        request_id=request_id,
        source_url=source_url,
        root_dir=root_dir,
        ingestion_timestamp=ingestion_timestamp,
    )

from src.airfare_ml.data.provenance import (
    ProvenanceMetadata,
    attach_provenance,
    validate_provenance,
)
from src.airfare_ml.data.raw_storage import (
    RawRecord,
    create_raw_record,
    save_raw_record,
)
from src.airfare_ml.data.source_config import SourceConfig


class IngestionResult:
    """
    Result of one source ingestion operation.
    """

    def __init__(
        self,
        *,
        raw_record: RawRecord,
        observations: pd.DataFrame,
        raw_path: Path,
    ) -> None:
        self.raw_record = raw_record
        self.observations = observations
        self.raw_path = raw_path


def ingest_source(
    *,
    adapter: Any,
    config: SourceConfig,
    payload: Any,
    collection_timestamp: str,
    request_id: str | None = None,
    source_url: str | None = None,
    root_dir: str | Path = "data/raw",
    ingestion_timestamp: str | None = None,
) -> IngestionResult:
    """
    Process one already-retrieved source response.

    Network communication is deliberately outside this function.
    This keeps ingestion deterministic and easy to test.
    """

    if not config.enabled:
        raise ValueError(
            f"Source '{config.name}' is disabled."
        )

    if adapter is None:
        raise ValueError("adapter must not be None.")

    raw_record = create_raw_record(
        source=config.name,
        payload=payload,
        collection_timestamp=collection_timestamp,
        request_id=request_id,
        source_url=source_url,
        ingestion_timestamp=ingestion_timestamp,
    )

    raw_path = save_raw_record(
        raw_record,
        root_dir=root_dir,
    )

    observations = adapter.transform(payload)

    provenance = ProvenanceMetadata(
        raw_record_id=raw_record.raw_record_id,
        source=raw_record.source,
        collection_timestamp=raw_record.collection_timestamp,
        ingestion_timestamp=raw_record.ingestion_timestamp,
    )

    observations = attach_provenance(
        observations,
        provenance,
    )

    validate_provenance(observations)

    return IngestionResult(
        raw_record=raw_record,
        observations=observations,
        raw_path=raw_path,
    )