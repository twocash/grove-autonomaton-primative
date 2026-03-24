# V-021 Spec Compliance Review

> *Validated against: Pattern Release Draft 1.3, TCP/IP Paper, SMOKE-TEST.md, VIOLATIONS.md*
> *Reviewed: 2026-03-23 by Claude (Opus 4.6) in architecture review session*

## Verdict: SPEC IS 80% CORRECT — Four Gaps Will Break the Build

The V-021 delete list is correct. The "what stays" list has gaps that will cause
runtime failures or leave coach domain code in the engine.

---

## GAP 1: compiler.py Is NOT Engine-Core (CRITICAL — WILL LEAVE DEAD CODE)

The V-021 spec says "keep compiler.py — Stage 3 context assembly."

**Reality:** pipeline.py does NOT import compiler.py. Zero references. Stage 3
(Compilation) in the pipeline queries the dock directly via `_run_compilation()`.

compiler.py is 654 lines of coach_demo domain code:
- **Privacy Mask** (~lines 1-150): Entity alias loading, name masking for minors.
- **Standing Context** (~lines 153-317): `gather_state_snapshot()` reads entities,
  content pipeline, skills. Called from autonomaton.py lines ~199, ~556 — both in
  code paths being deleted (cortex tail-pass and kaizen queue processing).
- **Entity Gap Detection** (~lines 320-397): `detect_entity_gaps()`.
- **Structured Plan Generation** (~lines 432+): `generate_structured_plan()`,
  `write_structured_plan()`.

After V-021 removes its consumers, nothing imports compiler.py. 654 lines of dead code.

**Action:** Add `engine/compiler.py` to the delete list.

---

## GAP 2: config_loader.py Has Dead Domain Functions (MEDIUM)

After cortex.py and content_engine.py are deleted, these functions become dead code:

- `load_entity_config()` (~line 213): Only consumer was cortex.py.
- `load_content_config()` (~line 238): Only consumer was content_engine.py.
  Contains TikTok/Instagram platform template defaults.

**Action:** Delete `load_entity_config()` and `load_content_config()` from
config_loader.py. Keep `get_persona()`, `load_persona()`, `load_profile_config()`,
and `reset_persona_cache()`.

---

## GAP 3: profile.py Has Dead Helper Functions (LOW)

After cortex.py deletion, these functions become dead code:
- `get_entities_dir()` (~line 88)
- `get_queue_dir()` (~line 103)
- `get_pending_queue_path()` (~line 118)

**Action:** Delete these three functions from profile.py.

---

## GAP 4: test_purity_invariants.py References cortex (WILL CRASH PYTEST)

`tests/test_purity_invariants.py` line ~107 imports
`from engine.cortex import create_entity_validation_proposal`. This file is NOT
on the delete list but WILL crash at import time after cortex.py is deleted.

**Action:** Remove the cortex-specific test from test_purity_invariants.py.
If the file contains architectural invariant tests independent of cortex, keep
the file and remove only the cortex test. If mostly coach-specific, delete it.

---

## GAP 5 (MINOR): dispatcher.py Engine Manifest List

dispatcher.py line ~740 includes "cortex.py" and "compiler.py" in the static
engine source file list used by `show_engine_manifest`. After deletion, this
list references files that don't exist.

**Action:** Update the manifest list to remove deleted files.

---

## CORRECTED EXECUTION CHECKLIST

1. Delete `engine/cortex.py`
2. Delete `engine/content_engine.py`
3. Delete `engine/compiler.py` ← ADDED
4. Delete `profiles/coach_demo/` directory
5. Delete `tests/test_cortex.py`, `tests/test_cortex_evolution.py`, `tests/test_privacy_mask.py`
6. Fix `tests/test_purity_invariants.py` — remove cortex import and test ← ADDED
7. Edit `autonomaton.py` — remove cortex AND compiler imports and calls
8. Edit `engine/dispatcher.py` — remove cortex import, update engine manifest list
9. Edit `engine/config_loader.py` — remove `load_entity_config()` and `load_content_config()` ← ADDED
10. Edit `engine/profile.py` — remove `get_entities_dir()`, `get_queue_dir()`, `get_pending_queue_path()` ← ADDED
11. Delete tmpclaude-*, nul, .coach/, all __pycache__
12. Update .gitignore
13. Delete obsolete sprint docs
14. Run pytest — fix any remaining import errors
15. Run SMOKE-TEST.md — verify reference profile works clean
16. Commit: `V-021-reference-purification`

## ACCEPTANCE TESTS (updated)

1. `python autonomaton.py --profile reference` — starts cleanly, no `[CORTEX]` output
2. Full SMOKE-TEST.md passes (all 7 tests)
3. `python autonomaton.py --profile blank_template` — starts cleanly
4. `grep -r "cortex" engine/ --include="*.py"` → zero results
5. `grep -r "content_engine" engine/ --include="*.py"` → zero results
6. `grep -r "coach" engine/ --include="*.py"` → zero results
7. `grep -r "compiler" engine/ --include="*.py"` → zero results ← ADDED
8. `ls profiles/` → `blank_template/` and `reference/` only
9. `ls tmpclaude*` → no results
10. `pytest` → all remaining tests pass
