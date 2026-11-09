# Mnemo SDK (Python)

**Official Python client for the Mnemo API (`https://api.trymnemo.com`): watermark embedding vectors, then check whether a vector resolves to an object registered to your own Mnemo account.**

**Identity:** Mnemo here is the embedding-vector provenance API at trymnemo.com (GitHub [MnemoProtocol](https://github.com/MnemoProtocol); PyPI [mnemo-protocol](https://pypi.org/project/mnemo-protocol/), imported as mnemo_sdk). It is not the unrelated PyPI packages mnemo, mnemo-sdk, mnemo-ai or mnemo-mcp, and not an AI-memory app or MCP server.

**What it is:** Mnemo is an HTTP API for embedding vectors. `embed()` returns a measurably perturbed watermarked copy and a `vector_uid`; store and use that copy. `verify()` checks whether a vector you submit resolves to an object registered to your account. Not a vector database. This SDK covers the **API-key path only** (`X-API-Key`, subscription plan, never x402); it does not implement accountless namespaces, lineage or x402 payments.

**Provenance:** in Mnemo, provenance means a vector resolves to a `vector_uid` that Mnemo issued at embed time and that is still attributable to the account or namespace that issued it. Mnemo is not a similarity search. A nearest-neighbour search returns what is close to a vector; verify answers a narrower question, whether a vector you submit resolves to an object registered to your account.

**Use it when** you produce or store embeddings and later need to check whether a vector you hold (for example one returned by retrieval) resolves to an object registered to your own account, or (through the HTTP API, not this SDK) need to record and read a verified parent-to-child derivation.

**Not for:** vectors never embedded through Mnemo (there is no retroactive coverage); vectors issued to another account or namespace (verify cannot check another party's vectors); similarity search or storage; judging truth, authorship, ownership or the source model; file or document authenticity.

**Lineage (HTTP API, not in this SDK):** an embed may name one parent you own; Mnemo verifies the parent before it creates the child. `GET /v1/lineage/{vector_uid}` (with your `X-API-Key`, or a namespace capability) re-verifies every link on each read and returns the chain, or `409` when a link no longer verifies. Lineage records which parent you named, not what the transformation did. See §7 of the [agent protocol](https://www.trymnemo.com/agent-protocol.md).

**Get an API key:** [sign in or create a workspace](https://www.trymnemo.com/login?next=/platform/quickstart&utm_source=mnemo-sdk&utm_medium=readme&utm_campaign=mnemo-readme&utm_content=get-api-key) (a person signs in), then set `MNEMO_API_KEY` for the sample below.

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
expected_uid = result.vector_uid

check = client.verify(vector=result.watermarked_vector)
if check is None:
    # A normal result, not an error, and it counts as one verification:
    # attribution to this account could not be shown.
    print("not verified for this account")
elif check.vector_uid == expected_uid:
    print("verified: resolves to", check.vector_uid)
else:
    # Registered to your account, but to another of your objects, not this one.
    print("verified, but resolves to a different registered object:", check.vector_uid)
```

`verify()` returns a `VerifyResult` (`verified`, `confidence`, `vector_uid`, `policy_ok`, `signals`) when the API answers `verified: true`, and `None` when it answers `verified: false`. Decide on that, not on `confidence` or `policy_ok`. When you know which object a vector should be, also compare `check.vector_uid` with the `vector_uid` you stored at embed time.

**What verify checks:** Mnemo Verify checks whether a submitted vector resolves to an object registered to the caller's Mnemo account or namespace; with this SDK the caller is your account. `verify()` returns `None` when the API answers `verified: false`: attribution to your account could not be shown, which is not proof that the vector belongs to anyone else. Mnemo does not establish truth, authorship, ownership or the source model of a vector ([Guarantees and Limitations](https://github.com/MnemoProtocol/mnemo-sdk/blob/main/docs/GUARANTEES.md)).

**Links:** [SDK docs](https://github.com/MnemoProtocol/mnemo-sdk/tree/main/docs) · [OpenAPI 3.1](https://www.trymnemo.com/openapi.json) (HTTP contract, incl. `/v1/embed` and `/v1/verify` with `X-API-Key`) · [Agent protocol](https://github.com/MnemoProtocol/mnemo-agent-protocol) (accountless agents, x402 or MPP) · [PyPI](https://pypi.org/project/mnemo-protocol/) · [Terms of Service](https://www.trymnemo.com/terms) · API keys: a person signs in at https://www.trymnemo.com/login · Plans: https://www.trymnemo.com/pricing

**License:** Mnemo SDK License v2.0 (proprietary; [LICENSE](https://github.com/MnemoProtocol/mnemo-sdk/blob/main/LICENSE)); see the License and Legal sections below.

## Installation

Install with `pip install mnemo-protocol` (shown above). The package is `mnemo-protocol` on PyPI and is imported as `mnemo_sdk`.

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

Autonomous agents that have no account use the **Mnemo Agent API** directly over HTTP: create a short-lived namespace, embed, read lineage, and pay **0.01 USD per healthy verification via x402 on Base or MPP on Tempo, or buy 500 verifications for 5.00 USD**. This SDK does not wrap that flow. The public contract, OpenAPI document and examples are at:

- https://github.com/MnemoProtocol/mnemo-agent-protocol
- https://www.trymnemo.com/agent-protocol.md

There is no public MCP server in v1; use the HTTP API.

## Features

- **Embed** watermarks into floating-point vectors (512–4096 dimensions).
- **Verify** whether a vector resolves to an object registered to your Mnemo account, and retrieve its `vector_uid`.
- **Trusted subject binding** (optional) — attach subject context at embed time and replay a server-issued proof at verify time.
- **Policy configuration** passed through to the server on embed.
- **Automatic retries** on rate limits (`429`, honouring `Retry-After`) and on connections that were never established. `verify()`, `health()` and `usage()` also retry timeouts and dropped connections (`verify()` with the same `Idempotency-Key`); `embed()` is not re-sent once it may have reached the server.
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
client = MnemoClient(config=config)
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
    elif e.retryable:
        # Transient (429, 409 request_in_progress, 503 verification_unavailable,
        # connection failures): safe to call again, later.
        print(f"Retry later ({e.server_code or e.code.value}), retry_after={e.retry_after}")
    else:
        print(f"API error {e.status_code} {e.server_code}: {e.message}")
except MnemoValidationError as e:
    print(f"Validation error: {e.message}")
```

## Retries

The client retries `429` responses, waiting `Retry-After` when present (delta-seconds or an HTTP date; it does not sleep after the last attempt, and a wait longer than 60 seconds is raised at once as `RATE_LIMIT` with `retry_after` set). It also retries connection failures. `retry_attempts` is the total number of attempts per call, at least one. TLS and certificate errors are never retried.

`embed()` is not idempotent: each successful embed registers a new object. From 3.1.4 the SDK re-sends an embed only when the request certainly did not reach the server (a `429`, or a connection that was never established). After a read timeout or a dropped connection the outcome is unknown, so it raises `MnemoAPIError` (`code=NETWORK_ERROR`, `retryable=False`) instead of risking a second object. Retry it yourself only if a duplicate object is acceptable to you.

`verify()` sends an `Idempotency-Key` header: your `idempotency_key` verbatim, or a uuid4 generated for that call. The same value is sent on every internal retry of the call (including after timeouts), so a verify retried after a lost response is answered from the stored result instead of being counted again. Every `MnemoAPIError` raised by `verify()` carries the key it sent as `e.idempotency_key`. To retry the same verification yourself, pass it back: `verify(vector, idempotency_key=e.idempotency_key)`. If the first attempt is still in flight when a retry arrives, the server answers `409 request_in_progress` (`e.retryable` is `True`); retry later with the same key.

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

Use of the Mnemo API, including through an automated agent, script, SDK, wallet or other client, constitutes acceptance of the Mnemo Terms of Service on behalf of the operator and of the person or entity on whose behalf it acts. [Terms of Service](https://www.trymnemo.com/terms) (version 2026-10-12) · [Privacy Policy](https://www.trymnemo.com/privacy) · [Pricing](https://www.trymnemo.com/pricing) · Security reports: security@trymnemo.com (see [SECURITY.md](https://github.com/MnemoProtocol/mnemo-sdk/blob/main/SECURITY.md)).

Only these four files are MIT-licensed, as stated in `examples/LICENSE`, so you can copy and adapt them freely: `examples/quickstart.py`, `examples/embed_example.py`, `examples/verify_example.py` and `examples/subject_binding_example.py`. The MIT license grants no patent rights. Everything else in this repository, including the `mnemo_sdk` package, is licensed under the Mnemo SDK License (`LICENSE`). Neither license grants rights in Mnemo's hosted Services, verification technology or patents (patent pending). Use of the Services is governed by the [Terms of Service](https://www.trymnemo.com/terms), which incorporate the [Data Processing Addendum](https://www.trymnemo.com/dpa) automatically where applicable.

Copyright © Mnemo LLC. All rights reserved. Patent pending. Viewing this repository does not grant a license; rights are granted only as expressly stated in the applicable license and Terms of Service.
