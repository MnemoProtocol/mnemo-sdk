# Quickstart Guide

This guide shows how to use the Mnemo SDK to embed and verify watermarks via the Mnemo HTTP API.

## Prerequisites

- A Mnemo API key (sign up at https://app.mnemo.ai)
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

The client sends all requests to `https://api.mnemo.ai` by default. To use a different endpoint:

```python
client = MnemoClient(api_key="your-api-key", api_url="https://custom.endpoint.ai")
```

## Step 2: Embed a Watermark

Send a `POST /v1/embed` request to embed an invisible watermark into a vector:

```python
result = client.embed(
    vector=[0.1, 0.2, 0.3, 0.4, 0.5],
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

print(check.verified)    # True if a watermark was detected
print(check.confidence)  # Confidence score (0.0 to 1.0)
print(check.vector_uid)  # The watermark UID, if detected
print(check.policy_ok)   # Whether the watermark policy is still valid
```

## Step 4: Check Service Health

Send a `GET /v1/health` request:

```python
health = client.health()
print(health)  # {"status": "ok", "version": "..."}
```

## Step 5: Check Usage

Send a `GET /v1/usage` request to see your current usage statistics:

```python
usage = client.usage()
print(usage)  # {"embeds": ..., "verifications": ..., "quota_remaining": ...}
```

## Using Policies

Policies let you control watermark behavior such as lifetime and region:

```python
from mnemo_sdk import create_policy

policy = create_policy(
    ttl_hours=168,          # Watermark valid for 7 days
    usage_class="premium",
    retention="hot",
    region="eu",
)

result = client.embed(
    vector=[0.1, 0.2, 0.3],
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
    print(f"HTTP {e.status_code}: {e.message} (code: {e.code})")
except MnemoValidationError as e:
    print(f"Input error: {e.message}")
```

The client automatically retries on HTTP 429 (rate limit) responses, using the `Retry-After` header when available.

## HTTP Endpoints Summary

| Method | Endpoint           | Description                    |
|--------|--------------------|--------------------------------|
| POST   | `/v1/embed`        | Embed a watermark              |
| POST   | `/v1/verify`       | Verify a vector                |
| GET    | `/v1/health`       | Service health check           |
| GET    | `/v1/usage`        | Account usage statistics       |
