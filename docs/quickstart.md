# Quickstart Guide

This guide shows how to use the Mnemo SDK to embed and verify watermarks via the Mnemo HTTP API.

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

Send a `POST /v1/embed` request to embed an invisible watermark into a vector. Vectors must have 512–4096 finite numbers:

```python
import random

vector = [random.uniform(-1.0, 1.0) for _ in range(768)]  # stand-in for a real embedding

result = client.embed(
    vector=vector,
    model_id="text-embedding-3-small",
)

print(result.vector_uid)           # Unique watermark identifier
print(result.watermarked_vector)   # The watermarked vector (same dimensionality)
print(result.dimensions)           # Number of dimensions
print(result.created_at)           # Timestamp
```

The returned `watermarked_vector` is a drop-in replacement for the original. Store it in your vector database as you normally would.

## Step 3: Verify a Vector

Send a `POST /v1/verify` request to check whether a vector contains a Mnemo watermark:

```python
check = client.verify(vector=result.watermarked_vector)

if check is None:
    print("No watermark detected.")
else:
    print(check.verified)    # Always True when a result is returned
    print(check.confidence)  # Confidence score (0.0 to 1.0)
    print(check.vector_uid)  # The watermark UID
    print(check.policy_ok)   # Whether the watermark policy is still valid
```

`verify()` returns `None` when no watermark is detected.

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
directly (0.01 USDC per healthy verification via x402 on Base mainnet). See
https://github.com/MnemoProtocol/mnemo-agent-protocol.

## Using Policies

Policies let you control watermark behavior such as lifetime and region:

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

The client automatically retries on HTTP 429 (rate limit) responses, using the `Retry-After` header when available, and on connection errors and timeouts. `verify()` sends an `Idempotency-Key` header: your `idempotency_key` verbatim, or a uuid4 generated for that call. The same value is sent on every internal retry of the call, so a verify retried after a lost response is answered from the stored result instead of being counted again. Pass your own `idempotency_key` to make a retry that you issue (a second `verify()` call for the same request) idempotent too. If the first attempt is still in flight when a retry arrives, the server answers `409 request_in_progress` (raised as `MnemoAPIError`); retry later with the same key.

## HTTP Endpoints Summary

| Method | Endpoint           | Description                    |
|--------|--------------------|--------------------------------|
| POST   | `/v1/embed`        | Embed a watermark              |
| POST   | `/v1/verify`       | Verify a vector                |
| GET    | `/v1/health`       | Service health check (no auth) |
| GET    | `/v1/usage`        | Account usage statistics       |

All authenticated requests use the `X-API-Key` header.
