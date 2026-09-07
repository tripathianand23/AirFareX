import pytest

from src.airfare_ml.data.retry import RetryPolicy
from src.airfare_ml.data.source_config import (
    SourceConfig,
    build_retry_policy,
    create_source_registry,
    get_enabled_sources,
)


# =========================================================
# BASIC SOURCE CONFIGURATION
# =========================================================


def test_source_config_defaults():
    config = SourceConfig(
        name="sample",
        adapter="sample",
    )

    assert config.name == "sample"
    assert config.adapter == "sample"
    assert config.enabled is True
    assert config.timeout_seconds == 30
    assert config.max_retries == 3
    assert config.endpoint is None
    assert config.rate_limit_per_minute is None


def test_source_config_custom_values():
    config = SourceConfig(
        name="example",
        adapter="example_adapter",
        enabled=False,
        endpoint="https://example.com/api",
        timeout_seconds=60,
        max_retries=5,
        rate_limit_per_minute=20,
    )

    assert config.name == "example"
    assert config.adapter == "example_adapter"
    assert config.enabled is False
    assert config.endpoint == "https://example.com/api"
    assert config.timeout_seconds == 60
    assert config.max_retries == 5
    assert config.rate_limit_per_minute == 20


# =========================================================
# VALIDATION
# =========================================================


def test_empty_source_name_rejected():
    with pytest.raises(
        ValueError,
        match="Source name",
    ):
        SourceConfig(
            name="",
            adapter="sample",
        )


def test_empty_adapter_name_rejected():
    with pytest.raises(
        ValueError,
        match="Adapter name",
    ):
        SourceConfig(
            name="sample",
            adapter="",
        )


def test_invalid_timeout_rejected():
    with pytest.raises(
        ValueError,
        match="timeout_seconds",
    ):
        SourceConfig(
            name="sample",
            adapter="sample",
            timeout_seconds=0,
        )


def test_negative_retries_rejected():
    with pytest.raises(
        ValueError,
        match="max_retries",
    ):
        SourceConfig(
            name="sample",
            adapter="sample",
            max_retries=-1,
        )


def test_invalid_rate_limit_rejected():
    with pytest.raises(
        ValueError,
        match="rate_limit_per_minute",
    ):
        SourceConfig(
            name="sample",
            adapter="sample",
            rate_limit_per_minute=0,
        )


# =========================================================
# RETRY CONFIGURATION
# =========================================================


def test_source_config_retry_defaults():
    config = SourceConfig(
        name="sample",
        adapter="sample",
    )

    assert config.max_retries == 3
    assert config.retry_initial_delay_seconds == 1.0
    assert config.retry_backoff_multiplier == 2.0
    assert config.retry_max_delay_seconds == 30.0


def test_source_config_custom_retry_values():
    config = SourceConfig(
        name="sample",
        adapter="sample",
        max_retries=5,
        retry_initial_delay_seconds=2.0,
        retry_backoff_multiplier=3.0,
        retry_max_delay_seconds=20.0,
    )

    assert config.max_retries == 5
    assert config.retry_initial_delay_seconds == 2.0
    assert config.retry_backoff_multiplier == 3.0
    assert config.retry_max_delay_seconds == 20.0


def test_source_config_rejects_negative_retry_count():
    with pytest.raises(
        ValueError,
        match="max_retries",
    ):
        SourceConfig(
            name="sample",
            adapter="sample",
            max_retries=-1,
        )


def test_source_config_rejects_negative_retry_delay():
    with pytest.raises(
        ValueError,
        match="retry_initial_delay_seconds",
    ):
        SourceConfig(
            name="sample",
            adapter="sample",
            retry_initial_delay_seconds=-1,
        )


def test_source_config_rejects_invalid_backoff_multiplier():
    with pytest.raises(
        ValueError,
        match="retry_backoff_multiplier",
    ):
        SourceConfig(
            name="sample",
            adapter="sample",
            retry_backoff_multiplier=0.5,
        )


def test_source_config_rejects_negative_max_retry_delay():
    with pytest.raises(
        ValueError,
        match="retry_max_delay_seconds",
    ):
        SourceConfig(
            name="sample",
            adapter="sample",
            retry_max_delay_seconds=-1,
        )


# =========================================================
# RETRY POLICY CONSTRUCTION
# =========================================================


def test_build_retry_policy_from_source_config():
    config = SourceConfig(
        name="sample",
        adapter="sample",
        max_retries=5,
        retry_initial_delay_seconds=2.0,
        retry_backoff_multiplier=3.0,
        retry_max_delay_seconds=20.0,
    )

    policy = build_retry_policy(config)

    assert isinstance(
        policy,
        RetryPolicy,
    )

    assert policy.max_retries == 5
    assert policy.initial_delay_seconds == 2.0
    assert policy.backoff_multiplier == 3.0
    assert policy.max_delay_seconds == 20.0


# =========================================================
# SOURCE REGISTRY
# =========================================================


def test_registry_creation():
    sample = SourceConfig(
        name="sample",
        adapter="sample",
    )

    example = SourceConfig(
        name="example",
        adapter="example",
    )

    registry = create_source_registry(
        [sample, example]
    )

    assert list(registry.keys()) == [
        "sample",
        "example",
    ]

    assert registry["sample"] == sample
    assert registry["example"] == example


def test_duplicate_source_rejected():
    first = SourceConfig(
        name="sample",
        adapter="sample",
    )

    second = SourceConfig(
        name="sample",
        adapter="another",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate source configuration",
    ):
        create_source_registry(
            [first, second]
        )


# =========================================================
# ENABLED SOURCES
# =========================================================


def test_enabled_sources():
    enabled = SourceConfig(
        name="enabled",
        adapter="sample",
        enabled=True,
    )

    disabled = SourceConfig(
        name="disabled",
        adapter="sample",
        enabled=False,
    )

    registry = create_source_registry(
        [enabled, disabled]
    )

    result = get_enabled_sources(
        registry
    )

    assert result == [enabled]


def test_all_sources_disabled():
    first = SourceConfig(
        name="first",
        adapter="sample",
        enabled=False,
    )

    second = SourceConfig(
        name="second",
        adapter="sample",
        enabled=False,
    )

    registry = create_source_registry(
        [first, second]
    )

    result = get_enabled_sources(
        registry
    )

    assert result == []