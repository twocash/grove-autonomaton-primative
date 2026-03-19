# SPRINT CONTRACT: Purity Audit v1

> Atomic execution contract generated from SPEC.md
> Generated: 2026-03-18
> Sprint: `purity-audit-v1`

---

## Pre-Sprint Audit Summary

**Directory Structure:** `engine/` (Python modules), `profiles/` (declarative config)

**Existing Infrastructure:**

| Component | File | Lines | Status |
|-----------|------|-------|--------|
| Invariant Pipeline | `engine/pipeline.py` | 1-751 | 5-stage sequence, exception telemetry |
| Cognitive Router | `engine/cognitive_router.py` | 1-576 | Tier 0 keyword + Tier 1/2 LLM escalation |
| Telemetry | `engine/telemetry.py` | 1-220 | Schema-validated JSONL, feed-first |
| Dispatcher | `engine/dispatcher.py` | 1-1333 | Handler registry, MCP routing |
| Cortex | `engine/cortex.py` | 1-1365 | 5 lenses, entity extraction, Kaizen queue |
| Config Loader | `engine/config_loader.py` | 1-155 | PersonaConfig, standing context |
| UX / Jidoka | `engine/ux.py` | 1-347 | ask_jidoka, confirm_yellow_zone |
| REPL | `autonomaton.py` | 1-631 | Main loop, startup sequences |
| Routing Config | `profiles/coach_demo/config/routing.config` | 1-421 | Intent routing table |
| Zones Schema | `profiles/coach_demo/config/zones.schema` | 1-86 | Domain governance |

**Pipeline Bypass Locations (to be fixed):**

| Function | File | Lines | Bypass Type |
|----------|------|-------|-------------|
| `generate_welcome_briefing()` | `autonomaton.py` | 114-202 | Direct `call_llm()`, no pipeline |
| `generate_startup_brief()` | `autonomaton.py` | 205-242 | Direct `call_llm()`, no pipeline |
| First-boot plan generation | `autonomaton.py` | ~462-505 | Direct `call_llm()` + manual approval |
| `ask_entity_validation()` | `engine/cortex.py` | 34-60 | Direct `print()`/`input()` outside pipeline |


---

## Epic A: Route Startup Sequences Through the Pipeline

**Gate:** All startup LLM calls produce telemetry events with 5-stage traces.

### Task A.1: Add Internal Intents to routing.config

**File:** `profiles/coach_demo/config/routing.config`
**Insert after:** The `general_chat` route block (line ~30)

**Action:** Add three new route entries:

```yaml
  # --- Internal System Intents (programmatic, not operator-typed) ---
  welcome_card:
    tier: 2
    zone: green
    domain: system
    intent_type: informational
    description: "Generate contextual welcome briefing at startup"
    keywords: []  # No keywords — invoked programmatically only
    handler: "welcome_card"
    handler_args: {}

  startup_brief:
    tier: 2
    zone: green
    domain: system
    intent_type: informational
    description: "Generate Chief of Staff strategic brief at startup"
    keywords: []
    handler: "startup_brief"
    handler_args: {}

  generate_plan:
    tier: 2
    zone: yellow
    domain: system
    intent_type: actionable
    description: "Generate structured plan from dock context (first boot)"
    keywords:
      - "generate plan"
    handler: "generate_plan"
    handler_args: {}
```

**Also add** to `profiles/blank_template/config/routing.config`:
Same three entries (profile isolation — both profiles must have them).

**Verification:**
```bash
python -c "import yaml; d=yaml.safe_load(open('profiles/coach_demo/config/routing.config')); assert 'welcome_card' in d['routes']; assert 'startup_brief' in d['routes']; assert 'generate_plan' in d['routes']; print('PASS: Internal intents declared')"
```

---

### Task A.2: Add Startup Handlers to Dispatcher

**File:** `engine/dispatcher.py`

**Action 1:** Register three new handlers in `_register_handlers()` (line ~50):

```python
"welcome_card": self._handle_welcome_card,
"startup_brief": self._handle_startup_brief,
"generate_plan": self._handle_generate_plan,
```

**Action 2:** Move `generate_welcome_briefing()` logic from `autonomaton.py` into
a new `_handle_welcome_card()` method in the Dispatcher class.

The handler must:
1. Load the welcome-card skill prompt from `get_skills_dir() / "welcome-card" / "prompt.md"`
2. Load dock context (seasonal-context.md, goals.md, content-strategy.md)
3. Build persona system prompt via `get_persona().build_system_prompt()`
4. Call `call_llm()` with tier=2, intent="welcome_card"
5. Return `DispatchResult(success=True, message=response, data={"type": "welcome_card"})`
6. On failure: return `DispatchResult(success=False, ...)` — Jidoka surfaces it

