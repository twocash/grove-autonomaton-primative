"""
test_cognitive_router.py - Tests for Tier 0 Intent Classification

These tests enforce Architectural Invariant #2 (Config Over Code):
The Cognitive Router must load domain logic from routing.config,
not hardcode intent matching in Python.

TDD: Write tests first, then implement to pass.
"""

import pytest
from pathlib import Path


class TestRouterConfigLoading:
    """Tests for routing.config loading and parsing."""

    def test_router_loads_config(self):
        """
        The router must successfully parse profiles/coach_demo/config/routing.config.

        Invariant #2: Config Over Code - domain logic belongs in YAML/config files.
        """
        from engine.cognitive_router import get_router

        router = get_router()

        # Router should have loaded routes from config
        assert router._loaded is True, "Router should mark itself as loaded"
        assert len(router.routes) > 0, "Router should have loaded routes from config"

        # Verify expected routes exist (from routing.config)
        expected_routes = [
            "content_compilation",
            "pit_crew_build",
        ]
        for route_name in expected_routes:
            assert route_name in router.routes, f"Route '{route_name}' should exist in config"

    def test_router_config_has_required_fields(self):
        """
        Each route in routing.config must have tier, zone, and domain fields.

        These fields are required for pipeline governance.
        """
        from engine.cognitive_router import get_router

        router = get_router()

        for route_name, route_config in router.routes.items():
            assert "tier" in route_config, f"Route '{route_name}' missing 'tier'"
            assert "zone" in route_config, f"Route '{route_name}' missing 'zone'"
            assert "domain" in route_config, f"Route '{route_name}' missing 'domain'"


class TestRouterClassification:
    """Tests for intent classification from user input."""

    def test_router_classifies_compile_content(self):
        """
        Input "compile content" must return content_compilation intent.

        This is a Yellow Zone operation that writes to output/.
        """
        from engine.cognitive_router import classify_intent

        result = classify_intent("compile content")

        assert result.intent == "content_compilation", \
            f"Expected 'content_compilation', got '{result.intent}'"
        assert result.zone == "yellow", \
            f"Content compilation should be yellow zone, got '{result.zone}'"
        assert result.confidence > 0.8, \
            f"Exact match should have high confidence, got {result.confidence}"

    def test_router_classifies_dock_status(self):
        """
        Input "dock" must return dock_status intent.

        This is a Green Zone read-only status query.
        """
        from engine.cognitive_router import classify_intent

        result = classify_intent("dock")

        assert result.intent == "dock_status", \
            f"Expected 'dock_status', got '{result.intent}'"
        assert result.zone == "green", \
            f"Dock status should be green zone, got '{result.zone}'"

    def test_router_classifies_skills_list(self):
        """
        Input "skills" must return skills_list intent.
        """
        from engine.cognitive_router import classify_intent

        result = classify_intent("skills")

        assert result.intent == "skills_list", \
            f"Expected 'skills_list', got '{result.intent}'"
        assert result.zone == "green", \
            f"Skills list should be green zone, got '{result.zone}'"

    def test_router_classifies_queue_status(self):
        """
        Input "queue" must return queue_status intent.
        """
        from engine.cognitive_router import classify_intent

        result = classify_intent("queue")

        assert result.intent == "queue_status", \
            f"Expected 'queue_status', got '{result.intent}'"
        assert result.zone == "green", \
            f"Queue status should be green zone, got '{result.zone}'"

    def test_router_classifies_build_skill(self):
        """
        Input "build skill weekly-report" must return pit_crew_build intent.

        This is a Red Zone operation that modifies system capabilities.
        """
        from engine.cognitive_router import classify_intent

        result = classify_intent("build skill weekly-report")

        assert result.intent == "pit_crew_build", \
            f"Expected 'pit_crew_build', got '{result.intent}'"
        assert result.zone == "red", \
            f"Pit crew build should be red zone, got '{result.zone}'"

        # Should extract skill name from input
        assert result.extracted_args.get("skill_name") == "weekly-report", \
            f"Should extract skill name, got '{result.extracted_args}'"


