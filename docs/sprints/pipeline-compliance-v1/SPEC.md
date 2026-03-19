# SPRINT SPEC: Pipeline Telemetry Compliance

> *"Design is philosophy expressed through constraint."*
> Sprint Name: `pipeline-compliance-v1`
> Generated: 2026-03-19
> Provenance: Line-by-line audit against TCP/IP Paper, Pattern Doc 1.3, CLAUDE.md
> Dependency: Executes AFTER purity-audit-v2
> Domain Contract: Autonomaton Architect (Anti-Code-Party Protocol)

---

## Purpose

The pipeline is the invariant. Both published papers say each stage
produces a structured trace. The code produces two — Stage 1 and
Stage 5. Stages 2, 3, and 4 write to in-memory PipelineContext and
vanish. This is not a display bug. This is a pipeline that doesn't
do what the papers say it does. Every profile. Every interaction.

This sprint makes the pipeline produce what the architecture requires.
Eight violations identified. All fixed. All verified by tests that
enforce the invariants permanently.

---

## Architectural Compliance Audit

### Methodology
Every testable claim from the TCP/IP paper, Pattern Document, and
CLAUDE.md was extracted. Every engine file was read line-by-line.
Every claim verified against the code. No skimming. No assumptions.

Sources: [TCP] = TCP/IP Paper, [PAT] = Pattern Doc 1.3, [CLMD] = CLAUDE.md

### CRITICAL VIOLATIONS

**V1: Stages 2, 3, 4 Emit No Telemetry Traces**

