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
    """Verify glass pipeline display functions."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock PipelineContext for testing."""
        from engine.pipeline import PipelineContext
        ctx = PipelineContext(
            raw_input="hello",
            source="test"
        )
        ctx.telemetry_event = {"id": "test1234567890"}
        ctx.intent = "general_chat"
        ctx.domain = "system"
        ctx.zone = "green"
        ctx.approved = True
        ctx.executed = True
        ctx.entities = {
            "routing": {
                "tier": 0,
                "confidence": 1.0,
                "handler": "general_chat",
                "intent_type": "conversational",
                "action_required": False,
                "llm_metadata": {}
            }
        }
        ctx.dock_context = []
        ctx.result = {"status": "success", "message": "Done"}
        return ctx

    def test_glass_extracts_data(self, mock_context):
        from engine.glass import _extract_glass_data
        data = _extract_glass_data(mock_context)

        assert data["event_id"] == "test1234"  # First 8 chars
        assert data["intent"] == "general_chat"
        assert data["tier"] == 0
        assert data["method"] == "keyword"
        assert data["cost_str"] == "$0.00"
        assert data["zone"] == "green"

    def test_glass_keyword_match(self, mock_context):
        """Tier 0 keyword match shows correct method."""
        from engine.glass import _extract_glass_data
        data = _extract_glass_data(mock_context)

        assert data["tier"] == 0
        assert data["method"] == "keyword"
        assert data["is_cache_hit"] is False

    def test_glass_llm_classification(self, mock_context):
        """Tier 2 LLM shows cost estimate."""
        from engine.glass import _extract_glass_data

        mock_context.entities["routing"]["tier"] = 2
        mock_context.telemetry_event["tier"] = 2
        mock_context.telemetry_event["cost_usd"] = 0.0032

        data = _extract_glass_data(mock_context)

        assert data["tier"] == 2
        assert data["method"] == "LLM"
        assert "$0.003" in data["cost_str"]

    def test_glass_cache_hit(self, mock_context):
        """Cache hit shows HIT marker and $0.00."""
        from engine.glass import _extract_glass_data

        mock_context.entities["routing"]["llm_metadata"] = {"source": "pattern_cache"}

        data = _extract_glass_data(mock_context)

        assert data["method"] == "cache HIT"
        assert data["is_cache_hit"] is True
        assert data["cost_str"] == "$0.00"

    def test_glass_conversational_skip(self, mock_context):
        """Conversational intent shows 'Skipped' for compilation."""
        from engine.glass import _extract_glass_data

        mock_context.entities["routing"]["intent_type"] = "conversational"

        data = _extract_glass_data(mock_context)

        assert "Skipped" in data["compilation"]

    def test_glass_yellow_zone(self, mock_context):
        """Yellow zone shows confirmation required."""
        from engine.glass import _extract_glass_data

        mock_context.zone = "yellow"

        data = _extract_glass_data(mock_context)

        assert data["zone"] == "yellow"
        assert "requires confirmation" in data["approval"].lower()

    def test_glass_format_box_output(self, mock_context):
        """Format box produces multi-line output with all stages."""
        from engine.glass import _extract_glass_data, format_glass_box

        data = _extract_glass_data(mock_context)
        box = format_glass_box(data, "medium")

        # Should have all 5 stages
        assert "GLASS PIPELINE" in box
        assert "Telemetry" in box
        assert "Recognition" in box
        assert "Compilation" in box
        assert "Approval" in box
        assert "Execution" in box


class TestRatchetAnnouncement:
    """Verify Ratchet announcement fires once per session."""

    def test_ratchet_announcement_once(self):
        """Ratchet fires on first cache hit, not on second."""
        from engine.pipeline import PipelineContext
        from engine.glass import get_ratchet_announcement, reset_ratchet_announcement

        # Reset for clean test
        reset_ratchet_announcement()

        # Create cache hit context
        ctx = PipelineContext(raw_input="test", source="test")
        ctx.entities = {
            "routing": {
                "llm_metadata": {"source": "pattern_cache"}
            }
        }

        # First call should announce
        msg1 = get_ratchet_announcement(ctx)
        assert msg1 is not None
        assert "RATCHET" in msg1

        # Second call should not announce
        msg2 = get_ratchet_announcement(ctx)
        assert msg2 is None


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


class TestStartupForceRoute:
    """Verify startup intents work with force_route (bug fix E.2/F.6)."""

    def test_startup_force_route_welcome_card(self):
        """welcome_card routes correctly when force_route is used."""
        from engine.profile import set_profile
        from engine.pipeline import run_pipeline

        set_profile("coach_demo")
        # This would trigger Jidoka without force_route since keywords: []
        context = run_pipeline(
            "welcome_card",
            source="system_startup",
            force_route="welcome_card"
        )

        # Should NOT trigger clarification Jidoka
        assert context.intent == "welcome_card"
        assert context.zone == "green"

    def test_startup_force_route_startup_brief(self):
        """startup_brief routes correctly when force_route is used."""
        from engine.profile import set_profile
        from engine.pipeline import run_pipeline

        set_profile("coach_demo")
        context = run_pipeline(
            "startup_brief",
            source="system_startup",
            force_route="startup_brief"
        )

        assert context.intent == "startup_brief"
        assert context.zone == "green"

    def test_startup_force_route_generate_plan(self):
        """generate_plan config exists and is properly configured."""
        from engine.profile import set_profile
        from engine.cognitive_router import get_router, reset_router

        set_profile("coach_demo")
        reset_router()
        router = get_router()

        # Verify the intent exists in routing config (force_route uses this)
        assert "generate_plan" in router.routes
        route = router.routes["generate_plan"]
        assert route["zone"] == "yellow"
        assert route["handler"] == "generate_plan"


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