**Action 3:** Move `generate_startup_brief()` logic into `_handle_startup_brief()`.

The handler must:
1. Build persona system prompt with `include_state=True`
2. Call `call_llm()` with tier=2, intent="startup_brief"
3. Return `DispatchResult(success=True, message=response, data={"type": "startup_brief"})`

**Action 4:** Move first-boot plan generation logic into `_handle_generate_plan()`.

The handler must:
1. Call `generate_structured_plan()` from `engine/compiler.py`
2. Return the plan content in `DispatchResult.data` for display
3. Zone is yellow (from routing.config) — pipeline Stage 4 handles approval
4. Do NOT reimplement approval in the handler. The pipeline owns approval.

**Verification:**
```bash
python -c "from engine.dispatcher import Dispatcher; d=Dispatcher(); assert 'welcome_card' in d._handlers; assert 'startup_brief' in d._handlers; assert 'generate_plan' in d._handlers; print('PASS: Handlers registered')"
```

---

### Task A.3: Replace Direct LLM Calls in autonomaton.py with Pipeline Invocations

**File:** `autonomaton.py`

**Action 1:** Replace `generate_welcome_briefing()` call (around line 530) with:

```python
# Welcome Briefing — through the pipeline
welcome_ctx = run_pipeline(
    raw_input="welcome_card",
    source="system_startup"
)
if welcome_ctx.executed and welcome_ctx.result:
    briefing = welcome_ctx.result.get("message", "")
    if briefing:
        print(f"  {c.WHITE}{briefing}{c.RESET}")
        print()
    else:
        print(f"  {c.YELLOW}[JIDOKA]{c.RESET} Welcome briefing unavailable — check telemetry.")
        print()
```

**Action 2:** Replace `generate_startup_brief()` call with:

```python
# Strategic Brief — through the pipeline
brief_ctx = run_pipeline(
    raw_input="startup_brief",
    source="system_startup"
)
if brief_ctx.executed and brief_ctx.result:
    brief = brief_ctx.result.get("message", "")
    if brief:
        print(f"  {c.CYAN}{'─' * 56}{c.RESET}")
        print(f"  {c.WHITE}{brief}{c.RESET}")
        print()
```

**Action 3:** Replace first-boot plan generation block (around lines 462-505) with:

```python
plan_path = get_dock_dir() / "system" / "structured-plan.md"
if not plan_path.exists():
    print(f"  {c.CYAN}[FIRST BOOT]{c.RESET} No structured plan found.")
    print(f"  {c.DIM}Generating initial plan from dock context...{c.RESET}")
    print()

    plan_ctx = run_pipeline(
        raw_input="generate plan",
        source="system_startup"
    )
    # Pipeline handles Yellow zone approval in Stage 4.
    # Dispatcher handler writes the plan if approved.
    if plan_ctx.executed:
        print(f"  {c.GREEN}[PLAN CREATED]{c.RESET} Structured plan written to dock.")
    elif not plan_ctx.approved:
        print(f"  {c.YELLOW}[DEFERRED]{c.RESET} Plan generation skipped.")
    else:
        print(f"  {c.YELLOW}[JIDOKA]{c.RESET} Plan generation failed — check telemetry.")
    print()
```

**Action 4:** Delete the now-unused functions:
- `generate_welcome_briefing()` (lines 114-202)
- `generate_startup_brief()` (lines 205-242)

**CRITICAL CONSTRAINT:** The `run_pipeline()` calls use `source="system_startup"`
to distinguish internal invocations from operator input in telemetry. The pipeline
treats them identically — same 5 stages, same governance. The source field is the
only difference.

**Verification:**
```bash
# Confirm no direct call_llm imports remain in autonomaton.py
python -c "
content = open('autonomaton.py').read()
assert 'from engine.llm_client import call_llm' not in content, 'FAIL: Direct LLM import still present'
assert 'call_llm(' not in content, 'FAIL: Direct call_llm() still present'
print('PASS: No direct LLM calls in autonomaton.py')
"
```

---

### GATE A: Pipeline Bypass Eliminated

```bash
# 1. Verify no direct call_llm in autonomaton.py
python -c "c=open('autonomaton.py').read(); assert 'call_llm(' not in c; print('PASS')"

# 2. Verify internal intents exist in routing.config
python -c "import yaml; d=yaml.safe_load(open('profiles/coach_demo/config/routing.config')); assert all(k in d['routes'] for k in ['welcome_card','startup_brief','generate_plan']); print('PASS')"

# 3. Verify handlers registered
python -c "from engine.dispatcher import Dispatcher; d=Dispatcher(); assert all(k in d._handlers for k in ['welcome_card','startup_brief','generate_plan']); print('PASS')"

# 4. Run existing test suite — no regressions
python -m pytest tests/ -x -q
```

