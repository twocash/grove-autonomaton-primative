# HANDOFF PROMPT: Sprint 6 — Autonomic Memory & Ratchet Classification

## Who You Are Working With
Jim Calhoun, founder of The Grove Foundation. He built the Autonomaton — a domain-agnostic, declarative agentic system with a five-stage invariant pipeline (Telemetry → Recognition → Compilation → Approval → Execution). The `coach_demo` profile is a working reference implementation for a Catholic high school golf coach.

## The Repo
`C:\GitHub\grove-autonomaton-primative` — Python, main branch, no worktrees active.

**Do NOT modify files until you have audited the repo and discussed the plan with Jim.**

## What Has Been Done (Sprints 1-5 complete)

### Sprint 1-3: Foundation
- Coach_demo profile warmed with real content (6 players, 2 families, venue, skills)
- Welcome card with LLM-generated briefing
- Classification bumped to Tier 2 (Sonnet), JSON extraction fixed

### Sprint 4: Standing Context (Nervous System)
- `engine/compiler.py:gather_state_snapshot()` — reads dock, entities, content pipeline, skills, telemetry
- `engine/compiler.py:get_standing_context()` — cached snapshot, rides with every non-conversational LLM call
- `engine/config_loader.py:build_system_prompt(include_state=True)` — persona carries ambient awareness
- Silent failure purge — every `except` block logs to telemetry before returning defaults
- Diagnostic Jidoka — two-tier clarification (LLM best-guess first, smart options second)
- Strategy session handler rewritten to use full standing context + Sonnet synthesis

### Sprint 5: The Living Plan (Memory + Foresight)
- `dock/system/structured-plan.md` — auto-generated, operator-approved trajectory document
- `engine/compiler.py:generate_structured_plan()` — Tier 2 Sonnet synthesis of goals + context
- Context Gardener (Cortex Lens 6) — proposes 3 Kaizen types: gap_alert, plan_update, stale_alert
- `config/cortex.yaml` — gating config (min 10 events, max 1x/session)
- Gap detection at startup — surfaces missing entity data in the brief
- Plan refresh cycle — approved proposals trigger standing context refresh
- `KaizenProposal` extended with proposal_type, target_file, target_section

### Sprint 5.5: Pit Crew (Self-Authoring Layer)
- `engine/pit_crew.py` — skill generation with Red Zone governance
- Generates SKILL.md, prompt.md, config.yaml per skill
- All Pit Crew operations require explicit Red Zone approval

## What This Sprint Delivers

Sprint 6 adds TWO things:

1. **ADR-001: Universal Ratchet Classification** — The two-layer pattern (deterministic first → LLM fallback → telemetry → demotion) has been reinvented 7 times across the codebase. This sprint codifies it as one function (`ratchet_classify()`) that enforces the pattern and produces standardized telemetry the Ratchet can systematically read.

2. **Autonomic Memory** — The system learns from operator corrections. When the coach says "Danny's issue is alignment, not confidence," the Memory Accumulator detects the correction, normalizes it through the pipeline, and proposes a memory entry via the Kaizen queue. Confirmed learnings persist in standardized exhaust and compound across sessions.

## CRITICAL ARCHITECTURAL CONSTRAINT

**The interpret layer in `ratchet_classify()` MUST route through the invariant pipeline via the cognitive router.** It is NOT a raw `call_llm()` call. The interpret route is declared in `routing.config` — which tier, which prompt template, which zone. The engine reads config and routes through all 5 pipeline stages.

A hardcoded LLM call that bypasses the pipeline is an **Invariant #1 violation.** No exceptions.

This means:
- Each classification task declares its LLM fallback as a `routing.config` entry
- The `ratchet_interpreter` handler in `dispatcher.py` is a generic handler that reads the prompt template from config and returns structured results
- New classification tasks = new config entries + prompt templates. No engine code changes.

## Source Documents (READ THESE BEFORE PLANNING)

Two concept documents contain the full architectural vision:

