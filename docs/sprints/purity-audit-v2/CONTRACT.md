# SPRINT CONTRACT: Purity Audit v2

> Atomic execution contract generated from SPEC.md
> Generated: 2026-03-18
> Sprint: `purity-audit-v2`
> Dependency: `purity-audit-v1` must be merged first

---

## Pre-Sprint Audit Summary

**Existing Infrastructure (post v1):**

| Component | File | Key Detail |
|-----------|------|------------|
| TelemetryEvent | `engine/telemetry.py:48-110` | Dataclass: id, timestamp, source, raw_transcript, zone_context, inferred |
| log_event() | `engine/telemetry.py:152-200` | Creates event, validates, appends to JSONL |
| LLM Client | `engine/llm_client.py:31-53` | Hardcoded TIER_MODELS and MODEL_PRICING dicts |
| Pipeline Stage 4 | `engine/pipeline.py:~325-340` | Red zone calls confirm_yellow_zone() |
| run_pipeline_with_mcp | `engine/pipeline.py:762-798` | No try/except wrapper |
| Standing context | `engine/config_loader.py:~60` | except Exception: pass |

**Telemetry call sites to update (Epic A):**
- `engine/pipeline.py` — `_run_telemetry()`, `_log_pipeline_failure()`
- `engine/cognitive_router.py` — LLM classification logging, cache hit logging (from v1)
- `engine/llm_client.py` — `log_llm_event()` (separate stream, but should align)
- `engine/cortex.py` — tail-pass logging
- `engine/dispatcher.py` — handler error logging
- `engine/compiler.py` — compilation error logging
- `autonomaton.py` — welcome/startup error logging (post v1: now in dispatcher)


---

## Epic A: Flat Telemetry Schema

**Gate:** Telemetry events have first-class `intent`, `tier`, `confidence`, `cost_usd` fields.

### Task A.1: Add Optional Fields to TelemetryEvent Dataclass

**File:** `engine/telemetry.py`

**Action:** Add four optional fields to the `TelemetryEvent` dataclass,
after the existing `inferred` field:

```python
@dataclass
class TelemetryEvent:
    # ... existing required fields ...
    source: str
    raw_transcript: str
    zone_context: str
    id: str = field(default_factory=_generate_id)
    timestamp: str = field(default_factory=_generate_timestamp)
    inferred: dict = field(default_factory=dict)

    # Routing metadata — first-class for auditability
    # These fields make routing decisions grep-able without parsing inferred.
    intent: Optional[str] = None
    tier: Optional[int] = None
    confidence: Optional[float] = None
    cost_usd: Optional[float] = None
    human_feedback: Optional[str] = None  # "approved", "rejected", "clarified"
```

**Note:** These are OPTIONAL fields with None defaults. This means:
- Existing code that creates TelemetryEvent without these fields still works
- The `_validate()` method does NOT require them
- They appear in `to_dict()` output only when set (see Task A.2)
- Backward compatibility with existing telemetry data is preserved


### Task A.2: Update to_dict() to Include Flat Fields

**File:** `engine/telemetry.py`

**Action:** Modify `to_dict()` to include the new fields when they are set:

```python
def to_dict(self) -> dict:
    """Convert to dictionary for JSON serialization."""
    event = {
        "id": self.id,
        "timestamp": self.timestamp,
        "source": self.source,
        "raw_transcript": self.raw_transcript,
        "zone_context": self.zone_context,
        "inferred": self.inferred
    }
    # Flat routing fields — included when set, omitted when None
    if self.intent is not None:
        event["intent"] = self.intent
    if self.tier is not None:
        event["tier"] = self.tier
    if self.confidence is not None:
        event["confidence"] = self.confidence
    if self.cost_usd is not None:
        event["cost_usd"] = self.cost_usd
    if self.human_feedback is not None:
        event["human_feedback"] = self.human_feedback
    return event
```

---

### Task A.3: Update create_event() and log_event() Signatures

**File:** `engine/telemetry.py`

**Action:** Add optional parameters to both functions:

```python
def create_event(
    source: str,
    raw_transcript: str,
    zone_context: str = "green",
    inferred: Optional[dict] = None,
    intent: Optional[str] = None,
    tier: Optional[int] = None,
    confidence: Optional[float] = None,
    cost_usd: Optional[float] = None,
    human_feedback: Optional[str] = None,
) -> dict:
```

