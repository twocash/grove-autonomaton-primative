# EXECUTION PROMPT: Purity Audit v2

> **Self-contained handoff for Claude Code.**
> Sprint: `purity-audit-v2`
> Generated: 2026-03-18
> Repo: `C:\GitHub\grove-autonomaton-primative`
> Dependency: `purity-audit-v1` MUST be merged first

---

## Context

You are executing the second purity audit sprint on the Autonomaton.
Sprint v1 fixed the HIGH violations (pipeline bypasses, the Ratchet,
Cortex governance). This sprint fixes six MEDIUM violations that affect
the system's ability to demonstrate the claims in its published papers.

**Read these files FIRST before writing any code:**
1. `CLAUDE.md` — The architectural invariants
2. `docs/sprints/purity-audit-v2/SPEC.md` — Why this sprint exists
3. `docs/sprints/purity-audit-v2/CONTRACT.md` — Atomic task list with gates

The CONTRACT.md is your step-by-step plan. Follow it task by task.


## Critical Rules

1. **Backward compatibility is mandatory.** The new telemetry fields are
   OPTIONAL with None defaults. Every existing `log_event()` call site
   must continue to work without changes. New flat fields only appear
   when explicitly passed.

2. **Config over code.** Model IDs go in `models.yaml`. The `llm_client.py`
   reads from config with hardcoded fallback defaults if the file is missing.
   The system must never crash because a config file doesn't exist.

3. **Only flatten the five fields.** Promote `intent`, `tier`, `confidence`,
   `cost_usd`, and `human_feedback` to first-class. Everything else stays
   in `inferred`. Don't over-flatten.

4. **Red zone must feel different.** Use `confirm_red_zone_with_context()`
   which calls the persona to explain the action. Yellow zone stays
   `confirm_yellow_zone()`. The operator must experience the difference.

5. **Run tests after every epic.** `python -m pytest tests/ -x -q`


## Pre-Execution Checklist

```bash
cd C:\GitHub\grove-autonomaton-primative

# 1. Verify purity-audit-v1 is merged
git log --oneline -5
# Should see v1 commits: "feat: route startup sequences through pipeline",
# "feat: add pattern cache for ratchet tier demotion", etc.

# 2. Create worktree for this sprint
# git worktree add ../grove-autonomaton-primative-purity-v2 purity-audit-v2

# 3. Run existing tests — must pass before you start
python -m pytest tests/ -x -q

# 4. Verify key files exist (post v1)
test -f profiles/coach_demo/config/pattern_cache.yaml && echo "pattern_cache: OK (from v1)"
test -f tests/test_purity_invariants.py && echo "purity_v1_tests: OK"
```


## Execution Sequence

### Epic A: Flat Telemetry Schema

**The biggest epic. Touches the most files.**

1. **A.1:** Add 5 optional fields to `TelemetryEvent` in `engine/telemetry.py`:
   `intent`, `tier`, `confidence`, `cost_usd`, `human_feedback`. All Optional
   with None defaults. See CONTRACT Task A.1.

2. **A.2:** Update `to_dict()` to include non-None fields. See CONTRACT Task A.2.

3. **A.3:** Update `create_event()` and `log_event()` signatures to accept the
   new params. Pass through to TelemetryEvent. See CONTRACT Task A.3.

4. **A.4:** Add `_log_pipeline_completion()` to the pipeline. Call it and the
   pattern cache write at end of `_run_execution()`. Update
   `_log_pipeline_failure()` to use flat fields. See CONTRACT Task A.4.

5. **A.5:** Update cognitive router telemetry (LLM classification, cache hits)
   to use flat fields. See CONTRACT Task A.5.

6. **A.6:** Sweep remaining call sites in dispatcher, cortex, compiler.
   Only promote the 5 designated fields. See CONTRACT Task A.6.

7. **A.7:** Add 3 new tests to `test_telemetry_schema.py`. See CONTRACT Task A.7.

**Gate A:**
```bash
python -c "from engine.telemetry import create_event; e=create_event(source='t',raw_transcript='hi',zone_context='green',intent='test',tier=2,confidence=0.9); assert e['intent']=='test'; print('PASS')"
python -c "from engine.telemetry import create_event; e=create_event(source='t',raw_transcript='hi',zone_context='green'); assert 'intent' not in e; print('PASS')"
python -m pytest tests/test_telemetry_schema.py -x -q
python -m pytest tests/ -x -q
```


### Epic B: Externalize Model Config

1. **B.1:** Create `profiles/coach_demo/config/models.yaml` and
   `profiles/blank_template/config/models.yaml` with current model
   strings and pricing. See CONTRACT Task B.1 for exact YAML.

2. **B.2:** In `engine/llm_client.py`:
   - Rename `TIER_MODELS` → `_DEFAULT_TIER_MODELS` (fallback)
   - Rename `MODEL_PRICING` → `_DEFAULT_MODEL_PRICING` (fallback)
   - Add `_load_models_config()` that reads from `models.yaml`
   - Add `reset_models_config()` for profile switching
   - Update `call_llm()` to use `_load_models_config()`
   - Update `_calculate_cost()` to use `_load_models_config()`
   See CONTRACT Task B.2.

