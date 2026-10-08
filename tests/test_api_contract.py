"""Contract guards: default host, error-body parsing, 402 handling, version.

Mirrors the live MnemoV2 contract for API-key calls:
* errors are ``{"detail": ...}`` (FastAPI) or a bare ``{"code": ...}`` (billing);
* an API key whose plan has no verifications left gets a plain
  ``402 {"code": "insufficient_credits"}`` — never x402, nothing to pay.
"""

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import mnemo_sdk
from mnemo_sdk import MnemoClient, MnemoConfig
from mnemo_sdk import client as client_mod
from mnemo_sdk.errors import MnemoAPIError, MnemoErrorCode

REPO_ROOT = Path(__file__).resolve().parent.parent


def _mock_response(status_code, json_data=None, headers=None, text=None):
    resp = MagicMock()
    resp.status_code = status_code
    if json_data is None and text is not None:
        resp.json.side_effect = ValueError("not json")
        resp.text = text
    else:
        resp.json.return_value = json_data
        resp.text = json.dumps(json_data)
    resp.headers = headers or {}
    return resp


# ---------------------------------------------------------------------------
# Default host
# ---------------------------------------------------------------------------

def test_default_api_url_is_public_host():
    client = MnemoClient(api_key="k")
    assert client._api_url == "https://api.trymnemo.com"
    assert MnemoConfig(api_key="k").api_url == "https://api.trymnemo.com"


def test_no_third_party_host_in_public_files():
    """`mnemo.ai` is a third-party domain and must not appear in shipped files."""
    candidates = [
        *sorted((REPO_ROOT / "mnemo_sdk").glob("*.py")),
        REPO_ROOT / "README.md",
        REPO_ROOT / "llms.txt",
        REPO_ROOT / "agent-manifest.json",
        *sorted((REPO_ROOT / "docs").glob("*.md")),
        *sorted((REPO_ROOT / "examples").glob("*.py")),
    ]
    present = [p for p in candidates if p.is_file()]
    offenders = [str(p.relative_to(REPO_ROOT)) for p in present
                 if re.search(r"(?<![\w-])mnemo\.ai\b", p.read_text())]
    assert offenders == []


def test_agent_manifest_is_valid_json():
    manifest = REPO_ROOT / "agent-manifest.json"
    if not manifest.is_file():
        pytest.skip("agent-manifest.json not present (installed package)")
    data = json.loads(manifest.read_text())
    assert data["api_base"] == "https://api.trymnemo.com"
    assert data["version"] == mnemo_sdk.__version__


# ---------------------------------------------------------------------------
# 402 insufficient_credits: raise, no retry, no payment
# ---------------------------------------------------------------------------

@patch("mnemo_sdk.client.time.sleep")
@patch("mnemo_sdk.client.requests.Session")
def test_402_insufficient_credits_maps_to_quota_exceeded(MockSession, mock_sleep):
    s = MockSession.return_value
    s.post.return_value = _mock_response(402, {"code": "insufficient_credits"})

    client = MnemoClient(api_key="k", api_url="https://mnemo.test")
    with pytest.raises(MnemoAPIError) as exc_info:
        client.verify(vector=[0.1] * 512)

    err = exc_info.value
    assert err.status_code == 402
    assert err.code is MnemoErrorCode.QUOTA_EXCEEDED
    assert err.message == "insufficient_credits"
    assert err.details == {"code": "insufficient_credits"}
    assert s.post.call_count == 1
    mock_sleep.assert_not_called()


@patch("mnemo_sdk.client.time.sleep")
@patch("mnemo_sdk.client.requests.Session")
def test_402_with_payment_required_header_still_raises_and_never_pays(MockSession, mock_sleep):
    s = MockSession.return_value
    s.post.return_value = _mock_response(
        402, {"code": "insufficient_credits"},
        headers={"PAYMENT-REQUIRED": "eyJ4NDAyVmVyc2lvbiI6Mn0="},
    )

    client = MnemoClient(api_key="k", api_url="https://mnemo.test")
    with pytest.raises(MnemoAPIError) as exc_info:
        client.verify(vector=[0.1] * 512)

    assert exc_info.value.code is MnemoErrorCode.QUOTA_EXCEEDED
    # Exactly one request; no retry, no back-off sleep.
    assert s.post.call_count == 1
    mock_sleep.assert_not_called()
    # Nothing payment-shaped was ever sent: not in the session headers, not per request.
    session_headers = s.headers.update.call_args[0][0]
    assert not any(h.upper().startswith("PAYMENT") for h in session_headers)
    _, kwargs = s.post.call_args
    assert not any(h.upper().startswith("PAYMENT") for h in (kwargs.get("headers") or {}))
    assert set(kwargs["json"]) == {"vector"}


