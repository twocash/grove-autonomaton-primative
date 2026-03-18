"""
ratchet.py - Universal Ratchet Classification

ADR-001: Every classification task MUST use ratchet_classify().
The two-layer architecture: deterministic first (free) -> pipeline interpretation (through cognitive router).

The Ratchet is the OPTIMIZATION PATTERN. The Cognitive Router is the STRUCTURE.
This module provides the universal function that enforces the pattern.

Architectural Invariants Enforced:
- #1 Invariant Pipeline: The interpret layer routes THROUGH the pipeline, not around it
- #2 Config Over Code: Deterministic rules and prompt templates declared in config
- #5 Feed-First Telemetry: Every classification logged with standardized schema
- #12 Ratchet Classification: No raw call_llm() for classification without deterministic first pass
"""

from dataclasses import dataclass
from typing import TypeVar, Optional, Callable, Generic, Any
import time

T = TypeVar('T')


@dataclass
class RatchetResult(Generic[T]):
    """
    Result of a ratchet classification.

    Attributes:
        result: The classification result (None if both layers failed)
        source: Which layer produced this - "deterministic" | "pipeline" | "none"
        confidence: Confidence score 0.0-1.0
        latency_ms: Total classification latency in milliseconds
        label: Which classifier produced this (for telemetry grouping)
    """
    result: Optional[T]
    source: str  # "deterministic" | "pipeline" | "none"
    confidence: float
    latency_ms: int
    label: str


@dataclass
class RatchetConfig(Generic[T]):
    """
    Configuration for a ratchet classification task.

    The deterministic layer is a function that reads from config
    (routing.config keywords, cortex.yaml rules, etc.).

    The interpret layer is NOT a raw LLM call. It declares a
    pipeline route - a classification intent in routing.config
    that the cognitive router handles like any other intent.
    This ensures the interpret layer goes through all 5 stages:
    Telemetry -> Recognition -> Compilation -> Approval -> Execution.

    Attributes:
        label: Classifier name for telemetry grouping ("intent", "entity_extraction", etc.)
        deterministic: Function that reads config and returns (result, confidence) or None
        interpret_route: routing.config intent name for LLM classification fallback
        threshold: Confidence threshold - below this, escalate to pipeline (default 0.7)
    """
    label: str
    deterministic: Callable[[str], Optional[tuple]]
    interpret_route: str
    threshold: float = 0.7


def ratchet_classify(
    input_text: str,
    config: RatchetConfig,
    context: Optional[dict] = None
) -> RatchetResult:
    """
    Universal ratchet classification.

    Layer 1: Run deterministic function (free, reads from config).
    Layer 2: If deterministic misses or low confidence, route through the
             INVARIANT PIPELINE via the cognitive router. The interpret_route
             declares which routing.config intent handles the classification.
             This ensures the LLM call goes through all 5 stages.
    Always: Log to telemetry with standardized schema.

    CRITICAL: The interpret layer is a PIPELINE TRAVERSAL, not a raw
    call_llm(). This is Invariant #1. No bypass paths.

    Args:
        input_text: The text to classify
        config: RatchetConfig with deterministic function and pipeline route
        context: Optional additional context for the classification

    Returns:
        RatchetResult with result, source, confidence, latency
    """
    from engine.telemetry import log_event

    start_time = time.time()

    # Layer 1: Deterministic (free)
    det_result = None
    try:
        det_result = config.deterministic(input_text)
    except Exception as e:
        # Deterministic layer failed - log and continue to pipeline
        log_event(
            source=f"ratchet:{config.label}",
            raw_transcript=input_text[:200],
            zone_context="yellow",
            inferred={
                "classifier": config.label,
                "stage": "deterministic_error",
                "error": str(e),
                "error_type": type(e).__name__
            }
        )

    if det_result is not None:
        result, confidence = det_result
        if confidence >= config.threshold:
            latency_ms = int((time.time() - start_time) * 1000)

            # Log deterministic hit
            log_event(
                source=f"ratchet:{config.label}",
                raw_transcript=input_text[:200],
                zone_context="green",
                inferred={
                    "classifier": config.label,
                    "source": "deterministic",
                    "result": str(result) if result is not None else None,
                    "confidence": confidence,
                    "latency_ms": latency_ms,
                    "tier": 0
                }
            )

            return RatchetResult(
                result=result,
                source="deterministic",
                confidence=confidence,
                latency_ms=latency_ms,
                label=config.label
            )

    # Layer 2: Pipeline Interpretation (through the invariant pipeline)
    # NOT a raw call_llm(). Route through the cognitive router.
    from engine.pipeline import run_pipeline

    try:
        # Build the pipeline input - the interpret_route tells the router
        # which classification handler to use
        pipeline_input = input_text
        if context:
            # Include context in the pipeline metadata
            pass  # Context flows through pipeline.context.entities

        pipeline_context = run_pipeline(
            raw_input=pipeline_input,
            source=f"ratchet:{config.label}",
            force_route=config.interpret_route  # Force routing to the classification handler
        )

        latency_ms = int((time.time() - start_time) * 1000)

        if pipeline_context.executed and pipeline_context.result:
            result_data = pipeline_context.result

            # The ratchet_interpreter handler returns classification in data
            if isinstance(result_data, dict):
                classification = result_data.get("data", {}).get("classification")
                confidence = result_data.get("data", {}).get("confidence", 0.5)
            else:
                classification = None
                confidence = 0.0

            if classification is not None:
                # Log the pipeline classification
                log_event(
                    source=f"ratchet:{config.label}",
                    raw_transcript=input_text[:200],
                    zone_context="green",
                    inferred={
                        "classifier": config.label,
                        "source": "pipeline",
                        "result": str(classification),
                        "confidence": confidence,
                        "latency_ms": latency_ms,
                        "interpret_route": config.interpret_route,
                        "tier": _get_tier_for_route(config.interpret_route),
                        "deterministic_miss": True,
                        "deterministic_partial": str(det_result) if det_result else None
                    }
                )

                return RatchetResult(
                    result=classification,
                    source="pipeline",
                    confidence=confidence,
                    latency_ms=latency_ms,
                    label=config.label
                )

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        log_event(
            source=f"ratchet:{config.label}",
            raw_transcript=input_text[:200],
            zone_context="yellow",
            inferred={
                "classifier": config.label,
                "stage": "pipeline_error",
                "error": str(e),
                "error_type": type(e).__name__,
                "interpret_route": config.interpret_route,
                "latency_ms": latency_ms
            }
        )

    # Both layers failed
    latency_ms = int((time.time() - start_time) * 1000)

    log_event(
        source=f"ratchet:{config.label}",
        raw_transcript=input_text[:200],
        zone_context="yellow",
        inferred={
            "classifier": config.label,
            "source": "none",
            "latency_ms": latency_ms,
            "interpret_route": config.interpret_route,
            "deterministic_partial": str(det_result) if det_result else None
        }
    )

    return RatchetResult(
        result=None,
        source="none",
        confidence=0.0,
        latency_ms=latency_ms,
        label=config.label
    )


