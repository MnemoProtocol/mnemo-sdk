"""PR J1 — SDK alignment to the MnemoV2 #65 trusted subject-proof transport.

The SDK is TRANSPORT ONLY: it passes raw `subject` context and the opaque
`subject_proof` carrier through to the core runtime, which derives the fingerprint,
mints the proof, and re-verifies it. These tests assert the SDK:
  * sends `subject` only when provided (backward compatible otherwise),
  * never derives a fingerprint or supplies trust/proof fields,
  * captures the server-issued `subject_proof` into EmbedResult,
  * passes a `subject_proof` carrier back verbatim on verify, untouched and untrusted,
  * parses optional `signals`, tolerates missing + unknown response fields.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from mnemo_sdk import (
    MnemoClient, Subject, SubjectProof, VerifySignals, EmbedResult, VerifyResult,
)
from mnemo_sdk.errors import MnemoValidationError


def _mock_response(status_code=200, json_data=None, headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = json.dumps(json_data or {})
    resp.headers = headers or {}
    return resp


# A representative server-issued carrier (verbatim shape from V1SubjectProofResponse).
SUBJECT_PROOF_CARRIER = {
    "version": "subject-proof-v1",
    "proof_type": "hmac_sha256",
    "proof_key_id": "subjk1",
    "tenant_id": "tenantA",
    "subject_fingerprint": "f" * 64,
    "canonicalization_version": "subjcanon-v1",
    "issued_at": 1_700_000_000.0,
    "expires_at": 1_700_003_600.0,
    "proof": "ab" * 32,
}

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

SIGNALS = {
    "method": "oracle",
    "spectral_status": "NO_MATCH",
    "oracle_status": "MATCH",
    "oracle_best_dist": 0.1,
    "oracle_margin": 0.5,
    "oracle_candidate_count": 5,
    "mode": "STRICT",
    "latency_ms": 7.3,
}


def _client(url="https://test.mnemo.ai", key="k"):
    return MnemoClient(api_key=key, api_url=url)


def _body(session_instance):
    return session_instance.post.call_args[1]["json"]


# ── embed: subject input ──────────────────────────────────────────────────────

class TestEmbedSubjectInput:
    @patch("mnemo_sdk.client.requests.Session")
    def test_embed_without_subject_is_backward_compatible(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _mock_response(200, EMBED_RESPONSE)
        r = _client().embed(vector=[0.1, 0.2, 0.3], model_id="m1")
        assert "subject" not in _body(s)
        assert r.vector_uid == "uid-abc-123"
        assert r.subject_proof is None

    @patch("mnemo_sdk.client.requests.Session")
    def test_embed_with_Subject_model_serializes(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _mock_response(200, EMBED_RESPONSE)
        subj = Subject(subject_uri="mnemo://subj/t/document/doc-1", subject_type="document",
                       object_id="doc-1", adapters={"openrtb": {"x": 1}})
        _client().embed(vector=[0.1, 0.2, 0.3], model_id="m1", subject=subj)
        sent = _body(s)["subject"]
        assert sent == {
            "subject_uri": "mnemo://subj/t/document/doc-1",
            "subject_type": "document",
            "object_id": "doc-1",
            "adapters": {"openrtb": {"x": 1}},
        }
        # None-valued optionals dropped; no trust/proof fields present
        assert "subject_fingerprint" not in sent and "trust_mode" not in sent

    @patch("mnemo_sdk.client.requests.Session")
    def test_embed_with_dict_subject_serializes(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _mock_response(200, EMBED_RESPONSE)
        d = {"subject_uri": "mnemo://s", "subject_type": "record"}
        _client().embed(vector=[0.1], model_id="m1", subject=d)
        assert _body(s)["subject"] == d

    @patch("mnemo_sdk.client.requests.Session")
    def test_sdk_does_not_allow_client_supplied_fingerprint_or_trust(self, MockSession):
        # The SDK must never let the client supply server-derived trust fields.
        s = MockSession.return_value
        s.post.return_value = _mock_response(200, EMBED_RESPONSE)
        c = _client()
        for bad in (
            {"subject_uri": "u", "subject_type": "t", "subject_fingerprint": "deadbeef"},
            {"subject_uri": "u", "subject_type": "t", "trust_mode": "B_trusted"},
            {"subject_uri": "u", "subject_type": "t", "proof": "x"},
            {"subject_uri": "u", "subject_type": "t", "proof_key_id": "k"},
        ):
            with pytest.raises(MnemoValidationError):
                c.embed(vector=[0.1], model_id="m1", subject=bad)
        s.post.assert_not_called()  # rejected before any request

    def test_Subject_model_has_no_fingerprint_or_proof_fields(self):
        # Structural guarantee: the typed model cannot carry server-derived trust.
        fields = set(Subject(subject_uri="u", subject_type="t").to_dict())
        assert not ({"subject_fingerprint", "trust_mode", "proof",
                     "proof_type", "proof_digest", "proof_key_id"} & fields)


# ── embed: subject_proof output ───────────────────────────────────────────────

class TestEmbedSubjectProofOutput:
    @patch("mnemo_sdk.client.requests.Session")
    def test_embed_parses_subject_proof(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _mock_response(200, {**EMBED_RESPONSE, "subject_proof": SUBJECT_PROOF_CARRIER})
        r = _client().embed(vector=[0.1], model_id="m1",
                            subject={"subject_uri": "u", "subject_type": "t"})
        assert isinstance(r.subject_proof, SubjectProof)
        assert r.subject_proof.proof_key_id == "subjk1"
        assert r.subject_proof.expires_at == 1_700_003_600.0
        # round-trips verbatim
        assert r.subject_proof.to_dict() == SUBJECT_PROOF_CARRIER

    @patch("mnemo_sdk.client.requests.Session")
    def test_embed_without_subject_proof_in_response_gives_none(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _mock_response(200, EMBED_RESPONSE)  # no subject_proof
        r = _client().embed(vector=[0.1], model_id="m1")
        assert r.subject_proof is None

    @patch("mnemo_sdk.client.requests.Session")
    def test_embed_tolerates_unknown_extra_response_fields(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _mock_response(200, {**EMBED_RESPONSE, "future_field": 123,
                                                   "subject_proof": {**SUBJECT_PROOF_CARRIER, "new_k": "v"}})
        r = _client().embed(vector=[0.1], model_id="m1")
        assert r.vector_uid == "uid-abc-123"
        # unknown carrier field preserved verbatim for round-trip
        assert r.subject_proof.to_dict()["new_k"] == "v"


# ── verify: subject_proof carrier (opaque, untrusted) ─────────────────────────

class TestVerifySubjectProofCarrier:
    @patch("mnemo_sdk.client.requests.Session")
    def test_verify_without_subject_proof_is_backward_compatible(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _mock_response(200, VERIFY_RESPONSE)
        r = _client().verify(vector=[0.1])
        assert "subject_proof" not in _body(s)
        assert r.verified is True

    @patch("mnemo_sdk.client.requests.Session")
    def test_verify_with_SubjectProof_sends_carrier_exactly(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _mock_response(200, VERIFY_RESPONSE)
        proof = SubjectProof.from_dict(SUBJECT_PROOF_CARRIER)
        _client().verify(vector=[0.1], subject_proof=proof)
        assert _body(s)["subject_proof"] == SUBJECT_PROOF_CARRIER  # verbatim

    @patch("mnemo_sdk.client.requests.Session")
    def test_verify_with_dict_subject_proof_sends_carrier_exactly(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _mock_response(200, VERIFY_RESPONSE)
        _client().verify(vector=[0.1], subject_proof=SUBJECT_PROOF_CARRIER)
        assert _body(s)["subject_proof"] == SUBJECT_PROOF_CARRIER

    @patch("mnemo_sdk.client.requests.Session")
    def test_malformed_subject_proof_passed_through_untouched(self, MockSession):
        # The SDK must NOT validate/trust the carrier — a malformed one is sent as-is;
        # the server is the sole validator (and would fail it closed).
        s = MockSession.return_value
        s.post.return_value = _mock_response(200, VERIFY_RESPONSE)
        for bad in ({"binding_id": "b"}, {"garbage": True}, {"proof": "tampered"}, {}):
            s.post.reset_mock()
            s.post.return_value = _mock_response(200, VERIFY_RESPONSE)
            _client().verify(vector=[0.1], subject_proof=bad)
            assert _body(s)["subject_proof"] == bad  # untouched

    @patch("mnemo_sdk.client.requests.Session")
    def test_subject_proof_roundtrip_embed_to_verify(self, MockSession):
        s = MockSession.return_value
        c = _client()
        s.post.return_value = _mock_response(200, {**EMBED_RESPONSE, "subject_proof": SUBJECT_PROOF_CARRIER})
        emb = c.embed(vector=[0.1], model_id="m1", subject={"subject_uri": "u", "subject_type": "t"})
        s.post.reset_mock()
        s.post.return_value = _mock_response(200, VERIFY_RESPONSE)
        c.verify(vector=[0.1], subject_proof=emb.subject_proof)
        assert _body(s)["subject_proof"] == SUBJECT_PROOF_CARRIER

    def test_invalid_subject_proof_type_rejected(self):
        from mnemo_sdk.client import _serialize_subject_proof
        with pytest.raises(MnemoValidationError):
            _serialize_subject_proof(12345)


# ── verify: signals ───────────────────────────────────────────────────────────

class TestVerifySignals:
    @patch("mnemo_sdk.client.requests.Session")
    def test_verify_parses_signals(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _mock_response(200, {**VERIFY_RESPONSE, "signals": SIGNALS})
        r = _client().verify(vector=[0.1])
        assert isinstance(r.signals, VerifySignals)
        assert r.signals.method == "oracle"
        assert r.signals.mode == "STRICT"
        assert r.signals.oracle_margin == 0.5

    @patch("mnemo_sdk.client.requests.Session")
    def test_verify_without_signals_gives_none(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _mock_response(200, VERIFY_RESPONSE)
        assert _client().verify(vector=[0.1]).signals is None

    @patch("mnemo_sdk.client.requests.Session")
    def test_verify_tolerates_unknown_response_fields(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _mock_response(200, {**VERIFY_RESPONSE, "brand_new": 1,
                                                   "signals": {**SIGNALS, "future": "x"}})
        r = _client().verify(vector=[0.1])
        assert r.verified is True and r.signals.method == "oracle"


# ── backward compatibility: old positional/keyword usage still works ──────────

class TestBackwardCompat:
    @patch("mnemo_sdk.client.requests.Session")
    def test_old_embed_args_still_work(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _mock_response(200, EMBED_RESPONSE)
        r = _client().embed([0.1, 0.2], "m1", model_version="2.0", policy={"ttl_hours": 24})
        assert r.vector_uid == "uid-abc-123"
        b = _body(s)
        assert b["model_version"] == "2.0" and b["policy"] == {"ttl_hours": 24}
        assert "subject" not in b

    @patch("mnemo_sdk.client.requests.Session")
    def test_old_verify_args_still_work(self, MockSession):
        s = MockSession.return_value
        s.post.return_value = _mock_response(200, VERIFY_RESPONSE)
        r = _client().verify([0.11, 0.22, 0.33])
        assert r.verified is True
        assert "subject_proof" not in _body(s)
