# Quickstart Guide

This guide shows how to use the Mnemo SDK to watermark embedding vectors and check them against your account via the Mnemo HTTP API.

## Prerequisites

- A Mnemo account API key (sign in at https://www.trymnemo.com/login)
- Python 3.9+

## Installation

```bash
pip install mnemo-protocol
```

## Step 1: Initialize the Client

```python
from mnemo_sdk import MnemoClient

client = MnemoClient(api_key="your-api-key")
```

The client sends all requests to `https://api.trymnemo.com` by default, with your key in the `X-API-Key` header. To use a different endpoint:

```python
client = MnemoClient(api_key="your-api-key", api_url="https://custom.endpoint.example")
```

## Step 2: Embed a Watermark

Send a `POST /v1/embed` request to get a measurably perturbed watermarked copy of a vector. Vectors must have 512–4096 finite numbers:

```python
import random

vector = [random.uniform(-1.0, 1.0) for _ in range(768)]  # stand-in for a real embedding

result = client.embed(
    vector=vector,
    model_id="text-embedding-3-small",
)

print(result.vector_uid)           # Unique identifier for this embed
print(result.watermarked_vector)   # The watermarked vector (same dimensionality)
print(result.dimensions)           # Number of dimensions
print(result.created_at)           # Timestamp
```

The returned `watermarked_vector` is a measurably perturbed copy of the original. Store it in your vector database in place of the original, and check retrieval quality on your own data before switching over.

## Step 3: Verify a Vector

Send a `POST /v1/verify` request to check whether a vector resolves to an object registered to your Mnemo account:

```python
check = client.verify(vector=result.watermarked_vector)

if check is None:
    print("not verified for this account")
elif check.vector_uid == result.vector_uid:
    print("verified: resolves to", check.vector_uid)  # the object you embedded
    print(check.policy_ok)   # Reflects at most the TTL set at embed time
else:
    # Resolves to another object registered to your account, not the one you expected.
    print("verified, but resolves to a different registered object:", check.vector_uid)
```

Decide on whether `verify()` returned a result and on its `vector_uid`. `confidence` is a relative signal, not a probability and not a threshold to apply yourself.

`verify()` returns `None` when the API answers `verified: false`: attribution to your account could not be shown, which is not proof that the vector belongs to anyone else. It is a normal result, not an error, and it counts as one verification.

## Step 4: Check Service Health

Send a `GET /v1/health` request:

```python
health = client.health()
print(health)  # {"status": "ok", "version": "...", "timestamp": "..."}
```

## Step 5: Check Usage

Send a `GET /v1/usage` request to see the current month's usage and your plan's limits:

```python
usage = client.usage()
print(usage)
# {"embed_count": ..., "verify_count": ..., "period": "YYYY-MM", "tier": "...",
#  "embed_limit": ..., "verify_limit": ...}
```

## API Keys and Billing

Calls made with an API key use the account's subscription plan: included monthly
verifications, no automatic overage, no top-ups, and never x402. Plans and prices:
https://www.trymnemo.com/pricing.

When the plan's verifications are used up, `POST /v1/verify` answers
`402 {"code": "insufficient_credits"}` with no `PAYMENT-REQUIRED` header, and the SDK
raises `MnemoAPIError` with `code == MnemoErrorCode.QUOTA_EXCEEDED`.

Agents without an account do not use this SDK: they use the Mnemo Agent API
directly (0.01 USD per healthy verification via x402 on Base or MPP on Tempo,
or 500 verifications for 5.00 USD). See
https://github.com/MnemoProtocol/mnemo-agent-protocol.

## Using Policies

Policies attach values such as a TTL and a region at embed time. Verify's `policy_ok` reflects at most the TTL; `usage_class`, `retention` and `region` are passed through but not evaluated by verify:

```python
from mnemo_sdk import create_policy

policy = create_policy(
    ttl_hours=168,          # 7 days
    usage_class="std",
    retention="hot",
    region="us",
)

result = client.embed(
    vector=vector,
    model_id="text-embedding-3-small",
    policy=policy,
)
```

## Error Handling

The SDK raises typed exceptions for different failure modes:

```python
from mnemo_sdk.errors import MnemoAPIError, MnemoValidationError

try:
    result = client.embed(vector=[0.1], model_id="model-id")
except MnemoAPIError as e:
    # e.code is a MnemoErrorCode, e.g. INVALID_INPUT for 400/422,
    # QUOTA_EXCEEDED for 402 insufficient_credits.
    print(f"HTTP {e.status_code}: {e.message} (code: {e.code})")
except MnemoValidationError as e:
    print(f"Input error: {e.message}")
```

The client retries `429` responses, waiting `Retry-After` when present (delta-seconds or an HTTP date; it does not sleep after the last attempt, and a wait longer than 60 seconds is raised at once as `RATE_LIMIT` with `retry_after` set). It also retries connection failures. `retry_attempts` is the total number of attempts per call, at least one. TLS and certificate errors are never retried.

`embed()` is not idempotent: each successful embed registers a new object. From 3.1.4 the SDK re-sends an embed only when the request certainly did not reach the server (a `429`, or a connection that was never established). After a read timeout or a dropped connection the outcome is unknown, so it raises `MnemoAPIError` (`code=NETWORK_ERROR`, `retryable=False`) instead of risking a second object. Retry it yourself only if a duplicate object is acceptable to you.

`verify()` sends an `Idempotency-Key` header: your `idempotency_key` verbatim, or a uuid4 generated for that call. The same value is sent on every internal retry of the call (including after timeouts), so a verify retried after a lost response is answered from the stored result instead of being counted again. Every `MnemoAPIError` raised by `verify()` carries the key it sent as `e.idempotency_key`. To retry the same verification yourself, pass it back: `verify(vector, idempotency_key=e.idempotency_key)`. If the first attempt is still in flight when a retry arrives, the server answers `409 request_in_progress` (`e.retryable` is `True`); retry later with the same key.

## HTTP Endpoints Summary

| Method | Endpoint           | Description                    |
|--------|--------------------|--------------------------------|
| POST   | `/v1/embed`        | Get a watermarked copy         |
| POST   | `/v1/verify`       | Check a vector against your account |
| GET    | `/v1/health`       | Service health check (no auth) |
| GET    | `/v1/usage`        | Account usage statistics       |

All authenticated requests use the `X-API-Key` header.
