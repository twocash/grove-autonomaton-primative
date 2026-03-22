"""
test_flywheel.py - Flywheel Stage 2 (DETECT) Tests

White Paper Part III S3: "Same intent pattern 3+ times in 14 days
-> surface as potential skill."

Tests validate that:
1. pattern_hash appears in completion telemetry
2. Repeated intents produce matching pattern_hashes
3. detect_patterns() surfaces candidates at threshold
4. LLM-classified intents include pattern_label in hash
5. Ratchet cache preserves pattern_label for free reuse
"""

import pytest
import json
import hashlib
from unittest.mock import patch
from tests.conftest import PIPELINE_STAGES


# =========================================================================
# Dual-Write Fixture: Memory + Disk for Flywheel Tests
# =========================================================================

@pytest.fixture
def telemetry_dual_sink(setup_reference_profile):
    """
    Captures telemetry entries to BOTH memory AND disk.

    The Flywheel reads from disk via detect_patterns(). Standard
    telemetry_sink only captures to memory. This fixture does both:
    - Memory list for test assertions
    - Real JSONL file for Flywheel to read

    Also clears telemetry before each test for isolation.
    """
    from engine.profile import get_telemetry_path

    entries = []
    telemetry_path = get_telemetry_path()

    # Clear telemetry file before test
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    with open(telemetry_path, "w", encoding="utf-8") as f:
        pass  # Truncate

    def dual_write_log_event(**kwargs):
        from engine.telemetry import create_event
        event = create_event(**kwargs)
        entries.append(event)

        # Also write to disk for Flywheel
        with open(telemetry_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

        return event

    with patch('engine.pipeline.log_event', side_effect=dual_write_log_event):
        with patch('engine.telemetry.log_event', side_effect=dual_write_log_event):
            yield entries

    # Cleanup: clear telemetry after test
    with open(telemetry_path, "w", encoding="utf-8") as f:
        pass


# =========================================================================
# Part A Tests: pattern_hash in Telemetry
# =========================================================================

class TestPatternHashInTelemetry:
    """pattern_hash must appear in completion traces."""

    def test_completion_trace_has_pattern_hash(self, telemetry_dual_sink, mock_llm):
        """Keyword-matched intent produces pattern_hash in completion trace."""
        from engine.pipeline import run_pipeline

        mock_llm.append("Hello there!")
        context = run_pipeline(raw_input="hello", source="test")

        # Find completion trace (stage: execution)
        completion = next(
            (e for e in telemetry_dual_sink
             if e.get("inferred", {}).get("stage") == "execution"
             and e.get("source") == "test"),
            None
        )

        assert completion is not None, "Completion trace must exist"
        assert "pattern_hash" in completion, \
            f"Completion trace must include pattern_hash. Keys: {list(completion.keys())}"
        assert len(completion["pattern_hash"]) == 12, \
            f"pattern_hash should be 12 chars, got {len(completion['pattern_hash'])}"

    def test_same_intent_produces_same_hash(self, telemetry_dual_sink, mock_llm):
        """Different inputs matching the same intent produce the same pattern_hash."""
        from engine.pipeline import run_pipeline

        mock_llm.append("Hi!")
        mock_llm.append("Hey there!")
        run_pipeline(raw_input="hello", source="test")
        run_pipeline(raw_input="hey", source="test")

        completions = [
            e for e in telemetry_dual_sink
            if e.get("inferred", {}).get("stage") == "execution"
            and e.get("source") == "test"
        ]

        assert len(completions) == 2, f"Expected 2 completions, got {len(completions)}"
        assert completions[0]["pattern_hash"] == completions[1]["pattern_hash"], \
            "Same intent (general_chat) should produce same pattern_hash"

    def test_different_intents_produce_different_hashes(self, telemetry_dual_sink, mock_llm):
        """Different intents produce different pattern_hashes."""
        from engine.pipeline import run_pipeline

        mock_llm.append("Hi!")  # for general_chat
        run_pipeline(raw_input="hello", source="test")
        run_pipeline(raw_input="dock status", source="test")

        completions = [
            e for e in telemetry_dual_sink
            if e.get("inferred", {}).get("stage") == "execution"
            and e.get("source") == "test"
        ]

        assert len(completions) == 2, f"Expected 2 completions, got {len(completions)}"
        assert completions[0]["pattern_hash"] != completions[1]["pattern_hash"], \
            "Different intents should produce different pattern_hashes"

    def test_pattern_hash_is_deterministic(self, telemetry_dual_sink, mock_llm):
        """Same intent:domain always produces the same hash."""
        import hashlib

        mock_llm.append("Response")
        from engine.pipeline import run_pipeline
        run_pipeline(raw_input="hello", source="test")

        completion = next(
            (e for e in telemetry_dual_sink
             if e.get("inferred", {}).get("stage") == "execution"),
            None
        )

        # general_chat:system should be the pattern
        expected = hashlib.sha256("general_chat:system".encode()).hexdigest()[:12]
        assert completion["pattern_hash"] == expected, \
            f"Expected {expected}, got {completion['pattern_hash']}"


# =========================================================================
# Part B Tests: pattern_label from LLM
# =========================================================================

class TestPatternLabelFromLLM:
    """LLM classification enriches pattern_hash via pattern_label."""

    def test_llm_classification_includes_pattern_label(
        self, telemetry_dual_sink, mock_ux_input, mock_llm
    ):
        """When LLM classifies, pattern_label flows into cache entry."""
        from engine.pipeline import run_pipeline
        from engine.profile import get_config_dir
        import yaml

        mock_ux_input.append("1")  # Consent to LLM
        mock_llm.append(json.dumps({
            "intent": "explain_system",
            "confidence": 0.85,
            "reasoning": "asking about compliance",
            "intent_type": "informational",
            "action_required": False,
            "pattern_label": "compliance.data_residency"
        }))
        mock_llm.append("Data residency explanation.")

        run_pipeline(
            raw_input="What about enterprise data residency requirements?",
            source="test"
        )

        # Check that cache entry includes pattern_label
        cache_path = get_config_dir() / "pattern_cache.yaml"
        assert cache_path.exists(), "Cache file should exist"

        with open(cache_path, "r") as f:
            data = yaml.safe_load(f) or {}

        cache = data.get("cache", {})
        entry = None
        for v in cache.values():
            if "data residency" in v.get("original_input", "").lower():
                entry = v
                break

        assert entry is not None, "Cache entry should exist for test input"
        assert entry.get("pattern_label") == "compliance.data_residency", \
            f"Cache should store pattern_label, got: {entry.get('pattern_label')}"

    def test_pattern_hash_uses_label_when_available(
        self, telemetry_dual_sink, mock_ux_input, mock_llm
    ):
        """pattern_hash should use pattern_label (granular) over intent:domain (coarse)."""
        from engine.pipeline import run_pipeline

        mock_ux_input.append("1")
        mock_llm.append(json.dumps({
            "intent": "explain_system",
            "confidence": 0.85,
            "reasoning": "asking about compliance",
            "intent_type": "informational",
            "action_required": False,
            "pattern_label": "compliance.data_residency"
        }))
        mock_llm.append("Data residency explanation.")

        run_pipeline(
            raw_input="What about enterprise data residency requirements?",
            source="test"
        )

        completion = next(
            (e for e in telemetry_dual_sink
             if e.get("inferred", {}).get("stage") == "execution"
             and e.get("source") == "test"),
            None
        )

        assert completion is not None
        expected_hash = hashlib.sha256(
            "compliance.data_residency".encode()
        ).hexdigest()[:12]
        assert completion["pattern_hash"] == expected_hash, \
            f"pattern_hash should derive from pattern_label, got {completion['pattern_hash']}"


# =========================================================================
# Part C Tests: Flywheel Detection
# =========================================================================

class TestFlywheelDetection:
    """Flywheel Stage 2: DETECT surfaces recurring patterns."""

    def test_detect_returns_empty_with_no_telemetry(self, setup_reference_profile):
        """No telemetry -> no patterns."""
        from engine.flywheel import detect_patterns
        from engine.profile import get_telemetry_path

        # Ensure clean telemetry
        telemetry_path = get_telemetry_path()
        telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(telemetry_path, "w") as f:
            pass

        patterns = detect_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) == 0

    def test_detect_surfaces_candidate(self, telemetry_dual_sink, mock_llm):
        """3+ occurrences of the same pattern -> candidate.

        THIS TEST IS THE FLYWHEEL'S PROOF OF LIFE.
        It validates that detect_patterns() reads REAL telemetry from disk.
        """
        from engine.pipeline import run_pipeline
        from engine.flywheel import detect_patterns

        # Run the pipeline 3 times with matching intents (all hit general_chat)
        for greeting in ["hello", "hi", "hey"]:
            mock_llm.append(f"Response to {greeting}")
            run_pipeline(raw_input=greeting, source="test")

        # detect_patterns reads from disk - this is the real test
        patterns = detect_patterns(min_count=3)
        candidates = [p for p in patterns if p["is_candidate"]]

        assert len(candidates) >= 1, \
            f"Should have at least 1 candidate pattern. Got patterns: {patterns}"

        # Verify the candidate is general_chat
        chat_candidate = next(
            (p for p in candidates if "general_chat" in p["intent"]),
            None
        )
        assert chat_candidate is not None, \
            f"general_chat should be a candidate. Patterns: {patterns}"
        assert chat_candidate["count"] >= 3, \
            f"general_chat should have 3+ occurrences, got {chat_candidate['count']}"

    def test_detect_respects_time_window(self, telemetry_dual_sink, mock_llm):
        """Patterns outside the window are not counted."""
        from engine.flywheel import detect_patterns

        # Detection with 0-day window should return nothing
        # (all events are "in the future" relative to a 0-day lookback)
        patterns = detect_patterns(days=0)
        candidates = [p for p in patterns if p["is_candidate"]]
        assert len(candidates) == 0

    def test_detect_respects_min_count(self, telemetry_dual_sink, mock_llm):
        """Patterns below min_count are not candidates."""
        from engine.pipeline import run_pipeline
        from engine.flywheel import detect_patterns

        # Run only twice
        mock_llm.append("Response 1")
        mock_llm.append("Response 2")
        run_pipeline(raw_input="hello", source="test")
        run_pipeline(raw_input="hi", source="test")

        # With min_count=3, should have no candidates
        patterns = detect_patterns(min_count=3)
        candidates = [p for p in patterns if p["is_candidate"]]
        assert len(candidates) == 0, \
            f"2 occurrences should not be a candidate at min_count=3. Got: {candidates}"

        # With min_count=2, should have a candidate
        patterns = detect_patterns(min_count=2)
        candidates = [p for p in patterns if p["is_candidate"]]
        assert len(candidates) >= 1, \
            f"2 occurrences should be a candidate at min_count=2. Got: {patterns}"