Pass the new fields through to `TelemetryEvent(...)`:

```python
    event = TelemetryEvent(
        source=source,
        raw_transcript=raw_transcript,
        zone_context=zone_context,
        inferred=inferred if inferred is not None else {},
        intent=intent,
        tier=tier,
        confidence=confidence,
        cost_usd=cost_usd,
        human_feedback=human_feedback,
    )
```

Apply the identical signature change and pass-through to `log_event()`.

**CRITICAL:** All existing call sites that don't pass these new params
continue to work — the params default to None and are omitted from output.
Zero breaking changes.

**Verification:**
```bash
python -c "
from engine.telemetry import create_event
# Old-style call still works
e1 = create_event(source='test', raw_transcript='hello', zone_context='green')
assert 'intent' not in e1, 'None fields should be omitted'

# New-style call includes flat fields
e2 = create_event(source='test', raw_transcript='hello', zone_context='green',
                   intent='strategy_session', tier=2, confidence=0.85)
assert e2['intent'] == 'strategy_session'
assert e2['tier'] == 2
assert e2['confidence'] == 0.85
print('PASS: Flat telemetry fields work')
"
```


### Task A.4: Update Pipeline Telemetry Calls

**File:** `engine/pipeline.py`

**Action 1:** In `_run_telemetry()` (Stage 1), add intent field if known:

The Stage 1 event fires before recognition, so intent/tier/confidence
are not yet known. No change needed here — the fields stay None.

**Action 2:** After Stage 5 execution completes successfully, log a
completion event with full routing metadata as flat fields.

Add a new method `_log_pipeline_completion()` and call it at the end
of `_run_execution()` when `self.context.executed` is True:

```python
def _log_pipeline_completion(self) -> None:
    """Log pipeline completion with flat routing fields for auditability."""
    routing_info = self.context.entities.get("routing", {})

    log_event(
        source=self.context.source,
        raw_transcript=self.context.raw_input[:200],
        zone_context=self.context.zone,
        intent=self.context.intent,
        tier=routing_info.get("tier"),
        confidence=routing_info.get("confidence"),
        human_feedback="approved" if self.context.approved else "rejected",
        inferred={
            "stage": "pipeline_complete",
            "handler": routing_info.get("handler"),
            "intent_type": routing_info.get("intent_type"),
        }
    )
```

Call this at the end of `_run_execution()`:
```python
if self.context.executed:
    self._log_pipeline_completion()
    self._write_to_pattern_cache()  # From v1
```

**Action 3:** Update `_log_pipeline_failure()` to use flat fields:

```python
def _log_pipeline_failure(self, exception: Exception) -> None:
    log_event(
        source="pipeline_failure",
        raw_transcript=self.context.raw_input[:200] if self.context.raw_input else "",
        zone_context=self.context.zone,
        intent=self.context.intent,
        tier=self.context.entities.get("routing", {}).get("tier"),
        inferred={
            "error": str(exception),
            "error_type": type(exception).__name__,
            "domain": self.context.domain,
            "stage": self._get_current_stage()
        }
    )
```


### Task A.5: Update Cognitive Router Telemetry Calls

**File:** `engine/cognitive_router.py`

**Action:** In `_escalate_to_llm()`, update the classification telemetry
to use flat fields:

```python
# Log classification to telemetry for Ratchet
log_event(
    source="cognitive_router",
    raw_transcript=user_input[:200],
    zone_context="classification",
    intent=classified_intent,
    tier=2,
    confidence=confidence,
    inferred={
        "classification_tier": 2,
        "model": "claude-sonnet",
        "latency_ms": latency_ms,
        "output": classification
    }
)
```

**Also update** the cache hit telemetry (from v1) in `_check_pattern_cache()`:

```python
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
```

---

### Task A.6: Update Remaining Call Sites

**Files:** `engine/dispatcher.py`, `engine/cortex.py`, `engine/compiler.py`

**Action:** Search each file for `log_event(` calls. For any call that
includes routing-related data in `inferred`, promote the relevant fields:

**Pattern:** If you see this:
```python
log_event(
    source="dispatcher",
    raw_transcript=raw_input[:200],
    zone_context="yellow",
    inferred={"error": str(e), "handler": "general_chat", "intent": "general_chat"}
)
```

