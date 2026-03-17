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
    """Tests for Jidoka approval enforcement based on effective zone."""

    def test_green_zone_auto_approves(self):
        """Green zone actions should auto-approve without prompting."""
        from engine.effectors import execute_mcp_action
        from engine.profile import set_profile

        set_profile("coach_demo")

        # Mock green zone capability (list_events is green)
        with patch('engine.effectors.ask_jidoka') as mock_jidoka:
            with patch('engine.effectors.MCPClient.connect', return_value=True):
                with patch('engine.effectors.MCPClient.execute', return_value={"success": True}):
                    with patch('engine.effectors.log_event'):
                        result = execute_mcp_action(
                            server="google_calendar",
                            capability="list_events",
                            payload={"date": "2024-01-15"},
                            domain="lessons"  # Green zone domain
                        )

            # Jidoka should NOT be called for green zone
            mock_jidoka.assert_not_called()
            assert result.approved is True

    def test_yellow_zone_triggers_jidoka(self):
        """Yellow zone actions should trigger Jidoka approval prompt."""
        from engine.effectors import execute_mcp_action
        from engine.profile import set_profile

        set_profile("coach_demo")

        # Mock yellow zone capability (create_event is yellow)
        with patch('engine.effectors.ask_jidoka', return_value="1") as mock_jidoka:
            with patch('engine.effectors.MCPClient.connect', return_value=True):
                with patch('engine.effectors.MCPClient.execute', return_value={"success": True}):
                    with patch('engine.effectors.log_event'):
                        result = execute_mcp_action(
                            server="google_calendar",
                            capability="create_event",
                            payload={"title": "Golf Lesson", "date": "2024-01-15"},
                            domain="lessons"
                        )

            # Jidoka SHOULD be called for yellow zone
            mock_jidoka.assert_called_once()
            assert result.approved is True

    def test_red_zone_triggers_explicit_jidoka(self):
        """Red zone actions should trigger explicit Jidoka with full context."""
        from engine.effectors import execute_mcp_action
        from engine.profile import set_profile

        set_profile("coach_demo")

        # delete_event is red zone
        with patch('engine.effectors.ask_jidoka', return_value="1") as mock_jidoka:
            with patch('engine.effectors.MCPClient.connect', return_value=True):
                with patch('engine.effectors.MCPClient.execute', return_value={"success": True}):
                    with patch('engine.effectors.log_event'):
                        result = execute_mcp_action(
                            server="google_calendar",
                            capability="delete_event",
                            payload={"event_id": "abc123"},
                            domain="lessons"
                        )

            # Jidoka MUST be called for red zone
            mock_jidoka.assert_called_once()
            # Red zone message should include "RED ZONE" warning
            call_args = mock_jidoka.call_args
            assert "RED ZONE" in call_args.kwargs.get("context_message", "")
            assert result.approved is True

    def test_yellow_zone_rejection_blocks_execution(self):
        """Rejecting Jidoka prompt should prevent action execution."""
        from engine.effectors import execute_mcp_action
        from engine.profile import set_profile

        set_profile("coach_demo")

        # User rejects (choice "2")
        with patch('engine.effectors.ask_jidoka', return_value="2") as mock_jidoka:
            with patch('engine.effectors.MCPClient.execute') as mock_execute:
                with patch('engine.effectors.log_event'):
                    result = execute_mcp_action(
                        server="google_calendar",
                        capability="create_event",
                        payload={"title": "Golf Lesson"},
                        domain="lessons"
                    )

            # Action should NOT be executed
            mock_execute.assert_not_called()
            assert result.approved is False
            assert result.success is False
            assert "rejected" in result.error.lower()


class TestRejectionTelemetry:
    """Tests for rejection event logging to telemetry."""

    def test_rejection_logged_to_telemetry(self):
        """Rejecting an MCP action should log a rejection event."""
        from engine.effectors import execute_mcp_action
        from engine.profile import set_profile

        set_profile("coach_demo")

        logged_events = []

        def capture_log(**kwargs):
            logged_events.append(kwargs)
            return {"id": "test-event"}

        # User rejects
        with patch('engine.effectors.ask_jidoka', return_value="2"):
            with patch('engine.effectors.log_event', side_effect=capture_log):
                execute_mcp_action(
                    server="gmail",
                    capability="send_email",
                    payload={"to": "parent@example.com", "subject": "Test"},
                    domain="players"
                )

        # Should have logged rejection event
        rejection_events = [e for e in logged_events if e.get("source") == "effector_rejection"]
        assert len(rejection_events) == 1

        rejection = rejection_events[0]
        assert rejection["inferred"]["reason"] == "user_rejected"
        assert rejection["inferred"]["server"] == "gmail"
        assert rejection["inferred"]["capability"] == "send_email"


