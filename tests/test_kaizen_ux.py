"""V-018: Kaizen UX Tests

Tests for:
- Problem 1: Cost Display Truth (estimate_turn_cost, get_model_label)
- Problem 2: Unified Tiers (response_tier propagation, {total_cost} resolution)
- Problem 3: Learning Mode Discovery (toggle handler, tip event)
"""
import pytest
from unittest.mock import patch, MagicMock


class TestCostEstimation:
    """Problem 1: Config Over Code — pricing from models.yaml."""

    def test_estimate_turn_cost_returns_float(self):
        """estimate_turn_cost returns a float cost value."""
        from engine.llm_client import estimate_turn_cost

        cost = estimate_turn_cost(tier=1)
        assert isinstance(cost, float)
        assert cost >= 0

    def test_estimate_turn_cost_tier_ordering(self):
        """Higher tiers cost more than lower tiers."""
        from engine.llm_client import estimate_turn_cost

        tier1_cost = estimate_turn_cost(tier=1)
        tier2_cost = estimate_turn_cost(tier=2)
        tier3_cost = estimate_turn_cost(tier=3)

        # Haiku < Sonnet < Opus
        assert tier1_cost < tier2_cost < tier3_cost

    def test_get_model_label_haiku(self):
        """Tier 1 returns 'Haiku' label."""
        from engine.llm_client import get_model_label

        label = get_model_label(tier=1)
        assert label == "Haiku"

    def test_get_model_label_sonnet(self):
        """Tier 2 returns 'Sonnet' label."""
        from engine.llm_client import get_model_label

        label = get_model_label(tier=2)
        assert label == "Sonnet"

    def test_get_model_label_opus(self):
        """Tier 3 returns 'Opus' label."""
        from engine.llm_client import get_model_label

        label = get_model_label(tier=3)
        assert label == "Opus"


class TestOptionTemplateResolution:
    """Problem 2: {total_cost} template resolution for unified options."""

    def test_resolve_total_cost_template(self):
        """Resolves {total_cost} from classification_tier + response_tier."""
        from engine.ux import _resolve_option_template

        label = "Answer with Sonnet (~${total_cost}/turn)"
        resolved = _resolve_option_template(
            label,
            classification_tier=1,
            response_tier=2
        )

        # Should contain a dollar amount, not the template
        assert "{total_cost}" not in resolved
        assert "$" in resolved
        # Should resolve to a numeric cost format
        assert "/turn" in resolved
        # Cost should be non-zero for tier 2
        import re
        match = re.search(r'\$(\d+\.\d+)', resolved)
        assert match is not None
        cost_value = float(match.group(1))
        assert cost_value > 0

    def test_resolve_legacy_tier_templates(self):
        """Resolves legacy {tier_label} and {tier_cost} templates."""
        from engine.ux import _resolve_option_template

        label = "Use {tier_label} (~${tier_cost})"
        resolved = _resolve_option_template(label, tier=2)

        assert "{tier_label}" not in resolved
        assert "{tier_cost}" not in resolved
        assert "Sonnet" in resolved

    def test_no_template_unchanged(self):
        """Labels without templates pass through unchanged."""
        from engine.ux import _resolve_option_template

        label = "I'll rephrase"
        resolved = _resolve_option_template(label, tier=1)

        assert resolved == label


class TestKaizenConfig:
    """Problem 2: Kaizen options use unified tier model."""

    def test_kaizen_options_have_response_tier(self):
        """LLM classify options specify response_tier."""
        import yaml
        from pathlib import Path

        config_path = Path("profiles/reference/config/kaizen.yaml")
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        kaizen = config.get("kaizen", {})
        options = kaizen.get("options", {})

        # Option 1 should have response_tier for Sonnet
        opt1 = options.get("1", {})
        assert opt1.get("capability") == "llm_classify"
        assert opt1.get("response_tier") == 2  # Sonnet

        # Option 2 should have response_tier for Opus
        opt2 = options.get("2", {})
        assert opt2.get("capability") == "llm_classify"
        assert opt2.get("response_tier") == 3  # Opus

    def test_kaizen_options_say_answer_not_classify(self):
        """Options say 'Answer with X', not 'Classify with X'."""
        import yaml
        from pathlib import Path

        config_path = Path("profiles/reference/config/kaizen.yaml")
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        kaizen = config.get("kaizen", {})
        options = kaizen.get("options", {})

        for key, opt in options.items():
            label = opt.get("label", "")
            # Should NOT say "Classify with"
            assert "Classify with" not in label, f"Option {key} exposes plumbing"