Promote `intent` to a flat field:
```python
log_event(
    source="dispatcher",
    raw_transcript=raw_input[:200],
    zone_context="yellow",
    intent="general_chat",
    inferred={"error": str(e), "handler": "general_chat"}
)
```

**Rule:** Only promote `intent`, `tier`, `confidence`, `cost_usd`, and
`human_feedback`. Everything else stays in `inferred`. Don't over-flatten —
the `inferred` dict is still the right place for error details, handler
names, latency data, and domain-specific metadata.


### Task A.7: Update Existing Telemetry Tests

**File:** `tests/test_telemetry_schema.py`

**Action:** Add test methods to the existing `TestTelemetryEventSchema` class:

```python
def test_telemetry_event_flat_routing_fields(self):
    """Flat routing fields appear in output when set."""
    from engine.telemetry import TelemetryEvent
    event = TelemetryEvent(
        source="test",
        raw_transcript="hello",
        zone_context="green",
        intent="strategy_session",
        tier=2,
        confidence=0.85,
        cost_usd=0.012,
        human_feedback="approved"
    )
    d = event.to_dict()
    assert d["intent"] == "strategy_session"
    assert d["tier"] == 2
    assert d["confidence"] == 0.85
    assert d["cost_usd"] == 0.012
    assert d["human_feedback"] == "approved"

def test_telemetry_event_omits_none_fields(self):
    """None routing fields are omitted from dict output."""
    from engine.telemetry import TelemetryEvent
    event = TelemetryEvent(
        source="test",
        raw_transcript="hello",
        zone_context="green"
    )
    d = event.to_dict()
    assert "intent" not in d
    assert "tier" not in d
    assert "confidence" not in d
    assert "cost_usd" not in d
    assert "human_feedback" not in d

def test_log_event_accepts_flat_fields(self):
    """log_event() accepts and persists flat routing fields."""
    from engine.telemetry import create_event
    event = create_event(
        source="test",
        raw_transcript="hello",
        zone_context="green",
        intent="general_chat",
        tier=1,
        confidence=0.95
    )
    assert event["intent"] == "general_chat"
    assert event["tier"] == 1
```

**Verification:**
```bash
python -m pytest tests/test_telemetry_schema.py -x -q
```

---

### GATE A: Flat Telemetry Schema

```bash
# 1. Flat fields work in create_event
python -c "
from engine.telemetry import create_event
e = create_event(source='test', raw_transcript='hi', zone_context='green',
                 intent='test', tier=2, confidence=0.9)
assert e['intent'] == 'test' and e['tier'] == 2
print('PASS: Flat fields in create_event')
"

# 2. None fields omitted
python -c "
from engine.telemetry import create_event
e = create_event(source='test', raw_transcript='hi', zone_context='green')
assert 'intent' not in e
print('PASS: None fields omitted')
"

# 3. Telemetry tests pass
python -m pytest tests/test_telemetry_schema.py -x -q

# 4. Full test suite — no regressions
python -m pytest tests/ -x -q
```

**Do not proceed to Epic B until all four checks pass.**


---

## Epic B: Externalize Model Config

**Gate:** `llm_client.py` reads tier-to-model mapping from `models.yaml`.

### Task B.1: Create models.yaml Config File

**File:** `profiles/coach_demo/config/models.yaml` (NEW)

**Action:** Create the model configuration file:

```yaml
# models.yaml
# Tier-to-model mapping and pricing for the Cognitive Router.
#
# This is the cognitive agnosticism principle in action:
# swap models by editing this file. No code deployment.
#
# When local models become capable enough, add them here:
#   1: "local://llama-3.2-7b"
# The router doesn't care. It validates outputs against structure.

tiers:
  1:
    model: "claude-3-5-haiku-20241022"
    description: "Fast, cheap — classification, extraction, chat"
    pricing:
      input_per_million: 1.0
      output_per_million: 5.0
  2:
    model: "claude-sonnet-4-20250514"
    description: "Quality — content generation, skill execution, synthesis"
    pricing:
      input_per_million: 3.0
      output_per_million: 15.0
  3:
    model: "claude-opus-4-20250514"
    description: "Apex — Pit Crew generation, Architectural Judge"
    pricing:
      input_per_million: 15.0
      output_per_million: 75.0

# Default max tokens per request
default_max_tokens: 1024
```

**Also create** `profiles/blank_template/config/models.yaml` with the same content.

