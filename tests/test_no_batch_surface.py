"""Regression guard (PR J1): the SDK exposes ONLY core-owned runtime surfaces.

The MnemoV2 core runtime supports `/v1/embed` and `/v1/verify` only — there is no
`/v1/embed/batch` or `/v1/verify/batch` endpoint (core owns metering, proof
issuance/verification, tenant scoping, STRICT gating, and audit per call). The
unsupported `MnemoBatch` scaffold (which posted to those non-existent routes) was
removed. These tests lock the contract so the batch surface cannot silently return.
"""
import inspect

import pytest

import mnemo_sdk
from mnemo_sdk import client as client_mod


def test_mnemobatch_not_exported():
    assert not hasattr(mnemo_sdk, "MnemoBatch")
    assert "MnemoBatch" not in getattr(mnemo_sdk, "__all__", [])


def test_mnemobatch_import_fails():
    with pytest.raises(ImportError):
        from mnemo_sdk import MnemoBatch  # noqa: F401


def test_no_batch_class_in_client_module():
    assert not hasattr(client_mod, "MnemoBatch")


def test_no_public_batch_symbols():
    # No public batch method on the client.
    public_client = [n for n in dir(mnemo_sdk.MnemoClient) if not n.startswith("_")]
    assert not any("batch" in n.lower() for n in public_client), public_client
    # No public batch symbol exported by the package.
    assert not any("batch" in n.lower() for n in mnemo_sdk.__all__), mnemo_sdk.__all__


def test_no_batch_endpoint_references_in_client_source():
    src = inspect.getsource(client_mod)
    assert "/v1/embed/batch" not in src
    assert "/v1/verify/batch" not in src
