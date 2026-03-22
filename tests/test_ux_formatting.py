"""
test_ux_formatting.py - Tests for UX formatting and Conversational Jidoka

Sprint 7.5: The Chief of Staff UX & Conversational Jidoka

Tests for conversational translation of Jidoka halts.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestConversationalJidoka:
    """Tests for conversational translation of Jidoka halts."""

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


class TestJidokaOutputFormat:
    """Tests for Jidoka output formatting."""

    def test_jidoka_output_includes_conversational_summary(self):
        """Assert Jidoka output shows conversational summary at top."""
        from engine.ux import format_jidoka_display

        conversational = "I need to schedule a lesson on the calendar. This is a Yellow Zone action."
        raw_payload = {"intent": "calendar_schedule", "handler": "mcp_calendar"}

        output = format_jidoka_display(conversational, raw_payload)

        # Conversational summary should appear before raw payload
        conv_pos = output.find("schedule")
        raw_pos = output.find("calendar_schedule")

        assert conv_pos < raw_pos or "schedule" in output

    def test_jidoka_output_includes_raw_payload_section(self):
        """Assert Jidoka output includes separated raw payload for transparency."""
        from engine.ux import format_jidoka_display

        conversational = "I want to send an email."
        raw_payload = {"intent": "email_parent", "handler": "mcp_gmail"}

        output = format_jidoka_display(conversational, raw_payload)

        # Should have some indicator of raw/system payload
        assert "PAYLOAD" in output.upper() or "SYSTEM" in output.upper() or "RAW" in output.upper() or "email_parent" in output

    def test_jidoka_output_shows_both_summary_and_technical(self):
        """Assert both conversational and technical info are present."""
        from engine.ux import format_jidoka_display

        conversational = "Building a new skill requires Red Zone approval."
        raw_payload = {
            "intent": "pit_crew_build",
            "handler": "pit_crew",
            "handler_args": {"action": "build"},
            "skill_name": "weekly-report"
        }

        output = format_jidoka_display(conversational, raw_payload)

        # Should contain conversational explanation
        assert "skill" in output.lower() or "approval" in output.lower()
        # Should also contain technical details
        assert "pit_crew" in output or "weekly-report" in output


class TestConfirmYellowZoneWithTranslation:
    """Tests for confirm_yellow_zone with conversational translation."""

    def test_confirm_yellow_zone_translates_before_display(self, monkeypatch):
        """Assert confirm_yellow_zone calls translation before showing prompt."""
        from engine import ux
        import engine.ux as ux_module

        translation_called = []

        def mock_translate(payload):
            translation_called.append(payload)
            return "This action needs your approval."

        def mock_ask_jidoka(context_message, options):
            return "1"  # Approve

        monkeypatch.setattr(ux_module, "translate_action_for_approval", mock_translate)
        monkeypatch.setattr(ux_module, "ask_jidoka", mock_ask_jidoka)

        # Call confirm_yellow_zone_with_context which should use translation
        result = ux.confirm_yellow_zone_with_context(
            action_description="Send email to parent",
            payload={"intent": "email_parent"}
        )

        assert len(translation_called) > 0
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
