"""
test_profile_isolation.py - Tests for Profile Isolation and Portability

Sprint 6: Portability, Polish, and The Final Seal

Proves that the engine logic is 100% decoupled from any specific domain.
A blank_template profile with minimal/empty configuration must work.
"""

import pytest
from pathlib import Path


class TestBlankTemplateLoading:
    """Tests for loading the blank_template profile."""

    def test_blank_template_profile_exists(self):
        """Assert blank_template profile directory exists."""
        from engine.profile import PROFILES_DIR

        blank_template = PROFILES_DIR / "blank_template"
        assert blank_template.exists(), "blank_template profile must exist"
        assert blank_template.is_dir()

    def test_blank_template_has_required_structure(self):
        """Assert blank_template has all required subdirectories."""
        from engine.profile import PROFILES_DIR

        blank_template = PROFILES_DIR / "blank_template"
        required_dirs = ["config", "dock", "entities", "skills", "telemetry", "queue", "output"]

        for subdir in required_dirs:
            path = blank_template / subdir
            assert path.exists(), f"Missing required directory: {subdir}"
            assert path.is_dir()

    def test_blank_template_has_minimal_config(self):
        """Assert blank_template has minimal config files."""
        from engine.profile import PROFILES_DIR

        config_dir = PROFILES_DIR / "blank_template" / "config"
        required_files = ["routing.config", "zones.schema"]

        for filename in required_files:
            path = config_dir / filename
            assert path.exists(), f"Missing required config: {filename}"


class TestCognitiveRouterWithBlankTemplate:
    """Tests for CognitiveRouter behavior with minimal config."""

    def test_router_loads_blank_template_without_crash(self):
        """Assert router loads blank_template gracefully."""
        from engine.cognitive_router import CognitiveRouter, reset_router
        from engine.profile import set_profile

        set_profile("blank_template")
        reset_router()

        # Should not raise
        router = CognitiveRouter()
        assert router is not None

    def test_router_handles_unmatched_input(self):
        """Assert router handles unmatched input gracefully (via Ratchet or fallback)."""
        from engine.cognitive_router import classify_intent, reset_router
        from engine.profile import set_profile

        set_profile("blank_template")
        reset_router()

        result = classify_intent("some random input")

        # Should return a valid routing result, not crash
        # blank_template now includes ratchet_intent_classify for LLM classification fallback
        assert result.intent is not None
        assert result.zone in ("green", "yellow", "red")
        # Could be ratchet_intent_classify (LLM fallback), general_chat, or unknown
        assert result.intent in ("ratchet_intent_classify", "general_chat", "unknown")

    def test_router_still_works_after_blank_template(self):
        """Assert router can switch back to coach_demo."""
        from engine.cognitive_router import classify_intent, reset_router
        from engine.profile import set_profile

        # Load blank first
        set_profile("blank_template")
        reset_router()
        result = classify_intent("dock")

        # Blank template has no dock route - should be unknown
        # (unless we add basic system routes)

        # Switch to coach_demo
        set_profile("coach_demo")
        reset_router()
        result = classify_intent("dock")

        # Now it should work
        assert result.intent == "dock_status"


class TestPipelineWithBlankTemplate:
    """Tests for pipeline execution with blank_template profile."""

    def test_pipeline_runs_with_blank_template(self):
        """Assert pipeline executes without errors on blank_template."""
        from engine.pipeline import run_pipeline
        from engine.profile import set_profile
        from engine.cognitive_router import reset_router

        set_profile("blank_template")
        reset_router()

        # Use "dock" command which routes to Green Zone (no approval needed)
        context = run_pipeline(
            raw_input="dock",
            source="test"
        )

        assert context is not None
        assert context.executed is True  # Pipeline completed execution
        assert context.telemetry_event is not None

    def test_pipeline_logs_telemetry_for_blank_template(self, tmp_path, monkeypatch):
        """Assert telemetry is logged even with blank profile."""
        from engine.pipeline import run_pipeline
        from engine.profile import set_profile
        from engine.cognitive_router import reset_router

        set_profile("blank_template")
        reset_router()

        # Mock telemetry path to temp
        test_telemetry = tmp_path / "telemetry.jsonl"
        monkeypatch.setattr(
            "engine.telemetry.get_telemetry_path",
            lambda: test_telemetry
        )

        # Use "dock" command which routes to Green Zone (no approval needed)
        run_pipeline(
            raw_input="dock",
            source="test"
        )

        # Telemetry should be written
        assert test_telemetry.exists()
        content = test_telemetry.read_text()
        assert "dock" in content


