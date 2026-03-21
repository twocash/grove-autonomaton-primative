"""
cognitive_router.py — Config-Driven Intent Lookup

A pure lookup function. Reads routing.config, checks cache, does keyword
matching, returns a result. No LLM. No telemetry. No escalation.

Three paths:
1. Cache hit → Tier 0, return immediately
2. Keyword match → Tier 1, return match
3. No match → return unknown (Stage 4 handles it)
"""

import re
import hashlib
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from engine.profile import get_config_dir


@dataclass
class RoutingResult:
    """Result of cognitive routing."""
    intent: str
    domain: str
    zone: str
    tier: int
    confidence: float
    handler: Optional[str] = None
    handler_args: dict = field(default_factory=dict)
    extracted_args: dict = field(default_factory=dict)
    intent_type: str = "actionable"
    action_required: bool = True
    llm_metadata: dict = field(default_factory=dict)
    classification_source: str = "unknown"  # "cache" | "keyword" | "llm" | "unknown"


class CognitiveRouter:
    """Config-driven intent classifier. Pure lookup, no LLM."""

    def __init__(self):
        self.config: dict = {}
        self.routes: dict = {}
        self.matching: dict = {}
        self.cache_config: dict = {}
        self.cache: dict = {}
        self._loaded = False

    def load_config(self) -> bool:
        """Load routing.config and pattern_cache.yaml from active profile."""
        try:
            config_path = get_config_dir() / "routing.config"
        except RuntimeError:
            return False
        if not config_path.exists():
            return False
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
        except Exception:
            return False

        self.routes = self.config.get("routes", {})
        self.matching = self.config.get("router", {}).get("matching", {
            "confidence": {"exact": 1.0, "prefix": 0.9, "contains": 0.5},
            "min_confidence": 0.7,
            "word_boundary_min_length": 4
        })
        self.cache_config = self.config.get("cache", {
            "enabled": True, "base_confidence": 0.75,
            "confidence_increment": 0.05, "max_confidence": 0.99
        })
        self._loaded = True
        self.load_cache()
        return True

    def load_cache(self) -> bool:
        """Load pattern_cache.yaml into memory."""
        try:
            cache_path = get_config_dir() / "pattern_cache.yaml"
            if cache_path.exists():
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self.cache = data.get("cache", {})
            else:
                self.cache = {}
            return True
        except Exception:
            self.cache = {}
            return False

    def classify(self, user_input: str) -> RoutingResult:
        """Classify input: cache → keyword → unknown. No LLM."""
        if not self._loaded:
            self.load_config()
        if not user_input or not user_input.strip():
            return self._unknown_result()

        # Tier 0: Cache check
        if self.cache_config.get("enabled", True):
            cache_result = self._check_cache(user_input)
            if cache_result:
                return cache_result

        # Tier 1: Keyword match
        match = self._keyword_match(user_input)
        if match:
            return match

        # No match
        return self._unknown_result()

    def _check_cache(self, user_input: str) -> Optional[RoutingResult]:
        """Check pattern cache. Returns Tier 0 result or None."""
        input_hash = hashlib.sha256(user_input.lower().strip().encode()).hexdigest()[:16]
        entry = self.cache.get(input_hash)
        if not entry:
            return None
        intent = entry.get("intent", "unknown")
        if intent not in self.routes and intent != "unknown":
            return None  # Stale entry
        confirmed = entry.get("confirmed_count", 1)
        conf = min(
            self.cache_config.get("base_confidence", 0.75) +
            (confirmed * self.cache_config.get("confidence_increment", 0.05)),
            self.cache_config.get("max_confidence", 0.99)
        )
        return RoutingResult(
            intent=intent, domain=entry.get("domain", "general"),
            zone=entry.get("zone", "yellow"), tier=0, confidence=conf,
            handler=entry.get("handler"), handler_args=entry.get("handler_args", {}),
            intent_type=entry.get("intent_type", "actionable"),
            action_required=entry.get("intent_type") != "conversational",
            llm_metadata={"source": "pattern_cache", "cache_hash": input_hash},
            classification_source="cache"
        )

    def _keyword_match(self, user_input: str) -> Optional[RoutingResult]:
        """Keyword matching per config. Returns best match or None."""
        normalized = user_input.lower().strip()
        conf_exact = self.matching.get("confidence", {}).get("exact", 1.0)
        conf_prefix = self.matching.get("confidence", {}).get("prefix", 0.9)
        conf_contains = self.matching.get("confidence", {}).get("contains", 0.5)
        min_conf = self.matching.get("min_confidence", 0.7)
        word_boundary_min = self.matching.get("word_boundary_min_length", 4)

        best = None  # (intent, route, confidence)
        for intent_name, route in self.routes.items():
            for kw in route.get("keywords", []):
                kw_lower = kw.lower()
                score = 0.0
                if normalized == kw_lower:
                    score = conf_exact
                elif normalized.startswith(kw_lower + " ") or normalized.startswith(kw_lower):
                    score = conf_prefix
                elif kw_lower in normalized:
                    if len(kw_lower) < word_boundary_min:
                        if re.search(r'\b' + re.escape(kw_lower) + r'\b', normalized):
                            score = conf_contains
                    else:
                        score = conf_contains
                if score > 0 and (best is None or score > best[2]):
                    best = (intent_name, route, score)

        if not best or best[2] < min_conf:
            return None

        intent_name, route, confidence = best
        intent_type = route.get("intent_type", "actionable")
        return RoutingResult(
            intent=intent_name, domain=route.get("domain", "general"),
            zone=route.get("zone", "yellow"), tier=route.get("tier", 1),
            confidence=confidence, handler=route.get("handler"),
            handler_args=route.get("handler_args", {}),
            extracted_args=self._extract_args(user_input, route.get("extract_args", [])),
            intent_type=intent_type, action_required=intent_type != "conversational",
            classification_source="keyword"
        )

    def _extract_args(self, user_input: str, specs: list) -> dict:
        """Extract positional arguments from input."""
        parts = user_input.split()
        result = {}
        for spec in specs:
            name, pos = spec.get("name"), spec.get("position")
            if name and pos is not None and pos < len(parts):
                result[name] = " ".join(parts[pos:])
        return result

    def _unknown_result(self) -> RoutingResult:
        """Return unknown result. Stage 4 handles via Kaizen."""
        return RoutingResult(
            intent="unknown", domain="general", zone="yellow", tier=1,
            confidence=0.0, classification_source="unknown"
        )

    def get_route_descriptions(self) -> dict:
        """Returns {intent: description} for LLM classification prompt."""
        return {name: route.get("description", name)
                for name, route in self.routes.items()}


