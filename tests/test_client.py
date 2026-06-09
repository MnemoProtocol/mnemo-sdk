"""Tests for MnemoClient HTTP interactions."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from mnemo_sdk import MnemoClient
from mnemo_sdk.errors import MnemoAPIError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_numpy() -> bool:
    try:
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False

def _mock_response(status_code=200, json_data=None, headers=None):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = json.dumps(json_data or {})
    resp.headers = headers or {}
    return resp


EMBED_RESPONSE = {
    "vector_uid": "uid-abc-123",
    "watermarked_vector": [0.11, 0.22, 0.33],
    "created_at": "2026-01-01T00:00:00Z",
    "dimensions": 3,
}

VERIFY_RESPONSE = {
    "verified": True,
    "confidence": 0.98,
    "vector_uid": "uid-abc-123",
    "policy_ok": True,
}

VERIFY_NOT_FOUND_RESPONSE = {
    "verified": False,
    "confidence": 0.12,
    "policy_ok": False,
}

HEALTH_RESPONSE = {"status": "ok", "version": "3.0.0"}

USAGE_RESPONSE = {"embeds": 100, "verifications": 50, "quota_remaining": 9900}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMnemoClient:

    @patch("mnemo_sdk.client.requests.Session")
    def test_embed_sends_correct_request(self, MockSession, mock_api_url, mock_api_key):
        session_instance = MockSession.return_value
        session_instance.post.return_value = _mock_response(200, EMBED_RESPONSE)

        client = MnemoClient(api_key=mock_api_key, api_url=mock_api_url)
        result = client.embed(vector=[0.1, 0.2, 0.3], model_id="text-embedding-3-small")

        session_instance.post.assert_called_once()
        call_args = session_instance.post.call_args
        assert call_args[0][0] == f"{mock_api_url}/v1/embed"

        body = call_args[1]["json"]
        assert body["vector"] == [0.1, 0.2, 0.3]
        assert body["model_id"] == "text-embedding-3-small"
        assert result.vector_uid == "uid-abc-123"
        assert result.watermarked_vector == [0.11, 0.22, 0.33]

    @patch("mnemo_sdk.client.requests.Session")
    def test_verify_detected_returns_result(self, MockSession, mock_api_url, mock_api_key):
        session_instance = MockSession.return_value
        session_instance.post.return_value = _mock_response(200, VERIFY_RESPONSE)

        client = MnemoClient(api_key=mock_api_key, api_url=mock_api_url)
        result = client.verify(vector=[0.11, 0.22, 0.33])

        session_instance.post.assert_called_once()
        call_args = session_instance.post.call_args
        assert call_args[0][0] == f"{mock_api_url}/v1/verify"

        body = call_args[1]["json"]
        assert body["vector"] == [0.11, 0.22, 0.33]
        assert result is not None
        assert result.verified is True
        assert result.confidence == 0.98
        assert result.vector_uid == "uid-abc-123"

    @patch("mnemo_sdk.client.requests.Session")
    def test_verify_not_detected_returns_none(self, MockSession, mock_api_url, mock_api_key):
        session_instance = MockSession.return_value
        session_instance.post.return_value = _mock_response(200, VERIFY_NOT_FOUND_RESPONSE)

        client = MnemoClient(api_key=mock_api_key, api_url=mock_api_url)
        result = client.verify(vector=[0.5, 0.6, 0.7])

        assert result is None

    @patch("mnemo_sdk.client.requests.Session")
    def test_verify_invariant_violation_raises(self, MockSession, mock_api_url, mock_api_key):
        """Server says verified=True but omits vector_uid — SDK must reject."""
        bad_response = {"verified": True, "confidence": 0.95, "policy_ok": True}
        session_instance = MockSession.return_value
        session_instance.post.return_value = _mock_response(200, bad_response)

        client = MnemoClient(api_key=mock_api_key, api_url=mock_api_url)
        with pytest.raises(MnemoAPIError) as exc_info:
            client.verify(vector=[0.1, 0.2, 0.3])

        assert "Invariant violation" in exc_info.value.message

    @patch("mnemo_sdk.client.requests.Session")
    def test_health_check(self, MockSession, mock_api_url, mock_api_key):
        session_instance = MockSession.return_value
        session_instance.get.return_value = _mock_response(200, HEALTH_RESPONSE)

        client = MnemoClient(api_key=mock_api_key, api_url=mock_api_url)
        result = client.health()

        session_instance.get.assert_called_once()
        call_args = session_instance.get.call_args
        assert call_args[0][0] == f"{mock_api_url}/v1/health"
        assert result["status"] == "ok"

    @patch("mnemo_sdk.client.requests.Session")
    def test_usage(self, MockSession, mock_api_url, mock_api_key):
        session_instance = MockSession.return_value
        session_instance.get.return_value = _mock_response(200, USAGE_RESPONSE)

        client = MnemoClient(api_key=mock_api_key, api_url=mock_api_url)
        result = client.usage()

        session_instance.get.assert_called_once()
        call_args = session_instance.get.call_args
        assert call_args[0][0] == f"{mock_api_url}/v1/usage"
        assert result["embeds"] == 100

    @patch("mnemo_sdk.client.requests.Session")
    def test_api_key_header(self, MockSession, mock_api_url, mock_api_key):
        session_instance = MockSession.return_value
        session_instance.post.return_value = _mock_response(200, EMBED_RESPONSE)

        client = MnemoClient(api_key=mock_api_key, api_url=mock_api_url)
        # headers.update is called in __init__
        session_instance.headers.update.assert_called_once()
        headers = session_instance.headers.update.call_args[0][0]
        assert headers["X-API-Key"] == mock_api_key
        assert "mnemo-protocol/" in headers["User-Agent"]

    @patch("mnemo_sdk.client.requests.Session")
    def test_error_handling(self, MockSession, mock_api_url, mock_api_key):
        session_instance = MockSession.return_value
        error_body = {"error": "Invalid vector dimensions"}
        session_instance.post.return_value = _mock_response(400, error_body)

        client = MnemoClient(api_key=mock_api_key, api_url=mock_api_url)
        with pytest.raises(MnemoAPIError) as exc_info:
            client.embed(vector=[0.1], model_id="test-model")

        assert exc_info.value.status_code == 400
        assert "Invalid vector dimensions" in exc_info.value.message

    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    def test_retry_on_429(self, MockSession, mock_sleep, mock_api_url, mock_api_key):
        session_instance = MockSession.return_value

        rate_limit_resp = _mock_response(429, {"error": "Rate limited"}, {"Retry-After": "1"})
        ok_resp = _mock_response(200, EMBED_RESPONSE)
        session_instance.post.side_effect = [rate_limit_resp, ok_resp]

        client = MnemoClient(api_key=mock_api_key, api_url=mock_api_url)
        result = client.embed(vector=[0.1, 0.2, 0.3], model_id="test-model")

        assert session_instance.post.call_count == 2
        mock_sleep.assert_called_once_with(1.0)
        assert result.vector_uid == "uid-abc-123"

    @patch("mnemo_sdk.client.requests.Session")
    def test_serialize_list(self, MockSession, mock_api_url, mock_api_key):
        session_instance = MockSession.return_value
        session_instance.post.return_value = _mock_response(200, EMBED_RESPONSE)

        client = MnemoClient(api_key=mock_api_key, api_url=mock_api_url)
        client.embed(vector=[1.0, 2.0, 3.0], model_id="test-model")

        body = session_instance.post.call_args[1]["json"]
        assert body["vector"] == [1.0, 2.0, 3.0]
        assert isinstance(body["vector"], list)

    @pytest.mark.skipif(not _has_numpy(), reason="numpy not installed")
    @patch("mnemo_sdk.client.requests.Session")
    def test_serialize_numpy(self, MockSession, mock_api_url, mock_api_key):
        import numpy as np

        session_instance = MockSession.return_value
        session_instance.post.return_value = _mock_response(200, EMBED_RESPONSE)

        client = MnemoClient(api_key=mock_api_key, api_url=mock_api_url)
        arr = np.array([1.0, 2.0, 3.0])
        client.embed(vector=arr, model_id="test-model")

        body = session_instance.post.call_args[1]["json"]
        assert body["vector"] == [1.0, 2.0, 3.0]
        assert isinstance(body["vector"], list)
