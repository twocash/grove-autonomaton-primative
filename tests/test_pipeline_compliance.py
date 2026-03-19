"""
test_pipeline_compliance.py - Architectural Invariant Tests

These tests ENFORCE the architectural claims from the TCP/IP paper
and Pattern Document. They verify structural properties, not behavior.
If any future sprint breaks these, the test suite blocks the merge.
"""

import pytest
import json
import re
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestPerStageTraces:
    """V1: Every stage produces a structured trace."""

    def _run_and_collect(self, text="hello", profile="reference"):
        from engine.profile import set_profile
        set_profile(profile)
        from engine.cognitive_router import reset_router
        reset_router()
        from engine.pipeline import run_pipeline
        ctx = run_pipeline(text, source="test_compliance")
        # Read telemetry
        from engine.profile import get_telemetry_path
        events = []
        tpath = get_telemetry_path()
        if tpath.exists():
            with open(tpath) as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))
        pid = ctx.telemetry_event["id"]
        return [e for e in events
                if e.get("id") == pid
                or e.get("inferred", {}).get("pipeline_id") == pid]

    def test_five_stage_traces_exist(self):
        events = self._run_and_collect("hello")
        stages = {e.get("inferred", {}).get("stage") for e in events}
        required = {"telemetry", "recognition", "compilation",
                    "approval", "execution"}
        assert required.issubset(stages), \
            f"Missing stages: {required - stages}"

    def test_pipeline_id_correlation(self):
        events = self._run_and_collect("hello")
        pid = events[0]["id"]  # Stage 1 event
        for e in events[1:]:
            assert e.get("inferred", {}).get("pipeline_id") == pid, \
                f"Stage {e.get('inferred',{}).get('stage')} missing pipeline_id"

    def test_recognition_includes_routing_data(self):
        events = self._run_and_collect("hello")
        rec = [e for e in events
               if e.get("inferred", {}).get("stage") == "recognition"]
        assert len(rec) == 1
        assert rec[0].get("intent") is not None
        assert rec[0].get("tier") is not None

    def test_approval_includes_human_feedback(self):
        events = self._run_and_collect("hello")
        appr = [e for e in events
                if e.get("inferred", {}).get("stage") == "approval"]
        assert len(appr) == 1
        assert appr[0].get("human_feedback") in ("approved", "rejected")


class TestProfileIsolation:
    """V2: Zero domain logic in cognitive_router.py."""

    def test_no_domain_terms_in_cognitive_router(self):
        """Check cognitive_router.py for hardcoded domain terms per V2."""
        domain_terms = [
            "calendar_schedule", "mcp_calendar", "google_calendar",
            "content_draft", "lessons",
        ]
        content = Path("engine/cognitive_router.py").read_text(encoding="utf-8")
        for term in domain_terms:
            assert term not in content, \
                f"Domain term '{term}' still in cognitive_router.py"

    def test_clarification_resolves_to_valid_intents(self):
        from engine.profile import set_profile
        from engine.cognitive_router import (
            get_clarification_options, resolve_clarification,
            get_router, reset_router
        )
        for profile in ["reference", "coach_demo"]:
            set_profile(profile)
            reset_router()
            router = get_router()
            opts = get_clarification_options()
            for choice in opts.keys():
                result = resolve_clarification(choice, "test")
                if result.intent != "general_chat":
                    assert result.intent in router.routes, \
                        f"{profile}: '{result.intent}' not in routes"


class TestClassificationAccuracy:
    """V3: Basic conversational input classifies correctly."""

    @pytest.mark.parametrize("text", [
        "hello", "hi", "my name is bob", "thanks",
        "thank you", "goodbye", "what is this",
    ])
    def test_conversational_input(self, text):
        from engine.profile import set_profile
        from engine.cognitive_router import classify_intent, reset_router
        set_profile("reference")
        reset_router()
        result = classify_intent(text)
        assert result.intent == "general_chat", \
            f"'{text}' classified as '{result.intent}'"
        assert result.confidence >= 0.5, \
            f"'{text}' confidence {result.confidence} too low"


class TestNoPipelineBypasses:
    """V6: Zero input() calls outside ux.py and REPL prompt."""

    def test_no_input_in_engine_except_ux(self):
        allowed = {"ux.py"}
        for py_file in Path("engine/").glob("*.py"):
            if py_file.name in allowed:
                continue
            content = py_file.read_text(encoding="utf-8")
            for i, line in enumerate(content.split("\n")):
                if line.lstrip().startswith("#"):
                    continue
                if re.search(r'(?<!raw_)input\(', line):
                    pytest.fail(
                        f"{py_file.name}:{i+1} has input() outside ux.py"
                    )

    def test_autonomaton_single_input_call(self):
        content = Path("autonomaton.py").read_text(encoding="utf-8")
        lines = content.split("\n")
        input_lines = []
        for i, line in enumerate(lines):
            if line.lstrip().startswith("#"):
                continue
            if re.search(r'(?<!raw_)input\(', line):
                input_lines.append(i + 1)
        assert len(input_lines) <= 1, \
            f"autonomaton.py has input() on lines {input_lines}"


class TestDeclarativeClarification:
    """V8: Clarification behavior is declarative (config-driven)."""

    def test_clarification_yaml_exists_all_profiles(self):
        profiles = ["reference", "coach_demo", "blank_template"]
        for profile in profiles:
            path = Path(f"profiles/{profile}/config/clarification.yaml")
            assert path.exists(), f"Missing clarification.yaml in {profile}"

    def test_clarification_options_from_config(self):
        from engine.profile import set_profile
        from engine.cognitive_router import get_clarification_options
        set_profile("reference")
        opts = get_clarification_options()
        # Should have at least 2 options from config
        assert len(opts) >= 2


class TestTelemetryConsumer:
    """E: Glass reads telemetry, not PipelineContext."""

    def test_glass_telemetry_functions_exist(self):
        from engine.glass import read_pipeline_events, display_glass_from_telemetry
        # Functions should exist and be callable
        assert callable(read_pipeline_events)
        assert callable(display_glass_from_telemetry)

    def test_read_pipeline_events_returns_list(self):
        from engine.profile import set_profile
        set_profile("reference")
        from engine.pipeline import run_pipeline
        from engine.cognitive_router import reset_router
        reset_router()
        ctx = run_pipeline("hello", source="test")
        pid = ctx.telemetry_event["id"]

        from engine.glass import read_pipeline_events
        events = read_pipeline_events(pid)
        assert isinstance(events, list)
        assert len(events) >= 1
