from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SourceStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class SourceCollectionStatus:
    source: str
    status: SourceStatus
    started_at: datetime
    completed_at: datetime | None = None
    observation_count: int = 0
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("source must not be empty.")

        if self.observation_count < 0:
            raise ValueError("observation_count must not be negative.")

        if self.status == SourceStatus.SUCCESS:
            if self.error_type is not None or self.error_message is not None:
                raise ValueError(
                    "Successful sources must not contain error information."
                )

        if self.status == SourceStatus.FAILED:
            if not self.error_type or not self.error_message:
                raise ValueError(
                    "Failed sources must contain error information."
                )

    @property
    def duration_seconds(self) -> float | None:
        if self.completed_at is None:
            return None

        return (self.completed_at - self.started_at).total_seconds()


@dataclass(frozen=True)
class CollectionCycleStatus:
    cycle_id: str
    started_at: datetime
    completed_at: datetime | None
    sources: tuple[SourceCollectionStatus, ...]

    def __post_init__(self) -> None:
        if not self.cycle_id.strip():
            raise ValueError("cycle_id must not be empty.")

    @property
    def total_sources(self) -> int:
        return len(self.sources)

    @property
    def successful_sources(self) -> int:
        return sum(
            source.status == SourceStatus.SUCCESS
            for source in self.sources
        )

    @property
    def failed_sources(self) -> int:
        return sum(
            source.status == SourceStatus.FAILED
            for source in self.sources
        )

    @property
    def skipped_sources(self) -> int:
        return sum(
            source.status == SourceStatus.SKIPPED
            for source in self.sources
        )

    @property
    def completeness_ratio(self) -> float:
        if self.total_sources == 0:
            return 0.0

        return self.successful_sources / self.total_sources

    @property
    def is_complete(self) -> bool:
        return self.completed_at is not None

    @property
    def is_successful(self) -> bool:
        return (
            self.is_complete
            and self.total_sources > 0
            and self.failed_sources == 0
        )

    @property
    def duration_seconds(self) -> float | None:
        if self.completed_at is None:
            return None

        return (self.completed_at - self.started_at).total_seconds()