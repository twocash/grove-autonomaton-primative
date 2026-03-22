# Architectural Compliance Roadmap

> *Audit conducted 2026-03-21 against Pattern Release Draft 1.3, TCP/IP Paper (Working Draft), and autonomaton.html presentation deck.*
> *Tag under review: `v0.1.0-pattern-proven` (86ac595)*
> *Test suite at audit time: 221 passed, 0 failures*

**Overall Grade: B+**

The pipeline invariant is structurally sound. V-001 (sub-pipeline violation) is resolved. The Ratchet works. Feed-first telemetry is enforced. Zone governance is functional. What pulls this from an A is terminology drift that obscures the Toyota Production System lineage, a second pipeline code path that violates the hourglass invariant, and spec-level features (Skill Flywheel stages 2-6) that exist in the white paper but have no implementation surface.

This document defines the sprint backlog to bring the reference implementation into full compliance with the published specification. Each sprint is one Claude Code session. One fix. Clean commit. Move on.

---

## Sprint Backlog

| Sprint | ID | Title | Impact | Complexity | Unblocks |
|---|---|---|---|---|---|
| **1** | V-010 | ~~Pipeline Invariant Bug: `run_pipeline_with_mcp()` second code path~~ | CRITICAL | LOW | ✅ `b0811b3` |
| **2** | V-011 | ~~Jidoka / Andon / Kaizen terminology alignment~~ | HIGH | LOW | ✅ TPS lineage legible |
| **3** | V-012 | Dispatcher domain extraction | HIGH | MEDIUM | Config Over Code, Profile Isolation |
| **4** | V-013 | `pattern_hash` in telemetry + Flywheel Stage 2 stub | HIGH | MEDIUM | Self-improvement claim |
| **5** | V-014 | OOBE config annotation pass | MEDIUM | TRIVIAL | Three-files-and-a-loop story |
| **6** | V-015 | Red zone spec reconciliation | MEDIUM | LOW | Zone governance accuracy |
| **7** | V-005 | Repo hygiene (tmpclaude, nul, stale pycache) | LOW | TRIVIAL | External review readiness |

**Session discipline:** Read this document FIRST. Read the white paper SECOND. Then read the code for the specific sprint. Do not modify code outside the sprint scope. Do not add features. The correct direction for line count is DOWN.

---

## Standing Policy: Test Suite Governance

> **Effective after V-010. Applies to all sprints. This is not a sprint — it is a standing rule.**

Tests assert on **telemetry exhaust** or **structural invariants**. Nothing else matters.

A test suite audit (2026-03-21) found the suite is 64% implementation-coupled — tests that assert on RoutingResult fields, PipelineContext attributes, mock call_args, and function return values. These tests are **legacy scaffolding** from the build phase. They couple the suite to implementation shapes that are actively being refactored, and they break every time architecture improves.

**The 74 tests that matter:**
- **24 TELEMETRY tests** — send input through the pipeline, assert on the telemetry JSONL trace. These prove the pipeline works.
- **50 STRUCTURAL tests** — assert on code shape, file existence, config structure, import guards. These prove the architecture hasn't drifted.

**The rule:**

When a compliance sprint breaks a legacy internal test, **DELETE IT**. Do not repair implementation-coupled tests. Do not rewrite them to match the new internal shape — that just re-couples to the new implementation.

The 74 telemetry + structural tests are the acceptance gate. **If they pass, the sprint passes.**

Over time, the 134 legacy tests die naturally as the architecture improves. No migration sprint. No conversion project. Line count goes down. Coupling goes down. Every sprint gets easier.

**Rationale (White Paper Part III §4):** "The telemetry stream is the single source of truth for audit, learning, and observability." A test suite that bypasses telemetry and reaches into internals contradicts the pattern's own first principle. Feed-first means feed-first — including in how we verify the system works.

---

## Sprint 1: V-010 — Pipeline Invariant Bug ✅ COMPLETE

### Title
Eliminate second pipeline code path in `run_pipeline_with_mcp()`

