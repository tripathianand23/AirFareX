from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from uuid import uuid4

from src.airfare_ml.data.collection_status import (
    CollectionCycleStatus,
    SourceCollectionStatus,
    SourceStatus,
)
from src.airfare_ml.data.ingestion import IngestionResult, ingest_configured_source
from src.airfare_ml.data.retry import retry_call
from src.airfare_ml.data.source_config import (
    SourceConfig,
    build_retry_policy,
    get_enabled_sources,
)


@dataclass(frozen=True)
class CollectionRequest:
    """
    Request metadata for one source collection operation.
    """

    source: str
    collection_timestamp: str
    request_id: str | None = None
    source_url: str | None = None


Collector = Callable[
    [SourceConfig, CollectionRequest],
    Any,
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso() -> str:
    return _utc_now().isoformat()


def _build_cycle_id() -> str:
    timestamp = _utc_now().strftime("%Y%m%dT%H%M%S")
    return f"cycle-{timestamp}-{uuid4().hex[:8]}"


def collect_one_source(
    *,
    config: SourceConfig,
    request: CollectionRequest,
    collector: Collector,
    root_dir: str = "data/raw",
) -> SourceCollectionStatus:
    """
    Collect and ingest one configured source.

    Retry applies only to the external collection operation.
    Ingestion is performed after a successful collection and is
    deliberately not retried.
    """

    started_at = _utc_now()
    attempts = 0

    def collect_operation() -> Any:
        nonlocal attempts
        attempts += 1

        return collector(config, request)

    try:
        payload = retry_call(
            collect_operation,
            policy=build_retry_policy(config),
        )

        ingestion_result: IngestionResult = ingest_configured_source(
            config=config,
            payload=payload,
            collection_timestamp=request.collection_timestamp,
            request_id=request.request_id,
            source_url=request.source_url,
            root_dir=root_dir,
        )

        completed_at = _utc_now()

        return SourceCollectionStatus(
            source=config.name,
            status=SourceStatus.SUCCESS,
            started_at=started_at,
            completed_at=completed_at,
            observation_count=len(ingestion_result.observations),
        )

    except Exception as exc:
        completed_at = _utc_now()

        return SourceCollectionStatus(
            source=config.name,
            status=SourceStatus.FAILED,
            started_at=started_at,
            completed_at=completed_at,
            observation_count=0,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )


def run_collection_cycle(
    *,
    configs: Mapping[str, SourceConfig],
    collector: Collector,
    collection_timestamp: str | None = None,
    request_id: str | None = None,
    cycle_id: str | None = None,
    root_dir: str = "data/raw",
) -> CollectionCycleStatus:
    """
    Execute one collection cycle across all enabled sources.

    Each source is isolated: failure of one source does not stop
    the remaining enabled sources.
    """

    cycle_started_at = _utc_now()

    if collection_timestamp is None:
        collection_timestamp = cycle_started_at.isoformat()

    if cycle_id is None:
        cycle_id = _build_cycle_id()

    source_statuses: list[SourceCollectionStatus] = []

    for config in get_enabled_sources(configs):
        request = CollectionRequest(
            source=config.name,
            collection_timestamp=collection_timestamp,
            request_id=request_id,
            source_url=config.endpoint,
        )

        status = collect_one_source(
            config=config,
            request=request,
            collector=collector,
            root_dir=root_dir,
        )

        source_statuses.append(status)

    cycle_completed_at = _utc_now()

    return CollectionCycleStatus(
        cycle_id=cycle_id,
        started_at=cycle_started_at,
        completed_at=cycle_completed_at,
        sources=tuple(source_statuses),
    )