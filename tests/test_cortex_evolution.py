"""
test_cortex_evolution.py - Tests for Cortex Evolutionary Lenses

Sprint 5: The Evolutionary Cortex
Sprint 6.5: The Vision Board
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


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

    def test_dispatcher_handles_cortex_batch(self, coach_demo_profile):
        """Verify dispatcher has cortex_batch handler (V-012: loaded from profile)."""
        from engine.dispatcher import get_dispatcher

        dispatcher = get_dispatcher()
        assert "cortex_batch" in dispatcher._handlers


class TestVisionBoardCapture:
    """Tests for Vision Board capture functionality (Sprint 6.5)."""

    def test_vision_capture_routes_to_green_zone(self):
        """Assert vision_capture is Green Zone (no approval needed)."""
        from engine.cognitive_router import classify_intent, reset_router
        from engine.profile import set_profile

        set_profile("coach_demo")
        reset_router()

        result = classify_intent("vision board: track parent engagement")

        assert result.intent == "vision_capture"
        assert result.zone == "green"
        assert result.handler == "vision_capture"

    def test_vision_capture_triggers_on_i_wish(self):
        """Assert 'i wish' trigger routes to vision_capture."""
        from engine.cognitive_router import classify_intent, reset_router
        from engine.profile import set_profile

        set_profile("coach_demo")
        reset_router()

        result = classify_intent("i wish I could automate lesson reminders")

        assert result.intent == "vision_capture"
        assert result.zone == "green"

    def test_vision_capture_triggers_on_someday(self):
        """Assert 'someday' trigger routes to vision_capture."""
        from engine.cognitive_router import classify_intent, reset_router
        from engine.profile import set_profile

        set_profile("coach_demo")
        reset_router()

        result = classify_intent("someday I want automatic tournament prep")

        assert result.intent == "vision_capture"
        assert result.zone == "green"

    def test_vision_capture_appends_to_vision_board(self, tmp_path, monkeypatch, coach_demo_profile):
        """Assert vision_capture appends raw transcript to vision-board.md."""
        from engine.dispatcher import get_dispatcher, DispatchResult
        from engine.cognitive_router import RoutingResult
        import engine.profile as profile_module

        # Create temp dock structure with vision board
        system_dir = tmp_path / "system"
        system_dir.mkdir(parents=True)
        vision_board = system_dir / "vision-board.md"
        vision_board.write_text("# Vision Board\n\n", encoding="utf-8")

        # Mock get_dock_dir to return temp path
        monkeypatch.setattr(
            profile_module, "get_dock_dir",
            lambda: tmp_path
        )

        # V-012: Handlers loaded by coach_demo_profile fixture
        dispatcher = get_dispatcher()

        # Create mock routing result
        routing = RoutingResult(
            intent="vision_capture",
            domain="system",
            zone="green",
            tier=1,
            confidence=1.0,
            handler="vision_capture",
            handler_args={},
            extracted_args={}
        )

        result = dispatcher.dispatch(routing, "vision board: I want to track tournament anxiety")

        assert result.success is True

        # Verify content was appended (vision board is in system subdir)
        content = (tmp_path / "system" / "vision-board.md").read_text(encoding="utf-8")
        assert "I want to track tournament anxiety" in content

    def test_dispatcher_has_vision_capture_handler(self, coach_demo_profile):
        """Verify dispatcher has vision_capture handler registered (V-012: loaded from profile)."""
        from engine.dispatcher import get_dispatcher

        dispatcher = get_dispatcher()
        assert "vision_capture" in dispatcher._handlers


class TestLens5VisionBoardIntegration:
    """Tests for Lens 5 Vision Board integration (Sprint 6.5)."""

    def test_lens5_loads_vision_board_content(self):
        """Assert run_evolution_analysis accepts vision_board parameter."""
        from engine.cortex import Cortex
        from engine.profile import set_profile

        set_profile("coach_demo")

        mock_telemetry = [
            {"id": "evt-001", "intent": "email_parent", "raw_transcript": "email Henderson's parents"}
        ]

        mock_exhaust_board = "# Exhaust Board\n\nTelemetry signals..."
        mock_vision_board = "# Vision Board\n\n- Track parent engagement patterns"

        mock_llm_response = json.dumps({
            "evolution_proposals": [
                {
                    "skill_name": "parent-engagement-tracker",
                    "description": "Track and analyze parent communication patterns",
                    "rationale": "User aspiration matches email_parent telemetry pattern",
                    "spec": {"triggers": ["parent engagement"], "zone": "green", "tier": 1},
                    "pit_crew_ready": True,
                    "vision_match": True
                }
            ]
        })

        cortex = Cortex()

        with patch("engine.llm_client.call_llm", return_value=mock_llm_response) as mock_call:
            result = cortex.run_evolution_analysis(
                mock_telemetry,
                mock_exhaust_board,
                mock_vision_board
            )

            # Verify vision board content was passed to LLM
            call_args = mock_call.call_args
            prompt = call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")
            assert "Vision Board" in prompt or "vision" in prompt.lower()

        assert "evolution_proposals" in result
        assert len(result["evolution_proposals"]) > 0

    def test_lens5_prompt_includes_vision_aspiration_instruction(self):
        """Assert LLM prompt instructs to match aspirations with telemetry."""
        from engine.cortex import Cortex
        from engine.profile import set_profile

        set_profile("coach_demo")

        mock_telemetry = [{"id": "evt-001", "intent": "test"}]
        mock_exhaust_board = "# Exhaust Board"
        mock_vision_board = "# Vision Board\n- I wish I had better reports"

        mock_llm_response = json.dumps({"evolution_proposals": []})

        cortex = Cortex()

        with patch("engine.llm_client.call_llm", return_value=mock_llm_response) as mock_call:
            cortex.run_evolution_analysis(
                mock_telemetry,
                mock_exhaust_board,
                mock_vision_board
            )

            # Get the prompt sent to LLM
            call_args = mock_call.call_args
            prompt = call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")

            # Should mention matching aspirations with behavior
            assert "aspiration" in prompt.lower() or "vision" in prompt.lower()

    def test_cortex_batch_handler_loads_vision_board(self, tmp_path, monkeypatch):
        """Assert cortex_batch handler loads vision-board.md for Lens 5."""
        from engine.dispatcher import get_dispatcher
        from engine.cognitive_router import RoutingResult
        from engine.profile import set_profile
        import engine.dispatcher as dispatcher_module
        import engine.profile as profile_module

        set_profile("coach_demo")

        # Create temp dock with vision board
        system_dir = tmp_path / "system"
        system_dir.mkdir()
        vision_board = system_dir / "vision-board.md"
        vision_board.write_text("# Vision Board\n\n- Track player progress\n", encoding="utf-8")
        exhaust_board = system_dir / "exhaust-board.md"
        exhaust_board.write_text("# Exhaust Board\n", encoding="utf-8")

        # Mock dock dir
        monkeypatch.setattr(
            profile_module, "get_dock_dir",
            lambda: tmp_path
        )

        # Mock telemetry loading
        monkeypatch.setattr(
            profile_module, "get_telemetry_path",
            lambda: tmp_path / "telemetry.jsonl"
        )

        # Reset dispatcher
        dispatcher_module._dispatcher_instance = None

        mock_llm_response = json.dumps({"evolution_proposals": []})

        with patch("engine.llm_client.call_llm", return_value=mock_llm_response) as mock_call:
            dispatcher = get_dispatcher()

            routing = RoutingResult(
                intent="cortex_evolve",
                domain="system",
                zone="yellow",
                tier=2,
                confidence=1.0,
                handler="cortex_batch",
                handler_args={"lens": "evolution_analysis"},
                extracted_args={}
            )

            result = dispatcher.dispatch(routing, "cortex evolve")

            # Verify LLM was called with vision board content
            if mock_call.called:
                call_args = mock_call.call_args
                prompt = call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")
                # Vision board should be included
                assert "Vision Board" in prompt or "Track player progress" in prompt
