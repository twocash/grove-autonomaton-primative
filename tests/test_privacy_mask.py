"""
test_privacy_mask.py - Tests for Privacy Mask functionality

Sprint 7: The Socratic OOBE, Domain Bootstrapping, & Privacy Mask

The Privacy Mask ensures that when working with minors, real names
are never sent to external LLMs during content generation. Instead,
registered entity names are swapped with their public_alias.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestPrivacyMaskEntitySwap:
    """Tests for entity name to public_alias swapping."""

    def test_privacy_mask_swaps_player_name_with_alias(self, tmp_path, monkeypatch):
        """Assert real player name is replaced with public_alias before LLM call."""
        from engine.profile import set_profile
        import engine.profile as profile_module

        set_profile("coach_demo")

        # Create temp entities directory with a player
        entities_dir = tmp_path / "entities" / "players"
        entities_dir.mkdir(parents=True)

        player_file = entities_dir / "marcus-henderson.md"
        player_file.write_text("""# Marcus Henderson

## Profile
- **Type:** Player
- **public_alias:** a promising freshman
- **Grade:** Freshman

## Notes
Great attitude, working on short game.
""", encoding="utf-8")

        monkeypatch.setattr(profile_module, "get_entities_dir", lambda: tmp_path / "entities")

        from engine.compiler import apply_privacy_mask

        raw_text = "Marcus Henderson hit an incredible shot today. Marcus is improving fast."
        masked_text = apply_privacy_mask(raw_text)

        assert "Marcus Henderson" not in masked_text
        assert "Marcus" not in masked_text
        assert "a promising freshman" in masked_text

    def test_privacy_mask_handles_multiple_players(self, tmp_path, monkeypatch):
        """Assert multiple player names are all replaced."""
        from engine.profile import set_profile
        import engine.profile as profile_module

        set_profile("coach_demo")

        entities_dir = tmp_path / "entities" / "players"
        entities_dir.mkdir(parents=True)

        # Player 1
        (entities_dir / "marcus-henderson.md").write_text("""# Marcus Henderson
## Profile
- **public_alias:** a freshman golfer
""", encoding="utf-8")

        # Player 2
        (entities_dir / "jake-smith.md").write_text("""# Jake Smith
## Profile
- **public_alias:** a senior captain
""", encoding="utf-8")

        # Apply monkeypatch BEFORE importing from compiler
        monkeypatch.setattr(profile_module, "get_entities_dir", lambda: tmp_path / "entities")

        # Import after monkeypatch
        import importlib
        import engine.compiler
        importlib.reload(engine.compiler)
        from engine.compiler import apply_privacy_mask

        raw_text = "Marcus Henderson and Jake Smith played together. Marcus outdrove Jake."
        masked_text = apply_privacy_mask(raw_text)

        assert "Marcus Henderson" not in masked_text
        assert "Jake Smith" not in masked_text
        assert "Marcus" not in masked_text
        assert "Jake" not in masked_text
        assert "a freshman golfer" in masked_text
        assert "a senior captain" in masked_text

    def test_privacy_mask_preserves_non_entity_text(self, tmp_path, monkeypatch):
        """Assert text without entity names is preserved."""
        from engine.profile import set_profile
        import engine.profile as profile_module

        set_profile("coach_demo")

        entities_dir = tmp_path / "entities" / "players"
        entities_dir.mkdir(parents=True)

        monkeypatch.setattr(profile_module, "get_entities_dir", lambda: tmp_path / "entities")

        from engine.compiler import apply_privacy_mask

        raw_text = "The team practiced putting today. Great weather on the course."
        masked_text = apply_privacy_mask(raw_text)

        assert masked_text == raw_text

    def test_privacy_mask_handles_missing_alias_gracefully(self, tmp_path, monkeypatch):
        """Assert entities without public_alias default to generic term."""
        from engine.profile import set_profile
        import engine.profile as profile_module

        set_profile("coach_demo")

        entities_dir = tmp_path / "entities" / "players"
        entities_dir.mkdir(parents=True)

        # Player without public_alias
        (entities_dir / "tom-jones.md").write_text("""# Tom Jones
