"""
Pytest configuration and shared fixtures.

V-009 Phase 1: Telemetry-based test fixtures for the Autonomaton
reference implementation. ALL architecture tests run against the
reference profile — the naked engine with no domain assumptions.

Profile Isolation (Invariant #6): The engine is domain-agnostic.
Architecture tests prove this by testing the reference profile,
which has no domain config, no startup ceremonies, no skills.
"""

import pytest
import sys
import yaml
from pathlib import Path
from unittest.mock import patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# =========================================================================
# Pipeline Stage Constants
# =========================================================================

# The five canonical pipeline stages (white paper Part III: "The Pipeline").
# Tests filter telemetry for these stages to enforce the hourglass invariant.
PIPELINE_STAGES = {"telemetry", "recognition", "compilation", "approval", "execution"}



# =========================================================================
# Profile Setup — Reference Profile for ALL Architecture Tests
# =========================================================================

@pytest.fixture(autouse=True)
def setup_reference_profile():
    """
    Set the reference profile before each test. Auto-applied.

    White paper Part VIII: "You spent a weekend. You built what most
    enterprise AI teams haven't built after months." The reference
    profile IS the weekend build. Architecture tests validate it.

    Also clears the pattern cache to prevent cross-test contamination.
    Fate-Sharing (TCP/IP paper §III): each test maintains its own state.
    """
    from engine.profile import set_profile, get_config_dir

    set_profile("reference")

    # Save and clear pattern cache before each test
    cache_path = get_config_dir() / "pattern_cache.yaml"
    original_cache = None
    if cache_path.exists():
        original_cache = cache_path.read_text(encoding="utf-8")
        with open(cache_path, "w", encoding="utf-8") as f:
            yaml.dump({"cache": {}}, f, default_flow_style=False)

    yield

    # Restore original cache after test
    if original_cache is not None:
        cache_path.write_text(original_cache, encoding="utf-8")
    elif cache_path.exists():
        with open(cache_path, "w", encoding="utf-8") as f:
            yaml.dump({"cache": {}}, f, default_flow_style=False)

    # Reset router cache
    try:
        from engine.cognitive_router import reset_router
        reset_router()
    except ImportError:
        pass



# =========================================================================
# V-009 Telemetry-Based Test Fixtures
# =========================================================================

@pytest.fixture
def telemetry_sink():
    """
    Captures telemetry entries in memory for assertion.

    Feed-First Telemetry (white paper Part III): "The telemetry stream
    is the single source of truth for audit, learning, and observability."

    Tests read traces and assert on structured properties. The trace IS
    the contract. Glass is presentation.
    """
    entries = []

    def capture_log_event(**kwargs):
        from engine.telemetry import create_event
        event = create_event(**kwargs)
        entries.append(event)
        return event

    with patch('engine.pipeline.log_event', side_effect=capture_log_event):
        with patch('engine.telemetry.log_event', side_effect=capture_log_event):
            yield entries


@pytest.fixture
def mock_llm():
    """
    Returns deterministic LLM responses. Queue strings for sequential calls.

    Model Independence (Principle 7, white paper Part IX): "The system's
    intelligence lives in its architecture, not its model." Tests mock
    the LLM because the pipeline doesn't care which model responded.

    Accepts the FULL call_llm signature: prompt, tier, intent, system,
    max_tokens. Handlers like general_chat pass system prompts.
    """
    responses = []

    def _mock_call(prompt, tier=2, intent="", system=None, max_tokens=None):
        if responses:
            return responses.pop(0)
        return "Mocked LLM response."

    with patch('engine.llm_client.call_llm', side_effect=_mock_call):
        yield responses


@pytest.fixture
def mock_ux_input():
    """
    Simulates operator choices at Kaizen prompts.

    Digital Jidoka (white paper Part II): the system stops when uncertain.
    Tests mock the operator's menu selections to exercise each consent path.

    Queue choices in the order they'll be requested:
        "1" = LLM classify, "2" = local context, "3" = config menu, "4" = cancel
    """
    choices = []

    def _mock_jidoka(context_message, options):
        if choices:
            return choices.pop(0)
        return "1"

    with patch('engine.ux.ask_jidoka', side_effect=_mock_jidoka):
        yield choices



# =========================================================================
# Legacy Fixtures (retained for backward compatibility)
# =========================================================================

@pytest.fixture
def mock_jidoka_approve():
    """Auto-approve Jidoka prompts for testing yellow/red zone commands."""
    with patch('engine.ux.confirm_yellow_zone', return_value=True):
        yield


@pytest.fixture
def mock_jidoka_reject():
    """Auto-reject Jidoka prompts for testing rejection flows."""
    with patch('engine.ux.confirm_yellow_zone', return_value=False):
        yield
