# SDK Usage Guide

## Core Methods

### `client.embed(vector, model_id, ...)`

Embeds an invisible watermark into a vector and returns a tracked result.

**Parameters:**
- `vector` — list of floats (your embedding)
- `model_id` — string identifying the embedding model
- `model_version` — optional version string (default `"1.0"`)
- `policy` — optional `PolicyConfig` for access control

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

---

### `client.verify(vector)`

Attempts to identify a watermarked vector.

**Parameters:**
- `vector` — list of floats to verify

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

---

### `client.health()`

Returns server health status.

### `client.usage()`

Returns usage statistics for your API key.

---

## Error Handling

```python
from mnemo_sdk import MnemoAPIError, MnemoValidationError

try:
    result = client.embed(vector, model_id="test")
except MnemoAPIError as e:
    print(f"Server error: {e.status_code} — {e}")
except MnemoValidationError as e:
    print(f"Invalid input: {e}")
```

## Batch Operations

```python
from mnemo_sdk import MnemoBatch

batch = MnemoBatch(client)
results = batch.embed_batch(vectors, model_id="test")
checks = batch.verify_batch(vectors)
```
