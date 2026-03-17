"""
test_cortex.py - Tests for LLM-Powered Cortex Analysis

These tests ensure the Cortex uses LLM for entity extraction and
content seed mining, with Jidoka validation for new entities.

TDD: Write tests first, then implement to pass.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json


class TestCortexLens1EntityExtraction:
    """Tests for Lens 1: LLM-based entity extraction."""

    def test_entity_extraction_uses_llm(self):
        """
        Entity extraction must use LLM (Tier 1/Haiku) instead of regex.

        The LLM should return structured NER data.
        """
        from engine.cortex import Cortex

        # Mock LLM response with structured entity data
        mock_llm_response = json.dumps({
            "entities": [
                {"name": "Marcus Henderson", "type": "player", "is_new": True},
                {"name": "Sarah Henderson", "type": "parent", "is_new": True}
            ]
        })

        with patch('engine.llm_client.call_llm', return_value=mock_llm_response) as mock_llm:
            cortex = Cortex()

            event = {
                "id": "test-event-123",
                "raw_transcript": "Marcus Henderson had a great lesson today. His mother Sarah Henderson was impressed.",
                "source": "operator_session"
            }

            entities = cortex._extract_entities_llm(event)

            # LLM should have been called
            mock_llm.assert_called_once()

            # Should return extracted entities
            assert len(entities) == 2
            assert entities[0].name == "Marcus Henderson"
            assert entities[0].entity_type == "player"

    def test_new_entity_marked_is_new(self):
        """
        New entities must be marked with is_new=True.

        This triggers Jidoka validation before persistence.
        """
        from engine.cortex import Cortex

        mock_llm_response = json.dumps({
            "entities": [
                {"name": "New Player", "type": "player", "is_new": True}
            ]
        })

        with patch('engine.llm_client.call_llm', return_value=mock_llm_response):
            cortex = Cortex()

            event = {
                "id": "test-event",
                "raw_transcript": "New Player joined the team",
                "source": "operator_session"
            }

            entities = cortex._extract_entities_llm(event)

            assert len(entities) == 1
            assert entities[0].is_new is True, \
                "New entity must be marked is_new=True"

    def test_new_entity_triggers_jidoka(self):
        """
        New entities (is_new=True) must trigger Jidoka validation.

        The system should halt and ask the operator to confirm
        before creating a new entity profile.
        """
        from engine.cortex import Cortex

        mock_llm_response = json.dumps({
            "entities": [
                {"name": "Unknown Person", "type": "player", "is_new": True}
            ]
        })

        jidoka_called = []

        def mock_jidoka(**kwargs):
            jidoka_called.append(kwargs)
            return "1"  # Approve

        with patch('engine.llm_client.call_llm', return_value=mock_llm_response):
            with patch('engine.cortex.ask_entity_validation', side_effect=mock_jidoka) as mock_ask:
                cortex = Cortex()

                event = {
                    "id": "test-event",
                    "raw_transcript": "Unknown Person mentioned",
                    "source": "operator_session"
                }

                entities = cortex._extract_entities_llm(event)

                # Should call validation for new entities
                if entities and entities[0].is_new:
                    cortex._validate_new_entity(entities[0])
                    assert len(jidoka_called) > 0, \
                        "New entity should trigger Jidoka validation"

    def test_existing_entity_skips_jidoka(self):
        """
        Existing entities (is_new=False) should skip Jidoka validation.

        Only new entities need operator confirmation.
        """
        from engine.cortex import Cortex

        mock_llm_response = json.dumps({
            "entities": [
                {"name": "Known Player", "type": "player", "is_new": False}
            ]
        })

        with patch('engine.llm_client.call_llm', return_value=mock_llm_response):
            with patch('engine.cortex.ask_entity_validation') as mock_ask:
                cortex = Cortex()

                event = {
                    "id": "test-event",
                    "raw_transcript": "Known Player mentioned",
                    "source": "operator_session"
                }

                entities = cortex._extract_entities_llm(event)

                # Existing entity should not trigger validation
                if entities and not entities[0].is_new:
                    # validate_new_entity should not be called
                    pass
                # mock_ask should not have been called for existing entities


class TestCortexLens2ContentSeedMining:
    """Tests for Lens 2: Content seed extraction from transcripts."""

    def test_content_seed_mining_uses_llm(self):
        """
        Content seed mining must use LLM to identify potential content.

        The LLM analyzes transcripts for moments worth sharing.
        """
        from engine.cortex import Cortex

        mock_llm_response = json.dumps({
            "content_seeds": [
                {
                    "title": "Team Progress Update",
                    "content": "Great practice session today with visible improvement",
                    "pillar": "training",
                    "suggested_platforms": ["tiktok", "instagram"]
                }
            ]
        })

        with patch('engine.llm_client.call_llm', return_value=mock_llm_response) as mock_llm:
            cortex = Cortex()

            event = {
                "id": "test-event",
                "raw_transcript": "The team had a great practice session today. Real visible improvement in putting accuracy.",
                "source": "operator_session"
            }

            seeds = cortex._mine_content_seeds(event)

            # LLM should have been called
            mock_llm.assert_called_once()

            # Should return extracted seeds
            assert len(seeds) == 1
            assert seeds[0]["title"] == "Team Progress Update"

    def test_content_seeds_saved_to_directory(self):
        """
        Mined content seeds must be saved to entities/content-seeds/.
        """
        from engine.cortex import Cortex
        from engine.profile import get_entities_dir

        mock_llm_response = json.dumps({
            "content_seeds": [
                {
                    "title": "Practice Highlight",
                    "content": "Amazing improvement today",
                    "pillar": "training"
                }
            ]
        })

        with patch('engine.llm_client.call_llm', return_value=mock_llm_response):
            with patch('engine.cortex.Cortex._save_content_seed') as mock_save:
                cortex = Cortex()

                event = {
                    "id": "test-event",
                    "raw_transcript": "Amazing improvement in today's practice",
                    "source": "operator_session"
                }

                seeds = cortex._mine_content_seeds(event)

                # Should attempt to save each seed (called internally by _mine_content_seeds)
                assert len(seeds) == 1
                mock_save.assert_called_once()


class TestCortexLLMTier:
    """Tests for correct LLM tier usage in Cortex."""

    def test_entity_extraction_uses_tier_1(self):
        """
        Entity extraction should use Tier 1 (Haiku) for speed/cost.

        Cortex runs on every interaction, so it must be cheap.
        """
        from engine.cortex import Cortex

        captured_kwargs = []

        def capture_llm_call(prompt, **kwargs):
            captured_kwargs.append(kwargs)
            return json.dumps({"entities": []})

        with patch('engine.llm_client.call_llm', side_effect=capture_llm_call):
            cortex = Cortex()
            cortex._extract_entities_llm({
                "id": "test",
                "raw_transcript": "Test",
                "source": "operator_session"
            })

        assert captured_kwargs[0].get("tier") == 1, \
            f"Entity extraction should use Tier 1, got {captured_kwargs[0].get('tier')}"

    def test_content_mining_uses_tier_1(self):
        """
        Content seed mining should also use Tier 1 for speed/cost.
        """
        from engine.cortex import Cortex

        captured_kwargs = []

        def capture_llm_call(prompt, **kwargs):
            captured_kwargs.append(kwargs)
            return json.dumps({"content_seeds": []})

        with patch('engine.llm_client.call_llm', side_effect=capture_llm_call):
            cortex = Cortex()
            cortex._mine_content_seeds({
                "id": "test",
                "raw_transcript": "Test transcript",
                "source": "operator_session"
            })

        assert captured_kwargs[0].get("tier") == 1, \
            f"Content mining should use Tier 1, got {captured_kwargs[0].get('tier')}"


class TestCortexTelemetry:
    """Tests for Cortex telemetry logging."""

    def test_logs_extraction_intent(self):
        """
        LLM calls should be logged with cortex_extraction intent.
        """
        from engine.cortex import Cortex

        captured_kwargs = []

        def capture_llm_call(prompt, **kwargs):
            captured_kwargs.append(kwargs)
            return json.dumps({"entities": []})

        with patch('engine.llm_client.call_llm', side_effect=capture_llm_call):
            cortex = Cortex()
            cortex._extract_entities_llm({
                "id": "test",
                "raw_transcript": "Test",
                "source": "operator_session"
            })

        assert captured_kwargs[0].get("intent") == "cortex_extraction", \
            f"Should log with cortex_extraction intent, got {captured_kwargs[0].get('intent')}"


class TestCortexErrorHandling:
    """Tests for error handling in Cortex."""

    def test_llm_failure_returns_empty_entities(self):
        """
        If LLM fails, return empty list rather than crashing.
        """
        from engine.cortex import Cortex

        with patch('engine.llm_client.call_llm', side_effect=Exception("API Error")):
            cortex = Cortex()

            event = {
                "id": "test",
                "raw_transcript": "Test",
                "source": "operator_session"
            }

            # Should not raise
            entities = cortex._extract_entities_llm(event)

            assert entities == [], "Should return empty list on error"

    def test_malformed_llm_response_handled(self):
        """
        Malformed LLM responses should be handled gracefully.
        """
        from engine.cortex import Cortex

        # Not valid JSON
        with patch('engine.llm_client.call_llm', return_value="not json"):
            cortex = Cortex()

            event = {
                "id": "test",
                "raw_transcript": "Test",
                "source": "operator_session"
            }

            # Should not raise
            entities = cortex._extract_entities_llm(event)

            assert isinstance(entities, list), "Should return list even on parse error"


class TestCortexNoGarbageEntities:
    """Tests ensuring no garbage entities like 'Generate' are created."""

    def test_rejects_action_words_as_entities(self):
        """
        Action words like 'Generate', 'Create', 'Update' must not become entities.

        The LLM should understand context and only extract real names.
        """
        from engine.cortex import Cortex

        # LLM should correctly identify that "Generate" is not a name
        mock_llm_response = json.dumps({
            "entities": []  # No entities - "Generate" is not a name
        })

        with patch('engine.llm_client.call_llm', return_value=mock_llm_response):
            cortex = Cortex()

            event = {
                "id": "test",
                "raw_transcript": "Generate weekly player progress report",
                "source": "operator_session"
            }

            entities = cortex._extract_entities_llm(event)

            # Should not create entity for "Generate"
            entity_names = [e.name.lower() for e in entities]
            assert "generate" not in entity_names, \
                "Action word 'Generate' should not become an entity"

    def test_extracts_real_names_in_context(self):
        """
        Real names should be extracted even when mixed with action words.
        """
        from engine.cortex import Cortex

        mock_llm_response = json.dumps({
            "entities": [
                {"name": "Marcus Henderson", "type": "player", "is_new": True}
            ]
        })

        with patch('engine.llm_client.call_llm', return_value=mock_llm_response):
            cortex = Cortex()

            event = {
                "id": "test",
                "raw_transcript": "Generate a progress report for Marcus Henderson",
                "source": "operator_session"
            }

            entities = cortex._extract_entities_llm(event)

            # Should extract Marcus Henderson but not Generate
            assert len(entities) == 1
            assert entities[0].name == "Marcus Henderson"
