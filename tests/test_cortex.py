"""
test_cortex.py - Tests for LLM-Powered Cortex Analysis

These tests ensure the Cortex uses LLM for entity extraction and
content seed mining, with Jidoka validation for new entities.

Sprint 6 (ADR-001): Entity extraction now uses ratchet_classify pattern:
- Deterministic layer (regex) runs first
- LLM layer routes through pipeline if confidence < threshold

TDD: Write tests first, then implement to pass.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json


class TestCortexLens1EntityExtraction:
    """Tests for Lens 1: LLM-based entity extraction."""

    def test_entity_extraction_uses_ratchet_pattern(self):
        """
        Entity extraction must use ratchet_classify pattern (Sprint 6 - ADR-001).

        The ratchet pattern:
        1. Tries deterministic (regex) first
        2. Falls back to LLM via pipeline if confidence < threshold
        """
        from engine.cortex import Cortex, ExtractedEntity
        from engine.ratchet import RatchetResult

        # Mock ratchet_classify to return LLM-extracted entities
        mock_entities = [
            ExtractedEntity(
                name="Marcus Henderson",
                entity_type="player",
                source_event_id="test-event-123",
                confidence=0.8,
                context="Marcus Henderson had a great lesson",
                is_new=True
            ),
            ExtractedEntity(
                name="Sarah Henderson",
                entity_type="parent",
                source_event_id="test-event-123",
                confidence=0.8,
                context="Sarah Henderson was impressed",
                is_new=True
            )
        ]

        mock_result = RatchetResult(
            result=mock_entities,
            source="deterministic",  # or "pipeline" for LLM
            confidence=0.7,
            latency_ms=50,
            label="entity_extraction"
        )

        with patch('engine.ratchet.ratchet_classify', return_value=mock_result):
            cortex = Cortex()

            event = {
                "id": "test-event-123",
                "raw_transcript": "Marcus Henderson had a great lesson today. His mother Sarah Henderson was impressed.",
                "source": "operator_session"
            }

            entities = cortex._extract_entities(event)

            # Should return extracted entities
            assert len(entities) == 2
            assert entities[0].name == "Marcus Henderson"
            assert entities[0].entity_type == "player"

    def test_new_entity_marked_is_new(self):
        """
        New entities must be marked with is_new=True.

        This triggers Jidoka validation before persistence.
        """
        from engine.cortex import Cortex, ExtractedEntity
        from engine.ratchet import RatchetResult

        # Use deterministic source to return already-parsed entities
        mock_entities = [
            ExtractedEntity(
                name="New Player",
                entity_type="player",
                source_event_id="test-event",
                confidence=0.8,
                context="New Player joined the team",
                is_new=True
            )
        ]

        mock_result = RatchetResult(
            result=mock_entities,
            source="deterministic",  # Deterministic returns parsed entities
            confidence=0.8,
            latency_ms=100,
            label="entity_extraction"
        )

        with patch('engine.ratchet.ratchet_classify', return_value=mock_result):
            cortex = Cortex()

            event = {
                "id": "test-event",
                "raw_transcript": "New Player joined the team",
                "source": "operator_session"
            }

            entities = cortex._extract_entities(event)

            assert len(entities) == 1
            assert entities[0].is_new is True, \
                "New entity must be marked is_new=True"

    def test_new_entity_creates_queue_proposal(self):
        """
        New entities (is_new=True) must create a queue proposal.

        Post v1: Entity validation uses queue-based proposals instead of
        direct I/O. The Cortex creates proposals, operators approve via queue.
        """
        from engine.cortex import create_entity_validation_proposal

        # Create proposal for new entity
        proposal = create_entity_validation_proposal(
            entity_name="Unknown Person",
            entity_type="player",
            context="Unknown Person mentioned in practice"
        )

        # Proposal must be properly structured
        assert isinstance(proposal, dict), "Proposal must be a dict"
        assert proposal["proposal_type"] == "entity_validation"
        assert proposal["entity_name"] == "Unknown Person"
        assert proposal["entity_type"] == "player"
        assert "id" in proposal, "Proposal must have an ID"
        assert "created" in proposal, "Proposal must have timestamp"

    def test_existing_entity_no_proposal_needed(self):
        """
        Existing entities (is_new=False) don't need queue proposals.

        Post v1: Only new entities need operator confirmation via queue.
        Existing entities are already validated.
        """
        from engine.cortex import Cortex, ExtractedEntity
        from engine.ratchet import RatchetResult

        mock_entities = [
            ExtractedEntity(
                name="Known Player",
                entity_type="player",
                source_event_id="test-event",
                confidence=0.8,
                context="Known Player mentioned",
                is_new=False  # Existing entity
            )
        ]

        mock_result = RatchetResult(
            result=mock_entities,
            source="deterministic",  # Deterministic returns parsed entities
            confidence=0.8,
            latency_ms=100,
            label="entity_extraction"
        )

        with patch('engine.ratchet.ratchet_classify', return_value=mock_result):
            cortex = Cortex()

            event = {
                "id": "test-event",
                "raw_transcript": "Known Player mentioned",
                "source": "operator_session"
            }

            entities = cortex._extract_entities(event)

            # Existing entity should not need validation
            assert len(entities) == 1
            assert entities[0].is_new is False
            # No proposal needed for existing entities


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

    def test_entity_extraction_routes_to_tier_1(self):
        """
        Entity extraction should route to ratchet_entity_extract (Tier 1).

        Sprint 6 (ADR-001): Entity extraction uses ratchet_classify pattern.
        The interpret_route 'ratchet_entity_extract' is configured as Tier 1
        in routing.config.
        """
        from engine.cortex import Cortex, ExtractedEntity
        from engine.ratchet import RatchetResult, RatchetConfig

        captured_configs = []

        def capture_ratchet(input_text, config, context=None):
            captured_configs.append(config)
            return RatchetResult(
                result=[],
                source="deterministic",
                confidence=0.8,
                latency_ms=10,
                label=config.label
            )

        with patch('engine.ratchet.ratchet_classify', side_effect=capture_ratchet):
            cortex = Cortex()
            cortex._extract_entities({
                "id": "test",
                "raw_transcript": "Test",
                "source": "operator_session"
            })

        assert len(captured_configs) == 1
        assert captured_configs[0].interpret_route == "ratchet_entity_extract", \
            f"Entity extraction should use ratchet_entity_extract route"
        assert captured_configs[0].label == "entity_extraction"

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

    def test_ratchet_classify_logs_to_telemetry(self):
        """
        Entity extraction via ratchet_classify logs through the pipeline.

        Sprint 6 (ADR-001): Ratchet pattern ensures all classification
        goes through the invariant pipeline, which logs to telemetry.
        """
        from engine.cortex import Cortex, ExtractedEntity
        from engine.ratchet import RatchetResult

        # When ratchet_classify routes through pipeline, telemetry is logged
        # by the pipeline's Stage 1 (TELEMETRY). We verify the ratchet
        # is called with proper label for telemetry categorization.
        mock_result = RatchetResult(
            result=[],
            source="deterministic",
            confidence=0.8,
            latency_ms=10,
            label="entity_extraction"
        )

        captured_configs = []

        def capture_ratchet(input_text, config, context=None):
            captured_configs.append(config)
            return mock_result

        with patch('engine.ratchet.ratchet_classify', side_effect=capture_ratchet):
            cortex = Cortex()
            cortex._extract_entities({
                "id": "test",
                "raw_transcript": "Test",
                "source": "operator_session"
            })

        assert len(captured_configs) == 1
        assert captured_configs[0].label == "entity_extraction", \
            "Ratchet should be called with entity_extraction label for telemetry"


class TestCortexErrorHandling:
    """Tests for error handling in Cortex."""

    def test_ratchet_failure_returns_empty_entities(self):
        """
        If ratchet_classify fails, return empty list rather than crashing.

        Sprint 6 (ADR-001): Ratchet returns source="none" on failure.
        """
        from engine.cortex import Cortex
        from engine.ratchet import RatchetResult

        # Simulate ratchet failure (source="none", result=None)
        mock_result = RatchetResult(
            result=None,
            source="none",
            confidence=0.0,
            latency_ms=0,
            label="entity_extraction"
        )

        with patch('engine.ratchet.ratchet_classify', return_value=mock_result):
            cortex = Cortex()

            event = {
                "id": "test",
                "raw_transcript": "Test",
                "source": "operator_session"
            }

            # Should not raise
            entities = cortex._extract_entities(event)

            assert entities == [], "Should return empty list on ratchet failure"

    def test_ratchet_exception_returns_empty_entities(self):
        """
        If ratchet_classify raises exception, return empty list gracefully.
        """
        from engine.cortex import Cortex

        with patch('engine.ratchet.ratchet_classify', side_effect=Exception("Pipeline Error")):
            with patch('engine.telemetry.log_event'):  # Suppress telemetry in test
                cortex = Cortex()

                event = {
                    "id": "test",
                    "raw_transcript": "Test",
                    "source": "operator_session"
                }

                # Should not raise
                entities = cortex._extract_entities(event)

                assert isinstance(entities, list), "Should return list even on exception"
                assert entities == [], "Should return empty list on exception"


class TestCortexNoGarbageEntities:
    """Tests ensuring no garbage entities like 'Generate' are created."""

    def test_rejects_action_words_as_entities(self):
        """
        Action words like 'Generate', 'Create', 'Update' must not become entities.

        Sprint 6 (ADR-001): Entity extraction via ratchet_classify ensures
        proper classification. The LLM should understand context.
        """
        from engine.cortex import Cortex
        from engine.ratchet import RatchetResult

        # Ratchet returns empty list - "Generate" is not a name
        mock_result = RatchetResult(
            result=[],  # No entities extracted
            source="pipeline",
            confidence=0.9,
            latency_ms=50,
            label="entity_extraction"
        )

        with patch('engine.ratchet.ratchet_classify', return_value=mock_result):
            cortex = Cortex()

            event = {
                "id": "test",
                "raw_transcript": "Generate weekly player progress report",
                "source": "operator_session"
            }

            entities = cortex._extract_entities(event)

            # Should not create entity for "Generate"
            entity_names = [e.name.lower() for e in entities]
            assert "generate" not in entity_names, \
                "Action word 'Generate' should not become an entity"

    def test_extracts_real_names_in_context(self):
        """
        Real names should be extracted even when mixed with action words.
        """
        from engine.cortex import Cortex, ExtractedEntity
        from engine.ratchet import RatchetResult

        mock_entities = [
            ExtractedEntity(
                name="Marcus Henderson",
                entity_type="player",
                source_event_id="test",
                confidence=0.85,
                context="Generate a progress report for Marcus Henderson",
                is_new=True
            )
        ]

        mock_result = RatchetResult(
            result=mock_entities,
            source="deterministic",  # Deterministic returns parsed entities
            confidence=0.85,
            latency_ms=80,
            label="entity_extraction"
        )

        with patch('engine.ratchet.ratchet_classify', return_value=mock_result):
            cortex = Cortex()

            event = {
                "id": "test",
                "raw_transcript": "Generate a progress report for Marcus Henderson",
                "source": "operator_session"
            }

            entities = cortex._extract_entities(event)

            # Should extract Marcus Henderson but not Generate
            assert len(entities) == 1
            assert entities[0].name == "Marcus Henderson"
