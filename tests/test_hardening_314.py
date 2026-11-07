"""Regression tests for the 3.1.4 security and correctness patch.

Covers: credential redaction, embed never re-sent once it may have reached the
server, retry-loop fixes (Retry-After parsing and caps, no sleep after the last
attempt, retry_attempts=0, TLS errors), response validation, typed error
attributes, cleartext-URL warning, and the unauthenticated health route.
No test calls the live API; the socket tests use 127.0.0.1 only.
"""

import json
import socket
import threading
import warnings
from email.utils import format_datetime
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
import requests_mock as rm
from urllib3.exceptions import MaxRetryError, NewConnectionError, ProtocolError

import mnemo_sdk
from mnemo_sdk import MnemoAPIError, MnemoClient, MnemoConfig, MnemoErrorCode, MnemoValidationError
from mnemo_sdk.client import _parse_retry_after, _request_never_sent

URL = "https://sdk.test"
KEY = "mnemo_sk_test_" + "zq" * 24  # key-shaped placeholder; not hex, so the secret scan ignores it
EMBED_OK = {"vector_uid": "uid-1", "watermarked_vector": [0.1, 0.2], "created_at": "t", "dimensions": 2}
VERIFY_OK = {"verified": True, "confidence": 0.9, "vector_uid": "uid-1", "policy_ok": True}


def _resp(status_code=200, json_data=None, headers=None, text=None):
    resp = MagicMock()
    resp.status_code = status_code
    if isinstance(json_data, Exception):
        resp.json.side_effect = json_data
    else:
        resp.json.return_value = json_data if json_data is not None else {}
    resp.text = text if text is not None else json.dumps(json_data if not isinstance(json_data, Exception) else "")
    resp.headers = headers or {}
    return resp


def _client(**kw):
    return MnemoClient(api_key=KEY, api_url=URL, **kw)


def _refused():
    """A ConnectionError shaped like requests raises for a refused connection."""
    reason = NewConnectionError(None, "Failed to establish a new connection: [Errno 61] Connection refused")
    return requests.exceptions.ConnectionError(MaxRetryError(None, "/v1/embed", reason=reason))


def _aborted():
    """A ConnectionError shaped like requests raises when the server drops the
    connection after the request was sent."""
    return requests.exceptions.ConnectionError(
        ProtocolError("Connection aborted.", ConnectionResetError(54, "Connection reset by peer"))
    )


# ---------------------------------------------------------------------------
# Credential redaction
# ---------------------------------------------------------------------------

class TestRedaction:

    def test_config_repr_and_str_hide_the_key(self):
        cfg = MnemoConfig(api_key=KEY)
        assert KEY not in repr(cfg)
        assert KEY not in str(cfg)
        assert "api_url=" in repr(cfg)
        assert cfg.api_key == KEY  # the value itself is unchanged

    def test_client_repr_hides_the_key(self):
        client = _client()
        assert KEY not in repr(client)
        assert "sdk.test" in repr(client)

    def test_client_built_from_config_only(self):
        client = MnemoClient(config=MnemoConfig(api_key=KEY, api_url=URL))
        assert KEY not in repr(client)

    def test_missing_key_without_config_is_a_validation_error(self):
        with pytest.raises(MnemoValidationError):
            MnemoClient()

    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    @pytest.mark.parametrize("status", [400, 401, 402, 403, 409, 429, 500, 503])
    def test_api_errors_never_contain_the_key(self, MockSession, _sleep, status):
        MockSession.return_value.post.return_value = _resp(status, {"detail": "nope"})
        with pytest.raises(MnemoAPIError) as ei:
            _client(retry_attempts=1).verify([0.1, 0.2])
        exc = ei.value
        for text in (str(exc), repr(exc), exc.message, json.dumps(exc.details, default=str)):
            assert KEY not in text

    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    def test_network_errors_never_contain_the_key(self, MockSession, _sleep):
        MockSession.return_value.post.side_effect = requests.exceptions.ReadTimeout("read timed out")
        with pytest.raises(MnemoAPIError) as ei:
            _client().embed([0.1, 0.2], model_id="m")
        assert KEY not in str(ei.value) and KEY not in repr(ei.value)

    def test_health_does_not_send_the_key(self):
        client = _client()
        with rm.Mocker() as m:
            m.get(f"{URL}/v1/health", json={"status": "ok", "version": "x", "timestamp": "t"})
            m.get(f"{URL}/v1/usage", json={"embed_count": 0})
            client.health()
            assert "X-API-Key" not in m.request_history[-1].headers
            client.usage()  # authenticated routes still send it
            assert m.request_history[-1].headers["X-API-Key"] == KEY

    def test_py_typed_marker_is_shipped(self):
        assert (Path(mnemo_sdk.__file__).parent / "py.typed").is_file()