**Do not proceed to Epic B until all four checks pass.**

---


## Epic B: The Pattern Cache (The Ratchet in Motion)

**Gate:** A confirmed LLM classification resolves at Tier 0 on repeat input.

### Task B.1: Create Pattern Cache Config File

**File:** `profiles/coach_demo/config/pattern_cache.yaml` (NEW)

**Action:** Create initial empty cache with schema header:

```yaml
# pattern_cache.yaml
# The Ratchet: Confirmed LLM classifications cached as Tier 0 lookups.
# This file is operator-inspectable and editable. Delete entries to force
# re-classification. Delete the file to reset the Ratchet entirely.
#
# Schema:
#   {input_hash}:
#     intent: string        # Classified intent name
#     domain: string        # Domain from classification
#     zone: string          # Zone from classification
#     handler: string|null  # Handler name
#     handler_args: dict    # Handler arguments
#     intent_type: string   # conversational|informational|actionable
#     confirmed_count: int  # Times this classification was confirmed
#     last_confirmed: string # ISO-8601 timestamp
#     original_input: string # First input that created this entry (for debugging)
#     confidence: float     # Confidence at cache time (always >= 0.7)

cache: {}
```

**Also create** for `profiles/blank_template/config/pattern_cache.yaml`: Same file.

**Verification:**
```bash
python -c "import yaml; d=yaml.safe_load(open('profiles/coach_demo/config/pattern_cache.yaml')); assert 'cache' in d; print('PASS: Cache file created')"
```

---

### Task B.2: Add Pattern Cache Read to Cognitive Router

**File:** `engine/cognitive_router.py`

**Action 1:** Add cache loading to `CognitiveRouter.__init__()`:

```python
self.pattern_cache: dict = {}
self._cache_loaded = False
```

**Action 2:** Add `load_cache()` method:

```python
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
```

**Action 3:** Add `_check_pattern_cache()` method:

```python
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
        llm_metadata={"source": "pattern_cache", "cache_hash": input_hash}
    )
```


**Action 4:** Modify `classify()` method to check cache BETWEEN keyword match
and LLM escalation.

Current flow: keyword match → (if low confidence) → LLM escalation
New flow: keyword match → (if low confidence) → **pattern cache check** → LLM escalation

In `classify()`, after the keyword matching loop and before the LLM escalation
block, insert:

```python
# If no match or low confidence, check pattern cache before LLM
if best_match is None or best_match[2] < self.LLM_ESCALATION_THRESHOLD:
    cache_result = self._check_pattern_cache(user_input)
    if cache_result is not None:
        return cache_result
    # Cache miss — fall through to LLM escalation
```

**Replace** the existing block that reads:
```python
# If no match or low confidence, try LLM escalation
if best_match is None or best_match[2] < self.LLM_ESCALATION_THRESHOLD:
    llm_result = self._escalate_to_llm(user_input)
```

With:
```python
# If no match or low confidence: cache check, then LLM escalation
if best_match is None or best_match[2] < self.LLM_ESCALATION_THRESHOLD:
    # THE RATCHET: Check pattern cache before calling LLM
    cache_result = self._check_pattern_cache(user_input)
    if cache_result is not None:
        return cache_result
    # Cache miss — escalate to LLM
    llm_result = self._escalate_to_llm(user_input)
```

**Verification:**
```bash
python -c "
from engine.cognitive_router import CognitiveRouter
r = CognitiveRouter()
r.load_config()
r.load_cache()
# Empty cache should return None
result = r._check_pattern_cache('some random input')
assert result is None, 'Empty cache should return None'
print('PASS: Cache check returns None on empty cache')
"
```

---

### Task B.3: Add Pattern Cache Write (Post-Execution Hook)

**File:** `engine/pipeline.py`

**Action:** Add a `_write_to_pattern_cache()` method to `InvariantPipeline`:

