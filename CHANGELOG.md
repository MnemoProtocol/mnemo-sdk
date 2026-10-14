# Changelog

## 3.1.3 (unreleased)

Documentation and package metadata only. No API or behavior changes; the only code change is the version string (`__version__`, User-Agent `mnemo-protocol/3.1.3 python`).

- README first screen: package identity (PyPI `mnemo-protocol`, import `mnemo_sdk`, GitHub org MnemoProtocol, API `https://api.trymnemo.com`) and a note that the unrelated PyPI packages `mnemo`, `mnemo-sdk`, `mnemo-ai` and `mnemo-mcp` are not Mnemo's; a minimal embed + verify example that handles `verify()` returning `None`; what verify checks (objects registered to your own account); links to the SDK docs, OpenAPI, agent protocol, PyPI and Terms. License, copyright and patent notices are unchanged.
- Package metadata: new summary, keywords, Audience/OS/Topic classifiers, and project URLs for Documentation (https://www.trymnemo.com/docs/sdk), Source, Issues, Security and Changelog. License expression unchanged (`LicenseRef-Mnemo-SDK-2.0`).
- `llms.txt`: same identity note and verify-scope wording as the README.

## 3.1.2 (2026-10-12)

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
