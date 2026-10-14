# Mnemo SDK (Python)

**Official Python client for the Mnemo API (`https://api.trymnemo.com`): watermark embedding vectors, then check whether a vector resolves to an object registered to your own Mnemo account.**

**Identity:** PyPI distribution [`mnemo-protocol`](https://pypi.org/project/mnemo-protocol/), imported as `mnemo_sdk`, published from the GitHub org [MnemoProtocol](https://github.com/MnemoProtocol). Mnemo here is the embedding-vector provenance API at trymnemo.com (GitHub MnemoProtocol; PyPI mnemo-protocol, imported as mnemo_sdk). It is not the unrelated PyPI packages mnemo, mnemo-sdk, mnemo-ai or mnemo-mcp, and not an AI-memory app or MCP server.

**What it is:** Mnemo is an HTTP API for embedding vectors. `embed()` returns a measurably perturbed watermarked copy and a `vector_uid`; store and use that copy. `verify()` checks whether a vector you submit resolves to an object registered to your account. Not a vector database. This SDK covers the **API-key path only** (`X-API-Key`, subscription plan, never x402); it does not implement accountless namespaces, lineage or x402 payments.

```bash
pip install mnemo-protocol
```

```python
import os
import random

from mnemo_sdk import MnemoClient

client = MnemoClient(api_key=os.environ["MNEMO_API_KEY"])  # account API key, sent as X-API-Key

# Stand-in for your real embedding: 512–4096 finite numbers.
vector = [random.uniform(-1.0, 1.0) for _ in range(768)]

result = client.embed(vector=vector, model_id="text-embedding-3-small")
# Store result.watermarked_vector in place of `vector`, and keep result.vector_uid.

check = client.verify(vector=result.watermarked_vector)
if check is None:
    # A normal result, not an error: attribution to this account could not be shown.
    print("not verified for this account")
else:
    print("verified:", check.vector_uid, check.confidence)
```

**What verify checks:** Mnemo Verify checks whether a submitted vector resolves to an object registered to the caller's Mnemo account or namespace; with this SDK the caller is your account. `verify()` returns `None` when the API answers `verified: false`: attribution to your account could not be shown, which is not proof that the vector belongs to anyone else. Mnemo does not establish truth, authorship, ownership or the source model of a vector ([Guarantees and Limitations](https://github.com/MnemoProtocol/mnemo-sdk/blob/main/docs/GUARANTEES.md)).

**Links:** [SDK docs](https://www.trymnemo.com/docs/sdk?src=github) · [OpenAPI 3.1](https://www.trymnemo.com/openapi.json) (HTTP contract, incl. `/v1/embed` and `/v1/verify` with `X-API-Key`) · [Agent protocol](https://github.com/MnemoProtocol/mnemo-agent-protocol) (accountless agents, x402) · [PyPI](https://pypi.org/project/mnemo-protocol/) · [Terms of Service](https://www.trymnemo.com/terms) · API keys: a person signs in at https://www.trymnemo.com/login · Plans: https://www.trymnemo.com/pricing

**License:** Mnemo SDK License v2.0 (proprietary; [LICENSE](https://github.com/MnemoProtocol/mnemo-sdk/blob/main/LICENSE)); see the License and Legal sections below.

## Installation

```bash
pip install mnemo-protocol
```

The package is `mnemo-protocol` on PyPI and is imported as `mnemo_sdk`.

To use numpy helpers (e.g. `EmbedResult.to_numpy()`):

```bash
pip install "mnemo-protocol[numpy]"
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
- **Verify** whether a vector resolves to an object registered to your Mnemo account, and retrieve its `vector_uid`.
- **Trusted subject binding** (optional) — attach subject context at embed time and replay a server-issued proof at verify time.
- **Policy configuration** passed through to the server on embed.
- **Automatic retries** on rate limits (`429`, honouring `Retry-After`), connection errors and timeouts.
- **Numpy integration** for seamless conversion between lists and arrays.

## Trusted Subject Binding (optional)

You can optionally attach **subject context** to an embed and replay a
**server-issued proof** at verify time. Every subject-aware call routes to the
Mnemo service, which processes the subject and issues and checks any proof.
**The SDK is transport only — it never creates, validates, or interprets a
proof.**

```python
from mnemo_sdk import MnemoClient, Subject

client = MnemoClient(api_key="your-api-key")

# Embed with subject context (client context — the service processes it).
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
  `subject_uri` + `subject_type` (and optional locators/adapters). The Mnemo
  service processes it; the SDK only transports it, and it rejects any attempt to
  pass the service-set fields `subject_fingerprint` / `trust_mode` / `proof*`.
- **`subject_proof` is an opaque, server-issued carrier.** Treat it as a token:
  store it, and pass it back on `verify`. The SDK does **not** validate, verify,
  or interpret it — only the service can check it. It may be absent if the
  feature is not enabled.
- The service decides when a proof is used; passing one does not imply extra
  work or latency on every verify.
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
connection errors or timeouts, up to `retry_attempts` times. `verify()` sends an `Idempotency-Key` header: your `idempotency_key` verbatim, or a uuid4 generated for that call. The same value is sent on every internal retry of the call, so a verify retried after a lost response is answered from the stored result instead of being counted again. Pass your own `idempotency_key` to make a retry that you issue (a second `verify()` call for the same request) idempotent too. If the first attempt is still in flight when a retry arrives, the server answers `409 request_in_progress` (raised as `MnemoAPIError`); retry later with the same key.

## API Reference

Full reference documentation is in the [docs/](https://github.com/MnemoProtocol/mnemo-sdk/tree/main/docs) directory:

- [Quickstart Guide](https://github.com/MnemoProtocol/mnemo-sdk/blob/main/docs/quickstart.md)
- [SDK Reference](https://github.com/MnemoProtocol/mnemo-sdk/blob/main/docs/sdk_reference.md)
- [Guarantees and Limitations](https://github.com/MnemoProtocol/mnemo-sdk/blob/main/docs/GUARANTEES.md)

## Requirements

- Python 3.9+
- `requests` library (installed automatically)

## License

Mnemo SDK License v2.0 (proprietary; governed by Wyoming law). See [LICENSE](https://github.com/MnemoProtocol/mnemo-sdk/blob/main/LICENSE). You may use the SDK for development, evaluation, testing and production integration, and you may distribute the unmodified SDK only as incorporated into, or as a required dependency of, your own application that interoperates with Mnemo. Standalone resale or sublicensing of the SDK is not permitted. The SDK license is separate from access to the Mnemo hosted Services: the free trial lasts at most 30 days and 10,000 verifications in total, ending earlier when the allowance is used up. Continued access to Mnemo's hosted Services after any applicable trial requires a valid paid Service entitlement or other access expressly authorized by Mnemo. A paid Service entitlement may be provided through a subscription or another supported paid access mechanism.

## Legal

Use of the Mnemo API, including through an automated agent, script, SDK, wallet or other client, constitutes acceptance of the Mnemo Terms of Service on behalf of the operator and of the person or entity on whose behalf it acts. [Terms of Service](https://www.trymnemo.com/terms) (version 2026-10-12) · [Privacy Policy](https://www.trymnemo.com/privacy) · [Pricing](https://www.trymnemo.com/pricing) · Security reports: security@trymnemo.com (see [SECURITY.md](SECURITY.md)).

Only these four files are MIT-licensed, as stated in `examples/LICENSE`, so you can copy and adapt them freely: `examples/quickstart.py`, `examples/embed_example.py`, `examples/verify_example.py` and `examples/subject_binding_example.py`. The MIT license grants no patent rights. Everything else in this repository, including the `mnemo_sdk` package, is licensed under the Mnemo SDK License (`LICENSE`). Neither license grants rights in Mnemo's hosted Services, verification technology or patents (patent pending). Use of the Services is governed by the [Terms of Service](https://www.trymnemo.com/terms), which incorporate the [Data Processing Addendum](https://www.trymnemo.com/dpa) automatically where applicable.

Copyright © Mnemo LLC. All rights reserved. Patent pending. Viewing this repository does not grant a license; rights are granted only as expressly stated in the applicable license and Terms of Service.
