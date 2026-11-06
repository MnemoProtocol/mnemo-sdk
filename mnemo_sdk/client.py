"""HTTP client for the Mnemo watermarking API."""

import json
import math
import time
import uuid
import warnings
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

import requests
from urllib3.exceptions import NewConnectionError

from mnemo_sdk.errors import MnemoAPIError, MnemoErrorCode, MnemoValidationError
from mnemo_sdk.types import (
    DEFAULT_API_URL,
    EmbedResult,
    MnemoConfig,
    PolicyConfig,
    Subject,
    SubjectProof,
    VerifyResult,
    VerifySignals,
)

_SDK_VERSION = "3.1.4"
_USER_AGENT = f"mnemo-protocol/{_SDK_VERSION} python"

# Longest Retry-After the client will sleep through on its own. A longer wait
# is raised at once as RATE_LIMIT with ``retry_after`` set, so a call never
# blocks for minutes inside the SDK.
_MAX_RETRY_AFTER_SECONDS = 60.0

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

# Service-set fields the client may NEVER supply on a subject; a subject carrying
# any of these is rejected client-side (the runtime would also reject it
# via extra="forbid", but we fail fast with a clear SDK error).
_FORBIDDEN_SUBJECT_KEYS = frozenset(
    {"subject_fingerprint", "trust_mode", "proof", "proof_type", "proof_digest", "proof_key_id"}
)


def _serialize_subject(subject) -> Dict[str, Any]:
    """Normalize a ``subject`` arg (Subject or dict) to the wire shape.

    The SDK is transport-only: it passes subject context through unchanged and
    rejects a dict that tries to supply a service-set field."""
    if isinstance(subject, Subject):
        return subject.to_dict()
    if isinstance(subject, dict):
        bad = _FORBIDDEN_SUBJECT_KEYS & set(subject)
        if bad:
            raise MnemoValidationError(
                "subject must not include server-derived fields "
                f"{sorted(bad)} — these fields are set by the service"
            )
        return dict(subject)
    raise MnemoValidationError("subject must be a Subject or a dict")


def _serialize_subject_proof(subject_proof) -> Dict[str, Any]:
    """Normalize a ``subject_proof`` arg (SubjectProof or dict) to the opaque
    carrier to send back to the server. The SDK does NOT validate, verify, or
    interpret it — it is passed through verbatim; the server re-verifies it."""
    if isinstance(subject_proof, SubjectProof):
        return subject_proof.to_dict()
    if isinstance(subject_proof, dict):
        return subject_proof
    raise MnemoValidationError("subject_proof must be a SubjectProof or a dict")


def _resolve_idempotency_key(idempotency_key) -> str:
    """Return the ``Idempotency-Key`` for ONE ``verify()`` call.

    A caller-supplied key is used verbatim. When the caller passes none, a fresh
    uuid4 is generated. The value is resolved once per call, before the first
    attempt, so every internal retry of that call carries the same key and the
    server can recognise a retry instead of charging for it again."""
    if idempotency_key is None:
        return str(uuid.uuid4())
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise MnemoValidationError("idempotency_key must be a non-empty string")
    return idempotency_key


