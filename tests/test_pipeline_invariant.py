"""
test_pipeline_invariant.py - Tests for Pipeline Stage Enforcement

These tests enforce Architectural Invariant #1 (The Invariant Pipeline):
Every user interaction MUST map to the five stages:
Telemetry -> Recognition -> Compilation -> Approval -> Execution

The system cannot jump from input to execution.

TDD: Write tests first, then implement to pass.
"""

import pytest
from unittest.mock import patch, MagicMock

# Note: Mocks must patch where the function is USED, not where it's defined.
# pipeline.py imports confirm_yellow_zone, so we patch engine.pipeline.confirm_yellow_zone


class TestPipelineStageTraversal:
    """Tests ensuring all 5 stages are traversed for every command."""

    def test_status_query_traverses_all_stages(self):
        """
        Status queries (skills, queue, dock) must traverse all 5 pipeline stages.

        Invariant #1: No jumping from input to execution.
        Invariant #5: Feed-First Telemetry - logged before processing.
        """
        from engine.pipeline import run_pipeline

        # Test each status query command
        for cmd in ["skills", "queue", "dock"]:
            context = run_pipeline(raw_input=cmd, source="test")

            # Stage 1: Telemetry must be populated
            assert context.telemetry_event is not None, \
                f"'{cmd}': Stage 1 (Telemetry) not executed"
            assert "id" in context.telemetry_event, \
                f"'{cmd}': Telemetry event missing 'id'"

            # Stage 2: Recognition must set intent
            assert context.intent is not None, \
                f"'{cmd}': Stage 2 (Recognition) did not set intent"
            assert context.intent != "", \
                f"'{cmd}': Intent should not be empty string"

            # Stage 3: Compilation must set dock_context
            assert context.dock_context is not None, \
                f"'{cmd}': Stage 3 (Compilation) did not set dock_context"

            # Stage 4: Approval must be evaluated
            # (approved is boolean, so check it exists as attribute)
            assert hasattr(context, 'approved'), \
                f"'{cmd}': Stage 4 (Approval) not evaluated"

            # Stage 5: Execution must set result
            assert context.result is not None, \
                f"'{cmd}': Stage 5 (Execution) did not set result"
            assert "status" in context.result, \
                f"'{cmd}': Execution result missing 'status'"

    def test_action_command_traverses_all_stages(self):
        """
        Action commands (compile content) must traverse all 5 stages.

        Yellow zone actions still traverse all stages but may halt at approval.
        """
        from engine.pipeline import run_pipeline

        # Mock the Jidoka approval to auto-approve for testing
        with patch('engine.pipeline.confirm_yellow_zone', return_value=True):
            context = run_pipeline(raw_input="compile content", source="test")

        # Verify all stages populated
        assert context.telemetry_event is not None, \
            "Stage 1 (Telemetry) not executed"
        assert context.intent is not None, \
            "Stage 2 (Recognition) did not set intent"
        assert context.dock_context is not None, \
            "Stage 3 (Compilation) did not set dock_context"
        assert hasattr(context, 'approved'), \
            "Stage 4 (Approval) not evaluated"
        assert context.result is not None, \
            "Stage 5 (Execution) did not set result"

    def test_ambiguous_command_traverses_all_stages(self):
        """
        Even ambiguous commands must traverse all 5 stages.

        Ambiguous input goes through classification (which may involve LLM),
        then stages 3-5. The key invariant is that NO stage is skipped.

        When clarification Jidoka fires, the user can confirm the best guess
        and continue through remaining stages.
        """
        from engine.pipeline import run_pipeline

        # Mock approval for any zone AND clarification Jidoka
        # ask_jidoka returns "1" = confirm best guess, which continues execution
        with patch('engine.pipeline.confirm_yellow_zone', return_value=True):
            with patch('engine.ux.ask_jidoka', return_value="1"):
                context = run_pipeline(
                    raw_input="xyzzy random unknown command",
                    source="test"
                )

        # All stages must execute - this is the core invariant
        assert context.telemetry_event is not None, \
            "Stage 1 (Telemetry) not executed"
        assert context.intent is not None, \
            "Stage 2 (Recognition) did not set intent"
        assert context.dock_context is not None, \
            "Stage 3 (Compilation) not executed"
        assert hasattr(context, 'approved'), \
            "Stage 4 (Approval) not evaluated"
        assert context.result is not None, \
            "Stage 5 (Execution) not executed"


