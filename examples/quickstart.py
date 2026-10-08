"""Mnemo SDK quickstart example.

Demonstrates basic embed and verify operations against https://api.trymnemo.com.
Replace 'your-api-key' with an account API key (sign in at https://www.trymnemo.com/login).
"""

import random

from mnemo_sdk import MnemoClient

# Initialize the client
client = MnemoClient(api_key="your-api-key")

# Stand-in for a real embedding. Vectors must have 512-4096 finite numbers.
vector = [random.uniform(-1.0, 1.0) for _ in range(768)]

# Embed a watermark into a vector
result = client.embed(
    vector=vector,
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
