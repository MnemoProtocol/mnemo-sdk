"""HTTP client for the Mnemo watermarking API."""

import json
import time
import uuid
from typing import Any, Dict, List, Optional
import requests

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

_SDK_VERSION = "3.1.1"
_USER_AGENT = f"mnemo-protocol/{_SDK_VERSION} python"

# Server-derived / trust fields the client may NEVER supply on a subject. The
# server derives the fingerprint and mints all proof/trust fields; a raw subject
# carrying any of these is rejected client-side (the runtime would also reject it
# via extra="forbid", but we fail fast with a clear SDK error).
_FORBIDDEN_SUBJECT_KEYS = frozenset(
    {"subject_fingerprint", "trust_mode", "proof", "proof_type", "proof_digest", "proof_key_id"}
)


def _serialize_subject(subject) -> Dict[str, Any]:
    """Normalize a ``subject`` arg (Subject or dict) to the wire shape.

    The SDK is transport-only: it passes raw subject context through unchanged. It
    does NOT compute ``subject_fingerprint`` or any trust/proof field, and it
    rejects a dict that tries to supply one (the server is the sole deriver of
    trust)."""
    if isinstance(subject, Subject):
        return subject.to_dict()
    if isinstance(subject, dict):
        bad = _FORBIDDEN_SUBJECT_KEYS & set(subject)
        if bad:
            raise MnemoValidationError(
                "subject must not include server-derived fields "
                f"{sorted(bad)} — the server derives the fingerprint and mints the proof"
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
        api_key: str,
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
            self._api_key = api_key
            self._api_url = api_url.rstrip("/")
            self._timeout = timeout
            self._retry_attempts = retry_attempts

        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-API-Key": self._api_key,
                "User-Agent": _USER_AGENT,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
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
            subject: Optional trusted-subject context (``Subject`` or dict) — RAW
                client context only. The **server** canonicalizes it into a
                tenant-scoped ``subject_fingerprint`` and (when enabled+configured)
                returns a server-issued ``subject_proof`` carrier on the result.
                The SDK never derives the fingerprint or any trust/proof field and
                rejects a dict that tries to supply one. Sending ``subject`` does
                not by itself change verification — the proof only matters later, on
                a STRICT oracle-only Case 3 verify under FP-squash.

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

        data = self._post_with_retry("/v1/embed", payload)
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
        """Verify whether a vector contains a Mnemo watermark.

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
            subject_proof: Optional server-issued carrier (``SubjectProof`` or dict)
                obtained from a prior ``embed``. It is an **opaque, untrusted**
                artifact: the SDK passes it through verbatim and never validates,
                verifies, or interprets it — the **server** re-verifies it. It is
                only consulted on a STRICT oracle-only Case 3 verify under FP-squash;
                in other modes/paths it is ignored, so passing it does not imply
                always-on work or latency.

        Returns:
            VerifyResult if a watermark is detected, None otherwise.
        """
        payload: Dict[str, Any] = {
            "vector": _serialize_vector(vector),
        }
        if subject_proof is not None:
            payload["subject_proof"] = _serialize_subject_proof(subject_proof)

        # Resolved ONCE per call, outside the retry loop.
        headers = {"Idempotency-Key": _resolve_idempotency_key(idempotency_key)}

        data = self._post_with_retry("/v1/verify", payload, headers=headers)

        if not data.get("verified"):
            return None

        vector_uid = data.get("vector_uid")
        if not vector_uid:
            raise MnemoAPIError(
                message="Invariant violation: verified response missing vector_uid",
                status_code=502,
                code=MnemoErrorCode.SERVER_ERROR,
            )

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
        return self._get_with_retry("/v1/health")

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
    ) -> Dict[str, Any]:
        """``headers``: per-request headers, sent unchanged on every attempt."""
        url = f"{self._api_url}{endpoint}"
        last_exc: Optional[Exception] = None
        request_kwargs: Dict[str, Any] = {"json": payload, "timeout": self._timeout}
        if headers:
            request_kwargs["headers"] = dict(headers)

        for attempt in range(self._retry_attempts):
            try:
                resp = self._session.post(url, **request_kwargs)

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", 2 ** attempt))
                    time.sleep(retry_after)
                    last_exc = MnemoAPIError(
                        message="Rate limited",
                        status_code=429,
                        code=MnemoErrorCode.RATE_LIMIT,
                    )
                    continue

                if resp.status_code >= 400:
                    _raise_api_error(resp)

                return resp.json()

            except requests.exceptions.ConnectionError as exc:
                last_exc = MnemoAPIError(
                    message=f"Connection error: {exc}",
                    status_code=0,
                    code=MnemoErrorCode.NETWORK_ERROR,
                )
                if attempt < self._retry_attempts - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise last_exc from exc

            except requests.exceptions.Timeout as exc:
                last_exc = MnemoAPIError(
                    message=f"Request timed out: {exc}",
                    status_code=0,
                    code=MnemoErrorCode.NETWORK_ERROR,
                )
                if attempt < self._retry_attempts - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise last_exc from exc

        if last_exc is not None:
            raise last_exc
        raise MnemoAPIError(
            message="Exhausted retries",
            status_code=0,
            code=MnemoErrorCode.NETWORK_ERROR,
        )

    def _get_with_retry(self, endpoint: str) -> Dict[str, Any]:
        url = f"{self._api_url}{endpoint}"
        last_exc: Optional[Exception] = None

        for attempt in range(self._retry_attempts):
            try:
                resp = self._session.get(url, timeout=self._timeout)

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", 2 ** attempt))
                    time.sleep(retry_after)
                    last_exc = MnemoAPIError(
                        message="Rate limited",
                        status_code=429,
                        code=MnemoErrorCode.RATE_LIMIT,
                    )
                    continue

                if resp.status_code >= 400:
                    _raise_api_error(resp)

                return resp.json()

            except requests.exceptions.ConnectionError as exc:
                last_exc = MnemoAPIError(
                    message=f"Connection error: {exc}",
                    status_code=0,
                    code=MnemoErrorCode.NETWORK_ERROR,
                )
                if attempt < self._retry_attempts - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise last_exc from exc

            except requests.exceptions.Timeout as exc:
                last_exc = MnemoAPIError(
                    message=f"Request timed out: {exc}",
                    status_code=0,
                    code=MnemoErrorCode.NETWORK_ERROR,
                )
                if attempt < self._retry_attempts - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise last_exc from exc

        if last_exc is not None:
            raise last_exc
        raise MnemoAPIError(
            message="Exhausted retries",
            status_code=0,
            code=MnemoErrorCode.NETWORK_ERROR,
        )


# ------------------------------------------------------------------
# Module-level helpers (no class state)
# ------------------------------------------------------------------


def _serialize_vector(vector) -> List[float]:
    """Convert a vector to a plain Python list of floats."""
    if hasattr(vector, "tolist"):
        return vector.tolist()
    return list(vector)


def _raise_api_error(resp: requests.Response) -> None:
    """Parse an error response and raise MnemoAPIError.

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

    if isinstance(body, dict):
        detail = body.get("detail")
        code = body.get("code")
        if "error" in body or "message" in body:
            message = body.get("error", body.get("message"))
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

    raise MnemoAPIError(
        message=message,
        status_code=resp.status_code,
        code=error_code,
        details=details,
    )
