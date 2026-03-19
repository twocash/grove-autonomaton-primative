# SPRINT CONTRACT: Pipeline Telemetry Compliance

> Atomic execution contract generated from SPEC.md
> Generated: 2026-03-19
> Sprint: `pipeline-compliance-v1`

---

## Pre-Sprint: Hygiene & Baseline

### Task 0.1: Delete tmpclaude files and update .gitignore
```cmd
cd /d C:\GitHub\grove-autonomaton-primative
del tmpclaude-*-cwd
del nul
```

Add to `.gitignore`:
```
tmpclaude-*
__pycache__/
*.pyc
.pytest_cache/
nul
```

### Task 0.2: Verify clean baseline
```cmd
python -m pytest tests/ -x -q
```
ALL existing tests must pass. Stop if they don't.

---

## Epic A: Per-Stage Telemetry Traces (V1, V4, V7)

**Gate:** telemetry.jsonl contains 5 events per pipeline traversal,
each with an `inferred.stage` field and `inferred.pipeline_id`.

### Task A.1: Modify Stage 1 — Add stage identifier

**File:** `engine/pipeline.py`
**Method:** `_run_telemetry()`

Change the existing log_event() call to include stage identifier:

```python
def _run_telemetry(self) -> None:
    self.context.telemetry_event = log_event(
        source=self.context.source,
        raw_transcript=self.context.raw_input,
        zone_context=self.context.zone,
        inferred={"stage": "telemetry"}
    )
```

The `id` field of this event becomes pipeline_id for stages 2-5.

### Task A.2: Add Stage 2 trace — Recognition

**File:** `engine/pipeline.py`
**Method:** `_run_recognition()`

Add log_event() call as the FINAL line of the method, after
BOTH the force_route path AND the normal classification path.
(Add it once, at the very end, so both paths hit it.)

```python
    # --- End of _run_recognition ---
    # Stage 2 trace: recognition complete
    routing_info = self.context.entities.get("routing", {})
    log_event(
        source=self.context.source,
        raw_transcript=self.context.raw_input[:200],
        zone_context=self.context.zone,
        intent=self.context.intent,
        tier=routing_info.get("tier"),
        confidence=routing_info.get("confidence"),
        inferred={
            "stage": "recognition",
            "pipeline_id": self.context.telemetry_event.get("id"),
            "domain": self.context.domain,
            "handler": routing_info.get("handler"),
            "intent_type": routing_info.get("intent_type"),
            "method": "forced" if self.context.force_route else (
                "cache" if routing_info.get("llm_metadata", {}).get("source") == "pattern_cache"
                else ("llm" if routing_info.get("tier", 0) >= 2 else "keyword")
            ),
        }
    )
```

### Task A.3: Add Stage 3 trace — Compilation

**File:** `engine/pipeline.py`
**Method:** `_run_compilation()`

Add log_event() as the FINAL line of the method:

```python
    # --- End of _run_compilation ---
    routing_info = self.context.entities.get("routing", {})
    log_event(
        source=self.context.source,
        raw_transcript=self.context.raw_input[:200],
        zone_context=self.context.zone,
        intent=self.context.intent,
        inferred={
            "stage": "compilation",
            "pipeline_id": self.context.telemetry_event.get("id"),
            "intent_type": routing_info.get("intent_type", "actionable"),
            "dock_chunks": len(self.context.dock_context) if self.context.dock_context else 0,
            "skipped": routing_info.get("intent_type") == "conversational",
        }
    )
```

### Task A.4: Add Stage 4 trace — Approval

**File:** `engine/pipeline.py`
**Method:** `_run_approval()`

This method has MULTIPLE return paths (green auto, yellow confirm,
red confirm, clarification jidoka). The trace must fire on ALL paths.

Add log_event() as the LAST line of _run_approval(), AFTER all
the if/elif/else branches. Every branch sets self.context.approved
and returns or falls through — the trace goes after ALL of them:

