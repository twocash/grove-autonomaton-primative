"""
test_jidoka_consent.py - V-009 Digital Jidoka Tests

Tests 2 and 6: Digital Jidoka consent flow.

White paper Part II ("Where Jidoka Meets Kaizen"): "When a machine detects
a quality problem, it stops the production line automatically and signals
for human intervention."

White paper Part III ("Sovereignty Guardrails"): "The system's self-improvement
never exceeds the boundaries the human sets."

V-009: Assert on telemetry traces, not terminal output.
"""

import pytest
from unittest.mock import patch
from tests.conftest import PIPELINE_STAGES


class TestDigitalJidoka:
    """
    Test 2: Digital Jidoka — Unknown Input Stops the Line

    Jidoka means the system stops when uncertain. Unknown input triggers
    the consent mechanism (Kaizen prompt), not silent fallback.
    """

    def test_unknown_input_stops_the_line(self, telemetry_sink, mock_ux_input):
        """
        Option 2 (local context): system answers from dock without LLM spend.

        White paper Part III ("Digital Jidoka"): "No confident output from
        an uncertain pipeline."
        """
        from engine.pipeline import run_pipeline

        mock_ux_input.append("2")  # Option 2: answer from local context

        context = run_pipeline(
            raw_input="How does this handle regulatory compliance?",
            source="test"
        )

        # Recognition shows unknown
        recognition = next(
            e for e in telemetry_sink
            if e.get("inferred", {}).get("stage") == "recognition"
        )
        assert recognition["intent"] == "unknown", \
            f"Expected intent 'unknown', got '{recognition.get('intent')}'"

        # Approval shows Kaizen fired
        approval = next(
            e for e in telemetry_sink
            if e.get("inferred", {}).get("stage") == "approval"
        )
        label = approval.get("inferred", {}).get("label", "")
        assert "kaizen" in label.lower(), \
            f"Expected 'kaizen' in approval label, got '{label}'"

        # Pipeline approved (Option 2 is valid)
        assert context.approved is True

    def test_unknown_input_routes_to_general_chat(self, telemetry_sink, mock_ux_input):
        """
        Option 2 (local context) routes to general_chat handler.
        No LLM classification spend.
        """
        from engine.pipeline import run_pipeline

        mock_ux_input.append("2")

        context = run_pipeline(
            raw_input="What is your architecture?",
            source="test"
        )

        assert context.intent == "general_chat", \
            f"Option 2 should set intent to 'general_chat', got '{context.intent}'"
        assert context.zone == "green", \
            f"Option 2 should set zone to 'green', got '{context.zone}'"


class TestConfigDrivenRouting:
    """
    Test 6: Config-Driven Routing — Option 3 Sub-Menu

    White paper Part III ("Declarative Behavior Governance"): "All behavior
    lives in declarative configuration, not imperative code. The test: can
    a non-technical domain expert alter the system's behavior by editing a
    config file, without a deploy?"

    The sub-menu options come from clarification.yaml, not hardcoded strings.
    """

    def test_option3_shows_config_menu(self, telemetry_sink, mock_ux_input):
        """
        Option 3 → config sub-menu → selection resolves to known intent.

        Proves the consent architecture is declarative: clarification.yaml
        defines the fallback options, routing.config defines the handlers.
        """
        from engine.pipeline import run_pipeline

        mock_ux_input.append("3")  # Show what you can help with
        mock_ux_input.append("1")  # First sub-menu option

        context = run_pipeline(
            raw_input="xyzzy plugh nothing",
            source="test"
        )

        # Recognition shows unknown
        recognition = next(
            e for e in telemetry_sink
            if e.get("inferred", {}).get("stage") == "recognition"
        )
        assert recognition["intent"] == "unknown"

        # After sub-menu, intent resolves (not unknown)
        assert context.intent != "unknown", \
            f"Sub-menu should resolve to a known intent, got '{context.intent}'"
        assert context.approved is True

        # Handler set from routing.config
        routing_info = context.entities.get("routing", {})
        assert routing_info.get("handler") is not None, \
            "Sub-menu should set a handler from routing.config"


    def test_option4_cancels_pipeline(self, telemetry_sink, mock_ux_input):
        """
        Option 4 (rephrase) cancels the pipeline gracefully.

        White paper Part III ("Sovereignty Guardrails"): the system
        "cannot unilaterally grant itself new authority." If the operator
        says rephrase, the pipeline halts.
        """
        from engine.pipeline import run_pipeline

        mock_ux_input.append("4")

        context = run_pipeline(
            raw_input="completely nonsensical gibberish here",
            source="test"
        )

        assert context.approved is False, \
            "Option 4 should not approve the pipeline"
        assert context.result.get("status") == "cancelled", \
            f"Expected status 'cancelled', got '{context.result.get('status')}'"

    def test_jidoka_fires_for_low_confidence(self, telemetry_sink, mock_ux_input):
        """
        Unknown input with zero confidence triggers Kaizen consent flow.

        White paper Part III ("Digital Jidoka"): "When any stage of the
        pipeline degrades... the system stops."
        """
        from engine.pipeline import run_pipeline

        mock_ux_input.append("2")  # Option 2 to continue

        context = run_pipeline(
            raw_input="something that definitely won't match any keywords",
            source="test"
        )

        recognition = next(
            e for e in telemetry_sink
            if e.get("inferred", {}).get("stage") == "recognition"
        )
        confidence = recognition.get("confidence", 1.0)
        assert confidence == 0.0 or recognition["intent"] == "unknown", \
            f"Low confidence input should be 'unknown'"

        assert "kaizen_fired" in context.events, \
            f"Kaizen should fire for low confidence, events: {context.events}"