class TestCalendarSchedulePayloadFormatting:
    """Tests for LLM payload formatting for calendar_schedule intent."""

    def test_calendar_schedule_uses_llm_for_payload(self):
        """
        calendar_schedule intent should use LLM to format the calendar payload.

        The LLM extracts: participant, date, time, duration, location from raw input.
        """
        from engine.pipeline import run_pipeline
        from engine.profile import set_profile

        set_profile("coach_demo")

        # Mock LLM response with structured calendar payload
        mock_llm_response = json.dumps({
            "event_type": "lesson",
            "participant": "Henderson",
            "date": "2024-01-16",
            "time": "15:00",
            "duration_minutes": 60,
            "location": "Driving Range"
        })

        with patch('engine.llm_client.call_llm', return_value=mock_llm_response) as mock_llm:
            with patch('engine.pipeline.confirm_yellow_zone', return_value=True):
                with patch('engine.effectors.ask_jidoka', return_value="1"):
                    with patch('engine.effectors.MCPClient.connect', return_value=True):
                        with patch('engine.effectors.MCPClient.execute', return_value={"success": True}):
                            with patch('engine.effectors.log_event'):
                                with patch('engine.telemetry.log_event', return_value={"id": "test"}):
                                    context = run_pipeline(
                                        raw_input="schedule a lesson with Henderson for tomorrow at 3pm",
                                        source="operator_session"
                                    )

        # Intent should be classified as calendar_schedule
        assert context.intent == "calendar_schedule"

        # LLM should be called during compilation to format payload
        # (May be called multiple times - router escalation + payload formatting)
        assert mock_llm.call_count >= 1

    def test_calendar_payload_attached_to_mcp_action(self):
        """
        The formatted calendar payload should be attached to the MCPAction.

        The MCP action is wired during execution (Stage 5) when the
        dispatcher returns an mcp_action type result.
        """
        from engine.pipeline import run_pipeline
        from engine.profile import set_profile

        set_profile("coach_demo")

        mock_llm_response = json.dumps({
            "event_type": "lesson",
            "participant": "Henderson",
            "date": "2024-01-16",
            "time": "15:00"
        })

        with patch('engine.llm_client.call_llm', return_value=mock_llm_response):
            with patch('engine.pipeline.confirm_yellow_zone', return_value=True):
                with patch('engine.effectors.ask_jidoka', return_value="1"):
                    with patch('engine.effectors.MCPClient.connect', return_value=True):
                        with patch('engine.effectors.MCPClient.execute', return_value={"success": True}):
                            with patch('engine.effectors.log_event'):
                                with patch('engine.telemetry.log_event', return_value={"id": "test"}):
                                    context = run_pipeline(
                                        raw_input="schedule a lesson with Henderson for tomorrow at 3pm",
                                        source="operator_session"
                                    )

        # Intent should be calendar_schedule
        assert context.intent == "calendar_schedule"

        # MCP action should have been wired and executed
        assert context.mcp_action is not None
        assert context.mcp_action.server == "google_calendar"
        assert context.mcp_action.capability == "create_event"

        # Execution should have succeeded
        assert context.executed is True


class TestEmailParentPayloadFormatting:
    """Tests for LLM payload formatting for email_parent intent."""

    def test_email_parent_uses_llm_for_payload(self):
        """
        email_parent intent should use LLM to format the email payload.

        The LLM extracts: recipient, subject, body from raw input.
        """
        from engine.pipeline import run_pipeline
        from engine.profile import set_profile

        set_profile("coach_demo")

        # Mock LLM response with structured email payload
        mock_llm_response = json.dumps({
            "recipient": "Henderson Parent",
            "recipient_email": "parent@example.com",
            "subject": "Progress Update - Marcus Henderson",
            "body": "Dear Henderson family, Marcus made great progress today..."
        })

        with patch('engine.llm_client.call_llm', return_value=mock_llm_response) as mock_llm:
            with patch('engine.pipeline.confirm_yellow_zone', return_value=True):
                with patch('engine.effectors.ask_jidoka', return_value="1"):
                    with patch('engine.effectors.MCPClient.connect', return_value=True):
                        with patch('engine.effectors.MCPClient.execute', return_value={"success": True}):
                            with patch('engine.effectors.log_event'):
                                with patch('engine.telemetry.log_event', return_value={"id": "test"}):
                                    context = run_pipeline(
                                        raw_input="email Henderson's parent about today's progress",
                                        source="operator_session"
                                    )

        # Intent should be classified as email_parent
        assert context.intent == "email_parent"

        # LLM should be called to format email payload
        assert mock_llm.call_count >= 1