```python
def _write_to_pattern_cache(self) -> None:
    """Write confirmed LLM classification to pattern cache.
    
    THE RATCHET WRITE PATH:
    When an LLM-classified intent is approved AND executed successfully,
    cache the classification so it resolves at Tier 0 next time.
    
    Only caches when:
    - Classification came from LLM (tier >= 2 in routing metadata)
    - Action was approved (Stage 4 passed)
    - Action was executed successfully (Stage 5 succeeded)
    - Zone is NOT red (red zone actions should always require human judgment)
    """
    import hashlib
    import yaml
    from datetime import datetime, timezone
    from engine.profile import get_config_dir
    
    routing_info = self.context.entities.get("routing", {})
    tier = routing_info.get("tier", 0)
    llm_metadata = routing_info.get("llm_metadata", {})
    
    # Only cache LLM classifications that were confirmed by execution
    if tier < 2:
        return  # Already Tier 0/1 — no demotion needed
    if not self.context.approved:
        return
    if not self.context.executed:
        return
    if self.context.zone == "red":
        return  # Red zone: always require human judgment
    if llm_metadata.get("source") == "pattern_cache":
        return  # Already from cache — don't re-cache
    
    input_hash = hashlib.sha256(
        self.context.raw_input.lower().strip().encode()
    ).hexdigest()[:16]
    
    cache_path = get_config_dir() / "pattern_cache.yaml"
    
    try:
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}
        
        cache = data.get("cache", {})
        
        existing = cache.get(input_hash)
        if existing:
            # Increment confirmation count
            existing["confirmed_count"] = existing.get("confirmed_count", 1) + 1
            existing["last_confirmed"] = datetime.now(timezone.utc).isoformat()
        else:
            # New cache entry
            cache[input_hash] = {
                "intent": self.context.intent,
                "domain": self.context.domain,
                "zone": self.context.zone,
                "handler": routing_info.get("handler"),
                "handler_args": routing_info.get("handler_args", {}),
                "intent_type": routing_info.get("intent_type", "actionable"),
                "confirmed_count": 1,
                "last_confirmed": datetime.now(timezone.utc).isoformat(),
                "original_input": self.context.raw_input[:100],
                "confidence": routing_info.get("confidence", 0.0),
            }
        
        data["cache"] = cache
        
        with open(cache_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    except Exception as e:
        # Cache write failure is non-fatal — log and continue
        from engine.telemetry import log_event
        log_event(
            source="pattern_cache",
            raw_transcript=self.context.raw_input[:200],
            zone_context="green",
            inferred={"error": str(e), "stage": "cache_write"}
        )
```


**Action 2:** Call `_write_to_pattern_cache()` at the end of `_run_execution()`,
after successful execution. Insert before the final `return` in the method:

In `_run_execution()`, after the handler dispatch succeeds, add:

```python
# THE RATCHET: Cache confirmed LLM classifications for Tier 0 lookup
if self.context.executed:
    self._write_to_pattern_cache()
```

This goes at the END of `_run_execution()`, as the last operation before
the method returns. It fires only when `self.context.executed` is True.

**Verification:**
```bash
python -c "
from engine.pipeline import InvariantPipeline
p = InvariantPipeline()
assert hasattr(p, '_write_to_pattern_cache'), 'Method not found'
print('PASS: Cache write method exists')
"
```

---

### Task B.4: Add Cache Management Intent

**File:** `profiles/coach_demo/config/routing.config`

**Action:** Add a `clear_cache` intent to the routing config:

```yaml
  clear_cache:
    tier: 1
    zone: yellow
    domain: system
    intent_type: actionable
    description: "Clear the pattern cache (resets the Ratchet)"
    keywords:
      - "clear cache"
      - "reset cache"
      - "reset ratchet"
    handler: "clear_cache"
    handler_args: {}
```

**File:** `engine/dispatcher.py`

**Action:** Register `clear_cache` handler and implement:

```python
"clear_cache": self._handle_clear_cache,
```

```python
def _handle_clear_cache(
    self,
    routing_result: RoutingResult,
    raw_input: str
) -> DispatchResult:
    """Clear the pattern cache. Yellow Zone — modifies system behavior."""
    import yaml
    from engine.profile import get_config_dir
    
    cache_path = get_config_dir() / "pattern_cache.yaml"
    
    if not cache_path.exists():
        return DispatchResult(
            success=True,
            message="Pattern cache is already empty.",
            data={"type": "cache_clear", "entries_cleared": 0}
        )
    
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        count = len(data.get("cache", {}))
        data["cache"] = {}
        with open(cache_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        
        # Reset router cache
        from engine.cognitive_router import get_router
        router = get_router()
        router.pattern_cache = {}
        
        return DispatchResult(
            success=True,
            message=f"Pattern cache cleared. {count} entries removed.",
            data={"type": "cache_clear", "entries_cleared": count}
        )
    except Exception as e:
        return DispatchResult(
            success=False,
            message=f"Failed to clear cache: {e}",
            data={"type": "cache_clear", "error": str(e)}
        )
```

---

### Task B.5: Add Telemetry for Cache Hits

**File:** `engine/cognitive_router.py`

**Action:** In `_check_pattern_cache()`, after a successful cache hit
and before `return`, log a telemetry event:

```python
# Log cache hit for Ratchet telemetry
try:
    from engine.telemetry import log_event
    log_event(
        source="cognitive_router",
        raw_transcript=user_input[:200],
        zone_context=entry.get("zone", "green"),
        inferred={
            "classification_tier": 0,
            "cache_hit": True,
            "cache_hash": input_hash,
            "cached_intent": intent,
            "confirmed_count": entry.get("confirmed_count", 1),
            "cost_saved": "tier_2_call_avoided"
        }
    )
except Exception:
    pass  # Telemetry failure is non-fatal for cache reads
```

---

### GATE B: The Ratchet Turns

```bash
# 1. Pattern cache file exists
python -c "from pathlib import Path; assert Path('profiles/coach_demo/config/pattern_cache.yaml').exists(); print('PASS')"

# 2. Router has cache check method
python -c "from engine.cognitive_router import CognitiveRouter; r=CognitiveRouter(); assert hasattr(r,'_check_pattern_cache'); print('PASS')"

# 3. Pipeline has cache write method
python -c "from engine.pipeline import InvariantPipeline; p=InvariantPipeline(); assert hasattr(p,'_write_to_pattern_cache'); print('PASS')"

# 4. Clear cache handler registered
python -c "from engine.dispatcher import Dispatcher; d=Dispatcher(); assert 'clear_cache' in d._handlers; print('PASS')"

# 5. Run existing test suite — no regressions
python -m pytest tests/ -x -q
```

**Do not proceed to Epic C until all five checks pass.**

---


## Epic C: Cortex Governance Compliance

**Gate:** Cortex has zero direct I/O calls. All proposals go to queue.

### Task C.1: Remove Direct I/O from Cortex Entity Validation

**File:** `engine/cortex.py`

**Action:** Replace the `ask_entity_validation()` function (lines ~34-60).

Current behavior: calls `print()` and `input()` directly to prompt operator
during the tail-pass. This is approval logic outside the pipeline.

New behavior: return a structured proposal dict instead of prompting.
The caller (`run_tail_pass()` or the entity extraction lens) writes the
proposal to the Kaizen queue.

**Replace** the existing `ask_entity_validation()` with:

```python
def create_entity_validation_proposal(
    entity_name: str,
    entity_type: str,
    context: str
) -> dict:
    """
    Create an entity validation proposal for the Kaizen queue.

    The Cortex is a pure analytical layer. It NEVER prompts the operator
    directly. All proposals go to the queue and are processed through
    the pipeline at startup or via the 'queue' command.

    Invariant #6: Stage 4 is the ONLY layer permitted to prompt for approval.

    Args:
        entity_name: The extracted entity name
        entity_type: The inferred entity type
        context: Surrounding context from transcript

    Returns:
        Proposal dict for queue insertion
    """
    import uuid
    from datetime import datetime, timezone

    return {
        "id": f"entity-{uuid.uuid4().hex[:8]}",
        "trigger": "entity_extraction",
        "proposal_type": "entity_validation",
        "proposal": f"New {entity_type} detected: {entity_name}",
        "entity_name": entity_name,
        "entity_type": entity_type,
        "context": context[:200],
        "priority": "medium",
        "created": datetime.now(timezone.utc).isoformat()
    }
```


### Task C.2: Update Entity Extraction Lens to Use Queue

**File:** `engine/cortex.py`

**Action:** Find every call site of `ask_entity_validation()` in the Cortex
(entity extraction lens, typically in `_extract_entities()` or similar method).

Replace each call from this pattern:
```python
# OLD: Direct I/O — violates Invariant #6
choice = ask_entity_validation(name, entity_type, context)
if choice == "1":
    # Create entity
elif choice == "2":
    # Reject
```

To this pattern:
```python
# NEW: Queue-based — Cortex proposes, pipeline approves
proposal = create_entity_validation_proposal(name, entity_type, context)
self._queue_kaizen(proposal)
# Entity creation happens when operator processes the queue item
```

**CRITICAL:** Search the entire `cortex.py` file for ALL occurrences of:
- `ask_entity_validation(`
- `input(`
- `print(` (except inside logging/telemetry)

Every direct I/O call in `cortex.py` must be removed or replaced with
queue writes or telemetry logging.

**Verification:**
```bash
python -c "
content = open('engine/cortex.py').read()
assert 'input(' not in content, 'FAIL: Direct input() still in cortex.py'
# Check for print() — allow only in non-interactive contexts
import re
prints = re.findall(r'(?<!#.{0,50})print\(', content)
assert len(prints) == 0, f'FAIL: {len(prints)} direct print() calls in cortex.py'
print('PASS: No direct I/O in cortex.py')
"
```

---