```python
    # --- End of _run_approval (after ALL branches) ---
    routing_info = self.context.entities.get("routing", {})
    log_event(
        source=self.context.source,
        raw_transcript=self.context.raw_input[:200],
        zone_context=self.context.zone,
        intent=self.context.intent,
        human_feedback="approved" if self.context.approved else "rejected",
        inferred={
            "stage": "approval",
            "pipeline_id": self.context.telemetry_event.get("id"),
            "effective_zone": self.context.zone,
            "action_required": routing_info.get("action_required", True),
        }
    )
```

CRITICAL: _handle_clarification_jidoka() has early return paths.
These set self.context.approved and return FROM _handle_clarification_jidoka
back to _run_approval. The approval trace at the end of _run_approval
still fires after the clarification handler returns. Verify this.

**CORRECTION on Task A.4:** _run_approval() has EARLY RETURNS that
skip code placed at the end. The clarification jidoka path has
`self._handle_clarification_jidoka(); return`. The non-actionable
green path has `self.context.approved = True; return`.

The correct approach: create a helper method _log_approval_trace()
and call it before EVERY return path in _run_approval():

```python
def _log_approval_trace(self) -> None:
    """Log Stage 4 approval trace. Called before every return."""
    routing_info = self.context.entities.get("routing", {})
    log_event(
        source=self.context.source,
        raw_transcript=self.context.raw_input[:200],
        zone_context=self.context.zone,
        intent=self.context.intent,
        human_feedback="approved" if self.context.approved else "rejected",
        inferred={
            "stage": "approval",
            "pipeline_id": self.context.telemetry_event.get("id"),
            "effective_zone": self.context.zone,
            "action_required": routing_info.get("action_required", True),
        }
    )
```

Then in _run_approval(), add `self._log_approval_trace()` before:
1. The `return` after `self._handle_clarification_jidoka()`
2. The `return` after non-actionable green auto-approve
3. At the END of the method (covers green/yellow/red/unknown branches)

### Task A.5: Log Jidoka Resolution (V4)

**File:** `engine/pipeline.py`
**Method:** `_handle_clarification_jidoka()`

After EACH resolution path (Tier A confirmed, Tier B resolved,
generic fallback resolved), add a log_event for the clarification:

```python
log_event(
    source="clarification_jidoka",
    raw_transcript=self.context.raw_input[:200],
    zone_context=self.context.zone,
    intent=self.context.intent,
    human_feedback="clarified",
    inferred={
        "stage": "approval_jidoka",
        "pipeline_id": self.context.telemetry_event.get("id"),
        "resolved_intent": self.context.intent,
        "jidoka_tier": "a" or "b" or "generic",  # whichever path
    }
)
```

Insert this AFTER the context is updated with the resolved routing
but BEFORE the method returns.

### Task A.6: Modify Stage 5 trace — add pipeline_id

**File:** `engine/pipeline.py`
**Method:** `_log_pipeline_completion()`

The existing completion log already fires at Stage 5. Modify it
to include pipeline_id and change stage name from "pipeline_complete"
to "execution":

Change `"stage": "pipeline_complete"` to `"stage": "execution"`
and add `"pipeline_id": self.context.telemetry_event.get("id")`
to the inferred dict.

### Task A.7: Populate cost_usd in completion trace (V7)

**File:** `engine/pipeline.py`
**Method:** `_log_pipeline_completion()`

The telemetry schema supports cost_usd but the pipeline never
populates it. Add cost_usd extraction from LLM metadata:

```python
llm_metadata = routing_info.get("llm_metadata", {})
cost = llm_metadata.get("cost_usd")  # Set by call_llm if available
```

Pass `cost_usd=cost` to the log_event() call.

### GATE A: Per-Stage Telemetry

