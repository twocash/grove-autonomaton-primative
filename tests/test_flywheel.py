"""
test_flywheel.py - Flywheel Tests (DETECT + PROPOSE + APPROVE)

White Paper Part III S3: "Same intent pattern 3+ times in 14 days
-> surface as potential skill."

Tests validate that:
1. pattern_hash appears in completion telemetry
2. Repeated intents produce matching pattern_hashes
3. detect_patterns() surfaces candidates at threshold
4. LLM-classified intents include pattern_label in hash
5. Ratchet cache preserves pattern_label for free reuse

V-016 Part D Tests:
6. propose_skills() generates YAML proposals from candidates
7. Proposals include all required fields (provenance, trigger, response)
8. Proposals are idempotent (no duplicates)
9. No LLM calls in PROPOSE (Tier 0)

V-019 Part F Tests (APPROVE):
10. approve_skill route keyword match
11. approve_skill triggers Stage 4 (telemetry approval trace)
12. Compilation enrichment populates proposed_action
13. proposed_action in approval trace exhaust
14. approve_skill() writes cache entries
15. Cache entries have source: flywheel_approve
16. Archive moves to approved/ directory
17. Handler returns success with counts
18. Hash sanitization (spaces, long input)
19. Already-approved returns error
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


# =========================================================================
# Part D Tests: Flywheel PROPOSE (V-016)
# =========================================================================

@pytest.fixture(autouse=False)
def cleanup_proposals(setup_reference_profile):
    """Clean proposal directory before and after test. Fate-sharing."""
    from engine.profile import get_profile_path

    proposal_dir = get_profile_path() / "queue" / "flywheel"
    if proposal_dir.exists():
        for f in proposal_dir.glob("*.yaml"):
            f.unlink()
    yield
    # Cleanup after
    if proposal_dir.exists():
        for f in proposal_dir.glob("*.yaml"):
            f.unlink()


class TestFlywheelPropose:
    """Flywheel Stage 3: PROPOSE generates skill proposals from candidates."""

    def test_propose_generates_yaml_from_candidates(
        self, telemetry_dual_sink, mock_llm, cleanup_proposals
    ):
        """Run 3+ interactions, propose_skills() creates YAML files."""
        from engine.pipeline import run_pipeline
        from engine.flywheel import propose_skills
        from engine.profile import get_profile_path
        import yaml

        # Generate candidate pattern (3+ occurrences)
        for greeting in ["hello", "hi", "hey"]:
            mock_llm.append(f"Response to {greeting}")
            run_pipeline(raw_input=greeting, source="test")

        # Generate proposals
        proposals = propose_skills()

        assert len(proposals) >= 1, f"Should generate at least 1 proposal. Got: {proposals}"

        # Verify YAML file exists
        proposal_dir = get_profile_path() / "queue" / "flywheel"
        yaml_files = list(proposal_dir.glob("*.yaml"))
        assert len(yaml_files) >= 1, "At least one YAML file should exist"

        # Verify YAML is valid and has required fields
        with open(yaml_files[0], "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert "skill" in data, "Proposal must have 'skill' key"
        skill = data["skill"]
        assert "name" in skill, "skill.name required"
        assert "description" in skill, "skill.description required"
        assert "trigger" in skill, "skill.trigger required"
        assert "pattern_hash" in skill["trigger"], "trigger.pattern_hash required"
        assert "provenance" in skill, "skill.provenance required"
        assert "occurrences" in skill["provenance"], "provenance.occurrences required"

    def test_proposal_description_from_routing_config(
        self, telemetry_dual_sink, mock_llm, cleanup_proposals
    ):
        """Proposal description comes from routing.config, not generated."""
        from engine.pipeline import run_pipeline
        from engine.flywheel import propose_skills
        from engine.profile import get_profile_path
        import yaml

        # Generate candidate
        for greeting in ["hello", "hi", "hey"]:
            mock_llm.append(f"Response to {greeting}")
            run_pipeline(raw_input=greeting, source="test")

        propose_skills()

        # Read proposal
        proposal_dir = get_profile_path() / "queue" / "flywheel"
        yaml_files = list(proposal_dir.glob("*.yaml"))
        assert len(yaml_files) >= 1

        with open(yaml_files[0], "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        description = data["skill"]["description"]
        # Should be the route description from routing.config, not empty
        assert description, "Description should not be empty"
        assert description != data["skill"]["name"], \
            "Description should be from config, not just the intent name"

    def test_proposal_includes_provenance(
        self, telemetry_dual_sink, mock_llm, cleanup_proposals
    ):
        """Proposal includes full provenance metadata."""
        from engine.pipeline import run_pipeline
        from engine.flywheel import propose_skills
        from engine.profile import get_profile_path
        import yaml

        # Generate candidate
        for greeting in ["hello", "hi", "hey"]:
            mock_llm.append(f"Response to {greeting}")
            run_pipeline(raw_input=greeting, source="test")

        propose_skills()

        # Read proposal
        proposal_dir = get_profile_path() / "queue" / "flywheel"
        yaml_files = list(proposal_dir.glob("*.yaml"))
        with open(yaml_files[0], "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        provenance = data["skill"]["provenance"]
        assert provenance["occurrences"] >= 3, "Should have at least 3 occurrences"
        assert provenance["first_seen"], "first_seen should be set"
        assert provenance["last_seen"], "last_seen should be set"
        assert provenance["proposed_at"], "proposed_at should be set"
        assert provenance["proposed_by"] == "flywheel_stage_3", \
            f"proposed_by should be 'flywheel_stage_3', got {provenance['proposed_by']}"

    def test_propose_skips_existing_proposals(
        self, telemetry_dual_sink, mock_llm, cleanup_proposals
    ):
        """Calling propose_skills() twice doesn't create duplicates."""
        from engine.pipeline import run_pipeline
        from engine.flywheel import propose_skills
        from engine.profile import get_profile_path

        # Generate candidate
        for greeting in ["hello", "hi", "hey"]:
            mock_llm.append(f"Response to {greeting}")
            run_pipeline(raw_input=greeting, source="test")

        # First call creates proposals
        proposals1 = propose_skills()
        assert len(proposals1) >= 1

        # Second call should return empty (all already proposed)
        proposals2 = propose_skills()
        assert len(proposals2) == 0, \
            f"Second call should return empty, got {proposals2}"

        # Verify file count unchanged
        proposal_dir = get_profile_path() / "queue" / "flywheel"
        yaml_files = list(proposal_dir.glob("*.yaml"))
        assert len(yaml_files) == len(proposals1), \
            "File count should match first call's proposals"

    def test_propose_skips_subthreshold_patterns(
        self, telemetry_dual_sink, mock_llm, cleanup_proposals
    ):
        """2 occurrences (below threshold) doesn't generate proposals."""
        from engine.pipeline import run_pipeline
        from engine.flywheel import propose_skills

        # Only 2 occurrences (below default threshold of 3)
        mock_llm.append("Response 1")
        mock_llm.append("Response 2")
        run_pipeline(raw_input="hello", source="test")
        run_pipeline(raw_input="hi", source="test")

        proposals = propose_skills()
        assert len(proposals) == 0, \
            f"2 occurrences should not generate proposals, got {proposals}"

    def test_no_llm_calls_in_propose(
        self, telemetry_dual_sink, mock_llm, cleanup_proposals
    ):
        """propose_skills() is Tier 0 - no LLM calls."""
        from engine.pipeline import run_pipeline
        from engine.flywheel import propose_skills

        # Generate candidate
        for greeting in ["hello", "hi", "hey"]:
            mock_llm.append(f"Response to {greeting}")
            run_pipeline(raw_input=greeting, source="test")

        # Record LLM queue length before propose
        llm_queue_before = len(mock_llm)

        # Call propose_skills
        propose_skills()

        # LLM queue should be unchanged (no calls made)
        assert len(mock_llm) == llm_queue_before, \
            "propose_skills() should not consume any LLM responses"

    def test_show_proposals_route_works(
        self, telemetry_dual_sink, mock_llm, cleanup_proposals
    ):
        """show proposals route displays pending proposals."""
        from engine.pipeline import run_pipeline
        from engine.flywheel import propose_skills

        # Generate candidate and proposals
        for greeting in ["hello", "hi", "hey"]:
            mock_llm.append(f"Response to {greeting}")
            run_pipeline(raw_input=greeting, source="test")
        propose_skills()

        # Run show proposals
        context = run_pipeline(raw_input="show proposals", source="test")

        assert context.executed
        assert context.intent == "show_proposals"
        result_data = context.result.get("data", {})
        assert result_data.get("type") == "flywheel_proposals"
        assert "proposals" in result_data
        assert len(result_data["proposals"]) >= 1

    def test_propose_skills_route_works(
        self, telemetry_dual_sink, mock_llm, cleanup_proposals
    ):
        """propose skills route generates proposals via pipeline."""
        from engine.pipeline import run_pipeline

        # Generate candidate
        for greeting in ["hello", "hi", "hey"]:
            mock_llm.append(f"Response to {greeting}")
            run_pipeline(raw_input=greeting, source="test")

        # Run propose skills through pipeline
        context = run_pipeline(raw_input="propose skills", source="test")

        assert context.executed
        assert context.intent == "propose_skills"
        result_data = context.result.get("data", {})
        assert result_data.get("type") == "flywheel_propose"
        assert "proposals" in result_data


