"""
cognitive_router.py - Hybrid Intent Classification (Tier 0 + Tier 1)

Implements two-tier intent classification:
- Tier 0: Fast keyword-based matching from routing.config
- Tier 1: LLM escalation for ambiguous input (confidence < 0.7)

Architectural Invariants Enforced:
- #2 Config Over Code: Domain logic loaded from routing.config YAML
- #3 Zone Governance: Every intent has declared zone from config
- #4 Digital Jidoka: Unknown intents trigger clarification, not blanket approval

Sprint 8: Enriched LLM classification with structured output for Ratchet data.
- LLM returns intent_type, action_required, entities, content_seeds, sentiment
- Every LLM classification logged to telemetry for Ratchet analysis
- Clarification Jidoka for truly ambiguous input (confidence < 0.5)
"""

import json
import time
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

    Sprint 8 additions:
    - intent_type: conversational, informational, actionable
    - action_required: Whether this needs execution (vs just conversation)
    - llm_metadata: Rich extraction from LLM classification (entities, seeds, sentiment)
    """
    intent: str
    domain: str
    zone: str
    tier: int
    confidence: float
    handler: Optional[str] = None
    handler_args: dict = field(default_factory=dict)
    extracted_args: dict = field(default_factory=dict)
    # Sprint 8: Enriched routing metadata
    intent_type: str = "actionable"  # conversational, informational, actionable
    action_required: bool = True  # False for conversational = skip approval UX
    llm_metadata: dict = field(default_factory=dict)  # entities, content_seeds, sentiment


class CognitiveRouter:
    """
    Hybrid Tier 0/1 intent classifier.

    Tier 0 (Keyword Matching):
    - Loads routing.config from the active profile
    - Matches user input against declared keyword patterns
    - Fast, no API calls

    Tier 1 (LLM Escalation):
    - Activated when Tier 0 confidence < 0.7
    - Uses Haiku for cost efficiency
    - Returns structured JSON with intent_type, action_required, entities, etc.
    - Every call logged to telemetry for Ratchet analysis

    Matching Strategy:
    1. Exact match on keywords (confidence: 1.0)
    2. Prefix match - input starts with keyword (confidence: 0.9)
    3. Contains match (confidence: 0.5)
    4. LLM classification for low confidence inputs

    Unknown inputs with low confidence trigger clarification Jidoka.
    """

    # Confidence threshold for LLM escalation
    LLM_ESCALATION_THRESHOLD = 0.7

    # Confidence threshold for clarification Jidoka
    # Below this, we ask the user what they want instead of guessing
    CLARIFICATION_THRESHOLD = 0.5

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

    def reload_config(self) -> bool:
        """
        Reload routing.config (hot reload).

        Sprint 4: Called by Pit Crew after skill registration
        to make new skills immediately invocable.

        Returns:
            True if reload successful, False otherwise.
        """
        # Reset loaded state and reload
        self._loaded = False
        self.routes = {}
        self.tiers = {}
        return self.load_config()

    def classify(self, user_input: str) -> RoutingResult:
        """
        Classify user input and return routing result.

        Args:
            user_input: Raw user input string

        Returns:
            RoutingResult with intent, domain, zone, tier, confidence,
            handler information, intent_type, and action_required.
        """
        if not self._loaded:
            self.load_config()

        if not self.routes:
            return self._create_default_result()

        normalized_input = user_input.lower().strip()

        # Empty input defaults to unknown
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
                # Require word boundary match for short keywords to avoid
                # false positives (e.g. "hi" in "nothing")
                elif keyword_lower in normalized_input:
                    # Check word boundaries for short keywords (< 4 chars)
                    if len(keyword_lower) < 4:
                        # Must be surrounded by word boundaries
                        import re
                        pattern = r'\b' + re.escape(keyword_lower) + r'\b'
                        if re.search(pattern, normalized_input):
                            confidence = 0.5
                    else:
                        confidence = 0.5

                if confidence > 0:
                    if best_match is None or confidence > best_match[2]:
                        best_match = (intent_name, route_config, confidence)

        # If no match or low confidence, try LLM escalation
        if best_match is None or best_match[2] < self.LLM_ESCALATION_THRESHOLD:
            llm_result = self._escalate_to_llm(user_input)
            if llm_result is not None:
                return llm_result
            # If LLM fails and we had no keyword match, return default
            if best_match is None:
                return self._create_default_result()

        intent_name, route_config, confidence = best_match

        # Extract arguments if specified in config
        extracted_args = self._extract_arguments(
            user_input,
            route_config.get("extract_args", [])
        )

        # Get intent_type from config, default based on zone
        intent_type = route_config.get("intent_type")
        if not intent_type:
            # Infer from zone if not specified
            zone = route_config.get("zone", "yellow")
            intent_type = "actionable" if zone in ("yellow", "red") else "informational"

        # action_required is False for conversational intents
        action_required = intent_type != "conversational"

        return RoutingResult(
            intent=intent_name,
            domain=route_config.get("domain", "general"),
            zone=route_config.get("zone", "yellow"),
            tier=route_config.get("tier", 2),
            confidence=confidence,
            handler=route_config.get("handler"),
            handler_args=route_config.get("handler_args", {}),
            extracted_args=extracted_args,
            intent_type=intent_type,
            action_required=action_required,
            llm_metadata={}
        )

    def _create_default_result(self) -> RoutingResult:
        """
        Create a default result for unknown intents.

        Note: Unknown intents now trigger clarification Jidoka
        instead of blanket yellow zone approval.
        """
        return RoutingResult(
            intent="unknown",
            domain="general",
            zone="yellow",
            tier=2,
            confidence=0.0,
            handler=None,
            handler_args={},
            extracted_args={},
            intent_type="actionable",
            action_required=True,  # Will trigger clarification Jidoka
            llm_metadata={}
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

    def _escalate_to_llm(self, user_input: str) -> Optional[RoutingResult]:
        """
        Escalate to Tier 2 LLM for structured intent classification.

        Uses Sonnet for reliable natural language understanding.
        Haiku is too brittle for compound inputs and conversational phrasing.

        Every classification is logged to telemetry for Ratchet analysis.

        Args:
            user_input: The ambiguous user input

        Returns:
            RoutingResult if LLM successfully classifies, None on failure
        """
        try:
            from engine.llm_client import call_llm
            from engine.telemetry import log_event
        except ImportError:
            return None

        # Build list of valid intents from config (ALL intents now, including general_chat)
        valid_intents = list(self.routes.keys())
        if not valid_intents:
            return None

        # Create intent descriptions for LLM context
        intent_descriptions = []
        for intent_name, route_config in self.routes.items():
            desc = route_config.get("description", intent_name)
            intent_type = route_config.get("intent_type", "actionable")
            zone = route_config.get("zone", "yellow")
            intent_descriptions.append(
                f"- {intent_name} (type: {intent_type}, zone: {zone}): {desc}"
            )

        # Structured classification prompt — concise, Sonnet-grade
        prompt = f"""You are an intent classifier. Given a user input and a list of valid intents, return a JSON object classifying the input.

