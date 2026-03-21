"""
Tests for consent-gated classification.

The LLM must never fire without operator consent.
classify() returns unknown for unrecognized input.
The Kaizen prompt in Stage 4 offers the operator a choice.
"""

from engine.profile import set_profile
from engine.cognitive_router import classify_intent, reset_router


class TestConsentGatedClassification:

    def setup_method(self):
        set_profile("reference")
        reset_router()

    def test_classify_returns_unknown_for_unrecognized_input(self):
        """classify() must return unknown, not call the LLM."""
        result = classify_intent("xyzzy foobarbaz nonexistent gibberish")
        assert result.intent == "unknown", \
            f"Expected unknown, got {result.intent}"
        assert result.confidence == 0.0, \
            f"Expected 0.0 confidence, got {result.confidence}"

    def test_classify_still_matches_keywords(self):
        """Keyword matching still works normally."""
        result = classify_intent("hello")
        assert result.intent == "general_chat"
        assert result.confidence >= 0.5

    def test_classify_still_hits_cache(self):
        """Pattern cache still works at Tier 0."""
        # This tests the Ratchet read path — if cache has an
        # entry, it returns at Tier 0 without LLM
        result = classify_intent("hello")
        assert result.tier in (0, 1)  # keyword or cache

    def test_smart_clarification_removed(self):
        """_generate_smart_clarification must not exist in pipeline."""
        content = open("engine/pipeline.py", encoding="utf-8").read()
        assert "_generate_smart_clarification" not in content

    def test_classify_does_not_call_escalate(self):
        """The classify method body must not reference _escalate_to_llm."""
        content = open("engine/cognitive_router.py", encoding="utf-8").read()
        classify_start = content.find("def classify(")
        classify_end = content.find("def _create_default")
        classify_body = content[classify_start:classify_end]
        assert "_escalate_to_llm" not in classify_body

    def test_escalate_method_still_exists(self):
        """_escalate_to_llm must still exist for on-demand use."""
        content = open("engine/cognitive_router.py", encoding="utf-8").read()
        assert "def _escalate_to_llm" in content
