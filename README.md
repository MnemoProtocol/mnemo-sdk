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
- **Batch** operations for embedding and verifying multiple vectors at once.
- **Policy configuration** to control watermark lifetime, region, and usage class.
- **Automatic retries** with exponential back-off on rate limits and transient errors.
- **Numpy integration** for seamless conversion between lists and arrays.

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

## Batch Operations

```python
from mnemo_sdk import MnemoBatch

batch = MnemoBatch(client)
results = batch.embed_batch(vectors=[v1, v2, v3], model_id="model-id")
checks = batch.verify_batch(vectors=[r.watermarked_vector for r in results])
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
