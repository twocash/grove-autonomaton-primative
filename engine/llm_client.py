"""
llm_client.py - LLM Provider Abstraction Layer

Wraps the Anthropic Python SDK with mandatory telemetry logging.

CRITICAL INVARIANT (Ratchet Compliance):
Every LLM call MUST log telemetry with:
- model: The model used (e.g., claude-3-haiku-20240307)
- tokens_in: Input token count
- tokens_out: Output token count
- cost: Estimated cost in USD
- intent: The intent being served

Tier Routing:
- Tier 1: claude-3-haiku-20240307 (fast, cheap - for classification, extraction)
- Tier 2: claude-3-5-sonnet-20241022 (quality - for content generation)
- Tier 3: claude-3-opus-20240229 (apex - for Pit Crew skill generation, Architectural Judge)
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

from engine.profile import get_telemetry_dir


# =========================================================================
# Model Configuration
# =========================================================================

TIER_MODELS = {
    1: "claude-3-haiku-20240307",
    2: "claude-3-5-sonnet-20241022",
    3: "claude-3-opus-20240229",  # Apex tier for Pit Crew and Architectural Judge
}

# Pricing per million tokens (as of 2024)
MODEL_PRICING = {
    "claude-3-haiku-20240307": {
        "input": 0.25,   # $0.25 per million input tokens
        "output": 1.25,  # $1.25 per million output tokens
    },
    "claude-3-5-sonnet-20241022": {
        "input": 3.0,    # $3.00 per million input tokens
        "output": 15.0,  # $15.00 per million output tokens
    },
    "claude-3-opus-20240229": {
        "input": 15.0,   # $15.00 per million input tokens
        "output": 75.0,  # $75.00 per million output tokens
    },
}

DEFAULT_MAX_TOKENS = 1024


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
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-3-haiku-20240307"])

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
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """
    Call the LLM with the given prompt.

    Args:
        prompt: The user message to send
        tier: Model tier (1=Haiku for speed, 2=Sonnet for quality)
        intent: The intent being served (for telemetry)
        system: Optional system prompt
        max_tokens: Maximum response tokens

    Returns:
        The text content of the response

    Raises:
        LLMError: If the API call fails

    INVARIANT: Every call logs telemetry with model, tokens, cost, intent.
    """
    model = TIER_MODELS.get(tier, TIER_MODELS[1])

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
