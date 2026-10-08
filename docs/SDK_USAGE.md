# SDK Usage Guide

## Core Methods

### `client.embed(vector, model_id, ...)`

Embeds an invisible watermark into a vector and returns a tracked result.

**Parameters:**
- `vector` — list of floats (your embedding; 512–4096 finite numbers)
- `model_id` — string identifying the embedding model
- `model_version` — optional version string (default `"1.0"`)
- `policy` — optional policy dict (from `create_policy()` or `PolicyBuilder().build()`)
- `subject` — optional trusted-subject context (see below)

**Returns:** `EmbedResult`

```python
result = client.embed([0.1, -0.3, 0.5, ...], model_id="text-embedding-3-small")
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `vector_uid` | `str` | Unique identity assigned to this vector |
| `watermarked_vector` | `list[float]` | The watermarked vector (same dimensions) |
| `created_at` | `str` | ISO timestamp of when the watermark was created |
| `dimensions` | `int` | Number of dimensions |
| `subject_proof` | `SubjectProof \| None` | Server-issued carrier, only when a `subject` was supplied and the server transport is enabled |

---

### `client.verify(vector)`

Attempts to identify a watermarked vector.

**Parameters:**
- `vector` — list of floats to verify (512–4096 finite numbers)
- `subject_proof` — optional carrier from a prior `embed()` (see below)

**Returns:** `VerifyResult` if identified, `None` if not.

```python
result = client.verify(some_vector)
if result is not None:
    print(result.vector_uid)
```

**Response fields (when verified):**

| Field | Type | Description |
|-------|------|-------------|
| `verified` | `bool` | Always `True` when a result is returned |
| `confidence` | `float` | Confidence score (0.0 to 1.0) |
| `vector_uid` | `str` | The identified vector's UID |
| `policy_ok` | `bool` | Whether the vector's access policy is satisfied |

When verification fails, `verify()` returns `None` — not a `VerifyResult` with `verified=False`.

`VerifyResult` may also carry an optional `signals` diagnostic block (method,
spectral/oracle statuses, oracle metrics, `mode`, `latency_ms`).

---

### Trusted subject binding (optional)

`embed()` accepts an optional `subject` (a `Subject` or dict of **raw** context),
and `verify()` accepts an optional `subject_proof` (the server-issued carrier from a
prior embed). All subject-aware calls route to the core runtime, which does all
trust work; **the SDK is transport only** — it never derives a fingerprint, mints a
proof, validates a proof, or interprets corroboration.

```python
from mnemo_sdk import Subject

emb = client.embed(vec, model_id="m", subject=Subject(
    subject_uri="mnemo://subj/tenant/document/doc-1", subject_type="document"))
# emb.subject_proof is an opaque carrier (or None if the server transport is off).
check = client.verify(emb.watermarked_vector, subject_proof=emb.subject_proof)
```

- `subject` is **raw context**; the server derives `subject_fingerprint`. The SDK
  rejects any client-supplied `subject_fingerprint` / `trust_mode` / `proof*`.
- `subject_proof` is **opaque and untrusted**; the SDK replays it verbatim and the
  **server** re-verifies it.
- The proof is consulted **only** on a STRICT oracle-only Case 3 verify under
  FP-squash (the provenance-grade, claim-bearing path) — not on every verify, and
  with no implied always-on latency. **BALANCED/HIGH_RECALL are non-claim-bearing**
  for subject-proof / oracle-only recovery.

---

### `client.health()`

Calls `GET /v1/health` (no authentication required). Returns `status`, `version`
and `timestamp`.

### `client.usage()`

Calls `GET /v1/usage`. Returns the current month's counters and the account tier's
limits: `embed_count`, `verify_count`, `period` (`YYYY-MM`), `tier`, `embed_limit`,
`verify_limit`.

---

## Error Handling

```python
from mnemo_sdk import MnemoAPIError, MnemoErrorCode, MnemoValidationError

try:
    result = client.verify(vector)
except MnemoAPIError as e:
    if e.code is MnemoErrorCode.QUOTA_EXCEEDED:
        # 402 {"code": "insufficient_credits"}: the plan's included verifications
        # are used up. API keys have no overage, no top-ups and never x402.
        print("Verification allowance exhausted")
    else:
        print(f"Server error: {e.status_code} — {e}")
except MnemoValidationError as e:
    print(f"Invalid input: {e}")
```