def _get_tier_for_route(route_name: str) -> int:
    """
    Get the LLM tier for a routing.config route.

    Reads from routing.config to determine which tier the route uses.
    Returns 1 (Haiku) as default if route not found.
    """
    try:
        from engine.cognitive_router import get_router
        router = get_router()
        route = router.routes.get(route_name, {})
        return route.get("tier", 1)
    except Exception:
        return 1  # Default to Haiku


# =========================================================================
# Pre-configured RatchetConfigs for common classification tasks
# These are imported and used by the cognitive_router and cortex modules
# =========================================================================

def create_intent_config(deterministic_fn: Callable) -> RatchetConfig:
    """
    Create RatchetConfig for intent classification.

    Args:
        deterministic_fn: Function that matches keywords from routing.config

    Returns:
        RatchetConfig configured for intent classification
    """
    return RatchetConfig(
        label="intent",
        deterministic=deterministic_fn,
        interpret_route="ratchet_intent_classify",
        threshold=0.7
    )


def create_entity_config(deterministic_fn: Callable) -> RatchetConfig:
    """
    Create RatchetConfig for entity extraction.

    Args:
        deterministic_fn: Function that uses regex patterns from config

    Returns:
        RatchetConfig configured for entity extraction
    """
    return RatchetConfig(
        label="entity_extraction",
        deterministic=deterministic_fn,
        interpret_route="ratchet_entity_extract",
        threshold=0.7
    )


def create_correction_config(deterministic_fn: Callable) -> RatchetConfig:
    """
    Create RatchetConfig for correction detection (Memory Accumulator).

    Args:
        deterministic_fn: Function that matches correction keywords from cortex.yaml

    Returns:
        RatchetConfig configured for correction detection
    """
    return RatchetConfig(
        label="correction_detection",
        deterministic=deterministic_fn,
        interpret_route="ratchet_correction_detect",
        threshold=0.6  # Lower threshold - corrections matter
    )


def create_gap_config(deterministic_fn: Callable) -> RatchetConfig:
    """
    Create RatchetConfig for gap detection.

    Args:
        deterministic_fn: Function that checks entity schemas for missing fields

    Returns:
        RatchetConfig configured for gap detection
    """
    return RatchetConfig(
        label="gap_detection",
        deterministic=deterministic_fn,
        interpret_route="ratchet_gap_detect",
        threshold=0.8  # High threshold - deterministic is good for gaps
    )
