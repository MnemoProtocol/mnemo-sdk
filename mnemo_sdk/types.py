"""Data types for the Mnemo SDK."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Public Mnemo API host.
DEFAULT_API_URL = "https://api.trymnemo.com"


@dataclass
class MnemoConfig:
    """Configuration for the Mnemo API client."""

    api_key: str
    api_url: str = DEFAULT_API_URL
    timeout: int = 30
    retry_attempts: int = 3


@dataclass
class PolicyConfig:
    """Policy configuration for watermark embedding."""

    ttl_hours: int = 720
    usage_class: str = "std"
    retention: str = "hot"
    region: str = "us"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ttl_hours": self.ttl_hours,
            "usage_class": self.usage_class,
            "retention": self.retention,
            "region": self.region,
        }


@dataclass
class Subject:
    """Optional subject context for an embed call.

    This is **client context only**; the Mnemo service processes it and the SDK
    only transports it. By construction this model has NO ``subject_fingerprint`` /
    ``trust_mode`` / ``proof_*`` fields; those are set by the service.
    """

    subject_uri: str
    subject_type: str
    canonicalization_version: Optional[str] = None  # advisory only; the server pins its own
    object_id: Optional[str] = None
    parent_id: Optional[str] = None
    segment_id: Optional[str] = None
    offset: Optional[Dict[str, Any]] = None
    adapters: Optional[Dict[str, Any]] = None  # opaque per-namespace metadata, stored verbatim

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to the wire shape, dropping None-valued optionals."""
        out: Dict[str, Any] = {
            "subject_uri": self.subject_uri,
            "subject_type": self.subject_type,
        }
        for k in ("canonicalization_version", "object_id", "parent_id", "segment_id", "offset", "adapters"):
            v = getattr(self, k)
            if v is not None:
                out[k] = v
        return out


@dataclass
class SubjectProof:
    """Opaque subject-proof token returned by ``embed``.

    This is an **opaque proof token issued and checked by the service**. The SDK
    never validates or interprets it — it only carries it back to the service on a
    later ``verify`` call; only the service can check it. The original
    server payload is preserved verbatim (``_raw``) so it round-trips byte-for-byte
    even if the server adds fields later. The typed attributes are read-only
    convenience accessors.
    """

    version: Optional[str] = None
    proof_type: Optional[str] = None
    proof_key_id: Optional[str] = None
    tenant_id: Optional[str] = None
    subject_fingerprint: Optional[str] = None
    canonicalization_version: Optional[str] = None
    issued_at: Optional[float] = None
    expires_at: Optional[float] = None
    proof: Optional[str] = None
    # Verbatim server payload — what is sent back on verify (opaque round-trip).
    _raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubjectProof":
        """Parse a server response carrier. Tolerant: unknown fields are preserved
        in ``_raw`` and ignored for typed accessors; missing fields stay None. Does
        NOT validate or trust anything."""
        d = dict(data or {})
        return cls(
            version=d.get("version"),
            proof_type=d.get("proof_type"),
            proof_key_id=d.get("proof_key_id"),
            tenant_id=d.get("tenant_id"),
            subject_fingerprint=d.get("subject_fingerprint"),
            canonicalization_version=d.get("canonicalization_version"),
            issued_at=d.get("issued_at"),
            expires_at=d.get("expires_at"),
            proof=d.get("proof"),
            _raw=d,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return the opaque carrier to send back on verify — the verbatim server
        payload when available, else the typed fields. Never re-derives trust."""
        if self._raw:
            return dict(self._raw)
        return {k: v for k, v in {
            "version": self.version, "proof_type": self.proof_type,
            "proof_key_id": self.proof_key_id, "tenant_id": self.tenant_id,
            "subject_fingerprint": self.subject_fingerprint,
            "canonicalization_version": self.canonicalization_version,
            "issued_at": self.issued_at, "expires_at": self.expires_at,
            "proof": self.proof,
        }.items() if v is not None}


@dataclass
class EmbedResult:
    """Result returned from an embed operation."""

    vector_uid: str
    watermarked_vector: List[float]
    created_at: str
    dimensions: int
    # Opaque subject-proof token issued by the service; present only when a `subject` was
    # supplied AND the server-side transport is enabled+configured, else None.
    subject_proof: Optional["SubjectProof"] = None

    def to_numpy(self):
        """Convert watermarked_vector to a numpy array.

        Raises:
            ImportError: If numpy is not installed.
        """
        try:
            import numpy as np
        except ImportError:
            raise ImportError(
                "numpy is required for to_numpy(). "
                "Install it with: pip install mnemo-protocol[numpy]"
            )
        return np.array(self.watermarked_vector)


@dataclass
class VerifySignals:
    """Diagnostic signals returned by the service with a verify result.

    Values are informational and may change; field names are kept for
    compatibility. Do not build trust decisions on them.
    """

    method: Optional[str] = None
    spectral_status: Optional[str] = None
    oracle_status: Optional[str] = None
    oracle_best_dist: Optional[float] = None
    oracle_margin: Optional[float] = None
    oracle_candidate_count: Optional[int] = None
    mode: Optional[str] = None
    latency_ms: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerifySignals":
        """Tolerant parse — unknown fields ignored, missing fields stay None."""
        d = dict(data or {})
        return cls(
            method=d.get("method"),
            spectral_status=d.get("spectral_status"),
            oracle_status=d.get("oracle_status"),
            oracle_best_dist=d.get("oracle_best_dist"),
            oracle_margin=d.get("oracle_margin"),
            oracle_candidate_count=d.get("oracle_candidate_count"),
            mode=d.get("mode"),
            latency_ms=d.get("latency_ms"),
        )


@dataclass
class VerifyResult:
    """Result returned from a successful verify operation.

    Only returned when a watermark is detected (verified == True).
    """

    verified: bool
    confidence: float
    vector_uid: str
    policy_ok: bool
    # Additive diagnostic block (optional; None if the server omits it).
    signals: Optional["VerifySignals"] = None


class PolicyBuilder:
    """Fluent builder for constructing policy configuration dictionaries."""

    def __init__(self) -> None:
        self._config = PolicyConfig()

    def ttl_hours(self, hours: int) -> "PolicyBuilder":
        self._config.ttl_hours = hours
        return self

    def ttl_days(self, days: int) -> "PolicyBuilder":
        self._config.ttl_hours = days * 24
        return self

    def usage_class(self, cls: str) -> "PolicyBuilder":
        self._config.usage_class = cls
        return self

    def retention(self, retention: str) -> "PolicyBuilder":
        self._config.retention = retention
        return self

    def region(self, region: str) -> "PolicyBuilder":
        self._config.region = region
        return self

    def build(self) -> Dict[str, Any]:
        return self._config.to_dict()


def create_policy(
    *,
    ttl_hours: int = 720,
    usage_class: str = "std",
    retention: str = "hot",
    region: str = "us",
) -> Dict[str, Any]:
    """Convenience function to create a policy dict."""
    return PolicyConfig(
        ttl_hours=ttl_hours,
        usage_class=usage_class,
        retention=retention,
        region=region,
    ).to_dict()
