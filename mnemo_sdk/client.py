"""HTTP client for the Mnemo watermarking API."""

import json
import time
from typing import Any, Dict, List, Optional
import requests

from mnemo_sdk.errors import MnemoAPIError, MnemoErrorCode, MnemoValidationError
from mnemo_sdk.types import EmbedResult, MnemoConfig, PolicyConfig, VerifyResult

_SDK_VERSION = "3.0.0"
_USER_AGENT = f"mnemo-protocol/{_SDK_VERSION} python"


class MnemoClient:
    """Python client for the Mnemo watermarking API.

    All watermarking operations are executed server-side; this client
    contains no algorithm code.
    """

    def __init__(
        self,
        api_key: str,
        *,
        api_url: str = "https://api.mnemo.ai",
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
    ) -> EmbedResult:
        """Embed a watermark into a vector.

        Args:
            vector: Input vector (list or numpy array).
            model_id: Identifier for the model that produced the vector.
            model_version: Version of the model.
            policy: Optional policy dict (use ``create_policy`` or ``PolicyBuilder``).

        Returns:
            EmbedResult with the watermarked vector and metadata.
        """
        payload: Dict[str, Any] = {
            "vector": _serialize_vector(vector),
            "model_id": model_id,
            "model_version": model_version,
        }
        if policy is not None:
            payload["policy"] = policy

        data = self._post_with_retry("/v1/embed", payload)
        return EmbedResult(
            vector_uid=data["vector_uid"],
            watermarked_vector=data["watermarked_vector"],
            created_at=data["created_at"],
            dimensions=data["dimensions"],
        )

    def verify(
        self,
        vector,
    ) -> Optional[VerifyResult]:
        """Verify whether a vector contains a Mnemo watermark.

        Args:
            vector: Vector to verify (list or numpy array).

        Returns:
            VerifyResult if a watermark is detected, None otherwise.
        """
        payload: Dict[str, Any] = {
            "vector": _serialize_vector(vector),
        }

        data = self._post_with_retry("/v1/verify", payload)

        if not data.get("verified"):
            return None

        vector_uid = data.get("vector_uid")
        if not vector_uid:
            raise MnemoAPIError(
                message="Malformed response: verified result missing vector_uid",
                status_code=502,
                code=MnemoErrorCode.SERVER_ERROR,
            )

        return VerifyResult(
            verified=True,
            confidence=data["confidence"],
            vector_uid=vector_uid,
            policy_ok=data.get("policy_ok", False),
        )

    def health(self) -> Dict[str, Any]:
        """Check the health of the Mnemo API.

        Returns:
            Dictionary with service health information.
        """
        return self._get_with_retry("/v1/health")

    def usage(self) -> Dict[str, Any]:
        """Retrieve current API usage statistics.

        Returns:
            Dictionary with usage data for the authenticated account.
        """
        return self._get_with_retry("/v1/usage")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post_with_retry(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self._api_url}{endpoint}"
        last_exc: Optional[Exception] = None

        for attempt in range(self._retry_attempts):
            try:
                resp = self._session.post(url, json=payload, timeout=self._timeout)

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


class MnemoBatch:
    """Batch operations for the Mnemo API."""

    def __init__(self, client: MnemoClient) -> None:
        self._client = client

    def embed_batch(
        self,
        vectors,
        model_id: str,
        *,
        model_version: str = "1.0",
        policy: Optional[Dict[str, Any]] = None,
    ) -> List[EmbedResult]:
        """Embed watermarks into multiple vectors.

        Args:
            vectors: Iterable of vectors (lists or numpy arrays).
            model_id: Identifier for the model that produced the vectors.
            model_version: Version of the model.
            policy: Optional policy dict applied to all vectors.

        Returns:
            List of EmbedResult, one per input vector.
        """
        serialized = [_serialize_vector(v) for v in vectors]
        payload: Dict[str, Any] = {
            "vectors": serialized,
            "model_id": model_id,
            "model_version": model_version,
        }
        if policy is not None:
            payload["policy"] = policy

        data = self._client._post_with_retry("/v1/embed/batch", payload)
        return [
            EmbedResult(
                vector_uid=item["vector_uid"],
                watermarked_vector=item["watermarked_vector"],
                created_at=item["created_at"],
                dimensions=item["dimensions"],
            )
            for item in data["results"]
        ]

    def verify_batch(
        self,
        vectors,
    ) -> List[Optional[VerifyResult]]:
        """Verify multiple vectors for Mnemo watermarks.

        Args:
            vectors: Iterable of vectors (lists or numpy arrays).

        Returns:
            List of VerifyResult (or None for unverified) per input vector.
        """
        serialized = [_serialize_vector(v) for v in vectors]
        payload: Dict[str, Any] = {
            "vectors": serialized,
        }

        data = self._client._post_with_retry("/v1/verify/batch", payload)
        results: List[Optional[VerifyResult]] = []
        for item in data["results"]:
            if not item.get("verified"):
                results.append(None)
                continue
            vector_uid = item.get("vector_uid")
            if not vector_uid:
                raise MnemoAPIError(
                    message="Malformed response: verified result missing vector_uid",
                    status_code=502,
                    code=MnemoErrorCode.SERVER_ERROR,
                )
            results.append(VerifyResult(
                verified=True,
                confidence=item["confidence"],
                vector_uid=vector_uid,
                policy_ok=item.get("policy_ok", False),
            ))
        return results


# ------------------------------------------------------------------
# Module-level helpers (no class state)
# ------------------------------------------------------------------


def _serialize_vector(vector) -> List[float]:
    """Convert a vector to a plain Python list of floats."""
    if hasattr(vector, "tolist"):
        return vector.tolist()
    return list(vector)


def _raise_api_error(resp: requests.Response) -> None:
    """Parse an error response and raise MnemoAPIError."""
    try:
        body = resp.json()
        message = body.get("error", body.get("message", resp.text))
        details = body.get("details")
    except (json.JSONDecodeError, ValueError):
        message = resp.text
        details = None

    code_map = {
        400: MnemoErrorCode.INVALID_INPUT,
        401: MnemoErrorCode.UNAUTHORIZED,
        403: MnemoErrorCode.UNAUTHORIZED,
        404: MnemoErrorCode.NOT_FOUND,
        429: MnemoErrorCode.RATE_LIMIT,
    }
    error_code = code_map.get(resp.status_code, MnemoErrorCode.SERVER_ERROR)

    raise MnemoAPIError(
        message=message,
        status_code=resp.status_code,
        code=error_code,
        details=details,
    )
