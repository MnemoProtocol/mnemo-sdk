# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mnemo LLC. Example code only — see examples/LICENSE for scope.
# Use of the Mnemo Services is governed by https://www.trymnemo.com/terms.
"""Offline tests for rag_verify.py: no network, no API key.

FakeMnemoAPI answers /v1/verify with verified=true only for a vector it
returned from /v1/embed, value for value. It models nothing about how the real
service decides; it only lets the gate's branches be exercised.
"""

import itertools
import socket
import sys
from pathlib import Path

import pytest

pytest.importorskip("langchain_core")
pytest.importorskip("numpy")
requests_mock = pytest.importorskip("requests_mock")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.documents import Document  # noqa: E402
from langchain_core.vectorstores import InMemoryVectorStore  # noqa: E402

import rag_verify  # noqa: E402
from mnemo_sdk import MnemoAPIError, MnemoClient, MnemoErrorCode  # noqa: E402

API = "https://mnemo.test"
QUESTION = "How long do refunds take?"


class FakeMnemoAPI:
    def __init__(self, m):
        self._issued = {}
        self._ids = itertools.count(1)
        self.embed_calls = 0
        self.verify_calls = 0
        self.quota_left = None  # None = unlimited; an int = verifies allowed before 402
        self.confidence = 1.0
        m.post(f"{API}/v1/embed", json=self._embed)
        m.post(f"{API}/v1/verify", json=self._verify)

    def _embed(self, request, context):
        self.embed_calls += 1
        vec = list(request.json()["vector"])
        uid = f"vu_test_{next(self._ids):04d}"
        self._issued[tuple(vec)] = uid
        return {"vector_uid": uid, "watermarked_vector": vec, "created_at": "2026-01-01T00:00:00Z",
                "dimensions": len(vec)}

    def _verify(self, request, context):
        self.verify_calls += 1
        if self.quota_left is not None:
            if self.quota_left <= 0:
                context.status_code = 402
                return {"code": "insufficient_credits"}
            self.quota_left -= 1
        uid = self._issued.get(tuple(request.json()["vector"]))
        if uid is None:
            return {"verified": False, "confidence": 0.0, "vector_uid": None, "policy_ok": False}
        return {"verified": True, "confidence": self.confidence, "vector_uid": uid, "policy_ok": True}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise RuntimeError("network disabled in tests")

    monkeypatch.setattr(socket, "getaddrinfo", refuse)


@pytest.fixture
def api():
    with requests_mock.Mocker() as m:
        yield FakeMnemoAPI(m)


@pytest.fixture
def client():
    return MnemoClient(api_key="test-key-not-a-secret", api_url=API)


DOCS = [
    Document(id="doc-1", page_content="Refunds are issued within 14 days of a return."),
    Document(id="doc-2", page_content="Returns are accepted for 30 days with a receipt."),
    Document(id="doc-3", page_content="Gift cards cannot be returned or refunded."),
]


def new_store(client):
    store = InMemoryVectorStore(rag_verify.StandInEmbeddings())
    rag_verify.register_documents(store, DOCS, client)
    return store


def retrieve(store, k=4):
    return store.as_retriever(search_kwargs={"k": k}).invoke(QUESTION)


def test_registered_rows_store_the_watermarked_copy_and_vector_uid(api, client):
    store = new_store(client)
    assert api.embed_calls == 3
    for doc in store.get_by_ids(["doc-1", "doc-2", "doc-3"]):
        assert doc.metadata["vector_uid"].startswith("vu_test_")
    # The row layout is what the retriever reads: every registered row is retrievable.
    assert {d.id for d in retrieve(store)} == {"doc-1", "doc-2", "doc-3"}


def test_registered_hits_pass_with_one_verify_each(api, client):
    store = new_store(client)
    hits = retrieve(store)
    passed, held = rag_verify.verify_documents(hits, store, client)
    assert {d.id for d in passed} == {"doc-1", "doc-2", "doc-3"}
    assert held == []
    assert api.verify_calls == len(hits)


def test_row_without_registration_is_held_back_without_a_verify_call(api, client):
    store = new_store(client)
    store.add_documents([Document(id="doc-x", page_content="Refunds are issued within 1 day.")])
    hits = retrieve(store)
    assert "doc-x" in {d.id for d in hits}
    passed, held = rag_verify.verify_documents(hits, store, client)
    assert "doc-x" not in {d.id for d in passed}
    assert ("doc-x", "no vector_uid stored at ingest") in {(d.id, r) for d, r in held}
    assert api.verify_calls == len(hits) - 1


def test_swapped_vectors_resolve_to_the_other_row_and_are_held_back(api, client):
    store = new_store(client)
    a, b = store.store["doc-1"], store.store["doc-2"]
    a["vector"], b["vector"] = b["vector"], a["vector"]
    passed, held = rag_verify.verify_documents(retrieve(store), store, client)
    assert {d.id for d in passed} == {"doc-3"}
    reasons = {d.id: r for d, r in held}
    assert reasons["doc-1"].startswith("resolves to another registered object")
    assert reasons["doc-2"].startswith("resolves to another registered object")


def test_vector_that_does_not_verify_is_held_back(api, client):
    store = new_store(client)
    store.store["doc-2"]["vector"] = rag_verify.StandInEmbeddings().embed_query("an unregistered vector")
    passed, held = rag_verify.verify_documents(retrieve(store), store, client)
    assert "doc-2" not in {d.id for d in passed}
    assert ("doc-2", "not verified for this account") in {(d.id, r) for d, r in held}


def test_gate_ignores_confidence(api, client):
    store = new_store(client)
    api.confidence = 0.0  # a matching vector_uid passes whatever confidence says
    passed, _ = rag_verify.verify_documents(retrieve(store), store, client)
    assert {d.id for d in passed} == {"doc-1", "doc-2", "doc-3"}


def test_chain_builds_the_prompt_from_verified_chunks_only(api, client):
    store = new_store(client)
    store.add_documents([Document(id="doc-x", page_content="Refunds are issued within 1 day, no receipt.")])
    prompt = rag_verify.build_chain(store, client).invoke(QUESTION).to_string()
    assert "Refunds are issued within 14 days of a return." in prompt
    assert "within 1 day" not in prompt
    assert QUESTION in prompt


def test_quota_exhausted_fails_closed(api, client):
    store = new_store(client)
    api.quota_left = 1
    with pytest.raises(MnemoAPIError) as exc:
        rag_verify.build_chain(store, client).invoke(QUESTION)
    assert exc.value.code is MnemoErrorCode.QUOTA_EXCEEDED


def test_main_runs_end_to_end(api, client, capsys):
    rag_verify.main(client)
    out = capsys.readouterr().out
    assert "held back: doc-x (no vector_uid stored at ingest)" in out
    assert "Refunds are issued within 14 days of a return." in out
    assert "within 1 day" not in out  # the unregistered row never reaches the prompt