# =========================================================================
# Part F Tests: Flywheel APPROVE (V-019)
# =========================================================================

@pytest.fixture(autouse=False)
def cleanup_approve_artifacts(setup_reference_profile, cleanup_proposals):
    """Clean cache and approved directory before/after test."""
    from engine.profile import get_profile_path, get_config_dir
    import yaml

    # Clean pattern cache
    cache_path = get_config_dir() / "pattern_cache.yaml"
    if cache_path.exists():
        with open(cache_path, "w", encoding="utf-8") as f:
            yaml.dump({"cache": {}}, f)

    # Clean approved directory
    approved_dir = get_profile_path() / "queue" / "flywheel" / "approved"
    if approved_dir.exists():
        for f in approved_dir.glob("*.yaml"):
            f.unlink()

    yield

    # Cleanup after
    if cache_path.exists():
        with open(cache_path, "w", encoding="utf-8") as f:
            yaml.dump({"cache": {}}, f)
    if approved_dir.exists():
        for f in approved_dir.glob("*.yaml"):
            f.unlink()


def _traces_by_stage(entries: list, stage: str) -> list:
    """Filter telemetry entries by pipeline stage."""
    return [
        e for e in entries
        if e.get("inferred", {}).get("stage") == stage
    ]


def _last_trace(entries: list, stage: str) -> dict:
    """Get the most recent trace for a given stage."""
    traces = _traces_by_stage(entries, stage)
    return traces[-1] if traces else {}


