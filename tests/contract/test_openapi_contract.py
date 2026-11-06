"""Contract tests: the SDK against the published Mnemo OpenAPI document.

`tests/contract/openapi.json` is a byte-for-byte copy of the published contract
(https://www.trymnemo.com/openapi.json, identical to MnemoProtocol/MnemoV2
docs/public/openapi.json at a9a9458 and to MnemoProtocol/mnemo-agent-protocol).
Update it only together with a contract change; the hash test below fails
when it is edited by hand. A scheduled workflow (contract-drift.yml) reports
when the published copy changes.

What is checked, offline (HTTP is mocked; nothing calls the live API):
  * every request body the SDK builds validates against the operation's
    requestBody schema, the auth header matches the apiKey security scheme,
    and the verify Idempotency-Key satisfies its parameter schema;
  * every documented success response (examples, or schema-valid bodies the
    test builds and validates first) is parsed by the SDK;
  * every documented error status for the API-key operations surfaces as a
    MnemoAPIError with the documented status (never a raw exception).

Known contract gaps are strict xfails that name the work item that closes
them (K4 = public OpenAPI completeness). When the contract is fixed the xfail
turns into a failure, so the marker must be removed in the same change.
"""

import hashlib
import json
import uuid
from pathlib import Path

import pytest
import requests_mock as rm

jsonschema = pytest.importorskip("jsonschema")
from jsonschema import Draft202012Validator  # noqa: E402

from mnemo_sdk import MnemoAPIError, MnemoClient, MnemoErrorCode, create_policy  # noqa: E402

SPEC_PATH = Path(__file__).with_name("openapi.json")
SPEC_SHA256 = "c94f313fa916f565d1a9b07d4823aad55afcc741ebfb2de0678fa9fe1950b42c"
SPEC = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

BASE = "https://contract.test"
KEY = "contract-test-key"
DIM = 512  # the published Vector schema requires 512-4096 numbers
VEC = [0.01] * DIM


def _validator(ref_or_schema):
    schema = {"$ref": ref_or_schema} if isinstance(ref_or_schema, str) else dict(ref_or_schema)
    schema["components"] = SPEC["components"]
    return Draft202012Validator(schema)


def _errors(schema, instance):
    return sorted(e.message for e in _validator(schema).iter_errors(instance))


def _op(method, path):
    return SPEC["paths"][path][method]


def _request_schema(method, path):
    return _op(method, path)["requestBody"]["content"]["application/json"]["schema"]


def _response_content(method, path, status):
    return _op(method, path)["responses"][str(status)].get("content", {}).get("application/json", {})


def _capture(call, method, path, response_json):
    """Run `call(client)` against a mock and return the request it sent."""
    client = MnemoClient(api_key=KEY, api_url=BASE, retry_attempts=1)
    with rm.Mocker() as m:
        m.register_uri(method.upper(), f"{BASE}{path}", json=response_json)
        call(client)
        return m.request_history[-1]


EMBED_200 = {
    "vector_uid": "6f1c9d3e-0000-4000-8000-000000000001",
    "watermarked_vector": VEC,
    "created_at": "2026-11-06T00:00:00Z",
    "dimensions": DIM,
}
VERIFY_200 = {"verified": True, "confidence": 0.97, "vector_uid": EMBED_200["vector_uid"], "policy_ok": True}


# ---------------------------------------------------------------------------
# The vendored document
# ---------------------------------------------------------------------------

def test_vendored_spec_is_the_recorded_version():
    assert hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest() == SPEC_SHA256
    assert SPEC["openapi"].startswith("3.1")


def test_response_fixtures_used_below_are_schema_valid():
    assert _errors("#/components/schemas/EmbedResponse", EMBED_200) == []
    assert _errors("#/components/schemas/VerifyResponse", VERIFY_200) == []


# ---------------------------------------------------------------------------
# Operations and authentication
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,path", [("post", "/v1/embed"), ("post", "/v1/verify")])
def test_sdk_operation_is_published(method, path):
    assert method in SPEC["paths"][path]
    assert {"apiKey": []} in _op(method, path)["security"]