**Note on model strings:** The models above are current as of March 2026.
The point is not which specific models are listed — it's that the operator
can change them without touching code.

**Verification:**
```bash
python -c "
import yaml
d = yaml.safe_load(open('profiles/coach_demo/config/models.yaml'))
assert 'tiers' in d
assert 1 in d['tiers'] and 2 in d['tiers'] and 3 in d['tiers']
print('PASS: models.yaml created with 3 tiers')
"
```


### Task B.2: Update llm_client.py to Read From Config

**File:** `engine/llm_client.py`

**Action 1:** Keep the existing `TIER_MODELS` and `MODEL_PRICING` dicts as
FALLBACK defaults (renamed with underscore prefix):

```python
# Fallback defaults — used only if models.yaml is missing
_DEFAULT_TIER_MODELS = {
    1: "claude-3-5-haiku-20241022",
    2: "claude-sonnet-4-20250514",
    3: "claude-opus-4-20250514",
}

_DEFAULT_MODEL_PRICING = {
    "claude-3-5-haiku-20241022": {"input": 1.0, "output": 5.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
}
```

**Action 2:** Add a config loader function:

```python
_models_config_cache = None

def _load_models_config() -> tuple[dict, dict, int]:
    """
    Load model configuration from profile's models.yaml.

    Returns (tier_models, model_pricing, max_tokens).
    Falls back to hardcoded defaults if config is missing.

    This is Invariant #2: Config Over Code.
    The operator controls which models the system uses.
    """
    global _models_config_cache
    if _models_config_cache is not None:
        return _models_config_cache

    try:
        import yaml
        from engine.profile import get_config_dir
        config_path = get_config_dir() / "models.yaml"

        if not config_path.exists():
            _models_config_cache = (
                _DEFAULT_TIER_MODELS,
                _DEFAULT_MODEL_PRICING,
                DEFAULT_MAX_TOKENS
            )
            return _models_config_cache

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        tier_models = {}
        model_pricing = {}

        for tier_num, tier_config in data.get("tiers", {}).items():
            tier_int = int(tier_num)
            model_id = tier_config.get("model", "")
            tier_models[tier_int] = model_id

            pricing = tier_config.get("pricing", {})
            if pricing:
                model_pricing[model_id] = {
                    "input": pricing.get("input_per_million", 0),
                    "output": pricing.get("output_per_million", 0),
                }

        max_tokens = data.get("default_max_tokens", DEFAULT_MAX_TOKENS)

        _models_config_cache = (
            tier_models if tier_models else _DEFAULT_TIER_MODELS,
            model_pricing if model_pricing else _DEFAULT_MODEL_PRICING,
            max_tokens,
        )
        return _models_config_cache

    except Exception:
        _models_config_cache = (
            _DEFAULT_TIER_MODELS,
            _DEFAULT_MODEL_PRICING,
            DEFAULT_MAX_TOKENS
        )
        return _models_config_cache


def reset_models_config() -> None:
    """Reset model config cache. Call after profile switch."""
    global _models_config_cache
    _models_config_cache = None
```


**Action 3:** Update `call_llm()` to use the config loader:

Replace the line:
```python
model = TIER_MODELS.get(tier, TIER_MODELS[1])
```

With:
```python
tier_models, _, _ = _load_models_config()
model = tier_models.get(tier, tier_models.get(1, "claude-3-5-haiku-20241022"))
```

**Action 4:** Update `_calculate_cost()` to use the config loader:

Replace the line:
```python
pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-3-haiku-20240307"])
```

With:
```python
_, model_pricing, _ = _load_models_config()
pricing = model_pricing.get(model, {"input": 0, "output": 0})
```

**Action 5:** Remove the old top-level `TIER_MODELS` and `MODEL_PRICING` dicts
(now renamed to `_DEFAULT_TIER_MODELS` and `_DEFAULT_MODEL_PRICING` in Action 1).

**Verification:**
```bash
python -c "
from engine.llm_client import _load_models_config
tiers, pricing, max_tok = _load_models_config()
assert 1 in tiers and 2 in tiers and 3 in tiers
assert max_tok > 0
print(f'PASS: Loaded {len(tiers)} tiers from config')
for t, m in tiers.items():
    print(f'  Tier {t}: {m}')
"
```

---

### GATE B: Model Config Externalized