class MnemoClient:
    """Python client for the Mnemo watermarking API.

    All watermarking operations are executed server-side; this client
    contains no algorithm code.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        api_url: str = DEFAULT_API_URL,
        timeout: int = 30,
        retry_attempts: int = 3,
        config: Optional[MnemoConfig] = None,
    ) -> None:
        if config is not None:
            self._api_key = config.api_key
            self._api_url = config.api_url.rstrip("/")
            self._timeout = config.timeout
            self._retry_attempts = config.retry_attempts
        else:
            if api_key is None:
                raise MnemoValidationError("api_key is required (or pass config=MnemoConfig(...))")
            self._api_key = api_key
            self._api_url = api_url.rstrip("/")
            self._timeout = timeout
            self._retry_attempts = retry_attempts
        # retry_attempts is the total number of attempts per call; a call
        # always makes at least one request.
        self._retry_attempts = max(1, self._retry_attempts)
        _warn_if_cleartext(self._api_url)

        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-API-Key": self._api_key,
                "User-Agent": _USER_AGENT,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def __repr__(self) -> str:
        # Never include the API key.
        return (
            f"MnemoClient(api_url={self._api_url!r}, timeout={self._timeout!r}, "
            f"retry_attempts={self._retry_attempts!r})"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed(
        self,
        vector,
        model_id: str,
        *,
        model_version: str = "1.0",
        policy: Optional[Dict[str, Any]] = None,
        subject=None,
    ) -> EmbedResult:
        """Embed a watermark into a vector.

        Args:
            vector: Input vector (list or numpy array).
            model_id: Identifier for the model that produced the vector.
            model_version: Version of the model.
            policy: Optional policy dict (use ``create_policy`` or ``PolicyBuilder``).
            subject: Optional subject context (``Subject`` or dict) — client
                context only. The Mnemo service processes it and (when the feature
                is enabled) returns an opaque ``subject_proof`` token on the
                result. The SDK only transports it and rejects a dict that tries
                to supply a service-set field.

        Returns:
            EmbedResult with the watermarked vector and metadata. ``subject_proof``
            is set only when a subject was supplied AND the server-side transport is
            enabled+configured; otherwise it is None.
        """
        payload: Dict[str, Any] = {
            "vector": _serialize_vector(vector),
            "model_id": model_id,
            "model_version": model_version,
        }
        if policy is not None:
            payload["policy"] = policy
        if subject is not None:
            payload["subject"] = _serialize_subject(subject)

        # embed registers a new object and the API has no idempotent replay
        # for it, so the SDK never re-sends an embed whose request may already
        # have reached the server (see _post_with_retry).
        data = self._post_with_retry("/v1/embed", payload, idempotent=False)
        _require_fields(data, ("vector_uid", "watermarked_vector", "created_at", "dimensions"), "embed")
        raw_proof = data.get("subject_proof")
        return EmbedResult(
            vector_uid=data["vector_uid"],
            watermarked_vector=data["watermarked_vector"],
            created_at=data["created_at"],
            dimensions=data["dimensions"],
            subject_proof=SubjectProof.from_dict(raw_proof) if raw_proof else None,
        )

    def verify(
        self,
        vector,
        *,
        subject_proof=None,
        idempotency_key: Optional[str] = None,
    ) -> Optional[VerifyResult]:
        """Check whether a vector resolves to an object registered to the caller's account.

        Every call sends an ``Idempotency-Key`` header. The same value is sent on
        each internal retry of the call (rate limit, connection error, timeout),
        so the server can recognise a retry after a lost response and answer it
        from the stored result instead of charging for it a second time. If the
        first attempt is still being processed when a retry arrives, the server
        answers 409 (``request_in_progress``), raised as ``MnemoAPIError``.

        Args:
            vector: Vector to verify (list or numpy array).
            idempotency_key: Optional key to send as ``Idempotency-Key``. Pass
                your own to make a retry that YOU issue (a second ``verify()``
                call for the same request) idempotent as well. When omitted, the
                SDK generates a uuid4 for this call only; two separate calls
                never share a generated key.
            subject_proof: Optional opaque proof token (``SubjectProof`` or dict)
                issued by the service on a prior ``embed``. The SDK passes it
                through verbatim and never validates or interprets it; only the
                service can check it, and the service decides when it is used.

        Returns:
            VerifyResult when the API answers verified=true; None when the API
            answers verified=false (attribution to the caller's account could
            not be shown; a normal result that counts as one verification).
        """
        payload: Dict[str, Any] = {
            "vector": _serialize_vector(vector),
        }
        if subject_proof is not None:
            payload["subject_proof"] = _serialize_subject_proof(subject_proof)

        # Resolved ONCE per call, outside the retry loop.
        key = _resolve_idempotency_key(idempotency_key)
        headers = {"Idempotency-Key": key}

        try:
            data = self._post_with_retry("/v1/verify", payload, headers=headers)
        except MnemoAPIError as exc:
            # Expose the key so the caller can retry this same verification
            # (verify(..., idempotency_key=exc.idempotency_key)) without it
            # being counted twice.
            exc.idempotency_key = key
            raise

        if not data.get("verified"):
            return None

        vector_uid = data.get("vector_uid")
        if not vector_uid:
            raise MnemoAPIError(
                message="Invariant violation: verified response missing vector_uid",
                status_code=502,
                code=MnemoErrorCode.SERVER_ERROR,
            )

        _require_fields(data, ("confidence",), "verify")
        raw_signals = data.get("signals")
        return VerifyResult(
            verified=True,
            confidence=data["confidence"],
            vector_uid=vector_uid,
            policy_ok=data.get("policy_ok", False),
            signals=VerifySignals.from_dict(raw_signals) if raw_signals else None,
        )

    def health(self) -> Dict[str, Any]:
        """Check the health of the Mnemo API (``GET /v1/health``, no auth required).

        Returns:
            Dictionary with ``status``, ``version`` and ``timestamp``.
        """
        # The health route is unauthenticated: do not send the API key to it.
        return self._get_with_retry("/v1/health", headers={"X-API-Key": None})

    def usage(self) -> Dict[str, Any]:
        """Retrieve current API usage statistics (``GET /v1/usage``).

        Returns:
            Dictionary for the current calendar month: ``embed_count``,
            ``verify_count``, ``period`` (``YYYY-MM``), ``tier``, ``embed_limit``
            and ``verify_limit``.
        """
        return self._get_with_retry("/v1/usage")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post_with_retry(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        *,
        headers: Optional[Dict[str, str]] = None,
        idempotent: bool = True,
    ) -> Dict[str, Any]:
        """``headers``: per-request headers, sent unchanged on every attempt.

        ``idempotent=False`` (embed): the request is retried only when it
        certainly did not reach the server (429, or the connection was never
        established). A timeout or dropped connection after the request was
        sent is raised at once with ``retryable=False``, because retrying could
        register a second object.
        """
        return self._request_with_retry(
            "post", endpoint, json_payload=payload, headers=headers, idempotent=idempotent
        )

    def _get_with_retry(
        self, endpoint: str, *, headers: Optional[Dict[str, Optional[str]]] = None
    ) -> Dict[str, Any]:
        return self._request_with_retry("get", endpoint, headers=headers, idempotent=True)

    def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        *,
        json_payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        idempotent: bool = True,
    ) -> Dict[str, Any]:
        url = f"{self._api_url}{endpoint}"
        send = self._session.post if method == "post" else self._session.get
        request_kwargs: Dict[str, Any] = {"timeout": self._timeout}
        if json_payload is not None:
            request_kwargs["json"] = json_payload
        if headers:
            request_kwargs["headers"] = dict(headers)
        attempts = self._retry_attempts

        for attempt in range(attempts):
            last_attempt = attempt == attempts - 1
            try:
                resp = send(url, **request_kwargs)
            except requests.exceptions.SSLError as exc:
                # Certificate and TLS failures are not transient: never retried.
                raise MnemoAPIError(
                    message=f"TLS error: {exc}",
                    status_code=0,
                    code=MnemoErrorCode.NETWORK_ERROR,
                    retryable=False,
                ) from exc
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                not_sent = _request_never_sent(exc)
                if not idempotent and not not_sent:
                    raise MnemoAPIError(
                        message=(
                            f"Request outcome unknown ({exc.__class__.__name__}): the server "
                            f"may have processed it. {endpoint} is not retried automatically "
                            "because a retry could create a second object."
                        ),
                        status_code=0,
                        code=MnemoErrorCode.NETWORK_ERROR,
                        retryable=False,
                    ) from exc
                kind = "Request timed out" if isinstance(exc, requests.exceptions.Timeout) else "Connection error"
                err = MnemoAPIError(
                    message=f"{kind}: {exc}",
                    status_code=0,
                    code=MnemoErrorCode.NETWORK_ERROR,
                    retryable=True,
                )
                if last_attempt:
                    raise err from exc
                time.sleep(2 ** attempt)
                continue
            except requests.exceptions.ChunkedEncodingError as exc:
                # The response broke off while it was being read: the request
                # was processed. Safe to repeat only for idempotent calls.
                err = MnemoAPIError(
                    message=f"Response interrupted: {exc}",
                    status_code=0,
                    code=MnemoErrorCode.NETWORK_ERROR,
                    retryable=idempotent,
                )
                if not idempotent or last_attempt:
                    raise err from exc
                time.sleep(2 ** attempt)
                continue

            if resp.status_code == 429:
                retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
                err = _build_api_error(resp)
                err.message = "Rate limited"
                err.retry_after = retry_after
                wait = retry_after if retry_after is not None else float(2 ** attempt)
                if last_attempt or wait > _MAX_RETRY_AFTER_SECONDS:
                    raise err
                time.sleep(wait)
                continue

            if resp.status_code >= 400:
                raise _build_api_error(resp)

            return _json_body(resp)

        # Unreachable: every path above returns or raises on the last attempt.
        raise MnemoAPIError(
            message="Exhausted retries",
            status_code=0,
            code=MnemoErrorCode.NETWORK_ERROR,
        )


# ------------------------------------------------------------------
# Module-level helpers (no class state)
# ------------------------------------------------------------------


def _serialize_vector(vector) -> List[float]:
    """Convert a vector to a plain Python list of floats.

    NaN and infinity cannot be sent as JSON; they are refused here with a
    ``MnemoValidationError`` instead of escaping as a ``requests`` error."""
    values = vector.tolist() if hasattr(vector, "tolist") else list(vector)
    for i, x in enumerate(values):
        if isinstance(x, float) and not math.isfinite(x):
            raise MnemoValidationError(f"vector contains a non-finite value ({x}) at index {i}")
    return values


def _warn_if_cleartext(api_url: str) -> None:
    """Warn when the API key would travel over plain http to a non-local host."""
    parts = urlsplit(api_url)
    if parts.scheme == "http" and (parts.hostname or "") not in _LOCAL_HOSTS:
        warnings.warn(
            f"api_url {api_url!r} uses http://; the API key would be sent unencrypted. "
            "Use https:// (http is intended only for localhost).",
            UserWarning,
            stacklevel=3,
        )


def _request_never_sent(exc: Exception) -> bool:
    """True only when the connection was never established, so the server
    cannot have received the request (connect timeout, DNS failure, connection
    refused). Read timeouts and dropped connections return False."""
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return True
    if not isinstance(exc, requests.exceptions.ConnectionError):
        return False
    seen = set()
    stack: List[Any] = [exc]
    while stack:
        cur = stack.pop()
        if cur is None or id(cur) in seen:
            continue
        seen.add(id(cur))
        if isinstance(cur, NewConnectionError):
            return True
        stack.extend(getattr(cur, "args", ()) or ())
        stack.append(getattr(cur, "reason", None))
        stack.append(getattr(cur, "__cause__", None))
        stack.append(getattr(cur, "__context__", None))
    return False


def _parse_retry_after(value: Optional[str]) -> Optional[float]:
    """Parse ``Retry-After`` (delta-seconds or an HTTP date). None if absent or unparseable."""
    if value is None:
        return None
    value = str(value).strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


def _json_body(resp: requests.Response) -> Dict[str, Any]:
    """Decode a successful response; a non-JSON or non-object body is an API error."""
    try:
        data = resp.json()
    except ValueError as exc:  # json.JSONDecodeError and requests' JSONDecodeError
        raise MnemoAPIError(
            message=f"Invalid JSON in API response (HTTP {resp.status_code})",
            status_code=resp.status_code,
            code=MnemoErrorCode.SERVER_ERROR,
        ) from exc
    if not isinstance(data, dict):
        raise MnemoAPIError(
            message=f"Unexpected API response shape (HTTP {resp.status_code}): expected a JSON object",
            status_code=resp.status_code,
            code=MnemoErrorCode.SERVER_ERROR,
        )
    return data


def _require_fields(data: Dict[str, Any], fields, operation: str) -> None:
    missing = [f for f in fields if f not in data]
    if missing:
        raise MnemoAPIError(
            message=f"Invalid {operation} response: missing {', '.join(missing)}",
            status_code=502,
            code=MnemoErrorCode.SERVER_ERROR,
        )


def _retryable_for(status: int, server_code: Optional[str]) -> Optional[bool]:
    """Retry guidance that the API contract supports objectively."""
    if status in (408, 429):
        return True
    if status == 409:
        # Another attempt with the same Idempotency-Key is still running.
        return server_code == "request_in_progress"
    if status == 503 and server_code == "verification_unavailable":
        # Contract: the verification was not completed and nothing was charged.
        return True
    if 400 <= status < 500:
        return False
    return None


def _raise_api_error(resp: requests.Response) -> None:
    """Parse an error response and raise MnemoAPIError."""
    raise _build_api_error(resp)


def _build_api_error(resp: requests.Response) -> MnemoAPIError:
    """Parse an error response into a MnemoAPIError.

    The API answers errors in three shapes:

    * ``{"code": "<code>"}`` — billing refusals, e.g. an API key whose plan has
      no verifications left gets ``402 {"code": "insufficient_credits"}``;
    * ``{"detail": "<message>"}`` or ``{"detail": {"code": ..., "message": ...}}``
      — ordinary request errors;
    * ``{"detail": [ ... ]}`` — request validation errors (422).

    ``message`` is the most specific human-readable text available; ``details``
    carries the structured part (the ``detail`` object/list, or ``{"code": ...}``).
    """
    message = resp.text
    details = None
    try:
        body = resp.json()
    except (json.JSONDecodeError, ValueError):
        body = None

    server_code: Optional[str] = None
    if isinstance(body, dict):
        detail = body.get("detail")
        code = body.get("code")
        if isinstance(code, str):
            server_code = code
        elif isinstance(detail, dict) and isinstance(detail.get("code"), str):
            server_code = detail["code"]
        if "error" in body or "message" in body:
            text = body.get("error", body.get("message"))
            message = str(text) if text is not None else resp.text
        elif isinstance(detail, str):
            message = detail
        elif isinstance(detail, dict):
            message = detail.get("message") or detail.get("code") or resp.text
        elif isinstance(code, str):
            message = code

        if body.get("details") is not None:
            details = body["details"]
        elif isinstance(detail, (dict, list)):
            details = detail
        elif code is not None:
            details = {"code": code}

    code_map = {
        400: MnemoErrorCode.INVALID_INPUT,
        401: MnemoErrorCode.UNAUTHORIZED,
        # insufficient_credits: raised immediately, never retried. API keys are
        # never offered x402 and the SDK has no payment path.
        402: MnemoErrorCode.QUOTA_EXCEEDED,
        403: MnemoErrorCode.UNAUTHORIZED,
        404: MnemoErrorCode.NOT_FOUND,
        422: MnemoErrorCode.INVALID_INPUT,
        429: MnemoErrorCode.RATE_LIMIT,
    }
    error_code = code_map.get(resp.status_code, MnemoErrorCode.SERVER_ERROR)

    return MnemoAPIError(
        message=message,
        status_code=resp.status_code,
        code=error_code,
        details=details,
        server_code=server_code,
        retry_after=_parse_retry_after(resp.headers.get("Retry-After")) if resp.headers else None,
        retryable=_retryable_for(resp.status_code, server_code),
    )
