from __future__ import annotations


class IngestionError(Exception):
    """Base exception for airfare ingestion failures."""


class IngestionFailure(IngestionError):
    """Structured ingestion failure."""

    def __init__(
        self,
        *,
        source: str,
        error_type: str,
        error_message: str,
    ) -> None:
        if not source.strip():
            raise ValueError("source must not be empty.")

        if not error_type.strip():
            raise ValueError("error_type must not be empty.")

        if not error_message.strip():
            raise ValueError("error_message must not be empty.")

        self.source = source
        self.error_type = error_type
        self.error_message = error_message

        super().__init__(error_message)


class SourceIngestionError(IngestionError):
    """Raised when a source cannot be ingested."""


class TransientCollectionError(SourceIngestionError):
    """
    Error that may succeed if the collection operation is retried.
    """


class PermanentCollectionError(SourceIngestionError):
    """
    Error that should not be retried automatically.
    """


class RateLimitError(TransientCollectionError):
    """The source temporarily rate-limited the client."""


class UpstreamServerError(TransientCollectionError):
    """The source or upstream service returned a server error."""


class CollectionTimeoutError(TransientCollectionError):
    """The collection request timed out."""


class CollectionNetworkError(TransientCollectionError):
    """A temporary network failure occurred."""

class ClientRequestError(PermanentCollectionError):
    """The source rejected the request with a non-retryable 4xx error."""

class BadRequestError(PermanentCollectionError):
    """The source rejected the request as invalid."""


class AuthenticationError(PermanentCollectionError):
    """Authentication failed."""


class AuthorizationError(PermanentCollectionError):
    """Authorization failed."""


class NotFoundError(PermanentCollectionError):
    """The requested resource was not found."""


def classify_http_status(
    status_code: int,
) -> type[SourceIngestionError] | None:
    """
    Classify an HTTP status code into a collection error type.

    Returns None for successful or otherwise unclassified responses.
    """

    if not isinstance(status_code, int):
        raise TypeError("status_code must be an integer.")

    if status_code == 408:
        return CollectionTimeoutError

    if status_code == 429:
        return RateLimitError

    if 500 <= status_code <= 599:
        return UpstreamServerError

    if status_code == 400:
        return BadRequestError

    if status_code == 401:
        return AuthenticationError

    if status_code == 403:
        return AuthorizationError

    if status_code == 404:
        return NotFoundError

    if 400 <= status_code <= 499:
        return ClientRequestError

    return None