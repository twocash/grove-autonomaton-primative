"""
test_dispatcher.py - Tests for Dispatcher functionality

Sprint 7.5: The Chief of Staff UX & Conversational Jidoka

Tests for general_chat intent and conversational fallback.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestGeneralChatIntent:
    """Tests for general_chat conversational fallback."""

    def test_general_chat_routes_to_green_zone(self):
        """Assert general_chat is Green Zone (no approval needed)."""
        from engine.cognitive_router import classify_intent, reset_router
        from engine.profile import set_profile

        set_profile("coach_demo")
        reset_router()

        result = classify_intent("hello")

        assert result.intent == "general_chat"
        assert result.zone == "green"
        assert result.handler == "general_chat"

    def test_general_chat_triggers_on_hi(self):
        """Assert 'hi' routes to general_chat."""
        from engine.cognitive_router import classify_intent, reset_router
        from engine.profile import set_profile

        set_profile("coach_demo")
        reset_router()

        result = classify_intent("hi there")

        assert result.intent == "general_chat"
        assert result.zone == "green"

    def test_general_chat_triggers_on_hey(self):
        """Assert 'hey' routes to general_chat."""
        from engine.cognitive_router import classify_intent, reset_router
        from engine.profile import set_profile

        set_profile("coach_demo")
        reset_router()

        result = classify_intent("hey!")

        assert result.intent == "general_chat"
        assert result.zone == "green"

    def test_general_chat_triggers_on_who_are_you(self):
        """Assert 'who are you' routes to general_chat."""
        from engine.cognitive_router import classify_intent, reset_router
        from engine.profile import set_profile

        set_profile("coach_demo")
        reset_router()

        result = classify_intent("who are you")

        assert result.intent == "general_chat"
        assert result.zone == "green"

    def test_general_chat_returns_friendly_response(self):
        """Assert general_chat returns friendly text without Yellow Zone halt."""
        from engine.dispatcher import get_dispatcher, DispatchResult
        from engine.cognitive_router import RoutingResult
        from engine.profile import set_profile
        import engine.dispatcher as dispatcher_module

        set_profile("coach_demo")

        # Reset dispatcher
        dispatcher_module._dispatcher_instance = None

        mock_llm_response = "Hello! I'm your Chief of Staff, ready to help with the @ChristInTheFairway mission."

        with patch("engine.llm_client.call_llm", return_value=mock_llm_response):
            dispatcher = get_dispatcher()

            routing = RoutingResult(
                intent="general_chat",
                domain="system",
                zone="green",
                tier=1,
                confidence=1.0,
                handler="general_chat",
                handler_args={},
                extracted_args={}
            )

            result = dispatcher.dispatch(routing, "hello")

        assert result.success is True
        assert "Chief of Staff" in result.message or "Hello" in result.message or len(result.message) > 0

    def test_dispatcher_has_general_chat_handler(self):
        """Verify dispatcher has general_chat handler registered."""
        from engine.dispatcher import get_dispatcher

        dispatcher = get_dispatcher()
        assert "general_chat" in dispatcher._handlers


class TestGeneralChatNoYellowZone:
    """Tests ensuring general_chat doesn't trigger Yellow Zone."""

    def test_hello_does_not_trigger_jidoka(self):
        """Assert 'hello' processes without Jidoka halt."""
        from engine.pipeline import run_pipeline
        from engine.profile import set_profile

        set_profile("coach_demo")

        mock_llm_response = "Hello! Ready to serve the mission."

        with patch("engine.llm_client.call_llm", return_value=mock_llm_response):
            context = run_pipeline(raw_input="hello", source="test")

        # Should be executed (not cancelled by Jidoka)
        assert context.executed is True
        assert context.zone == "green"

    def test_greeting_returns_text_response(self):
        """Assert greeting returns actual text content."""
        from engine.pipeline import run_pipeline
        from engine.profile import set_profile

        set_profile("coach_demo")

        mock_llm_response = "Good morning! The @ChristInTheFairway channels await."

        with patch("engine.llm_client.call_llm", return_value=mock_llm_response):
            context = run_pipeline(raw_input="hey", source="test")

        # Result should contain the LLM response
        assert context.result is not None
        data = context.result.get("data", {})
        assert data.get("type") == "general_chat"
        assert "response" in data or "message" in context.result