# ---------------------------------------------------------------------------
# FastAPI-style error bodies
# ---------------------------------------------------------------------------

@patch("mnemo_sdk.client.requests.Session")
def test_detail_string_becomes_message(MockSession):
    s = MockSession.return_value
    s.post.return_value = _mock_response(401, {"detail": "Invalid API key"})

    client = MnemoClient(api_key="k", api_url="https://mnemo.test")
    with pytest.raises(MnemoAPIError) as exc_info:
        client.embed(vector=[0.1] * 512, model_id="m")

    assert exc_info.value.message == "Invalid API key"
    assert exc_info.value.code is MnemoErrorCode.UNAUTHORIZED
    assert exc_info.value.details is None


@patch("mnemo_sdk.client.requests.Session")
def test_detail_object_uses_message_then_code(MockSession):
    s = MockSession.return_value
    body = {"detail": {"code": "SUBJECT_TOO_LARGE", "max_subject_bytes": 4096}}
    s.post.return_value = _mock_response(413, body)

    client = MnemoClient(api_key="k", api_url="https://mnemo.test")
    with pytest.raises(MnemoAPIError) as exc_info:
        client.embed(vector=[0.1] * 512, model_id="m")

    assert exc_info.value.message == "SUBJECT_TOO_LARGE"
    assert exc_info.value.details == body["detail"]


@patch("mnemo_sdk.client.requests.Session")
def test_422_validation_list_maps_to_invalid_input(MockSession):
    s = MockSession.return_value
    detail = [{"loc": ["body", "vector"], "msg": "too short", "type": "value_error"}]
    s.post.return_value = _mock_response(422, {"detail": detail})

    client = MnemoClient(api_key="k", api_url="https://mnemo.test")
    with pytest.raises(MnemoAPIError) as exc_info:
        client.embed(vector=[0.1], model_id="m")

    assert exc_info.value.status_code == 422
    assert exc_info.value.code is MnemoErrorCode.INVALID_INPUT
    assert exc_info.value.details == detail


@patch("mnemo_sdk.client.requests.Session")
def test_non_json_error_body_uses_text(MockSession):
    s = MockSession.return_value
    s.get.return_value = _mock_response(500, text="Internal Server Error")

    client = MnemoClient(api_key="k", api_url="https://mnemo.test")
    with pytest.raises(MnemoAPIError) as exc_info:
        client.usage()

    assert exc_info.value.message == "Internal Server Error"
    assert exc_info.value.code is MnemoErrorCode.SERVER_ERROR


# ---------------------------------------------------------------------------
# Version consistency
# ---------------------------------------------------------------------------

def test_version_consistent_across_package_user_agent_and_pyproject():
    assert client_mod._SDK_VERSION == mnemo_sdk.__version__
    assert client_mod._USER_AGENT == f"mnemo-protocol/{mnemo_sdk.__version__} python"
    pyproject = REPO_ROOT / "pyproject.toml"
    if not pyproject.is_file():
        pytest.skip("pyproject.toml not present (installed package)")
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(), re.MULTILINE)
    assert m and m.group(1) == mnemo_sdk.__version__


def test_no_license_classifier_alongside_license_expression():
    """PEP 639: PyPI rejects License :: classifiers when License-Expression is set."""
    tomllib = pytest.importorskip("tomllib")  # Python 3.11+
    pyproject = REPO_ROOT / "pyproject.toml"
    if not pyproject.is_file():
        pytest.skip("pyproject.toml not present (installed package)")
    project = tomllib.loads(pyproject.read_text())["project"]
    assert isinstance(project["license"], str)
    assert project["license"] == "LicenseRef-Proprietary"
    assert set(project["license-files"]) == {"LICENSE", "TERMS.md"}
    assert not [c for c in project.get("classifiers", []) if c.startswith("License ::")]
