from __future__ import annotations

from pathlib import Path

import pytest

from src.airfare_ml.data.collection_cycle import (
    CollectionRequest,
    collect_one_source,
    run_collection_cycle,
)
from src.airfare_ml.data.collection_status import SourceStatus
from src.airfare_ml.data.source_config import SourceConfig


def _sample_payload():
    return [
        {
            "collected_at": "2026-09-04T10:00:00+00:00",
            "from": "DEL",
            "to": "BOM",
            "flight_date": "2026-09-11",
            "carrier": "TEST",
            "flight_no": "T100",
            "advance_days": 7,
            "price": 5500.0,
            "currency": "INR",
        }
    ]


def test_collect_one_source_success(tmp_path: Path):
    config = SourceConfig(
        name="sample",
        adapter="sample",
        enabled=True,
    )

    request = CollectionRequest(
        source="sample",
        collection_timestamp="2026-09-04T10:00:00+00:00",
        request_id="test-request",
    )

    calls = []

    def collector(config, request):
        calls.append(1)
        return _sample_payload()

    result = collect_one_source(
        config=config,
        request=request,
        collector=collector,
        root_dir=str(tmp_path),
    )

    assert result.source == "sample"
    assert result.status == SourceStatus.SUCCESS
    assert result.observation_count == 1
    assert result.error_type is None
    assert result.error_message is None
    assert len(calls) == 1


def test_collect_one_source_failure_is_captured(tmp_path: Path):
    config = SourceConfig(
        name="sample",
        adapter="sample",
        enabled=True,
        max_retries=0,
    )

    request = CollectionRequest(
        source="sample",
        collection_timestamp="2026-09-04T10:00:00+00:00",
    )

    def collector(config, request):
        raise ConnectionError("source unavailable")

    result = collect_one_source(
        config=config,
        request=request,
        collector=collector,
        root_dir=str(tmp_path),
    )

    assert result.source == "sample"
    assert result.status == SourceStatus.FAILED
    assert result.observation_count == 0
    assert result.error_type == "ConnectionError"
    assert "source unavailable" in result.error_message


def test_collect_one_source_retries_transient_failure(tmp_path: Path):
    config = SourceConfig(
        name="sample",
        adapter="sample",
        enabled=True,
        max_retries=2,
        retry_initial_delay_seconds=0,
    )

    request = CollectionRequest(
        source="sample",
        collection_timestamp="2026-09-04T10:00:00+00:00",
    )

    attempts = []

    def collector(config, request):
        attempts.append(1)

        if len(attempts) < 3:
            raise ConnectionError("temporary failure")

        return _sample_payload()

    result = collect_one_source(
        config=config,
        request=request,
        collector=collector,
        root_dir=str(tmp_path),
    )

    assert result.status == SourceStatus.SUCCESS
    assert result.observation_count == 1
    assert len(attempts) == 3


def test_non_retryable_exception_is_not_retried(tmp_path: Path):
    config = SourceConfig(
        name="sample",
        adapter="sample",
        enabled=True,
        max_retries=5,
        retry_initial_delay_seconds=0,
    )

    request = CollectionRequest(
        source="sample",
        collection_timestamp="2026-09-04T10:00:00+00:00",
    )

    attempts = []

    def collector(config, request):
        attempts.append(1)
        raise ValueError("invalid response")

    result = collect_one_source(
        config=config,
        request=request,
        collector=collector,
        root_dir=str(tmp_path),
    )

    assert result.status == SourceStatus.FAILED
    assert result.error_type == "ValueError"
    assert len(attempts) == 1


def test_run_collection_cycle_success(tmp_path: Path):
    configs = {
        "sample": SourceConfig(
            name="sample",
            adapter="sample",
            enabled=True,
        )
    }

    def collector(config, request):
        assert request.source == "sample"
        return _sample_payload()

    result = run_collection_cycle(
        configs=configs,
        collector=collector,
        collection_timestamp="2026-09-04T10:00:00+00:00",
        request_id="cycle-test",
        cycle_id="cycle-test-001",
        root_dir=str(tmp_path),
    )

    assert result.cycle_id == "cycle-test-001"
    assert result.total_sources == 1
    assert result.successful_sources == 1
    assert result.failed_sources == 0
    assert result.skipped_sources == 0
    assert result.completeness_ratio == 1.0
    assert result.is_complete is True
    assert result.is_successful is True


def test_failed_source_does_not_stop_cycle(tmp_path: Path):
    configs = {
        "working": SourceConfig(
            name="working",
            adapter="sample",
            enabled=True,
        ),
        "failing": SourceConfig(
            name="failing",
            adapter="sample",
            enabled=True,
            max_retries=0,
        ),
    }

    def collector(config, request):
        if config.name == "failing":
            raise ConnectionError("temporary outage")

        return _sample_payload()

    result = run_collection_cycle(
        configs=configs,
        collector=collector,
        collection_timestamp="2026-09-04T10:00:00+00:00",
        root_dir=str(tmp_path),
    )

    assert result.total_sources == 2
    assert result.successful_sources == 1
    assert result.failed_sources == 1
    assert result.completeness_ratio == 0.5
    assert result.is_complete is True
    assert result.is_successful is False


def test_disabled_sources_are_not_collected(tmp_path: Path):
    configs = {
        "enabled": SourceConfig(
            name="enabled",
            adapter="sample",
            enabled=True,
        ),
        "disabled": SourceConfig(
            name="disabled",
            adapter="sample",
            enabled=False,
        ),
    }

    collected_sources = []

    def collector(config, request):
        collected_sources.append(config.name)
        return _sample_payload()

    result = run_collection_cycle(
        configs=configs,
        collector=collector,
        collection_timestamp="2026-09-04T10:00:00+00:00",
        root_dir=str(tmp_path),
    )

    assert result.total_sources == 1
    assert result.successful_sources == 1
    assert collected_sources == ["enabled"]


def test_cycle_generates_cycle_id(tmp_path: Path):
    configs = {
        "sample": SourceConfig(
            name="sample",
            adapter="sample",
            enabled=True,
        )
    }

    def collector(config, request):
        return _sample_payload()

    result = run_collection_cycle(
        configs=configs,
        collector=collector,
        collection_timestamp="2026-09-04T10:00:00+00:00",
        root_dir=str(tmp_path),
    )

    assert result.cycle_id.startswith("cycle-")


def test_cycle_with_no_enabled_sources(tmp_path: Path):
    configs = {
        "disabled": SourceConfig(
            name="disabled",
            adapter="sample",
            enabled=False,
        )
    }

    def collector(config, request):
        pytest.fail("Collector must not be called.")

    result = run_collection_cycle(
        configs=configs,
        collector=collector,
        collection_timestamp="2026-09-04T10:00:00+00:00",
        root_dir=str(tmp_path),
    )

    assert result.total_sources == 0
    assert result.successful_sources == 0
    assert result.failed_sources == 0
    assert result.completeness_ratio == 0.0
    assert result.is_complete is True
    assert result.is_successful is False