# ---------------------------------------------------------------------------
# embed is never re-sent once it may have reached the server
# ---------------------------------------------------------------------------

class TestEmbedRetrySafety:

    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    @pytest.mark.parametrize("failure", [
        requests.exceptions.ReadTimeout("read timed out"),
        requests.exceptions.Timeout("timed out"),
        _aborted(),
        requests.exceptions.ChunkedEncodingError("broken"),
    ])
    def test_ambiguous_failure_sends_exactly_one_request(self, MockSession, sleep, failure):
        s = MockSession.return_value
        s.post.side_effect = [failure, _resp(200, EMBED_OK)]
        with pytest.raises(MnemoAPIError) as ei:
            _client().embed([0.1, 0.2], model_id="m")
        assert s.post.call_count == 1
        sleep.assert_not_called()
        assert ei.value.code == MnemoErrorCode.NETWORK_ERROR
        assert ei.value.status_code == 0
        assert ei.value.retryable is False

    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    @pytest.mark.parametrize("failure", [
        requests.exceptions.ConnectTimeout("connect timed out"),
        _refused(),
    ])
    def test_never_sent_failure_is_retried(self, MockSession, _sleep, failure):
        s = MockSession.return_value
        s.post.side_effect = [failure, _resp(200, EMBED_OK)]
        result = _client().embed([0.1, 0.2], model_id="m")
        assert s.post.call_count == 2
        assert result.vector_uid == "uid-1"

    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    def test_429_is_still_retried(self, MockSession, _sleep):
        s = MockSession.return_value
        s.post.side_effect = [_resp(429, {"detail": "slow down"}, {"Retry-After": "1"}), _resp(200, EMBED_OK)]
        assert _client().embed([0.1, 0.2], model_id="m").vector_uid == "uid-1"
        assert s.post.call_count == 2

    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    @pytest.mark.parametrize("failure", [
        requests.exceptions.ReadTimeout("read timed out"),
        _aborted(),
        requests.exceptions.ChunkedEncodingError("broken"),
    ])
    def test_verify_still_retries_with_the_same_key(self, MockSession, _sleep, failure):
        s = MockSession.return_value
        s.post.side_effect = [failure, _resp(200, VERIFY_OK)]
        assert _client().verify([0.1, 0.2]).vector_uid == "uid-1"
        keys = [c.kwargs["headers"]["Idempotency-Key"] for c in s.post.call_args_list]
        assert len(keys) == 2 and keys[0] == keys[1]


class _SilentServer:
    """127.0.0.1 server that accepts connections, reads the request and never
    answers. Counts the connections it accepted."""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.port = self.sock.getsockname()[1]
        self.accepted = 0
        self._stop = threading.Event()
        self._conns = []
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def _run(self):
        self.sock.settimeout(0.05)
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except OSError:
                continue
            self.accepted += 1
            self._conns.append(conn)

    def close(self):
        self._stop.set()
        self._t.join(timeout=1)
        for c in self._conns:
            c.close()
        self.sock.close()


