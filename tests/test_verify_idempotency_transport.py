"""verify() idempotency transport.

`POST /v1/verify` is the billed operation. The client retries on a rate limit, a
connection error and a timeout; a timeout in particular can mean the server
completed the request and only the response was lost. These tests pin that:

  * every verify() call carries ONE `Idempotency-Key`, resolved before the first
    attempt and sent unchanged on every internal retry of that call;
  * the generated key is a uuid4 and is never shared between two calls;
  * a caller-supplied key is sent verbatim, on the first attempt and on retries;
  * an unusable caller key is refused before any request is made;
  * embed() is unchanged (no idempotency header).
"""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
import requests

from mnemo_sdk import MnemoAPIError, MnemoClient, MnemoValidationError

URL = "https://sdk.test"
HEADER = "Idempotency-Key"

VERIFY_OK = {"verified": True, "confidence": 0.98, "vector_uid": "uid-1", "policy_ok": True}
EMBED_OK = {"vector_uid": "uid-1", "watermarked_vector": [0.1, 0.2], "created_at": "t", "dimensions": 2}


def _resp(status_code=200, json_data=None, headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = json.dumps(json_data or {})
    resp.headers = headers or {}
    return resp


def _client(**kw):
    return MnemoClient(api_key="k", api_url=URL, **kw)


def _sent_keys(session):
    """The Idempotency-Key of every POST attempt, in order."""
    return [c.kwargs.get("headers", {}).get(HEADER) for c in session.post.call_args_list]


def _is_uuid4(value) -> bool:
    try:
        return uuid.UUID(value).version == 4 and str(uuid.UUID(value)) == value
    except (ValueError, AttributeError, TypeError):
        return False


class TestGeneratedKey:

    @patch("mnemo_sdk.client.requests.Session")
    def test_single_attempt_sends_a_uuid4_key(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _resp(200, VERIFY_OK)
        _client().verify([0.1, 0.2])
        keys = _sent_keys(s)
        assert len(keys) == 1
        assert _is_uuid4(keys[0])

    @pytest.mark.parametrize("failure", [
        requests.exceptions.Timeout("read timed out"),
        requests.exceptions.ConnectionError("connection reset"),
    ], ids=["timeout", "connection_error"])
    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    def test_same_key_on_retry_after_lost_response(self, MockSession, _sleep, failure):
        s = MockSession.return_value
        s.post.side_effect = [failure, _resp(200, VERIFY_OK)]
        result = _client().verify([0.1, 0.2])
        assert result is not None and result.vector_uid == "uid-1"
        keys = _sent_keys(s)
        assert len(keys) == 2
        assert _is_uuid4(keys[0])
        assert keys[1] == keys[0], "the retry must carry the key of the first attempt"

    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    def test_same_key_across_every_attempt(self, MockSession, _sleep):
        s = MockSession.return_value
        s.post.side_effect = [
            requests.exceptions.Timeout("t"),
            _resp(429, {"error": "Rate limited"}, {"Retry-After": "0"}),
            _resp(200, VERIFY_OK),
        ]
        _client(retry_attempts=3).verify([0.1, 0.2])
        keys = _sent_keys(s)
        assert len(keys) == 3
        assert len(set(keys)) == 1 and _is_uuid4(keys[0])

    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    def test_same_key_when_every_attempt_fails(self, MockSession, _sleep):
        s = MockSession.return_value
        s.post.side_effect = requests.exceptions.Timeout("t")
        with pytest.raises(MnemoAPIError):
            _client(retry_attempts=3).verify([0.1, 0.2])
        keys = _sent_keys(s)
        assert len(keys) == 3
        assert len(set(keys)) == 1 and _is_uuid4(keys[0])

    @patch("mnemo_sdk.client.requests.Session")
    def test_two_calls_never_share_a_generated_key(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _resp(200, VERIFY_OK)
        c = _client()
        c.verify([0.1, 0.2])
        c.verify([0.1, 0.2])
        keys = _sent_keys(s)
        assert len(keys) == 2 and keys[0] != keys[1]

    @patch("mnemo_sdk.client.requests.Session")
    def test_key_is_a_header_not_a_body_field(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _resp(200, VERIFY_OK)
        _client().verify([0.1, 0.2])
        assert set(s.post.call_args.kwargs["json"]) == {"vector"}


class TestCallerSuppliedKey:

    @patch("mnemo_sdk.client.requests.Session")
    def test_caller_key_is_sent_verbatim(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _resp(200, VERIFY_OK)
        _client().verify([0.1, 0.2], idempotency_key="order-42/verify")
        assert _sent_keys(s) == ["order-42/verify"]

    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    def test_caller_key_is_preserved_on_retry(self, MockSession, _sleep):
        s = MockSession.return_value
        s.post.side_effect = [requests.exceptions.Timeout("t"), _resp(200, VERIFY_OK)]
        _client().verify([0.1, 0.2], idempotency_key="order-42/verify")
        assert _sent_keys(s) == ["order-42/verify", "order-42/verify"]

    @pytest.mark.parametrize("bad", ["", "   ", 42, b"bytes", ["k"]])
    def test_unusable_key_is_refused_before_any_request(self, bad):
        with patch("mnemo_sdk.client.requests.Session") as MockSession:
            s = MockSession.return_value
            with pytest.raises(MnemoValidationError):
                _client().verify([0.1, 0.2], idempotency_key=bad)
            s.post.assert_not_called()


class TestEmbedUnchanged:

    @patch("mnemo_sdk.client.requests.Session")
    def test_embed_sends_no_idempotency_header(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _resp(200, EMBED_OK)
        _client().embed([0.1, 0.2], model_id="m")
        assert "headers" not in s.post.call_args.kwargs


class TestOnTheWire:
    """Through a real `requests.Session`: what actually leaves the client."""

    def test_retry_after_timeout_carries_the_same_header(self):
        requests_mock = pytest.importorskip("requests_mock")
        with requests_mock.Mocker() as m, patch("mnemo_sdk.client.time.sleep"):
            m.post(f"{URL}/v1/verify", [
                {"exc": requests.exceptions.ConnectTimeout},
                {"json": VERIFY_OK, "status_code": 200},
            ])
            result = _client().verify([0.1, 0.2])
            assert result is not None and result.verified is True
            # requests-mock records the attempt that raised as well as the one that answered.
            sent = [r.headers.get(HEADER) for r in m.request_history]
            assert len(sent) == 2
            assert _is_uuid4(sent[0]) and sent[1] == sent[0]
            # the per-request header is added to the session headers, not instead of them
            assert all(r.headers.get("X-API-Key") == "k" for r in m.request_history)

    def test_caller_key_reaches_the_wire_unchanged(self):
        requests_mock = pytest.importorskip("requests_mock")
        with requests_mock.Mocker() as m, patch("mnemo_sdk.client.time.sleep"):
            m.post(f"{URL}/v1/verify", [
                {"exc": requests.exceptions.ConnectionError},
                {"json": VERIFY_OK, "status_code": 200},
            ])
            _client().verify([0.1, 0.2], idempotency_key="order-42/verify")
            assert [r.headers.get(HEADER) for r in m.request_history] == ["order-42/verify"] * 2
