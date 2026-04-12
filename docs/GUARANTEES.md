# Guarantees and Limitations

> **This document is informational only and does not create contractual
> obligations, warranties, or guarantees.** For binding terms, see
> [LICENSE](../LICENSE) and [TERMS.md](../TERMS.md).

## What the SDK does

The Mnemo SDK is a thin client for the Mnemo watermarking API. It does
not perform watermarking or verification locally. All cryptographic and
detection work happens server-side; the SDK forwards vectors and
returns the API's response.

## What the API returns

### Embed
A successful embed call returns a watermarked vector, a `vector_uid`
that identifies the embedding event, a creation timestamp, and the
vector dimensionality. The watermarked vector can be stored and used
in place of the original embedding.

### Verify
A verify call returns either:

- A `VerifyResult` containing `verified=True`, a confidence score, the
  matched `vector_uid`, and a `policy_ok` flag indicating whether the
  vector is being used within the policy bounds set at embed time, or
- `None`, indicating that no Mnemo watermark was detected.

The SDK never decides on its own whether a vector is watermarked. It
reflects the verdict the API returned.

## What is supported

- Embedding watermarks into floating-point vectors produced by standard
  embedding models.
- Verifying vectors that were previously embedded through the Mnemo API.
- Common storage and serialization round-trips (float32/float64 casts,
  JSON encoding, typical database persistence).
- Policy-aware responses: each verification reflects the policy that
  was attached at embed time (TTL, usage class, retention, region).

## What is not guaranteed

- **Offline operation.** The SDK requires network access to the Mnemo
  API. There is no local verification path.
- **Retroactive coverage.** Only vectors that were embedded through
  the Mnemo API can be verified. Pre-existing embeddings cannot be
  identified after the fact.
- **Robustness under aggressive transforms.** Verification is
  best-effort under significant noise injection, large-scale
  dimensionality reduction, adversarial perturbation, or any
  transformation specifically designed to defeat watermarking.
  Detection in those regimes is not guaranteed.
- **Tamper resistance.** Mnemo provides traceability for normal data
  pipelines, not cryptographic resistance against a motivated
  adversary with full knowledge of the system.
- **Lossless embedding.** The watermarking process introduces a small
  perturbation to the input vector. For typical downstream tasks this
  is negligible, but it is not zero.

## Operational note

Confidence scores returned by the API are intended as a relative
signal, not a probability. Applications that need a hard accept/reject
decision should pair the verdict with their own threshold appropriate
to their use case. When the API returns `None`, treat the vector as
unverified — do not infer the absence of a watermark with certainty
from a single call.

## Right to modify

Mnemo may modify, improve, or deprecate verification methods,
algorithms, API behavior, and SDK capabilities at any time without
prior notice. The descriptions in this document reflect the current
release and are subject to change.
