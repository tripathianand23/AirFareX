import pytest

from src.airfare_ml.data.retry import (
    RetryPolicy,
    retry_call,
)

from src.airfare_ml.data.ingestion_errors import (
    AuthenticationError,
    RateLimitError,
    UpstreamServerError,
)

from src.airfare_ml.data.ingestion_errors import (
    CollectionNetworkError,
    CollectionTimeoutError,
    TransientCollectionError,
)

DEFAULT_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    TimeoutError,
    ConnectionError,
    TransientCollectionError,
    CollectionTimeoutError,
    CollectionNetworkError,
)

def test_retry_policy_defaults():
    policy = RetryPolicy()

    assert policy.max_retries == 3
    assert policy.initial_delay_seconds == 1.0
    assert policy.backoff_multiplier == 2.0
    assert policy.max_delay_seconds == 30.0
    assert policy.max_attempts == 4


def test_retry_policy_rejects_negative_retries():
    with pytest.raises(ValueError):
        RetryPolicy(max_retries=-1)


def test_retry_policy_rejects_negative_delay():
    with pytest.raises(ValueError):
        RetryPolicy(initial_delay_seconds=-1)


def test_retry_policy_requires_valid_backoff_multiplier():
    with pytest.raises(ValueError):
        RetryPolicy(backoff_multiplier=0.5)


def test_retry_policy_rejects_negative_max_delay():
    with pytest.raises(ValueError):
        RetryPolicy(max_delay_seconds=-1)


def test_retry_delay_uses_exponential_backoff():
    policy = RetryPolicy(
        max_retries=3,
        initial_delay_seconds=1,
        backoff_multiplier=2,
    )

    assert policy.delay_for_retry(1) == 1
    assert policy.delay_for_retry(2) == 2
    assert policy.delay_for_retry(3) == 4


def test_retry_delay_is_capped():
    policy = RetryPolicy(
        max_retries=5,
        initial_delay_seconds=5,
        backoff_multiplier=2,
        max_delay_seconds=10,
    )

    assert policy.delay_for_retry(1) == 5
    assert policy.delay_for_retry(2) == 10
    assert policy.delay_for_retry(3) == 10


def test_retry_delay_requires_positive_retry_number():
    policy = RetryPolicy()

    with pytest.raises(ValueError):
        policy.delay_for_retry(0)


def test_successful_call_is_not_retried():
    calls = []
    sleeps = []

    def func():
        calls.append(1)
        return "success"

    result = retry_call(
        func,
        sleep_func=sleeps.append,
    )

    assert result == "success"
    assert len(calls) == 1
    assert sleeps == []


def test_timeout_is_retried():
    calls = []
    sleeps = []

    def func():
        calls.append(1)

        if len(calls) < 3:
            raise TimeoutError("temporary timeout")

        return "success"

    result = retry_call(
        func,
        policy=RetryPolicy(
            max_retries=3,
            initial_delay_seconds=1,
            backoff_multiplier=2,
        ),
        sleep_func=sleeps.append,
    )

    assert result == "success"
    assert len(calls) == 3
    assert sleeps == [1, 2]


def test_connection_error_is_retried():
    calls = []

    def func():
        calls.append(1)

        if len(calls) == 1:
            raise ConnectionError("temporary connection failure")

        return "success"

    result = retry_call(
        func,
        policy=RetryPolicy(
            max_retries=2,
            initial_delay_seconds=1,
        ),
        sleep_func=lambda _: None,
    )

    assert result == "success"
    assert len(calls) == 2


def test_non_retryable_exception_is_raised_immediately():
    calls = []
    sleeps = []

    def func():
        calls.append(1)
        raise ValueError("invalid payload")

    with pytest.raises(ValueError, match="invalid payload"):
        retry_call(
            func,
            policy=RetryPolicy(max_retries=3),
            sleep_func=sleeps.append,
        )

    assert len(calls) == 1
    assert sleeps == []


def test_retry_exhaustion_raises_original_exception():
    calls = []
    sleeps = []

    def func():
        calls.append(1)
        raise TimeoutError("persistent timeout")

    with pytest.raises(TimeoutError, match="persistent timeout"):
        retry_call(
            func,
            policy=RetryPolicy(
                max_retries=2,
                initial_delay_seconds=1,
                backoff_multiplier=2,
            ),
            sleep_func=sleeps.append,
        )

    assert len(calls) == 3
    assert sleeps == [1, 2]


def test_custom_retryable_exception():
    calls = []

    def func():
        calls.append(1)

        if len(calls) == 1:
            raise RuntimeError("temporary failure")

        return "success"

    result = retry_call(
        func,
        policy=RetryPolicy(max_retries=1),
        retryable_exceptions=(RuntimeError,),
        sleep_func=lambda _: None,
    )

    assert result == "success"
    assert len(calls) == 2

def test_retry_rate_limit_error():
    attempts = []

    def operation():
        attempts.append(1)

        if len(attempts) < 3:
            raise RateLimitError("rate limited")

        return "success"

    result = retry_call(
        operation,
        policy=RetryPolicy(
            max_retries=2,
            initial_delay_seconds=0,
        ),
    )

    assert result == "success"
    assert len(attempts) == 3


def test_retry_upstream_server_error():
    attempts = []

    def operation():
        attempts.append(1)

        if len(attempts) < 2:
            raise UpstreamServerError("server unavailable")

        return "success"

    result = retry_call(
        operation,
        policy=RetryPolicy(
            max_retries=1,
            initial_delay_seconds=0,
        ),
    )

    assert result == "success"
    assert len(attempts) == 2


def test_authentication_error_is_not_retried():
    attempts = []

    def operation():
        attempts.append(1)
        raise AuthenticationError("invalid credentials")

    with pytest.raises(AuthenticationError):
        retry_call(
            operation,
            policy=RetryPolicy(
                max_retries=5,
                initial_delay_seconds=0,
            ),
        )

    assert len(attempts) == 1    