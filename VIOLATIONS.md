# Autonomaton Architectural Violations Register

> Each violation is one Claude Code session. Fix it, test it, commit it, move on.

**Status key:** ⬜ Open | 🔧 In Progress | ✅ Resolved | ⏭️ Deferred

---

## V-001: Sub-Pipeline Cache Poisoning (ADR-001 Violation)
**Status:** ✅ Resolved
**Priority:** CRITICAL — blocks all smoke testing
**Files:** `engine/pipeline.py`, `engine/cognitive_router.py`, `engine/ratchet.py`, `engine/dispatcher.py`, `profiles/reference/config/routing.config`

**The Problem:**
`_escalate_to_llm()` in cognitive_router.py spawns a nested pipeline via `run_pipeline(force_route="ratchet_intent_classify")`. The inner pipeline's `_write_to_pattern_cache()` stores the forced route intent (`ratchet_intent_classify`) instead of the actual classified intent (`explain_system`). The Ratchet cache is poisoned. Subsequent identical inputs dispatch to the classification handler instead of answering the question.

**Root Cause:**
ADR-001 decided LLM classification should traverse a nested pipeline "for telemetry consistency." This violates the core invariant: one operator input = one pipeline traversal. The pipeline is for operator interactions, not internal function calls. LLM classification is Stage 2 infrastructure.

**The Fix:**
1. Rewrite `_escalate_to_llm()` to make a direct LLM call via `llm_client.call_llm()` instead of spawning a sub-pipeline
2. The LLM call should: send the user's input + list of valid intents, request structured JSON classification, log via llm_client's existing telemetry
3. Return the classification result (intent, confidence, metadata) to the caller
4. Remove `force_route` parameter from `PipelineContext` and `run_pipeline()`
5. Remove the force_route branch in `_run_recognition()`
6. Remove `ratchet_intent_classify` route from `routing.config`
7. Remove or repurpose `ratchet_interpreter` handler from dispatcher
8. Remove `engine/ratchet.py` (the universal ratchet_classify function)
9. Clear the poisoned pattern cache
10. Supersede ADR-001 with a note

**Acceptance Test:**
Smoke Test 2-5. After Option 1 consent, `show cache` must show `intent: explain_system`, not `intent: ratchet_intent_classify`. Test 4 (THE RATCHET) must show `intent:explain_system T0 cache ✓ $0.00`.

**Commit:** d705d40 `V-001-remove-sub-pipeline` — 14 files, +129/-884 lines. Removed `engine/ratchet.py`, `force_route` from pipeline, `ratchet_interpreter` from dispatcher, ratchet routes from all profiles. `_escalate_to_llm()` rewritten as direct `call_llm()`. ADR-001 superseded. Startup ceremony calls fixed to use keyword routing with `source="startup_ceremony"`.

**Addendum (bcd4132):** Fixed tier bug in `_kaizen_llm_classify()`: LLM classification RoutingResult was inheriting `tier=1` from route config instead of `tier=2` (actual compute used). This prevented `_write_to_pattern_cache()` from firing (guard: `if tier < 2: return`). The Ratchet economic thesis requires the tier to reflect actual compute cost, not the route's preferred keyword tier. Single-line fix: `tier=rc.get("tier", 2)` → `tier=2`.

**Resolved:** 2026-03-20 (sub-pipeline removal), 2026-03-21 (tier fix + V-009 tests confirm)

**Note:** `tests/test_cortex.py` imports deleted `engine.ratchet` — will crash during pytest. Fix scope: V-009.

---

## V-002: Keyword List Bloat in routing.config
**Status:** ⬜ Open
**Priority:** HIGH — obscures the architecture for reviewers
**Files:** `profiles/reference/config/routing.config`

**The Problem:**
The `explain_system` route has ~150 keywords including conversational follow-ups ("ok but", "yeah but", "huh"), competitive comparisons ("vs openai", "vs langchain"), and general curiosity ("tell me more", "go on"). This is keyword-stuffing to avoid the Kaizen prompt — the exact problem the Kaizen prompt exists to solve.