### Priority
CRITICAL — this is a violation of the hourglass invariant, the pattern's single most important architectural claim.

### The Problem

`run_pipeline_with_mcp()` (pipeline.py, lines ~980–1021) reimplements the five-stage pipeline sequence outside the `InvariantPipeline.run()` method:

```python
def run_pipeline_with_mcp(...) -> PipelineContext:
    pipeline = InvariantPipeline()
    pipeline.context = PipelineContext(...)  # Manually constructs context
    
    # Duplicated stage sequence — THIS IS THE BUG
    try:
        pipeline._run_telemetry()
        pipeline._run_recognition()
        pipeline._run_compilation()
        pipeline._run_approval()
        pipeline._run_execution()
    except Exception as e:
        pipeline._log_pipeline_failure(e)
        ...
    return pipeline.context
```

Two problems:

**Invariant violation.** The TCP/IP paper §III: "the five-stage pipeline is the thin waist of the cognitive hourglass." The thin waist must be ONE code path. If `run()` gets modified (new telemetry field, new error handling, new stage hook), `run_pipeline_with_mcp()` silently diverges. The invariant has a seam.

**Context construction bypass.** `run_pipeline_with_mcp()` manually sets `pipeline.context` before calling stages, bypassing `run()`'s context initialization. It pre-sets `mcp_action`, `domain`, and `zone` directly — meaning Stage 2 (Recognition) runs but the MCP metadata was already injected. The pipeline stages should be the ONLY authority over context state.

### Architectural Justification

- **Hourglass Invariant (TCP/IP Paper §III):** "Every cognitive interaction must pass through the same five stages in the same order." Two code paths = two hourglasses. Only one is tested by `test_pipeline_invariant.py`.
- **Declarative Behavior Governance (White Paper Part III §1):** MCP routing should be expressed in `routing.config`, not in a special-purpose pipeline entry point.
- **The One Rule:** "One operator input = one IMMUTABLE pipeline traversal. No exceptions. None."

### The Fix

1. **Delete `run_pipeline_with_mcp()`.** Find all call sites first.
2. **Route MCP interactions through `run_pipeline()`.** MCP intents are already classified by the Cognitive Router via keywords in `routing.config` (see `mcp_calendar`, `mcp_gmail` routes in coach_demo). The MCP action is already assembled by the dispatcher in Stage 5 (see `_handle_mcp_formatter()`). The separate entry point is scaffolding from early sprints.
3. **Migrate tests** that call `run_pipeline_with_mcp()` to call `run_pipeline()` with mock router return values.
4. **Verify:** `grep -r "run_pipeline_with_mcp" .` returns zero results. All tests pass.

### Files to Touch

| File | Action |
|---|---|
| `engine/pipeline.py` | Delete `run_pipeline_with_mcp()` (~40 lines) |
| `tests/test_mcp_governance.py` | Rewrite tests to use `run_pipeline()` with mock router |
| Any other callers | Search and migrate |

### Acceptance Test

1. `grep -r "run_pipeline_with_mcp" .` → zero results (excluding `.git`)
2. `pytest` → all tests pass
3. `pipeline.py` has exactly ONE public entry point: `run_pipeline()`
4. `InvariantPipeline.run()` is the SOLE implementation of the five-stage sequence

### Anti-Requirements

Do NOT create a new convenience wrapper. If MCP-specific setup is needed, it belongs in a pre-pipeline helper that constructs the `raw_input` string or in the Cognitive Router's classification logic. The pipeline is input-agnostic. That's the point.

### Commit Message
`V-010-single-pipeline-path`

### Result
- **Status:** ✅ COMPLETE
- **Commit:** `b0811b3` on branch `v010-single-pipeline-path`
- **Delta:** -54 lines (47 deleted from pipeline.py, 7 net removed from test_purity_v2.py)
- **Verification:** grep clean, 221 tests pass, single entry point confirmed
- **Date:** 2026-03-21

---

