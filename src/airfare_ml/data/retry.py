from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from src.airfare_ml.data.ingestion_errors import (
    CollectionNetworkError,
    CollectionTimeoutError,
    TransientCollectionError,
)

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 3
    initial_delay_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    max_delay_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative.")

        if self.initial_delay_seconds < 0:
            raise ValueError(
                "initial_delay_seconds must not be negative."
            )

        if self.backoff_multiplier < 1:
            raise ValueError(
                "backoff_multiplier must be at least 1."
            )

        if self.max_delay_seconds < 0:
            raise ValueError(
                "max_delay_seconds must not be negative."
            )

    @property
    def max_attempts(self) -> int:
        return self.max_retries + 1

    def delay_for_retry(self, retry_number: int) -> float:
        if retry_number < 1:
            raise ValueError(
                "retry_number must be at least 1."
            )

        delay = self.initial_delay_seconds * (
            self.backoff_multiplier ** (retry_number - 1)
        )

        return min(
            delay,
            self.max_delay_seconds,
        )


DEFAULT_RETRY_POLICY = RetryPolicy()


DEFAULT_RETRYABLE_EXCEPTIONS: tuple[
    type[Exception], ...
] = (
    TimeoutError,
    ConnectionError,
    TransientCollectionError,
    CollectionTimeoutError,
    CollectionNetworkError,
)


def retry_call(
    func: Callable[[], T],
    *,
    policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    retryable_exceptions: tuple[type[Exception], ...] = (
        DEFAULT_RETRYABLE_EXCEPTIONS
    ),
    sleep_func: Callable[[float], None] = time.sleep,
) -> T:
    """
    Execute a callable with bounded retry and exponential backoff.

    Only explicitly classified retryable exceptions are retried.
    Permanent collection errors propagate immediately.
    """

    attempt = 0

    while True:
        try:
            return func()

        except retryable_exceptions:
            if attempt >= policy.max_retries:
                raise

            attempt += 1

            delay = policy.delay_for_retry(
                attempt
            )

            sleep_func(delay)