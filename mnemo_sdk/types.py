"""Data types for the Mnemo SDK."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MnemoConfig:
    """Configuration for the Mnemo API client."""

    api_key: str
    api_url: str = "https://api.mnemo.ai"
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
class EmbedResult:
    """Result returned from an embed operation."""

    vector_uid: str
    watermarked_vector: List[float]
    created_at: str
    dimensions: int

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
class VerifyResult:
    """Result returned from a successful verify operation.

    Only returned when a watermark is detected (verified == True).
    """

    verified: bool
    confidence: float
    vector_uid: str
    policy_ok: bool


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
