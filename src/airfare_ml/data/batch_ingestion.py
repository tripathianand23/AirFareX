from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.airfare_ml.data.ingestion import (
    IngestionResult,
    ingest_configured_source,
)
from src.airfare_ml.data.ingestion_errors import IngestionFailure
from src.airfare_ml.data.source_config import SourceConfig


@dataclass(frozen=True)
class SourcePayload:
    config: SourceConfig
    payload: Any
    collection_timestamp: str
    request_id: str | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class BatchIngestionResult:
    results: tuple[IngestionResult, ...]
    failures: tuple[IngestionFailure, ...] = ()

    @property
    def observations(self) -> pd.DataFrame:
        if not self.results:
            return pd.DataFrame()

        return pd.concat(
            [result.observations for result in self.results],
            ignore_index=True,
        )

    @property
    def raw_paths(self) -> list[Path]:
        return [result.raw_path for result in self.results]

    @property
    def successful_sources(self) -> list[str]:
        return [
            result.raw_record.source
            for result in self.results
        ]

    @property
    def failed_sources(self) -> list[str]:
        return [failure.source for failure in self.failures]

    @property
    def is_successful(self) -> bool:
        return len(self.failures) == 0

    @property
    def has_results(self) -> bool:
        return len(self.results) > 0


def ingest_batch(
    source_payloads: list[SourcePayload],
    *,
    root_dir: str | Path = "data/raw",
    ingestion_timestamp: str | None = None,
    fail_fast: bool = False,
) -> BatchIngestionResult:
    results: list[IngestionResult] = []
    failures: list[IngestionFailure] = []

    for item in source_payloads:
        try:
            result = ingest_configured_source(
                config=item.config,
                payload=item.payload,
                collection_timestamp=item.collection_timestamp,
                request_id=item.request_id,
                source_url=item.source_url,
                root_dir=root_dir,
                ingestion_timestamp=ingestion_timestamp,
            )

            results.append(result)

        except Exception as exc:
            failure = IngestionFailure(
                source=item.config.name,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

            failures.append(failure)

            if fail_fast:
                raise

    return BatchIngestionResult(
        results=tuple(results),
        failures=tuple(failures),
    )