# Module interface
_router: Optional[CognitiveRouter] = None

def get_router() -> CognitiveRouter:
    global _router
    if _router is None:
        _router = CognitiveRouter()
        _router.load_config()
    return _router

def classify_intent(user_input: str) -> RoutingResult:
    return get_router().classify(user_input)

def reset_router() -> None:
    global _router
    _router = None

# Clarification support (Stage 4 reads these)
def get_clarification_options() -> dict:
    """Load clarification options from profile config."""
    try:
        path = get_config_dir() / "clarification.yaml"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            opts = {str(k): v.get("label", f"Option {k}")
                    for k, v in data.get("fallback_options", {}).items()}
            if opts:
                return opts
    except Exception:
        pass
    return {"1": "Start a conversation", "2": "I'll rephrase"}

def resolve_clarification(choice: str, original_input: str) -> RoutingResult:
    """Resolve clarification choice to a RoutingResult."""
    try:
        path = get_config_dir() / "clarification.yaml"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            intent = data.get("fallback_options", {}).get(choice, {}).get("intent")
            if intent:
                router = get_router()
                if intent in router.routes:
                    r = router.routes[intent]
                    return RoutingResult(
                        intent=intent, domain=r.get("domain", "system"),
                        zone=r.get("zone", "green"), tier=r.get("tier", 1),
                        confidence=1.0, handler=r.get("handler"),
                        handler_args=r.get("handler_args", {}),
                        intent_type=r.get("intent_type", "actionable"),
                        action_required=r.get("intent_type") != "conversational",
                        classification_source="clarification"
                    )
    except Exception:
        pass
    return RoutingResult(
        intent="general_chat", domain="system", zone="green", tier=1,
        confidence=1.0, handler="general_chat", intent_type="conversational",
        action_required=False, classification_source="clarification"
    )
