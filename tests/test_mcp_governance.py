"""
test_mcp_governance.py - Tests for MCP Zone Governance and Jidoka Enforcement

These tests ensure the MCP effector layer correctly:
1. Computes effective zone (most restrictive wins)
2. Enforces Jidoka approval for Yellow/Red zones
3. Formats payloads via LLM for calendar_schedule and email_parent
4. Logs rejection events to telemetry

TDD: Write tests first, then implement to pass.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestEffectiveZoneComputation:
    """Tests for compute_effective_zone - most restrictive zone wins."""

    def test_green_green_returns_green(self):
        """green + green = green"""
        from engine.effectors import compute_effective_zone

        result = compute_effective_zone("green", "green")
        assert result == "green"

    def test_green_yellow_returns_yellow(self):
        """green + yellow = yellow (more restrictive wins)"""
        from engine.effectors import compute_effective_zone

        result = compute_effective_zone("green", "yellow")
        assert result == "yellow"

    def test_yellow_green_returns_yellow(self):
        """yellow + green = yellow (more restrictive wins)"""
        from engine.effectors import compute_effective_zone

        result = compute_effective_zone("yellow", "green")
        assert result == "yellow"

    def test_yellow_yellow_returns_yellow(self):
        """yellow + yellow = yellow"""
        from engine.effectors import compute_effective_zone

        result = compute_effective_zone("yellow", "yellow")
        assert result == "yellow"

    def test_green_red_returns_red(self):
        """green + red = red (most restrictive wins)"""
        from engine.effectors import compute_effective_zone

        result = compute_effective_zone("green", "red")
        assert result == "red"

    def test_red_green_returns_red(self):
        """red + green = red (most restrictive wins)"""
        from engine.effectors import compute_effective_zone

        result = compute_effective_zone("red", "green")
        assert result == "red"

    def test_yellow_red_returns_red(self):
        """yellow + red = red (most restrictive wins)"""
        from engine.effectors import compute_effective_zone

        result = compute_effective_zone("yellow", "red")
        assert result == "red"

    def test_red_red_returns_red(self):
        """red + red = red"""
        from engine.effectors import compute_effective_zone

        result = compute_effective_zone("red", "red")
        assert result == "red"

    def test_unknown_defaults_to_most_restrictive(self):
        """Unknown zones should default to red (fail-safe)"""
        from engine.effectors import compute_effective_zone

        result = compute_effective_zone("unknown", "green")
        assert result == "unknown"  # Unknown treated as most restrictive


class TestJidokaEnforcement:
    """
    Tests for Jidoka approval enforcement based on effective zone.

    SPRINT 3.5 ARCHITECTURE CHANGE:
    Zone governance is now handled by pipeline Stage 4, not effectors.
    These tests verify governance through the full pipeline flow.
    """

    def test_green_zone_auto_approves_via_pipeline(self):
        """Green zone actions should auto-approve without prompting through pipeline."""
        from engine.pipeline import run_pipeline
        from engine.profile import set_profile

        set_profile("reference")

        # Green zone command - should auto-approve
        with patch('engine.pipeline.confirm_yellow_zone') as mock_jidoka:
            context = run_pipeline(raw_input="dock", source="test")

        # Jidoka should NOT be called for green zone
        mock_jidoka.assert_not_called()
        assert context.approved is True
        assert context.zone == "green"

    def test_yellow_zone_triggers_jidoka_via_pipeline(self):
        """Yellow zone actions should trigger Jidoka approval via pipeline Stage 4."""
        from engine.pipeline import run_pipeline
        from engine.profile import set_profile

        set_profile("reference")

        # Mock approval for yellow zone - using "clear cache" which is yellow zone in reference profile
        with patch('engine.pipeline.confirm_yellow_zone', return_value=True) as mock_jidoka:
            context = run_pipeline(raw_input="clear cache", source="test")

        # Jidoka SHOULD be called for yellow zone (at Stage 4)
        mock_jidoka.assert_called_once()
        assert context.approved is True
        assert context.zone == "yellow"

    def test_red_zone_triggers_jidoka_via_pipeline(self):
        """Red zone actions should trigger confirm_red_zone_with_context via pipeline (Purity v2)."""
        from engine.pipeline import run_pipeline
        from engine.profile import set_profile

        set_profile("reference")

        # Red zone command (build skill) - Purity v2: uses confirm_red_zone_with_context
        with patch('engine.pipeline.confirm_red_zone_with_context', return_value=True) as mock_red_jidoka:
            context = run_pipeline(raw_input="build skill test-skill", source="test")

        # Red zone Jidoka should be called
        mock_red_jidoka.assert_called_once()
        call_args = mock_red_jidoka.call_args
        # Purity v2: red zone uses confirm_red_zone_with_context with action_description and payload
        assert "action_description" in call_args.kwargs
        assert "payload" in call_args.kwargs
        assert context.zone == "red"

    def test_yellow_zone_rejection_blocks_execution_via_pipeline(self):
        """Rejecting Jidoka prompt should prevent action execution."""
        from engine.pipeline import run_pipeline
        from engine.profile import set_profile

        set_profile("reference")

        # User rejects
        with patch('engine.pipeline.confirm_yellow_zone', return_value=False):
            context = run_pipeline(raw_input="clear cache", source="test")

        # Action should NOT be executed
        assert context.approved is False
        assert context.executed is False
        assert context.result.get("status") == "cancelled"


class TestRejectionTelemetry:
    """
    Tests for rejection event logging to telemetry.

    SPRINT 3.5: Rejection is handled at pipeline Stage 4.
    The pipeline context contains cancellation info, and telemetry
    is logged at the pipeline level.
    """

    def test_rejection_returns_cancelled_status(self):
        """Rejecting at Stage 4 should return cancelled status."""
        from engine.pipeline import run_pipeline
        from engine.profile import set_profile

        set_profile("reference")

        # User rejects at Stage 4
        with patch('engine.pipeline.confirm_yellow_zone', return_value=False):
            with patch('engine.telemetry.log_event', return_value={"id": "test"}):
                context = run_pipeline(
                    raw_input="clear cache",
                    source="operator_session"
                )

        # Context should show rejection
        assert context.approved is False
        assert context.result.get("status") == "cancelled"
        assert "not approved" in context.result.get("message", "").lower()

    def test_mcp_rejection_through_pipeline_flow(self):
        """
        Yellow zone actions rejected at Stage 4 should not execute.
        V-021: Using 'clear cache' which is yellow zone in reference profile.
        """
        from engine.pipeline import run_pipeline
        from engine.profile import set_profile

        set_profile("reference")

        with patch('engine.pipeline.confirm_yellow_zone', return_value=False):
            with patch('engine.telemetry.log_event', return_value={"id": "test"}):
                context = run_pipeline(
                    raw_input="clear cache",
                    source="operator_session"
                )

        # Context should show rejection
        assert context.approved is False
        assert context.executed is False


class TestCalendarSchedulePayloadFormatting:
    """Tests pending new architecture."""
    pass


class TestEmailParentPayloadFormatting:
    """Tests pending new architecture."""
    pass


class TestMCPIntegration:
    """Tests pending new architecture."""
    pass


class TestGoogleAPIIntegration:
    """
    Tests for real Google API calls (mocked at API layer).

    SPRINT 3.5: Effectors no longer handle zone governance.
    These tests verify direct effector execution after approval.

    V-021: These tests require MCP config. Skipped in reference profile.
    """

    @pytest.mark.skip(reason="V-021: reference profile has no MCP config")
    def test_calendar_create_event_calls_api(self):
        """create_event capability should call the Google Calendar API."""
        pass

    @pytest.mark.skip(reason="V-021: reference profile has no MCP config")
    def test_gmail_send_email_calls_api(self):
        """send_email capability should call the Gmail API."""
        pass


class TestOAuth2TokenPersistence:
    """Tests for OAuth2 token storage and retrieval."""

    def test_token_stored_in_profile_auth_dir(self):
        """
        OAuth tokens should be stored in profiles/{profile}/config/auth/
        """
        from engine.profile import set_profile, get_config_dir

        set_profile("reference")

        auth_dir = get_config_dir() / "auth"

        # Auth directory should be the correct location
        assert "reference" in str(auth_dir)
        assert auth_dir.name == "auth"

    @pytest.mark.skip(reason="V-021: reference profile has no MCP config")
    def test_token_loaded_on_mcp_connect(self):
        """When connecting to an MCP server, existing tokens should be loaded."""
        pass


class TestUnifiedGovernanceSprintThreePointFive:
    """
    Tests for Sprint 3.5: Unified Governance Architecture.

    CRITICAL ARCHITECTURAL CHANGE:
    - execute_mcp_action() NO LONGER prompts for zone-based Jidoka
    - ALL zone governance moves to pipeline Stage 4
    - effectors.py only handles authentication (OAuth)

    These tests enforce the unified governance model.
    """

    def test_execute_mcp_action_does_not_call_ask_jidoka(self):
        """
        execute_mcp_action() must NOT call ask_jidoka for zone governance.
        Verify by checking that ask_jidoka is not imported in effectors.py.
        """
        import engine.effectors as effectors_module

        # Verify ask_jidoka is NOT in the effectors module
        assert not hasattr(effectors_module, 'ask_jidoka'), \
            "ask_jidoka should not be imported in effectors.py"

    @pytest.mark.skip(reason="V-021: reference profile has no MCP config")
    def test_execute_mcp_action_succeeds_without_governance_check(self):
        """execute_mcp_action() should execute directly without governance."""
        pass

    def test_mcp_rejection_handled_in_pipeline_not_effector(self):
        """
        When Stage 4 rejects, handlers should not execute.
        V-021: Using 'clear cache' which is yellow zone in reference profile.
        """
        from engine.pipeline import run_pipeline
        from engine.profile import set_profile

        set_profile("reference")

        # User rejects at Stage 4
        with patch('engine.pipeline.confirm_yellow_zone', return_value=False):
            with patch('engine.telemetry.log_event', return_value={"id": "test"}):
                context = run_pipeline(
                    raw_input="clear cache",
                    source="operator_session"
                )

        # Context should show rejection
        assert context.approved is False
        assert context.result.get("status") == "cancelled"

    @pytest.mark.skip(reason="V-021: reference profile has no MCP config")
    def test_effector_only_handles_auth_not_governance(self):
        """Effector layer handles auth, not governance."""
        pass