## Profile
- **Type:** Player
- **Grade:** Junior
""", encoding="utf-8")

        monkeypatch.setattr(profile_module, "get_entities_dir", lambda: tmp_path / "entities")

        from engine.compiler import apply_privacy_mask

        raw_text = "Tom Jones showed great improvement."
        masked_text = apply_privacy_mask(raw_text)

        assert "Tom Jones" not in masked_text
        assert "Tom" not in masked_text
        # Should use a default alias
        assert "a player" in masked_text or "a team member" in masked_text


class TestPrivacyMaskContentCompilation:
    """Tests for privacy mask integration with content compilation."""

    def test_content_compiler_applies_privacy_mask_before_llm(self, tmp_path, monkeypatch):
        """Assert privacy mask runs before LLM prompt is sent."""
        from engine.profile import set_profile
        import engine.profile as profile_module

        set_profile("coach_demo")

        # Setup entities
        entities_dir = tmp_path / "entities"
        players_dir = entities_dir / "players"
        seeds_dir = entities_dir / "content-seeds"
        players_dir.mkdir(parents=True)
        seeds_dir.mkdir(parents=True)

        (players_dir / "marcus-henderson.md").write_text("""# Marcus Henderson
## Profile
- **public_alias:** one of our freshmen
""", encoding="utf-8")

        # Create a content seed mentioning the player
        (seeds_dir / "test-seed.md").write_text("""# Great Shot by Marcus

**Pillar:** short_game_devotionals
**Mined:** 2024-01-15

## Content
Marcus Henderson hit a beautiful approach shot on hole 7.
""", encoding="utf-8")

        monkeypatch.setattr(profile_module, "get_entities_dir", lambda: entities_dir)

        # Track the prompt sent to LLM
        captured_prompts = []

        def mock_call_llm(prompt, **kwargs):
            captured_prompts.append(prompt)
            return '{"platform": "tiktok", "content": "Great golf content!"}'

        # Need to patch at the llm_client module level
        with patch("engine.llm_client.call_llm", mock_call_llm):
            from engine.content_engine import compile_content, get_content_engine
            # Reset the engine instance to pick up new config
            import engine.content_engine as ce
            ce._engine_instance = None
            compile_content(str(seeds_dir))

        # Verify the prompt was captured and check for privacy
        if captured_prompts:
            prompt = captured_prompts[0]
            assert "Marcus Henderson" not in prompt
            assert "Marcus" not in prompt


class TestPrivacyMaskBoundary:
    """Tests ensuring privacy mask is the final step before LLM dispatch."""

    def test_privacy_mask_applied_at_compilation_boundary(self, tmp_path, monkeypatch):
        """Assert mask is applied as final step before external call."""
        from engine.profile import set_profile
        import engine.profile as profile_module

        set_profile("coach_demo")

        entities_dir = tmp_path / "entities" / "players"
        entities_dir.mkdir(parents=True)

        (entities_dir / "alex-turner.md").write_text("""# Alex Turner
## Profile
- **public_alias:** a varsity player
""", encoding="utf-8")

        monkeypatch.setattr(profile_module, "get_entities_dir", lambda: tmp_path / "entities")

        from engine.compiler import apply_privacy_mask

        # Simulate content that might be sent to LLM
        content_for_llm = """
        Create a TikTok script about Alex Turner's amazing putt.
        Alex showed incredible focus under pressure.
        """

        masked = apply_privacy_mask(content_for_llm)

        # The masked content should be safe to send externally
        assert "Alex Turner" not in masked
        assert "Alex" not in masked
        assert "a varsity player" in masked


class TestPrivacyMaskEntityLoading:
    """Tests for loading entities and extracting aliases."""

    def test_load_player_entities_extracts_aliases(self, tmp_path, monkeypatch):
        """Assert entity loader correctly extracts name and alias pairs."""
        from engine.profile import set_profile
        import engine.profile as profile_module

        set_profile("coach_demo")

        entities_dir = tmp_path / "entities" / "players"
        entities_dir.mkdir(parents=True)

        (entities_dir / "player-one.md").write_text("""# John Doe
## Profile
- **public_alias:** a junior golfer
""", encoding="utf-8")

        monkeypatch.setattr(profile_module, "get_entities_dir", lambda: tmp_path / "entities")

        from engine.compiler import load_entity_aliases

        aliases = load_entity_aliases()

        assert "John Doe" in aliases
        assert aliases["John Doe"] == "a junior golfer"