## Sprint 2: V-011 — Jidoka / Andon / Kaizen Terminology Alignment ✅ COMPLETE

### Title
Align code terminology with Toyota Production System lineage as defined in the white paper.

### Priority
HIGH — The TPS lineage is a core differentiator of the pattern. Imprecise terminology undermines the spec's most distinctive architectural claim.

### The Problem

The white paper defines three distinct TPS concepts:

- **Jidoka** = the DISCIPLINE. The system has awareness of quality and the authority to stop. "Automation with a human touch." White paper Part II: "Jidoka transforms a machine from a blind, repetitive engine into an active partner in quality control."
- **Andon** = the MECHANISM. The actual signal that fires. White paper Part II: "signals for human intervention with the 'andon cord'." And: "This is Toyoda's 'andon cord', digitized."
- **Kaizen** = the RESPONSE. The improvement proposal. White paper Part VI: "Kaizen means the system doesn't just stop. It analyzes the failure pattern, generates a proposed repair."

The code conflates these. The UX display header says "JIDOKA: Stopping the line for human input" when the Andon is what fires. The method `_handle_clarification_jidoka()` implements Kaizen (propose improvement paths) but is named Jidoka.

### The Fix — Terminology Map

| TPS Concept | Spec Definition | Code Element | Current Name | Target Name |
|---|---|---|---|---|
| Jidoka | Quality awareness discipline | The pipeline's ability to detect uncertainty | (implicit — correct) | (stays implicit) |
| Andon | The signal/stop mechanism | `ask_jidoka()` display header | "JIDOKA: Stopping the line" | "ANDON GATE: Stopping the line" |
| Kaizen | The improvement proposal flow | `_handle_clarification_jidoka()` | `_handle_clarification_jidoka` | `_handle_kaizen_proposal` |
| Kaizen config | Declarative improvement options | `kaizen.yaml` | Correct as-is | No change |
| Kaizen event | Pipeline event tracking | `kaizen_fired` | Correct as-is | No change |
| Jidoka (legitimate) | Failure detection with diagnostic context | Fail-fast / fail-loud behavior | Correct as-is | No change |

### Files to Touch

| File | Action |
|---|---|
| `engine/ux.py` | Rename display header in `ask_jidoka()`: "JIDOKA" → "ANDON GATE". Consider renaming the function to `fire_andon()` or adding an alias. |
| `engine/pipeline.py` | Rename `_handle_clarification_jidoka()` → `_handle_kaizen_proposal()`. Update caller. |
| `profiles/reference/config/clarification.yaml` | Update comment: "when Jidoka fires" → "after the Andon Gate fires" |
| `CLAUDE.md` | Update Invariant #4 to distinguish Jidoka (principle), Andon (mechanism), Kaizen (response) |
| `tests/test_jidoka_consent.py` | Rename to reflect Andon/Kaizen distinction |
| `SMOKE-TEST.md` | Update terminology in test descriptions |

### Acceptance Test

1. A reviewer reading `pipeline.py` sees three distinct concepts: Jidoka (quality awareness), Andon (the stop mechanism), Kaizen (the improvement proposal)
2. The UX display matches the white paper's terminology
3. All tests pass with updated names
4. `grep -r "clarification_jidoka" .` → zero results (excluding `.git`)

### Anti-Requirements

Do NOT change behavior. This is a naming pass. Zero functional change.

### Commit Message
`V-011-tps-terminology`

### Result
- **Status:** ✅ COMPLETE
- **Commit:** On branch `v011-tps-terminology`
- **Changes:**
  - `engine/ux.py`: Display header "JIDOKA" → "ANDON GATE", updated module docstring
  - `engine/pipeline.py`: Renamed `_handle_clarification_jidoka()` → `_handle_kaizen_proposal()`, updated comments
  - `profiles/reference/config/clarification.yaml`: Updated comment
  - `CLAUDE.md`: Updated Invariant #4 with TPS breakdown, Stage 4 description, Layer 2, Principle #6
  - `tests/test_jidoka_consent.py` → `tests/test_andon_consent.py`: Renamed file, class, method
  - `tests/test_ux_formatting.py`: Renamed classes and methods
  - `tests/test_reference_ux.py`: Updated comment
  - `tests/conftest.py`: Updated docstrings
