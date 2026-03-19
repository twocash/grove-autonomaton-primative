# SPRINT: Purity Audit v1 — Pipeline Integrity & The Ratchet

> *"Design is philosophy expressed through constraint."*
> Sprint Name: `purity-audit-v1`
> Generated: 2026-03-18
> Provenance: Architectural Purity Audit performed against Pattern Release 1.3 and TCP/IP Paper

---

## Purpose

This sprint fixes the structural violations discovered in the purity audit.
The codebase is architecturally sound — the invariant pipeline holds, zone
governance is declarative, telemetry fires before processing. But four HIGH
violations exist that undermine the proof-of-concept's ability to demonstrate
the claims made in both published papers.

Two categories of violation:

**Category A: Pipeline Bypass (Violations 1-3)**
Three codepaths call `call_llm()` directly without traversing the five-stage
pipeline. This breaks Invariant #1 (the hourglass) and Invariant #5 (Feed-First
Telemetry). These are real cognitive work — LLM calls that produce operator-facing
output — happening outside governance. An auditor tracing the telemetry log would
see gaps where the system did work but left no structured trace.

**Category B: The Ratchet Does Not Ratchet (Violation 7)**
The Cognitive Router classifies ambiguous input by calling Tier 2 (Sonnet) every
time. There is no mechanism for a confirmed LLM classification to become a Tier 0
deterministic lookup on the next occurrence. The Ratchet analysis (Lens 4) can
*propose* tier demotions, but the router has no pattern cache to *receive* them.
This means the central economic argument of both papers — "gets cheaper with use" —
is assertion, not demonstration.


## Domain Contract

**Applicable contract:** Autonomaton Architect (Anti-Code-Party Protocol)
**Contract version:** 1.0
**Additional requirements:** All changes must route through declarative config.
No new imperative handlers. The engine reads the map; the map is never built
into the engine.

---

## What Success Looks Like

After this sprint:

1. **Zero pipeline bypasses.** Every LLM call in the system traverses all five
   stages. An auditor reading `telemetry.jsonl` can reconstruct every cognitive
   action the system performed, including welcome briefings, startup briefs,
   and plan generation.

2. **The Ratchet turns.** When the LLM classifies "how's my season going?" as
   `strategy_session` with 0.85 confidence, and the operator confirms by
   proceeding, that classification is cached. Next time the operator types
   something similar, the Cognitive Router resolves it at Tier 0 — deterministic
   lookup, zero API cost, zero latency. The telemetry shows the demotion.

3. **Cortex stops prompting.** Entity validation proposals go to the Kaizen
   queue. They get processed at startup or via `queue` command — through the
   pipeline, with telemetry, with zone governance.

4. **Tests prove it.** New tests verify that startup sequences produce telemetry
   events, that the pattern cache resolves confirmed classifications, and that
   the Cortex never calls `input()` or `print()` directly.

---

## Epic Structure

### Epic A: Route Startup Sequences Through the Pipeline
**Violations addressed:** #2 (welcome briefing), #2 (startup brief), #3 (first-boot plan)
**Invariants enforced:** #1 (Pipeline), #5 (Feed-First), #6 (Unified Governance)

Three functions in `autonomaton.py` call `call_llm()` directly:
- `generate_welcome_briefing()` — Tier 2 call, no telemetry, no governance
- `generate_startup_brief()` — Tier 2 call, no telemetry, no governance
- First-boot plan generation — Tier 2 call, manual Stage 4 reimplementation

**Fix:** Create three internal intents in `routing.config` (`welcome_card`,
`startup_brief`, `generate_plan`). Route each through `run_pipeline()`.
Replace the direct LLM calls in `main()` with pipeline invocations.
The dispatcher handlers already exist or are trivially adapted from the
existing functions.

**Key constraint:** These are *internal* pipeline invocations (source:
`system_startup`), not operator-typed commands. The pipeline must accept
programmatic invocation with the same governance guarantees.

### Epic B: The Pattern Cache (The Ratchet in Motion)
**Violation addressed:** #7 (No Tier 0 cache)
**Principles enforced:** The Ratchet, Reverse Tax, Cognitive Router tiers

This is the hardest and most important epic. The Cognitive Router currently
has two paths: Tier 0 keyword matching and Tier 1/2 LLM escalation. There
is no bridge between them — no mechanism for confirmed LLM classifications
to become Tier 0 lookups.

