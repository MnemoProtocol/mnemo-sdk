"""Mnemo SDK — Python client for the Mnemo watermarking API."""

from mnemo_sdk.client import MnemoClient, MnemoConfig, MnemoBatch
from mnemo_sdk.types import EmbedResult, VerifyResult, PolicyConfig, PolicyBuilder, create_policy
from mnemo_sdk.errors import (
    MnemoException, MnemoAPIError, MnemoValidationError, MnemoErrorCode,
)

__version__ = "3.0.0"
__all__ = [
    "MnemoClient", "MnemoConfig", "MnemoBatch",
    "EmbedResult", "VerifyResult", "PolicyConfig", "PolicyBuilder", "create_policy",
    "MnemoException", "MnemoAPIError", "MnemoValidationError", "MnemoErrorCode",
]