**Gate B:**
```bash
python -c "from pathlib import Path; assert Path('profiles/coach_demo/config/models.yaml').exists(); print('PASS')"
python -c "from engine.llm_client import _load_models_config; t,p,m=_load_models_config(); assert 1 in t; print('PASS')"
python -c "import inspect; from engine.llm_client import call_llm; src=inspect.getsource(call_llm); assert 'claude-3-haiku' not in src; print('PASS')"
python -m pytest tests/ -x -q
```


### Epic C: Zone UX + Defensive Hardening

1. **C.1:** In `engine/pipeline.py` `_run_approval()`, change the red zone
   block to call `confirm_red_zone_with_context()` with a payload dict.
   See CONTRACT Task C.1.

2. **C.2:** Wrap `run_pipeline_with_mcp()` in try/except matching the
   standard pipeline's exception handling. Or delegate to `pipeline.run()`.
   See CONTRACT Task C.2.

3. **C.3:** In `engine/config_loader.py` `build_system_prompt()`, replace
   the silent `except Exception: pass` on standing context with a version
   that logs to telemetry. See CONTRACT Task C.3.

4. **C.4:** Add "Handler Interface Contract" section to `CLAUDE.md`.
   See CONTRACT Task C.4 for exact markdown.

**Gate C:**
```bash
python -c "import inspect; from engine.pipeline import InvariantPipeline; assert 'confirm_red_zone_with_context' in inspect.getsource(InvariantPipeline._run_approval); print('PASS')"
python -c "import inspect; from engine.pipeline import run_pipeline_with_mcp; src=inspect.getsource(run_pipeline_with_mcp); assert 'except' in src or '.run(' in src; print('PASS')"
python -c "import inspect; from engine.config_loader import PersonaConfig; assert 'log_event' in inspect.getsource(PersonaConfig.build_system_prompt); print('PASS')"
python -c "assert 'Handler Interface Contract' in open('CLAUDE.md').read(); print('PASS')"
python -m pytest tests/ -x -q
```


### Epic D: Test Suite

1. **D.1:** Create `tests/test_purity_v2.py` with four test classes from
   CONTRACT Task D.1:
   - `TestFlatTelemetry` (3 tests) — flat fields present when set, omitted when None, backward compat
   - `TestModelConfig` (4 tests) — YAML exists, 3 tiers, config loader works, no hardcoded strings
   - `TestRedZoneUX` (2 tests) — red zone uses context approval, not yellow zone function
   - `TestDefensiveHardening` (3 tests) — MCP exception handling, standing context telemetry, handler contract documented

**Gate D:**
```bash
python -m pytest tests/ -x -v
# Expected: ALL tests pass, zero failures
```


---

## Final Sprint Gate

Run this complete verification sequence. Every line must print PASS.

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
python -c "
import inspect; from engine.config_loader import PersonaConfig
assert 'log_event' in inspect.getsource(PersonaConfig.build_system_prompt); print('PASS')
"
python -c "assert 'Handler Interface Contract' in open('CLAUDE.md').read(); print('PASS')"

echo "=== GATE D: Full Test Suite ==="
python -m pytest tests/ -x -q

echo "=== ALL GATES PASSED ==="
```


---

## Troubleshooting

**Existing tests fail after telemetry schema change:**
The new fields are all Optional with None defaults. Existing `create_event()`
and `log_event()` calls that don't pass the new params should work identically.
If a test fails, check whether it's asserting on the exact dict keys of a
telemetry event — the new fields won't be present unless explicitly passed,
but the test may need updating if it does strict key-count assertions.

**models.yaml not found at runtime:**
The `_load_models_config()` function falls back to `_DEFAULT_TIER_MODELS` if
the file is missing. The system never crashes on a missing config file. If
tests fail because the file isn't found, check that the test is running from
the repo root where `profiles/` is accessible.

**confirm_red_zone_with_context import fails:**
This function already exists in `engine/ux.py`. If the import fails, check
the function name spelling. It's `confirm_red_zone_with_context` (with
underscores), taking `action_description: str` and `payload: dict`.

**LLM telemetry dual-stream question:**
`llm_client.py` has its own telemetry stream (`llm_calls.jsonl`) via
`log_llm_event()`. This is SEPARATE from the pipeline telemetry stream
(`events.jsonl`) via `log_event()`. Both should exist. The LLM stream
tracks token-level cost data. The pipeline stream tracks routing decisions.
Epic A adds flat fields to the pipeline stream. The LLM stream is unchanged
in this sprint (it already has model, tokens, cost as first-class fields).

**Cache from v1 conflicts:**
If the pattern cache from v1 causes issues, clear it:
`python -c "import yaml; yaml.dump({'cache':{}}, open('profiles/coach_demo/config/pattern_cache.yaml','w'))"`


---

## Commit Strategy

One commit per epic gate. Use `.bat` files for commits on Windows.

```
Epic A complete → commit: "feat: flatten telemetry schema with first-class routing fields"
Epic B complete → commit: "feat: externalize model config to models.yaml"
Epic C complete → commit: "fix: red zone UX differentiation and defensive hardening"
Epic D complete → commit: "test: add purity audit v2 test suite"
```

---

*This execution prompt is self-contained. All context needed to execute
the sprint is in this file, CONTRACT.md, SPEC.md, and CLAUDE.md.*