**Root Cause:**
Claude Code sessions kept adding keywords to prevent unknown-input triggers, instead of letting the Kaizen consent flow work. The reference profile should demonstrate the Kaizen flow, not hide it behind exhaustive keyword lists.

**The Fix:**
Strip `explain_system` keywords to the core architectural terms only (pipeline, zones, ratchet, flywheel, jidoka, tiers, cognitive router). General curiosity and conversational follow-ups should either classify via the Ratchet (after first LLM classification) or route through the Kaizen prompt. The reference profile WANTS reviewers to see the Kaizen prompt — it's the consent architecture in action.

**Acceptance Test:**
Type "How is this different from a chatbot?" — should trigger Kaizen prompt (not keyword match). After Option 1 consent and Ratchet cache, the same input should resolve at T0 next time.

**Commit:** _pending_

---

## V-003: Glass Pipeline Rendering Inconsistency
**Status:** ⬜ Open (partially addressed by V-011)
**Priority:** MEDIUM — UX issue, not architectural
**Files:** `engine/glass.py`, `engine/pipeline.py`

**The Problem:**
Glass Pipeline rendering depends on telemetry traces emitted during pipeline execution. When the Kaizen prompt fires in Stage 4, Glass may render before or after the prompt interaction. Stage 4 (Approval) line sometimes missing from Glass output. The smoke test accepts either ordering but notes the gap.

**Root Cause:**
Glass reads from the telemetry stream post-pipeline. The Kaizen prompt interrupts the pipeline mid-Stage-4, and the approval trace may not have been written yet when Glass renders. Need to audit the trace emission points in `_handle_clarification_jidoka()` and `_log_approval_trace()`.

**Partial Fix (V-011):** V-011 removes the duplicate `_log_approval_trace()` call after the Kaizen handler, eliminating the double Stage 4 line. Remaining issue: audit whether ALL Kaizen exit paths emit a trace that Glass renders as Stage 4.

**The Fix:**
Ensure `_log_approval_trace()` fires for ALL exit paths from Stage 4, including every Kaizen option. Glass should always show 5 stages after pipeline completion, regardless of which Kaizen option was chosen.

**Acceptance Test:**
Smoke Test 2-4. Glass shows Stage 4 line (approval) in all cases — green auto-approve, Kaizen Option 1, Kaizen Option 2.

**Commit:** _pending_

---

## V-004: Overly Complex _handle_clarification_jidoka()
**Status:** ✅ Resolved
**Priority:** HIGH — readability, 200+ lines of nested branching
**Files:** `engine/pipeline.py`, `profiles/*/config/kaizen.yaml`

**The Problem:**
`_handle_clarification_jidoka()` in pipeline.py is ~200 lines of nested if/elif with duplicated routing logic for Options 1-4, plus a nested fallback Jidoka prompt when Option 1 fails. This is the most complex method in the entire pipeline and it's doing too much.

**Root Cause:**
Sequential Claude Code sessions each added edge cases and fallback paths without refactoring. The method now contains: the Kaizen prompt, Option 1 (LLM classification + fallback Jidoka), Option 2 (local context routing), Option 3 (config-driven sub-menu + resolution), Option 4 (rephrase), plus telemetry for each path.

**The Fix:**
Config-driven dispatch via `kaizen.yaml`. Options defined declaratively, capabilities implemented as `_kaizen_{capability}` methods. Capability handlers mutate context state only; single `_log_approval_trace()` at end emits one Stage 4 event. LLM failure diagnostic uses `jidoka_llm_failure` stage (not approval stage) so Glass doesn't render it as Stage 4.

**Dependency:** V-001 must be resolved first (changes Option 1 flow).

**Acceptance Test:**
Smoke Test 2-4. Same behavior, half the code. A reviewer should be able to read the method and understand the consent flow in 30 seconds.

**Commit:** `76b2291` V-004: Declarative Kaizen consent flow — 4 files, +214/-194 lines
**Resolved:** 2026-03-21

---

