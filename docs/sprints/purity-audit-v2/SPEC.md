# SPRINT: Purity Audit v2 — Inspectable Telemetry, Model Agnosticism, Zone UX

> *"Design is philosophy expressed through constraint."*
> Sprint Name: `purity-audit-v2`
> Generated: 2026-03-18
> Provenance: Architectural Purity Audit — MEDIUM violations
> Dependency: Executes AFTER `purity-audit-v1` lands

---

## Purpose

Purity Audit v1 fixed the structural violations — pipeline bypasses, the
missing Ratchet, Cortex governance. This sprint fixes the observability and
fidelity violations. These are the things a reviewer comparing the code to
the papers will notice:

"The paper says every trace is auditable. But the telemetry buries routing
data in an unstructured dict."

"The paper says model-agnostic. But the model IDs are hardcoded in Python."

"The paper says Red zone requires explicit approval with context. But the
code calls the same one-thumb function as Yellow zone."

None of these break the system. All of them undermine the claim. This sprint
closes the gap between what the papers assert and what the code demonstrates.


## The Six Violations

**MEDIUM — Directly observable against the papers:**

**Violation 4: Telemetry schema buries routing data.** The Pattern Release 1.3
specifies a flat telemetry entry: `{"ts":..., "intent":"propose_skill",
"tier":2, "zone":"yellow", "confidence":0.78, "cost_usd":0.012,
"human_feedback":"approved"}`. The current `TelemetryEvent` dataclass has
six fields: id, timestamp, source, raw_transcript, zone_context, inferred.
All routing metadata (intent, tier, confidence, cost) gets stuffed into the
`inferred` dict as unstructured data. An auditor can't run `grep` on the
telemetry log for Tier 2 calls. The Cortex has to parse nested dicts to
find routing signals. The Ratchet analysis (Lens 4) is harder than it needs
to be. Fix: promote intent, tier, confidence, and cost_usd to first-class
optional fields on TelemetryEvent.

**Violation 5: Model IDs hardcoded in Python.** `llm_client.py` lines 31-53
hardcode `claude-3-haiku-20240307`, `claude-3-5-sonnet-20241022`, and
`claude-3-opus-20240229` — model strings from 2024. This violates Invariant
#2 (Config Over Code) and the cognitive agnosticism principle. The operator
should be able to swap models by editing a config file. The Ratchet's
"capability propagation" thesis assumes model upgrades are config changes,
not code deployments. Fix: move tier-to-model mapping and pricing to
`config/models.yaml`.

**Violation 8: Red zone uses Yellow zone UX.** `pipeline.py` line 337 calls
`confirm_yellow_zone()` for red zone actions, with a `[RED ZONE]` text
prefix as the only differentiation. The Pattern Release 1.3 defines Red as
"explicit approval with full context review." `ux.py` already has
`confirm_red_zone_with_context()` — it just isn't wired. Fix: one function
call change in `_run_approval()`.


**LOW-MEDIUM — Defensive hardening:**

**Violation 6: Handler registry is imperative.** `dispatcher.py` registers
handlers in a Python dict. Adding a handler requires code changes. This
tension is partially mitigated by the Pit Crew — generated skills route
through `skill_executor`, which IS config-driven. The core handler set
(status_display, content_engine, pit_crew, etc.) is effectively the
"built-in instruction set" of the engine. The pragmatic fix is NOT to
build a dynamic plugin loader (overengineering). It's to document the
handler contract explicitly and ensure the registration pattern is
consistent and discoverable. Scope: documentation and a consistency pass,
not a refactor.

**Violation 9: `run_pipeline_with_mcp()` skips exception handling.**
Lines 762-798 of `pipeline.py` call the five stage methods directly without
the `try/except` wrapper that `InvariantPipeline.run()` provides. A crash
in this path produces no telemetry — a ghost failure violating Invariant #5.
Fix: wrap in the same exception handler, or delegate to `self.run()`.