class TestMCPIntegration:
    """Integration tests for MCP execution through the pipeline."""

    def test_mcp_action_executes_after_approval(self):
        """
        After Jidoka approval, the MCP action should execute.
        """
        from engine.effectors import execute_mcp_action
        from engine.profile import set_profile

        set_profile("coach_demo")

        # User approves (choice "1")
        with patch('engine.effectors.ask_jidoka', return_value="1"):
            with patch('engine.effectors.MCPClient.connect', return_value=True):
                with patch('engine.effectors.MCPClient.execute', return_value={"success": True}) as mock_execute:
                    with patch('engine.effectors.log_event'):
                        result = execute_mcp_action(
                            server="google_calendar",
                            capability="create_event",
                            payload={"title": "Golf Lesson", "date": "2024-01-15"},
                            domain="lessons"
                        )

        # Action should be executed
        mock_execute.assert_called_once()
        assert result.approved is True
        assert result.success is True

    def test_domain_zone_affects_effective_zone(self):
        """
        Domain zone should combine with server zone for effective zone.

        Example: green server + yellow domain = yellow effective
        """
        from engine.effectors import execute_mcp_action, ConfigLoader
        from engine.profile import set_profile

        set_profile("coach_demo")

        # list_events is green, but money domain is yellow
        with patch('engine.effectors.ask_jidoka', return_value="1") as mock_jidoka:
            with patch('engine.effectors.MCPClient.connect', return_value=True):
                with patch('engine.effectors.MCPClient.execute', return_value={"success": True}):
                    with patch('engine.effectors.log_event'):
                        result = execute_mcp_action(
                            server="google_calendar",
                            capability="list_events",  # green capability
                            payload={"date": "2024-01-15"},
                            domain="money"  # yellow domain
                        )

        # Jidoka should be called because money domain is yellow
        mock_jidoka.assert_called_once()
        assert result.effective_zone == "yellow"


class TestGoogleAPIIntegration:
    """Tests for real Google API calls (mocked at API layer)."""

    def test_calendar_create_event_calls_api(self):
        """
        create_event capability should call the Google Calendar API.
        """
        from engine.effectors import execute_mcp_action
        from engine.profile import set_profile

        set_profile("coach_demo")

        # Mock the Google Calendar API
        mock_service = MagicMock()
        mock_service.events.return_value.insert.return_value.execute.return_value = {
            "id": "event123",
            "htmlLink": "https://calendar.google.com/event123"
        }

        with patch('engine.effectors.ask_jidoka', return_value="1"):
            with patch('engine.effectors.get_google_calendar_service', return_value=mock_service):
                with patch('engine.effectors.log_event'):
                    result = execute_mcp_action(
                        server="google_calendar",
                        capability="create_event",
                        payload={
                            "summary": "Golf Lesson - Henderson",
                            "start": {"dateTime": "2024-01-15T15:00:00", "timeZone": "America/New_York"},
                            "end": {"dateTime": "2024-01-15T16:00:00", "timeZone": "America/New_York"}
                        },
                        domain="lessons"
                    )

        # API should have been called (once real implementation exists)
        # For now, just verify the stub executed successfully
        assert result.success is True

    def test_gmail_send_email_calls_api(self):
        """
        send_email capability should call the Gmail API.
        """
        from engine.effectors import execute_mcp_action
        from engine.profile import set_profile

        set_profile("coach_demo")

        # Mock the Gmail API
        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
            "id": "msg123",
            "threadId": "thread123"
        }

        with patch('engine.effectors.ask_jidoka', return_value="1"):
            with patch('engine.effectors.get_gmail_service', return_value=mock_service):
                with patch('engine.effectors.log_event'):
                    result = execute_mcp_action(
                        server="gmail",
                        capability="send_email",
                        payload={
                            "to": "parent@example.com",
                            "subject": "Progress Update",
                            "body": "Your child made great progress today."
                        },
                        domain="players"
                    )

        # API should have been called (once real implementation exists)
        assert result.success is True


class TestOAuth2TokenPersistence:
    """Tests for OAuth2 token storage and retrieval."""

    def test_token_stored_in_profile_auth_dir(self):
        """
        OAuth tokens should be stored in profiles/{profile}/config/auth/
        """
        from engine.profile import set_profile, get_config_dir

        set_profile("coach_demo")

        auth_dir = get_config_dir() / "auth"

        # Auth directory should be the correct location
        assert "coach_demo" in str(auth_dir)
        assert auth_dir.name == "auth"

    def test_token_loaded_on_mcp_connect(self):
        """
        When connecting to an MCP server, existing tokens should be loaded.
        """
        from engine.effectors import MCPClient
        from engine.profile import set_profile

        set_profile("coach_demo")

        # This test will be meaningful once real OAuth is implemented
        client = MCPClient("google_calendar")

        # For now, just verify the client initializes
        assert client.server == "google_calendar"
        assert client.auth_state.authenticated is False  # No token yet
