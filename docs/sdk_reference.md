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

#### `embed(vector, model_id, *, model_version="1.0", policy=None, subject=None) -> EmbedResult`

Embed a watermark into a vector via `POST /v1/embed`.

| Parameter       | Type                       | Description                                |
|-----------------|----------------------------|--------------------------------------------|
| `vector`        | `list[float]` or `ndarray` | The input vector.                          |
| `model_id`      | `str`                      | Identifier for the source model.           |
| `model_version` | `str`                      | Model version string (default `"1.0"`).    |
| `policy`        | `Optional[dict]`           | Policy dict from `create_policy` or `PolicyBuilder`. |
| `subject`       | `Optional[Subject \| dict]` | Optional **raw** subject context. The server canonicalizes it into a tenant-scoped `subject_fingerprint` and (when enabled+configured) returns a server-issued `subject_proof`. The SDK passes it through unchanged and **rejects** any client-supplied `subject_fingerprint` / `trust_mode` / `proof*` field — trust is derived server-side. |

**Returns:** `EmbedResult` (with `subject_proof` set only when a subject was supplied and the server-side transport is enabled+configured).

#### `verify(vector, *, subject_proof=None) -> VerifyResult`

Verify a vector for a Mnemo watermark via `POST /v1/verify`.

| Parameter       | Type                        | Description                         |
|-----------------|-----------------------------|-------------------------------------|
| `vector`        | `list[float]` or `ndarray`  | The vector to verify.               |
| `subject_proof` | `Optional[SubjectProof \| dict]` | Optional **opaque, untrusted** carrier from a prior `embed`. The SDK transports it verbatim and never validates/verifies/interprets it — the **server** re-verifies it. It is consulted **only** on an oracle-only Case 3 verify under **STRICT** mode with FP-squash enabled (the provenance-grade, claim-bearing path); it does not run on every verify. |

**Returns:** `VerifyResult` (with `signals` populated when the server returns the diagnostic block). BALANCED/HIGH_RECALL are non-claim-bearing for subject-proof / oracle-only recovery.

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
    subject_proof: Optional[SubjectProof] = None
```

| Field                | Type             | Description                                  |
|----------------------|------------------|----------------------------------------------|
| `vector_uid`         | `str`            | Unique identifier for the watermark.         |
| `watermarked_vector` | `list[float]`    | The watermarked vector.                      |
| `created_at`         | `str`            | ISO 8601 timestamp of creation.              |
| `dimensions`         | `int`            | Number of dimensions in the vector.          |
| `subject_proof`      | `Optional[SubjectProof]` | Server-issued subject-proof carrier; present only when a `subject` was supplied AND the server-side transport is enabled+configured, else `None`. Opaque/untrusted — store it and replay on `verify`. |

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
    signals: Optional[VerifySignals] = None
```

| Field        | Type            | Description                                      |
|--------------|-----------------|--------------------------------------------------|
| `verified`   | `bool`          | `True` if a watermark was detected.              |
| `confidence` | `float`         | Confidence score between 0.0 and 1.0.            |
| `vector_uid` | `Optional[str]` | The watermark UID, if detected.                  |
| `policy_ok`  | `bool`          | Whether the watermark policy is still valid.     |
| `signals`    | `Optional[VerifySignals]` | Optional diagnostic arbitration breakdown (method, statuses, oracle metrics, `mode`, latency). `None` if the server omits it. |

---

## Subject

Optional **raw** subject context for `embed()`. Mirrors the runtime `V1SubjectRequest`. The SDK passes it through unchanged; the **server** derives the tenant-scoped `subject_fingerprint`. By construction this model has no `subject_fingerprint` / `trust_mode` / `proof*` fields — the client cannot supply trust.

```python
@dataclass
class Subject:
    subject_uri: str
    subject_type: str
    canonicalization_version: Optional[str] = None  # advisory; server pins its own
    object_id: Optional[str] = None
    parent_id: Optional[str] = None
    segment_id: Optional[str] = None
    offset: Optional[dict] = None
    adapters: Optional[dict] = None  # opaque; never read by the server for trust
```

`to_dict()` serializes to the wire shape, dropping `None`-valued optionals. A plain `dict` may be passed to `embed(subject=...)` instead of a `Subject`; a dict containing any server-derived trust field is rejected with `MnemoValidationError`.

---

## SubjectProof

Server-issued, **opaque and untrusted** carrier returned by `embed()` and replayed on `verify()`. Mirrors the runtime `V1SubjectProofResponse`. The SDK never validates, verifies, or interprets it — the **server** re-verifies it (a tenant-scoped, UID-bound HMAC) and only honors it on a STRICT oracle-only Case 3 verify under FP-squash. The original server payload is preserved verbatim so it round-trips byte-for-byte.

```python
@dataclass
class SubjectProof:
    version: Optional[str] = None
    proof_type: Optional[str] = None
    proof_key_id: Optional[str] = None
    tenant_id: Optional[str] = None
    subject_fingerprint: Optional[str] = None
    canonicalization_version: Optional[str] = None
    issued_at: Optional[float] = None
    expires_at: Optional[float] = None
    proof: Optional[str] = None
```

`SubjectProof.from_dict(d)` parses a server carrier (tolerant of missing/unknown fields). `to_dict()` returns the verbatim carrier to send back on `verify`. A plain `dict` may be passed to `verify(subject_proof=...)` instead.

---

## VerifySignals

Diagnostic arbitration breakdown carried on `VerifyResult.signals`. Mirrors the runtime `V1VerifySignals`. `mode` is the effective decision mode (`STRICT` | `BALANCED` | `HIGH_RECALL`); only **STRICT** is the provenance-grade / claim-bearing posture for subject-proof / compressed oracle-only recovery.

```python
@dataclass
class VerifySignals:
    method: Optional[str] = None
    spectral_status: Optional[str] = None
    oracle_status: Optional[str] = None
    oracle_best_dist: Optional[float] = None
    oracle_margin: Optional[float] = None
    oracle_candidate_count: Optional[int] = None
    mode: Optional[str] = None
    latency_ms: Optional[float] = None
```

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