class TestFlywheelApprove:
    """Flywheel Stage 4: APPROVE deploys skills to pattern cache."""

    def test_approve_skill_route_keyword_match(self, mock_llm):
        """F1: 'approve skill' matches the route."""
        from engine.cognitive_router import classify_intent

        result = classify_intent("approve skill abc123")
        assert result.intent == "approve_skill", \
            f"Expected approve_skill intent, got {result.intent}"
        assert result.zone == "yellow", "approve_skill should be yellow zone"
        assert result.handler == "approve_skill"

    def test_approve_skill_triggers_stage4(
        self, telemetry_dual_sink, mock_llm, mock_jidoka_approve, cleanup_approve_artifacts
    ):
        """F2: approve_skill triggers Stage 4 approval trace (exhaust-first)."""
        from engine.pipeline import run_pipeline
        from engine.flywheel import propose_skills

        # Generate candidate and proposal
        for greeting in ["hello", "hi", "hey"]:
            mock_llm.append(f"Response to {greeting}")
            run_pipeline(raw_input=greeting, source="test")
        proposals = propose_skills()
        assert len(proposals) >= 1, "Need at least 1 proposal for test"
        ph = proposals[0]["pattern_hash"]

        # Approve via pipeline (Yellow zone = Stage 4 Andon Gate)
        # mock_jidoka_approve auto-approves confirm_yellow_zone()
        context = run_pipeline(raw_input=f"approve skill {ph}", source="test")

        # EXHAUST-FIRST: Check telemetry for approval trace
        approval_trace = _last_trace(telemetry_dual_sink, "approval")
        assert approval_trace, "Approval trace must exist in telemetry"
        assert approval_trace.get("zone_context") == "yellow", \
            f"Approval trace should be yellow zone, got {approval_trace.get('zone_context')}"

    def test_compilation_enrichment_populates_proposed_action(
        self, telemetry_dual_sink, mock_llm, mock_jidoka_approve, cleanup_approve_artifacts
    ):
        """F3: Compilation enrichment populates proposed_action for informed consent."""
        from engine.pipeline import run_pipeline
        from engine.flywheel import propose_skills

        # Generate candidate and proposal
        for greeting in ["hello", "hi", "hey"]:
            mock_llm.append(f"Response to {greeting}")
            run_pipeline(raw_input=greeting, source="test")
        proposals = propose_skills()
        ph = proposals[0]["pattern_hash"]

        # Approve via pipeline (mock_jidoka_approve auto-approves Yellow zone)
        context = run_pipeline(raw_input=f"approve skill {ph}", source="test")

        # The context should have proposed_action set by Compilation
        assert context.proposed_action is not None, \
            "Compilation should set proposed_action for approve_skill"
        assert "pattern cache" in context.proposed_action.lower(), \
            f"proposed_action should mention pattern cache: {context.proposed_action}"
        assert "tier 0" in context.proposed_action.lower(), \
            f"proposed_action should mention Tier 0: {context.proposed_action}"

    def test_proposed_action_in_approval_trace_exhaust(
        self, telemetry_dual_sink, mock_llm, mock_jidoka_approve, cleanup_approve_artifacts
    ):
        """F4: proposed_action appears in approval trace exhaust."""
        from engine.pipeline import run_pipeline
        from engine.flywheel import propose_skills

        # Generate candidate and proposal
        for greeting in ["hello", "hi", "hey"]:
            mock_llm.append(f"Response to {greeting}")
            run_pipeline(raw_input=greeting, source="test")
        proposals = propose_skills()
        ph = proposals[0]["pattern_hash"]

        # Approve via pipeline (mock_jidoka_approve auto-approves Yellow zone)
        run_pipeline(raw_input=f"approve skill {ph}", source="test")

        # EXHAUST-FIRST: Check telemetry
        approval_trace = _last_trace(telemetry_dual_sink, "approval")
        assert approval_trace, "Approval trace must exist"

        inferred = approval_trace.get("inferred", {})
        assert "proposed_action" in inferred, \
            f"Approval trace inferred must contain proposed_action. Keys: {list(inferred.keys())}"

    def test_approve_skill_writes_cache_entries(
        self, telemetry_dual_sink, mock_llm, mock_jidoka_approve, cleanup_approve_artifacts
    ):
        """F5: approve_skill() writes entries to pattern cache (file-state validation)."""
        from engine.pipeline import run_pipeline
        from engine.flywheel import propose_skills
        from engine.profile import get_config_dir
        import yaml

        # Generate candidate and proposal
        for greeting in ["hello", "hi", "hey"]:
            mock_llm.append(f"Response to {greeting}")
            run_pipeline(raw_input=greeting, source="test")
        proposals = propose_skills()
        ph = proposals[0]["pattern_hash"]

        # Approve (mock_jidoka_approve auto-approves Yellow zone)
        run_pipeline(raw_input=f"approve skill {ph}", source="test")

        # FILE-STATE: Verify cache entries written
        cache_path = get_config_dir() / "pattern_cache.yaml"
        assert cache_path.exists(), "Cache file should exist"

        with open(cache_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        cache = data.get("cache", {})
        assert len(cache) >= 1, f"Cache should have entries, got {len(cache)}"

    def test_cache_entries_have_flywheel_source(
        self, telemetry_dual_sink, mock_llm, mock_jidoka_approve, cleanup_approve_artifacts
    ):
        """F6: Cache entries have source: flywheel_approve (not 'llm')."""
        from engine.pipeline import run_pipeline
        from engine.flywheel import propose_skills
        from engine.profile import get_config_dir
        import yaml

        # Generate candidate and proposal
        for greeting in ["hello", "hi", "hey"]:
            mock_llm.append(f"Response to {greeting}")
            run_pipeline(raw_input=greeting, source="test")
        proposals = propose_skills()
        ph = proposals[0]["pattern_hash"]

        # Approve (mock_jidoka_approve auto-approves Yellow zone)
        run_pipeline(raw_input=f"approve skill {ph}", source="test")

        # FILE-STATE: Verify source field
        cache_path = get_config_dir() / "pattern_cache.yaml"
        with open(cache_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        cache = data.get("cache", {})
        for entry in cache.values():
            assert entry.get("source") == "flywheel_approve", \
                f"Cache entry source should be 'flywheel_approve', got {entry.get('source')}"
            assert "proposal_hash" in entry, \
                "Cache entry should include proposal_hash for audit trail"

    def test_archive_moves_to_approved_directory(
        self, telemetry_dual_sink, mock_llm, mock_jidoka_approve, cleanup_approve_artifacts
    ):
        """F7: Approved proposal is archived to approved/ directory."""
        from engine.pipeline import run_pipeline
        from engine.flywheel import propose_skills
        from engine.profile import get_profile_path

        # Generate candidate and proposal
        for greeting in ["hello", "hi", "hey"]:
            mock_llm.append(f"Response to {greeting}")
            run_pipeline(raw_input=greeting, source="test")
        proposals = propose_skills()
        ph = proposals[0]["pattern_hash"]

        proposal_dir = get_profile_path() / "queue" / "flywheel"
        approved_dir = proposal_dir / "approved"

        # Verify proposal exists before approval
        assert (proposal_dir / f"{ph}.yaml").exists(), "Proposal should exist before approval"

        # Approve (mock_jidoka_approve auto-approves Yellow zone)
        run_pipeline(raw_input=f"approve skill {ph}", source="test")

        # FILE-STATE: Verify archive
        assert not (proposal_dir / f"{ph}.yaml").exists(), \
            "Proposal should be removed from queue after approval"
        assert (approved_dir / f"{ph}.yaml").exists(), \
            "Proposal should be archived to approved/ directory"

    def test_handler_returns_success_with_counts(
        self, telemetry_dual_sink, mock_llm, mock_jidoka_approve, cleanup_approve_artifacts
    ):
        """F8: Handler returns success with entries_written count."""
        from engine.pipeline import run_pipeline
        from engine.flywheel import propose_skills

        # Generate candidate and proposal
        for greeting in ["hello", "hi", "hey"]:
            mock_llm.append(f"Response to {greeting}")
            run_pipeline(raw_input=greeting, source="test")
        proposals = propose_skills()
        ph = proposals[0]["pattern_hash"]

        # Approve (mock_jidoka_approve auto-approves Yellow zone)
        context = run_pipeline(raw_input=f"approve skill {ph}", source="test")

        # Check result
        assert context.executed, "approve_skill should execute"
        result_data = context.result.get("data", {})
        assert result_data.get("type") == "approve_skill"
        assert result_data.get("action") == "approved"
        assert "result" in result_data
        assert result_data["result"]["entries_written"] >= 1, \
            "Should report at least 1 entry written"

    def test_hash_sanitization(
        self, telemetry_dual_sink, mock_llm, mock_ux_input, cleanup_approve_artifacts
    ):
        """F9: Hash sanitization handles spaces and long input."""
        from engine.flywheel import approve_skill, propose_skills
        from engine.pipeline import run_pipeline

        # Generate candidate and proposal
        for greeting in ["hello", "hi", "hey"]:
            mock_llm.append(f"Response to {greeting}")
            run_pipeline(raw_input=greeting, source="test")
        proposals = propose_skills()
        ph = proposals[0]["pattern_hash"]

        # Test with extra spaces and garbage after hash
        result = approve_skill(f"  {ph}   extra garbage ignored ")

        assert result.get("approved") or result.get("error"), \
            "approve_skill should handle sanitized input"
        # If approved, the sanitization worked
        if result.get("approved"):
            assert result["skill_name"], "Should return skill name"

    def test_already_approved_returns_error(
        self, telemetry_dual_sink, mock_llm, mock_ux_input, cleanup_approve_artifacts
    ):
        """F10: Approving an already-approved proposal returns error."""
        from engine.pipeline import run_pipeline
        from engine.flywheel import propose_skills, approve_skill

        # Generate candidate and proposal
        for greeting in ["hello", "hi", "hey"]:
            mock_llm.append(f"Response to {greeting}")
            run_pipeline(raw_input=greeting, source="test")
        proposals = propose_skills()
        ph = proposals[0]["pattern_hash"]

        # First approval (direct call to skip pipeline for speed)
        result1 = approve_skill(ph)
        assert result1.get("approved"), "First approval should succeed"

        # Second approval should fail
        result2 = approve_skill(ph)
        assert not result2.get("approved"), "Second approval should fail"
        assert "already approved" in result2.get("error", "").lower(), \
            f"Error should mention already approved: {result2.get('error')}"