**Violation 10: Standing context exception silently swallowed.**
`config_loader.py` line ~62 wraps standing context loading in
`except Exception: pass`. If compilation fails to load standing context,
the LLM gets no context and no one knows. Fix: log a telemetry event on
failure. Keep the `pass` (it IS enrichment, not critical path) but surface
the failure for debugging.


---

## Domain Contract

**Applicable contract:** Autonomaton Architect (Anti-Code-Party Protocol)
**Contract version:** 1.0
**Additional requirements:** Config over code. No new imperative patterns.

---

## What Success Looks Like

After this sprint:

1. **Telemetry is flat and grep-able.** An auditor can run
   `grep '"tier":2' events.jsonl` and get every Tier 2 call. Intent,
   tier, confidence, and cost are first-class fields. The `inferred` dict
   still exists for extensible metadata, but the routing decision is
   reconstructable from top-level fields alone.

2. **Model config is declarative.** `config/models.yaml` defines the
   tier-to-model mapping and pricing. The operator can swap
   `claude-3-haiku-20240307` for `claude-3-5-haiku-20250414` by editing
   one line in a YAML file. No code deployment. The cognitive agnosticism
   claim is provable.

3. **Red zone feels different.** Red zone approval shows full context with
   the persona explaining what the system wants to do and why it needs
   explicit permission. Yellow zone stays one-thumb. The zone model isn't
   just classification — it's experienced as different governance levels.

4. **No ghost failures.** `run_pipeline_with_mcp()` catches exceptions and
   logs to telemetry. Standing context failures log to telemetry instead of
   silently passing.

5. **Handler contract is documented.** CLAUDE.md includes the handler
   interface contract so new handlers follow a consistent pattern.

---

## Epic Structure

### Epic A: Flat Telemetry Schema
Promote intent, tier, confidence, cost_usd to first-class optional fields.
Update all call sites. Update schema validation. Update existing tests.

### Epic B: Externalize Model Config
Create `models.yaml`. Update `llm_client.py` to read from config.
Add profile isolation (both profiles get the file).

### Epic C: Zone UX + Defensive Hardening
Wire red zone to `confirm_red_zone_with_context()`. Fix
`run_pipeline_with_mcp()` exception handling. Add standing context
failure telemetry. Document handler contract.

### Epic D: Test Suite
New tests verifying flat telemetry fields, model config loading from
YAML, red zone UX differentiation, and MCP pipeline exception handling.

---

## Sequencing & Gates

```
Epic A (Flat Telemetry) ────→ GATE: Telemetry events have first-class routing fields
        │
Epic B (Model Config) ─────→ GATE: llm_client reads from models.yaml, not hardcoded
        │
Epic C (Zone UX + Defense) ─→ GATE: Red zone calls confirm_red_zone_with_context;
        │                           run_pipeline_with_mcp has exception handling
        │
Epic D (Tests) ─────────────→ GATE: All new + existing tests pass
```

Epics A, B, and C are independent — they touch different files and can
theoretically be done in any order. Epic D runs last.

---

## Files Touched

| File | Epic | Change Type |
|------|------|-------------|
| `engine/telemetry.py` | A | Add optional fields to TelemetryEvent |
| `engine/pipeline.py` | A, C | Update telemetry calls; fix red zone UX; fix MCP exception handling |
| `engine/cognitive_router.py` | A | Update telemetry calls with flat fields |
| `engine/llm_client.py` | A, B | Update telemetry calls; read model config from YAML |
| `engine/cortex.py` | A | Update telemetry calls with flat fields |
| `engine/dispatcher.py` | A | Update telemetry calls with flat fields |
| `engine/config_loader.py` | C | Add telemetry on standing context failure |
| `engine/compiler.py` | A | Update any telemetry calls |
| `profiles/*/config/models.yaml` | B | New file — tier-to-model mapping |
| `CLAUDE.md` | C | Document handler contract |
| `tests/test_purity_v2.py` | D | New test file |
| `tests/test_telemetry_schema.py` | A | Update existing tests for new fields |
