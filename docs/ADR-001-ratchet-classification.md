# ADR-001: Ratchet Classification — LLM Interprets, Deterministic Compiles

> Status: **Superseded (V-001)**
> Date: 2026-03-18
> Author: Jim Calhoun / Grove Architecture
> Superseded: 2026-03-20 — The interpret layer is a direct LLM call
> within the cognitive router, not a pipeline traversal. Sub-pipelines
> violated the core invariant (one operator input = one pipeline traversal)
> and poisoned the Ratchet cache. See VIOLATIONS.md V-001.

---

## Context

Every classification task in the Autonomaton follows (or should follow)
the same two-layer architecture. But each implementation reinvents it.
The cognitive router has keyword matching → Sonnet escalation. Entity
extraction has regex → Haiku NER. Gap detection is pure deterministic.
Ratchet analysis is pure LLM. No consistent interface. No standardized
telemetry. No systematic path from LLM to deterministic.

The result: the Ratchet (Cortex Lens 4) can't systematically identify
demotion candidates because every classification task logs differently
(or doesn't log at all). The investment in cognition never pays down.

## Decision

**Every classification task MUST use the universal `ratchet_classify()`
function.** No exceptions. No raw LLM calls for classification without
a deterministic first pass. No deterministic-only tasks that skip
telemetry.

### The Two-Layer Architecture

```
INPUT
  │
  ▼
LAYER 1: Deterministic (free)
  Keywords, regex, lookup table, string matching.
  Rules declared in config (routing.config, ratchet.config).
  Runs FIRST. If confidence ≥ threshold → return result.
  │
  ▼ (confidence < threshold)
LAYER 2: LLM Interpretation — THROUGH THE PIPELINE
  NOT a raw call_llm(). The interpret layer is a PIPELINE
  TRAVERSAL routed through the cognitive router.
  The config declares: which tier, which prompt template,
  which zone. The engine reads config and routes.
  │
  ▼
TELEMETRY: Every classification logged (both layers)
  Standardized exhaust schema.
  Source layer recorded (deterministic vs pipeline).
  │
  ▼
RATCHET: Stable LLM patterns → deterministic rules
  When an LLM classification is confirmed N times,
  the Ratchet proposes a Tier 0 keyword/rule.
  The classification becomes FREE.
```

### Rules

1. **No classification task may use only an LLM layer.** Even if the
   deterministic layer starts empty, the interface must exist. The
   Ratchet fills it over time.

2. **No classification task may skip telemetry.** Every classification
   — deterministic or LLM — is logged with the standardized schema.
   The Ratchet reads this log to identify demotion candidates.

3. **The interpret layer runs through the pipeline.** No raw
   `call_llm()` for classification. The interpret layer is a pipeline
   traversal routed through the cognitive router. The prompt template,
   tier, and zone are declared in config — NOT hardcoded in a callable.
   A hardcoded interpret function is an Invariant #1 violation.

4. **Deterministic rules are declared in config.** Keywords live in
   `routing.config`. Regex patterns live in `ratchet.config`. The
   deterministic layer reads config at runtime — it doesn't hardcode
   matching logic. When the Ratchet proposes a Tier 0 rule, it ADDS
   to the config. The config grows. The code doesn't change.

5. **Deterministic rules are append-only.** When the Ratchet proposes
   a Tier 0 rule, it ADDS to the deterministic config. It never
   removes existing rules. The deterministic layer grows monotonically.

---

## The Universal Function

```python
# engine/ratchet.py — The universal classification function

from dataclasses import dataclass, field
from typing import TypeVar, Optional, Callable, Any, Generic
import time

T = TypeVar('T')


@dataclass
class RatchetResult(Generic[T]):
    """Result of a ratchet classification."""
    result: Optional[T]
    source: str  # "deterministic" | "pipeline" | "none"
    confidence: float
    latency_ms: int
    label: str  # Which classifier produced this


@dataclass
class RatchetConfig(Generic[T]):
    """
    Configuration for a ratchet classification task.

    The deterministic layer is a function that reads from config
    (routing.config keywords, ratchet.config rules, etc.).

    The interpret layer is NOT a raw LLM call. It declares a
    pipeline route — a classification intent in routing.config
    that the cognitive router handles like any other intent.
    This ensures the interpret layer goes through all 5 stages:
    Telemetry → Recognition → Compilation → Approval → Execution.
    """
    label: str                                          # "intent", "entity_type", "correction_signal"
    deterministic: Callable[[str], Optional[tuple]]     # Reads config, returns (result, confidence) or None
    interpret_route: str                                # routing.config intent for LLM classification
    threshold: float = 0.7                              # Below this → escalate through pipeline

    Every caller provides:
    1. A label (for telemetry grouping)
    2. A deterministic function (reads from config — free)
    3. An interpret_route (routing.config intent — through the pipeline)
    4. A confidence threshold for escalation
    """
    label: str                                          # "intent", "entity_type", "correction_signal"
    deterministic: Callable[[str], Optional[tuple]]     # Reads config, returns (result, confidence) or None
    interpret_route: str                                # routing.config intent for pipeline classification
    threshold: float = 0.7                              # Below this → escalate through pipeline


def ratchet_classify(
    input_text: str,
    config: RatchetConfig
) -> RatchetResult:
    """
    Universal ratchet classification.

    Layer 1: Run deterministic function (free, reads from config).
    Layer 2: If deterministic misses, route through the INVARIANT PIPELINE
             via the cognitive router. The interpret_route declares which
             routing.config intent handles the classification. This ensures
             the LLM call goes through all 5 stages.
    Always: Log to telemetry with standardized schema.

    CRITICAL: The interpret layer is a PIPELINE TRAVERSAL, not a raw
    call_llm(). This is Invariant #1. No bypass paths.

    Args:
        input_text: The text to classify
        config: RatchetConfig with deterministic function and pipeline route

    Returns:
        RatchetResult with result, source, confidence, latency
    """
    from engine.telemetry import log_event

    start_time = time.time()

    # Layer 1: Deterministic (free)
    det_result = config.deterministic(input_text)

    if det_result is not None:
        result, confidence = det_result
        if confidence >= config.threshold:
            latency_ms = int((time.time() - start_time) * 1000)

            # Log deterministic hit
            log_event(
                source=f"ratchet:{config.label}",
                raw_transcript=input_text[:200],
                zone_context="classification",
                inferred={
                    "classifier": config.label,
                    "source": "deterministic",
                    "result": str(result),
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

    pipeline_context = run_pipeline(
        raw_input=input_text,
        source=f"ratchet:{config.label}"
        # The pipeline will:
        # 1. Log telemetry (Stage 1)
        # 2. Route through cognitive router using interpret_route (Stage 2)
        # 3. Compile with dock context if needed (Stage 3)
        # 4. Apply zone governance (Stage 4)
        # 5. Execute the classification handler (Stage 5)
    )

    latency_ms = int((time.time() - start_time) * 1000)

    if pipeline_context.executed and pipeline_context.result:
        result_data = pipeline_context.result.get("data", {})
        classification = result_data.get("classification")
        confidence = result_data.get("confidence", 0.5)

        if classification is not None:
            # Log the pipeline classification
            log_event(
                source=f"ratchet:{config.label}",
                raw_transcript=input_text[:200],
                zone_context="classification",
                inferred={
                    "classifier": config.label,
                    "source": "pipeline",
                    "result": str(classification),
                    "confidence": confidence,
                    "latency_ms": latency_ms,
                    "interpret_route": config.interpret_route,
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

    # Both layers failed
    log_event(
        source=f"ratchet:{config.label}",
        raw_transcript=input_text[:200],
        zone_context="classification_failed",
        inferred={
            "classifier": config.label,
            "source": "none",
            "latency_ms": latency_ms,
            "interpret_route": config.interpret_route
        }
    )

    return RatchetResult(
        result=None,
        source="none",
        confidence=0.0,
        latency_ms=latency_ms,
        label=config.label
    )
```

### What This Means for routing.config

Each ratchet classification task declares its interpret route in
routing.config. The cognitive router handles it like any other intent:

```yaml
# Classification sub-intents (interpret layer for ratchet_classify)
ratchet_intent_classify:
    tier: 2
    zone: green
    domain: system
    intent_type: actionable
    description: "LLM interpret layer for intent classification ratchet"
    handler: "ratchet_interpreter"
    handler_args:
      classifier: "intent"
      prompt_template: "classify_intent"

ratchet_entity_extract:
    tier: 1
    zone: green
    domain: system
    intent_type: actionable
    description: "LLM interpret layer for entity extraction ratchet"
    handler: "ratchet_interpreter"
    handler_args:
      classifier: "entity_extraction"
      prompt_template: "extract_entities"

ratchet_correction_detect:
    tier: 1
    zone: green
    domain: system
    intent_type: actionable
    description: "LLM interpret layer for correction detection ratchet"
    handler: "ratchet_interpreter"
    handler_args:
      classifier: "correction_detection"
      prompt_template: "detect_correction"
```

The prompt templates live in config (or in a prompt template file
referenced by config). The tier and zone are declared. The handler
is a generic `ratchet_interpreter` that reads the template and
returns structured classification results. NOTHING is hardcoded.

A new classification task = a new routing.config entry + a new
prompt template. No engine code changes. Config over code.

---

## Existing Implementations to Refactor

### 1. Intent Classification (`cognitive_router.py`)

Currently: Custom keyword matching + custom Sonnet escalation + custom
telemetry logging. ~200 lines of bespoke code.

Refactored:
```python
intent_config = RatchetConfig(
    label="intent",
    deterministic=keyword_match_intent,       # Reads routing.config keywords
    interpret_route="ratchet_intent_classify", # routing.config intent for LLM fallback
    threshold=0.7
)

result = ratchet_classify(user_input, intent_config)
```

The deterministic function reads keywords from routing.config (already
does this). The interpret route points to a routing.config entry that
declares the tier (Sonnet), prompt template, and zone. Everything
through the pipeline. Everything declared in config.

### 2. Entity Extraction (`cortex.py`)

Currently: `_extract_entities()` (regex) and `_extract_entities_llm()`
(Haiku) as separate methods. No telemetry on the deterministic pass.

Refactored:
```python
entity_config = RatchetConfig(
    label="entity_extraction",
    deterministic=regex_extract_entities,        # Reads entity patterns from config
    interpret_route="ratchet_entity_extract",    # routing.config → Haiku NER
    threshold=0.7
)

result = ratchet_classify(transcript, entity_config)
```

### 3. Gap Detection (`cortex.py`)

Currently: Pure deterministic string parsing. No LLM fallback. No
telemetry.

Refactored:
```python
gap_config = RatchetConfig(
    label="gap_detection",
    deterministic=detect_gaps_deterministic,   # Reads entity schemas from config
    interpret_route="ratchet_gap_detect",      # routing.config → Haiku subtle gaps
    threshold=0.8                              # High bar — deterministic is good here
)
```

This is interesting: gap detection works well deterministically today.
But the `interpret` layer exists as a SAFETY NET. If the deterministic
layer misses a gap that Haiku would catch, the Ratchet logs it. Over
time, the deterministic rules improve to cover those cases. The LLM
layer's job is to disappear.

### 4. Correction Detection (Sprint 6 — Memory Accumulator)

Not yet built. Without the ADR, it would be reinvented again.

With the ADR:
```python
correction_config = RatchetConfig(
    label="correction_detection",
    deterministic=detect_correction_keywords,     # "actually", "no, it's" — from config
    interpret_route="ratchet_correction_detect",  # routing.config → Haiku inference
    threshold=0.6                                 # Lower bar — corrections matter
)

result = ratchet_classify(user_input, correction_config)
if result.result:
    # Operator is correcting the system — trigger Memory Accumulator
    propose_memory_entry(result)
```

### 5. Ratchet Analysis Itself (`cortex.py`)

Currently: Pure Sonnet with no deterministic layer. This violates
the ADR. The deterministic layer should check: "Has this exact
pattern been analyzed before? Is the proposal identical to a
previous proposal?" If yes, return cached result. Only escalate
to Sonnet for novel patterns.

### 6. Plan Update Detection

Currently: Pure deterministic intent counting. Works for simple
cases. But "Coach hasn't mentioned revenue in 3 weeks" requires
semantic understanding that Haiku provides. The `interpret` layer
catches what counting misses.

---

## Standardized Classification Telemetry

Every `ratchet_classify()` call produces a telemetry event with this
schema:

```yaml
source: "ratchet:{label}"           # e.g., "ratchet:intent"
zone_context: "classification"
inferred:
  classifier: "{label}"             # Groups events by classifier
  source: "deterministic|pipeline|none"  # Which layer resolved it
  result: "{classification_result}" # The actual classification
  confidence: 0.0-1.0
  latency_ms: N
  tier: 0|1|2                       # 0=deterministic, 1=Haiku, 2=Sonnet
  deterministic_miss: true|false    # Did the deterministic layer miss?
  deterministic_partial: "..."      # What deterministic DID find (if any)
```

The Ratchet (Lens 4) reads this telemetry and identifies demotion
candidates:

1. Filter for `source: "pipeline"` events
2. Group by `classifier` + `result`
3. When a group has N+ occurrences with consistent results → propose
   a deterministic rule
4. The rule is added to the classifier's deterministic layer
5. Next time, the deterministic layer catches it → zero cost

This is the systematic demotion path that's currently missing. The
cognitive router has an ad-hoc version. The ADR makes it universal.

---

## Enforcement

- **Code review rule:** If you're classifying input and not using
  `ratchet_classify()`, that's a violation. Explain why or refactor.
- **No raw `call_llm()` for classification.** Generation (content,
  briefings, synthesis) uses `call_llm()`. Classification ALWAYS
  goes through `ratchet_classify()` → pipeline → cog router.
- **The interpret layer is a pipeline traversal.** Any `RatchetConfig`
  with a hardcoded LLM call instead of an `interpret_route` pointing
  to routing.config is an Invariant #1 violation. No exceptions.
- **New classification tasks** = new routing.config entry + prompt
  template + `RatchetConfig`. No engine code changes required.
  Config over code.
- **CLAUDE.md addition:** Add this ADR reference to the Architectural
  Invariants section as Invariant #12.

---

## Integration with Sprint 6

The ADR is a **prerequisite** for Sprint 6. The Memory Accumulator
(Lens 7) needs `ratchet_classify()` for correction detection. The
standardized exhaust schema needs the classification telemetry schema
as its foundation. Without this ADR, Sprint 6 would reinvent the
pattern for the eighth time.

### Sprint 6 Sequencing (Revised)

**Epic 6.0 (NEW): ADR Implementation**
1. Create `engine/ratchet.py` with `ratchet_classify()` and types
2. Add `ratchet_interpreter` handler to `dispatcher.py` — generic
   handler that reads prompt template from config and returns
   structured classification results
3. Add ratchet classification routes to `routing.config`:
   `ratchet_intent_classify`, `ratchet_entity_extract`, etc.
4. Add prompt templates to `config/ratchet-prompts/` (or inline in
   routing.config handler_args) — one per classification task
5. Refactor `cognitive_router.py:classify()` onto `ratchet_classify()`
6. Refactor `cortex.py:_extract_entities()` onto `ratchet_classify()`
7. Update CLAUDE.md with Invariant #12
8. Verify all existing tests still pass

**Then:** Epics 6A-6D from the Autonomic Memory concept proceed with
the universal function already in place. The Memory Accumulator's
correction detection is just another `RatchetConfig` plugged into the
same framework.

---

## Consequences

### Positive
- Every new classification task gets the ratchet for free
- Standardized telemetry enables systematic demotion
- The Ratchet can now read ALL classification events uniformly
- Cost optimization compounds across the entire system
- New autonomaton subprocesses plug into the same interface

### Negative
- Refactoring existing classifiers requires touching stable code
- The deterministic functions need to be extracted from their
  current inline implementations
- Test coverage needs to verify both layers independently

### Neutral
- The function adds ~5 lines of overhead per classification task
  (the config definition). This is offset by removing ~50 lines of
  bespoke fallback/logging logic per task.

---

## The Principle

> "The LLM is the brain. Keywords are the reflex. Reflexes develop
> FROM experience."

The ADR codifies this principle as executable infrastructure. Every
LLM classification is a teaching moment. The Ratchet watches, learns,
and compiles stable patterns into deterministic rules. The system's
investment in cognition is finite. The benefit compounds forever.

---

*ADR-001 — Proposed 2026-03-18*
*Autonomaton Architecture Decision Record*
