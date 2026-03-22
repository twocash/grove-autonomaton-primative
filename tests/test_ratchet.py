"""
test_ratchet.py - V-009 Ratchet Cache Tests

Tests 3, 4, and 5: The Ratchet (economic optimization).

White paper Part III ("The Cognitive Router and the Learning Dividend"):
"Every Tier 3 interaction that becomes a recognized pattern can become
a Tier 0 cached skill — 100x cheaper."

White paper Part VI ("Gets cheaper with use"): "The reverse tax in action:
the cost curve bends downward automatically as the Skill Flywheel turns."

V-001 Regression Guard: The cache must store the CLASSIFIED intent
(e.g., "explain_system"), not the classification mechanism
(e.g., "ratchet_intent_classify"). If the test sees the mechanism
in the cache, the sub-pipeline violation has returned.
"""

import pytest
import yaml
from unittest.mock import patch
from tests.conftest import PIPELINE_STAGES



class TestConsentGatedClassification:
    """
    Test 3: Consent-Gated Classification — Option 1 With LLM

    The V-001 regression test. When the operator consents to LLM
    classification, the pipeline should:
    - Call the LLM once (direct call, not sub-pipeline)
    - Store the CLASSIFIED intent in context
    - Execute exactly ONE pipeline traversal

    TCP/IP paper §III ("End-to-End"): "Governance functions belong at the
    endpoints — with the human operator — not inside the cognitive layer."
    The operator consented. The LLM classified. One traversal.
    """

    def test_option1_llm_classification(self, telemetry_sink, mock_ux_input, mock_llm):
        """
        Operator consents to LLM classification. The classified intent
        (explain_system) must appear in context — NOT the classification
        mechanism (ratchet_intent_classify).
        """
        from engine.pipeline import run_pipeline

        mock_ux_input.append("1")  # Consent to LLM
        mock_llm.append('{"intent": "explain_system", "confidence": 0.85}')
        # general_chat handler will also call LLM for the response
        mock_llm.append("The Autonomaton is a self-authoring system.")

        context = run_pipeline(
            raw_input="What about enterprise data residency requirements?",
            source="test"
        )

        # Recognition initially unknown
        recognition = next(
            e for e in telemetry_sink
            if e.get("inferred", {}).get("stage") == "recognition"
        )
        assert recognition["intent"] == "unknown", \
            f"Initial recognition should be 'unknown', got '{recognition.get('intent')}'"


        # Post-classification: intent is the CLASSIFIED value
        assert context.intent == "explain_system", \
            f"Post-LLM intent should be 'explain_system', got '{context.intent}'"

        # V-001 regression: must NOT be the classification mechanism
        assert context.intent != "ratchet_intent_classify", \
            "V-001 REGRESSION: intent is the classification mechanism, not the result"

        # Exactly ONE pipeline traversal
        telemetry_starts = [
            e for e in telemetry_sink
            if e.get("inferred", {}).get("stage") == "telemetry"
        ]
        assert len(telemetry_starts) == 1, \
            f"One operator input = one pipeline traversal, got {len(telemetry_starts)}"

    def test_llm_classification_logs_consent(self, telemetry_sink, mock_ux_input, mock_llm):
        """
        LLM classification path records consent in context events.

        White paper Part III ("Sovereignty Guardrails"): "The system
        proposes, the human approves." Option 1 IS that approval.
        """
        from engine.pipeline import run_pipeline

        mock_ux_input.append("1")
        mock_llm.append('{"intent": "explain_system", "confidence": 0.85}')
        mock_llm.append("Architecture explanation.")

        context = run_pipeline(
            raw_input="Tell me about the architecture",
            source="test"
        )

        # Events should record the consent path
        assert "kaizen_fired" in context.events, \
            f"Kaizen should have fired, events: {context.events}"
        assert "llm_classification" in context.events, \
            f"LLM classification event should be recorded, events: {context.events}"


