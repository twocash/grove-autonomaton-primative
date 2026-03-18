"""
test_cortex_evolution.py - Tests for Cortex Evolutionary Lenses

Sprint 5: The Evolutionary Cortex
"""

import pytest
import json
from unittest.mock import patch


class TestLens3PatternAnalysis:
    """Tests for Lens 3: Pattern Analysis."""

    def test_lens3_pattern_analysis(self):
        """Assert telemetry + dock goals yields Kaizen proposal."""
        from engine.cortex import Cortex
        from engine.profile import set_profile

        set_profile("coach_demo")

        mock_telemetry = [
            {"id": "evt-001", "intent": "calendar_schedule", "raw_transcript": "schedule lesson"},
            {"id": "evt-002", "intent": "email_parent", "raw_transcript": "email parent"}
        ]

        mock_llm_response = json.dumps({
            "patterns_detected": ["Henderson workflow spans scheduling and communication"],
            "kaizen_proposals": [
                {"id": "kaizen-001", "proposal": "Create player-360-view skill", "trigger": "pattern_detected", "priority": "high"}
            ]
        })

        cortex = Cortex()

        with patch("engine.llm_client.call_llm", return_value=mock_llm_response):
            result = cortex.run_pattern_analysis(mock_telemetry)

        assert "kaizen_proposals" in result
        assert len(result["kaizen_proposals"]) > 0
        proposal = result["kaizen_proposals"][0]
        assert "proposal" in proposal
        assert "trigger" in proposal


class TestLens4RatchetAnalysis:
    """Tests for Lens 4: Ratchet Analysis."""

    def test_lens4_ratchet_analysis(self):
        """Assert LLM telemetry yields Ratchet demotion proposal."""
        from engine.cortex import Cortex
        from engine.profile import set_profile

        set_profile("coach_demo")

        mock_llm_telemetry = [
            {"id": "llm-001", "model": "sonnet", "intent": "intent_classification"}
        ]

        mock_routing_patterns = [
            {"intent": "dock_status", "confidence": 0.99, "count": 50}
        ]

        mock_llm_response = json.dumps({
            "ratchet_proposals": [
                {"intent": "dock_status", "current_tier": 1, "proposed_action": "Demote to Tier 0", "confidence": 0.99, "sample_count": 50, "recommendation": "Demote to Tier 0 deterministic rule."}
            ],
            "total_potential_savings": "$0.50/month"
        })

        cortex = Cortex()

        with patch("engine.llm_client.call_llm", return_value=mock_llm_response):
            result = cortex.run_ratchet_analysis(mock_llm_telemetry, mock_routing_patterns)

        assert "ratchet_proposals" in result
        assert len(result["ratchet_proposals"]) > 0
        proposal = result["ratchet_proposals"][0]
        assert "intent" in proposal
        assert "recommendation" in proposal


class TestLens5EvolutionProposals:
    """Tests for Lens 5: Evolution/Personal Product Manager."""

    def test_lens5_evolution_proposals(self):
        """Assert telemetry + exhaust board yields Pit Crew work order."""
        from engine.cortex import Cortex
        from engine.profile import set_profile

        set_profile("coach_demo")

        mock_telemetry = [
            {"id": "evt-001", "intent": "calendar_schedule", "raw_transcript": "schedule practice"},
            {"id": "evt-002", "intent": "email_parent", "raw_transcript": "email parents"}
        ]

        mock_exhaust_board = "# Exhaust Board\n\nTelemetry unlocks here..."

        mock_llm_response = json.dumps({
            "evolution_proposals": [
                {"skill_name": "practice-scheduler", "description": "Automate weekly practice", "rationale": "Detected pattern", "spec": {"triggers": ["schedule practice"], "zone": "yellow", "tier": 2}, "pit_crew_ready": True}
            ]
        })

        cortex = Cortex()

        with patch("engine.llm_client.call_llm", return_value=mock_llm_response):
            result = cortex.run_evolution_analysis(mock_telemetry, mock_exhaust_board)

        assert "evolution_proposals" in result
        assert len(result["evolution_proposals"]) > 0
        proposal = result["evolution_proposals"][0]
        assert "skill_name" in proposal
        assert "description" in proposal
        assert "spec" in proposal
        assert "pit_crew_ready" in proposal


class TestCortexBatchHandler:
    """Tests for Cortex batch handler integration."""

    def test_cortex_analyze_routes_through_pipeline(self):
        """Verify cortex analyze routes correctly."""
        from engine.cognitive_router import classify_intent, reset_router
        from engine.profile import set_profile

        set_profile("coach_demo")
        reset_router()

        result = classify_intent("cortex analyze")

        assert result.intent == "cortex_analyze"
        assert result.zone == "yellow"
        assert result.handler == "cortex_batch"
        assert result.handler_args.get("lens") == "pattern_analysis"

    def test_cortex_ratchet_routes_through_pipeline(self):
        """Verify cortex ratchet routes correctly."""
        from engine.cognitive_router import classify_intent, reset_router
        from engine.profile import set_profile

        set_profile("coach_demo")
        reset_router()

        result = classify_intent("cortex ratchet")

        assert result.intent == "cortex_ratchet"
        assert result.zone == "yellow"
        assert result.handler == "cortex_batch"
        assert result.handler_args.get("lens") == "ratchet_analysis"

    def test_cortex_evolve_routes_through_pipeline(self):
        """Verify cortex evolve routes correctly."""
        from engine.cognitive_router import classify_intent, reset_router
        from engine.profile import set_profile

        set_profile("coach_demo")
        reset_router()

        result = classify_intent("cortex evolve")

        assert result.intent == "cortex_evolve"
        assert result.zone == "yellow"
        assert result.handler == "cortex_batch"
        assert result.handler_args.get("lens") == "evolution_analysis"

    def test_dispatcher_handles_cortex_batch(self):
        """Verify dispatcher has cortex_batch handler."""
        from engine.dispatcher import get_dispatcher

        dispatcher = get_dispatcher()
        assert "cortex_batch" in dispatcher._handlers