```bash
# 1. Run pipeline and verify 5 stage traces
python -c "
from engine.profile import set_profile
set_profile('reference')
from engine.pipeline import run_pipeline
from engine.telemetry import read_recent_events
ctx = run_pipeline('hello', source='test')
pid = ctx.telemetry_event['id']
events = read_recent_events(limit=50)
stages = [e['inferred'].get('stage') for e in events
          if e.get('inferred', {}).get('pipeline_id') == pid
          or e['id'] == pid]
print(f'Stages found: {stages}')
required = {'telemetry','recognition','compilation','approval','execution'}
assert required.issubset(set(stages)), f'Missing: {required - set(stages)}'
print('PASS: All 5 stage traces present')
"

# 2. No regressions
python -m pytest tests/ -x -q
```

**Do not proceed to Epic B until both checks pass.**

---

## Epic B: Declarative Clarification (V2, V8)

**Gate:** Zero hardcoded domain logic in engine/cognitive_router.py.

### Task B.1: Create clarification.yaml for reference profile

**File:** `profiles/reference/config/clarification.yaml` (NEW)

```yaml
# clarification.yaml
# Fallback options when Jidoka fires for ambiguous input.
# Each option resolves to an intent in THIS profile's routing.config.

fallback_options:
  "1":
    label: "Start a conversation about this topic"
    intent: "general_chat"
  "2":
    label: "Check system status or information"
    intent: "dock_status"
  "3":
    label: "I'll rephrase with more context"
    intent: null
```

### Task B.2: Create clarification.yaml for coach_demo

**File:** `profiles/coach_demo/config/clarification.yaml` (NEW)

```yaml
fallback_options:
  "1":
    label: "Draft or compile content"
    intent: "content_engine"
  "2":
    label: "Check on status or information"
    intent: "dock_status"
  "3":
    label: "Just chatting"
    intent: "general_chat"
  "4":
    label: "I'll rephrase with more context"
    intent: null
```

### Task B.3: Create clarification.yaml for blank_template

**File:** `profiles/blank_template/config/clarification.yaml` (NEW)

Same as reference profile (minimal, generic).

### Task B.4: Rewrite get_clarification_options() to read config

**File:** `engine/cognitive_router.py`

Replace the existing get_clarification_options() function:

```python
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
```

### Task B.5: Rewrite resolve_clarification() to read config

**File:** `engine/cognitive_router.py`

Replace the existing resolve_clarification() function:

```python
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
```

### GATE B: Declarative Clarification

```bash
# 1. No domain logic in cognitive_router.py
python -c "
content = open('engine/cognitive_router.py').read()
terms = ['calendar_schedule','mcp_calendar','google_calendar',
         'content_draft','lessons']
for t in terms:
    assert t not in content, f'Domain term \"{t}\" still in engine'
print('PASS: Zero domain logic in engine')
"

# 2. Clarification loads from config
python -c "
from engine.profile import set_profile
set_profile('reference')
from engine.cognitive_router import get_clarification_options
opts = get_clarification_options()
assert len(opts) >= 2
print(f'PASS: {len(opts)} options loaded from config')
"

# 3. Resolve maps to valid intents
python -c "
from engine.profile import set_profile
set_profile('reference')
from engine.cognitive_router import resolve_clarification, get_router
router = get_router()
for choice in ['1','2','3']:
    result = resolve_clarification(choice, 'test')
    if result.intent != 'general_chat':
        assert result.intent in router.routes, f'{result.intent} not in routes'
print('PASS: All resolutions valid for profile')
"

# 4. No regressions
python -m pytest tests/ -x -q
```

---

## Epic C: Classification Accuracy (V3, V5)

**Gate:** "my name is bob" → general_chat in ALL profiles. No Jidoka.

### Task C.1: Expand general_chat keywords — all profiles

**Files:** `profiles/reference/config/routing.config`,
`profiles/coach_demo/config/routing.config`,
`profiles/blank_template/config/routing.config`

Replace general_chat keywords in ALL profiles:

```yaml
    keywords:
      - "hello"
      - "hi"
      - "hey"
      - "how are you"
      - "who are you"
      - "what can you do"
      - "good morning"
      - "good afternoon"
      - "good evening"
      - "my name is"
      - "thanks"
      - "thank you"
      - "bye"
      - "goodbye"
      - "nice to meet you"
      - "what is this"
      - "tell me about yourself"
```

