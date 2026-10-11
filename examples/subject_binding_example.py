# SPDX-License-Identifier: MIT
# Copyright (c) 2025-2026 Mnemo LLC. Example code only — see examples/LICENSE for scope.
# Use of the Mnemo Services is governed by https://www.trymnemo.com/terms.
"""Trusted subject binding (optional) — embed with subject, replay proof on verify.

Notes:
  * `subject` is client context. The Mnemo service processes it; the SDK only transports it.
  * `subject_proof` is an opaque token issued by the service. Store it and pass it back on verify unchanged; only the service can check it. It may be absent if the feature is not enabled.
"""

import random

from mnemo_sdk import MnemoClient, Subject


def main() -> None:
    client = MnemoClient(api_key="your-api-key")

    # 1) Embed with subject context. The service processes it and (when the
    #    feature is enabled) returns an opaque proof token.
    result = client.embed(
        # Stand-in for a real embedding (512-4096 finite numbers).
        vector=[random.uniform(-1.0, 1.0) for _ in range(768)],
        model_id="text-embedding-3-small",
        subject=Subject(
            subject_uri="mnemo://subj/your-tenant/document/doc-123",
            subject_type="document",
            object_id="doc-123",
            # `adapters` is opaque per-namespace metadata, stored verbatim.
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
        # Diagnostic signals returned by the service; values are informational
        # and may change.
        print("method:", check.signals.method, "mode:", check.signals.mode)


if __name__ == "__main__":
    main()