**Fix:** Add a pattern cache file (`config/pattern_cache.yaml`) that the
Cognitive Router checks between keyword matching and LLM escalation.

The cache stores: `{normalized_input_hash: {intent, domain, zone, tier,
confidence, handler, handler_args, confirmed_count, last_confirmed}}`.

Population mechanism:
- When an LLM classification leads to successful execution (approved + executed),
  the pipeline's post-execution hook writes the classification to the cache.
- The cache entry includes a `confirmed_count` that increments on repeat confirmations.
- The router checks the cache after keyword match fails but BEFORE LLM escalation.
- Cache hits resolve as Tier 0 with confidence proportional to confirmed_count.

Eviction: entries not confirmed in 30 days decay. Operator can clear the cache
via a `clear cache` command (Yellow zone — it's modifying system behavior).

**This is the Ratchet.** Every confirmed LLM classification becomes a
deterministic lookup. The system literally gets cheaper with use.

### Epic C: Cortex Governance Compliance
**Violation addressed:** #1 (Cortex bypasses Stage 4)
**Invariant enforced:** #6 (Unified Governance)

`cortex.py` → `ask_entity_validation()` calls `print()` and `input()` directly
during the tail-pass. This is approval logic happening outside the pipeline.

**Fix:** Remove all direct I/O from the Cortex. Entity validation proposals go
to the Kaizen queue as Yellow-zone items. They get processed through the pipeline
at startup (via `process_pending_queue()`) or on-demand via `queue` command.

The Cortex becomes a pure analytical layer — it reads telemetry, produces
proposals, and writes them to the queue. It never prompts the operator.

### Epic D: Test Suite for Purity Invariants
**Cross-cutting:** Verifies all three epics hold under test.

New test file: `tests/test_purity_invariants.py`

Tests:
- Startup sequences produce telemetry events
- Pattern cache resolves confirmed classifications at Tier 0
- Pattern cache entries include correct metadata
- Cortex never calls `input()` or `print()`
- Pipeline context traces show all 5 stages for internal invocations
- Cache eviction works on stale entries
- Red zone cannot be auto-approved via cache (sovereignty safety)

---

## Sequencing & Gates

```
Epic A (Pipeline Bypass) ──→ GATE: All startup LLM calls produce telemetry
        │
Epic C (Cortex Governance) ─→ GATE: Cortex has zero direct I/O calls
        │
Epic B (Pattern Cache) ─────→ GATE: Confirmed classification resolves at Tier 0
        │
Epic D (Tests) ──────────────→ GATE: All new + existing tests pass
```

Epic A and C can be done in parallel — they touch different files.
Epic B depends on A being complete (the pipeline post-execution hook
needs the clean pipeline path to exist).
Epic D runs after all three.

---

## Files Touched

| File | Epic | Change Type |
|------|------|-------------|
| `engine/cognitive_router.py` | B | Add pattern cache check between keyword and LLM |
| `engine/pipeline.py` | A, B | Add post-execution cache write; accept internal invocations |
| `engine/cortex.py` | C | Remove direct I/O; queue-only proposals |
| `engine/dispatcher.py` | A | Adapt startup handlers for pipeline routing |
| `autonomaton.py` | A | Replace direct LLM calls with `run_pipeline()` |
| `profiles/*/config/routing.config` | A, B | Add internal intents; cache management intent |
| `profiles/*/config/pattern_cache.yaml` | B | New file — the Ratchet cache |
| `tests/test_purity_invariants.py` | D | New test file |

## Anti-Patterns to Watch For

Per the Autonomaton Architect protocol:

1. **Do NOT hardcode cache logic into the router class.** The cache is a
   config file. The router reads it. Config over code.
2. **Do NOT create a separate "internal pipeline" path.** The same pipeline
   handles operator input and system-initiated input. Same stages. Same
   governance. Different `source` field in telemetry.
3. **Do NOT skip Stage 4 for internal intents.** Green zone auto-approves.
   That IS the pipeline working. The stage still executes; it just returns
   `approved=True` immediately for green-zone intents.
4. **Do NOT make the pattern cache a Python dict in memory.** It must be a
   file the operator can inspect, edit, and delete. Declarative sovereignty
   means the operator controls their own Ratchet.
