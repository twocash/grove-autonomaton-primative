"""
test_llm_client.py - Tests for LLM Client with Telemetry

These tests enforce the critical Ratchet invariant:
Every LLM call MUST log telemetry with model, tokens, cost, and intent.

TDD: Write tests first, then implement to pass.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from dataclasses import dataclass


class TestLLMClientTelemetry:
    """Tests ensuring every LLM call logs telemetry."""

    def test_llm_call_logs_telemetry(self):
        """
        Every LLM call must append a telemetry event with:
        - model: The model used (e.g., claude-3-haiku-20240307)
        - tokens_in: Input token count
        - tokens_out: Output token count
        - cost: Estimated cost in USD
        - intent: The intent being served

        This is CRITICAL for Ratchet analysis.
        """
        from engine.llm_client import call_llm

        telemetry_events = []

        def capture_telemetry(**kwargs):
            telemetry_events.append(kwargs)
            return {"id": "test-event"}

        # Mock both telemetry and Anthropic client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Test response")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch('engine.llm_client.log_llm_event', side_effect=capture_telemetry):
            with patch('engine.llm_client.get_anthropic_client') as mock_client:
                mock_client.return_value.messages.create.return_value = mock_response

                result = call_llm(
                    prompt="Test prompt",
                    tier=1,
                    intent="test_intent"
                )

        # Must have logged exactly one event
        assert len(telemetry_events) == 1, \
            f"Expected 1 telemetry event, got {len(telemetry_events)}"

        event = telemetry_events[0]

        # Required fields
        assert "model" in event, "Telemetry must include 'model'"
        assert "tokens_in" in event, "Telemetry must include 'tokens_in'"
        assert "tokens_out" in event, "Telemetry must include 'tokens_out'"
        assert "cost" in event, "Telemetry must include 'cost'"
        assert "intent" in event, "Telemetry must include 'intent'"

        # Values must be populated
        assert event["tokens_in"] == 100, f"Expected 100 tokens_in, got {event['tokens_in']}"
        assert event["tokens_out"] == 50, f"Expected 50 tokens_out, got {event['tokens_out']}"
        assert event["intent"] == "test_intent", f"Intent mismatch: {event['intent']}"

    def test_llm_call_calculates_cost(self):
        """
        Cost must be calculated based on model pricing and token counts.
        """
        from engine.llm_client import call_llm

        telemetry_events = []

        def capture_telemetry(**kwargs):
            telemetry_events.append(kwargs)
            return {"id": "test-event"}

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Response")]
        mock_response.usage = MagicMock(input_tokens=1000, output_tokens=500)

        with patch('engine.llm_client.log_llm_event', side_effect=capture_telemetry):
            with patch('engine.llm_client.get_anthropic_client') as mock_client:
                mock_client.return_value.messages.create.return_value = mock_response

                call_llm(prompt="Test", tier=1, intent="test")

        event = telemetry_events[0]
        assert event["cost"] > 0, "Cost must be calculated and > 0"
        assert isinstance(event["cost"], float), "Cost must be a float"


class TestLLMClientTierRouting:
    """Tests for tier-based model routing."""

    def test_tier_1_uses_haiku(self):
        """
        Tier 1 calls must use claude-3-haiku-20240307.

        Haiku is for fast, cheap operations like intent classification.
        """
        from engine.llm_client import call_llm

        telemetry_events = []

        def capture_telemetry(**kwargs):
            telemetry_events.append(kwargs)
            return {"id": "test-event"}

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Response")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch('engine.llm_client.log_llm_event', side_effect=capture_telemetry):
            with patch('engine.llm_client.get_anthropic_client') as mock_client:
                mock_client.return_value.messages.create.return_value = mock_response

                call_llm(prompt="Test", tier=1, intent="classification")

        event = telemetry_events[0]
        assert "haiku" in event["model"].lower(), \
            f"Tier 1 should use Haiku, got '{event['model']}'"

    def test_tier_2_uses_sonnet(self):
        """
        Tier 2 calls must use claude-3-5-sonnet-20241022.

        Sonnet is for more complex tasks like content generation.
        """
        from engine.llm_client import call_llm

        telemetry_events = []

        def capture_telemetry(**kwargs):
            telemetry_events.append(kwargs)
            return {"id": "test-event"}

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Response")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch('engine.llm_client.log_llm_event', side_effect=capture_telemetry):
            with patch('engine.llm_client.get_anthropic_client') as mock_client:
                mock_client.return_value.messages.create.return_value = mock_response

                call_llm(prompt="Test", tier=2, intent="generation")

        event = telemetry_events[0]
        assert "sonnet" in event["model"].lower(), \
            f"Tier 2 should use Sonnet, got '{event['model']}'"

    def test_default_tier_is_1(self):
        """
        If no tier specified, default to Tier 1 (cheapest).
        """
        from engine.llm_client import call_llm

        telemetry_events = []

        def capture_telemetry(**kwargs):
            telemetry_events.append(kwargs)
            return {"id": "test-event"}

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Response")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch('engine.llm_client.log_llm_event', side_effect=capture_telemetry):
            with patch('engine.llm_client.get_anthropic_client') as mock_client:
                mock_client.return_value.messages.create.return_value = mock_response

                # No tier specified
                call_llm(prompt="Test", intent="test")

        event = telemetry_events[0]
        assert "haiku" in event["model"].lower(), \
            f"Default tier should use Haiku, got '{event['model']}'"


class TestLLMClientResponse:
    """Tests for LLM response handling."""

    def test_returns_text_content(self):
        """
        call_llm must return the text content from the response.
        """
        from engine.llm_client import call_llm

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is the response")]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)

        with patch('engine.llm_client.log_llm_event'):
            with patch('engine.llm_client.get_anthropic_client') as mock_client:
                mock_client.return_value.messages.create.return_value = mock_response

                result = call_llm(prompt="Test", intent="test")

        assert result == "This is the response", \
            f"Expected response text, got '{result}'"

    def test_handles_empty_response(self):
        """
        Empty responses should return empty string, not crash.
        """
        from engine.llm_client import call_llm

        mock_response = MagicMock()
        mock_response.content = []
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=0)

        with patch('engine.llm_client.log_llm_event'):
            with patch('engine.llm_client.get_anthropic_client') as mock_client:
                mock_client.return_value.messages.create.return_value = mock_response

                result = call_llm(prompt="Test", intent="test")

        assert result == "", "Empty response should return empty string"


class TestLLMClientSystemPrompt:
    """Tests for system prompt handling."""

    def test_accepts_system_prompt(self):
        """
        call_llm should accept an optional system prompt.
        """
        from engine.llm_client import call_llm

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Response")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch('engine.llm_client.log_llm_event'):
            with patch('engine.llm_client.get_anthropic_client') as mock_client:
                mock_instance = mock_client.return_value
                mock_instance.messages.create.return_value = mock_response

                call_llm(
                    prompt="User message",
                    system="You are a helpful assistant",
                    intent="test"
                )

                # Verify system was passed to API
                call_args = mock_instance.messages.create.call_args
                assert "system" in call_args.kwargs, \
                    "System prompt should be passed to API"


class TestLLMClientErrorHandling:
    """Tests for error handling."""

    def test_logs_error_on_api_failure(self):
        """
        API failures should be logged to telemetry with error details.
        """
        from engine.llm_client import call_llm, LLMError

        telemetry_events = []

        def capture_telemetry(**kwargs):
            telemetry_events.append(kwargs)
            return {"id": "test-event"}

        with patch('engine.llm_client.log_llm_event', side_effect=capture_telemetry):
            with patch('engine.llm_client.get_anthropic_client') as mock_client:
                mock_client.return_value.messages.create.side_effect = Exception("API Error")

                with pytest.raises(LLMError):
                    call_llm(prompt="Test", intent="test")

        # Should still log the attempt with error
        assert len(telemetry_events) >= 1, "Should log even on error"
        # Last event should indicate error
        error_event = telemetry_events[-1]
        assert "error" in error_event or error_event.get("tokens_out", 0) == 0, \
            "Error should be logged"