@pytest.mark.xfail(strict=True, reason="K4: GET /v1/health and GET /v1/usage are live and used by the SDK "
                                       "but absent from the public OpenAPI")
@pytest.mark.parametrize("path", ["/v1/health", "/v1/usage"])
def test_sdk_get_operation_is_published(path):
    assert path in SPEC["paths"]


def test_auth_header_matches_the_api_key_scheme():
    scheme = SPEC["components"]["securitySchemes"]["apiKey"]
    assert (scheme["type"], scheme["in"]) == ("apiKey", "header")
    req = _capture(lambda c: c.verify(VEC), "post", "/v1/verify", VERIFY_200)
    assert req.headers[scheme["name"]] == KEY


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label,call", [
    ("minimal", lambda c: c.embed(VEC, model_id="text-embedding-3-small")),
    ("model_version", lambda c: c.embed(VEC, model_id="m", model_version="2024-01")),
    ("subject", lambda c: c.embed(VEC, model_id="m", subject={"subject_uri": "doc://1", "subject_type": "chunk"})),
])
def test_embed_request_matches_contract(label, call):
    req = _capture(call, "post", "/v1/embed", EMBED_200)
    assert _errors(_request_schema("post", "/v1/embed"), req.json()) == []


@pytest.mark.xfail(strict=True, reason="C1/K4: the SDK sends `policy` on embed and the server accepts it, but the "
                                       "published EmbedRequest has no `policy` and additionalProperties:false")
def test_embed_request_with_policy_matches_contract():
    req = _capture(lambda c: c.embed(VEC, model_id="m", policy=create_policy(ttl_days=30)),
                   "post", "/v1/embed", EMBED_200)
    assert _errors(_request_schema("post", "/v1/embed"), req.json()) == []


@pytest.mark.parametrize("label,call", [
    ("minimal", lambda c: c.verify(VEC)),
    ("subject_proof", lambda c: c.verify(VEC, subject_proof={"token": "opaque"})),
    ("caller_key", lambda c: c.verify(VEC, idempotency_key="order-42")),
])
def test_verify_request_matches_contract(label, call):
    req = _capture(call, "post", "/v1/verify", VERIFY_200)
    assert _errors(_request_schema("post", "/v1/verify"), req.json()) == []
    params = {p["name"]: p for p in _op("post", "/v1/verify")["parameters"]}
    key = req.headers["Idempotency-Key"]
    assert _errors(params["Idempotency-Key"]["schema"], key) == []
    if label != "caller_key":
        assert uuid.UUID(key).version == 4
    assert "PAYMENT-SIGNATURE" not in req.headers  # the SDK never pays


def test_embed_sends_no_payment_or_idempotency_header():
    req = _capture(lambda c: c.embed(VEC, model_id="m"), "post", "/v1/embed", EMBED_200)
    assert "PAYMENT-SIGNATURE" not in req.headers
    assert "Idempotency-Key" not in req.headers


# ---------------------------------------------------------------------------
# Success responses
# ---------------------------------------------------------------------------

def test_embed_response_is_parsed():
    client = MnemoClient(api_key=KEY, api_url=BASE)
    with rm.Mocker() as m:
        m.post(f"{BASE}/v1/embed", json=EMBED_200)
        res = client.embed(VEC, model_id="m")
    assert res.vector_uid == EMBED_200["vector_uid"]
    assert res.dimensions == DIM


def test_embed_response_with_optional_fields_is_parsed():
    body = dict(EMBED_200, lineage={"parent_uid": "p", "relation": "derived_from", "depth": 1},
                subject_proof={"token": "opaque"})
    assert _errors("#/components/schemas/EmbedResponse", body) == []
    client = MnemoClient(api_key=KEY, api_url=BASE)
    with rm.Mocker() as m:
        m.post(f"{BASE}/v1/embed", json=body)
        res = client.embed(VEC, model_id="m")
    assert res.subject_proof is not None


