# Changelog

Release dates are the UTC publish dates of the GitHub releases.

## 3.1.4 (2026-11-08)

Security and correctness patch. No change to the API calls the SDK makes, the request bodies, authentication, or the `verify()` / `embed()` return types.

- **API key never shown by `repr()`.** `MnemoConfig.api_key` is excluded from `repr()`, and `MnemoClient` has a `repr()` without the key. The key is no longer sent to the unauthenticated `GET /v1/health`.
- **`embed()` is never re-sent once it may have reached the server.** Before, a read timeout or dropped connection made the SDK send the embed again, which could register a second object. Now `embed()` is retried only on `429` and on connections that were never established. Otherwise it raises `MnemoAPIError` (`NETWORK_ERROR`, `retryable=False`). **Behaviour change:** callers that relied on the automatic resend now see the error and decide themselves. `verify()`, `health()` and `usage()` keep their retries (`verify()` is protected by its `Idempotency-Key`).
- **Retry loop fixes.** No sleep after the last attempt. `Retry-After` given as an HTTP date is parsed (it raised `ValueError` before). A `Retry-After` longer than 60 seconds is raised at once as `RATE_LIMIT` with `retry_after`, instead of blocking the call. `retry_attempts=0` (or negative) now sends one request instead of none. TLS and certificate errors are not retried. A response that breaks off while being read (`ChunkedEncodingError`) is raised as `MnemoAPIError`, and retried only for idempotent calls.
- **Typed error attributes (additive).** `MnemoAPIError` gains `server_code`, `retry_after`, `retryable` and, for `verify()`, `idempotency_key`, the key that was sent, so a caller can retry the same verification after `409 request_in_progress`. Existing attributes, codes and the constructor's positional arguments are unchanged.
- **Response and input validation.** A success response that is not a JSON object, or that lacks a required field, raises `MnemoAPIError` (`SERVER_ERROR`) instead of a raw `JSONDecodeError` or `KeyError`. A vector containing NaN or infinity raises `MnemoValidationError` before any request, instead of a `requests` error.
- `MnemoClient(config=MnemoConfig(...))` no longer requires `api_key` to be passed a second time. A plain `http://` `api_url` to a host other than localhost emits a `UserWarning`.
- The package ships a `py.typed` marker (PEP 561).
- Docs: README has a "Get an API key" line above the install command; its retry bullet describes the 3.1.4 behaviour, and the `MnemoConfig` example passes only `config=`. README "Use it when" no longer suggests lineage is in this SDK. `docs/GUARANTEES.md` no longer advises applying your own confidence threshold, which the agent protocol rules out, and `examples/verify_example.py` no longer branches on `confidence`. README, package summary and `context7.json` describe verify in the API's own terms: whether a vector resolves to an object registered to your account, rather than whether it "was issued" to it. Retry and error documentation updated.

## 3.1.3 (2026-10-15)

Documentation and package metadata only. No API or behavior changes and no code changes beyond docstrings.

- README first screen: package identity (PyPI `mnemo-protocol`, import `mnemo_sdk`, GitHub org MnemoProtocol, API `https://api.trymnemo.com`) and a note that the unrelated PyPI packages `mnemo`, `mnemo-sdk`, `mnemo-ai` and `mnemo-mcp` are not Mnemo's; a minimal embed + verify example that handles `verify()` returning `None`; what verify checks (objects registered to your own account); links to the SDK docs, OpenAPI, agent protocol, PyPI and Terms. License, copyright and patent notices are unchanged.
- Verify wording across `README.md`, `llms.txt`, `agent-manifest.json`, `docs/*.md`, the examples and the `verify()` / `VerifyResult` docstrings: `None` means the API answered `verified: false` (attribution to your account could not be shown; not proof the vector belongs to anyone else; counts as one verification), not "no watermark detected". `embed()` returns a measurably perturbed watermarked copy ("invisible", "drop-in replacement" and "negligible" removed). `confidence` is a relative signal, not a probability.
- `docs/GUARANTEES.md`: `policy_ok` reflects at most the TTL set at embed time; `usage_class`, `retention` and `region` are not evaluated by verify. "Detection" wording replaced; `None` does not show that a vector carries no watermark or belongs to anyone else.
- Policy wording in `docs/sdk_reference.md`, `docs/quickstart.md` and `examples/embed_example.py`: `ttl_hours` is a time-to-live after which verify's `policy_ok` is false; `retention` and `region` are values passed through to the server and not evaluated by verify.
- Package metadata: new summary, keywords, Audience/OS/Topic classifiers, and project URLs: `Repository` renamed to `Source`; new Security, Changelog and License URLs; Documentation now points to https://www.trymnemo.com/docs/sdk (Issues unchanged). License expression unchanged (`LicenseRef-Mnemo-SDK-2.0`).
- `llms.txt`: same identity note and verify-scope wording as the README.
- `context7.json` (repository-only, not packaged): points Context7 indexing at the README, `docs/` and `examples/`, and lists usage rules (install and import names, `X-API-Key`, `verify()` returning `None`, what verify checks).

## 3.1.2 (2026-10-13)

Licensing and metadata only. No API or behavior changes.

- License: Mnemo SDK License v2.0 replaces the Mnemo Proprietary Software License v1.0. It permits development, evaluation, testing and production integration, and distribution of the unmodified SDK only as incorporated into, or as a required dependency of, an application that interoperates with Mnemo. Governing law: Wyoming.
- Examples: `examples/quickstart.py`, `examples/embed_example.py`, `examples/verify_example.py` and `examples/subject_binding_example.py` are MIT-licensed through `examples/LICENSE`. No other file is MIT-licensed.
- `TERMS.md` (SDK Terms of Use v3.1) is retired; the Mnemo Terms of Service at https://www.trymnemo.com/terms govern the hosted Services. Package metadata: `License-Expression: LicenseRef-Mnemo-SDK-2.0`, license files: `LICENSE` only.
- `agent-manifest.json` and `llms.txt`: governing law Wyoming, `sdk_terms_url` removed, `license_url` points to `LICENSE`.

## 3.1.1 (2026-10-11)

- `verify()` now sends an `Idempotency-Key`, generated once per call (or your `idempotency_key`) and reused on every internal retry, so a retried verify is not counted twice against your plan. No other behaviour change; default host `https://api.trymnemo.com`.

## 3.1.0 (2026-10-08)

First public release of the Mnemo Python SDK, published to PyPI as `mnemo-protocol` (import `mnemo_sdk`).

- Default API host: `https://api.trymnemo.com`.
- API-key client for `/v1/embed`, `/v1/verify`, `/v1/health` and `/v1/usage` (header `X-API-Key`).
- Errors parse the server's `detail` / `code` bodies; HTTP 402 (`insufficient_credits`) raises `QUOTA_EXCEEDED` and is never retried or paid. The SDK has no payment (x402) path; API-key plans never use x402.
- Accountless agent access (capability namespaces, x402) is documented in the public protocol repository: https://github.com/MnemoProtocol/mnemo-agent-protocol
- Licensed under the Mnemo Proprietary Software License v1.0 at the time (superseded by the Mnemo SDK License v2.0 in 3.1.2).
