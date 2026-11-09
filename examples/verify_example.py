# SPDX-License-Identifier: MIT
# Copyright (c) 2025-2026 Mnemo LLC. Example code only — see examples/LICENSE for scope.
# Use of the Mnemo Services is governed by https://www.trymnemo.com/terms.
"""Mnemo SDK verification example.

Shows how to check whether a vector resolves to an object registered to
your Mnemo account, and how to interpret the result.
"""

import random

from mnemo_sdk import MnemoAPIError, MnemoClient, MnemoErrorCode

client = MnemoClient(api_key="your-api-key")

# A watermarked vector (in practice, this comes from a prior embed call
# or from a database / vector store). Vectors must have 512-4096 finite numbers.
embedded = client.embed(
    vector=[random.uniform(-1.0, 1.0) for _ in range(768)],
    model_id="text-embedding-3-small",
)
watermarked_vector = embedded.watermarked_vector
expected_uid = embedded.vector_uid  # store this next to the vector

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
    print("Not verified for this account (a normal result; counts as one verification).")
else:
    print(f"Verified:    {result.verified}")
    print(f"Vector UID:  {result.vector_uid}")
    print(f"Policy OK:   {result.policy_ok}")

    # Decide on the verdict: verify() returns None when the API answers
    # verified=false. confidence is a diagnostic score, not a probability and
    # not a threshold to apply yourself. Then compare the vector_uid with the
    # one you stored at embed time.
    if result.vector_uid == expected_uid:
        print(f"Verified for this account: resolves to {result.vector_uid}.")
    else:
        print(f"Verified, but resolves to a different registered object: {result.vector_uid}.")
