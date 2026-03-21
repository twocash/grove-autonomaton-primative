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
**Resolved:** 2026-03-20

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
**Status:** ⬜ Open
**Priority:** MEDIUM — UX issue, not architectural
**Files:** `engine/glass.py`, `engine/pipeline.py`

**The Problem:**
Glass Pipeline rendering depends on telemetry traces emitted during pipeline execution. When the Kaizen prompt fires in Stage 4, Glass may render before or after the prompt interaction. Stage 4 (Approval) line sometimes missing from Glass output. The smoke test accepts either ordering but notes the gap.

**Root Cause:**
Glass reads from the telemetry stream post-pipeline. The Kaizen prompt interrupts the pipeline mid-Stage-4, and the approval trace may not have been written yet when Glass renders. Need to audit the trace emission points in `_handle_clarification_jidoka()` and `_log_approval_trace()`.

**The Fix:**
Ensure `_log_approval_trace()` fires for ALL exit paths from Stage 4, including every Kaizen option. Glass should always show 5 stages after pipeline completion, regardless of which Kaizen option was chosen.

**Acceptance Test:**
Smoke Test 2-4. Glass shows Stage 4 line (approval) in all cases — green auto-approve, Kaizen Option 1, Kaizen Option 2.

**Commit:** _pending_

---

## V-004: Overly Complex _handle_clarification_jidoka()
**Status:** ⬜ Open
**Priority:** HIGH — readability, 200+ lines of nested branching
**Files:** `engine/pipeline.py`

**The Problem:**
`_handle_clarification_jidoka()` in pipeline.py is ~200 lines of nested if/elif with duplicated routing logic for Options 1-4, plus a nested fallback Jidoka prompt when Option 1 fails. This is the most complex method in the entire pipeline and it's doing too much.

**Root Cause:**
Sequential Claude Code sessions each added edge cases and fallback paths without refactoring. The method now contains: the Kaizen prompt, Option 1 (LLM classification + fallback Jidoka), Option 2 (local context routing), Option 3 (config-driven sub-menu + resolution), Option 4 (rephrase), plus telemetry for each path.

**The Fix:**
Each option should be a clean, named helper method. The main method should be a 20-line switch that reads like architecture: "If choice 1, escalate to LLM. If choice 2, route to local context. If choice 3, show config options. If choice 4, cancel." The routing logic for Options 2/3 is identical (set intent, domain, zone, handler on self.context) — extract to a shared method.

**Dependency:** V-001 must be resolved first (changes Option 1 flow).

**Acceptance Test:**
Smoke Test 2-4. Same behavior, half the code. A reviewer should be able to read the method and understand the consent flow in 30 seconds.

**Commit:** _pending_

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
**Status:** ⬜ Open
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

**Commit:** _pending_

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
**Status:** ⬜ Open
**Priority:** HIGH — tests must enforce invariants, not just pass
**Files:** `tests/`

**The Problem:**
Tests reference removed concepts (force_route, ratchet_classify, sub-pipelines) after V-001. `tests/test_cortex.py` imports deleted `engine.ratchet` — crashes at import time. Tests may also be testing implementation details rather than architectural invariants.

**Dependency:** V-001 (resolved).

**The Fix:**
Audit test suite against the 7 invariant tests from the Architect SKILL. Remove tests that test removed features. Ensure the 7 mandatory invariant tests exist and pass.

**Acceptance Test:**
`pytest` passes. All 7 invariant tests from the Architect SKILL are present and green.

**Commit:** _pending_

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

## Recommended Sequence

1. ~~**V-005** (tmpclaude cleanup)~~ ✅
2. ~~**V-001** (sub-pipeline removal)~~ ✅ `d705d40`
3. **V-002** (keyword bloat — simplifies the demo experience)
4. **V-004** (clarification jidoka simplification — depends on V-001)
5. **V-003** (Glass consistency — UX polish)
6. **V-010** (Glass stale intent — vet architecturally before implementing)
7. **V-006** (documentation update — depends on V-001)
8. **V-007** (dispatcher audit — depends on V-001)
9. **V-008** (startup audit)
10. **V-009** (test suite alignment — depends on V-001)

---

*Last updated: 2026-03-20*
*Register maintained by: Jim Calhoun / Grove Architecture*