- **Verification:** grep "clarification_jidoka" returns zero in active code, grep "JIDOKA: Stopping" returns zero, 221 tests pass
- **Date:** 2026-03-21

---

## Sprint 3: V-012 — Dispatcher Domain Extraction

### Title
Extract coach_demo-specific handlers from the shared engine dispatcher.

### Priority
HIGH — The dispatcher is 1,715 lines with 20+ handlers. Many are coach_demo domain features baked into the engine. This violates Config Over Code (Invariant #2) and Profile Isolation (Invariant #10).

### The Problem

The spec says the engine is "100% domain-agnostic." The `blank_template` profile proves the engine needs nothing domain-specific. But the dispatcher contains handlers that only make sense for coach_demo:

- `_handle_session_zero` — coach_demo intake
- `_handle_vision_capture` — coach_demo aspiration tracking
- `_handle_cortex_batch` — coach_demo analytical lenses
- `_handle_plan_update` — coach_demo plan management
- `_handle_regenerate_plan` — coach_demo plan generation
- `_handle_fill_entity_gap` — coach_demo entity management
- `_handle_generate_plan` — coach_demo first-boot plan
- `_handle_welcome_card` — coach_demo welcome ceremony
- `_handle_startup_brief` — coach_demo startup briefing

A CTO reading the reference profile's engine sees 20 handlers when the architecture requires ~5 for the reference demo: `status_display`, `general_chat`, `show_file`, `show_engine_manifest`, `clear_cache`.

### The Fix

Design sprint. Options include:
1. **Plugin handler registry** — handlers loaded from profile config, engine has only core handlers
2. **Handler module per profile** — `profiles/coach_demo/handlers.py` imported at runtime
3. **Conditional registration** — handlers registered only when their profile is active

The correct answer per the spec is option 1 or 2. The handler mapping should be declarative (config-driven registration), not a hardcoded registry.

### Architectural Justification

- **Config Over Code (White Paper Part III §1):** "Can a non-technical domain expert alter the system's behavior by editing a config file?" Handler registration should be config.
- **Profile Isolation (Invariant #10):** "The engine is 100% domain-agnostic." Domain handlers in the engine violate this.
- **Simplicity (TCP/IP Paper §III, RFC 3439):** "Complexity is the primary mechanism that impedes efficient scaling." 1,715 lines in the dispatcher is complexity in the pipeline's thin waist.

### Acceptance Test

1. `engine/dispatcher.py` contains only engine-core handlers (≤ 8)
2. coach_demo-specific handlers live in `profiles/coach_demo/` or a plugin mechanism
3. Reference profile works with the reduced handler set
4. coach_demo profile works with its domain handlers loaded at runtime
5. `blank_template` profile works with zero domain handlers
6. All tests pass

### Commit Message
`V-012-dispatcher-extraction`

---

## Sprint 4: V-013 — pattern_hash + Flywheel Stage 2 Stub

### Title
Add `pattern_hash` to telemetry and implement Flywheel detection (Stage 2).

### Priority
HIGH — The Skill Flywheel is the spec's most ambitious claim ("authors its own evolution"). Stages 2-6 are unimplemented. This sprint adds the structural prerequisite (pattern_hash) and the detection mechanism (Stage 2 stub).

### The Problem

The white paper's telemetry example includes `pattern_hash` as a field:
```json
{"ts":"2026-02-28T17:02:11-05:00","intent":"propose_skill","tier":2,
 "zone":"yellow","pattern_hash":"b1c2…","confidence":0.78,
 "cost_usd":0.012,"human_feedback":"approved"}
```

This field is absent from the implementation's `TelemetryEvent` schema. Without it, the telemetry can feed the Ratchet (which uses its own SHA-256 hash of raw input) but can't feed the broader Flywheel's detection stage: "When the same pattern_hash appears X+ times in N days, you have a candidate skill."

The Skill Flywheel has six stages per the spec (Part III §3):
1. OBSERVE — Log every interaction ✅ (implemented)
2. DETECT — Same pattern 3+ times → surface as candidate ❌ (not implemented)
3. PROPOSE — Draft a skill specification ❌ (not implemented)
4. APPROVE — Human blesses the pattern ❌ (not implemented)
5. EXECUTE — Skill runs automatically ✅ (Pit Crew skills work)
6. REFINE — Usage data improves the skill ❌ (not implemented)

### The Fix

**Part A: Add `pattern_hash` to telemetry**

Add a `pattern_hash` field to `TelemetryEvent`. The hash normalizes by intent so that "tell me about the pipeline" and "explain the pipeline stages" both map to `explain_system` and share a pattern_hash.

Compute as: `sha256(f"{intent}:{domain}".encode()).hexdigest()[:12]`

Populated by `_log_pipeline_completion()`. Optional field, backward compatible.

**Part B: Flywheel Stage 2 — Detection Stub**

Add a function (in `engine/flywheel.py` or `engine/cortex.py`) that:
1. Reads the last N telemetry entries
2. Groups by `pattern_hash`
3. Any pattern_hash appearing 3+ times within 14 days → candidate
4. Returns a list of candidate patterns with intent, count, last_seen

Add `show patterns` route to reference profile's `routing.config` that runs the detector and displays results.

### Architectural Justification

- **Skill Flywheel (White Paper Part III §3):** The six-stage flywheel is the mechanism behind "authors its own evolution." Without detection, the system can't propose.
- **Feed-First Telemetry (White Paper Part III §4):** "The telemetry serves triple duty: learning, observability, and compliance." The learning path is incomplete without pattern_hash.
- **The Compounding Effect (White Paper Part VI):** "Gets smarter with use. Pattern detection surfaces recurring needs you haven't consciously identified."

### Files to Touch

| File | Action |
|---|---|
| `engine/telemetry.py` | Add optional `pattern_hash` field to `TelemetryEvent` |
| `engine/pipeline.py` | Compute and include `pattern_hash` in `_log_pipeline_completion()` |
| `engine/flywheel.py` (new) or `engine/cortex.py` | Flywheel detection function |
| `profiles/reference/config/routing.config` | Add `show_patterns` route |
| `engine/dispatcher.py` | Add `show_patterns` handler |

### Acceptance Test

1. Telemetry entries include `pattern_hash` field
2. `show patterns` displays detected patterns with counts
3. Running the same intent 3+ times surfaces it as a detected pattern
4. All existing tests pass (backward compatible)

### Commit Message
`V-013-flywheel-detection`

---

## Sprint 5: V-014 — OOBE Config Annotation Pass

### Title
Annotate non-core config files as Out-of-Box Experience enhancements.

### Priority
MEDIUM — The spec says "three files and a loop." The reference profile has 8+ config files. Each is justified but the simplicity claim needs to be self-documenting.

### The Fix

Add a one-line comment at the top of each non-core config file:

```yaml
# OOBE: Out-of-box experience enhancement.
# Core pattern requires only: routing.config, zones.schema, telemetry.log
```

Create `profiles/reference/config/CONFIG-MANIFEST.md` categorizing:

**Core (required by pattern):**
- `routing.config` — Intent-to-handler mapping
- `zones.schema` — Zone governance definitions

**Core output (produced by pattern):**
- `telemetry/telemetry.jsonl` — Feed-first audit trail

**OOBE (enhances demo experience):**
- `kaizen.yaml` — Kaizen prompt options
- `clarification.yaml` — Fallback menu options
- `persona.yaml` — Engine personality for LLM responses
- `voice.yaml` — Brand voice configuration
- `ux.yaml` — Tips and display preferences
- `cognitive-router/prompts/classify_intent.md` — LLM classification prompt template

### Acceptance Test

1. Every non-core config file has the OOBE annotation
2. CONFIG-MANIFEST.md exists and is accurate
3. A reviewer can identify the three core files in under 10 seconds

### Commit Message
`V-014-oobe-annotations`

---

## Sprint 6: V-015 — Red Zone Spec Reconciliation

### Title
Reconcile Red zone behavior between spec and implementation.

### Priority
MEDIUM — The spec says Red zone "surfaces information only." The implementation offers "Approve and execute."

### The Problem

White paper Part III §2 (Sovereignty Guardrails):
> **Red — Human-Only Zones.** Architecture decisions, security changes, production deployments, anything the human has explicitly reserved for themselves. **The system doesn't propose here. It surfaces information and waits.**

The implementation's Red zone (`confirm_red_zone_with_context()`) offers "Approve and execute" as option 1. This is a proposal. The spec says no proposals in Red.

### The Fix

Two options (decide during sprint):

**Option A: Fix the implementation.** Red zone surfaces information and context but does NOT offer "Approve and execute." The operator must take the action through a different channel.

**Option B: Fix the spec.** Red zone requires "explicit approval with full context" (which is what the implementation does). Update spec language accordingly.

Either way, spec and code must agree. The decision should be documented as an ADR.

### Acceptance Test

1. Red zone behavior matches the spec's description word-for-word
2. `zones.schema` description for Red matches the chosen behavior
3. Decision documented

### Commit Message
`V-015-red-zone-reconciliation`

---

## Sprint 7: V-005 — Repo Hygiene

### Title
Clean temp files, stale caches, and Windows artifacts.

### Priority
LOW — cosmetic, but signals process discipline to external reviewers.

### The Fix

1. Delete all `tmpclaude-*` files from repo root
2. Delete `nul` file
3. Clean all `__pycache__` directories (especially `ratchet.cpython-314.pyc`)
4. Audit `.coach/` directory — delete if stale
5. Verify `.gitignore` coverage
6. `pytest` passes

### Commit Message
`V-005-repo-hygiene`

---

## Audit Context: What's Already Compliant

These elements PASSED the compliance review and should NOT be modified during these sprints:

| Element | Status | Evidence |
|---|---|---|
| 5-stage invariant pipeline | **PASS** | `pipeline.py`, `test_pipeline_invariant.py` |
| One input = one traversal | **PASS** | V-001 resolved, no sub-pipelines |
| Config-driven routing | **PASS** | `routing.config` is authoritative |
| Zone governance (Green/Yellow/Red) | **PASS** | Stage 4 is sole approval gate |
| Feed-first telemetry with validation | **PASS** | `telemetry.py`, schema enforcement |
| The Ratchet (Tier 2 → Tier 0 migration) | **PASS** | `_write_to_pattern_cache()`, `test_ratchet.py` |
| Glass Pipeline (telemetry-based rendering) | **PASS** | `glass.py` reads telemetry, not context |
| Profile isolation proof | **PASS** | `blank_template` exists |
| Model independence (structural) | **PASS** | Tier abstraction, output validation |
| Clean startup (no LLM before operator input) | **PASS** | `test_no_telemetry_before_operator_input` |
| V-001 sub-pipeline removal | **PASS** | `ratchet.py` deleted, `force_route` gone |
| V-009 telemetry-based tests | **PASS** | 221 tests, all green |

---

## How to Use This Document

**Before each Claude Code session:**
1. Read this document to identify which sprint you're working on
2. Read the white paper sections referenced in the sprint spec
3. Read ONLY the files listed in "Files to Touch"
4. Execute the fix per the spec
5. Run the acceptance test
6. Update this document: mark the sprint status, add commit hash

**After all sprints complete:**
Run the full compliance audit again. The target grade is A.

---

*Last updated: 2026-03-21 (V-010 complete, test policy added)*
*Author: Jim Calhoun / Grove Architecture*
*Audit partner: Claude (Opus 4.6)*
