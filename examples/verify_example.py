"""Mnemo SDK verification example.

Shows how to verify whether a vector contains a Mnemo watermark
and interpret the result.
"""

from mnemo_sdk import MnemoClient

client = MnemoClient(api_key="your-api-key")

# A watermarked vector (in practice, this comes from a prior embed call
# or from a database / vector store).
watermarked_vector = [0.11, 0.22, 0.33, 0.44, 0.55]

result = client.verify(vector=watermarked_vector)

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
