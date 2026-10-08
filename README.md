# Mnemo SDK

**Invisible, verifiable watermarks for AI-generated embeddings.**

`mnemo-protocol` is the Python client for the Mnemo API (`https://api.trymnemo.com`). It lets you embed invisible watermarks into embedding vectors and verify them later, with no changes to your model or downstream pipeline. All watermarking runs server-side; the SDK contains no algorithm code.

The SDK authenticates with an **account API key** (`X-API-Key`). It does not implement accountless agent namespaces or x402 payments — see [Agents without an account](#agents-without-an-account).

## Installation

```bash
pip install mnemo-protocol
```

The package is `mnemo-protocol` on PyPI and is imported as `mnemo_sdk`. The unrelated PyPI projects `mnemo-sdk` and `mnemo-ai` are not Mnemo's.

To use numpy helpers (e.g. `EmbedResult.to_numpy()`):

```bash
pip install "mnemo-protocol[numpy]"
```

## Quick Start

```python
import random

from mnemo_sdk import MnemoClient

client = MnemoClient(api_key="your-api-key")

# Stand-in for a real embedding. Vectors must have 512–4096 finite numbers.
vector = [random.uniform(-1.0, 1.0) for _ in range(768)]

# Embed a watermark
result = client.embed(vector=vector, model_id="text-embedding-3-small")
print(result.vector_uid)

# Verify a watermark — returns a VerifyResult, or None when nothing is detected
check = client.verify(vector=result.watermarked_vector)
if check is not None:
    print(check.verified, check.confidence, check.vector_uid)
```

## What the SDK calls

| Method | HTTP route | Auth |
|---|---|---|
| `embed()` | `POST /v1/embed` | `X-API-Key` |
| `verify()` | `POST /v1/verify` | `X-API-Key` |
| `health()` | `GET /v1/health` | none required |
| `usage()` | `GET /v1/usage` | `X-API-Key` |

There are no batch endpoints and no batch methods.

## API keys and billing

- Sign in at https://www.trymnemo.com/login to get an account and API keys.
- Calls made with an API key use that account's **subscription plan**: included monthly verifications, **no automatic overage, no top-ups, and never x402**. Plans and prices: https://www.trymnemo.com/pricing.
- When the plan's verifications are used up, `POST /v1/verify` answers `402 {"code": "insufficient_credits"}` with no `PAYMENT-REQUIRED` header. The SDK raises `MnemoAPIError` with `status_code == 402`, `code == MnemoErrorCode.QUOTA_EXCEEDED` and `details == {"code": "insufficient_credits"}`. There is nothing to pay from the SDK; the plan's allowance governs further verifications.
- `usage()` returns the current month's counters and limits: `embed_count`, `verify_count`, `period` (`YYYY-MM`), `tier`, `embed_limit`, `verify_limit`.

## Agents without an account

Autonomous agents that have no account use the **Mnemo Agent API** directly over HTTP: create a short-lived namespace, embed, read lineage, and pay **0.01 USDC per healthy verification via x402 on Base mainnet**. This SDK does not wrap that flow. The public contract, OpenAPI document and examples are at:

- https://github.com/MnemoProtocol/mnemo-agent-protocol
- https://www.trymnemo.com/agent-protocol.md

There is no public MCP server in v1; use the HTTP API.

## Features

- **Embed** watermarks into floating-point vectors (512–4096 dimensions).
- **Verify** whether a vector carries a Mnemo watermark and retrieve its `vector_uid`.
- **Trusted subject binding** (optional) — attach subject context at embed time and replay a server-issued proof at verify time.
- **Policy configuration** passed through to the server on embed.
- **Automatic retries** on rate limits (`429`, honouring `Retry-After`), connection errors and timeouts.
- **Numpy integration** for seamless conversion between lists and arrays.

## Trusted Subject Binding (optional)

You can optionally attach **subject context** to an embed and replay a
**server-issued proof** at verify time. Every subject-aware call routes to the
Mnemo core runtime, which performs all trust work centrally (canonicalization,
proof issuance, proof verification, tenant scoping, metering, and fail-closed
gating). **The SDK is transport only — it never derives a fingerprint, mints a
proof, validates a proof, or interprets corroboration.**

```python
from mnemo_sdk import MnemoClient, Subject

client = MnemoClient(api_key="your-api-key")

# Embed with subject context (RAW context — the server derives the fingerprint).
result = client.embed(
    vector=vector,  # 512–4096 floats
    model_id="text-embedding-3-small",
    subject=Subject(
        subject_uri="mnemo://subj/your-tenant/document/doc-123",
        subject_type="document",
        # optional: object_id, parent_id, segment_id, offset, adapters (opaque)
    ),
)

# `result.subject_proof` is a server-issued carrier — present only when the
# server-side subject-proof transport is enabled and configured; otherwise None.
proof = result.subject_proof  # opaque; store it alongside your record

# Later, replay the proof verbatim on verify. The SDK sends it untouched; the
# server re-verifies it.
check = client.verify(vector=result.watermarked_vector, subject_proof=proof)
```

How it works and what to expect:

- **`subject` is raw client context** sent to the server. You provide
  `subject_uri` + `subject_type` (and optional locators/adapters). The **server
  derives** the tenant-scoped `subject_fingerprint`; the SDK never computes it,
  and it rejects any attempt to pass `subject_fingerprint` / `trust_mode` /
  `proof*` fields.
- **`subject_proof` is an opaque, server-issued carrier.** Treat it as a token:
  store it, and pass it back on `verify`. The SDK does **not** validate, verify,
  or interpret it — the server re-verifies it (a tenant-scoped, UID-bound HMAC).
- **The proof only matters in a narrow case.** It is consulted **only** for an
  oracle-only "Case 3" verification under **STRICT** mode (the provenance-grade,
  claim-bearing posture) with the server's FP-squash gate enabled. It does **not**
  run on every verify and should not be assumed to add latency on normal paths.
  **BALANCED / HIGH_RECALL are non-claim-bearing** for subject-proof / compressed
  oracle-only recovery.
- Missing or invalid proofs **fail closed** server-side; the SDK simply transports
  whatever you pass.

## Configuration

```python
from mnemo_sdk import MnemoClient, MnemoConfig

config = MnemoConfig(
    api_key="your-api-key",
    api_url="https://api.trymnemo.com",  # the default
    timeout=30,
    retry_attempts=3,
)
client = MnemoClient(api_key="", config=config)
```

## Policy Configuration

```python
from mnemo_sdk import create_policy, PolicyBuilder

# Convenience function
policy = create_policy(ttl_hours=168, usage_class="std", region="us")

# Fluent builder
policy = (
    PolicyBuilder()
    .ttl_days(30)
    .usage_class("internal")
    .retention("cold")
    .region("us")
    .build()
)

result = client.embed(vector=vector, model_id="model-id", policy=policy)
```

## Error Handling

```python
from mnemo_sdk import MnemoAPIError, MnemoErrorCode, MnemoValidationError

try:
    check = client.verify(vector=vector)
except MnemoAPIError as e:
    if e.code is MnemoErrorCode.QUOTA_EXCEEDED:
        # 402 insufficient_credits: the plan's included verifications are used up.
        print("Verification allowance exhausted:", e.details)
    else:
        print(f"API error {e.status_code}: {e.message}")
except MnemoValidationError as e:
    print(f"Validation error: {e.message}")
```

## Retries

The client retries `429` responses (waiting `Retry-After` when present) and
connection errors or timeouts, up to `retry_attempts` times. `verify()` does not
send an `Idempotency-Key`, so a verify retried after a lost response may be
counted again against the plan; pass `retry_attempts=1` if you need at most one
attempt per call.

## API Reference

Full reference documentation is in the [docs/](https://github.com/MnemoProtocol/mnemo-sdk/tree/main/docs) directory:

- [Quickstart Guide](https://github.com/MnemoProtocol/mnemo-sdk/blob/main/docs/quickstart.md)
- [SDK Reference](https://github.com/MnemoProtocol/mnemo-sdk/blob/main/docs/sdk_reference.md)
- [Guarantees and Limitations](https://github.com/MnemoProtocol/mnemo-sdk/blob/main/docs/GUARANTEES.md)

## Requirements

- Python 3.9+
- `requests` library (installed automatically)

## License

Proprietary. See [LICENSE](https://github.com/MnemoProtocol/mnemo-sdk/blob/main/LICENSE) and [TERMS.md](https://github.com/MnemoProtocol/mnemo-sdk/blob/main/TERMS.md).
