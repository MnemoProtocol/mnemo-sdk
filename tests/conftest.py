"""Shared test fixtures for the Mnemo SDK test suite."""

import pytest


@pytest.fixture
def mock_api_url():
    """Base URL used by tests to avoid hitting a real server."""
    return "https://mnemo.test"


@pytest.fixture
def mock_api_key():
    """Dummy API key used in tests."""
    return "test-api-key-000"