### Task C.2: Add ambiguity floor to smart clarification

**File:** `engine/pipeline.py`
**Method:** `_handle_clarification_jidoka()`

Find the line:
```python
smart_options = self._generate_smart_clarification(self.context.raw_input)
```

Replace with:
```python
# Ambiguity floor: short unknown inputs skip LLM clarification.
# The LLM hallucinates specific options for genuinely unknown input.
word_count = len(self.context.raw_input.strip().split())
if word_count <= 2 and confidence < 0.2:
    smart_options = None
else:
    smart_options = self._generate_smart_clarification(self.context.raw_input)
```

### GATE C

```bash
python -c "
from engine.profile import set_profile
for profile in ['reference', 'coach_demo']:
    set_profile(profile)
    from engine.cognitive_router import classify_intent, reset_router
    reset_router()
    for text in ['hello','my name is bob','thanks','goodbye']:
        r = classify_intent(text)
        assert r.intent == 'general_chat', f'{profile}: \"{text}\" → {r.intent}'
    print(f'PASS: {profile}')
"
python -m pytest tests/ -x -q
```

---

## Epic D: Skill Build Pipeline Compliance (V6)

**Gate:** Zero input() calls outside the REPL prompt.

### Task D.1: Update pit_crew_build extract_args

**Files:** ALL profiles' `routing.config`

Update the pit_crew_build route to extract description inline:

```yaml
  pit_crew_build:
    tier: 3
    zone: red
    domain: system
    intent_type: actionable
    description: "Build new skill (RED ZONE). Usage: build skill [name] [description]"
    keywords:
      - "build skill"
    handler: "pit_crew"
    handler_args:
      action: "build"
    extract_args:
      - name: "skill_name"
        position: 2
      - name: "description"
        position: 3
```

### Task D.2: Update pit_crew handler for inline description

**File:** `engine/dispatcher.py`

In the pit_crew handler (_handle_pit_crew or equivalent), when
action is "build": read skill_name and description from
routing_result.extracted_args. If description is empty, return:

```python
return DispatchResult(
    success=False,
    message="Usage: build skill [name] [description]\n"
            "Example: build skill weekly-report generates a weekly summary from telemetry",
    data={"type": "pit_crew_usage"}
)
```

If description is present, proceed with build_skill(name, description).

### Task D.3: Remove handle_skill_build_interactive()

**File:** `autonomaton.py`

Delete the entire `handle_skill_build_interactive()` function.
Remove the call to it in `display_result()` where
`data_type == "pit_crew_build"` and `data.get("requires_description")`.

Replace that display_result branch with a simple message display
(the handler now returns usage instructions via DispatchResult).

### GATE D

```bash
python -c "
import re
content = open('autonomaton.py').read()
# Only the REPL prompt should use input()
calls = [l.strip() for l in content.split('\n')
         if 'input(' in l and not l.strip().startswith('#')
         and 'raw_input' not in l]
# Filter to actual input() calls (not variable names)
actual = [l for l in calls if re.search(r'(?<!raw_)input\(', l)]
assert len(actual) <= 1, f'Found {len(actual)} input() calls: {actual}'
print('PASS: ≤1 input() call (REPL prompt)')
"
python -m pytest tests/ -x -q
```

---

## Epic E: Glass Telemetry Consumer

**Gate:** Glass reads telemetry events by pipeline_id.

### Task E.1: Add pipeline event reader to glass.py

**File:** `engine/glass.py`

Add a function that reads recent telemetry events and filters
by pipeline_id:

```python
def read_pipeline_events(pipeline_id: str) -> list[dict]:
    """Read telemetry events for a specific pipeline traversal.

    Returns events ordered by stage for glass rendering.
    The pipeline_id is the Stage 1 event id.
    """
    from engine.telemetry import read_recent_events

    events = read_recent_events(limit=50)

    pipeline_events = []
    for event in events:
        if event.get("id") == pipeline_id:
            pipeline_events.append(event)
        elif event.get("inferred", {}).get("pipeline_id") == pipeline_id:
            pipeline_events.append(event)

    # Sort by stage order
    stage_order = {"telemetry": 1, "recognition": 2, "compilation": 3,
                   "approval": 4, "approval_jidoka": 4, "execution": 5}
    pipeline_events.sort(
        key=lambda e: stage_order.get(
            e.get("inferred", {}).get("stage", ""), 99
        )
    )
    return pipeline_events
```

### Task E.2: Add telemetry-based glass renderer

**File:** `engine/glass.py`

Add a function that renders the glass box from telemetry events:

```python
def display_glass_from_telemetry(pipeline_id: str,
                                 level: str = "medium") -> Optional[str]:
    """Render glass pipeline from telemetry events.

    This is the architecturally correct glass renderer.
    It reads from the same telemetry stream as Cortex, Ratchet,
    and Skill Flywheel. No PipelineContext needed.
    """
    events = read_pipeline_events(pipeline_id)
    if not events:
        return None

    lines = []
    width = 58
    border = f"{_c.DIM}{'─' * width}{_c.RESET}"
    lines.append(f"  {border}")
    lines.append(f"  {_c.DIM}│{_c.RESET} {_c.CYAN}GLASS PIPELINE{_c.RESET}")
    lines.append(f"  {border}")

    for event in events:
        stage = event.get("inferred", {}).get("stage", "")
        _render_stage_from_event(lines, event, stage, level)

    lines.append(f"  {border}")
    print("\n".join(lines))

    # Check for ratchet announcement
    for event in events:
        if event.get("inferred", {}).get("method") == "cache":
            return _format_ratchet_from_event(event)
    return None
```

Add `_render_stage_from_event()` that reads telemetry fields:

```python
def _render_stage_from_event(lines: list, event: dict,
                              stage: str, level: str) -> None:
    """Render one stage line from a telemetry event."""
    inf = event.get("inferred", {})

    if stage == "telemetry":
        eid = event.get("id", "unknown")[:8]
        src = event.get("source", "unknown")
        lines.append(
            f"  {_c.DIM}│{_c.RESET} {_c.CYAN}1{_c.RESET} Telemetry   "
            f"{_c.DIM}id:{_c.RESET}{eid} "
            f"{_c.DIM}src:{_c.RESET}{src}")

    elif stage == "recognition":
        intent = event.get("intent", "unknown")
        tier = event.get("tier", 0)
        conf = event.get("confidence", 0.0)
        method = inf.get("method", "unknown")
        cost = "$0.00" if tier < 2 else "~$0.003"
        lines.append(
            f"  {_c.DIM}│{_c.RESET} {_c.CYAN}2{_c.RESET} Recognition "
            f"{_c.DIM}intent:{_c.RESET}{intent} "
            f"{_c.DIM}T{tier}{_c.RESET} {method} "
            f"{_c.DIM}{cost}{_c.RESET}")
        if level in ("medium", "full") and conf > 0:
            lines.append(
                f"  {_c.DIM}│{_c.RESET}             "
                f"{_c.DIM}confidence:{_c.RESET} {conf:.0%}")

    elif stage == "compilation":
        skipped = inf.get("skipped", False)
        chunks = inf.get("dock_chunks", 0)
        comp = "Skipped — conversational" if skipped else f"Dock: {chunks} chunk(s)"
        lines.append(
            f"  {_c.DIM}│{_c.RESET} {_c.CYAN}3{_c.RESET} Compilation {comp}")

    elif stage == "approval":
        zone = event.get("zone_context", "green")
        feedback = event.get("human_feedback", "")
        zc = _get_zone_color(zone)
        if feedback == "rejected":
            app = "CANCELLED"
        elif zone == "green":
            app = "GREEN auto-approve"
        elif zone == "yellow":
            app = "YELLOW — confirmed"
        elif zone == "red":
            app = "RED — explicit approval"
        else:
            app = zone.upper()
        lines.append(
            f"  {_c.DIM}│{_c.RESET} {_c.CYAN}4{_c.RESET} Approval    "
            f"{zc}{app}{_c.RESET}")

    elif stage == "execution":
        handler = inf.get("handler", "passthrough")
        executed = "executed" # if it reached telemetry, it executed
        lines.append(
            f"  {_c.DIM}│{_c.RESET} {_c.CYAN}5{_c.RESET} Execution   "
            f"{_c.DIM}handler:{_c.RESET}{handler} "
            f"{_c.DIM}[{executed}]{_c.RESET}")
```