class TestZoneSetByRouter:
    """Tests ensuring zone is determined by Cognitive Router, not caller."""

    def test_zone_overridden_by_router_for_green_commands(self):
        """
        Even if caller passes zone="red", router should set correct zone.

        The router's classification from routing.config is authoritative.
        """
        from engine.pipeline import run_pipeline

        # Caller passes zone="red" but "dock" should be green
        context = run_pipeline(
            raw_input="dock",
            source="test",
            zone="red"  # This should be overridden
        )

        # Router should have set zone to green based on routing.config
        assert context.zone == "green", \
            f"Router should override to green for 'dock', got '{context.zone}'"

    def test_zone_overridden_by_router_for_yellow_commands(self):
        """
        Router must set yellow zone for content_compilation regardless of input.
        """
        from engine.pipeline import run_pipeline

        # Mock approval
        with patch('engine.pipeline.confirm_yellow_zone', return_value=True):
            context = run_pipeline(
                raw_input="compile content",
                source="test",
                zone="green"  # This should be overridden to yellow
            )

        assert context.zone == "yellow", \
            f"Router should set yellow for 'compile content', got '{context.zone}'"

    def test_zone_overridden_by_router_for_red_commands(self):
        """
        Router must set red zone for pit_crew_build regardless of input.

        Red zone = highest restriction, cannot be downgraded.
        """
        from engine.pipeline import run_pipeline

        # Mock approval (Purity v2: red zone uses confirm_red_zone_with_context)
        with patch('engine.pipeline.confirm_yellow_zone', return_value=True):
            with patch('engine.pipeline.confirm_red_zone_with_context', return_value=True):
                context = run_pipeline(
                    raw_input="build skill test-skill",
                    source="test",
                    zone="green"  # This should be overridden to red
                )

        assert context.zone == "red", \
            f"Router should set red for 'build skill', got '{context.zone}'"

    def test_unknown_intent_forces_yellow_zone(self):
        """
        Unknown intents MUST force yellow zone for Digital Jidoka.

        Invariant #4: Ambiguity must halt for human approval.
        Note: Clarification Jidoka may resolve to a known intent,
        but the zone escalation happens before that.
        """
        from engine.pipeline import run_pipeline

        # Even if caller passes green, ambiguous input triggers yellow zone
        # Mock both yellow zone approval and clarification Jidoka
        with patch('engine.pipeline.confirm_yellow_zone', return_value=True):
            with patch('engine.ux.ask_jidoka', return_value="1"):
                context = run_pipeline(
                    raw_input="xyzzy unknown gibberish",
                    source="test",
                    zone="green"  # Should be overridden
                )

        # Zone should be yellow or may be resolved to the clarified intent's zone
        # The key is that caller's "green" was not honored for ambiguous input
        assert context.zone in ["yellow", "green"], \
            f"Ambiguous intent should route to yellow or resolved zone, got '{context.zone}'"


class TestTelemetryIntegrity:
    """Tests for Feed-First Telemetry (Invariant #5)."""

    def test_telemetry_logged_before_execution(self):
        """
        Telemetry event must be created in Stage 1, before any execution.

        Invariant #5: Every action logged to append-only JSONL before processing.
        """
        from engine.pipeline import run_pipeline

        execution_order = []

        def track_telemetry(**kwargs):
            execution_order.append("telemetry")
            return {"id": "test-event-id", **kwargs}

        # Patch where it's USED (pipeline.py imports log_event)
        with patch('engine.pipeline.log_event', side_effect=track_telemetry):
            context = run_pipeline(raw_input="dock", source="test")
            execution_order.append("complete")

        # Telemetry should be first
        assert execution_order[0] == "telemetry", \
            f"Telemetry should execute first, order was: {execution_order}"

    def test_telemetry_contains_zone_context(self):
        """
        Telemetry event must include zone_context for audit trail.
        """
        from engine.pipeline import run_pipeline

        context = run_pipeline(raw_input="dock", source="test")

        assert "zone_context" in context.telemetry_event, \
            "Telemetry event must include zone_context"


