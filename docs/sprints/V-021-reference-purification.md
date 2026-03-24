# V-021: Reference Purification — Remove All Coach Domain Code

> *"The correct direction for line count is DOWN."*
> *IMPORTANT: Read docs/V-021-COMPLIANCE-REVIEW.md BEFORE executing. It corrects gaps in this spec.*

## The Decision

The reference implementation exists for one purpose: demonstrate the Autonomaton
Pattern to CTOs and technical reviewers. Everything that doesn't serve that purpose
is noise.

`coach_demo` was the development prototype that proved the pattern works for a domain.
It served its purpose. The domain code it left behind — in the engine, in the tests,
in the repo root — now obscures the architecture it was supposed to demonstrate.

This sprint removes all coach_demo domain code from the repo and leaves one clean
reference implementation of the Autonomaton Pattern.

## Why This Is Architecturally Correct

**White Paper Part III S1 (Declarative Behavior Governance):**
> "The same cognitive engine serves legal discovery, academic synthesis, personal
productivity, or enterprise knowledge management by swapping configuration, not
rewriting application logic."

The engine must be domain-free. If domain code lives in the engine, the claim is false.

**TCP/IP Paper SIII (Simplicity Principle):**
> "Complexity is the primary mechanism that impedes efficient scaling."

1,930+ lines of domain code (cortex.py + content_engine.py + compiler.py) in the
engine is complexity in the thin waist.

**Pattern Release Part VIII (Build It This Weekend):**
> "Three files and a loop."

## What Gets Removed

### Engine Files (delete)
| File | Lines | Reason |
|---|---|---|
| `engine/cortex.py` | 1,393 | 100% coach_demo domain logic |
| `engine/content_engine.py` | 537 | 100% coach_demo domain logic |
| `engine/compiler.py` | 654 | 100% coach_demo domain logic (see COMPLIANCE-REVIEW.md GAP 1) |

### Profile (delete entire directory)
| Path | Reason |
|---|---|
| `profiles/coach_demo/` | Domain prototype, no longer needed |

### Tests (delete)
| File | Reason |
|---|---|
| `tests/test_cortex.py` | Tests coach_demo cortex |
| `tests/test_cortex_evolution.py` | Tests coach_demo analytical lenses |
| `tests/test_privacy_mask.py` | Tests content_engine privacy masking |

### Repo Hygiene (delete)
- `tmpclaude-*` (~230 files)
- `nul`
- `.coach/` directory
- All `__pycache__` directories

### Docs (delete obsolete sprint docs)
Keep only docs relevant to reference profile architecture.

## What Gets Modified

### `autonomaton.py`
Remove: cortex imports, `run_tail_pass()` call, `process_pending_kaizen()`,
cortex_info from banner, cortex display handler, session_zero display handler,
compiler imports and calls.

### `engine/dispatcher.py`
Remove: cortex import in `_display_queue()`. Update engine manifest file list.

### `engine/config_loader.py`
Remove: `load_entity_config()`, `load_content_config()` (dead after cortex/content_engine deletion).

### `engine/profile.py`
Remove: `get_entities_dir()`, `get_queue_dir()`, `get_pending_queue_path()` (dead after cortex deletion).

### `tests/test_purity_invariants.py`
Remove: cortex-specific test that imports deleted module.

### `.gitignore`
Add: `tmpclaude-*`, `nul`, `__pycache__/`, `.coach/`

## What Does NOT Get Removed

| File | Why it stays |
|---|---|
| `engine/pipeline.py` | The invariant pipeline |
| `engine/cognitive_router.py` | Stage 2 classification |
| `engine/dispatcher.py` | Stage 5 dispatch (after cleanup) |
| `engine/glass.py` | Glass Pipeline rendering |
| `engine/ux.py` | Jidoka/Andon/Kaizen UX |
| `engine/telemetry.py` | Feed-first telemetry |
| `engine/llm_client.py` | LLM adapter |
| `engine/dock.py` | Local RAG |
| `engine/flywheel.py` | Flywheel detection |
| `engine/pit_crew.py` | Skill generation (Red zone) |
| `engine/effectors.py` | MCP execution layer |
| `engine/config_loader.py` | Config utilities (after dead function removal) |
| `engine/profile.py` | Profile management (after dead function removal) |
| `profiles/reference/` | The reference demo profile |
| `profiles/blank_template/` | Engine isolation proof |

## Acceptance Tests

1. `python autonomaton.py --profile reference` — starts cleanly, no `[CORTEX]` output
2. Full SMOKE-TEST.md passes (all 7 tests)
3. `python autonomaton.py --profile blank_template` — starts cleanly
4. `grep -r "cortex" engine/ --include="*.py"` → zero results
5. `grep -r "content_engine" engine/ --include="*.py"` → zero results
6. `grep -r "coach" engine/ --include="*.py"` → zero results
7. `grep -r "compiler" engine/ --include="*.py"` → zero results
8. `ls profiles/` → `blank_template/` and `reference/` only
9. `ls tmpclaude*` → no results
10. `pytest` → all remaining tests pass

## Commit Message
`V-021-reference-purification`

---

*Decision: Jim Calhoun*
*Spec: Claude (Opus 4.6)*
*Compliance Review: docs/V-021-COMPLIANCE-REVIEW.md*
