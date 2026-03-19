# EXECUTION PROMPT: Purity Audit v1

> **Self-contained handoff for Claude Code.**
> Sprint: `purity-audit-v1`
> Generated: 2026-03-18
> Repo: `C:\GitHub\grove-autonomaton-primative`

---

## Context

You are executing an architectural purity sprint on the Autonomaton — a
domain-agnostic, declarative agentic system written in Python. The system
has a five-stage invariant pipeline (Telemetry → Recognition → Compilation →
Approval → Execution) that ALL interactions must traverse. The sprint fixes
four structural violations discovered in a purity audit.

**Read these files FIRST before writing any code:**
1. `CLAUDE.md` — The 11 architectural invariants (your guardrails)
2. `docs/sprints/purity-audit-v1/SPEC.md` — Why this sprint exists
3. `docs/sprints/purity-audit-v1/CONTRACT.md` — Atomic task list with gates

**The CONTRACT.md is your step-by-step execution plan.** Follow it task by
task. Do not skip ahead. Each epic has a gate — run the gate checks before
proceeding to the next epic.


## Critical Rules (Anti-Code-Party Protocol)

1. **NEVER bypass the pipeline.** Every LLM call in this system must traverse
   all 5 stages. If you're tempted to call `call_llm()` directly from
   `autonomaton.py` or any file outside the engine, STOP. Route it through
   `run_pipeline()` instead.

2. **Config over code.** New intents go in `routing.config` (YAML). New zone
   classifications go in `zones.schema`. The engine is dumb pipes that route
   based on config. If you're writing `if intent == "foo":` in engine code,
   you're violating the architecture.

3. **The pattern cache is a YAML file, not a Python dict.** The operator must
   be able to open `pattern_cache.yaml` in a text editor, read every cached
   classification, and delete entries. Declarative sovereignty.

4. **Red zone actions are NEVER cached.** The Ratchet must not auto-approve
   high-consequence actions. Check for `zone == "red"` before writing to cache.

5. **The Cortex never prompts.** After this sprint, `engine/cortex.py` must
   contain zero calls to `input()` or `print()`. All proposals go to the
   Kaizen queue. They get processed through the pipeline.

6. **Run tests after every epic.** `python -m pytest tests/ -x -q` must pass
   before you proceed to the next epic.


## Pre-Execution Checklist

```bash
cd C:\GitHub\grove-autonomaton-primative

# 1. Verify you're on a worktree (NEVER work directly on master)
git branch --show-current
# If on master, create a worktree:
# git worktree add ../grove-autonomaton-primative-purity-audit purity-audit-v1

# 2. Run existing tests — must pass before you start
python -m pytest tests/ -x -q

# 3. Verify key files exist
test -f CLAUDE.md && echo "CLAUDE.md: OK"
test -f engine/pipeline.py && echo "pipeline.py: OK"
test -f engine/cognitive_router.py && echo "cognitive_router.py: OK"
test -f engine/cortex.py && echo "cortex.py: OK"
test -f engine/dispatcher.py && echo "dispatcher.py: OK"
test -f autonomaton.py && echo "autonomaton.py: OK"
test -f profiles/coach_demo/config/routing.config && echo "routing.config: OK"
```


## Execution Sequence

Execute epics in this order. Each has a gate. Do not proceed until the gate passes.

### Epic A: Route Startup Sequences Through the Pipeline

**Tasks (in order):**

1. **A.1:** Add `welcome_card`, `startup_brief`, `generate_plan`, and
   `clear_cache` intents to `profiles/coach_demo/config/routing.config`
   AND `profiles/blank_template/config/routing.config`.
   See CONTRACT.md Task A.1 for exact YAML.

2. **A.2:** Add `_handle_welcome_card()`, `_handle_startup_brief()`, and
   `_handle_generate_plan()` to `engine/dispatcher.py`. Register them in
   `_register_handlers()`. See CONTRACT.md Task A.2 for signatures.

   **⚠️ FLAG: `_handle_generate_plan()` Implementation Detail**
   This handler must call `generate_structured_plan()` from `engine/compiler.py`
   AND handle the file write (`write_structured_plan()`) within the handler itself.
   The pipeline Stage 4 handles Yellow zone approval. If approved, Stage 5
   dispatches to this handler, which does the write. Do NOT put file-write
   logic in `autonomaton.py` — the REPL is a display surface only.

3. **A.3:** In `autonomaton.py`, replace `generate_welcome_briefing()`,
   `generate_startup_brief()`, and the first-boot plan block with
   `run_pipeline()` calls using `source="system_startup"`.
   Delete the now-unused functions. See CONTRACT.md Task A.3 for exact code.

**Gate A:**
```bash
python -c "c=open('autonomaton.py').read(); assert 'call_llm(' not in c; print('PASS: No direct LLM calls')"
python -c "import yaml; d=yaml.safe_load(open('profiles/coach_demo/config/routing.config')); assert all(k in d['routes'] for k in ['welcome_card','startup_brief','generate_plan']); print('PASS: Intents declared')"
python -c "from engine.dispatcher import Dispatcher; d=Dispatcher(); assert all(k in d._handlers for k in ['welcome_card','startup_brief','generate_plan']); print('PASS: Handlers registered')"
python -m pytest tests/ -x -q
```


### Epic B: The Pattern Cache (The Ratchet)

**Tasks (in order):**

1. **B.1:** Create `profiles/coach_demo/config/pattern_cache.yaml` and
   `profiles/blank_template/config/pattern_cache.yaml` with empty cache
   and schema header. See CONTRACT.md Task B.1.