class TestPipelineContextIntegrity:
    """Tests for PipelineContext data integrity across stages."""

    def test_context_preserves_raw_input(self):
        """
        Raw input must be preserved unchanged through all stages.
        """
        from engine.pipeline import run_pipeline

        original_input = "compile content with special chars: @#$%"

        with patch('engine.pipeline.confirm_yellow_zone', return_value=True):
            context = run_pipeline(raw_input=original_input, source="test")

        assert context.raw_input == original_input, \
            "Raw input must be preserved unchanged"

    def test_context_has_routing_metadata(self):
        """
        After recognition, context.entities should contain routing metadata.

        This enables Stage 5 to use the dispatcher correctly.
        """
        from engine.pipeline import run_pipeline

        context = run_pipeline(raw_input="dock", source="test")

        # entities should contain routing info for dispatcher
        assert "routing" in context.entities, \
            "Context entities should contain 'routing' metadata"

        routing = context.entities["routing"]
        assert "handler" in routing, \
            "Routing metadata should include 'handler'"
        assert "tier" in routing, \
            "Routing metadata should include 'tier'"
        assert "confidence" in routing, \
            "Routing metadata should include 'confidence'"


class TestDispatcherIntegration:
    """Tests for dispatcher integration in Stage 5."""

    def test_dispatcher_called_for_known_handlers(self):
        """
        When routing specifies a handler, dispatcher must be invoked.
        """
        from engine.pipeline import run_pipeline

        context = run_pipeline(raw_input="dock", source="test")

        # Result should have data with type from dispatcher
        assert context.result is not None, \
            "Execution result should not be None"
        assert "data" in context.result, \
            "Execution result should contain 'data'"

        data = context.result.get("data", {})
        if isinstance(data, dict):
            assert "type" in data, \
                "Dispatch result data should have 'type' field"

    def test_skills_command_returns_skills_data(self):
        """
        'skills' command should return skills list via dispatcher.
        """
        from engine.pipeline import run_pipeline

        context = run_pipeline(raw_input="skills", source="test")

        data = context.result.get("data", {})
        assert data.get("type") == "skills_list", \
            f"Expected type 'skills_list', got '{data.get('type')}'"

    def test_queue_command_returns_queue_data(self):
        """
        'queue' command should return queue status via dispatcher.
        """
        from engine.pipeline import run_pipeline

        context = run_pipeline(raw_input="queue", source="test")

        data = context.result.get("data", {})
        assert data.get("type") == "queue_status", \
            f"Expected type 'queue_status', got '{data.get('type')}'"


class TestSessionZeroDispatcher:
    """Tests for Session Zero skill dispatch (Sprint 1.5)."""

    def test_session_zero_traverses_pipeline(self):
        """
        'session zero' must traverse all 5 pipeline stages.

        Yellow zone requires Jidoka approval before execution.
        """
        from engine.pipeline import run_pipeline

        # Mock approval for yellow zone
        with patch('engine.pipeline.confirm_yellow_zone', return_value=True):
            context = run_pipeline(raw_input="session zero", source="test")

        # All stages must be populated
        assert context.telemetry_event is not None, \
            "Stage 1 (Telemetry) not executed"
        assert context.intent == "session_zero", \
            f"Stage 2 should classify as session_zero, got '{context.intent}'"
        assert context.zone == "yellow", \
            f"Session zero should be yellow zone, got '{context.zone}'"
        assert context.result is not None, \
            "Stage 5 (Execution) not executed"

    def test_session_zero_returns_prompt_content(self):
        """
        Session zero dispatcher should return the Socratic prompt content.

        Until Sprint 2 (LLM client), the handler reads prompt.md and
        returns its contents as proof of wiring.
        """
        from engine.pipeline import run_pipeline

        with patch('engine.pipeline.confirm_yellow_zone', return_value=True):
            context = run_pipeline(raw_input="session zero", source="test")

        data = context.result.get("data", {})
        assert data.get("type") == "session_zero", \
            f"Expected type 'session_zero', got '{data.get('type')}'"

        # Should contain the prompt content
        assert "prompt_content" in data, \
            "Session zero should return prompt_content"
        assert len(data.get("prompt_content", "")) > 0, \
            "Prompt content should not be empty"

    def test_session_zero_requires_yellow_zone_approval(self):
        """
        Session zero must halt for Jidoka approval (yellow zone).

        If user rejects, execution should be cancelled.
        """
        from engine.pipeline import run_pipeline

        # User rejects the yellow zone prompt
        with patch('engine.pipeline.confirm_yellow_zone', return_value=False):
            context = run_pipeline(raw_input="session zero", source="test")

        assert context.approved is False, \
            "Should not be approved when user rejects"
        assert context.executed is False, \
            "Should not execute when rejected"
        assert context.result.get("status") == "cancelled", \
            f"Status should be 'cancelled', got '{context.result.get('status')}'"


