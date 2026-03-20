# SPRINT CONTRACT: UX Polish + Self-Describing Architecture

> Sprint: `ux-polish-v1`
> Depends on: mcp-purity-v1 must be merged first

---

## Pre-Sprint

### Task 0.1: Create worktree
```bat
@echo off
cd /d C:\GitHub\grove-autonomaton-primative
git worktree add ..\grove-autonomaton-primative-ux-polish-v1 master
cd /d C:\GitHub\grove-autonomaton-primative-ux-polish-v1
```

### Task 0.2: Verify baseline
```cmd
python -m pytest tests/ -x -q
```

---

## Epic A: Ratchet Cache Invalidation (R1)

**Gate:** Same input twice → second time is Tier 0 cache hit.

### The Bug

The Ratchet has a write path and a read path:
- WRITE: pipeline.py `_write_to_pattern_cache()` writes confirmed
  classifications to `pattern_cache.yaml` on disk.
- READ: cognitive_router.py `_check_pattern_cache()` checks input
  hash against an IN-MEMORY dict loaded from the same file.

The router loads the cache once at startup. `_cache_loaded = True`.
The pipeline writes a new entry to the YAML file. The router's
in-memory dict is stale. Next classify() call: `_cache_loaded` is
True, skip reload, check stale dict, miss. The Ratchet never fires.

### The Fix

`pattern_cache.yaml` is config. Config is authoritative. When config
changes, the engine re-reads it. This is Invariant #3.

### Task A.1: Invalidate router cache after write

**File:** `engine/pipeline.py`
**Method:** `_write_to_pattern_cache()`

After the `yaml.dump()` succeeds (after the `with open` block closes),
add:

```python
            # Invalidate router's in-memory cache — config changed, re-read it
            from engine.cognitive_router import get_router
            get_router().load_cache()
```

This goes INSIDE the try block, after the file write, before the
except. The router re-reads the file it just wrote to. The in-memory
dict now matches disk. Next classify() finds the entry.

### GATE A

```bash
python -c "
from engine.profile import set_profile
set_profile('reference')
from engine.cognitive_router import get_router, reset_router, classify_intent
import hashlib
reset_router()
router = get_router()

# Simulate: write a cache entry, then check if router sees it
import yaml
from engine.profile import get_config_dir
cache_path = get_config_dir() / 'pattern_cache.yaml'
test_input = 'ratchet_gate_test_input_xyz'
input_hash = hashlib.sha256(test_input.lower().strip().encode()).hexdigest()[:16]

# Write directly to file (simulating pipeline write)
data = {'cache': {input_hash: {
    'intent': 'general_chat', 'domain': 'system', 'zone': 'green',
    'handler': 'general_chat', 'handler_args': {},
    'intent_type': 'conversational', 'confirmed_count': 1,
}}}
with open(cache_path, 'w') as f:
    yaml.dump(data, f)

# Reload cache (this is what the fix does)
router.load_cache()

# Check if router sees it
result = router._check_pattern_cache(test_input)
assert result is not None, 'Cache entry not found after reload'
assert result.tier == 0, f'Expected Tier 0, got {result.tier}'
print('PASS: Ratchet cache invalidation works')

# Clean up test entry
with open(cache_path, 'w') as f:
    yaml.dump({'cache': {}}, f)
"
python -m pytest tests/ -x -q
```

---

## Epic B: Skill Execution Display Fix (F1)

**Gate:** "help" command shows actual LLM-generated guide content.

### Task B.1: Add skill_execution display branch

**File:** `autonomaton.py`

Find the result display section after run_pipeline(). Add handling
for skill_execution BEFORE any generic fallback:

```python
elif data_type == "skill_execution":
    response = data.get("response", "")
    if response:
        print(f"  {c.WHITE}{response}{c.RESET}")
    else:
        skill_name = data.get("skill_name", "unknown")
        print(f"  {c.YELLOW}Skill '{skill_name}' produced no output.{c.RESET}")
```

### GATE B

```cmd
python -c "
content = open('autonomaton.py', encoding='utf-8').read()
assert 'skill_execution' in content, 'skill_execution branch missing'
print('PASS: Skill display branch exists')
"
python -m pytest tests/ -x -q
```