# =========================================================================
# Part E Tests: show_patterns Route
# =========================================================================

class TestShowPatternsRoute:
    """The show patterns route is wired and functional."""

    def test_show_patterns_keyword_match(self, mock_llm):
        """'show patterns' matches the route."""
        from engine.cognitive_router import classify_intent

        result = classify_intent("show patterns")
        assert result.intent == "show_patterns", \
            f"Expected show_patterns intent, got {result.intent}"
        assert result.zone == "green", "show_patterns should be green zone"
        assert result.handler == "show_patterns"

    def test_show_patterns_runs_pipeline(self, telemetry_dual_sink, mock_llm):
        """show patterns runs through the full pipeline."""
        from engine.pipeline import run_pipeline

        context = run_pipeline(raw_input="show patterns", source="test")
        assert context.executed, "show patterns should execute"
        assert context.intent == "show_patterns"

    def test_show_patterns_output_format(self, telemetry_dual_sink, mock_llm):
        """show patterns returns proper DispatchResult structure."""
        from engine.pipeline import run_pipeline
        from engine.flywheel import detect_patterns

        # Run some interactions first
        mock_llm.append("Response 1")
        mock_llm.append("Response 2")
        mock_llm.append("Response 3")
        run_pipeline(raw_input="hello", source="test")
        run_pipeline(raw_input="hi", source="test")
        run_pipeline(raw_input="hey", source="test")

        # Now show patterns
        context = run_pipeline(raw_input="show patterns", source="test")

        # Check dispatch result (stored in context.result)
        assert context.executed
        assert context.result is not None
        result_data = context.result.get("data", {})
        assert result_data.get("type") == "flywheel_patterns"
        assert "patterns" in result_data