1. **`docs/ADR-001-ratchet-classification.md`** — The universal classification function. Contains:
   - The two-layer architecture (deterministic → pipeline interpretation)
   - The `RatchetConfig` and `ratchet_classify()` function signatures
   - Routing.config entries for classification sub-intents
   - All 7 existing implementations that need refactoring
   - The standardized classification telemetry schema
   - Enforcement rules

2. **`docs/SPRINT-6-CONCEPT-autonomic-memory.md`** — The memory architecture. Contains:
   - Standardized exhaust schema (the interoperability format)
   - Memory Accumulator subprocess (Cortex Lens 7)
   - Haiku normalization layer
   - Memory digest (human-readable view)
   - Exhaust manifest (connection protocol)
   - The multidimensional flywheel
   - Epic structure (6.0, 6A, 6B, 6C, 6D)

## Epic Structure and Sequencing

### Epic 6.0: ADR-001 Implementation (PREREQUISITE — ships first)

1. Create `engine/ratchet.py` with `ratchet_classify()`, `RatchetConfig`, `RatchetResult`
2. Add `ratchet_interpreter` handler to `dispatcher.py` — generic handler that reads prompt template from config, returns structured classification
3. Add ratchet classification routes to `routing.config`:
   - `ratchet_intent_classify` (Tier 2, Sonnet)
   - `ratchet_entity_extract` (Tier 1, Haiku)
   - `ratchet_gap_detect` (Tier 1, Haiku)
   - `ratchet_correction_detect` (Tier 1, Haiku)
4. Add prompt templates for each classifier (in config or referenced by config)

5. Refactor `cognitive_router.py:classify()` onto `ratchet_classify()`:
   - Extract keyword matching into a deterministic function
   - Point `interpret_route` to `ratchet_intent_classify` in routing.config
   - Remove bespoke telemetry logging (ratchet_classify handles it)
6. Refactor `cortex.py:_extract_entities()` + `_extract_entities_llm()` onto `ratchet_classify()`:
   - Extract regex logic into a deterministic function
   - Point `interpret_route` to `ratchet_entity_extract`
   - Merge two methods into one call
7. Add `ratchet_classify()` configs for gap detection and plan update detection
8. Update `CLAUDE.md` with Invariant #12: Ratchet Classification
9. All existing tests must still pass

### Epic 6A: Standardized Exhaust Schema + Log

- Define exhaust entry schema (see concept doc for full YAML spec)
- Create `telemetry/exhaust.jsonl` as the standardized exhaust log
- Add `write_exhaust()` and `read_exhaust()` to `engine/telemetry.py`
- Add type filtering: `read_exhaust(type="correction")`
- Update `gather_state_snapshot()` to read exhaust log summaries
- Context Gardener outputs become exhaust entries on approval

### Epic 6B: Memory Accumulator (Cortex Lens 7)

- New Cortex lens: correction detection from telemetry patterns
- Uses `ratchet_classify()` with `ratchet_correction_detect` route
- Signal detection: Jidoka rejection + follow-up, explicit correction language, entity edit detection
- Haiku normalization: varied human expression → standardized exhaust entries (through the pipeline)
- Kaizen proposal: "I noticed you corrected X. Save to memory?"
- On approval: write to exhaust.jsonl, refresh standing context

### Epic 6C: Memory Digest Generator

- Create `dock/system/memory-digest.md` — human-readable view of confirmed learnings
- Regenerated when exhaust log changes (after Kaizen approval)
- Standing context reads the digest for persona awareness
- Categories: entity corrections, timing patterns, priority learnings, dismissed observations

### Epic 6D: Exhaust Manifest (Connection Protocol)

- Create `config/exhaust-manifest.yaml` — declares subprocess producers and consumers
- Engine reads manifest at startup, wires connections
- Context Gardener updated to consume from exhaust.jsonl
- Ratchet updated to read exhaust entries for demotion candidates
- Foundation for cross-autonomaton connections (Sprint 7+)

## Architecture You Must Understand