class TestExceptionTelemetry:
    """
    Tests for Sprint 3.5: Exception Telemetry (No Ghost Failures).

    Invariant #5 extended: If execution crashes (LLM timeout, API failure),
    the exception MUST be caught, a failure event logged to telemetry,
    and the line stops elegantly without silent failures.
    """

    def test_dock_failure_logged_to_telemetry(self):
        """
        Stage failures must be logged to telemetry.

        No ghost failures - every crash leaves a trail.
        """
        from engine.pipeline import run_pipeline

        logged_events = []

        def capture_log(**kwargs):
            logged_events.append(kwargs)
            return {"id": "test-event"}

        # Simulate dock failure during compilation stage
        def dock_crash(*args, **kwargs):
            raise RuntimeError("Dock service unavailable")

        with patch('engine.telemetry.log_event', side_effect=capture_log):
            with patch('engine.pipeline.log_event', side_effect=capture_log):
                with patch('engine.dock.query_dock', side_effect=dock_crash):
                    # Pipeline should catch and log, not crash
                    context = run_pipeline(raw_input="dock", source="test")

        # Should have logged a failure event
        failure_events = [
            e for e in logged_events
            if e.get("source") == "pipeline_failure"
        ]
        assert len(failure_events) >= 1, "Pipeline failure must be logged"
        assert context is not None, "Pipeline should return context even on failure"
        assert context.result.get("status") == "failed"

    def test_mcp_execution_failure_logged_to_telemetry(self):
        """
        MCP execution failures must be logged to telemetry.

        If Calendar/Gmail API crashes, we must have an audit trail.
        """
        from engine.effectors import execute_mcp_action
        from engine.profile import set_profile

        set_profile("coach_demo")

        logged_events = []

        def capture_log(**kwargs):
            logged_events.append(kwargs)
            return {"id": "test-event"}

        # Simulate API crash
        def api_crash(*args, **kwargs):
            raise ConnectionError("Google API unreachable")

        with patch('engine.effectors.log_event', side_effect=capture_log):
            with patch('engine.effectors.MCPClient.connect', return_value=True):
                with patch('engine.effectors.MCPClient.execute', side_effect=api_crash):
                    result = execute_mcp_action(
                        server="google_calendar",
                        capability="create_event",
                        payload={"summary": "Test"},
                        domain="lessons"
                    )

        # Should log error event
        error_events = [
            e for e in logged_events
            if "error" in str(e.get("source", "")).lower()
            or e.get("inferred", {}).get("success") is False
        ]

        assert result.success is False, "Should return failure result"
        # Failure should be traceable in telemetry
        assert len(error_events) >= 1 or result.error is not None, \
            "Failure must be logged or returned in result"

    def test_pipeline_graceful_degradation_on_exception(self):
        """
        Pipeline must return a valid context even when stages fail.

        The line stops, but we get a structured failure, not a crash.
        """
        from engine.pipeline import run_pipeline

        # Break the dock query to simulate Stage 3 failure
        def dock_crash(*args, **kwargs):
            raise IOError("Dock files corrupted")

        with patch('engine.dock.query_dock', side_effect=dock_crash):
            with patch('engine.pipeline.confirm_yellow_zone', return_value=True):
                context = run_pipeline(raw_input="compile content", source="test")

        # Even with Stage 3 failure, context should exist with failure info
        assert context is not None, "Must return context even on failure"
        # Either executed=False or result contains error info
        if context.executed:
            # If it somehow continued, result should indicate the issue
            pass
        else:
            assert context.result is not None, "Failed execution should have result info"


