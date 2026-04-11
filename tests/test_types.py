"""Tests for Mnemo SDK data types."""

import sys

import pytest

from mnemo_sdk.types import (
    EmbedResult,
    PolicyBuilder,
    PolicyConfig,
    VerifyResult,
    create_policy,
)


def _numpy_available() -> bool:
    try:
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


class TestEmbedResult:

    def test_embed_result_construction(self):
        result = EmbedResult(
            vector_uid="uid-001",
            watermarked_vector=[0.1, 0.2, 0.3],
            created_at="2026-01-01T00:00:00Z",
            dimensions=3,
        )
        assert result.vector_uid == "uid-001"
        assert result.watermarked_vector == [0.1, 0.2, 0.3]
        assert result.created_at == "2026-01-01T00:00:00Z"
        assert result.dimensions == 3

    @pytest.mark.skipif(
        not _numpy_available(),
        reason="numpy not installed",
    )
    def test_embed_result_to_numpy(self):
        import numpy as np

        result = EmbedResult(
            vector_uid="uid-001",
            watermarked_vector=[0.1, 0.2, 0.3],
            created_at="2026-01-01T00:00:00Z",
            dimensions=3,
        )
        arr = result.to_numpy()
        assert isinstance(arr, np.ndarray)
        assert arr.tolist() == pytest.approx([0.1, 0.2, 0.3])


class TestVerifyResult:

    def test_verify_result_construction(self):
        result = VerifyResult(
            verified=True,
            confidence=0.95,
            vector_uid="uid-001",
            policy_ok=True,
        )
        assert result.verified is True
        assert result.confidence == 0.95
        assert result.vector_uid == "uid-001"
        assert result.policy_ok is True

    def test_verify_result_requires_vector_uid(self):
        """vector_uid is mandatory — no default, no Optional."""
        with pytest.raises(TypeError):
            VerifyResult(verified=True, confidence=0.9, policy_ok=True)


class TestPolicyConfig:

    def test_policy_config_to_dict(self):
        policy = PolicyConfig(
            ttl_hours=48,
            usage_class="premium",
            retention="cold",
            region="eu",
        )
        d = policy.to_dict()
        assert d == {
            "ttl_hours": 48,
            "usage_class": "premium",
            "retention": "cold",
            "region": "eu",
        }


class TestPolicyBuilder:

    def test_policy_builder(self):
        policy = (
            PolicyBuilder()
            .ttl_days(30)
            .usage_class("premium")
            .retention("cold")
            .region("eu")
            .build()
        )
        assert policy["ttl_hours"] == 720
        assert policy["usage_class"] == "premium"
        assert policy["retention"] == "cold"
        assert policy["region"] == "eu"


class TestCreatePolicy:

    def test_create_policy(self):
        policy = create_policy(
            ttl_hours=100,
            usage_class="internal",
            retention="warm",
            region="ap",
        )
        assert policy == {
            "ttl_hours": 100,
            "usage_class": "internal",
            "retention": "warm",
            "region": "ap",
        }