class TestRealTransport:
    """Real requests/urllib3 exceptions against 127.0.0.1 (no external network)."""

    @patch("mnemo_sdk.client.time.sleep")
    def test_read_timeout_embed_reaches_server_once(self, _sleep):
        server = _SilentServer()
        try:
            client = MnemoClient(api_key=KEY, api_url=f"http://127.0.0.1:{server.port}", timeout=0.3)
            with pytest.raises(MnemoAPIError) as ei:
                client.embed([0.1, 0.2], model_id="m")
            assert ei.value.retryable is False
            assert server.accepted == 1
        finally:
            server.close()

    @patch("mnemo_sdk.client.time.sleep")
    def test_read_timeout_verify_is_retried(self, _sleep):
        server = _SilentServer()
        try:
            client = MnemoClient(api_key=KEY, api_url=f"http://127.0.0.1:{server.port}", timeout=0.3,
                                 retry_attempts=2)
            with pytest.raises(MnemoAPIError) as ei:
                client.verify([0.1, 0.2])
            assert ei.value.retryable is True
            assert ei.value.idempotency_key
            assert server.accepted == 2
        finally:
            server.close()

    def test_refused_connection_is_classified_as_never_sent(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()  # nothing listens on this port now
        with pytest.raises(requests.exceptions.ConnectionError) as ei:
            requests.post(f"http://127.0.0.1:{port}/v1/embed", json={}, timeout=2)
        assert _request_never_sent(ei.value) is True


# ---------------------------------------------------------------------------
# Retry loop
# ---------------------------------------------------------------------------

class TestRetryLoop:

    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    def test_no_sleep_after_the_final_429(self, MockSession, sleep):
        s = MockSession.return_value
        s.post.return_value = _resp(429, {"detail": "slow"}, {"Retry-After": "5"})
        with pytest.raises(MnemoAPIError) as ei:
            _client(retry_attempts=3).verify([0.1])
        assert s.post.call_count == 3
        assert [c.args[0] for c in sleep.call_args_list] == [5.0, 5.0]  # not after the 3rd
        assert ei.value.code == MnemoErrorCode.RATE_LIMIT
        assert ei.value.retry_after == 5.0
        assert ei.value.retryable is True

    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    def test_long_retry_after_is_raised_not_slept(self, MockSession, sleep):
        s = MockSession.return_value
        s.post.return_value = _resp(429, {"detail": "slow"}, {"Retry-After": "3600"})
        with pytest.raises(MnemoAPIError) as ei:
            _client().verify([0.1])
        assert s.post.call_count == 1
        sleep.assert_not_called()
        assert ei.value.retry_after == 3600.0

    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    def test_http_date_retry_after_is_parsed(self, MockSession, sleep):
        when = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=10), usegmt=True)
        s = MockSession.return_value
        s.post.side_effect = [_resp(429, {}, {"Retry-After": when}), _resp(200, VERIFY_OK)]
        _client().verify([0.1])
        waited = sleep.call_args.args[0]
        assert 0.0 <= waited <= 11.0

    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    def test_unparseable_retry_after_falls_back_to_backoff(self, MockSession, sleep):
        s = MockSession.return_value
        s.post.side_effect = [_resp(429, {}, {"Retry-After": "soon"}), _resp(200, VERIFY_OK)]
        _client().verify([0.1])
        sleep.assert_called_once_with(1.0)

    @pytest.mark.parametrize("value,expected", [
        ("0", 0.0), ("2.5", 2.5), ("-3", 0.0), ("", None), ("garbage", None), (None, None),
        ("Wed, 21 Oct 2015 07:28:00 GMT", 0.0),  # in the past
    ])
    def test_parse_retry_after(self, value, expected):
        assert _parse_retry_after(value) == expected

    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    @pytest.mark.parametrize("attempts", [0, -1])
    def test_retry_attempts_below_one_still_sends_one_request(self, MockSession, _sleep, attempts):
        s = MockSession.return_value
        s.post.return_value = _resp(200, VERIFY_OK)
        assert _client(retry_attempts=attempts).verify([0.1]) is not None
        assert s.post.call_count == 1

    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    def test_tls_errors_are_not_retried(self, MockSession, sleep):
        s = MockSession.return_value
        s.post.side_effect = requests.exceptions.SSLError("certificate verify failed")
        with pytest.raises(MnemoAPIError) as ei:
            _client().verify([0.1])
        assert s.post.call_count == 1
        sleep.assert_not_called()
        assert ei.value.code == MnemoErrorCode.NETWORK_ERROR
        assert ei.value.retryable is False


# ---------------------------------------------------------------------------
# Response validation and input validation
# ---------------------------------------------------------------------------