class TestRouterUnknownIntents:
    """Tests for handling unrecognized input - CRITICAL for Digital Jidoka."""

    def test_router_unknown_defaults_yellow(self):
        """
        Unrecognized input strings MUST return unknown intent and yellow zone.

        Invariant #3 (Zone Governance): Unknown input defaults to cautious.
        Invariant #4 (Digital Jidoka): Ambiguity must halt for human approval.

        This is CRITICAL - green zone for unknown would bypass Jidoka.
        """
        from engine.cognitive_router import classify_intent

        result = classify_intent("xyzzy plugh random gibberish that matches nothing")

        assert result.intent == "unknown", \
            f"Unrecognized input should return 'unknown' intent, got '{result.intent}'"
        assert result.zone == "yellow", \
            f"CRITICAL: Unknown input MUST default to yellow zone, got '{result.zone}'"
        assert result.confidence == 0.0, \
            f"Unknown input should have zero confidence, got {result.confidence}"

    def test_router_empty_input_defaults_yellow(self):
        """
        Empty or whitespace input must also default to yellow zone.
        """
        from engine.cognitive_router import classify_intent

        result = classify_intent("   ")

        assert result.intent == "unknown", \
            "Empty input should return 'unknown' intent"
        assert result.zone == "yellow", \
            "Empty input MUST default to yellow zone"

    def test_router_partial_match_still_unknown(self):
        """
        Partial matches that don't meet confidence threshold should be unknown.
        """
        from engine.cognitive_router import classify_intent

        # "compile" alone without "content" might partially match
        # but shouldn't confidently classify
        result = classify_intent("comp")

        # Either it matches with low confidence or returns unknown
        # The key invariant: zone must be yellow for safety
        assert result.zone == "yellow", \
            f"Low confidence match MUST be yellow zone, got '{result.zone}'"


class TestRouterHandlerMapping:
    """Tests for handler and handler_args extraction."""

    def test_router_returns_handler_for_known_intents(self):
        """
        Known intents must include handler mapping for dispatcher.
        """
        from engine.cognitive_router import classify_intent

        result = classify_intent("dock")

        assert result.handler is not None, \
            "Known intent should have handler mapping"
        assert result.handler == "status_display", \
            f"Expected 'status_display' handler, got '{result.handler}'"

    def test_router_returns_handler_args(self):
        """
        Handler args must be passed through from config.
        """
        from engine.cognitive_router import classify_intent

        result = classify_intent("dock")

        assert result.handler_args is not None, \
            "Handler args should not be None"
        assert result.handler_args.get("display_type") == "dock", \
            f"Expected display_type='dock', got '{result.handler_args}'"


class TestSessionZeroIntake:
    """Tests for Session Zero intake skill routing (Sprint 1.5)."""

    def test_router_classifies_session_zero(self):
        """
        Input "session zero" must return session_zero intent.

        Session Zero is the Cortex's first act of learning - a guided
        Socratic intake to seed entities, business context, and voice.
        """
        from engine.cognitive_router import classify_intent

        result = classify_intent("session zero")

        assert result.intent == "session_zero", \
            f"Expected 'session_zero', got '{result.intent}'"
        assert result.zone == "yellow", \
            f"Session zero should be yellow zone (writes entities), got '{result.zone}'"
        assert result.confidence >= 0.85, \
            f"Exact match should have high confidence, got {result.confidence}"

    def test_router_classifies_run_session_zero(self):
        """
        Input "run session zero" must also return session_zero intent.
        """
        from engine.cognitive_router import classify_intent

        result = classify_intent("run session zero")

        assert result.intent == "session_zero", \
            f"Expected 'session_zero', got '{result.intent}'"
        assert result.zone == "yellow", \
            f"Session zero should be yellow zone, got '{result.zone}'"

    def test_session_zero_maps_to_handler(self):
        """
        Session zero must map to session_zero_handler for dispatcher.
        """
        from engine.cognitive_router import classify_intent

        result = classify_intent("session zero")

        assert result.handler == "session_zero_handler", \
            f"Expected 'session_zero_handler', got '{result.handler}'"

    def test_session_zero_has_skill_path(self):
        """
        Session zero handler args should include skill_path for locating prompt.
        """
        from engine.cognitive_router import classify_intent

        result = classify_intent("session zero")

        assert result.handler_args is not None, \
            "Handler args should not be None"
        assert "skill_name" in result.handler_args, \
            f"Handler args should include skill_name, got '{result.handler_args}'"