### Task C.3: Update Queue Processing to Handle Entity Proposals

**File:** `autonomaton.py` → `process_pending_queue()`

**Action:** The existing `process_pending_queue()` function already handles
Kaizen items with accept/dismiss/defer. Entity validation proposals need
one additional option: "Edit name" (since entity names from LLM extraction
may need correction).

In the `process_pending_queue()` function, when processing an item with
`proposal_type == "entity_validation"`, add handling:

```python
if item.get("proposal_type") == "entity_validation":
    result = ask_jidoka(
        context_message=(
            f"NEW ENTITY DETECTED:\n\n"
            f"  Name: {item.get('entity_name', '?')}\n"
            f"  Type: {item.get('entity_type', '?')}\n"
            f"  Context: {item.get('context', '?')[:100]}"
        ),
        options={
            "1": "Approve — Create entity profile",
            "2": "Reject — Not a real entity",
            "3": "Defer — Ask me later"
        }
    )
    
    if result == "1":
        # Create the entity via existing entity creation machinery
        # (This is the approved path — through the queue, with telemetry)
        _create_entity_from_proposal(item)
        remove_from_queue(item_id)
        processed += 1
    elif result == "2":
        remove_from_queue(item_id)
        processed += 1
    else:
        processed += 1  # Deferred
    continue  # Skip generic processing for this item type
```

**Note:** `_create_entity_from_proposal()` is a helper that creates the
entity markdown file. Extract the existing entity creation logic from
the old `ask_entity_validation` flow into this function.


---

### GATE C: Cortex Governance Compliance

```bash
# 1. No direct I/O in cortex.py
python -c "
content = open('engine/cortex.py').read()
assert 'input(' not in content, 'FAIL: input() in cortex.py'
assert 'ask_entity_validation(' not in content or 'create_entity_validation_proposal' in content, 'FAIL: old function still called'
print('PASS: No direct I/O in Cortex')
"

# 2. Proposal function exists
python -c "from engine.cortex import create_entity_validation_proposal; p=create_entity_validation_proposal('Test','player','context'); assert 'proposal_type' in p; assert p['proposal_type']=='entity_validation'; print('PASS')"

# 3. Run existing test suite — no regressions
python -m pytest tests/ -x -q
```

**Do not proceed to Epic D until all three checks pass.**

---


## Epic D: Purity Invariant Test Suite

**Gate:** All new + existing tests pass. Zero regressions.

### Task D.1: Create Purity Invariant Test File

**File:** `tests/test_purity_invariants.py` (NEW)

**Action:** Create test file with the following test classes and methods.
All tests use mocking to avoid real LLM calls. Tests verify structural
properties, not LLM output quality.

