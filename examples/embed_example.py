"""Mnemo SDK embedding example with policy configuration.

Shows how to embed watermarks with custom policies using both
the convenience function and the fluent PolicyBuilder API.
"""

import random

from mnemo_sdk import MnemoClient, PolicyBuilder, create_policy

client = MnemoClient(api_key="your-api-key")


def sample_vector(dims: int = 768):
    """Stand-in for a real embedding. Vectors must have 512-4096 finite numbers."""
    return [random.uniform(-1.0, 1.0) for _ in range(dims)]


# --- Option 1: create_policy convenience function ---

policy = create_policy(
    ttl_hours=168,        # 7-day watermark lifetime
    usage_class="std",
    retention="hot",
    region="us",
)

result = client.embed(
    vector=sample_vector(),
    model_id="text-embedding-3-small",
    model_version="1.0",
    policy=policy,
)
print(f"UID:        {result.vector_uid}")
print(f"Created at: {result.created_at}")

# --- Option 2: PolicyBuilder fluent API ---

policy_v2 = (
    PolicyBuilder()
    .ttl_days(30)
    .usage_class("internal")
    .retention("cold")
    .region("us")
    .build()
)

result_v2 = client.embed(
    vector=sample_vector(),
    model_id="text-embedding-ada-002",
    policy=policy_v2,
)
print(f"UID (v2):   {result_v2.vector_uid}")