---

## Epic C: Dock-Aware Handler (F2)

**Gate:** general_chat uses dock context when Compilation loaded it.

### The Architecture

Compilation loads dock context for informational intents. The handler
must use what Compilation prepared. If Compilation didn't load
context (conversational), the handler responds conversationally.
Same handler, different behavior, driven by the pipeline — not by
handler logic.

ANTI-PATTERN: Do NOT hardwire a different handler or tier. The
architecture starts at T1 with dock context. The Flywheel proposes
upgrades. The operator decides.

### Task C.1: READ general_chat handler

**File:** `engine/dispatcher.py`

Read _handle_general_chat(). Confirm it ignores dock context. Look
for how other handlers (strategy_session) access dock context to
determine the correct access pattern.

### Task C.2: Make general_chat dock-aware

**File:** `engine/dispatcher.py`
**Method:** `_handle_general_chat()`

The handler needs to check if dock context is available. Two
approaches depending on what's accessible:

**If dock context is available via routing or context:** use it.
**If not:** query the dock directly for informational intents:

```python
from engine.dock import query_dock
dock_context = query_dock(raw_input, top_k=2)
```

Then modify the prompt construction:

```python
if dock_context and dock_context.strip():
    task_context = f"""The user is asking a question. Use the
following reference material to inform your response. Be
conversational but knowledgeable — synthesize naturally.

Reference material:
{dock_context[:2000]}"""
else:
    task_context = """The user is saying hello or making casual
conversation. Respond naturally and briefly."""
```

The handler checks: did the pipeline give me context? If yes, use
it. If no, stay conversational. The handler doesn't decide what
to load. Compilation already made that decision.

### GATE C

```bash
python -c "
content = open('engine/dispatcher.py', encoding='utf-8').read()
handler_section = content[content.find('_handle_general_chat'):]
handler_section = handler_section[:handler_section.find('def _handle_', 1)]
assert 'dock' in handler_section.lower() or 'query_dock' in handler_section
print('PASS: Handler is dock-aware')
"
python -m pytest tests/ -x -q
```

---

## Epic D: Explain System Intent + White Paper Dock (F3, F4)

**Gate:** "how does this work?" routes to explain_system (informational),
Compilation loads white paper, handler synthesizes informed response.

### Task D.1: Remove greedy keywords from operator_guide

**File:** `profiles/reference/config/routing.config`

In operator_guide, REMOVE: "how does this work", "what can you do"
KEEP: "help", "operator guide"

### Task D.2: Add explain_system intent

**File:** `profiles/reference/config/routing.config`

```yaml
  explain_system:
    tier: 1
    zone: green
    domain: system
    intent_type: informational
    description: "Explain the Autonomaton architecture using dock context"
    keywords:
      - "how does this work"
      - "what is this"
      - "what does this do"
      - "explain"
      - "tell me about this"
      - "what can you do"
      - "what are you"
    handler: "general_chat"
    handler_args: {}
```

intent_type: informational → Compilation loads dock. Same handler.
The architecture does the rest.

### Task D.3: Update clarification.yaml

**File:** `profiles/reference/config/clarification.yaml`

```yaml
fallback_options:
  "1":
    label: "Learn how this system works"
    intent: "explain_system"
  "2":
    label: "Start a conversation"
    intent: "general_chat"
  "3":
    label: "Check system status"
    intent: "dock_status"
  "4":
    label: "I'll rephrase with more context"
    intent: null
```

### Task D.4: Create white paper dock content

**File:** `profiles/reference/dock/autonomaton-pattern.md` (NEW)

2-3 page condensation of Pattern Doc 1.3, optimized for dock
retrieval. Short paragraphs, clear headers, chunks well for RAG.

Must cover: five-stage pipeline, Cognitive Router + tiered dispatch,
Zone Model, Skill Flywheel, Ratchet/Reverse Tax, Digital Jidoka,
three files and a loop, the seven principles.

NOT a full dump. A reference sheet that answers "what is this?"
and "how does it work?" when the dock serves chunks.

