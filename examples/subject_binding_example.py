"""Trusted subject binding (optional) — embed with subject, replay proof on verify.

Every subject-aware call routes to the Mnemo core runtime, which does ALL trust
work centrally: canonicalization, proof issuance, proof verification, tenant
scoping, metering, and fail-closed gating. The SDK is transport only — it never
derives a fingerprint, mints a proof, validates a proof, or interprets
corroboration.

Notes on behavior:
  * `subject` is RAW client context; the server derives `subject_fingerprint`.
  * `subject_proof` is an opaque, server-issued carrier — store it, replay it; the
    server re-verifies it. It is consulted ONLY on a STRICT oracle-only "Case 3"
    verify under the server's FP-squash gate (the provenance-grade, claim-bearing
    path). It does not run on every verify and should not be assumed to add latency
    on normal paths. BALANCED/HIGH_RECALL are non-claim-bearing for subject-proof /
    compressed oracle-only recovery.
"""

from mnemo_sdk import MnemoClient, Subject


def main() -> None:
    client = MnemoClient(api_key="your-api-key")

    # 1) Embed with raw subject context. The server canonicalizes it and (when the
    #    subject-proof transport is enabled+configured) returns a proof carrier.
    result = client.embed(
        vector=[0.1, 0.2, 0.3, 0.4, 0.5],
        model_id="text-embedding-3-small",
        subject=Subject(
            subject_uri="mnemo://subj/your-tenant/document/doc-123",
            subject_type="document",
            object_id="doc-123",
            # `adapters` is opaque per-namespace metadata; the server never reads it
            # for verification. It is stored verbatim only.
            adapters={"your_namespace": {"source": "ingest-pipeline-v2"}},
        ),
    )
    print("vector_uid:", result.vector_uid)

    # `subject_proof` is None unless the server-side transport is enabled+configured.
    proof = result.subject_proof
    if proof is None:
        print("No subject_proof issued (transport disabled/unconfigured server-side).")
    else:
        # Treat it as an opaque token: persist it next to your record. Do not parse
        # it for trust — only the server can verify it.
        print("subject_proof issued (key:", proof.proof_key_id, "expires:", proof.expires_at, ")")

    # 2) Later, replay the proof verbatim on verify. The SDK transports it untouched.
    check = client.verify(vector=result.watermarked_vector, subject_proof=proof)
    if check is None:
        print("Not verified.")
        return
    print("verified:", check.verified, "confidence:", check.confidence)
    if check.signals is not None:
        # Diagnostic only. `mode == "STRICT"` is the provenance-grade posture; the
        # subject proof is only consulted on the STRICT oracle-only path.
        print("method:", check.signals.method, "mode:", check.signals.mode)


if __name__ == "__main__":
    main()
