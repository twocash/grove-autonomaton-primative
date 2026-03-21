"""
test_reference_profile.py - Reference Profile Sprint Verification Tests

Verifies:
1. Profile loading and config
2. Glass pipeline presentation layer
3. Handler registration and security
4. Tips engine behavior
5. Profile isolation (engine unchanged)
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ============================================================================
# Profile Loading Tests
# ============================================================================

class TestProfileLoading:
    """Verify reference profile loads correctly."""

    def test_reference_profile_loads(self):
        from engine.profile import set_profile, get_profile
        set_profile("reference")
        assert get_profile() == "reference"

    def test_list_profiles_includes_reference(self):
        from engine.profile import list_available_profiles
        profiles = list_available_profiles()
        assert "reference" in profiles
        assert "coach_demo" in profiles
        assert "blank_template" in profiles


class TestProfileConfigDefaults:
    """Verify profile config handles missing files gracefully."""

    def test_profile_config_defaults(self):
        """Missing profile.yaml returns defaults."""
        from engine.profile import set_profile
        from engine.config_loader import load_profile_config

        set_profile("blank_template")  # Has no profile.yaml
        config = load_profile_config()

        assert config["display"]["glass_pipeline"] is False
        assert config["display"]["tips"] is False
        assert config["startup"]["skip_welcome"] is False


class TestProfileConfigReference:
    """Verify reference profile.yaml loads correctly."""

    def test_profile_config_reference(self):
        from engine.profile import set_profile
        from engine.config_loader import load_profile_config

        set_profile("reference")
        config = load_profile_config()

        assert config["display"]["glass_pipeline"] is True
        assert config["display"]["tips"] is True
        assert config["display"]["glass_level"] == "medium"
        assert config["startup"]["skip_welcome"] is True
        assert config["startup"]["skip_plan_generation"] is True


# ============================================================================
# Glass Pipeline Tests
# ============================================================================

class TestGlassPipeline:
    """Verify glass pipeline display functions (telemetry-based)."""

    def test_glass_telemetry_functions_exist(self):
        """Telemetry-based glass functions are available."""
        from engine.glass import read_pipeline_events, display_glass_from_telemetry
        assert callable(read_pipeline_events)
        assert callable(display_glass_from_telemetry)

    def test_glass_reads_from_telemetry(self):
        """Glass reads events from telemetry stream."""
        from engine.profile import set_profile
        from engine.pipeline import run_pipeline
        from engine.cognitive_router import reset_router
        from engine.glass import read_pipeline_events

        set_profile("reference")
        reset_router()
        ctx = run_pipeline("hello", source="glass_test")
        pipeline_id = ctx.telemetry_event["id"]

        events = read_pipeline_events(pipeline_id)
        assert isinstance(events, list)
        assert len(events) >= 1

    def test_glass_stage_render_function_exists(self):
        """Stage renderer is available."""
        from engine.glass import _render_stage_from_event
        assert callable(_render_stage_from_event)

    def test_glass_zone_colors(self):
        """Zone color function returns correct colors (or empty in non-TTY)."""
        from engine.glass import _get_zone_color, _c

        # In TTY mode, colors contain ANSI codes; in non-TTY, they're empty
        green = _get_zone_color("green")
        yellow = _get_zone_color("yellow")
        red = _get_zone_color("red")

        if _c.ENABLED:
            assert "92" in green  # Green ANSI
            assert "93" in yellow  # Yellow ANSI
            assert "91" in red  # Red ANSI
        else:
            # Non-TTY: colors are disabled, function still returns valid strings
            assert green == ""
            assert yellow == ""
            assert red == ""


class TestRatchetAnnouncement:
    """Verify Ratchet announcement fires once per session."""

    def test_ratchet_announcement_once(self):
        """Ratchet fires on first cache hit, not on second."""
        from engine.glass import _format_ratchet_from_event, reset_ratchet_announcement

        # Reset for clean test
        reset_ratchet_announcement()

        # Create cache hit event
        cache_event = {"inferred": {"method": "cache"}}

        # First call should announce
        msg1 = _format_ratchet_from_event(cache_event)
        assert msg1  # Non-empty string
        assert "RATCHET" in msg1

        # Second call should not announce (session-scoped)
        msg2 = _format_ratchet_from_event(cache_event)
        assert msg2 == ""  # Empty string on second call


# ============================================================================
# Handler Tests
# ============================================================================

class TestShowFileHandler:
    """Verify show_file handler security and functionality."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from engine.profile import set_profile
        set_profile("reference")

    def test_show_file_valid_target(self):
        """show_file with valid path returns contents."""
        from engine.dispatcher import Dispatcher
        from engine.cognitive_router import RoutingResult

        dispatcher = Dispatcher()

        routing = RoutingResult(
            intent="show_config",
            domain="system",
            zone="green",
            tier=0,
            confidence=1.0,
            handler="show_file",
            handler_args={"target": "config/routing.config"}
        )

        result = dispatcher.dispatch(routing, "show config")

        assert result.success is True
        assert result.message  # Has content

    def test_show_file_path_traversal(self):
        """show_file rejects path traversal attempts."""
        from engine.dispatcher import Dispatcher
        from engine.cognitive_router import RoutingResult

        dispatcher = Dispatcher()

        routing = RoutingResult(
            intent="show_engine_unsafe",
            domain="system",
            zone="green",
            tier=0,
            confidence=1.0,
            handler="show_file",
            handler_args={"target": "../engine/pipeline.py"}
        )

        result = dispatcher.dispatch(routing, "show ../engine/pipeline.py")

        assert result.success is False
        assert "denied" in result.message.lower()

    def test_show_file_nonexistent(self):
        """show_file with nonexistent path returns graceful message."""
        from engine.dispatcher import Dispatcher
        from engine.cognitive_router import RoutingResult

        dispatcher = Dispatcher()

        routing = RoutingResult(
            intent="show_missing",
            domain="system",
            zone="green",
            tier=0,
            confidence=1.0,
            handler="show_file",
            handler_args={"target": "config/nonexistent.yaml"}
        )

        result = dispatcher.dispatch(routing, "show nonexistent")

        # Should handle gracefully, not crash
        assert result is not None