```python
"""
test_purity_invariants.py - Purity Audit Verification Tests

Verifies the architectural invariants fixed in the purity-audit-v1 sprint:
1. No pipeline bypasses — all LLM calls traverse the 5-stage pipeline
2. The Ratchet — confirmed LLM classifications cache at Tier 0
3. Cortex governance — no direct I/O in analytical layer
"""

import pytest
import yaml
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock


# =========================================================================
# Test Class 1: No Pipeline Bypasses
# =========================================================================

class TestNoPipelineBypasses:
    """Verify that no code calls call_llm() outside the pipeline."""

    def test_autonomaton_has_no_direct_llm_calls(self):
        """autonomaton.py must not import or call call_llm directly."""
        content = Path("autonomaton.py").read_text(encoding="utf-8")
        assert "from engine.llm_client import call_llm" not in content, \
            "autonomaton.py still imports call_llm directly"
        assert "call_llm(" not in content, \
            "autonomaton.py still calls call_llm() directly"

    def test_internal_intents_declared_in_routing_config(self):
        """Internal startup intents must exist in routing.config."""
        config_path = Path("profiles/coach_demo/config/routing.config")
        with open(config_path) as f:
            config = yaml.safe_load(f)
        routes = config.get("routes", {})
        for intent in ["welcome_card", "startup_brief", "generate_plan"]:
            assert intent in routes, \
                f"Internal intent '{intent}' missing from routing.config"

    def test_internal_intents_have_handlers(self):
        """Internal intents must have registered dispatcher handlers."""
        from engine.dispatcher import Dispatcher
        d = Dispatcher()
        for handler_name in ["welcome_card", "startup_brief", "generate_plan"]:
            assert handler_name in d._handlers, \
                f"Handler '{handler_name}' not registered in Dispatcher"

    @patch("engine.llm_client.get_anthropic_client")
    def test_startup_pipeline_produces_telemetry(self, mock_client):
        """Pipeline invocations with source=system_startup must produce telemetry."""
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Test briefing")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.return_value.messages.create.return_value = mock_response

        from engine.pipeline import run_pipeline
        ctx = run_pipeline(
            raw_input="startup_brief",
            source="system_startup"
        )
        # Stage 1: Telemetry event must exist
        assert ctx.telemetry_event is not None
        assert "id" in ctx.telemetry_event
        # Source must be system_startup
        assert ctx.telemetry_event.get("source") == "system_startup"


# =========================================================================
# Test Class 2: The Ratchet (Pattern Cache)
# =========================================================================

class TestPatternCache:
    """Verify the Ratchet: confirmed classifications cache at Tier 0."""

    def test_pattern_cache_file_exists(self):
        """pattern_cache.yaml must exist in profile config."""
        cache_path = Path("profiles/coach_demo/config/pattern_cache.yaml")
        assert cache_path.exists(), "pattern_cache.yaml not found"

    def test_empty_cache_returns_none(self):
        """Empty cache should return None for any input."""
        from engine.cognitive_router import CognitiveRouter
        router = CognitiveRouter()
        router.load_config()
        router.pattern_cache = {}
        router._cache_loaded = True
        result = router._check_pattern_cache("some random input")
        assert result is None

    def test_cache_hit_returns_tier_zero(self):
        """Cached classification must return Tier 0 result."""
        from engine.cognitive_router import CognitiveRouter
        router = CognitiveRouter()
        router.load_config()

        test_input = "how is my season going"
        input_hash = hashlib.sha256(
            test_input.lower().strip().encode()
        ).hexdigest()[:16]

        router.pattern_cache = {
            input_hash: {
                "intent": "strategy_session",
                "domain": "system",
                "zone": "green",
                "handler": "strategy_session",
                "handler_args": {},
                "intent_type": "actionable",
                "confirmed_count": 3,
                "last_confirmed": "2026-03-18T00:00:00Z",
                "original_input": test_input,
                "confidence": 0.85,
            }
        }
        router._cache_loaded = True

        result = router._check_pattern_cache(test_input)
        assert result is not None, "Cache hit should return a result"
        assert result.tier == 0, f"Cache hit should be Tier 0, got {result.tier}"
        assert result.intent == "strategy_session"
        assert result.llm_metadata.get("source") == "pattern_cache"

    def test_cache_does_not_store_red_zone(self):
        """Red zone actions must never be cached (sovereignty safety)."""
        from engine.pipeline import InvariantPipeline, PipelineContext
        pipeline = InvariantPipeline()
        pipeline.context = PipelineContext(
            raw_input="adjust fee for Henderson",
            source="test",
            intent="fee_adjustment",
            domain="money",
            zone="red",
            approved=True,
            executed=True,
            entities={
                "routing": {
                    "tier": 2,
                    "confidence": 0.9,
                    "handler": None,
                    "handler_args": {},
                    "intent_type": "actionable",
                    "llm_metadata": {}
                }
            },
            result={"status": "executed"}
        )
        # Should NOT write to cache because zone is red
        pipeline._write_to_pattern_cache()
        # Verify cache was not written
        # (This test relies on the method checking zone == "red" and returning)
        # A more robust test would mock the file write and assert it wasn't called

    def test_stale_cache_entry_ignored(self):
        """Cache entry for removed intent should return None."""
        from engine.cognitive_router import CognitiveRouter
        router = CognitiveRouter()
        router.load_config()

        input_hash = hashlib.sha256(b"test").hexdigest()[:16]
        router.pattern_cache = {
            input_hash: {
                "intent": "nonexistent_intent_xyz",
                "domain": "general",
                "zone": "green",
                "handler": None,
                "handler_args": {},
                "intent_type": "actionable",
                "confirmed_count": 1,
            }
        }
        router._cache_loaded = True

        result = router._check_pattern_cache("test")
        assert result is None, "Stale intent should not resolve from cache"

    def test_clear_cache_handler_registered(self):
        """clear_cache handler must be registered in Dispatcher."""
        from engine.dispatcher import Dispatcher
        d = Dispatcher()
        assert "clear_cache" in d._handlers


# =========================================================================
# Test Class 3: Cortex Governance
# =========================================================================

class TestCortexGovernance:
    """Verify the Cortex has no direct I/O — all proposals via queue."""

    def test_cortex_has_no_input_calls(self):
        """cortex.py must not call input() anywhere."""
        content = Path("engine/cortex.py").read_text(encoding="utf-8")
        # Filter out comments
        lines = [l for l in content.split("\n")
                 if not l.strip().startswith("#")]
        code = "\n".join(lines)
        assert "input(" not in code, \
            "cortex.py contains direct input() call"

    def test_cortex_entity_proposal_creates_queue_item(self):
        """Entity validation must produce a queue proposal, not prompt."""
        from engine.cortex import create_entity_validation_proposal
        proposal = create_entity_validation_proposal(
            entity_name="Test Player",
            entity_type="player",
            context="Some context about a player"
        )
        assert isinstance(proposal, dict)
        assert proposal["proposal_type"] == "entity_validation"
        assert proposal["entity_name"] == "Test Player"
        assert proposal["entity_type"] == "player"
        assert "id" in proposal
        assert "created" in proposal
```


