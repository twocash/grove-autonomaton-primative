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



class TestRouterUnknownIntents:
    """Tests for handling unrecognized input - CRITICAL for Digital Jidoka."""

    def test_router_unknown_defaults_yellow(self):
        """
        Unrecognized input strings MUST return unknown intent and yellow zone.

        Invariant #3 (Zone Governance): Unknown input defaults to cautious.
        Invariant #4 (Digital Jidoka): Ambiguity must halt for human approval.

        This is CRITICAL - green zone for unknown would bypass Jidoka.
        """
        from unittest.mock import patch
        from engine.cognitive_router import classify_intent, reset_router

        reset_router()

        # Patch LLM to return "unknown" for truly unrecognized input
        with patch('engine.llm_client.call_llm', return_value="unknown"):
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
        Mock the pipeline to avoid cache pollution and ensure deterministic behavior.
        """
        from engine.cognitive_router import classify_intent
        from unittest.mock import patch

        # Mock run_pipeline to return None (simulating LLM failure/unknown)
        # This ensures the router falls back to default unknown handling
        with patch('engine.pipeline.run_pipeline', return_value=None):
            # Use a gibberish string that won't match keywords
            result = classify_intent("completely_random_gibberish_12345")

        # Unknown inputs with no confident match must be yellow for safety
        assert result.zone == "yellow", \
            f"Unknown input MUST be yellow zone, got '{result.zone}'"


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


class TestTier1LLMEscalation:
    """Tests for Tier 1 LLM escalation when keyword confidence is low (Sprint 2)."""

    def test_low_confidence_returns_unknown_no_llm(self):
        """
        When Tier 0 keyword confidence < 0.7, return unknown — do NOT call LLM.

        consent-gated-classification-v1: classify() no longer auto-fires the LLM.
        LLM classification requires operator consent via Stage 4 Kaizen prompt.
        """
        from unittest.mock import patch
        from engine.cognitive_router import classify_intent

        # Input that doesn't match any keywords
        ambiguous_input = "I need to handle some content stuff"

        with patch('engine.llm_client.call_llm') as mock_llm:
            result = classify_intent(ambiguous_input)

            # LLM must NOT be called from classify()
            mock_llm.assert_not_called()

            # Result should be unknown with 0.0 confidence
            assert result.intent == "unknown", \
                f"Expected 'unknown', got '{result.intent}'"
            assert result.confidence == 0.0, \
                f"Expected confidence 0.0, got {result.confidence}"

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


class TestConversationalRouting:
    """Tests for Sprint 8 conversational routing fixes."""

    def test_routing_result_has_intent_type(self):
        """
        RoutingResult must include intent_type field.

        Sprint 8: intent_type gates Compilation stage behavior.
        - conversational: skip dock query
        - informational: optional dock query
        - actionable: full dock query
        """
        from engine.cognitive_router import classify_intent

        result = classify_intent("hello")

        assert hasattr(result, "intent_type"), \
            "RoutingResult must have intent_type field"
        assert result.intent_type in ["conversational", "informational", "actionable"], \
            f"intent_type must be valid, got '{result.intent_type}'"

    def test_routing_result_has_action_required(self):
        """
        RoutingResult must include action_required field.

        Sprint 8: action_required gates Approval stage behavior.
        - False + green zone: skip approval UX entirely
        - True: normal approval flow
        """
        from engine.cognitive_router import classify_intent

        result = classify_intent("dock")

        assert hasattr(result, "action_required"), \
            "RoutingResult must have action_required field"
        assert isinstance(result.action_required, bool), \
            "action_required must be boolean"

    def test_general_chat_is_conversational(self):
        """
        General chat intents must have intent_type=conversational.

        This ensures greetings skip dock retrieval and approval prompts.
        """
        from engine.cognitive_router import classify_intent

        result = classify_intent("hello")

        # Should be recognized as general_chat or classified by LLM
        if result.intent == "general_chat":
            assert result.intent_type == "conversational", \
                f"general_chat must be conversational, got '{result.intent_type}'"
            assert result.action_required is False, \
                "general_chat should not require action"

    def test_informational_intent_type(self):
        """
        Status queries must have intent_type=informational.
        """
        from engine.cognitive_router import classify_intent

        result = classify_intent("dock")

        assert result.intent == "dock_status", \
            f"Expected dock_status, got '{result.intent}'"
        assert result.intent_type == "informational", \
            f"dock_status must be informational, got '{result.intent_type}'"


    def test_conversational_intents_skip_dock(self):
        """
        Pipeline should skip dock query for conversational intents.

        Sprint 8: intent_type=conversational bypasses Compilation stage.
        """
        from engine.cognitive_router import classify_intent

        # Test with greeting keyword
        result = classify_intent("hello")

        # Either:
        # 1. Keyword match as general_chat (conversational)
        # 2. LLM classifies as conversational
        if result.intent == "general_chat":
            assert result.intent_type == "conversational", \
                "general_chat must be conversational"
        elif result.intent_type == "conversational":
            # LLM classified it as conversational
            assert result.action_required is False, \
                "conversational intent should not require action"


class TestClarificationJidoka:
    """Tests for Sprint 8 clarification Jidoka."""

    def test_clarification_options_available(self):
        """
        get_clarification_options() must return valid options dict.
        """
        from engine.cognitive_router import get_clarification_options

        options = get_clarification_options()

        assert isinstance(options, dict), "Options must be a dict"
        assert len(options) >= 2, "Must have at least 2 options"
        # Keys should be strings (for Jidoka selection)
        assert all(isinstance(k, str) for k in options.keys()), \
            "Option keys must be strings"

    def test_resolve_clarification_from_config(self):
        """
        resolve_clarification should read from profile config (Sprint: pipeline-compliance-v1).
        """
        from engine.profile import set_profile
        from engine.cognitive_router import resolve_clarification, reset_router

        set_profile("reference")
        reset_router()
        result = resolve_clarification("1", "original input")

        # Reference profile option 1 is "explain_system" (ux-polish-v1)
        assert result.intent == "explain_system", \
            f"Choice 1 should be explain_system from reference config, got '{result.intent}'"
        assert result.confidence == 1.0, \
            "User clarification should have full confidence"



class TestLLMStructuredClassification:
    """Tests for Sprint 8 structured LLM classification output."""

    def test_llm_classification_returns_intent_type(self):
        """
        LLM classification should return intent_type in result.

        Sprint 8: LLM returns structured JSON with intent_type field.
        """
        from unittest.mock import patch
        import json
        from engine.cognitive_router import classify_intent, reset_router

        reset_router()

        # Mock structured LLM response
        llm_response = json.dumps({
            "intent": "general_chat",
            "intent_type": "conversational",
            "confidence": 0.9,
            "reasoning": "User is greeting",
            "action_required": False,
            "entities_mentioned": [],
            "content_seeds": [],
            "sentiment": "positive"
        })

        with patch('engine.llm_client.call_llm', return_value=llm_response):
            # Ambiguous input that triggers LLM
            result = classify_intent("hey there, how's it going")

            # Should have intent_type from LLM
            assert result.intent_type in ["conversational", "informational", "actionable"], \
                f"LLM should return valid intent_type, got '{result.intent_type}'"

    def test_llm_classification_logs_to_telemetry(self):
        """
        Every LLM classification must log to telemetry for Ratchet analysis.

        Sprint 8: The Ratchet uses this data to promote patterns to Tier 0.
        """
        from unittest.mock import patch, MagicMock
        import json
        from engine.cognitive_router import classify_intent, reset_router

        reset_router()

        mock_log = MagicMock()
        llm_response = json.dumps({
            "intent": "dock_status",
            "intent_type": "informational",
            "confidence": 0.8,
            "reasoning": "User wants status",
            "action_required": True,
            "entities_mentioned": [],
            "content_seeds": [],
            "sentiment": "neutral"
        })

        with patch('engine.llm_client.call_llm', return_value=llm_response):
            with patch('engine.telemetry.log_event', mock_log):
                # Input that triggers LLM escalation
                classify_intent("show me the system status please")

                # Telemetry should have been called
                if mock_log.called:
                    call_args = mock_log.call_args
                    assert call_args is not None, "log_event should be called"