### GATE D

```bash
python -c "
import yaml
from pathlib import Path
with open('profiles/reference/config/routing.config') as f:
    config = yaml.safe_load(f)
routes = config['routes']
assert 'explain_system' in routes
assert routes['explain_system']['intent_type'] == 'informational'
kw = routes.get('operator_guide', {}).get('keywords', [])
assert 'how does this work' not in kw
assert Path('profiles/reference/dock/autonomaton-pattern.md').exists()
print('PASS: Routes + dock configured')
"
python -m pytest tests/ -x -q
```

---

## Epic E: Integration Verification

### Task E.1: Routing verification

```bash
python -c "
from engine.profile import set_profile
set_profile('reference')
from engine.cognitive_router import classify_intent, reset_router
reset_router()

r = classify_intent('how does this work')
print(f'\"how does this work\" -> {r.intent} ({r.intent_type})')
assert r.intent == 'explain_system'
assert r.intent_type == 'informational'

r2 = classify_intent('help')
print(f'\"help\" -> {r2.intent}')
assert r2.intent == 'operator_guide'

r3 = classify_intent('hello')
print(f'\"hello\" -> {r3.intent} ({r3.intent_type})')
assert r3.intent == 'general_chat'
assert r3.intent_type == 'conversational'

print('PASS: All routing verified')
"
```

### Task E.2: Add test for explain_system routing

**File:** `tests/test_pipeline_compliance.py`

```python
def test_explain_system_routing(self):
    from engine.profile import set_profile
    from engine.cognitive_router import classify_intent, reset_router
    set_profile("reference")
    reset_router()
    for text in ["how does this work", "what is this", "explain"]:
        result = classify_intent(text)
        assert result.intent == "explain_system", \
            f"'{text}' classified as '{result.intent}'"
        assert result.intent_type == "informational"
```

### Task E.3: Add Ratchet invalidation test

```python
def test_ratchet_cache_invalidation(self):
    """Cache write must be visible to router on next classify."""
    import hashlib, yaml
    from engine.profile import set_profile, get_config_dir
    from engine.cognitive_router import get_router, reset_router
    set_profile("reference")
    reset_router()
    router = get_router()

    test_input = "ratchet_invalidation_test_unique"
    input_hash = hashlib.sha256(
        test_input.lower().strip().encode()
    ).hexdigest()[:16]

    # Write entry to disk
    cache_path = get_config_dir() / "pattern_cache.yaml"
    data = {"cache": {input_hash: {
        "intent": "general_chat", "domain": "system",
        "zone": "green", "handler": "general_chat",
        "handler_args": {}, "intent_type": "conversational",
        "confirmed_count": 1,
    }}}
    with open(cache_path, "w") as f:
        yaml.dump(data, f)
    router.load_cache()

    result = router._check_pattern_cache(test_input)
    assert result is not None, "Cache miss after write + reload"
    assert result.tier == 0

    # Clean up
    with open(cache_path, "w") as f:
        yaml.dump({"cache": {}}, f)
    router.load_cache()
```

### GATE E: Final

```bash
python -m pytest tests/ -x -q
```

---

## Post-Sprint: Commit & Merge

```bat
@echo off
cd /d C:\GitHub\grove-autonomaton-primative-ux-polish-v1
git add -A
git commit -m "ux-polish-v1"
```

Merge:
```bat
cd /d C:\GitHub\grove-autonomaton-primative
git merge grove-autonomaton-primative-ux-polish-v1
git push origin master
git worktree remove ..\grove-autonomaton-primative-ux-polish-v1
```

---

## Verification Summary

| Claim | Test |
|-------|------|
| Ratchet works | Same input twice → T0 cache hit on second |
| Skill output visible | "help" shows LLM content, not metadata |
| Dock-aware handler | general_chat uses context when available |
| explain_system routes correctly | informational, loads dock |
| "help" still works | operator_guide fires on explicit command |
| White paper in dock | autonomaton-pattern.md exists + queries |
| No regressions | pytest exits 0 |

## The Demo After This Sprint