```bash
# 1. models.yaml exists
python -c "from pathlib import Path; assert Path('profiles/coach_demo/config/models.yaml').exists(); print('PASS')"

# 2. Config loader works
python -c "from engine.llm_client import _load_models_config; t,p,m = _load_models_config(); assert 1 in t; print('PASS')"

# 3. No hardcoded model strings in call_llm path
python -c "
import inspect
from engine.llm_client import call_llm
src = inspect.getsource(call_llm)
assert 'claude-3-haiku' not in src, 'Hardcoded model string in call_llm'
assert 'claude-3-5-sonnet' not in src, 'Hardcoded model string in call_llm'
print('PASS: No hardcoded model strings in call_llm')
"

# 4. Full test suite
python -m pytest tests/ -x -q
```

**Do not proceed to Epic C until all four checks pass.**


---

## Epic C: Zone UX Differentiation + Defensive Hardening

**Gate:** Red zone calls `confirm_red_zone_with_context()`. No ghost failures.

### Task C.1: Wire Red Zone to Proper UX

**File:** `engine/pipeline.py`

**Action:** In `_run_approval()`, find the red zone block (around line 337):

```python
        elif effective_zone == "red":
            # Red zone: Explicit approval with full context
            self.context.approved = confirm_yellow_zone(
                action_description=f"[RED ZONE] {self.context.proposed_action or 'Unknown action'}"
            )
```

Replace with:

```python
        elif effective_zone == "red":
            # Red zone: Explicit approval with full context and persona explanation
            from engine.ux import confirm_red_zone_with_context
            routing_info = self.context.entities.get("routing", {})
            payload = {
                "intent": self.context.intent,
                "domain": self.context.domain,
                "zone": "red",
                "handler": routing_info.get("handler"),
                "handler_args": routing_info.get("handler_args", {}),
                "proposed_action": self.context.proposed_action,
            }
            self.context.approved = confirm_red_zone_with_context(
                action_description=self.context.proposed_action or "Unknown action",
                payload=payload
            )
```

**Note:** `confirm_red_zone_with_context()` already exists in `ux.py` (lines
~303-330). It calls `translate_action_for_approval()` which uses the persona
to explain the action in conversational language, then shows both the
conversational summary AND the raw payload. This is what "explicit approval
with context" means — the operator sees what the system wants to do in
human language AND in raw data.

**Also update** the `import` at the top of `_run_approval()` or the file's
import block. `confirm_red_zone_with_context` needs to be importable.
Check if `ux.py` is already imported at the top of `pipeline.py` — if so,
add the import there. If imports are done inside the method, add it locally.

**Verification:**
```bash
python -c "
import inspect
from engine.pipeline import InvariantPipeline
src = inspect.getsource(InvariantPipeline._run_approval)
assert 'confirm_red_zone_with_context' in src, 'Red zone still using yellow zone UX'
print('PASS: Red zone wired to confirm_red_zone_with_context')
"
```


### Task C.2: Fix run_pipeline_with_mcp Exception Handling

**File:** `engine/pipeline.py`

**Action:** The `run_pipeline_with_mcp()` function (lines ~762-798) calls
the five stage methods directly without a try/except wrapper. Replace the
direct stage calls with a call to `pipeline.run()`, or wrap them in the
same exception handler.

**Preferred approach — delegate to `run()`:**

```python
def run_pipeline_with_mcp(
    raw_input: str,
    mcp_server: str,
    mcp_capability: str,
    mcp_payload: dict,
    domain: str = "general",
    source: str = "operator_session"
) -> PipelineContext:
    """
    Execute the pipeline with a pre-defined MCP action.
    """
    pipeline = InvariantPipeline()

    # Pre-set the MCP action before running the pipeline
    # The pipeline will pick this up during execution
    pipeline._pre_mcp_action = MCPAction(
        server=mcp_server,
        capability=mcp_capability,
        payload=mcp_payload
    )
    pipeline._pre_domain = domain

    # Use the standard run() method — gets full exception handling
    return pipeline.run(raw_input, source, zone="green")
```

**Alternative approach — if the above requires too many changes to `run()`:**

Wrap the existing direct calls in try/except matching `InvariantPipeline.run()`:

