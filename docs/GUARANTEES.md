# Guarantees and Limitations

> **This document is informational only and does not create contractual
> obligations, warranties, or guarantees.** For binding terms, see
> [LICENSE](../LICENSE) and the
> [Terms of Service](https://www.trymnemo.com/terms).

## What the SDK does

The Mnemo SDK is a thin client for the Mnemo watermarking API. It does
not perform watermarking or verification locally. All watermarking and
verification work happens server-side; the SDK forwards vectors and
returns the API's response.

## What the API returns

### Embed
A successful embed call returns a measurably perturbed watermarked
copy of the input vector, a `vector_uid` that identifies the embedding
event, a creation timestamp, and the vector dimensionality. Store and
use the watermarked copy in place of the original embedding.

### Verify
Mnemo Verify checks whether a submitted vector resolves to an object
registered to the caller's Mnemo account or namespace; with this SDK
the caller is your account. `verify()` returns either:

- A `VerifyResult` (the API answered `verified=true`) containing
  `verified=True`, a confidence value, the matched `vector_uid`, and a
  `policy_ok` flag. `policy_ok` reflects at most the TTL set at embed
  time; it does not evaluate usage class, retention or region.
- `None` (the API answered `verified=false`): attribution to your
  account could not be shown; this is not proof the vector belongs to
  anyone else. It is a normal result, not an error, and it counts as
  one verification.

The SDK never decides on its own whether a vector verifies. It
reflects the verdict the API returned.

## What is supported

- Embedding watermarks into floating-point vectors produced by standard
  embedding models.
- Verifying vectors that were previously embedded through the Mnemo API
  under your account.
- Common storage and serialization round-trips (float32/float64 casts,
  JSON encoding, typical database persistence).
- Policy attachment: `ttl_hours`, `usage_class`, `retention` and
  `region` can be attached at embed time. Verify's `policy_ok` reflects
  at most the TTL; the other fields are not evaluated by verify.

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
  A vector you embedded may not verify after such transforms.
- **Tamper resistance.** Mnemo provides traceability for normal data
  pipelines, not cryptographic resistance against a motivated
  adversary with full knowledge of the system.
- **Lossless embedding.** The returned vector is a measurably perturbed
  copy of the input; check retrieval quality on your own data before
  switching over.

## Operational note

Confidence scores returned by the API are intended as a relative
signal, not a probability. Applications that need a hard accept/reject
decision should pair the verdict with their own threshold appropriate
to their use case. When `verify()` returns `None`, treat the vector as
not verified for your account. `None` does not show that the vector
carries no watermark, and it does not show that the vector belongs to
anyone else.

## Right to modify

Mnemo may modify, improve, or deprecate verification methods,
algorithms, API behavior, and SDK capabilities at any time without
prior notice. The descriptions in this document reflect the current
release and are subject to change.