2. **B.2:** In `engine/cognitive_router.py`:
   - Add `pattern_cache` and `_cache_loaded` to `__init__()`
   - Add `load_cache()` method
   - Add `_check_pattern_cache()` method that returns RoutingResult at
     Tier 0 on cache hit, None on miss
   - Modify `classify()` to check cache BETWEEN keyword match and LLM
     escalation. The flow is: keywords → cache → LLM.
   See CONTRACT.md Tasks B.2-B.4 for exact code.

3. **B.3:** In `engine/pipeline.py`:
   - Add `_write_to_pattern_cache()` method to `InvariantPipeline`
   - Call it at the end of `_run_execution()` when `self.context.executed`
     is True
   - The method checks: tier >= 2, approved, executed, zone != "red",
     not already from cache. Only then writes to YAML.
   See CONTRACT.md Task B.3.

4. **B.4:** Add `clear_cache` intent to routing.config and handler to
   dispatcher. See CONTRACT.md Task B.4.

5. **B.5:** Add telemetry logging for cache hits in the router.
   See CONTRACT.md Task B.5.

**Gate B:**
```bash
python -c "from pathlib import Path; assert Path('profiles/coach_demo/config/pattern_cache.yaml').exists(); print('PASS: Cache file')"
python -c "from engine.cognitive_router import CognitiveRouter; r=CognitiveRouter(); assert hasattr(r,'_check_pattern_cache'); print('PASS: Cache check')"
python -c "from engine.pipeline import InvariantPipeline; p=InvariantPipeline(); assert hasattr(p,'_write_to_pattern_cache'); print('PASS: Cache write')"
python -c "from engine.dispatcher import Dispatcher; d=Dispatcher(); assert 'clear_cache' in d._handlers; print('PASS: Clear cache handler')"
python -m pytest tests/ -x -q
```


### Epic C: Cortex Governance Compliance

**Tasks (in order):**

1. **C.1:** In `engine/cortex.py`, replace `ask_entity_validation()` with
   `create_entity_validation_proposal()` that returns a dict instead of
   prompting. See CONTRACT.md Task C.1.

2. **C.2:** Find every call site of `ask_entity_validation()` in cortex.py
   and replace with queue writes using the new proposal function.
   Remove ALL `input()` and `print()` calls from cortex.py.
   See CONTRACT.md Task C.2.

3. **C.3:** In `autonomaton.py` → `process_pending_queue()`, add handling
   for `proposal_type == "entity_validation"` items that routes through
   `ask_jidoka()`. See CONTRACT.md Task C.3.

**Gate C:**
```bash
python -c "content=open('engine/cortex.py').read(); assert 'input(' not in content; print('PASS: No input() in cortex')"
python -c "from engine.cortex import create_entity_validation_proposal; p=create_entity_validation_proposal('Test','player','ctx'); assert p['proposal_type']=='entity_validation'; print('PASS: Proposal function')"
python -m pytest tests/ -x -q
```


### Epic D: Purity Invariant Test Suite

**Task:**

1. **D.1:** Create `tests/test_purity_invariants.py` with the three test
   classes from CONTRACT.md Task D.1:
   - `TestNoPipelineBypasses` (4 tests)
   - `TestPatternCache` (6 tests)
   - `TestCortexGovernance` (2 tests)

   All tests use mocking to avoid real LLM calls. Tests verify structural
   properties (method existence, file presence, schema compliance), not
   LLM output quality.

**Gate D:**
```bash
python -m pytest tests/ -x -v
# Expected: ALL tests pass, zero failures
```


---

## Final Sprint Gate

Run this complete verification sequence. Every line must print PASS.

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


## Troubleshooting

**Import errors after moving functions:**
When moving `generate_welcome_briefing()` and `generate_startup_brief()` from
`autonomaton.py` to dispatcher handlers, you may hit circular imports. The
dispatcher already imports from `engine.llm_client`, `engine.config_loader`,
`engine.profile`, etc. Use the same import pattern the existing handlers use
(imports at module top or inside the method if circular).

**Tests fail on profile path:**
Tests run from repo root. Profile paths resolve via `engine.profile` module.
If a test can't find `profiles/coach_demo/config/...`, make sure the test
is running from the repo root directory, or mock `get_config_dir()`.

**Pattern cache YAML serialization:**
`yaml.dump()` with `default_flow_style=False` produces human-readable YAML.
`handler_args` dicts with nested values may need explicit `sort_keys=False`
to maintain readability. Test by opening the file after a cache write.

**Cortex print() removal — false positives:**
Some `print()` calls may be inside comment strings or docstrings. The
verification script filters comments but check manually if the assertion
fails. The rule is: no `print()` in executable code paths within cortex.py.

**Gate check imports fail:**
If `from engine.cortex import create_entity_validation_proposal` fails,
the function hasn't been created yet or has a syntax error. Check the
function signature matches exactly what CONTRACT.md specifies.


## Commit Strategy

One commit per epic gate. Use `.bat` files for commits (inline git commit
messages with spaces fail on Windows CMD).

```
Epic A complete → commit: "feat: route startup sequences through pipeline"
Epic B complete → commit: "feat: add pattern cache for ratchet tier demotion"  
Epic C complete → commit: "refactor: remove direct IO from cortex layer"
Epic D complete → commit: "test: add purity invariant test suite"
```

---

## Post-Sprint

After all gates pass, delete the `tmpclaude-*` files from the repo root:
```bash
del tmpclaude-*
```

There are 49 of them. Clean repo for the next sprint.

---

*This execution prompt is self-contained. All context needed to execute
the sprint is in this file, CONTRACT.md, SPEC.md, and CLAUDE.md.*