class TestLearningModeRoutes:
    """Problem 3: Learning Mode toggle routes exist."""

    def test_enable_learning_route_exists(self):
        """routing.config has enable_learning route."""
        import yaml
        from pathlib import Path

        config_path = Path("profiles/reference/config/routing.config")
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        routes = config.get("routes", {})
        assert "enable_learning" in routes

        route = routes["enable_learning"]
        assert route.get("handler") == "toggle_learning_mode"
        assert route.get("handler_args", {}).get("enable") is True
        assert "enable learning" in route.get("keywords", [])

    def test_disable_learning_route_exists(self):
        """routing.config has disable_learning route."""
        import yaml
        from pathlib import Path

        config_path = Path("profiles/reference/config/routing.config")
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        routes = config.get("routes", {})
        assert "disable_learning" in routes

        route = routes["disable_learning"]
        assert route.get("handler") == "toggle_learning_mode"
        assert route.get("handler_args", {}).get("enable") is False


class TestLearningModeTip:
    """Problem 3: Tip surfaces when Kaizen fires in Free Mode."""

    def test_kaizen_fired_free_mode_tip_configured(self):
        """ux.yaml has tip for kaizen_fired_free_mode event."""
        import yaml
        from pathlib import Path

        config_path = Path("profiles/reference/config/ux.yaml")
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        tips = config.get("tips", {})
        events = tips.get("events", {})

        assert "kaizen_fired_free_mode" in events

        tip = events["kaizen_fired_free_mode"]
        assert "enable learning" in tip.get("message", "").lower()


class TestToggleLearningModeHandler:
    """Problem 3: toggle_learning_mode handler works correctly."""

    def test_handler_registered(self):
        """toggle_learning_mode handler is registered in dispatcher."""
        from engine.dispatcher import Dispatcher

        dispatcher = Dispatcher()
        assert "toggle_learning_mode" in dispatcher._handlers

    @patch("engine.profile.set_session_enrichment")
    @patch("engine.profile.get_session_enrichment")
    def test_enable_returns_success(self, mock_get, mock_set):
        """Enabling Learning Mode returns success with cost info."""
        from engine.dispatcher import Dispatcher
        from engine.cognitive_router import RoutingResult

        mock_get.return_value = False

        dispatcher = Dispatcher()

        routing_result = RoutingResult(
            intent="enable_learning",
            confidence=1.0,
            handler="toggle_learning_mode",
            handler_args={"enable": True},
            zone="yellow",
            tier=0,
            domain="system"
        )

        result = dispatcher.dispatch(routing_result, "enable learning")

        assert result.success is True
        assert "enabled" in result.message.lower()
        mock_set.assert_called_once_with(True)

    @patch("engine.profile.set_session_enrichment")
    @patch("engine.profile.get_session_enrichment")
    def test_disable_returns_success(self, mock_get, mock_set):
        """Disabling Learning Mode returns success."""
        from engine.dispatcher import Dispatcher
        from engine.cognitive_router import RoutingResult

        mock_get.return_value = True

        dispatcher = Dispatcher()

        routing_result = RoutingResult(
            intent="disable_learning",
            confidence=1.0,
            handler="toggle_learning_mode",
            handler_args={"enable": False},
            zone="yellow",
            tier=0,
            domain="system"
        )

        result = dispatcher.dispatch(routing_result, "disable learning")

        assert result.success is True
        assert "disabled" in result.message.lower() or "free mode" in result.message.lower()
        mock_set.assert_called_once_with(False)