### Task E.3: Wire telemetry-based glass in autonomaton.py

**File:** `autonomaton.py`

In the REPL loop, replace the existing glass rendering:

```python
# Current (reads PipelineContext):
if glass_enabled:
    from engine.glass import display_glass_pipeline, display_ratchet_announcement
    ratchet_msg = display_glass_pipeline(context, glass_level)
    if ratchet_msg:
        display_ratchet_announcement(ratchet_msg)
```

With:

```python
# New (reads telemetry stream):
if glass_enabled:
    from engine.glass import display_glass_from_telemetry, display_ratchet_announcement
    pipeline_id = context.telemetry_event.get("id", "")
    ratchet_msg = display_glass_from_telemetry(pipeline_id, glass_level)
    if ratchet_msg:
        display_ratchet_announcement(ratchet_msg)
```

### GATE E

```bash
# Manual test — glass renders from telemetry
# python autonomaton.py --profile reference
# Type "hello" — glass box should appear with all 5 stages
# Type "show config" — glass box, Tier 0 keyword match
# Verify glass output matches what's in telemetry.jsonl
```

---

## Epic F: Invariant Test Suite

**Gate:** All tests pass. Invariants permanently enforced.

### Task F.1: Create test_pipeline_compliance.py

**File:** `tests/test_pipeline_compliance.py` (NEW)

