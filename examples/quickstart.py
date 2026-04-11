"""Mnemo SDK quickstart example.

Demonstrates basic embed and verify operations.
Replace 'your-api-key' with a real API key from https://app.mnemo.ai.
"""

from mnemo_sdk import MnemoClient

# Initialize the client
client = MnemoClient(api_key="your-api-key")

# Embed a watermark into a vector
result = client.embed(
    vector=[0.1, 0.2, 0.3, 0.4, 0.5],
    model_id="text-embedding-3-small",
)
print(f"Watermark UID: {result.vector_uid}")
print(f"Dimensions:    {result.dimensions}")

# Verify the watermarked vector
check = client.verify(vector=result.watermarked_vector)
if check is None:
    print("No watermark detected.")
else:
    print(f"Verified:      {check.verified}")
    print(f"Confidence:    {check.confidence}")