class TestValidation:

    @patch("mnemo_sdk.client.requests.Session")
    def test_non_json_success_body_is_an_api_error(self, MockSession):
        MockSession.return_value.post.return_value = _resp(
            200, ValueError("Expecting value"), text="<html>proxy</html>")
        with pytest.raises(MnemoAPIError) as ei:
            _client().embed([0.1], model_id="m")
        assert ei.value.code == MnemoErrorCode.SERVER_ERROR
        assert "Invalid JSON" in ei.value.message

    @patch("mnemo_sdk.client.requests.Session")
    def test_non_object_success_body_is_an_api_error(self, MockSession):
        MockSession.return_value.post.return_value = _resp(200, ["not", "an", "object"])
        with pytest.raises(MnemoAPIError):
            _client().verify([0.1])

    @patch("mnemo_sdk.client.requests.Session")
    def test_embed_response_missing_fields_is_an_api_error(self, MockSession):
        MockSession.return_value.post.return_value = _resp(200, {"vector_uid": "u"})
        with pytest.raises(MnemoAPIError) as ei:
            _client().embed([0.1], model_id="m")
        assert "watermarked_vector" in ei.value.message

    @patch("mnemo_sdk.client.requests.Session")
    def test_verified_response_missing_confidence_is_an_api_error(self, MockSession):
        MockSession.return_value.post.return_value = _resp(200, {"verified": True, "vector_uid": "u"})
        with pytest.raises(MnemoAPIError):
            _client().verify([0.1])

    @patch("mnemo_sdk.client.requests.Session")
    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_vector_is_refused_before_sending(self, MockSession, bad):
        s = MockSession.return_value
        with pytest.raises(MnemoValidationError):
            _client().embed([0.1, bad], model_id="m")
        with pytest.raises(MnemoValidationError):
            _client().verify([bad])
        s.post.assert_not_called()

    def test_http_url_to_remote_host_warns(self):
        with pytest.warns(UserWarning, match="unencrypted"):
            MnemoClient(api_key=KEY, api_url="http://api.example.com")

    @pytest.mark.parametrize("url", ["https://api.trymnemo.com", "http://localhost:8000", "http://127.0.0.1:8000"])
    def test_https_and_localhost_do_not_warn(self, url):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            MnemoClient(api_key=KEY, api_url=url)


# ---------------------------------------------------------------------------
# Typed error attributes
# ---------------------------------------------------------------------------

class TestTypedErrors:

    @patch("mnemo_sdk.client.time.sleep")
    @patch("mnemo_sdk.client.requests.Session")
    @pytest.mark.parametrize("status,body,code,server_code,retryable", [
        (402, {"code": "insufficient_credits"}, MnemoErrorCode.QUOTA_EXCEEDED, "insufficient_credits", False),
        (409, {"code": "request_in_progress"}, MnemoErrorCode.SERVER_ERROR, "request_in_progress", True),
        (409, {"code": "idempotency_key_reused"}, MnemoErrorCode.SERVER_ERROR, "idempotency_key_reused", False),
        (409, {"detail": "Duplicate request_id"}, MnemoErrorCode.SERVER_ERROR, None, False),
        (503, {"code": "verification_unavailable", "message": "No credit was consumed"},
         MnemoErrorCode.SERVER_ERROR, "verification_unavailable", True),
        (400, {"detail": {"code": "idempotency_key_invalid", "message": "bad key"}},
         MnemoErrorCode.INVALID_INPUT, "idempotency_key_invalid", False),
        (422, {"detail": [{"loc": ["body", "vector"], "msg": "field required"}]},
         MnemoErrorCode.INVALID_INPUT, None, False),
        (401, {"detail": "Authentication required"}, MnemoErrorCode.UNAUTHORIZED, None, False),
        (500, {"detail": "Internal Server Error"}, MnemoErrorCode.SERVER_ERROR, None, None),
    ])
    def test_error_attributes(self, MockSession, _sleep, status, body, code, server_code, retryable):
        MockSession.return_value.post.return_value = _resp(status, body)
        with pytest.raises(MnemoAPIError) as ei:
            _client(retry_attempts=1).verify([0.1], idempotency_key="my-key-1")
        exc = ei.value
        assert exc.status_code == status
        assert exc.code == code
        assert exc.server_code == server_code
        assert exc.retryable is retryable
        assert exc.idempotency_key == "my-key-1"

    @patch("mnemo_sdk.client.requests.Session")
    def test_generated_verify_key_is_exposed_on_error(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _resp(409, {"code": "request_in_progress"})
        with pytest.raises(MnemoAPIError) as ei:
            _client(retry_attempts=1).verify([0.1])
        sent = s.post.call_args.kwargs["headers"]["Idempotency-Key"]
        assert ei.value.idempotency_key == sent

    @patch("mnemo_sdk.client.requests.Session")
    def test_embed_errors_have_no_idempotency_key(self, MockSession):
        MockSession.return_value.post.return_value = _resp(400, {"detail": "bad"})
        with pytest.raises(MnemoAPIError) as ei:
            _client().embed([0.1], model_id="m")
        assert ei.value.idempotency_key is None

    def test_constructor_stays_backward_compatible(self):
        exc = MnemoAPIError("m", 418, MnemoErrorCode.SERVER_ERROR, {"x": 1})
        assert (exc.message, exc.status_code, exc.details) == ("m", 418, {"x": 1})
        assert exc.server_code is None and exc.retry_after is None and exc.retryable is None
        assert isinstance(exc, mnemo_sdk.MnemoException)
