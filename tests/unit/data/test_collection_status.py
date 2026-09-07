from datetime import datetime, timedelta

import pytest

from src.airfare_ml.data.collection_status import (
    CollectionCycleStatus,
    SourceCollectionStatus,
    SourceStatus,
)


def test_successful_source_status():
    started = datetime(2026, 9, 3, 10, 0, 0)
    completed = datetime(2026, 9, 3, 10, 0, 5)

    status = SourceCollectionStatus(
        source="sample",
        status=SourceStatus.SUCCESS,
        started_at=started,
        completed_at=completed,
        observation_count=100,
    )

    assert status.status == SourceStatus.SUCCESS
    assert status.observation_count == 100
    assert status.duration_seconds == 5.0


def test_failed_source_requires_error():
    started = datetime(2026, 9, 3, 10, 0, 0)

    with pytest.raises(ValueError):
        SourceCollectionStatus(
            source="sample",
            status=SourceStatus.FAILED,
            started_at=started,
        )


def test_successful_source_cannot_have_error():
    started = datetime(2026, 9, 3, 10, 0, 0)

    with pytest.raises(ValueError):
        SourceCollectionStatus(
            source="sample",
            status=SourceStatus.SUCCESS,
            started_at=started,
            error_type="TimeoutError",
            error_message="Request timed out.",
        )


def test_negative_observation_count_is_rejected():
    started = datetime(2026, 9, 3, 10, 0, 0)

    with pytest.raises(ValueError):
        SourceCollectionStatus(
            source="sample",
            status=SourceStatus.SUCCESS,
            started_at=started,
            observation_count=-1,
        )


def test_collection_cycle_counts_sources():
    started = datetime(2026, 9, 3, 10, 0, 0)
    completed = started + timedelta(seconds=20)

    success = SourceCollectionStatus(
        source="source_a",
        status=SourceStatus.SUCCESS,
        started_at=started,
        completed_at=started + timedelta(seconds=5),
        observation_count=100,
    )

    failed = SourceCollectionStatus(
        source="source_b",
        status=SourceStatus.FAILED,
        started_at=started,
        completed_at=started + timedelta(seconds=10),
        error_type="TimeoutError",
        error_message="Request timed out.",
    )

    skipped = SourceCollectionStatus(
        source="source_c",
        status=SourceStatus.SKIPPED,
        started_at=started,
        completed_at=started,
    )

    cycle = CollectionCycleStatus(
        cycle_id="cycle-001",
        started_at=started,
        completed_at=completed,
        sources=(success, failed, skipped),
    )

    assert cycle.total_sources == 3
    assert cycle.successful_sources == 1
    assert cycle.failed_sources == 1
    assert cycle.skipped_sources == 1


def test_collection_completeness_ratio():
    started = datetime(2026, 9, 3, 10, 0, 0)

    sources = (
        SourceCollectionStatus(
            source="source_a",
            status=SourceStatus.SUCCESS,
            started_at=started,
            completed_at=started,
        ),
        SourceCollectionStatus(
            source="source_b",
            status=SourceStatus.SUCCESS,
            started_at=started,
            completed_at=started,
        ),
        SourceCollectionStatus(
            source="source_c",
            status=SourceStatus.FAILED,
            started_at=started,
            completed_at=started,
            error_type="ValueError",
            error_message="Invalid payload.",
        ),
        SourceCollectionStatus(
            source="source_d",
            status=SourceStatus.FAILED,
            started_at=started,
            completed_at=started,
            error_type="TimeoutError",
            error_message="Timeout.",
        ),
    )

    cycle = CollectionCycleStatus(
        cycle_id="cycle-002",
        started_at=started,
        completed_at=started,
        sources=sources,
    )

    assert cycle.completeness_ratio == 0.5


def test_collection_cycle_success_requires_all_sources_successful():
    started = datetime(2026, 9, 3, 10, 0, 0)

    source = SourceCollectionStatus(
        source="source_a",
        status=SourceStatus.SUCCESS,
        started_at=started,
        completed_at=started,
        observation_count=10,
    )

    cycle = CollectionCycleStatus(
        cycle_id="cycle-003",
        started_at=started,
        completed_at=started,
        sources=(source,),
    )

    assert cycle.is_complete is True
    assert cycle.is_successful is True


def test_collection_cycle_with_failure_is_not_successful():
    started = datetime(2026, 9, 3, 10, 0, 0)

    source = SourceCollectionStatus(
        source="source_a",
        status=SourceStatus.FAILED,
        started_at=started,
        completed_at=started,
        error_type="TimeoutError",
        error_message="Timeout.",
    )

    cycle = CollectionCycleStatus(
        cycle_id="cycle-004",
        started_at=started,
        completed_at=started,
        sources=(source,),
    )

    assert cycle.is_complete is True
    assert cycle.is_successful is False


def test_incomplete_collection_cycle():
    started = datetime(2026, 9, 3, 10, 0, 0)

    source = SourceCollectionStatus(
        source="source_a",
        status=SourceStatus.SUCCESS,
        started_at=started,
        observation_count=10,
    )

    cycle = CollectionCycleStatus(
        cycle_id="cycle-005",
        started_at=started,
        completed_at=None,
        sources=(source,),
    )

    assert cycle.is_complete is False
    assert cycle.is_successful is False


def test_empty_collection_has_zero_completeness():
    started = datetime(2026, 9, 3, 10, 0, 0)

    cycle = CollectionCycleStatus(
        cycle_id="cycle-006",
        started_at=started,
        completed_at=started,
        sources=(),
    )

    assert cycle.completeness_ratio == 0.0
    assert cycle.is_successful is False