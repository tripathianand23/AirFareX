from __future__ import annotations

import pytest

from src.airfare_ml.data.ingestion_errors import (
    AuthenticationError,
    AuthorizationError,
    BadRequestError,
    ClientRequestError,
    CollectionNetworkError,
    CollectionTimeoutError,
    IngestionError,
    IngestionFailure,
    NotFoundError,
    PermanentCollectionError,
    RateLimitError,
    SourceIngestionError,
    TransientCollectionError,
    UpstreamServerError,
    classify_http_status,
)


def test_ingestion_failure_requires_source():
    with pytest.raises(ValueError):
        IngestionFailure(
            source="",
            error_type="ValueError",
            error_message="bad input",
        )


def test_ingestion_failure_requires_error_type():
    with pytest.raises(ValueError):
        IngestionFailure(
            source="sample",
            error_type="",
            error_message="bad input",
        )


def test_ingestion_failure_requires_error_message():
    with pytest.raises(ValueError):
        IngestionFailure(
            source="sample",
            error_type="ValueError",
            error_message="",
        )


def test_source_ingestion_error_is_ingestion_error():
    assert issubclass(
        SourceIngestionError,
        IngestionError,
    )


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (400, BadRequestError),
        (401, AuthenticationError),
        (403, AuthorizationError),
        (404, NotFoundError),
        (408, CollectionTimeoutError),
        (409, ClientRequestError),
        (422, ClientRequestError),
        (429, RateLimitError),
        (500, UpstreamServerError),
        (501, UpstreamServerError),
        (502, UpstreamServerError),
        (503, UpstreamServerError),
        (504, UpstreamServerError),
        (599, UpstreamServerError),
    ],
)
def test_classify_http_status(
    status_code: int,
    expected: type[Exception],
):
    assert classify_http_status(status_code) is expected


@pytest.mark.parametrize(
    "status_code",
    [
        200,
        201,
        204,
        301,
        302,
        304,
    ],
)
def test_classify_http_status_returns_none_for_unclassified_status(
    status_code: int,
):
    assert classify_http_status(status_code) is None


def test_classify_http_status_requires_integer():
    with pytest.raises(TypeError):
        classify_http_status("429")


def test_transient_errors_share_common_base():
    assert issubclass(
        RateLimitError,
        TransientCollectionError,
    )

    assert issubclass(
        UpstreamServerError,
        TransientCollectionError,
    )

    assert issubclass(
        CollectionTimeoutError,
        TransientCollectionError,
    )

    assert issubclass(
        CollectionNetworkError,
        TransientCollectionError,
    )


def test_client_request_error_is_permanent():
    assert issubclass(
        ClientRequestError,
        PermanentCollectionError,
    )


def test_bad_request_error_is_permanent():
    assert issubclass(
        BadRequestError,
        PermanentCollectionError,
    )


def test_authentication_error_is_permanent():
    assert issubclass(
        AuthenticationError,
        PermanentCollectionError,
    )


def test_authorization_error_is_permanent():
    assert issubclass(
        AuthorizationError,
        PermanentCollectionError,
    )


def test_not_found_error_is_permanent():
    assert issubclass(
        NotFoundError,
        PermanentCollectionError,
    )