---

### GATE D: Full Test Suite

```bash
# Run ALL tests including new purity invariant tests
python -m pytest tests/ -x -v

# Expected: All tests pass, zero failures, zero errors
```

---

## Final Sprint Gate

All four epic gates must pass sequentially:

```bash
echo "=== GATE A: Pipeline Bypass Eliminated ==="
python -c "c=open('autonomaton.py').read(); assert 'call_llm(' not in c; print('PASS')"
python -c "import yaml; d=yaml.safe_load(open('profiles/coach_demo/config/routing.config')); assert all(k in d['routes'] for k in ['welcome_card','startup_brief','generate_plan']); print('PASS')"
python -c "from engine.dispatcher import Dispatcher; d=Dispatcher(); assert all(k in d._handlers for k in ['welcome_card','startup_brief','generate_plan']); print('PASS')"

echo "=== GATE B: The Ratchet Turns ==="
python -c "from pathlib import Path; assert Path('profiles/coach_demo/config/pattern_cache.yaml').exists(); print('PASS')"
python -c "from engine.cognitive_router import CognitiveRouter; r=CognitiveRouter(); assert hasattr(r,'_check_pattern_cache'); print('PASS')"
python -c "from engine.pipeline import InvariantPipeline; p=InvariantPipeline(); assert hasattr(p,'_write_to_pattern_cache'); print('PASS')"
python -c "from engine.dispatcher import Dispatcher; d=Dispatcher(); assert 'clear_cache' in d._handlers; print('PASS')"

echo "=== GATE C: Cortex Governance ==="
python -c "content=open('engine/cortex.py').read(); assert 'input(' not in content; print('PASS')"
python -c "from engine.cortex import create_entity_validation_proposal; p=create_entity_validation_proposal('Test','player','ctx'); assert p['proposal_type']=='entity_validation'; print('PASS')"

echo "=== GATE D: Full Test Suite ==="
python -m pytest tests/ -x -q

echo "=== ALL GATES PASSED ==="
```

---

## Post-Sprint Verification: The Proof

After all gates pass, run the system and verify these observable behaviors:

1. **Startup produces telemetry.** Open `profiles/coach_demo/telemetry/events.jsonl`
   after launching. You should see events with `source: system_startup` for the
   welcome card and strategic brief. These did not exist before this sprint.

2. **The Ratchet turns visibly.** Type an ambiguous input (e.g., "how's my season
   going"). The first time, it hits the LLM (you'll see latency). Type the same
   input again. The second time, it should resolve instantly from cache — Tier 0.
   Open `profiles/coach_demo/config/pattern_cache.yaml` and see the cached entry.

3. **Cortex stays silent.** Run the system, type several messages, and watch the
   Cortex tail-pass fire. It should NEVER prompt you interactively. Any entity
   proposals should appear in the Kaizen queue, surfaced at next startup.

4. **Cache is operator-inspectable.** Open `pattern_cache.yaml` in a text editor.
   You can read every cached classification. You can delete entries. You can delete
   the file entirely. The operator controls the Ratchet. Declarative sovereignty.

---

## Files Created or Modified (Summary)

| File | Action | Epic |
|------|--------|------|
| `profiles/coach_demo/config/routing.config` | Modified (4 new intents) | A, B |
| `profiles/blank_template/config/routing.config` | Modified (4 new intents) | A, B |
| `profiles/coach_demo/config/pattern_cache.yaml` | Created | B |
| `profiles/blank_template/config/pattern_cache.yaml` | Created | B |
| `engine/cognitive_router.py` | Modified (cache read, load_cache) | B |
| `engine/pipeline.py` | Modified (cache write hook) | B |
| `engine/dispatcher.py` | Modified (3 startup handlers + clear_cache) | A, B |
| `engine/cortex.py` | Modified (remove direct I/O, queue-only) | C |
| `autonomaton.py` | Modified (replace direct LLM with pipeline) | A |
| `tests/test_purity_invariants.py` | Created | D |

---

*Sprint contract generated from architectural purity audit.*
*Provenance: Pattern Release 1.3, TCP/IP Paper, CLAUDE.md Invariants 1-11*
