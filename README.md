# Mnemo SDK

**Invisible, verifiable watermarks for AI-generated embeddings.**

Mnemo SDK is a Python client for the Mnemo watermarking API. It lets you embed invisible watermarks into embedding vectors and verify them later, with no changes to your model or downstream pipeline.

## Installation

```bash
pip install mnemo-protocol
```

To use numpy helpers (e.g. `EmbedResult.to_numpy()`):

```bash
pip install mnemo-protocol[numpy]
```

## Quick Start

```python
from mnemo_sdk import MnemoClient

client = MnemoClient(api_key="your-api-key")

# Embed a watermark
result = client.embed(
    vector=[0.1, 0.2, 0.3, 0.4, 0.5],
    model_id="text-embedding-3-small",
)
print(result.vector_uid)

# Verify a watermark
check = client.verify(vector=result.watermarked_vector)
print(check.verified, check.confidence)
```

## Features

- **Embed** watermarks into any floating-point vector via a simple API call.
- **Verify** whether a vector carries a Mnemo watermark and retrieve its metadata.
- **Trusted subject binding** (optional) — attach subject context at embed time and replay a server-issued proof at verify time.
- **Policy configuration** to control watermark lifetime, region, and usage class.
- **Automatic retries** with exponential back-off on rate limits and transient errors.
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
    vector=[0.1, 0.2, 0.3, 0.4, 0.5],
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
    api_url="https://api.mnemo.ai",
    timeout=30,
    retry_attempts=3,
)
client = MnemoClient(api_key="", config=config)
```

## Policy Configuration

```python
from mnemo_sdk import create_policy, PolicyBuilder

# Convenience function
policy = create_policy(ttl_hours=168, usage_class="premium", region="eu")

# Fluent builder
policy = (
    PolicyBuilder()
    .ttl_days(30)
    .usage_class("internal")
    .retention("cold")
    .region("us")
    .build()
)

result = client.embed(vector=vec, model_id="model-id", policy=policy)
```

## Error Handling

```python
from mnemo_sdk import MnemoClient
from mnemo_sdk.errors import MnemoAPIError, MnemoValidationError

try:
    result = client.embed(vector=vec, model_id="model-id")
except MnemoAPIError as e:
    print(f"API error {e.status_code}: {e.message}")
except MnemoValidationError as e:
    print(f"Validation error: {e.message}")
```

## API Reference

Full reference documentation is available in the [docs/](docs/) directory:

- [Quickstart Guide](docs/quickstart.md)
- [SDK Reference](docs/sdk_reference.md)

## Requirements

- Python 3.9+
- `requests` library (installed automatically)

## License

See [LICENSE](LICENSE) for details.