class TestRouterReset:
    """Tests for router reset functionality (profile switching)."""

    def test_router_reset_clears_cache(self):
        """
        reset_router() must clear the cached instance.

        This is needed when switching profiles.
        """
        from engine.cognitive_router import get_router, reset_router

        # Get initial router
        router1 = get_router()
        assert router1._loaded is True

        # Reset
        reset_router()

        # Get new router - should be fresh instance
        router2 = get_router()

        # They should be different instances
        assert router1 is not router2, \
            "reset_router should create new instance"


class TestTier1LLMEscalation:
    """Tests for Tier 1 LLM escalation when keyword confidence is low (Sprint 2)."""

    def test_low_confidence_escalates_to_llm(self):
        """
        When Tier 0 keyword confidence < 0.7, escalate to Tier 1 LLM.

        This tests the hybrid classification approach:
        - Tier 0: Fast keyword matching
        - Tier 1: LLM classification for ambiguous input
        """
        from unittest.mock import patch
        from engine.cognitive_router import classify_intent

        # Input that partially matches but with low confidence
        ambiguous_input = "I need to handle some content stuff"

        # Mock the LLM client to return a classification
        mock_llm_response = "content_compilation"

        with patch('engine.llm_client.call_llm', return_value=mock_llm_response) as mock_llm:
            result = classify_intent(ambiguous_input)

            # If confidence was low, LLM should have been called
            if result.confidence < 0.7:
                mock_llm.assert_called_once()
                # LLM result should be used
                assert result.intent in ["content_compilation", "unknown"], \
                    f"LLM should classify intent, got '{result.intent}'"

    def test_high_confidence_skips_llm(self):
        """
        When Tier 0 keyword confidence >= 0.7, skip LLM call.

        High-confidence keyword matches should not waste LLM tokens.
        """
        from unittest.mock import patch
        from engine.cognitive_router import classify_intent

        # Exact match should have high confidence
        exact_input = "dock"

        with patch('engine.llm_client.call_llm') as mock_llm:
            result = classify_intent(exact_input)

            # Exact match should not call LLM
            assert result.confidence >= 0.85, \
                f"Exact match should have high confidence, got {result.confidence}"
            mock_llm.assert_not_called()

    def test_llm_escalation_respects_declared_intents(self):
        """
        LLM classification must only return intents declared in routing.config.

        The LLM is given the list of valid intents and must choose from them.
        """
        from unittest.mock import patch
        from engine.cognitive_router import classify_intent, get_router

        router = get_router()
        valid_intents = list(router.routes.keys())

        # Mock LLM to return a valid intent
        with patch('engine.llm_client.call_llm', return_value="dock_status"):
            result = classify_intent("show me the knowledge base status")

            # If LLM was used, result should be a valid intent or unknown
            assert result.intent in valid_intents or result.intent == "unknown", \
                f"LLM must return declared intent, got '{result.intent}'"

    def test_llm_failure_falls_back_to_unknown(self):
        """
        If LLM call fails, fall back to unknown intent with yellow zone.

        Never let LLM errors bypass the pipeline.
        """
        from unittest.mock import patch
        from engine.cognitive_router import classify_intent

        with patch('engine.llm_client.call_llm', side_effect=Exception("API Error")):
            # Ambiguous input that would normally trigger LLM
            result = classify_intent("do something vague and unclear")

            # Should fall back to unknown/yellow, not crash
            assert result.zone == "yellow", \
                f"LLM failure should default to yellow zone, got '{result.zone}'"