```python
    try:
        pipeline._run_telemetry()
        pipeline._run_recognition()
        pipeline._run_compilation()
        pipeline._run_approval()
        pipeline._run_execution()
    except Exception as e:
        pipeline._log_pipeline_failure(e)
        pipeline.context.executed = False
        pipeline.context.result = {
            "status": "failed",
            "message": f"Pipeline failure: {str(e)}",
            "error_type": type(e).__name__
        }

    return pipeline.context
```

**Use whichever approach is simpler given the post-v1 state of the code.**
The key requirement: a crash in `run_pipeline_with_mcp()` MUST produce a
telemetry event. Zero ghost failures.


### Task C.3: Add Telemetry on Standing Context Failure

**File:** `engine/config_loader.py`

**Action:** In `build_system_prompt()`, replace the silent exception handler:

```python
        if include_state:
            try:
                from engine.compiler import get_standing_context
                state = get_standing_context()
                if state:
                    prompt += f"\n\n{state}"
            except Exception:
                pass  # Standing context is enrichment, not critical path
```

With a version that logs the failure:

```python
        if include_state:
            try:
                from engine.compiler import get_standing_context
                state = get_standing_context()
                if state:
                    prompt += f"\n\n{state}"
            except Exception as e:
                # Standing context is enrichment, not critical path.
                # But surface the failure so it's debuggable.
                try:
                    from engine.telemetry import log_event
                    log_event(
                        source="config_loader",
                        raw_transcript="standing_context_load",
                        zone_context="yellow",
                        inferred={
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "stage": "standing_context_enrichment"
                        }
                    )
                except Exception:
                    pass  # Telemetry itself failed — truly nothing we can do
```

**Note:** The outer `pass` is gone — replaced by telemetry logging. The inner
`pass` on the telemetry call is acceptable: if telemetry itself is broken,
there's genuinely nothing left to do. But the common case (compiler error,
file not found, encoding issue) now leaves a trail.


### Task C.4: Document Handler Contract in CLAUDE.md

**File:** `CLAUDE.md`

**Action:** Add a new section after the "Architectural Invariants" section
and before "The Three-Layer Architecture":

```markdown
---

### Handler Interface Contract

Handlers are registered in `engine/dispatcher.py` and invoked by the
pipeline's Stage 5 (Execution). All handlers follow the same interface:

**Signature:**
```python
def _handle_{name}(self, routing_result: RoutingResult, raw_input: str) -> DispatchResult
```

**Contract:**
1. Handlers receive a `RoutingResult` (from Stage 2) and the raw input string.
2. Handlers return a `DispatchResult` with `success`, `message`, and `data`.
3. Handlers NEVER prompt the operator directly. Approval happens in Stage 4.
4. Handlers NEVER call `call_llm()` without a clear `intent` parameter for telemetry.
5. Handler `data` dicts MUST include a `type` field for display routing.
6. Failures return `DispatchResult(success=False, ...)` — never raise exceptions.

**Core handlers** (built into the engine):
- `status_display` — Green zone, informational
- `content_engine` — Yellow zone, actionable
- `pit_crew` — Red zone, system modification
- `general_chat` — Green zone, conversational
- `strategy_session` — Green zone, actionable
- `skill_executor` — Zone from config, executes Pit Crew generated skills
- `cortex_batch` — Yellow zone, analytical lenses

**Extension point:** New domain-specific capabilities should be built as
skills (via Pit Crew) routed through `skill_executor`, not as new core
handlers. This keeps the engine domain-agnostic. Core handlers change
only when the engine's structural capabilities change.
```

---

### GATE C: Zone UX + Defensive Hardening

```bash
# 1. Red zone wired to proper UX
python -c "
import inspect
from engine.pipeline import InvariantPipeline
src = inspect.getsource(InvariantPipeline._run_approval)
assert 'confirm_red_zone_with_context' in src
print('PASS: Red zone UX')
"

# 2. run_pipeline_with_mcp has exception handling
python -c "
import inspect
from engine.pipeline import run_pipeline_with_mcp
src = inspect.getsource(run_pipeline_with_mcp)
assert 'except' in src or '.run(' in src, 'No exception handling in run_pipeline_with_mcp'
print('PASS: MCP pipeline exception handling')
"

# 3. Standing context failure logs telemetry
python -c "
import inspect
from engine.config_loader import PersonaConfig
src = inspect.getsource(PersonaConfig.build_system_prompt)
assert 'log_event' in src
print('PASS: Standing context failure telemetry')
"

# 4. Handler contract in CLAUDE.md
python -c "
content = open('CLAUDE.md').read()
assert 'Handler Interface Contract' in content
print('PASS: Handler contract documented')
"

# 5. Full test suite
python -m pytest tests/ -x -q
```