Claim: "each stage produces a structured trace" [TCP §III]
Claim: "the audit trail is the learning loop" [PAT §IV]
Claim: "Every action MUST be logged before it is processed" [CLMD #5]

Code (engine/pipeline.py):

| Stage | Method | Telemetry? |
|-------|--------|------------|
| 1 Telemetry | _run_telemetry() | YES — log_event() |
| 2 Recognition | _run_recognition() | NO — PipelineContext only |
| 3 Compilation | _run_compilation() | NO — PipelineContext only |
| 4 Approval | _run_approval() | NO — PipelineContext only |
| 5 Execution | _run_execution() | YES — _log_pipeline_completion() |

2 events where 5 are required. An auditor cannot grep for Tier 2
classifications, dock queries, Yellow zone approvals, or Jidoka
events. Cortex and Ratchet have incomplete data for learning.
Impact: ALL profiles, ALL interactions.

**V2: Clarification Contains Hardcoded Domain Logic**

Claim: "Domain logic belongs in configuration files, not code" [CLMD #2]
Claim: "The engine is 100% domain-agnostic" [CLMD #10]

Code (engine/cognitive_router.py lines 530-600):
- get_clarification_options() returns "Draft or compile content",
  "Schedule something" — coach_demo-specific
- resolve_clarification() hardcodes intent="calendar_schedule",
  domain="lessons", handler="mcp_calendar",
  handler_args={"server": "google_calendar"}
- NONE of these intents exist in reference or blank_template profiles
- Picking option 2 in reference profile dispatches to a handler
  that doesn't exist. This is a crash path.
Impact: ALL non-coach_demo profiles. Profile isolation broken.

**V3: Keyword Gaps Cause False Jidoka on Basic Input**

Claim: Jidoka fires for genuinely ambiguous input [CLMD #4]

All profiles' general_chat keywords: "hello", "hi", "hey",
"how are you", "who are you", "what can you do",
"good morning", "good afternoon"

Missing: "my name is", "thanks", "thank you", "bye", "goodbye",
"nice to meet you", "what is this", "good evening"

"my name is bob" triggers Jidoka across ALL profiles. This is not
ambiguous input. It's a classification failure.
Impact: ALL profiles. False Jidoka erodes governance trust.

### HIGH VIOLATIONS

**V4: Jidoka Resolution Not Logged to Telemetry**

When _handle_clarification_jidoka() fires and resolves, the
resolution is NOT logged. An auditor sees a clean pipeline
completion with no trace that governance intervention occurred.
Impact: ALL profiles. Governance decisions invisible.

**V5: Smart Clarification Generates Hallucinated Options**

"nuclear" triggers Jidoka (correct) but generates "Build a
nuclear-related skill" (hallucinated specificity). No ambiguity
floor for short, low-confidence inputs.
Impact: ALL profiles. Misleading Jidoka options.

**V6: Post-Pipeline Operator Prompting**

handle_skill_build_interactive() in autonomaton.py calls input()
AFTER Stage 5 dispatches. Violates Invariant #6 and Handler
Interface Contract ("Handlers NEVER prompt the operator directly").
Impact: Profiles with pit_crew.

### MEDIUM VIOLATIONS

**V7: LLM Cost Not in Main Telemetry Stream**

cost_usd field exists on TelemetryEvent but is never populated by
the pipeline. Cost data goes to separate cost_log.jsonl.
Impact: ALL profiles. Ratchet can't analyze cost patterns.

**V8: Clarification Behavior Not Declarative**

Clarification options and resolution logic hardcoded in Python.
Domain expert cannot alter via config file.
Impact: ALL profiles. Declarative governance incomplete.

### WHAT THE CODE GETS RIGHT

- ✓ Pipeline traversal — every input through run_pipeline()
- ✓ Zone governance — green/yellow/red in Stage 4
- ✓ Effective zone computation — most restrictive wins
- ✓ Fate-sharing — all state in profile directory
- ✓ Model config externalized — models.yaml
- ✓ Pattern cache (Ratchet) — confirmed LLM → Tier 0
- ✓ Ratchet classification (ADR-001) — deterministic-first
- ✓ Red zone UX — confirm_red_zone_with_context()
- ✓ Schema-validated telemetry
- ✓ No direct LLM calls in autonomaton.py
- ✓ Cortex governance — no direct I/O in analytical layer

---

## Why Glass Comes Free

If each stage emits a telemetry event as it completes:
1. The telemetry stream IS the observation layer
2. Glass reads the same stream as Cortex, Ratchet, Flywheel
3. No callback system. No parallel channel. Just telemetry
4. Glass becomes ~30 lines of telemetry formatting

---

## Epics

### Epic A: Per-Stage Telemetry Traces (V1, V4, V7)
Each pipeline stage emits a structured log_event() after writing
to PipelineContext. Stage 1's event id becomes the pipeline_id
correlation key. Jidoka resolution logged with human_feedback.
Cost_usd populated from LLM client data.

### Epic B: Declarative Clarification (V2, V8)
New clarification.yaml per profile declares fallback options.
Engine reads config. get_clarification_options() and
resolve_clarification() become config readers. Zero domain
logic in engine code.

### Epic C: Classification Accuracy (V3, V5)
Expand general_chat keywords across all profiles. Add ambiguity
floor: ≤2 words AND confidence <0.2 → skip LLM smart
clarification, use config-driven fallback.

### Epic D: Skill Build Pipeline Compliance (V6)
Eliminate input() call in handle_skill_build_interactive().
Require description inline: "build skill foo for tracking stats".
Handler extracts via extract_args. Missing description returns
instructional message. Zero input() outside pipeline.

### Epic E: Glass Telemetry Consumer
Rewrite glass to read telemetry events by pipeline_id instead of
PipelineContext. Same visual output. Architecturally correct
data source.

### Epic F: Invariant Test Suite
Tests that ENFORCE architectural claims permanently. Per-stage
trace verification. Profile isolation. Classification accuracy.
Zero domain logic in engine. These block future regressions.

---

## Sequencing & Gates

```
Epic A (Per-Stage Traces) ───→ GATE: 5 telemetry events per traversal
        │
Epic B (Declarative Clarif) ─→ GATE: zero domain logic in engine
        │
Epic C (Classification) ────→ GATE: "my name is bob" → general_chat
        │
Epic D (Skill Build) ───────→ GATE: zero input() outside pipeline
        │
Epic E (Glass Consumer) ────→ GATE: glass reads telemetry, not ctx
        │
Epic F (Invariant Tests) ───→ GATE: all tests pass permanently
```

A lands first. B and C are independent. D is independent.
E depends on A. F runs last.

---

## Architectural Decisions

ADR-001: Per-stage log_event(), not callbacks.
Each stage calls log_event(). The telemetry stream IS the
observability layer. No parallel channels.

ADR-002: pipeline_id as correlation key.
Stage 1's event id propagates to stages 2-5 via
inferred.pipeline_id. Consumers reconstruct traversals
by grouping on pipeline_id.

ADR-003: Clarification config per profile.
New clarification.yaml declares fallback options. Engine
reads config. Options resolve to intents in routing.config.
No hardcoded intents that may not exist in active profile.

ADR-004: Inline skill description.
"build skill foo for tracking stats" — handler extracts
name and description from input. Missing description
returns instructional message. Zero input() calls.

ADR-005: Glass reads telemetry, not PipelineContext.
Glass reads events from telemetry.jsonl matching pipeline_id.
Formats for terminal. Same data source as every other consumer.

ADR-006: Ambiguity floor for smart clarification.
≤2 words AND confidence <0.2 → skip LLM smart clarification.
Use config-driven fallback. LLM cannot meaningfully disambiguate
a single word.

---

## Files Touched

| File | Epic | Change |
|------|------|--------|
| engine/pipeline.py | A, D | Per-stage traces; remove post-pipeline prompt |
| engine/cognitive_router.py | B | Config-driven clarification |
| engine/glass.py | E | Telemetry consumer rewrite |
| engine/ux.py | — | No change |
| autonomaton.py | D, E | Remove skill build interactive; wire glass |
| profiles/*/config/routing.config | B, C | Keywords; extract_args |
| profiles/*/config/clarification.yaml | B | NEW — per-profile fallback |
| tests/test_pipeline_compliance.py | F | NEW — invariant enforcement |
| .gitignore | — | tmpclaude pattern |

---

## Quality Gate

"Design is philosophy expressed through constraint."

Position: The pipeline's telemetry stream is the single source
of truth for all observability. Not a parallel channel.

Constraint: Each stage emits a structured trace to the same
stream. Every consumer reads the same data. There is no other path.
