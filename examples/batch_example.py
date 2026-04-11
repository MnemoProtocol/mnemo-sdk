"""Mnemo SDK batch operations example.

Shows how to embed and verify multiple vectors in a single request
using MnemoBatch.
"""

from mnemo_sdk import MnemoClient, MnemoBatch, create_policy

client = MnemoClient(api_key="your-api-key")
batch = MnemoBatch(client)

# Prepare a batch of vectors
vectors = [
    [0.1, 0.2, 0.3, 0.4, 0.5],
    [0.5, 0.4, 0.3, 0.2, 0.1],
    [0.9, 0.8, 0.7, 0.6, 0.5],
]

# Batch embed with an optional policy
policy = create_policy(ttl_hours=48, usage_class="std")

embed_results = batch.embed_batch(
    vectors=vectors,
    model_id="text-embedding-3-small",
    policy=policy,
)

print("=== Embed Results ===")
for i, result in enumerate(embed_results):
    print(f"  [{i}] UID: {result.vector_uid}  dims: {result.dimensions}")

# Collect the watermarked vectors for verification
watermarked = [r.watermarked_vector for r in embed_results]

# Batch verify
verify_results = batch.verify_batch(vectors=watermarked)

print("\n=== Verify Results ===")
for i, result in enumerate(verify_results):
    if result is None:
        print(f"  [{i}] NOT DETECTED")
    else:
        status = "PASS" if result.verified else "FAIL"
        print(f"  [{i}] {status}  confidence: {result.confidence:.2f}")