## V-005: tmpclaude File Pollution
**Status:** ✅ Resolved
**Priority:** LOW — cosmetic but signals undisciplined process
**Files:** Root directory (`C:\GitHub\grove-autonomaton-primative\`)

**The Problem:**
~95 `tmpclaude-*` files in the repo root from previous Claude Code sessions. These are temp files that should have been cleaned up.

**The Fix:**
Deleted all 95 `tmpclaude-*` files. `.gitignore` already contained the pattern. Files were untracked (never committed to git).

**Acceptance Test:**
`dir tmpclaude-*` returns "File Not Found". `.gitignore` contains the pattern. ✅ Both verified.

**Resolved:** 2026-03-20 — filesystem cleanup only, no git commit needed (files were never tracked).

---

## V-006: CLAUDE.md Invariant #12 References ADR-001
**Status:** ✅ Resolved (completed during V-001)
**Priority:** MEDIUM — documentation accuracy
**Files:** `CLAUDE.md`, `docs/ADR-001-ratchet-classification.md`

**The Problem:**
CLAUDE.md Invariant #12 ("Ratchet Classification") describes the two-layer architecture with pipeline traversal for the interpret layer — the exact pattern identified as an architectural violation in V-001. After V-001 is resolved, this documentation is wrong.

**The Fix:**
1. Update Invariant #12 in CLAUDE.md to describe the correct pattern: keyword matching + direct LLM call (not sub-pipeline)
2. Add a "Superseded" header to ADR-001 with a brief note: "The interpret layer is a direct LLM call within the cognitive router, not a pipeline traversal. See V-001."
3. Remove references to `ratchet_classify()`, `force_route`, `ratchet_interpreter`, and `interpret_route` from CLAUDE.md

**Dependency:** V-001 must be resolved first.

**Acceptance Test:**
Read CLAUDE.md — no references to sub-pipelines, force_route, or ratchet_classify().

**Commit:** Completed as part of V-001 (`d705d40`). Invariant #12 rewritten. ADR-001 file deleted. Full codebase search confirms zero references to `ratchet_classify`, `force_route`, `ratchet_interpreter`, or `interpret_route`.
**Resolved:** 2026-03-20 (verified 2026-03-21)

---

## V-007: Handler Bloat in dispatcher.py
**Status:** ⬜ Open
**Priority:** MEDIUM — code readability
**Files:** `engine/dispatcher.py`

**The Problem:**
Not yet audited. Expected: handlers that should be consolidated, handlers with hardcoded logic that should be config-driven, handlers that exist only to support removed features.

**The Fix:**
Audit after V-001. The `ratchet_interpreter` handler goes away. Check what else can be simplified.

**Acceptance Test:**
Each remaining handler is ≤50 lines. Handler names match routing.config handler references 1:1. No orphan handlers.

**Commit:** _pending_

---

## V-008: Startup Ceremony Bloat
**Status:** ⬜ Open
**Priority:** MEDIUM — UX cleanliness
**Files:** `autonomaton.py`, relevant handlers

**The Problem:**
Not yet audited. The reference profile skips startup ceremonies (welcome, brief, plan, queue). Need to verify this is clean — no LLM calls, no Jidoka prompts before the `autonomaton>` prompt appears.

**Acceptance Test:**
Smoke Test 1 (startup clean).

**Commit:** _pending_

---

## V-009: Test Suite Alignment
**Status:** 🔧 In Progress — Phase 1 complete, Phase 2 pending
**Priority:** HIGH — tests must enforce invariants, not just pass
**Files:** `tests/`

**Phase 1 — V-009 Telemetry-Based Architecture Tests: ✅ COMPLETE**
14 tests, 14 passing. Commit `bcd4132` on branch `v009-telemetry-tests`.
- `test_pipeline_invariant.py`: Tests 1, 7 (hourglass invariant, clean startup)
- `test_jidoka_consent.py`: Tests 2, 6 (Digital Jidoka, config-driven routing)
- `test_ratchet.py`: Tests 3, 4, 5 (consent-gated classification, Ratchet cache, cache integrity)
- `conftest.py`: Reference profile, mock_llm with full signature, cache cleanup per test
- All tests assert on telemetry traces, not PipelineContext — Feed-First Telemetry principle.

**Phase 2 — Legacy Test Cleanup: ⬜ OPEN**
Coach-specific tests deprecated. Old test files referencing removed concepts (`engine.ratchet`, `force_route`) need deletion or rewrite. Target: `pytest` runs clean across ALL test files, not just the V-009 files.

**Phase 3 — Flywheel Tests (8-10): ⬜ OPEN**
Tests for OBSERVE → DETECT → PROPOSE → APPROVE → EXECUTE → REFINE. These define the "authors its own evolution" target. Will likely need stub Flywheel infrastructure in the engine.

---

## V-010: Glass Shows Stale Intent After Kaizen Classification
**Status:** ✅ Resolved
**Priority:** MEDIUM — misleading display, not architectural
**Files:** `engine/glass.py`, `engine/pipeline.py`

**The Problem:**
When an unknown input triggers the Kaizen prompt and the operator consents to LLM classification (Option 1), Glass displays `intent:unknown` at Stage 2 — even though the LLM successfully classified the intent (e.g., `deep_analysis`). The handler and execution are correct, but the Glass display is stale.

**Root Cause:**
The Stage 2 telemetry trace is emitted in `_run_recognition()` BEFORE the Kaizen prompt fires in Stage 4. When `_handle_clarification_jidoka()` updates `self.context.intent` with the LLM-classified intent, the Stage 2 trace has already been written with `intent:unknown`. Glass reads traces — so it shows the stale value.

**Architectural Constraint:**
Any fix must be vetted for integrity against the pipeline invariant. The Stage 2 trace correctly reflects what Recognition knew at the time it ran. The question is whether Glass should render the trace-as-written (accurate to the stage) or the final pipeline state (accurate to the outcome). Both are defensible. The wrong answer is a hack that re-emits a fake Stage 2 trace after Stage 4 — that would corrupt the telemetry audit trail.

**Possible Approaches (evaluate before implementing):**
1. Glass renders final `context.intent` for the Recognition line instead of reading the Stage 2 trace — simple, but disconnects Glass from the telemetry stream
2. A dedicated "reclassification" trace emitted after Kaizen Option 1 succeeds, which Glass recognizes and uses to update the Stage 2 display — preserves telemetry integrity, adds complexity
3. Glass shows both: `intent:unknown → explain_system` — most honest, shows the Ratchet's value

**Acceptance Test:**
After Kaizen Option 1, Glass Stage 2 line must show the classified intent. `show telemetry` must NOT contain fabricated or backdated trace entries.

**Commit:** 629fe5a `V-010-glass-arrow` — Glass reads existing `approval_kaizen` trace's `resolved_intent` field. Shows `intent:unknown → explain_system` arrow. No telemetry fabrication.
**Resolved:** 2026-03-21

---

## V-011: Recognition Trace Lies About Tier and Method for Unknown Intents
**Status:** ✅ Resolved
**Priority:** HIGH — telemetry lies about cost on the free path
**Files:** `engine/cognitive_router.py`, `engine/pipeline.py`

**The Problem:**
When the cognitive router returns `unknown` (no keyword match, no cache hit), `_create_default_result()` sets `tier=2`. No LLM was called. Tier 2 means "Premium Cognition — LLM classification." The trace lies. Glass renders `T2 llm ~$0.003` for a path that cost nothing. When the operator chooses Kaizen Option 2 ("Answer from what you already know — free"), they see a cost that didn't happen.

Additionally, `_log_approval_trace()` fires after `_handle_clarification_jidoka()` returns, producing a duplicate Stage 4 line in Glass.

**Root Cause:**
`_create_default_result()` uses `tier=2` to mean "would need Tier 2 to classify" — but the `tier` field's architectural meaning is "which tier of intelligence HANDLED this request." No LLM handled it. The method determination in the recognition trace uses `tier >= 2` as a proxy for "LLM was called," compounding the lie. The duplicate Stage 4 comes from the Kaizen handler logging its own approval event, then `_run_approval()` logging a second one.

**Why tier=0 is also wrong:**
Tier 0 means Pattern Cache HIT. There was no cache hit. The highest tier that EXECUTED was Tier 1 (keyword matching). It produced a null result. That's the truth.

**The Fix (3 changes):**
1. `_create_default_result()` in `cognitive_router.py`: Change `tier=2` → `tier=1` (keyword matching ran, returned nothing)
2. Method determination in `_run_recognition()` trace in `pipeline.py`: Replace `tier >= 2` proxy with `llm_metadata.classification_confidence is not None` check
3. Remove `self._log_approval_trace()` call after `_handle_clarification_jidoka()` in `_run_approval()` (Kaizen handler already logged the approval)

**Acceptance Test:**
- Test 2 (Option 2): Glass shows `intent:unknown T1 keyword $0.00`, single Stage 4 line
- Test 3 (Option 1): Glass shows LLM tier and cost AFTER consent, reclassification arrow
- Test 1/4: No change

**Commit:** 107bf88 `V-011-tier-truth` — 2 files, +4/-4 lines
**Resolved:** 2026-03-21

---

## V-013: Flywheel Stage 2 — pattern_hash + DETECT
**Status:** ✅ Resolved
**Priority:** MEDIUM — enables "authors its own evolution"
**Files:** `engine/telemetry.py`, `engine/pipeline.py`, `engine/flywheel.py`, `engine/dispatcher.py`, `profiles/*/config/routing.config`, `profiles/*/config/cognitive-router/prompts/classify_intent.md`, `tests/test_flywheel.py`

**The Problem:**
The Skill Flywheel is the mechanism behind "authors its own evolution." Without `pattern_hash` in telemetry, the system can't detect recurring patterns. Without DETECT, the system can't propose improvements.

**The Fix:**
1. Add `pattern_hash` optional field to telemetry schema
2. Compute pattern_hash in `_log_pipeline_completion()` — uses pattern_label (from LLM) or intent:domain (from keyword match)
3. Enrich LLM classification prompt to return `pattern_label` (no extra cost — same call)
4. Cache `pattern_label` in Ratchet for free reuse on cache hits
5. Create `engine/flywheel.py` with `detect_patterns()` function
6. Add `flywheel` config section to routing.config (Config Over Code)
7. Add `show_patterns` route + handler (Green zone, Tier 0)
8. Create `tests/test_flywheel.py` with dual-write fixture for real telemetry reads

**Acceptance Test:**
- `pytest` passes (234 tests including 13 new flywheel tests)
- `show patterns` surfaces recurring patterns as skill candidates
- pattern_hash appears in completion telemetry traces
- LLM classifications include pattern_label in cache entry

**Commit:** `V-013-flywheel-detection`
**Resolved:** 2026-03-22

---

## Recommended Sequence

1. ~~**V-005** (tmpclaude cleanup)~~ ✅
2. ~~**V-001** (sub-pipeline removal + tier fix)~~ ✅ `d705d40` + `bcd4132`
3. ~~**V-010** (Glass stale intent)~~ ✅ `629fe5a`
4. ~~**V-006** (documentation update)~~ ✅ (completed during V-001)
5. ~~**V-011** (recognition trace lies — tier/method/cost)~~ ✅ `107bf88`
6. ~~**V-004** (clarification jidoka simplification)~~ ✅ `76b2291`
7. ~~**V-009 Phase 1** (telemetry-based architecture tests 1-7)~~ ✅ `bcd4132`
8. ~~**V-013** (Flywheel Stage 2 — pattern_hash + DETECT)~~ ✅
9. **V-009 Phase 2** (legacy test cleanup — now 234 tests)
10. **V-002** (keyword bloat — already partially addressed in reference profile)
11. **V-007** (dispatcher audit — extract coach-specific handlers)
12. **V-008** (startup ceremony audit — verify reference profile is clean)
13. **V-003** (Glass consistency — audit after V-011)
14. **V-009 Phase 3** (Flywheel Stages 3-6 — PROPOSE, APPROVE, EXECUTE, REFINE)

---

*Last updated: 2026-03-22 (V-013 complete — 234 tests green, Flywheel DETECT operational)*
*Register maintained by: Jim Calhoun / Grove Architecture*
