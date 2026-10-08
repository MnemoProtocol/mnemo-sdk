"""Mnemo SDK verification example.

Shows how to verify whether a vector contains a Mnemo watermark
and interpret the result.
"""

import random

from mnemo_sdk import MnemoAPIError, MnemoClient, MnemoErrorCode

client = MnemoClient(api_key="your-api-key")

# A watermarked vector (in practice, this comes from a prior embed call
# or from a database / vector store). Vectors must have 512-4096 finite numbers.
watermarked_vector = client.embed(
    vector=[random.uniform(-1.0, 1.0) for _ in range(768)],
    model_id="text-embedding-3-small",
).watermarked_vector

# With an API key, each verification counts against the account plan's included
# monthly verifications. When they are used up the server answers
# 402 {"code": "insufficient_credits"} (no overage, no top-ups, never x402).
try:
    result = client.verify(vector=watermarked_vector)
except MnemoAPIError as exc:
    if exc.code is MnemoErrorCode.QUOTA_EXCEEDED:
        raise SystemExit("Verification allowance exhausted for this billing period.")
    raise

if result is None:
    print("No watermark detected in this vector.")
else:
    print(f"Verified:    {result.verified}")
    print(f"Confidence:  {result.confidence}")
    print(f"Vector UID:  {result.vector_uid}")
    print(f"Policy OK:   {result.policy_ok}")

    if result.confidence > 0.9:
        print("High-confidence watermark detected.")
    else:
        print("Watermark detected with moderate confidence.")
