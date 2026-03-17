"""
Pytest configuration and shared fixtures.

Sets up the test environment for the Autonomaton test suite.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def setup_test_profile():
    """
    Automatically set the coach_demo profile before each test.

    This ensures routing.config and other config files are available.
    """
    from engine.profile import set_profile

    # Set to coach_demo profile for consistent test environment
    set_profile("coach_demo")

    yield

    # Cleanup: reset router cache after each test
    try:
        from engine.cognitive_router import reset_router
        reset_router()
    except ImportError:
        # Router not implemented yet - this is expected during TDD
        pass


@pytest.fixture
def mock_jidoka_approve():
    """
    Fixture to auto-approve Jidoka prompts for testing.

    Use this when testing yellow/red zone commands that would
    normally halt for human approval.
    """
    from unittest.mock import patch

    with patch('engine.ux.confirm_yellow_zone', return_value=True):
        yield


@pytest.fixture
def mock_jidoka_reject():
    """
    Fixture to auto-reject Jidoka prompts for testing.

    Use this to test rejection flows.
    """
    from unittest.mock import patch

    with patch('engine.ux.confirm_yellow_zone', return_value=False):
        yield
