# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mnemo LLC. Example code only — see examples/LICENSE for scope.
# Use of the Mnemo Services is governed by https://www.trymnemo.com/terms.
"""Verify retrieved chunks with Mnemo before they reach a LangChain prompt.

  ingest    your embedding -> Mnemo embed() -> store the watermarked copy and
            its vector_uid in the vector store
  retrieve  the LangChain retriever ranks chunks by similarity (LangChain's
            job; Mnemo does not search or rank)
  gate      for each hit, Mnemo verify() on the vector the store holds; the
            chunk reaches the prompt only when it resolves to the vector_uid
            stored with it at ingest

The gate answers one question per hit: does the vector in your store still
resolve to the object your pipeline registered for that row? A row written
without registration, or whose vector no longer resolves to its own
vector_uid, is held back.

Run:  pip install -r requirements.txt
      export MNEMO_API_KEY=...   # an account API key: https://www.trymnemo.com/login
      python rag_verify.py
"""

from __future__ import annotations

import os
import random
import uuid
from typing import Iterable

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda, RunnablePassthrough
from langchain_core.vectorstores import InMemoryVectorStore

from mnemo_sdk import MnemoClient

# The label of the embedding model you use; Mnemo records it with each object.
MODEL_ID = "stand-in-768"


class StandInEmbeddings(Embeddings):
    """A stand-in embedding model so the example runs without another API key.

    Deterministic 768-dimension word-hash vectors, unit length. Replace it with
    your real LangChain embeddings (any ``Embeddings`` that returns 512–4096
    floats); nothing else in this file changes.
    """

    dim = 768

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for word in text.lower().split():
            rng = random.Random(word)  # a str seed is hashed with SHA-512: stable across runs
            for i in range(self.dim):
                vec[i] += rng.uniform(-1.0, 1.0)
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / norm for x in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def register_documents(
    store: InMemoryVectorStore, docs: Iterable[Document], client: MnemoClient
) -> list[str]:
    """Embed each document, register it with Mnemo, and store the watermarked copy.

    The store keeps ``result.watermarked_vector`` (not your original vector) and
    ``metadata["vector_uid"]``. ``InMemoryVectorStore.add_documents()`` always
    re-embeds the text, so the precomputed vector is written in the layout
    ``add_documents()`` itself uses. With another vector store, use its method
    for adding precomputed vectors and keep vector_uid in the row's metadata.
    """
    docs = list(docs)
    vectors = store.embeddings.embed_documents([d.page_content for d in docs])
    ids = []
    for doc, vector in zip(docs, vectors):
        result = client.embed(vector, model_id=MODEL_ID)  # one registered object per chunk
        doc_id = doc.id or str(uuid.uuid4())
        store.store[doc_id] = {
            "id": doc_id,
            "vector": result.watermarked_vector,
            "text": doc.page_content,
            "metadata": {**doc.metadata, "vector_uid": result.vector_uid},
        }
        ids.append(doc_id)
    return ids


def verify_documents(
    docs: list[Document], store: InMemoryVectorStore, client: MnemoClient
) -> tuple[list[Document], list[tuple[Document, str]]]:
    """Split retrieved documents into (passed, held_back) using Mnemo verify().

    A hit passes only when verify() returns a result whose vector_uid equals the
    vector_uid stored with the row at ingest. ``confidence`` and ``signals`` are
    never consulted. Each verify() call counts as one verification on your plan,
    so keep the retriever's k small. A MnemoAPIError (for example the plan's
    verifications are used up) is not caught here: the chain raises and no
    unverified chunk reaches the prompt.
    """
    passed: list[Document] = []
    held_back: list[tuple[Document, str]] = []
    for doc in docs:
        expected = doc.metadata.get("vector_uid")
        row = store.store.get(doc.id) if doc.id else None
        if not expected or row is None:
            held_back.append((doc, "no vector_uid stored at ingest"))  # nothing to check; no verify call
            continue
        check = client.verify(row["vector"])  # the vector the store holds, not the query
        if check is None:
            held_back.append((doc, "not verified for this account"))
        elif check.vector_uid != expected:
            held_back.append((doc, f"resolves to another registered object ({check.vector_uid})"))
        else:
            passed.append(doc)
    return passed, held_back


def verify_gate(store: InMemoryVectorStore, client: MnemoClient) -> Runnable:
    """A Runnable for the chain: documents in, verified documents out."""

    def gate(docs: list[Document]) -> list[Document]:
        passed, held_back = verify_documents(docs, store, client)
        for doc, reason in held_back:
            print(f"held back: {doc.id} ({reason})")  # log for review
        return passed

    return RunnableLambda(gate)


PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "Answer only from the context. If the context is empty, say you don't know.\n\nContext:\n{context}"),
        ("human", "{question}"),
    ]
)


def format_docs(docs: list[Document]) -> str:
    return "\n".join(f"- {d.page_content}" for d in docs)


def build_chain(store: InMemoryVectorStore, client: MnemoClient, k: int = 4) -> Runnable:
    """retriever -> Mnemo verify gate -> prompt. Pipe the result into your chat model."""
    retriever = store.as_retriever(search_kwargs={"k": k})
    return {
        "context": retriever | verify_gate(store, client) | RunnableLambda(format_docs),
        "question": RunnablePassthrough(),
    } | PROMPT


def main(client: MnemoClient | None = None) -> None:
    client = client or MnemoClient(api_key=os.environ["MNEMO_API_KEY"])
    store = InMemoryVectorStore(StandInEmbeddings())

    register_documents(
        store,
        [
            Document(id="doc-1", page_content="Refunds are issued within 14 days of a return."),
            Document(id="doc-2", page_content="Returns are accepted for 30 days with a receipt."),
            Document(id="doc-3", page_content="Gift cards cannot be returned or refunded."),
        ],
        client,
    )
    # A row written straight into the store, without register_documents(): for
    # example a bulk import that skipped registration. It has no vector_uid, so
    # it is held back whatever its similarity to the question.
    store.add_documents([Document(id="doc-x", page_content="Refunds are issued within 1 day, no receipt needed.")])

    prompt = build_chain(store, client).invoke("How long do refunds take?")
    print(prompt.to_string())  # send `prompt` to your chat model, e.g. chain | llm


if __name__ == "__main__":
    main()