```python
"""
test_pipeline_compliance.py - Architectural Invariant Tests

These tests ENFORCE the architectural claims from the TCP/IP paper
and Pattern Document. They verify structural properties, not behavior.
If any future sprint breaks these, the test suite blocks the merge.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestPerStageTraces:
    """V1: Every stage produces a structured trace."""

    def _run_and_collect(self, text="hello", profile="reference"):
        from engine.profile import set_profile
        set_profile(profile)
        from engine.cognitive_router import reset_router
        reset_router()
        from engine.pipeline import run_pipeline
        ctx = run_pipeline(text, source="test_compliance")
        # Read telemetry
        from engine.profile import get_telemetry_path
        events = []
        tpath = get_telemetry_path()
        if tpath.exists():
            with open(tpath) as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))
        pid = ctx.telemetry_event["id"]
        return [e for e in events
                if e.get("id") == pid
                or e.get("inferred", {}).get("pipeline_id") == pid]

    def test_five_stage_traces_exist(self):
        events = self._run_and_collect("hello")
        stages = {e.get("inferred", {}).get("stage") for e in events}
        required = {"telemetry", "recognition", "compilation",
                    "approval", "execution"}
        assert required.issubset(stages), \
            f"Missing stages: {required - stages}"

    def test_pipeline_id_correlation(self):
        events = self._run_and_collect("hello")
        pid = events[0]["id"]  # Stage 1 event
        for e in events[1:]:
            assert e.get("inferred", {}).get("pipeline_id") == pid, \
                f"Stage {e.get('inferred',{}).get('stage')} missing pipeline_id"

    def test_recognition_includes_routing_data(self):
        events = self._run_and_collect("hello")
        rec = [e for e in events
               if e.get("inferred", {}).get("stage") == "recognition"]
        assert len(rec) == 1
        assert rec[0].get("intent") is not None
        assert rec[0].get("tier") is not None

    def test_approval_includes_human_feedback(self):
        events = self._run_and_collect("hello")
        appr = [e for e in events
                if e.get("inferred", {}).get("stage") == "approval"]
        assert len(appr) == 1
        assert appr[0].get("human_feedback") in ("approved", "rejected")


class TestProfileIsolation:
    """V2: Zero domain logic in engine code."""

    def test_no_domain_terms_in_engine(self):
        domain_terms = [
            "content_draft", "calendar_schedule", "mcp_calendar",
            "google_calendar", "lessons", "coaching", "player",
        ]
        engine_dir = Path("engine/")
        for py_file in engine_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for term in domain_terms:
                assert term not in content, \
                    f"Domain term '{term}' in {py_file.name}"

    def test_clarification_resolves_to_valid_intents(self):
        from engine.profile import set_profile
        from engine.cognitive_router import (
            get_clarification_options, resolve_clarification,
            get_router, reset_router
        )
        for profile in ["reference", "coach_demo"]:
            set_profile(profile)
            reset_router()
            router = get_router()
            opts = get_clarification_options()
            for choice in opts.keys():
                result = resolve_clarification(choice, "test")
                if result.intent != "general_chat":
                    assert result.intent in router.routes, \
                        f"{profile}: '{result.intent}' not in routes"


class TestClassificationAccuracy:
    """V3: Basic conversational input classifies correctly."""

    @pytest.mark.parametrize("text", [
        "hello", "hi", "my name is bob", "thanks",
        "thank you", "goodbye", "what is this",
    ])
    def test_conversational_input(self, text):
        from engine.profile import set_profile
        from engine.cognitive_router import classify_intent, reset_router
        set_profile("reference")
        reset_router()
        result = classify_intent(text)
        assert result.intent == "general_chat", \
            f"'{text}' classified as '{result.intent}'"
        assert result.confidence >= 0.5, \
            f"'{text}' confidence {result.confidence} too low"


class TestNoPipelineBypasses:
    """V6: Zero input() calls outside ux.py and REPL prompt."""

    def test_no_input_in_engine_except_ux(self):
        import re
        allowed = {"ux.py"}
        for py_file in Path("engine/").glob("*.py"):
            if py_file.name in allowed:
                continue
            content = py_file.read_text(encoding="utf-8")
            for i, line in enumerate(content.split("\n")):
                if line.lstrip().startswith("#"):
                    continue
                if re.search(r'(?<!raw_)input\(', line):
                    pytest.fail(
                        f"{py_file.name}:{i+1} has input() outside ux.py"
                    )

    def test_autonomaton_single_input_call(self):
        import re
        content = Path("autonomaton.py").read_text(encoding="utf-8")
        lines = content.split("\n")
        input_lines = []
        for i, line in enumerate(lines):
            if line.lstrip().startswith("#"):
                continue
            if re.search(r'(?<!raw_)input\(', line):
                input_lines.append(i + 1)
        assert len(input_lines) <= 1, \
            f"autonomaton.py has input() on lines {input_lines}"
```

### Task F.2: Run full test suite

```bash
python -m pytest tests/ -x -q --tb=short
```

ALL tests — existing + new — must pass.

### GATE F: Final

```bash
python -m pytest tests/ -x -q
python -c "
from pathlib import Path
assert len(list(Path('.').glob('tmpclaude-*'))) == 0
print('PASS: clean repo')
"
```

---

## Post-Sprint: Commit

```bat
@echo off
cd /d C:\GitHub\grove-autonomaton-primative
git add -A
git commit -m "pipeline-compliance-v1"
git push origin master
```

---

## Summary

| Epic | What It Fixes | Lines (est) |
|------|---------------|-------------|
| A: Per-stage traces | V1, V4, V7 | ~80 |
| B: Declarative clarification | V2, V8 | ~100 |
| C: Classification accuracy | V3, V5 | ~30 |
| D: Skill build compliance | V6 | ~40 |
| E: Glass telemetry consumer | Display | ~80 |
| F: Invariant tests | Regression gate | ~150 |
| Hygiene | tmpclaude, .gitignore | ~5 |
| **Total** | **8 violations** | **~485 lines** |