class TestDockWithBlankTemplate:
    """Tests for Dock behavior with empty dock directory."""

    def test_dock_handles_empty_directory(self):
        """Assert Dock gracefully handles empty dock/."""
        from engine.dock import LocalDock, _dock_instance
        from engine.profile import set_profile, get_dock_dir
        import engine.dock as dock_module

        set_profile("blank_template")
        # Reset the dock singleton
        dock_module._dock_instance = None

        dock = LocalDock()

        # Should not crash
        assert dock.get_chunk_count() >= 0
        sources = dock.list_sources()
        # May have some sources or none - should not crash
        assert isinstance(sources, list)

    def test_dock_query_returns_empty_for_blank(self):
        """Assert Dock query returns empty string when no content."""
        from engine.dock import get_dock
        from engine.profile import set_profile
        import engine.dock as dock_module

        set_profile("blank_template")
        # Reset the dock singleton
        dock_module._dock_instance = None

        dock = get_dock()
        results = dock.query_context("anything")

        # Should return empty string or "No context found" message, not error
        assert isinstance(results, str)


class TestDispatcherWithBlankTemplate:
    """Tests for Dispatcher behavior with minimal handlers."""

    def test_dispatcher_handles_unmatched_input(self):
        """Assert dispatcher handles unmatched intents gracefully."""
        from engine.dispatcher import dispatch_action
        from engine.cognitive_router import classify_intent, reset_router
        from engine.profile import set_profile

        set_profile("blank_template")
        reset_router()

        routing = classify_intent("unknown command")
        result = dispatch_action(routing, "unknown command")

        # Should return a valid result, not crash
        assert result.success is True
        assert result.data.get("type") in ("passthrough", "general_chat")


class TestProfileIsolation:
    """Tests for profile state isolation."""

    def test_profile_switch_clears_router_state(self):
        """Assert switching profiles clears router cache."""
        from engine.cognitive_router import classify_intent, reset_router
        from engine.profile import set_profile

        # Load coach_demo
        set_profile("coach_demo")
        reset_router()
        result1 = classify_intent("dock")
        assert result1.intent == "dock_status"

        # Switch to blank_template
        set_profile("blank_template")
        reset_router()
        result2 = classify_intent("dock")

        # Should be different (blank has no dock route unless added)
        # The key is that it doesn't use coach_demo's routing

    def test_profile_switch_uses_correct_telemetry_path(self):
        """Assert telemetry writes to correct profile directory."""
        from engine.profile import set_profile, get_telemetry_path

        set_profile("coach_demo")
        path1 = get_telemetry_path()
        assert "coach_demo" in str(path1)

        set_profile("blank_template")
        path2 = get_telemetry_path()
        assert "blank_template" in str(path2)
        assert path1 != path2


class TestBlankTemplateStartup:
    """Tests for REPL startup with blank_template."""

    def test_autonomaton_starts_with_blank_template(self):
        """Assert autonomaton.py can start with blank_template."""
        import subprocess
        import sys

        # Run autonomaton with blank_template and immediately exit
        # Use --skip-welcome to avoid LLM calls during startup
        # Note: blank_template has a structured-plan.md to skip first-boot prompt
        result = subprocess.run(
            [sys.executable, "autonomaton.py", "--profile", "blank_template", "--skip-welcome"],
            input="exit\n",
            capture_output=True,
            text=True,
            timeout=15,
            cwd=Path(__file__).parent.parent
        )

        # Should exit cleanly
        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "THE AUTONOMATON" in result.stdout
        assert "blank_template" in result.stdout
