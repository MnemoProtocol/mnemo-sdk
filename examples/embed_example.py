"""Mnemo SDK embedding example with policy configuration.

Shows how to embed watermarks with custom policies using both
the convenience function and the fluent PolicyBuilder API.
"""

from mnemo_sdk import MnemoClient, PolicyBuilder, create_policy

client = MnemoClient(api_key="your-api-key")

# --- Option 1: create_policy convenience function ---

policy = create_policy(
    ttl_hours=168,        # 7-day watermark lifetime
    usage_class="premium",
    retention="hot",
    region="us",
)

result = client.embed(
    vector=[0.1, 0.2, 0.3, 0.4, 0.5],
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
    .region("eu")
    .build()
)

result_v2 = client.embed(
    vector=[0.5, 0.4, 0.3, 0.2, 0.1],
    model_id="text-embedding-ada-002",
    policy=policy_v2,
)
print(f"UID (v2):   {result_v2.vector_uid}")