@pytest.mark.parametrize("name", sorted(_response_content("post", "/v1/verify", 200).get("examples", {})))
def test_documented_verify_examples_are_parsed(name):
    body = _response_content("post", "/v1/verify", 200)["examples"][name]["value"]
    assert _errors("#/components/schemas/VerifyResponse", body) == []
    client = MnemoClient(api_key=KEY, api_url=BASE)
    with rm.Mocker() as m:
        m.post(f"{BASE}/v1/verify", json=body)
        res = client.verify(VEC)
    if body["verified"]:
        assert res is not None and res.vector_uid == body["vector_uid"]
    else:
        assert res is None  # healthy negative: a normal result, not an error


# ---------------------------------------------------------------------------
# Error responses
# ---------------------------------------------------------------------------

# Minimal schema-valid bodies for statuses whose content is not specified.
_FALLBACK = {
    "401": {"detail": "Authentication required for /v1/ endpoints"},
    "403": {"detail": "Forbidden"},
    "409": {"code": "request_in_progress"},
    "410": {"detail": {"code": "EPHEMERAL_NAMESPACE_EXPIRED"}},
    "413": {"detail": {"code": "SUBJECT_TOO_LARGE"}},
    "422": {"detail": [{"loc": ["body", "vector"], "msg": "field required", "type": "missing"}]},
    "429": {"detail": "Rate limit exceeded"},
    "503": {"code": "verification_unavailable"},
}
# Per-operation overrides where the documented schema differs.
_FALLBACK_BY_PATH = {
    ("/v1/embed", "409"): {"detail": "Duplicate request_id"},  # ErrorDetail on embed
}
# What the SDK's status mapping promises (docs/sdk_reference.md, MnemoAPIError).
_MAPPING = {
    400: MnemoErrorCode.INVALID_INPUT, 401: MnemoErrorCode.UNAUTHORIZED, 402: MnemoErrorCode.QUOTA_EXCEEDED,
    403: MnemoErrorCode.UNAUTHORIZED, 404: MnemoErrorCode.NOT_FOUND, 422: MnemoErrorCode.INVALID_INPUT,
    429: MnemoErrorCode.RATE_LIMIT,
}


def _error_cases():
    for path in ("/v1/embed", "/v1/verify"):
        for status, resp in _op("post", path)["responses"].items():
            if not status.startswith(("4", "5")):
                continue
            content = resp.get("content", {}).get("application/json", {})
            bodies = []
            if "example" in content:
                bodies.append(("example", content["example"]))
            for name, ex in (content.get("examples") or {}).items():
                bodies.append((name, ex["value"]))
            if not bodies:
                bodies.append(("fallback", _FALLBACK_BY_PATH.get((path, status), _FALLBACK[status])))
            for name, body in bodies:
                yield pytest.param(path, int(status), body, id=f"{path}-{status}-{name}")


@pytest.mark.parametrize("path,status,body", list(_error_cases()))
def test_documented_errors_raise_mnemo_api_error(path, status, body):
    schema = _response_content("post", path, status).get("schema")
    if schema:
        assert _errors(schema, body) == [], "test body must be valid for the documented schema"
    client = MnemoClient(api_key=KEY, api_url=BASE, retry_attempts=1)
    with rm.Mocker() as m:
        m.post(f"{BASE}{path}", status_code=status, json=body)
        with pytest.raises(MnemoAPIError) as ei:
            if path == "/v1/embed":
                client.embed(VEC, model_id="m")
            else:
                client.verify(VEC)
    exc = ei.value
    assert exc.status_code == status
    assert exc.code == _MAPPING.get(status, MnemoErrorCode.SERVER_ERROR)
    assert exc.message  # never empty, whatever the envelope shape
    if isinstance(body, dict) and isinstance(body.get("code"), str):
        assert (exc.details or {}).get("code") == body["code"]
