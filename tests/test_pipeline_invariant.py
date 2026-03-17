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

    def test_unknown_command_traverses_all_stages(self):
        """
        Even unknown commands must traverse all 5 stages.

        Unknown input doesn't bypass the pipeline - it goes through
        with unknown intent and yellow zone.
        """
        from engine.pipeline import run_pipeline

        # Mock approval for yellow zone
        with patch('engine.pipeline.confirm_yellow_zone', return_value=True):
            context = run_pipeline(
                raw_input="xyzzy random unknown command",
                source="test"
            )

        # All stages must still execute
        assert context.telemetry_event is not None, \
            "Unknown command: Stage 1 (Telemetry) not executed"
        assert context.intent == "unknown", \
            f"Unknown command should have 'unknown' intent, got '{context.intent}'"
        assert context.dock_context is not None, \
            "Unknown command: Stage 3 (Compilation) not executed"
        assert context.result is not None, \
            "Unknown command: Stage 5 (Execution) not executed"


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

        # Mock approval (red zone uses same confirm for now)
        with patch('engine.pipeline.confirm_yellow_zone', return_value=True):
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
        """
        from engine.pipeline import run_pipeline

        # Even if caller passes green, unknown should be yellow
        with patch('engine.pipeline.confirm_yellow_zone', return_value=True):
            context = run_pipeline(
                raw_input="xyzzy unknown gibberish",
                source="test",
                zone="green"  # Should be overridden to yellow
            )

        assert context.zone == "yellow", \
            f"Unknown intent MUST be yellow zone, got '{context.zone}'"


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
