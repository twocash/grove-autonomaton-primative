"""
cognitive_router.py - Tier 0 Intent Classification

Implements keyword-based intent classification using routing.config.
No LLM - pure pattern matching for Sprint 1.

Architectural Invariants Enforced:
- #2 Config Over Code: Domain logic loaded from routing.config YAML
- #3 Zone Governance: Every intent has declared zone from config
- #4 Digital Jidoka: Unknown intents default to yellow zone (halt for approval)
"""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from engine.profile import get_config_dir


@dataclass
class RoutingResult:
    """
    Result of cognitive routing.

    Contains all information needed for pipeline governance and dispatch.
    """
    intent: str
    domain: str
    zone: str
    tier: int
    confidence: float
    handler: Optional[str] = None
    handler_args: dict = field(default_factory=dict)
    extracted_args: dict = field(default_factory=dict)


class CognitiveRouter:
    """
    Tier 0 keyword-based intent classifier.

    Loads routing.config from the active profile and matches
    user input against declared keyword patterns.

    Matching Strategy:
    1. Exact match on keywords (confidence: 1.0)
    2. Prefix match - input starts with keyword (confidence: 0.9)
    3. Contains match (confidence: 0.5)

    Unknown inputs default to yellow zone per Digital Jidoka principle.
    """

    # Default result for unknown intents - MUST be yellow zone
    DEFAULT_RESULT = RoutingResult(
        intent="unknown",
        domain="general",
        zone="yellow",  # Invariant #4: Ambiguity requires human approval
        tier=2,
        confidence=0.0,
        handler=None
    )

    def __init__(self):
        self.routes: dict = {}
        self.tiers: dict = {}
        self._loaded = False

    def load_config(self) -> bool:
        """
        Load routing.config from active profile.

        Returns:
            True if config loaded successfully, False otherwise.
        """
        try:
            config_path = get_config_dir() / "routing.config"
        except RuntimeError:
            # No profile set - return False
            return False

        if not config_path.exists():
            return False

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            return False

        self.routes = config.get("routes", {})
        self.tiers = config.get("tiers", {})
        self._loaded = True
        return True

    def classify(self, user_input: str) -> RoutingResult:
        """
        Classify user input and return routing result.

        Args:
            user_input: Raw user input string

        Returns:
            RoutingResult with intent, domain, zone, tier, confidence,
            and handler information for dispatch.
        """
        if not self._loaded:
            self.load_config()

        if not self.routes:
            return self._create_default_result()

        normalized_input = user_input.lower().strip()

        # Empty input defaults to unknown/yellow
        if not normalized_input:
            return self._create_default_result()

        best_match: Optional[tuple] = None  # (intent_name, route_config, confidence)

        for intent_name, route_config in self.routes.items():
            keywords = route_config.get("keywords", [])

            for keyword in keywords:
                keyword_lower = keyword.lower()
                confidence = 0.0

                # Exact match - highest confidence
                if normalized_input == keyword_lower:
                    confidence = 1.0
                # Starts with keyword + space (for commands with args)
                elif normalized_input.startswith(keyword_lower + " "):
                    confidence = 0.9
                # Starts with keyword (no space - still good match)
                elif normalized_input.startswith(keyword_lower):
                    confidence = 0.85
                # Contains keyword (lower priority)
                elif keyword_lower in normalized_input:
                    confidence = 0.5

                if confidence > 0:
                    if best_match is None or confidence > best_match[2]:
                        best_match = (intent_name, route_config, confidence)

        if best_match is None:
            return self._create_default_result()

        intent_name, route_config, confidence = best_match

        # Extract arguments if specified in config
        extracted_args = self._extract_arguments(
            user_input,
            route_config.get("extract_args", [])
        )

        return RoutingResult(
            intent=intent_name,
            domain=route_config.get("domain", "general"),
            zone=route_config.get("zone", "yellow"),
            tier=route_config.get("tier", 2),
            confidence=confidence,
            handler=route_config.get("handler"),
            handler_args=route_config.get("handler_args", {}),
            extracted_args=extracted_args
        )

    def _create_default_result(self) -> RoutingResult:
        """Create a fresh default result (unknown intent, yellow zone)."""
        return RoutingResult(
            intent="unknown",
            domain="general",
            zone="yellow",
            tier=2,
            confidence=0.0,
            handler=None,
            handler_args={},
            extracted_args={}
        )

    def _extract_arguments(self, user_input: str, extract_specs: list) -> dict:
        """
        Extract arguments from user input based on position specs.

        Args:
            user_input: Original user input
            extract_specs: List of extraction specifications from config

        Returns:
            Dict of extracted argument name -> value
        """
        extracted = {}
        parts = user_input.split()

        for spec in extract_specs:
            name = spec.get("name")
            position = spec.get("position")

            if name and position is not None and position < len(parts):
                # Get all remaining parts from position onward
                extracted[name] = " ".join(parts[position:])

        return extracted


# =========================================================================
# Module-level Singleton and Interface
# =========================================================================

_router_instance: Optional[CognitiveRouter] = None


def get_router() -> CognitiveRouter:
    """
    Get the shared CognitiveRouter instance.

    Creates and loads config on first call.
    """
    global _router_instance
    if _router_instance is None:
        _router_instance = CognitiveRouter()
        _router_instance.load_config()
    return _router_instance


def classify_intent(user_input: str) -> RoutingResult:
    """
    Classify user input and return routing result.

    This is the primary interface for pipeline integration.

    Args:
        user_input: Raw user input string

    Returns:
        RoutingResult with intent, domain, zone, and dispatch info
    """
    router = get_router()
    return router.classify(user_input)


def reset_router() -> None:
    """
    Reset router instance (useful when switching profiles).

    Must be called after set_profile() to reload routing.config.
    """
    global _router_instance
    _router_instance = None
