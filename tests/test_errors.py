"""Tests for Mnemo SDK error types."""

import pytest

from mnemo_sdk.errors import (
    MnemoAPIError,
    MnemoErrorCode,
    MnemoException,
    MnemoValidationError,
)


class TestMnemoErrorCode:

    def test_error_codes(self):
        assert MnemoErrorCode.SUCCESS.value == "SUCCESS"
        assert MnemoErrorCode.INVALID_INPUT.value == "INVALID_INPUT"
        assert MnemoErrorCode.NETWORK_ERROR.value == "NETWORK_ERROR"
        assert MnemoErrorCode.SERVER_ERROR.value == "SERVER_ERROR"
        assert MnemoErrorCode.RATE_LIMIT.value == "RATE_LIMIT"
        assert MnemoErrorCode.NOT_FOUND.value == "NOT_FOUND"
        assert MnemoErrorCode.VERIFICATION_FAILED.value == "VERIFICATION_FAILED"
        assert MnemoErrorCode.QUOTA_EXCEEDED.value == "QUOTA_EXCEEDED"
        assert MnemoErrorCode.UNAUTHORIZED.value == "UNAUTHORIZED"


class TestMnemoException:

    def test_mnemo_exception(self):
        exc = MnemoException("something went wrong")
        assert str(exc) == "something went wrong"
        assert exc.message == "something went wrong"
        assert exc.code == MnemoErrorCode.SERVER_ERROR
        assert exc.details is None
        assert isinstance(exc, Exception)

    def test_mnemo_exception_with_details(self):
        exc = MnemoException(
            "bad input",
            code=MnemoErrorCode.INVALID_INPUT,
            details={"field": "vector"},
        )
        assert exc.code == MnemoErrorCode.INVALID_INPUT
        assert exc.details == {"field": "vector"}


class TestMnemoAPIError:

    def test_api_error_with_status(self):
        exc = MnemoAPIError(
            message="Not found",
            status_code=404,
            code=MnemoErrorCode.NOT_FOUND,
        )
        assert exc.status_code == 404
        assert exc.code == MnemoErrorCode.NOT_FOUND
        assert exc.message == "Not found"
        assert isinstance(exc, MnemoException)
        assert isinstance(exc, Exception)

    def test_api_error_repr(self):
        exc = MnemoAPIError(
            message="Server error",
            status_code=500,
            code=MnemoErrorCode.SERVER_ERROR,
        )
        r = repr(exc)
        assert "500" in r
        assert "SERVER_ERROR" in r


class TestMnemoValidationError:

    def test_validation_error(self):
        exc = MnemoValidationError(
            message="Vector must not be empty",
            details={"field": "vector"},
        )
        assert exc.message == "Vector must not be empty"
        assert exc.code == MnemoErrorCode.INVALID_INPUT
        assert exc.details == {"field": "vector"}
        assert isinstance(exc, MnemoException)