Valid intents:
{chr(10).join(intent_descriptions)}

User input: "{user_input}"

Return ONLY a JSON object:
{{
  "intent": "<one of the intent names above, or 'unknown'>",
  "intent_type": "<conversational|informational|actionable>",
  "confidence": <0.0-1.0>,
  "action_required": <true|false>,
  "reasoning": "<one sentence>"
}}

Classification rules:
- Match to the CLOSEST valid intent, even if the wording is informal or indirect.
- Greetings, thanks, farewells, acknowledgments, small talk → general_chat (conversational, action_required: false)
- If the user mentions content, drafting, TikTok, Instagram, social media, posts → content_draft or content_compilation
- If the user asks about status, progress, what's loaded → informational intents
- If the user wants to DO something (schedule, build, compile, prepare) → actionable intents
- Compound inputs (multiple topics in one message): classify by the PRIMARY actionable intent.
- Only return "unknown" if you genuinely cannot determine what the user wants. Prefer a best-guess match over unknown.

JSON:"""

        start_time = time.time()

        try:
            response = call_llm(
                prompt=prompt,
                tier=2,  # Sonnet — Haiku is too brittle for natural language classification
                intent="intent_classification"
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Parse JSON response
            try:
                # Robust JSON extraction — find JSON object regardless of wrapping
                # Handles: clean JSON, markdown code blocks, prose preamble, etc.
                json_str = response.strip()
                start_idx = json_str.find('{')
                end_idx = json_str.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = json_str[start_idx:end_idx + 1]
                classification = json.loads(json_str)
            except json.JSONDecodeError:
                # Fallback: try to extract just the intent
                classified_intent = response.strip().lower()
                if classified_intent in valid_intents:
                    classification = {"intent": classified_intent, "confidence": 0.6}
                else:
                    classification = {"intent": "unknown", "confidence": 0.3}

            # Log classification to telemetry for Ratchet
            log_event(
                source="cognitive_router",
                raw_transcript=user_input[:200],
                zone_context="classification",
                inferred={
                    "classification_tier": 2,
                    "model": "claude-sonnet",
                    "latency_ms": latency_ms,
                    "input_text": user_input,
                    "output": classification
                }
            )

            # Extract fields from classification
            classified_intent = classification.get("intent", "unknown").lower()
            confidence = float(classification.get("confidence", 0.5))
            intent_type = classification.get("intent_type", "actionable")
            action_required = classification.get("action_required", True)

            # Build llm_metadata for downstream use
            llm_metadata = {
                "reasoning": classification.get("reasoning", ""),
                "classification_confidence": confidence
            }

            # Validate intent against declared routes
            if classified_intent in valid_intents:
                route_config = self.routes[classified_intent]
                return RoutingResult(
                    intent=classified_intent,
                    domain=route_config.get("domain", "general"),
                    zone=route_config.get("zone", "yellow"),
                    tier=route_config.get("tier", 2),
                    confidence=confidence,
                    handler=route_config.get("handler"),
                    handler_args=route_config.get("handler_args", {}),
                    extracted_args={},
                    intent_type=intent_type,
                    action_required=action_required,
                    llm_metadata=llm_metadata
                )

            # LLM returned unknown - pass through metadata for clarification
            return RoutingResult(
                intent="unknown",
                domain="general",
                zone="yellow",
                tier=2,
                confidence=confidence,
                handler=None,
                handler_args={},
                extracted_args={},
                intent_type=intent_type,
                action_required=action_required,
                llm_metadata=llm_metadata
            )

        except Exception as e:
            # Log failure
            try:
                log_event(
                    source="cognitive_router",
                    raw_transcript=user_input[:200],
                    zone_context="classification_error",
                    inferred={
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
            except Exception:
                pass
            return None


# =========================================================================
# Clarification Jidoka
# =========================================================================

def get_clarification_options() -> dict:
    """
    Get the standard clarification options for ambiguous input.

    Returns options dict for ask_jidoka.
    """
    return {
        "1": "Draft or compile content",
        "2": "Schedule something",
        "3": "Check on status/information",
        "4": "Just chatting"
    }


def resolve_clarification(choice: str, original_input: str) -> RoutingResult:
    """
    Resolve a clarification choice to a RoutingResult.

    Args:
        choice: The user's choice ("1", "2", "3", or "4")
        original_input: The original ambiguous input

    Returns:
        RoutingResult based on clarification
    """
    if choice == "1":
        # Content work
        return RoutingResult(
            intent="content_draft",
            domain="content",
            zone="green",
            tier=1,
            confidence=1.0,
            handler=None,
            intent_type="actionable",
            action_required=True,
            llm_metadata={"clarified_from": original_input}
        )
    elif choice == "2":
        # Scheduling
        return RoutingResult(
            intent="calendar_schedule",
            domain="lessons",
            zone="yellow",
            tier=2,
            confidence=1.0,
            handler="mcp_calendar",
            handler_args={"server": "google_calendar", "capability": "create_event"},
            intent_type="actionable",
            action_required=True,
            llm_metadata={"clarified_from": original_input}
        )
    elif choice == "3":
        # Status/information
        return RoutingResult(
            intent="dock_status",
            domain="system",
            zone="green",
            tier=1,
            confidence=1.0,
            handler="status_display",
            handler_args={"display_type": "dock"},
            intent_type="informational",
            action_required=False,
            llm_metadata={"clarified_from": original_input}
        )
    else:
        # Just chatting (default)
        return RoutingResult(
            intent="general_chat",
            domain="system",
            zone="green",
            tier=1,
            confidence=1.0,
            handler="general_chat",
            intent_type="conversational",
            action_required=False,
            llm_metadata={"clarified_from": original_input}
        )


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
        RoutingResult with intent, domain, zone, dispatch info,
        intent_type, action_required, and llm_metadata
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
