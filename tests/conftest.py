"""Shared test fixtures and markers for the Helix test suite."""

from unittest.mock import MagicMock

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers with pytest."""
    config.addinivalue_line(
        "markers",
        "pit_check: marks tests as Point-in-Time compliance checks",
    )


@pytest.fixture
def sim_adapter() -> None:
    """Placeholder fixture for SimAdapter — wired in Plan 04."""
    return None


@pytest.fixture
def mock_mt5() -> MagicMock:
    """Placeholder fixture providing a MagicMock for the MT5 adapter."""
    return MagicMock()


@pytest.fixture
def zmq_context() -> None:
    """Placeholder fixture for ZeroMQ context — wired in Plan 07."""
    return None
