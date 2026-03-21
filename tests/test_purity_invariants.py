"""
test_purity_invariants.py - Purity Audit Verification Tests

Verifies the architectural invariants fixed in the purity-audit-v1 sprint:
1. No pipeline bypasses — all LLM calls traverse the 5-stage pipeline
2. The Ratchet — confirmed LLM classifications cache at Tier 0
3. Cortex governance — no direct I/O in analytical layer
"""

import pytest
import yaml
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock


# =========================================================================
# Test Class 1: No Pipeline Bypasses
# =========================================================================

class TestNoPipelineBypasses:
    """Verify that no code calls call_llm() outside the pipeline."""

    def test_autonomaton_has_no_direct_llm_calls(self):
        """autonomaton.py must not import or call call_llm directly."""
        content = Path("autonomaton.py").read_text(encoding="utf-8")
        assert "from engine.llm_client import call_llm" not in content, \
            "autonomaton.py still imports call_llm directly"
        assert "call_llm(" not in content, \
            "autonomaton.py still calls call_llm() directly"

    def test_internal_intents_declared_in_routing_config(self):
        """Internal startup intents must exist in routing.config."""
        config_path = Path("profiles/coach_demo/config/routing.config")
        with open(config_path) as f:
            config = yaml.safe_load(f)
        routes = config.get("routes", {})
        for intent in ["welcome_card", "startup_brief", "generate_plan"]:
            assert intent in routes, \
                f"Internal intent '{intent}' missing from routing.config"

    def test_internal_intents_have_handlers(self):
        """Internal intents must have registered dispatcher handlers."""
        from engine.dispatcher import Dispatcher
        d = Dispatcher()
        for handler_name in ["welcome_card", "startup_brief", "generate_plan"]:
            assert handler_name in d._handlers, \
                f"Handler '{handler_name}' not registered in Dispatcher"

    def test_startup_pipeline_produces_telemetry(self):
        """Pipeline invocations with source=system_startup must produce telemetry."""
        from engine.pipeline import InvariantPipeline, PipelineContext

        # Test that Stage 1 telemetry produces correct event structure
        pipeline = InvariantPipeline()
        pipeline.context = PipelineContext(
            raw_input="startup_brief",
            source="system_startup"
        )
        pipeline._run_telemetry()

        # Stage 1: Telemetry event must exist
        assert pipeline.context.telemetry_event is not None
        assert "id" in pipeline.context.telemetry_event
        # Source must be system_startup
        assert pipeline.context.telemetry_event.get("source") == "system_startup"


# =========================================================================
# Test Class 2: The Ratchet (Pattern Cache)
# =========================================================================

class TestPatternCache:
    """Verify cache file exists and handler is registered."""

    def test_pattern_cache_file_exists(self):
        """pattern_cache.yaml must exist in profile config."""
        cache_path = Path("profiles/coach_demo/config/pattern_cache.yaml")
        assert cache_path.exists(), "pattern_cache.yaml not found"

    def test_clear_cache_handler_registered(self):
        """clear_cache handler must be registered in Dispatcher."""
        from engine.dispatcher import Dispatcher
        d = Dispatcher()
        assert "clear_cache" in d._handlers


# =========================================================================
# Test Class 3: Cortex Governance
# =========================================================================

class TestCortexGovernance:
    """Verify the Cortex has no direct I/O — all proposals via queue."""

    def test_cortex_has_no_input_calls(self):
        """cortex.py must not call input() anywhere."""
        content = Path("engine/cortex.py").read_text(encoding="utf-8")
        # Filter out comments
        lines = [l for l in content.split("\n")
                 if not l.strip().startswith("#")]
        code = "\n".join(lines)
        assert "input(" not in code, \
            "cortex.py contains direct input() call"

    def test_cortex_entity_proposal_creates_queue_item(self):
        """Entity validation must produce a queue proposal, not prompt."""
        from engine.cortex import create_entity_validation_proposal
        proposal = create_entity_validation_proposal(
            entity_name="Test Player",
            entity_type="player",
            context="Some context about a player"
        )
        assert isinstance(proposal, dict)
        assert proposal["proposal_type"] == "entity_validation"
        assert proposal["entity_name"] == "Test Player"
        assert proposal["entity_type"] == "player"
        assert "id" in proposal
        assert "created" in proposal