class TestShowEngineManifest:
    """Verify engine manifest handler."""

    def test_show_engine_manifest(self):
        """Engine manifest returns file list with line counts."""
        from engine.dispatcher import Dispatcher
        from engine.cognitive_router import RoutingResult
        from engine.profile import set_profile

        set_profile("reference")
        dispatcher = Dispatcher()

        routing = RoutingResult(
            intent="show_engine",
            domain="system",
            zone="green",
            tier=0,
            confidence=1.0,
            handler="show_engine_manifest",
            handler_args={}
        )

        result = dispatcher.dispatch(routing, "show engine")

        assert result.success is True
        assert "pipeline.py" in result.message
        assert "dispatcher.py" in result.message
        # Should have line counts
        assert "lines" in result.message.lower()


# ============================================================================
# Tips Engine Tests
# ============================================================================

class TestTipsEngine:
    """Verify tips engine behavior."""

    @pytest.fixture
    def mock_context(self):
        from engine.pipeline import PipelineContext
        ctx = PipelineContext(raw_input="hello", source="test")
        ctx.intent = "general_chat"
        ctx.zone = "green"
        ctx.entities = {
            "routing": {
                "tier": 0,
                "llm_metadata": {}
            }
        }
        return ctx

    def test_tip_fires_on_matching_trigger(self, mock_context):
        """Tip fires when trigger conditions match."""
        from engine.glass import TipEngine
        from engine.profile import set_profile

        set_profile("reference")
        engine = TipEngine()

        # First general_chat should trigger first_greeting tip
        tip = engine.evaluate(mock_context)

        assert tip is not None
        assert "won't recognize" in tip.lower()

    def test_tip_fires_once(self, mock_context):
        """Same trigger condition doesn't repeat tip."""
        from engine.glass import TipEngine
        from engine.profile import set_profile

        set_profile("reference")
        engine = TipEngine()

        # First call
        tip1 = engine.evaluate(mock_context)
        assert tip1 is not None

        # Second call with same conditions
        tip2 = engine.evaluate(mock_context)
        assert tip2 is None  # Already shown

    def test_tier_trigger_fires(self):
        """after_tier trigger fires correctly."""
        from engine.pipeline import PipelineContext
        from engine.glass import TipEngine
        from engine.profile import set_profile

        set_profile("reference")
        engine = TipEngine()

        # Skip the first_greeting tip
        ctx1 = PipelineContext(raw_input="hi", source="test")
        ctx1.intent = "general_chat"
        ctx1.entities = {"routing": {"tier": 0, "llm_metadata": {}}}
        engine.evaluate(ctx1)

        # Now trigger tier 2
        ctx2 = PipelineContext(raw_input="ambiguous", source="test")
        ctx2.intent = "strategy_session"
        ctx2.entities = {"routing": {"tier": 2, "llm_metadata": {}}}

        tip = engine.evaluate(ctx2)

        assert tip is not None
        assert "LLM" in tip

    def test_no_tips_file(self):
        """Missing tips.yaml produces no errors, no tips."""
        from engine.pipeline import PipelineContext
        from engine.glass import TipEngine
        from engine.profile import set_profile

        set_profile("blank_template")  # No tips.yaml
        engine = TipEngine()

        ctx = PipelineContext(raw_input="hi", source="test")
        ctx.intent = "general_chat"
        ctx.entities = {"routing": {"tier": 0, "llm_metadata": {}}}

        tip = engine.evaluate(ctx)

        assert tip is None  # No tips configured


# ============================================================================
# Integration Tests (Profile Isolation)
# ============================================================================

class TestProfileIsolation:
    """Verify engine behavior unchanged across profiles."""

    def test_engine_unchanged(self):
        """Pipeline produces same structure for identical input across profiles."""
        from engine.profile import set_profile
        from engine.pipeline import run_pipeline

        # Run with reference
        set_profile("reference")
        ref_context = run_pipeline("hello", source="test")

        # Run with blank_template
        set_profile("blank_template")
        blank_context = run_pipeline("hello", source="test")

        # Both should have same structural properties
        assert ref_context.intent is not None
        assert blank_context.intent is not None
        assert ref_context.zone is not None
        assert blank_context.zone is not None
        assert ref_context.telemetry_event is not None
        assert blank_context.telemetry_event is not None

    def test_coach_demo_unaffected(self):
        """coach_demo loads and runs without changes."""
        from engine.profile import set_profile
        from engine.pipeline import run_pipeline

        set_profile("coach_demo")
        context = run_pipeline("hello", source="test")

        # Should route to general_chat
        assert context.intent == "general_chat"
        assert context.executed is True


class TestReferenceProfileConfig:
    """Verify reference profile config files exist."""

    def test_reference_directory_exists(self):
        assert Path("profiles/reference").is_dir()

    def test_reference_config_files_exist(self):
        base = Path("profiles/reference/config")
        assert (base / "profile.yaml").exists()
        assert (base / "persona.yaml").exists()
        assert (base / "routing.config").exists()
        assert (base / "zones.schema").exists()
        assert (base / "pattern_cache.yaml").exists()
        assert (base / "tips.yaml").exists()

    def test_reference_skills_exist(self):
        skills = Path("profiles/reference/skills")
        assert skills.is_dir()
        assert (skills / "operator-guide").is_dir()
        assert (skills / "operator-guide/prompt.md").exists()
