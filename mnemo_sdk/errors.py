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
    """Raised when the Mnemo API returns an HTTP error response."""

    def __init__(
        self,
        message: str,
        status_code: int,
        code: MnemoErrorCode = MnemoErrorCode.SERVER_ERROR,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message, code=code, details=details)
        self.status_code = status_code

    def __repr__(self) -> str:
        return (
            f"MnemoAPIError(status_code={self.status_code}, "
            f"code={self.code!r}, message={self.message!r})"
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