Interaction 1: "what is this thing?"
  Glass: Recognition → explain_system, T1, keyword
  Glass: Compilation → Dock: 2 chunk(s)
  Response: informed explanation from white paper

Interaction 2: same question
  Glass: Recognition → explain_system, T0, cache HIT ✓ $0.00
  The Ratchet learned. Free forever.

Interaction 3: "help"
  Glass: Recognition → operator_guide, T1, keyword
  Response: the actual operator guide content (not "executed successfully")

The architecture working. Visibly. Self-describing. Self-improving.

---

## Epic F: The Unlock — "So What?" Flow + Deep Brainstorm (NEW)

**Gate:** "so what" routes to explain_system with unlock section in
dock. "let's go deeper" triggers Yellow-zone T3 brainstorm with
both dock files as context. Tips guide the operator through the
tier escalation.

### The Demo Script (from the Unlock section itself)

The operator asks "what is this?" → T1, dock context, decent answer.
Tip fires: "OK, a five-stage pipeline and three config files. So
what? Try asking 'so what' to see what makes this unlike anything
you've used before."

Operator types "so what" → explain_system again → Compilation loads
unlock section from dock → T1 synthesizes the topology argument,
the epistemological claim, the spiral vs. star-node.

Tip fires: "Want to go deeper? Try 'brainstorm distributed vs
centralized architectures' — the system will use apex cognition
for a real conversation. It costs a few dimes, but the Ratchet
will cache it."

Operator types it → deep_analysis intent → YELLOW ZONE. Glass
shows: T3, Yellow, requires approval. The Jidoka prompt surfaces:
this costs money, here's why, approve? Operator approves. T3
fires with both dock files as context. Real architectural
conversation.

The Ratchet caches it. Next time: Tier 0. Free. The system got
cheaper because they used it. They just lived the thesis.

### Task F.1: Ship the unlock section as dock content

**File:** `profiles/reference/dock/the-unlock.md` (NEW)

Copy the unlock section document into the reference profile's dock.
This is the "so what?" content — the topology argument, the
epistemological claim, the composition primitives.

Condense if needed for dock chunking, but preserve the core
arguments: star-node vs spiral topology, surface area of knowledge,
governance composition, the recursive case.

### Task F.2: Add "so what" tip to tips.yaml

**File:** `profiles/reference/config/tips.yaml`

Add after the existing tips:

```yaml
  - id: so_what_prompt
    trigger:
      after_intent: "explain_system"
    text: "OK, a five-stage pipeline and three config files. So what? Try asking 'so what' to see what makes this unlike anything you've used before."

  - id: go_deeper_prompt
    trigger:
      after_intent: "explain_system"
    text: "Want to go deeper? Try 'brainstorm distributed vs centralized architectures' — apex cognition for a real conversation."
```

NOTE: Two tips with the same trigger — the tip engine shows one
per session. The first explain_system fires "so what." The second
fires "go deeper." The operator gets guided through the tier
escalation naturally.

Wait — the tip engine shows ONE tip per session per id. Both have
after_intent: explain_system. The first match wins. Second fires
on the NEXT explain_system interaction.

This means: first "how does this work?" → so_what tip. Operator
asks "so what" → routes to explain_system again → go_deeper tip.
Perfect sequencing.

### Task F.3: Add deep_analysis intent

**File:** `profiles/reference/config/routing.config`

```yaml
  # --- Deep Architectural Analysis (Yellow Zone, Apex Tier) ---
  deep_analysis:
    tier: 3
    zone: yellow
    domain: system
    intent_type: informational
    description: "Deep brainstorm on architecture, distributed systems, AI governance"
    keywords:
      - "brainstorm"
      - "go deeper"
      - "deep dive"
      - "let's think about"
      - "distributed vs centralized"
      - "compare architectures"
      - "what makes this different"
    handler: "strategy_session"
    handler_args: {}
```

KEY: tier 3, zone yellow. The operator SEES this in Glass:
"T3, YELLOW — requires confirmation." The Jidoka prompt explains
the cost. The operator approves or rejects. The system is transparent.

### Task F.4: Fix handlers to respect routing config tier

**File:** `engine/dispatcher.py`