### The Invariant Pipeline (Immutable)
Every input traverses 5 stages: Telemetry → Recognition → Compilation → Approval → Execution. No bypass paths. The interpret layer in `ratchet_classify()` routes through this pipeline — it is NOT a shortcut.

### The Ratchet Thesis
Every LLM classification logs to telemetry. Over time, the Ratchet spots stable patterns and proposes Tier 0 deterministic rules. The keyword list WRITES ITSELF through confirmed patterns. Manual keyword expansion is forbidden.

### The Fractal Pattern
The pipeline is fractal. The top-level REPL runs it on operator input. Each Cortex lens runs its own cycle. The Memory Accumulator runs its own cycle. Every subprocess produces standardized exhaust that any other subprocess can read.

### Config Over Code (Invariant #2)
Classification prompts, tiers, and zones are declared in routing.config. The `ratchet_interpreter` handler is generic — it reads config and routes. New classification tasks = new config entries. No engine code changes.

### Digital Jidoka (Invariant #4)
No silent failures. Every `except` block logs to telemetry. The Memory Accumulator proposes learnings through the Kaizen queue — the operator approves or dismisses. The system NEVER writes to the dock without approval.

## Sprint Discipline

- Always create a git worktree before modifying files
- `git worktree add -b sprint/autonomic-memory-v1 C:\GitHub\grove-autonomaton-primative-autonomic-memory main`
- Write `.bat` files for git commits (inline messages with spaces fail on Windows CMD)
- Merge to main with fast-forward, then remove worktree and branch
- Audit repo FIRST, discuss plan with Jim SECOND, build THIRD

## How to Start This Session

1. Read `docs/ADR-001-ratchet-classification.md` (the universal function + refactoring targets)
2. Read `docs/SPRINT-6-CONCEPT-autonomic-memory.md` (the memory architecture + exhaust schema)
3. Audit `engine/cognitive_router.py` — the primary refactoring target for Epic 6.0
4. Audit `engine/cortex.py` — the entity extraction refactoring target + where Lens 7 goes
5. Audit `engine/dispatcher.py` — where `ratchet_interpreter` handler gets added
6. Audit `profiles/coach_demo/config/routing.config` — where classification sub-intents get declared
7. Run `python -m pytest tests/ -v` to confirm all tests pass before starting
8. Produce the atomic task breakdown from the concept docs
9. Discuss with Jim BEFORE writing code

## Key Files

| File | Role |
|------|------|
| `engine/cognitive_router.py` | Intent classification — refactor onto ratchet_classify() |
| `engine/cortex.py` | Entity extraction (refactor) + Memory Accumulator (new Lens 7) |
| `engine/compiler.py` | Standing context — needs exhaust log in snapshot |
| `engine/dispatcher.py` | Add ratchet_interpreter handler |
| `engine/telemetry.py` | Add write_exhaust() / read_exhaust() |
| `engine/pipeline.py` | ratchet_classify() routes through run_pipeline() |
| `engine/ratchet.py` | NEW — universal classification function |
| `profiles/coach_demo/config/routing.config` | Classification sub-intent routes |
| `profiles/coach_demo/config/exhaust-manifest.yaml` | NEW — subprocess connection protocol |
| `profiles/coach_demo/dock/system/memory-digest.md` | NEW — human-readable learning log |
| `profiles/coach_demo/telemetry/exhaust.jsonl` | NEW — standardized exhaust log |

## What NOT to Do

- **Do NOT hardcode LLM calls in ratchet_classify().** The interpret layer routes through the pipeline via routing.config. A raw `call_llm()` is an Invariant #1 violation.
- **Do NOT expand keyword lists manually.** Keywords grow through the Ratchet.
- **Do NOT write to dock/exhaust without Kaizen approval.** The operator decides.
- **Do NOT skip telemetry on any classification.** Every determination — deterministic or LLM — gets logged.
- **Do NOT make changes without discussing with Jim first.**

---

*"The LLM is the brain. Keywords are the reflex. Reflexes develop FROM experience."*
