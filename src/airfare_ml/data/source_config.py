from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.airfare_ml.data.retry import RetryPolicy


@dataclass(frozen=True)
class SourceConfig:
    """
    Configuration for one airfare data source.

    This contains operational configuration only.
    Credentials and secrets must never be stored here.
    """

    name: str
    adapter: str

    # Source configuration
    enabled: bool = True
    endpoint: str | None = None
    timeout_seconds: int = 30
    max_retries: int = 3
    rate_limit_per_minute: int | None = None

    # Retry policy configuration
    retry_initial_delay_seconds: float = 1.0
    retry_backoff_multiplier: float = 2.0
    retry_max_delay_seconds: float = 30.0

    def __post_init__(self) -> None:
        """
        Validate source and retry configuration.
        """

        # -------------------------------------------------
        # Basic source validation
        # -------------------------------------------------

        if not self.name.strip():
            raise ValueError(
                "Source name must not be empty."
            )

        if not self.adapter.strip():
            raise ValueError(
                "Adapter name must not be empty."
            )

        # -------------------------------------------------
        # Network configuration validation
        # -------------------------------------------------

        if self.timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

        if self.max_retries < 0:
            raise ValueError(
                "max_retries must not be negative."
            )

        if (
            self.rate_limit_per_minute is not None
            and self.rate_limit_per_minute <= 0
        ):
            raise ValueError(
                "rate_limit_per_minute must be greater than zero."
            )

        # -------------------------------------------------
        # Retry configuration validation
        # -------------------------------------------------

        if self.retry_initial_delay_seconds < 0:
            raise ValueError(
                "retry_initial_delay_seconds "
                "must not be negative."
            )

        if self.retry_backoff_multiplier < 1:
            raise ValueError(
                "retry_backoff_multiplier "
                "must be at least 1."
            )

        if self.retry_max_delay_seconds < 0:
            raise ValueError(
                "retry_max_delay_seconds "
                "must not be negative."
            )


def create_source_registry(
    configs: list[SourceConfig],
) -> Mapping[str, SourceConfig]:
    """
    Create a source registry keyed by source name.

    Duplicate source names are rejected.
    """

    registry: dict[str, SourceConfig] = {}

    for config in configs:

        if config.name in registry:
            raise ValueError(
                f"Duplicate source configuration: {config.name}"
            )

        registry[config.name] = config

    return registry


def get_enabled_sources(
    registry: Mapping[str, SourceConfig],
) -> list[SourceConfig]:
    """
    Return only enabled source configurations.
    """

    return [
        config
        for config in registry.values()
        if config.enabled
    ]


def build_retry_policy(
    config: SourceConfig,
) -> RetryPolicy:
    """
    Build a RetryPolicy from source-specific configuration.
    """

    return RetryPolicy(
        max_retries=config.max_retries,
        initial_delay_seconds=(
            config.retry_initial_delay_seconds
        ),
        backoff_multiplier=(
            config.retry_backoff_multiplier
        ),
        max_delay_seconds=(
            config.retry_max_delay_seconds
        ),
    )