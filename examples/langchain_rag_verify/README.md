# Gate retrieved chunks on their stored vectors before they reach the prompt (LangChain)

A retrieval-augmented generation (RAG) chain built from `langchain-core` building blocks, with a Mnemo verify gate between the retriever and the prompt. A retrieved chunk reaches the prompt only if the vector your store holds for it still resolves to the `vector_uid` your pipeline registered for that row at ingest. The chunk text itself is never checked (see below).

```
ingest:   your embedding ─► Mnemo embed() ─► store watermarked copy + vector_uid
query:    retriever (similarity, LangChain) ─► Mnemo verify gate ─► prompt ─► your chat model
```

**What the gate catches:**
- a row written to the vector store without registration, for example by a bulk import that skipped ingest;
- a row whose vector no longer resolves to its own `vector_uid`, for example vectors swapped between rows or replaced.

**What it does not do:**
- **It does not check the chunk text.** The gate verifies the vector stored for each row and compares the result with the `vector_uid` stored beside it; it never reads the text that goes into the prompt. It does not detect text edited after ingest, and a row that carries a copy of another registered row's vector and `vector_uid` passes. A passed row is not evidence that its text is authentic, unchanged or true. Detecting text edits needs a separate check of your own, for example a hash of each chunk's text recorded at ingest and kept outside the vector store.
- Mnemo does not search or rank. The retriever's similarity search still decides which chunks are candidates; the gate only drops candidates that fail the check.
- `verified` is about your own account. A held-back row is not evidence that someone else wrote it.

## Run it

```bash
pip install -r requirements.txt     # mnemo-protocol, langchain-core, numpy
export MNEMO_API_KEY=...            # an account API key: sign in at https://www.trymnemo.com/login
python rag_verify.py
```

The script registers three chunks (3 embeds), then writes a fourth row straight into the store with no registration, and runs the chain for one question. The unregistered row is held back without a verify call. Each of the other retrieved rows costs one verification on your plan.

It uses `StandInEmbeddings`, a deterministic stand-in so the example needs no second API key. Replace it with your real LangChain embeddings (512–4096 floats); nothing else changes. The output is the prompt, ready to pipe into a chat model (`chain | llm`).

## How the gate decides

For each retrieved `Document`, `verify_documents()`:

1. reads `metadata["vector_uid"]`, stored at ingest. If there is none, the row is held back and no verify call is made.
2. calls `client.verify()` on the **vector the store holds** for that row, not the query vector.
3. passes the row only when `verify()` returns a result **and** `check.vector_uid` equals the stored `vector_uid`.
   - `None` means not verified for this account: held back.
   - A different `vector_uid` means it resolves to another object registered to your account: held back.

`confidence` and `signals` are never used. If `verify()` raises `MnemoAPIError` (for example `QUOTA_EXCEEDED` when the plan's verifications are used up), the chain raises and nothing reaches the prompt. Catch it around `chain.invoke()` if you want a different policy.

`InMemoryVectorStore.add_documents()` always re-embeds text, so `register_documents()` writes the watermarked vector in the same row layout `add_documents()` uses. With another vector store, add the watermarked vector with that store's method for precomputed vectors and keep `vector_uid` in the row's metadata.

## Tests

```bash
pip install -r requirements-test.txt
pytest tests/
```

The tests run offline: a fake Mnemo API answers `verify` with `verified: true` only for a vector it returned from `embed`, and DNS is disabled. They cover registered rows passing, an unregistered row (no verify call), swapped vectors, a vector that does not verify, confidence being ignored, the prompt containing only verified chunks, quota exhaustion failing closed, and `main()` end to end. The fake models nothing about how the real service decides.

Python 3.10+ (`langchain-core` 1.x). The `mnemo-protocol` SDK itself needs no LangChain.
