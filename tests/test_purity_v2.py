"""
test_purity_v2.py - Purity Audit v2 Verification Tests

Verifies:
1. Telemetry events have flat routing fields
2. Model config loads from YAML, not hardcoded
3. Red zone uses differentiated UX
4. No ghost failures in MCP pipeline path
"""

import pytest
import yaml
import inspect
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestFlatTelemetry:
    """Verify telemetry events have first-class routing fields."""

    def test_create_event_with_flat_fields(self):
        from engine.telemetry import create_event
        e = create_event(
            source="test", raw_transcript="hi", zone_context="green",
            intent="strategy_session", tier=2, confidence=0.85,
            cost_usd=0.003, human_feedback="approved"
        )
        assert e["intent"] == "strategy_session"
        assert e["tier"] == 2
        assert e["confidence"] == 0.85
        assert e["cost_usd"] == 0.003
        assert e["human_feedback"] == "approved"

    def test_none_fields_omitted_from_output(self):
        from engine.telemetry import create_event
        e = create_event(
            source="test", raw_transcript="hi", zone_context="green"
        )
        assert "intent" not in e
        assert "tier" not in e

    def test_backward_compatible_with_existing_calls(self):
        """Existing log_event calls without new params must still work."""
        from engine.telemetry import create_event
        e = create_event(
            source="test", raw_transcript="hello",
            zone_context="green",
            inferred={"some": "data"}
        )
        assert e["inferred"] == {"some": "data"}
        assert "intent" not in e


class TestModelConfig:
    """Verify model config loads from YAML."""

    def test_models_yaml_exists(self):
        assert Path("profiles/coach_demo/config/models.yaml").exists()

    def test_models_yaml_has_three_tiers(self):
        with open("profiles/coach_demo/config/models.yaml") as f:
            data = yaml.safe_load(f)
        assert 1 in data["tiers"]
        assert 2 in data["tiers"]
        assert 3 in data["tiers"]

    def test_config_loader_returns_valid_models(self):
        from engine.llm_client import _load_models_config, reset_models_config
        reset_models_config()  # Clear cache
        config = _load_models_config()
        tiers = config["tiers"]
        pricing = config["pricing"]
        max_tok = config["default_max_tokens"]
        assert 1 in tiers and 2 in tiers and 3 in tiers
        assert max_tok > 0
        # Each tier model should have pricing
        for tier_num, model_id in tiers.items():
            assert model_id in pricing, \
                f"Tier {tier_num} model '{model_id}' missing pricing"

    def test_call_llm_no_hardcoded_models(self):
        """call_llm() must not contain hardcoded model strings."""
        from engine.llm_client import call_llm
        src = inspect.getsource(call_llm)
        assert "claude-3-haiku" not in src
        assert "claude-3-5-sonnet" not in src
        assert "claude-3-opus" not in src


class TestRedZoneUX:
    """Verify red zone uses differentiated approval UX."""

    def test_red_zone_uses_context_approval(self):
        from engine.pipeline import InvariantPipeline
        src = inspect.getsource(InvariantPipeline._run_approval)
        assert "confirm_red_zone_with_context" in src, \
            "Red zone still using confirm_yellow_zone"

    def test_red_zone_not_using_yellow_zone_function(self):
        from engine.pipeline import InvariantPipeline
        src = inspect.getsource(InvariantPipeline._run_approval)
        # Find the red zone block and verify it doesn't call confirm_yellow_zone
        lines = src.split("\n")
        in_red_block = False
        for line in lines:
            if "red" in line.lower() and "elif" in line:
                in_red_block = True
            elif in_red_block and ("elif" in line or "else:" in line):
                break
            if in_red_block and "confirm_yellow_zone" in line:
                pytest.fail("Red zone block calls confirm_yellow_zone")


class TestDefensiveHardening:
    """Verify ghost failure prevention and telemetry on errors."""

    def test_pipeline_has_exception_handling(self):
        """V-010: Single pipeline path must have exception handling."""
        from engine.pipeline import InvariantPipeline
        src = inspect.getsource(InvariantPipeline.run)
        assert "try:" in src and "except" in src, \
            "InvariantPipeline.run has no exception handling"

    def test_standing_context_failure_logs_telemetry(self):
        from engine.config_loader import PersonaConfig
        src = inspect.getsource(PersonaConfig.build_system_prompt)
        assert "log_event" in src, \
            "Standing context failure does not log telemetry"

    def test_handler_contract_documented(self):
        content = Path("CLAUDE.md").read_text(encoding="utf-8")
        assert "Handler Interface Contract" in content
