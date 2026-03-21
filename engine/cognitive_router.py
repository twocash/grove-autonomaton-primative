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
        # Pattern cache for the Ratchet (purity-audit-v1)
        self.pattern_cache: dict = {}
        self._cache_loaded = False

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

    def load_cache(self) -> bool:
        """Load pattern_cache.yaml from active profile.

        The pattern cache stores confirmed LLM classifications as Tier 0
        deterministic lookups. This is the Ratchet: every confirmed
        classification becomes free on repeat.
        """
        try:
            cache_path = get_config_dir() / "pattern_cache.yaml"
        except RuntimeError:
            return False
        if not cache_path.exists():
            self.pattern_cache = {}
            self._cache_loaded = True
            return True
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self.pattern_cache = data.get("cache", {})
            self._cache_loaded = True
            return True
        except Exception:
            self.pattern_cache = {}
            self._cache_loaded = True
            return False

    def _check_pattern_cache(self, user_input: str) -> Optional[RoutingResult]:
        """Check if input matches a cached LLM classification.

        Returns RoutingResult at Tier 0 if cache hit, None if miss.
        This is the Ratchet read path: confirmed patterns skip the LLM.
        """
        if not self._cache_loaded:
            self.load_cache()

        import hashlib
        input_hash = hashlib.sha256(
            user_input.lower().strip().encode()
        ).hexdigest()[:16]

        entry = self.pattern_cache.get(input_hash)
        if entry is None:
            return None

        # Validate the cached intent still exists in routing config
        intent = entry.get("intent", "unknown")
        if intent not in self.routes and intent != "unknown":
            return None  # Stale cache entry — route was removed

        # Log cache hit for Ratchet telemetry (Task B.5, Purity v2 flat fields)
        try:
            from engine.telemetry import log_event
            log_event(
                source="cognitive_router",
                raw_transcript=user_input[:200],
                zone_context=entry.get("zone", "green"),
                intent=intent,
                tier=0,
                confidence=min(0.7 + (entry.get("confirmed_count", 1) * 0.05), 0.99),
                inferred={
                    "cache_hit": True,
                    "cache_hash": input_hash,
                    "confirmed_count": entry.get("confirmed_count", 1),
                    "cost_saved": "tier_2_call_avoided"
                }
            )
        except Exception:
            pass  # Telemetry failure is non-fatal for cache reads

        return RoutingResult(
            intent=intent,
            domain=entry.get("domain", "general"),
            zone=entry.get("zone", "yellow"),
            tier=0,  # THE RATCHET: Tier 0, zero cost
            confidence=min(0.7 + (entry.get("confirmed_count", 1) * 0.05), 0.99),
            handler=entry.get("handler"),
            handler_args=entry.get("handler_args", {}),
            extracted_args={},
            intent_type=entry.get("intent_type", "actionable"),
            action_required=entry.get("intent_type") != "conversational",
            llm_metadata={
                "source": "pattern_cache",
                "cache_hash": input_hash,
                "entities": entry.get("entities", {}),
                "sentiment": entry.get("sentiment", "neutral"),
            }
        )

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

        # If no match or low confidence: cache check, then LLM escalation
        if best_match is None or best_match[2] < self.LLM_ESCALATION_THRESHOLD:
            # THE RATCHET: Check pattern cache (Tier 0, free)
            cache_result = self._check_pattern_cache(user_input)
            if cache_result is not None:
                return cache_result
            # No keyword match, no cache hit. Return unknown.
            # The LLM is NOT called here. LLM calls cost money.
            # Money is an action. Actions go through Stage 4.
            # Stage 4 will offer the Kaizen prompt.
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
            tier=1,  # Keyword matching (T1) ran. It found nothing.
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
        Direct LLM call for intent classification.

        V-001: This is Stage 2 infrastructure — NOT a pipeline traversal.
        The pipeline is for operator interactions. Classification is an
        implementation detail of Recognition.

        Reads the prompt template from config, calls call_llm() directly,
        parses the JSON classification, returns a RoutingResult.
        """
        import json
        from engine.llm_client import call_llm
        from engine.telemetry import log_event

        valid_intents = list(self.routes.keys())
        if not valid_intents:
            return None

        # Build intent descriptions for the prompt
        intent_lines = []
        for name, cfg in self.routes.items():
            desc = cfg.get("description", name)
            intent_lines.append(f"- {name}: {desc[:80]}")
        available_intents = "\n".join(intent_lines[:20])

        # Load prompt template (inline fallback if missing)
        try:
            tpl_path = get_config_dir() / "cognitive-router" / "prompts" / "classify_intent.md"
            if tpl_path.exists():
                prompt = tpl_path.read_text(encoding="utf-8")
                prompt = prompt.replace("{user_input}", user_input)
                prompt = prompt.replace("{available_intents}", available_intents)
            else:
                prompt = (
                    f'Classify this input: "{user_input}"\n\n'
                    f'Available intents:\n{available_intents}\n\n'
                    f'Return ONLY valid JSON: {{"intent":"<name>","confidence":<0-1>,'
                    f'"reasoning":"<why>","intent_type":"<conversational|informational|actionable>",'
                    f'"action_required":<true|false>}}'
                )
        except RuntimeError:
            return None

        try:
            response = call_llm(
                prompt=prompt,
                tier=2,
                intent="llm_intent_classify"
            )

            # Parse JSON from response
            json_str = response.strip()
            start_idx = json_str.find('{')
            end_idx = json_str.rfind('}')
            if start_idx != -1 and end_idx != -1:
                json_str = json_str[start_idx:end_idx + 1]
            result = json.loads(json_str)

            classified_intent = str(result.get("intent", "unknown")).lower()
            confidence = float(result.get("confidence", 0.5))
            intent_type = result.get("intent_type", "actionable")
            action_required = result.get("action_required", True)
            llm_metadata = {
                "source": "llm_classify",
                "reasoning": result.get("reasoning", ""),
                "classification_confidence": confidence,
                "entities": result.get("entities", {}),
                "sentiment": result.get("sentiment", "neutral"),
            }

            log_event(
                source="cognitive_router",
                raw_transcript=user_input[:200],
                zone_context="green",
                intent=classified_intent,
                tier=2,
                confidence=confidence,
                inferred={"stage": "llm_classification", "method": "direct_call"}
            )

            if classified_intent in valid_intents:
                rc = self.routes[classified_intent]
                return RoutingResult(
                    intent=classified_intent,
                    domain=rc.get("domain", "general"),
                    zone=rc.get("zone", "yellow"),
                    tier=rc.get("tier", 2),
                    confidence=confidence,
                    handler=rc.get("handler"),
                    handler_args=rc.get("handler_args", {}),
                    extracted_args={},
                    intent_type=intent_type,
                    action_required=action_required,
                    llm_metadata=llm_metadata,
                )

            return RoutingResult(
                intent="unknown", domain="general", zone="yellow", tier=2,
                confidence=confidence, handler=None, handler_args={},
                extracted_args={}, intent_type=intent_type,
                action_required=action_required, llm_metadata=llm_metadata,
            )

        except Exception as e:
            try:
                log_event(
                    source="cognitive_router",
                    raw_transcript=user_input[:200],
                    zone_context="yellow", intent="unknown", tier=2,
                    inferred={"error": str(e), "error_type": type(e).__name__,
                              "stage": "llm_escalation_error"}
                )
            except Exception:
                pass
            return None


# =========================================================================
# Clarification Jidoka
# =========================================================================

def get_clarification_options() -> dict:
    """Load fallback clarification options from profile config.

    Reads clarification.yaml from the active profile. If missing,
    returns minimal generic fallback. Zero hardcoded domain logic.
    """
    import yaml
    from engine.profile import get_config_dir

    try:
        config_path = get_config_dir() / "clarification.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            options = {}
            for key, entry in data.get("fallback_options", {}).items():
                options[str(key)] = entry.get("label", f"Option {key}")
            if options:
                return options
    except Exception:
        pass

    # Absolute minimal fallback (no domain assumptions)
    return {
        "1": "Start a conversation about this",
        "2": "I'll rephrase with more context",
    }


def resolve_clarification(choice: str, original_input: str) -> RoutingResult:
    """Resolve a clarification choice using profile config.

    Maps the user's choice to an intent declared in BOTH
    clarification.yaml AND the active routing.config. If the
    intent doesn't exist in routing.config, falls back to
    general_chat. Zero hardcoded domain logic.
    """
    import yaml
    from engine.profile import get_config_dir

    resolved_intent = None

    try:
        config_path = get_config_dir() / "clarification.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            entry = data.get("fallback_options", {}).get(choice, {})
            resolved_intent = entry.get("intent")
    except Exception:
        pass

    # null intent = user wants to rephrase (cancel)
    if resolved_intent is None:
        return RoutingResult(
            intent="general_chat",
            domain="system",
            zone="green",
            tier=1,
            confidence=1.0,
            handler="general_chat",
            intent_type="conversational",
            action_required=False,
            llm_metadata={"clarified_from": original_input, "action": "rephrase"}
        )

    # Validate intent exists in active routing.config
    router = get_router()
    if resolved_intent in router.routes:
        route = router.routes[resolved_intent]
        return RoutingResult(
            intent=resolved_intent,
            domain=route.get("domain", "system"),
            zone=route.get("zone", "green"),
            tier=route.get("tier", 1),
            confidence=1.0,
            handler=route.get("handler"),
            handler_args=route.get("handler_args", {}),
            intent_type=route.get("intent_type", "actionable"),
            action_required=route.get("intent_type") != "conversational",
            llm_metadata={"clarified_from": original_input}
        )

    # Intent in clarification.yaml but not in routing.config — fallback
    return RoutingResult(
        intent="general_chat",
        domain="system",
        zone="green",
        tier=1,
        confidence=1.0,
        handler="general_chat",
        intent_type="conversational",
        action_required=False,
        llm_metadata={"clarified_from": original_input, "fallback": True}
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