**Do not proceed to Epic D until all five checks pass.**


---

## Epic D: Test Suite for Purity v2

**Gate:** All new + existing tests pass. Zero regressions.

### Task D.1: Create test_purity_v2.py

**File:** `tests/test_purity_v2.py` (NEW)

**Action:** Create test file with four test classes:

```python
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
        tiers, pricing, max_tok = _load_models_config()
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

    def test_mcp_pipeline_has_exception_handling(self):
        from engine.pipeline import run_pipeline_with_mcp
        src = inspect.getsource(run_pipeline_with_mcp)
        has_try = "try:" in src or "except" in src
        has_delegation = ".run(" in src
        assert has_try or has_delegation, \
            "run_pipeline_with_mcp has no exception handling"

    def test_standing_context_failure_logs_telemetry(self):
        from engine.config_loader import PersonaConfig
        src = inspect.getsource(PersonaConfig.build_system_prompt)
        assert "log_event" in src, \
            "Standing context failure does not log telemetry"

    def test_handler_contract_documented(self):
        content = Path("CLAUDE.md").read_text(encoding="utf-8")
        assert "Handler Interface Contract" in content
```


---

### GATE D: Full Test Suite

```bash
python -m pytest tests/ -x -v
# Expected: All tests pass, zero failures
```

---

## Final Sprint Gate

```bash
echo "=== GATE A: Flat Telemetry Schema ==="
python -c "
from engine.telemetry import create_event
e = create_event(source='t', raw_transcript='hi', zone_context='green', intent='test', tier=2, confidence=0.9)
assert e['intent']=='test' and e['tier']==2; print('PASS')
"
python -c "
from engine.telemetry import create_event
e = create_event(source='t', raw_transcript='hi', zone_context='green')
assert 'intent' not in e; print('PASS')
"

echo "=== GATE B: Model Config Externalized ==="
python -c "from pathlib import Path; assert Path('profiles/coach_demo/config/models.yaml').exists(); print('PASS')"
python -c "from engine.llm_client import _load_models_config; t,p,m=_load_models_config(); assert 1 in t; print('PASS')"

echo "=== GATE C: Zone UX + Defense ==="
python -c "
import inspect; from engine.pipeline import InvariantPipeline
assert 'confirm_red_zone_with_context' in inspect.getsource(InvariantPipeline._run_approval); print('PASS')
"
python -c "
import inspect; from engine.pipeline import run_pipeline_with_mcp
src=inspect.getsource(run_pipeline_with_mcp)
assert 'except' in src or '.run(' in src; print('PASS')
"

echo "=== GATE D: Full Test Suite ==="
python -m pytest tests/ -x -q

echo "=== ALL GATES PASSED ==="
```

---

## Files Created or Modified (Summary)

| File | Action | Epic |
|------|--------|------|
| `engine/telemetry.py` | Modified — 5 new optional fields, updated to_dict, updated signatures | A |
| `engine/pipeline.py` | Modified — flat telemetry calls, red zone UX, MCP exception handling, completion event | A, C |
| `engine/cognitive_router.py` | Modified — flat telemetry in classification and cache hit logging | A |
| `engine/llm_client.py` | Modified — reads from models.yaml, fallback defaults | A, B |
| `engine/dispatcher.py` | Modified — flat telemetry in error logging | A |
| `engine/cortex.py` | Modified — flat telemetry in tail-pass logging | A |
| `engine/compiler.py` | Modified — flat telemetry in error logging (if applicable) | A |
| `engine/config_loader.py` | Modified — standing context failure telemetry | C |
| `profiles/coach_demo/config/models.yaml` | Created | B |
| `profiles/blank_template/config/models.yaml` | Created | B |
| `CLAUDE.md` | Modified — handler contract section | C |
| `tests/test_telemetry_schema.py` | Modified — new tests for flat fields | A |
| `tests/test_purity_v2.py` | Created | D |

---

*Sprint contract generated from architectural purity audit — MEDIUM violations.*
*Provenance: Pattern Release 1.3, TCP/IP Paper, CLAUDE.md Invariants #1, #2, #5*