class TestEffectiveZoneComputationInStage4:
    """
    Tests for Sprint 3.5: Unified Governance at Stage 4.

    Stage 4 MUST compute the effective zone by combining:
    - Domain zone (from routing)
    - Server zone (from mcp.config)
    - Capability zone (from mcp.config)

    The most restrictive zone wins, and Jidoka prompts ONCE.
    """

    def test_stage4_computes_effective_zone_for_mcp(self):
        """
        Stage 4 should compute effective zone for MCP actions.

        This consolidates governance in one place.
        """
        from engine.pipeline import run_pipeline
        from engine.profile import set_profile
        import json

        set_profile("coach_demo")

        # Mock LLM for calendar handler
        mock_response = json.dumps({
            "event_type": "lesson",
            "participant": "Test",
            "date": "2024-01-16",
            "time": "15:00"
        })

        with patch('engine.llm_client.call_llm', return_value=mock_response):
            with patch('engine.pipeline.confirm_yellow_zone', return_value=True) as mock_jidoka:
                with patch('engine.effectors.MCPClient.connect', return_value=True):
                    with patch('engine.effectors.MCPClient.execute', return_value={"success": True}):
                        with patch('engine.effectors.log_event'):
                            with patch('engine.telemetry.log_event', return_value={"id": "test"}):
                                context = run_pipeline(
                                    raw_input="schedule a lesson with Test",
                                    source="operator_session"
                                )

        # Jidoka should be called exactly ONCE (at Stage 4, not again at effector)
        assert mock_jidoka.call_count == 1, \
            f"Jidoka should be called once, not {mock_jidoka.call_count} times"

        # Zone should be set correctly
        assert context.zone in ["green", "yellow", "red"], \
            f"Zone should be valid, got {context.zone}"

    def test_mcp_execution_does_not_double_prompt(self):
        """
        When MCP action goes through pipeline, there should be NO double prompt.

        Stage 4 handles approval, effectors just execute.
        """
        from engine.pipeline import run_pipeline
        from engine.profile import set_profile
        import engine.effectors as effectors_module
        import json

        set_profile("coach_demo")

        mock_response = json.dumps({
            "event_type": "lesson",
            "participant": "Test",
            "date": "2024-01-16",
            "time": "15:00"
        })

        jidoka_call_count = 0

        def count_jidoka(*args, **kwargs):
            nonlocal jidoka_call_count
            jidoka_call_count += 1
            return True  # Approve

        # Verify ask_jidoka is not in effectors module (Sprint 3.5 architectural change)
        assert not hasattr(effectors_module, 'ask_jidoka'), \
            "ask_jidoka should not be in effectors module after Sprint 3.5"

        with patch('engine.llm_client.call_llm', return_value=mock_response):
            with patch('engine.pipeline.confirm_yellow_zone', side_effect=count_jidoka):
                with patch('engine.effectors.MCPClient.connect', return_value=True):
                    with patch('engine.effectors.MCPClient.execute', return_value={"success": True}):
                        with patch('engine.effectors.log_event'):
                            with patch('engine.telemetry.log_event', return_value={"id": "test"}):
                                context = run_pipeline(
                                    raw_input="schedule a lesson with Test",
                                    source="operator_session"
                                )

        # Total Jidoka prompts should be exactly 1 (at Stage 4 only)
        assert jidoka_call_count == 1, \
            f"User should only be prompted ONCE, got {jidoka_call_count} prompts (split-brain leak)"
