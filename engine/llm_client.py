"""
llm_client.py - LLM Provider Abstraction Layer

Wraps the Anthropic Python SDK with mandatory telemetry logging.

CRITICAL INVARIANT (Ratchet Compliance):
Every LLM call MUST log telemetry with:
- model: The model used
- tokens_in: Input token count
- tokens_out: Output token count
- cost: Estimated cost in USD
- intent: The intent being served

Tier Routing (models.yaml is authoritative):
- Tier 1: Fast, cheap - for classification, extraction
- Tier 2: Quality - for content generation
- Tier 3: Apex - for Pit Crew skill generation, Architectural Judge

The engine dispatches to TIERS, not models. Model IDs are in models.yaml.
Fallback defaults exist ONLY as crash prevention for missing config.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

from engine.profile import get_telemetry_dir


# =========================================================================
# Model Configuration
# =========================================================================

# Fallback defaults — ONLY used if models.yaml is missing (crash prevention)
# models.yaml is AUTHORITATIVE. The engine dispatches to tiers, not models.
_DEFAULT_TIER_MODELS = {
    1: "claude-haiku-4-5-20251001",
    2: "claude-sonnet-4-6",
    3: "claude-opus-4-6",
}

_DEFAULT_MODEL_PRICING = {
    "claude-haiku-4-5-20251001": {
        "input": 0.80,   # $0.80 per million input tokens
        "output": 4.0,   # $4.00 per million output tokens
    },
    "claude-sonnet-4-6": {
        "input": 3.0,    # $3.00 per million input tokens
        "output": 15.0,  # $15.00 per million output tokens
    },
    "claude-opus-4-6": {
        "input": 15.0,   # $15.00 per million input tokens
        "output": 75.0,  # $75.00 per million output tokens
    },
}

_DEFAULT_MAX_TOKENS = 1024

# Cached config (loaded once per session)
_models_config_cache = None


def _load_models_config() -> dict:
    """
    Load model configuration from the active profile's models.yaml.

    Falls back to hardcoded defaults if config is missing or invalid.
    Purity v2: System never crashes on missing config.

    Returns dict with keys: 'tiers', 'pricing', 'default_max_tokens'
    """
    global _models_config_cache

    if _models_config_cache is not None:
        return _models_config_cache

    defaults = {
        "tiers": _DEFAULT_TIER_MODELS,
        "pricing": _DEFAULT_MODEL_PRICING,
        "default_max_tokens": _DEFAULT_MAX_TOKENS,
    }

    try:
        from engine.profile import get_config_dir
        import yaml

        config_dir = get_config_dir()
        models_path = config_dir / "models.yaml"

        if not models_path.exists():
            _models_config_cache = defaults
            return defaults

        with open(models_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            _models_config_cache = defaults
            return defaults

        # Parse tiers - convert string keys to int
        tiers = {}
        if "tiers" in config and isinstance(config["tiers"], dict):
            for tier_key, model_id in config["tiers"].items():
                try:
                    tier_int = int(tier_key)
                    tiers[tier_int] = str(model_id)
                except (ValueError, TypeError):
                    pass

        # Parse pricing
        pricing = {}
        if "pricing" in config and isinstance(config["pricing"], dict):
            for model_id, prices in config["pricing"].items():
                if isinstance(prices, dict):
                    pricing[str(model_id)] = {
                        "input": float(prices.get("input", 0.25)),
                        "output": float(prices.get("output", 1.25)),
                    }

        # Parse default_max_tokens
        default_max_tokens = int(config.get("default_max_tokens", _DEFAULT_MAX_TOKENS))

        # Use loaded values if valid, otherwise fall back to defaults
        _models_config_cache = {
            "tiers": tiers if tiers else _DEFAULT_TIER_MODELS,
            "pricing": pricing if pricing else _DEFAULT_MODEL_PRICING,
            "default_max_tokens": default_max_tokens,
        }

        return _models_config_cache

    except Exception:
        # Any error: use defaults (Purity v2: no crashes on config issues)
        _models_config_cache = defaults
        return defaults


def get_model_for_tier(tier: int) -> str:
    """Get the model ID for a given tier."""
    config = _load_models_config()
    return config["tiers"].get(tier, config["tiers"].get(1, _DEFAULT_TIER_MODELS[1]))


def get_model_pricing(model: str) -> dict:
    """Get pricing info for a model."""
    config = _load_models_config()
    return config["pricing"].get(model, _DEFAULT_MODEL_PRICING.get(
        model, {"input": 0.25, "output": 1.25}
    ))


def get_default_max_tokens() -> int:
    """Get the default max tokens setting."""
    config = _load_models_config()
    return config["default_max_tokens"]


# Reset config cache (for testing or profile switch)
def reset_models_config() -> None:
    """Reset the models config cache (call after profile switch)."""
    global _models_config_cache
    _models_config_cache = None


# =========================================================================
# Exceptions
# =========================================================================

class LLMError(Exception):
    """Raised when an LLM API call fails."""
    pass


# =========================================================================
# Client Management
# =========================================================================

_anthropic_client = None


def get_anthropic_client():
    """
    Get or create a singleton Anthropic client.

    Requires ANTHROPIC_API_KEY environment variable to be set.
    """
    global _anthropic_client

    if _anthropic_client is None:
        try:
            from anthropic import Anthropic
        except ImportError:
            raise LLMError(
                "anthropic package not installed. "
                "Install with: pip install anthropic"
            )

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMError(
                "ANTHROPIC_API_KEY environment variable not set"
            )

        _anthropic_client = Anthropic(api_key=api_key)

    return _anthropic_client


# =========================================================================
# Telemetry Logging
# =========================================================================

def log_llm_event(
    model: str,
    tokens_in: int,
    tokens_out: int,
    cost: float,
    intent: str,
    error: Optional[str] = None,
    **kwargs
) -> dict:
    """
    Log an LLM call event to the telemetry file.

    This is CRITICAL for Ratchet analysis - enables tracking of:
    - Token usage patterns
    - Cost accumulation
    - Model tier effectiveness
    - Intent-to-cost mapping

    Returns the logged event.
    """
    event = {
        "id": f"llm-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "llm_call",
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost": cost,
        "intent": intent,
    }

    if error:
        event["error"] = error

    # Include any additional fields
    event.update(kwargs)

    # Write to LLM-specific telemetry file
    telemetry_dir = get_telemetry_dir()
    telemetry_dir.mkdir(parents=True, exist_ok=True)

    llm_log_path = telemetry_dir / "llm_calls.jsonl"

    with open(llm_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")

    return event


def _calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """
    Calculate the estimated cost of an LLM call.

    Returns cost in USD.
    """
    pricing = get_model_pricing(model)

    input_cost = (tokens_in / 1_000_000) * pricing["input"]
    output_cost = (tokens_out / 1_000_000) * pricing["output"]

    return round(input_cost + output_cost, 8)


# =========================================================================
# Main API
# =========================================================================

def call_llm(
    prompt: str,
    tier: int = 1,
    intent: str = "unknown",
    system: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """
    Call the LLM with the given prompt.

    Args:
        prompt: The user message to send
        tier: Model tier (1=Haiku for speed, 2=Sonnet for quality)
        intent: The intent being served (for telemetry)
        system: Optional system prompt
        max_tokens: Maximum response tokens (defaults to config value)

    Returns:
        The text content of the response

    Raises:
        LLMError: If the API call fails

    INVARIANT: Every call logs telemetry with model, tokens, cost, intent.
    """
    model = get_model_for_tier(tier)
    if max_tokens is None:
        max_tokens = get_default_max_tokens()

    # Build messages
    messages = [{"role": "user", "content": prompt}]

    # Prepare API call kwargs
    api_kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }

    if system:
        api_kwargs["system"] = system

    try:
        client = get_anthropic_client()
        response = client.messages.create(**api_kwargs)

        # Extract usage
        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens

        # Calculate cost
        cost = _calculate_cost(model, tokens_in, tokens_out)

        # Log telemetry (CRITICAL - must happen before return)
        log_llm_event(
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            intent=intent,
        )

        # Extract text content
        if response.content and len(response.content) > 0:
            return response.content[0].text
        return ""

    except Exception as e:
        # Log the failed attempt
        log_llm_event(
            model=model,
            tokens_in=0,
            tokens_out=0,
            cost=0.0,
            intent=intent,
            error=str(e),
        )

        # Re-raise as LLMError
        raise LLMError(f"LLM API call failed: {e}") from e
