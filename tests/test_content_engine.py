"""
test_content_engine.py - Tests for LLM-Powered Content Compilation

These tests ensure the content engine uses the LLM client to apply
voice rules and generate platform-ready content.

TDD: Write tests first, then implement to pass.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestContentEngineVoiceApplication:
    """Tests for LLM-based voice rule application."""

    def test_content_engine_uses_llm_for_compilation(self):
        """
        Content engine must use LLM client to compile drafts.

        The engine should inject voice.yaml, pillars.yaml, the content
        seed, and dock context into the prompt.
        """
        from engine.content_engine import ContentEngine

        # Mock LLM response
        mock_draft = "Great practice session today! The team showed real improvement. #GolfCoach"

        with patch('engine.llm_client.call_llm', return_value=mock_draft) as mock_llm:
            engine = ContentEngine()

            # Create a mock seed
            seed_content = "Today's practice focused on putting drills"

            # Compile with LLM
            result = engine._compile_with_llm(
                seed_content=seed_content,
                pillar="training",
                platform="tiktok"
            )

            # LLM should have been called
            mock_llm.assert_called_once()

            # Result should be the LLM output
            assert result == mock_draft

    def test_llm_prompt_includes_voice_config(self):
        """
        The LLM prompt must include voice.yaml configuration.

        This ensures brand consistency in generated content.
        """
        from engine.content_engine import ContentEngine

        captured_prompts = []

        def capture_llm_call(prompt, **kwargs):
            captured_prompts.append(prompt)
            return "Generated content"

        with patch('engine.llm_client.call_llm', side_effect=capture_llm_call):
            engine = ContentEngine()
            engine._compile_with_llm(
                seed_content="Test seed",
                pillar="training",
                platform="tiktok"
            )

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]

        # Prompt should mention voice/tone
        assert "voice" in prompt.lower() or "tone" in prompt.lower(), \
            "Prompt should include voice configuration"

    def test_llm_prompt_includes_pillar_context(self):
        """
        The LLM prompt must include pillar configuration.

        Pillars define the content themes and messaging.
        """
        from engine.content_engine import ContentEngine

        captured_prompts = []

        def capture_llm_call(prompt, **kwargs):
            captured_prompts.append(prompt)
            return "Generated content"

        with patch('engine.llm_client.call_llm', side_effect=capture_llm_call):
            engine = ContentEngine()
            engine._compile_with_llm(
                seed_content="Test seed",
                pillar="training",
                platform="tiktok"
            )

        prompt = captured_prompts[0]

        # Prompt should mention pillar
        assert "pillar" in prompt.lower() or "training" in prompt.lower(), \
            "Prompt should include pillar context"

    def test_llm_prompt_includes_platform_specifics(self):
        """
        The LLM prompt must include platform-specific requirements.

        Each platform has different content constraints (length, format, etc.).
        """
        from engine.content_engine import ContentEngine

        captured_kwargs = []

        def capture_llm_call(prompt, **kwargs):
            captured_kwargs.append({"prompt": prompt, **kwargs})
            return "Generated content"

        with patch('engine.llm_client.call_llm', side_effect=capture_llm_call):
            engine = ContentEngine()

            # Test different platforms
            for platform in ["tiktok", "instagram", "x"]:
                engine._compile_with_llm(
                    seed_content="Test seed",
                    pillar="training",
                    platform=platform
                )

        # Should have called for each platform
        assert len(captured_kwargs) == 3

        # Each prompt should mention the platform
        for call in captured_kwargs:
            prompt = call["prompt"]
            # Platform name should be in prompt somewhere
            assert any(p in prompt.lower() for p in ["tiktok", "instagram", "x", "twitter"]), \
                f"Prompt should mention platform: {prompt[:100]}..."


class TestContentEngineCompilation:
    """Tests for the full compilation workflow."""

    def test_compile_content_processes_all_seeds(self):
        """
        compile_content must process all seed files in the directory.
        """
        from engine.content_engine import compile_content

        with patch('engine.llm_client.call_llm', return_value="Draft content"):
            with patch('engine.content_engine.ContentEngine._load_seeds') as mock_load:
                # Mock 3 seeds
                mock_load.return_value = [
                    MagicMock(name="seed1", pillar="training", raw_content="Content 1"),
                    MagicMock(name="seed2", pillar="coaching", raw_content="Content 2"),
                    MagicMock(name="seed3", pillar="community", raw_content="Content 3"),
                ]

                drafts = compile_content()

                # Should generate drafts for each seed
                assert len(drafts) > 0, "Should generate drafts"

    def test_compile_content_returns_compiled_drafts(self):
        """
        Compiled drafts must include all required metadata.
        """
        from engine.content_engine import compile_content, CompiledDraft

        with patch('engine.llm_client.call_llm', return_value="Generated content"):
            drafts = compile_content()

            # Each draft should be a CompiledDraft with required fields
            for draft in drafts:
                assert isinstance(draft, CompiledDraft), \
                    "Should return CompiledDraft instances"
                assert draft.content, "Draft must have content"
                assert draft.platform, "Draft must have platform"
                assert draft.compiled_at, "Draft must have timestamp"


class TestContentEngineLLMTier:
    """Tests for correct LLM tier usage."""

    def test_uses_tier_2_for_content_generation(self):
        """
        Content generation should use Tier 2 (Sonnet) for quality.

        Content is user-facing and requires higher quality output.
        """
        from engine.content_engine import ContentEngine

        captured_kwargs = []

        def capture_llm_call(prompt, **kwargs):
            captured_kwargs.append(kwargs)
            return "Generated content"

        with patch('engine.llm_client.call_llm', side_effect=capture_llm_call):
            engine = ContentEngine()
            engine._compile_with_llm(
                seed_content="Test",
                pillar="training",
                platform="tiktok"
            )

        assert len(captured_kwargs) == 1
        assert captured_kwargs[0].get("tier") == 2, \
            f"Content generation should use Tier 2, got {captured_kwargs[0].get('tier')}"


class TestContentEngineFallback:
    """Tests for error handling and fallbacks."""

    def test_handles_llm_failure_gracefully(self):
        """
        If LLM fails, should return empty list, not crash.
        """
        from engine.content_engine import compile_content

        with patch('engine.llm_client.call_llm', side_effect=Exception("API Error")):
            # Should not raise
            drafts = compile_content()

            # Should return empty or partial results
            assert isinstance(drafts, list), "Should return list even on error"

    def test_logs_compilation_intent(self):
        """
        LLM calls should be logged with content_compilation intent.
        """
        from engine.content_engine import ContentEngine

        captured_kwargs = []

        def capture_llm_call(prompt, **kwargs):
            captured_kwargs.append(kwargs)
            return "Content"

        with patch('engine.llm_client.call_llm', side_effect=capture_llm_call):
            engine = ContentEngine()
            engine._compile_with_llm("Test", "training", "tiktok")

        assert captured_kwargs[0].get("intent") == "content_compilation", \
            f"Should log with content_compilation intent, got {captured_kwargs[0].get('intent')}"