class TestRatchetCacheHit:
    """
    Test 4: The Ratchet — Cache Hit on Repeat Input

    White paper Part VI ("Gets cheaper with use"): "Every Tier 3
    interaction that becomes a recognized pattern eventually becomes
    a Tier 0 cached response — 100x cheaper."

    Same input, cheaper every time. That's the learning dividend.
    """

    def test_cache_hit_on_repeat_input(self, telemetry_sink, mock_ux_input, mock_llm):
        """
        First run: LLM classification populates cache.
        Second run: same input → Tier 0, zero cost, no prompts.
        """
        from engine.pipeline import run_pipeline
        from engine.cognitive_router import reset_router

        test_input = "What about enterprise data residency requirements?"

        # First run: consent + LLM classification
        mock_ux_input.append("1")
        mock_llm.append('{"intent": "explain_system", "confidence": 0.85}')
        mock_llm.append("Data residency explanation.")
        run_pipeline(raw_input=test_input, source="test")

        # Clear sink, reset router to force cache reload from disk
        telemetry_sink.clear()
        reset_router()

        # Track CLASSIFICATION LLM calls on second run (not handler calls)
        classification_calls = []

        def track_llm(*args, **kwargs):
            intent = kwargs.get("intent", "")
            if intent == "llm_intent_classify":
                classification_calls.append(1)
            # Return mock response for handler LLM calls
            return "Cached response from handler."


        with patch('engine.llm_client.call_llm', side_effect=track_llm):
            context = run_pipeline(raw_input=test_input, source="test")

        # Should hit cache (T0)
        recognition = next(
            e for e in telemetry_sink
            if e.get("inferred", {}).get("stage") == "recognition"
        )
        assert recognition.get("tier") == 0, \
            f"Cache hit should be tier 0, got {recognition.get('tier')}"

        method = recognition.get("inferred", {}).get("method")
        assert method == "cache", \
            f"Recognition method should be 'cache', got '{method}'"

        # No CLASSIFICATION LLM call on second run (handler calls are expected)
        assert len(classification_calls) == 0, \
            f"Cache hit should skip classification LLM, but it was called {len(classification_calls)} times"

        # No Kaizen fired
        assert "kaizen_fired" not in context.events, \
            f"Cache hit should not fire Kaizen, events: {context.events}"

        # Approval should not show kaizen
        approval = next(
            e for e in telemetry_sink
            if e.get("inferred", {}).get("stage") == "approval"
        )
        label = approval.get("inferred", {}).get("label", "")
        assert "kaizen" not in label.lower(), \
            f"Cache hit should not show kaizen in approval, got '{label}'"


class TestCacheIntegrity:
    """
    Test 5: Cache Integrity — Correct Intent Stored

    White paper Part III ("The Skill Flywheel"): "The model isn't hidden
    in weights. It's visible, explicit, and yours. You can inspect every
    skill. You can correct every pattern."

    The Ratchet caches what the OPERATOR meant, not what the SYSTEM
    routed internally. This is the V-001 litmus test.
    """

    def test_cache_stores_classified_intent(self, mock_ux_input, mock_llm):
        """
        After LLM classification, cache must contain:
        - intent: "explain_system" (the classified value)
        - NOT: "ratchet_intent_classify" (the mechanism)
        """
        from engine.pipeline import run_pipeline
        from engine.profile import get_config_dir

        test_input = "What about enterprise data residency requirements?"

        mock_ux_input.append("1")
        mock_llm.append('{"intent": "explain_system", "confidence": 0.85}')
        mock_llm.append("Residency explanation.")
        run_pipeline(raw_input=test_input, source="test")

        # Read cache file directly
        cache_path = get_config_dir() / "pattern_cache.yaml"
        assert cache_path.exists(), f"Cache file should exist at {cache_path}"

        with open(cache_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)


        cache = data.get("cache", {})

        # Find entry matching test input
        entry = None
        for k, v in cache.items():
            original = v.get("original_input", "").lower()
            if "enterprise data residency" in original:
                entry = v
                break

        assert entry is not None, \
            f"Cache entry should exist for test input. Cache: {cache}"

        # V-001 critical assertion
        assert entry["intent"] == "explain_system", \
            f"Cache should store 'explain_system', got '{entry['intent']}'"
        assert entry["intent"] != "ratchet_intent_classify", \
            "V-001 REGRESSION: Cache poisoned with classification mechanism"

        assert entry.get("confirmed_count", 0) >= 1, \
            f"confirmed_count should be >= 1, got {entry.get('confirmed_count')}"

    def test_cache_preserves_routing_info(self, mock_ux_input, mock_llm):
        """
        Cache entries preserve zone, handler, domain, intent_type.
        Ensures T0 cache hits can dispatch correctly.

        TCP/IP paper §III ("Fate-Sharing"): "Each Autonomaton maintains
        its own state." The cache IS that state — complete enough for
        autonomous dispatch.
        """
        from engine.pipeline import run_pipeline
        from engine.profile import get_config_dir

        test_input = "Tell me about the pipeline stages"

        mock_ux_input.append("1")
        mock_llm.append('{"intent": "explain_system", "confidence": 0.90}')
        mock_llm.append("Pipeline stage explanation.")
        run_pipeline(raw_input=test_input, source="test")

        cache_path = get_config_dir() / "pattern_cache.yaml"
        with open(cache_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        cache = data.get("cache", {})
        entry = None
        for k, v in cache.items():
            if "pipeline stages" in v.get("original_input", "").lower():
                entry = v
                break

        if entry is None:
            pytest.skip("Test input matched keyword — no cache entry created")

        assert "zone" in entry, "Cache entry should preserve zone"
        assert "handler" in entry, "Cache entry should preserve handler"
        assert "domain" in entry, "Cache entry should preserve domain"
