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
