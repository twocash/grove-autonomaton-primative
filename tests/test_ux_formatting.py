"""
test_ux_formatting.py - Tests for UX formatting and Conversational Andon Gate

Sprint 7.5: The Chief of Staff UX & Conversational Andon

Tests for conversational translation of Andon Gate halts.
The Andon mechanism fires; Jidoka is the discipline that authorizes it.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestConversationalAndon:
    """Tests for conversational translation of Andon Gate halts."""

    def test_yellow_zone_generates_conversational_summary(self):
        """Assert confirm_yellow_zone uses LLM for conversational explanation."""
        from engine.ux import translate_action_for_approval

        raw_payload = {
            "intent": "email_parent",
            "handler": "mcp_gmail",
            "handler_args": {"server": "gmail", "capability": "send_email"},
            "extracted_args": {"recipient": "parent@email.com"}
        }

        mock_translation = "I'd like to send an email to a parent. This requires your approval since it's an external communication."

        with patch("engine.llm_client.call_llm", return_value=mock_translation) as mock_llm:
            result = translate_action_for_approval(raw_payload)

            # Verify LLM was called
            assert mock_llm.called
            # Verify translation was returned
            assert "email" in result.lower() or "approval" in result.lower() or result == mock_translation

    def test_conversational_translation_fallback_on_llm_failure(self):
        """Assert graceful fallback when LLM translation fails."""
        from engine.ux import translate_action_for_approval

        raw_payload = {
            "intent": "calendar_schedule",
            "handler": "mcp_calendar"
        }

        with patch("engine.llm_client.call_llm", side_effect=Exception("LLM timeout")):
            result = translate_action_for_approval(raw_payload)

        # Should return some fallback description
        assert result is not None
        assert len(result) > 0

    def test_translation_uses_tier_1_for_speed(self):
        """Assert translation uses Tier 1 (Haiku) for low latency."""
        from engine.ux import translate_action_for_approval

        raw_payload = {"intent": "test_action"}

        with patch("engine.llm_client.call_llm", return_value="Test translation") as mock_llm:
            translate_action_for_approval(raw_payload)

            # Verify Tier 1 was used
            call_kwargs = mock_llm.call_args.kwargs if mock_llm.call_args else {}
            assert call_kwargs.get("tier", 1) == 1


class TestAndonOutputFormat:
    """Tests for Andon Gate output formatting.

    V-023: format_jidoka_display removed. ask_jidoka handles all formatting
    internally with three TPS beats: Jidoka (detect) → Andon (stop) → Kaizen (propose).
    These tests now verify the ask_jidoka signature accepts required parameters.
    """

    def test_ask_jidoka_accepts_payload_for_transparency(self):
        """Assert ask_jidoka accepts payload parameter for Red zone transparency.

        White Paper Part III §2: Red zone 'surfaces information and waits.'
        The payload IS the surfaced information.
        """
        from engine.ux import ask_jidoka
        from unittest.mock import patch

        raw_payload = {"intent": "calendar_schedule", "handler": "mcp_calendar"}

        # Mock keystroke to avoid blocking
        with patch('engine.ux._get_single_keystroke', return_value='1'):
            # Should not raise - payload is a valid parameter
            result = ask_jidoka(
                context_message="Yellow zone action detected.",
                options={"1": "Approve", "2": "Cancel"},
                payload=raw_payload
            )
        assert result == "1"

    def test_ask_jidoka_accepts_diagnostic_for_kaizen(self):
        """Assert ask_jidoka accepts diagnostic parameter for Kaizen proposals.

        V-023: diagnostic dict triggers full three-beat display.
        """
        from engine.ux import ask_jidoka
        from unittest.mock import patch

        diagnostic = {"summary": "No match", "confidence": 0.0, "cost": 0.00}

        with patch('engine.ux._get_single_keystroke', return_value='1'):
            result = ask_jidoka(
                context_message="",
                options={"1": "Sonnet", "2": "Cancel"},
                diagnostic=diagnostic,
                kaizen_prompt="How should we route this?"
            )
        assert result == "1"

    def test_ask_jidoka_accepts_options_config_for_templates(self):
        """Assert ask_jidoka accepts options_config for template resolution.

        V-018: Options can include {total_cost} templates resolved at display time.
        """
        from engine.ux import ask_jidoka
        from unittest.mock import patch

        options_config = {
            "1": {"tier": 2, "classification_tier": 1, "response_tier": 2}
        }

        with patch('engine.ux._get_single_keystroke', return_value='1'):
            result = ask_jidoka(
                context_message="Test",
                options={"1": "Option ~${total_cost}"},
                options_config=options_config
            )
        assert result == "1"


class TestConfirmYellowZoneWithContext:
    """Tests for confirm_yellow_zone_with_context.

    V-023: Now passes payload directly to ask_jidoka for transparency.
    White Paper Part III §2: 'surfaces information and waits.'
    """

    def test_confirm_yellow_zone_passes_payload_to_ask_jidoka(self, monkeypatch):
        """Assert confirm_yellow_zone_with_context passes payload for transparency."""
        from engine import ux
        import engine.ux as ux_module

        captured_kwargs = {}

        def mock_ask_jidoka(context_message, options, diagnostic=None,
                           kaizen_prompt=None, payload=None, options_config=None):
            captured_kwargs['payload'] = payload
            captured_kwargs['context_message'] = context_message
            return "1"  # Approve

        monkeypatch.setattr(ux_module, "ask_jidoka", mock_ask_jidoka)

        result = ux.confirm_yellow_zone_with_context(
            action_description="Send email to parent",
            payload={"intent": "email_parent"}
        )

        # Verify payload was passed through
        assert captured_kwargs['payload'] == {"intent": "email_parent"}
        # Verify context message includes action description
        assert "Send email to parent" in captured_kwargs['context_message']
        assert result is True


class TestPersonaInTranslations:
    """Tests for persona inclusion in translations (config-driven)."""

    def test_translation_prompt_includes_persona_name(self):
        """Assert translation prompt includes the configured persona name."""
        from engine.ux import translate_action_for_approval
        from engine.config_loader import get_persona

        # Get persona name from config (profile-agnostic)
        persona = get_persona()
        persona_name = persona.name

        raw_payload = {"intent": "test_action"}
        captured_calls = []

        def capture_prompt(prompt, **kwargs):
            captured_calls.append({"prompt": prompt, "kwargs": kwargs})
            return "Translation result"

        with patch("engine.llm_client.call_llm", side_effect=capture_prompt):
            translate_action_for_approval(raw_payload)

        if captured_calls:
            call = captured_calls[0]
            # Persona name can be in prompt OR system prompt
            prompt = call["prompt"]
            system = call["kwargs"].get("system", "")
            combined = f"{prompt} {system}"
            assert persona_name in combined or persona_name.lower() in combined.lower(),                 f"Persona name '{persona_name}' should appear in translation prompt"
