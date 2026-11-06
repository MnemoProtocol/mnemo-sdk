"""Error types for the Mnemo SDK."""

from enum import Enum
from typing import Any, Optional


class MnemoErrorCode(Enum):
    """Standard error codes returned by the Mnemo API."""

    SUCCESS = "SUCCESS"
    INVALID_INPUT = "INVALID_INPUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    SERVER_ERROR = "SERVER_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    NOT_FOUND = "NOT_FOUND"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    UNAUTHORIZED = "UNAUTHORIZED"


class MnemoException(Exception):
    """Base exception for all Mnemo SDK errors."""

    def __init__(
        self,
        message: str,
        code: MnemoErrorCode = MnemoErrorCode.SERVER_ERROR,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def __repr__(self) -> str:
        return f"MnemoException(code={self.code!r}, message={self.message!r})"


class MnemoAPIError(MnemoException):
    """Raised when the Mnemo API returns an HTTP error response, or when a
    request could not be completed (``status_code == 0``, ``NETWORK_ERROR``).

    Attributes:
        status_code: HTTP status, or ``0`` when no HTTP response was received.
        code: SDK error category (``MnemoErrorCode``).
        message: Human-readable description.
        details: Structured part of the error body, if any.
        server_code: The API's own error code from the response body (for
            example ``"insufficient_credits"``, ``"request_in_progress"`` or
            ``"verification_unavailable"``), or ``None`` when the body has none.
        retry_after: Seconds the server asked the client to wait
            (``Retry-After``), or ``None``.
        retryable: ``True`` when calling again is known to be safe and may
            succeed; ``False`` when it is known not to help, or when the
            outcome of a non-idempotent request is unknown; ``None`` when the
            SDK cannot tell.
        idempotency_key: For ``verify()`` errors, the ``Idempotency-Key`` that
            was sent. Pass it as ``verify(..., idempotency_key=...)`` to retry
            the same verification without it being counted twice.
    """

    def __init__(
        self,
        message: str,
        status_code: int,
        code: MnemoErrorCode = MnemoErrorCode.SERVER_ERROR,
        details: Optional[Any] = None,
        *,
        server_code: Optional[str] = None,
        retry_after: Optional[float] = None,
        retryable: Optional[bool] = None,
        idempotency_key: Optional[str] = None,
    ) -> None:
        super().__init__(message, code=code, details=details)
        self.status_code = status_code
        self.server_code = server_code
        self.retry_after = retry_after
        self.retryable = retryable
        self.idempotency_key = idempotency_key

    def __repr__(self) -> str:
        extra = ""
        if self.server_code is not None:
            extra += f", server_code={self.server_code!r}"
        if self.retryable is not None:
            extra += f", retryable={self.retryable!r}"
        return (
            f"MnemoAPIError(status_code={self.status_code}, "
            f"code={self.code!r}, message={self.message!r}{extra})"
        )


class MnemoValidationError(MnemoException):
    """Raised when input validation fails before making an API request."""

    def __init__(
        self,
        message: str,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message, code=MnemoErrorCode.INVALID_INPUT, details=details)

    def __repr__(self) -> str:
        return f"MnemoValidationError(message={self.message!r})"