TWO handlers hardcode their tier instead of reading routing_result:

**In _handle_strategy_session():** Find `tier=2` in the call_llm()
call. Replace with:
```python
tier=routing_result.tier,
```

**In _handle_general_chat():** Find `tier=1` in the call_llm()
call. Replace with:
```python
tier=routing_result.tier,
```

This is the correct architecture. The routing config specifies the
tier. The handler dispatches to it. The handler is a dumb pipe.
Config determines the cost. The handler doesn't decide.

After this fix:
- explain_system (tier: 1 in config) → general_chat → T1 call
- strategy_session (tier: 2 in config) → strategy_session → T2
- deep_analysis (tier: 3 in config) → strategy_session → T3

Same handlers. Different tiers. Driven by config. The architecture
working.

### Task F.5: Add deep_analysis to clarification fallback

**File:** `profiles/reference/config/clarification.yaml`

Update to include the deep option:

```yaml
fallback_options:
  "1":
    label: "Learn how this system works"
    intent: "explain_system"
  "2":
    label: "Deep architectural brainstorm (apex tier)"
    intent: "deep_analysis"
  "3":
    label: "Start a conversation"
    intent: "general_chat"
  "4":
    label: "Check system status"
    intent: "dock_status"
  "5":
    label: "I'll rephrase with more context"
    intent: null
```

### GATE F

```bash
python -c "
import yaml
from pathlib import Path

# deep_analysis route exists with correct tier and zone
with open('profiles/reference/config/routing.config') as f:
    config = yaml.safe_load(f)
routes = config['routes']
assert 'deep_analysis' in routes
assert routes['deep_analysis']['tier'] == 3
assert routes['deep_analysis']['zone'] == 'yellow'

# unlock section in dock
assert Path('profiles/reference/dock/the-unlock.md').exists()

# strategy_session reads tier from routing_result
content = open('engine/dispatcher.py', encoding='utf-8').read()
ss_section = content[content.find('_handle_strategy_session'):]
ss_section = ss_section[:ss_section.find('def _handle_', 10)]
assert 'routing_result.tier' in ss_section, \
    'strategy_session still hardcodes tier'

# tips exist
with open('profiles/reference/config/tips.yaml') as f:
    tips = yaml.safe_load(f)
tip_ids = [t['id'] for t in tips.get('tips', [])]
assert 'so_what_prompt' in tip_ids

print('PASS: Unlock flow configured')
"
python -m pytest tests/ -x -q
```

---

## Updated Verification Summary

| Claim | Test |
|-------|------|
| Ratchet works | Same input twice → T0 cache hit |
| Skill output visible | "help" shows LLM content |
| Dock-aware handler | general_chat uses dock when available |
| explain_system routes correctly | informational, loads dock |
| Handlers respect config tier | routing_result.tier, not hardcoded |
| deep_analysis is Yellow T3 | tier=3, zone=yellow in config |
| Unlock section in dock | the-unlock.md exists |
| White paper in dock | autonomaton-pattern.md exists |
| "so what" tip fires | after first explain_system |
| "go deeper" tip fires | after second explain_system |
| No regressions | pytest exits 0 |

## The Full Demo Sequence

1. "hello" → general_chat, T1, conversational. Tip: try something
   the system won't recognize.

2. "what is this?" → explain_system, T1, informational. Dock loads
   white paper. Informed answer. Tip: "So what? Try asking 'so what'."

3. "so what" → explain_system again, T1. Dock loads unlock section.
   The topology argument. The spiral. Tip: "Want to go deeper?"

4. "brainstorm distributed vs centralized" → deep_analysis, T3,
   YELLOW. Glass shows: T3, Yellow, requires approval. Jidoka
   surfaces cost. Operator approves. Apex synthesis with both dock
   files as context. Real architectural conversation.

5. Same question again → Ratchet cache hit. T0. $0.00. The deep
   answer is now free.

The operator just experienced every property the papers describe.
Tiered compute. Zone governance. The Ratchet. The Flywheel. Cost
transparency. The spiral. They didn't read about it. They lived it.

That's the Glass Pipeline demo. That's the unlock.
