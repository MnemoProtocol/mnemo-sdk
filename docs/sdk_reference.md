# SDK Reference

Complete reference for all public classes, functions, and types in the Mnemo SDK.

---

## MnemoClient

The primary client for interacting with the Mnemo watermarking API.

### Constructor

```python
MnemoClient(
    api_key: str,
    *,
    api_url: str = "https://api.mnemo.ai",
    timeout: int = 30,
    retry_attempts: int = 3,
    config: Optional[MnemoConfig] = None,
)
```

**Parameters:**

| Name             | Type                    | Default                   | Description                              |
|------------------|-------------------------|---------------------------|------------------------------------------|
| `api_key`        | `str`                   | (required)                | Your Mnemo API key.                      |
| `api_url`        | `str`                   | `https://api.mnemo.ai`   | Base URL for the Mnemo API.              |
| `timeout`        | `int`                   | `30`                      | Request timeout in seconds.              |
| `retry_attempts` | `int`                   | `3`                       | Number of retry attempts on failure.     |
| `config`         | `Optional[MnemoConfig]` | `None`                    | Config object (overrides other params).  |

### Methods

#### `embed(vector, model_id, *, model_version="1.0", policy=None) -> EmbedResult`

Embed a watermark into a vector via `POST /v1/embed`.

| Parameter       | Type                       | Description                                |
|-----------------|----------------------------|--------------------------------------------|
| `vector`        | `list[float]` or `ndarray` | The input vector.                          |
| `model_id`      | `str`                      | Identifier for the source model.           |
| `model_version` | `str`                      | Model version string (default `"1.0"`).    |
| `policy`        | `Optional[dict]`           | Policy dict from `create_policy` or `PolicyBuilder`. |

**Returns:** `EmbedResult`

#### `verify(vector) -> VerifyResult`

Verify a vector for a Mnemo watermark via `POST /v1/verify`.

| Parameter    | Type                       | Description                         |
|--------------|----------------------------|-------------------------------------|
| `vector`     | `list[float]` or `ndarray` | The vector to verify.               |

**Returns:** `VerifyResult`

#### `health() -> dict`

Check the health of the Mnemo API via `GET /v1/health`.

**Returns:** Dictionary with service health information.

#### `usage() -> dict`

Retrieve API usage statistics via `GET /v1/usage`.

**Returns:** Dictionary with usage data for the authenticated account.

---

## MnemoConfig

Configuration dataclass for `MnemoClient`.

```python
@dataclass
class MnemoConfig:
    api_key: str
    api_url: str = "https://api.mnemo.ai"
    timeout: int = 30
    retry_attempts: int = 3
```

| Field            | Type  | Default                 | Description                          |
|------------------|-------|-------------------------|--------------------------------------|
| `api_key`        | `str` | (required)              | Your Mnemo API key.                  |
| `api_url`        | `str` | `https://api.mnemo.ai`  | Base URL for the API.                |
| `timeout`        | `int` | `30`                    | Request timeout in seconds.          |
| `retry_attempts` | `int` | `3`                     | Number of retry attempts on failure. |

---

## EmbedResult

Dataclass returned from `MnemoClient.embed()`.

```python
@dataclass
class EmbedResult:
    vector_uid: str
    watermarked_vector: list[float]
    created_at: str
    dimensions: int
```

| Field                | Type             | Description                                  |
|----------------------|------------------|----------------------------------------------|
| `vector_uid`         | `str`            | Unique identifier for the watermark.         |
| `watermarked_vector` | `list[float]`    | The watermarked vector.                      |
| `created_at`         | `str`            | ISO 8601 timestamp of creation.              |
| `dimensions`         | `int`            | Number of dimensions in the vector.          |

### Methods

#### `to_numpy() -> numpy.ndarray`

Convert `watermarked_vector` to a numpy array. Raises `ImportError` if numpy is not installed.

---

## VerifyResult

Dataclass returned from `MnemoClient.verify()`.

```python
@dataclass
class VerifyResult:
    verified: bool
    confidence: float
    vector_uid: Optional[str] = None
    policy_ok: bool = False
```

| Field        | Type            | Description                                      |
|--------------|-----------------|--------------------------------------------------|
| `verified`   | `bool`          | `True` if a watermark was detected.              |
| `confidence` | `float`         | Confidence score between 0.0 and 1.0.            |
| `vector_uid` | `Optional[str]` | The watermark UID, if detected.                  |
| `policy_ok`  | `bool`          | Whether the watermark policy is still valid.     |

---

## PolicyConfig

Dataclass for watermark policy configuration.

```python
@dataclass
class PolicyConfig:
    ttl_hours: int = 720
    usage_class: str = "std"
    retention: str = "hot"
    region: str = "us"
```

| Field         | Type  | Default | Description                            |
|---------------|-------|---------|----------------------------------------|
| `ttl_hours`   | `int` | `720`   | Watermark time-to-live in hours.       |
| `usage_class` | `str` | `"std"` | Usage classification tier.             |
| `retention`   | `str` | `"hot"` | Retention tier (`"hot"`, `"warm"`, `"cold"`). |
| `region`      | `str` | `"us"`  | Deployment region.                     |

### Methods

#### `to_dict() -> dict`

Convert the policy to a plain dictionary suitable for passing to `MnemoClient.embed()`.

---

## PolicyBuilder

Fluent builder for constructing policy configuration dictionaries.

### Methods

| Method                         | Returns          | Description                              |
|--------------------------------|------------------|------------------------------------------|
| `ttl_hours(hours: int)`        | `PolicyBuilder`  | Set TTL in hours.                        |
| `ttl_days(days: int)`          | `PolicyBuilder`  | Set TTL in days (converted to hours).    |
| `usage_class(cls: str)`        | `PolicyBuilder`  | Set the usage class.                     |
| `retention(retention: str)`    | `PolicyBuilder`  | Set the retention tier.                  |
| `region(region: str)`          | `PolicyBuilder`  | Set the deployment region.               |
| `build()`                      | `dict`           | Build and return the policy dictionary.  |

### Example

```python
policy = (
    PolicyBuilder()
    .ttl_days(30)
    .usage_class("premium")
    .retention("cold")
    .region("eu")
    .build()
)
```

---

## create_policy

Convenience function to create a policy dictionary.

```python
def create_policy(
    *,
    ttl_hours: int = 720,
    usage_class: str = "std",
    retention: str = "hot",
    region: str = "us",
) -> dict
```

**Returns:** A dictionary suitable for passing to the `policy` parameter of `MnemoClient.embed()`.

---

## MnemoException

Base exception for all Mnemo SDK errors.

```python
class MnemoException(Exception):
    message: str
    code: MnemoErrorCode
    details: Optional[Any]
```

| Attribute | Type             | Description                    |
|-----------|------------------|--------------------------------|
| `message` | `str`            | Human-readable error message.  |
| `code`    | `MnemoErrorCode` | Structured error code.         |
| `details` | `Optional[Any]`  | Additional error details.      |

---

## MnemoAPIError

Raised when the Mnemo API returns an HTTP error response. Subclass of `MnemoException`.

```python
class MnemoAPIError(MnemoException):
    status_code: int
```

| Attribute     | Type  | Description              |
|---------------|-------|--------------------------|
| `status_code` | `int` | HTTP status code.        |

Inherits `message`, `code`, and `details` from `MnemoException`.

---

## MnemoValidationError

Raised when input validation fails before making an API request. Subclass of `MnemoException`.

Always uses `MnemoErrorCode.INVALID_INPUT` as its error code.

---

## MnemoErrorCode

Enum of standard error codes.

```python
class MnemoErrorCode(Enum):
    SUCCESS = "SUCCESS"
    INVALID_INPUT = "INVALID_INPUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    SERVER_ERROR = "SERVER_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    NOT_FOUND = "NOT_FOUND"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    UNAUTHORIZED = "UNAUTHORIZED"
```

---

## MnemoBatch

Batch operations for embedding and verifying multiple vectors in single API calls.

### Constructor

```python
MnemoBatch(client: MnemoClient)
```

### Methods

#### `embed_batch(vectors, model_id, *, model_version="1.0", policy=None) -> list[EmbedResult]`

Embed watermarks into multiple vectors via `POST /v1/embed/batch`.

| Parameter       | Type                                   | Description                           |
|-----------------|----------------------------------------|---------------------------------------|
| `vectors`       | `Iterable[list[float]]` or `ndarray`s | Collection of input vectors.          |
| `model_id`      | `str`                                  | Identifier for the source model.      |
| `model_version` | `str`                                  | Model version (default `"1.0"`).      |
| `policy`        | `Optional[dict]`                       | Policy applied to all vectors.        |

**Returns:** `list[EmbedResult]`

#### `verify_batch(vectors) -> list[VerifyResult]`

Verify multiple vectors via `POST /v1/verify/batch`.

| Parameter  | Type                                   | Description                  |
|------------|----------------------------------------|------------------------------|
| `vectors`  | `Iterable[list[float]]` or `ndarray`s | Collection of vectors.       |

**Returns:** `list[VerifyResult]`
