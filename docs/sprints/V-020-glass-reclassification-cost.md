# Sprint: V-020 — Glass Telemetry Truth (Reclassification Cost)

> *The telemetry already has the data. The renderer already reads the event. We stopped one field short.*

**Priority:** HIGH — Glass lies about cost on LLM-reclassified interactions
**Complexity:** LOW — Three surgical edits, all within the existing Feed-First mechanism
**Net line delta:** +15 (enriching existing structures, no new functions)
**Session discipline:** ONE fix. ONE commit. No feature additions.

---

## The Problem

When the operator consents to LLM classification via Kaizen Option 1, Glass renders:

```
│ 2 Recognition intent:unknown → explain_system T1 keyword $0.00
```

The intent arrow is correct (`unknown → explain_system`). Everything else is a lie:
- **T1** — the LLM ran at Tier 2
- **keyword** — the method was LLM classification, not keyword matching
- **$0.00** — an LLM call was made; the actual cost was ~$0.003

An auditor reading this trace concludes the interaction was free. The API bill says otherwise.

---

## Why This Happened

The architecture is working exactly as designed — the bug is that we didn't finish feeding it.

**Stage 2 (Recognition)** runs first. The Cognitive Router returns `unknown, tier:1, method:keyword`. The recognition telemetry event is logged with these values. This is correct — Stage 2 DID return unknown via keyword matching at zero cost.

**Stage 4 (Approval)** runs later. The Kaizen flow fires. The operator consents. `_kaizen_llm_classify()` calls the LLM, gets back `explain_system` with confidence, and calls `_apply_routing_result()` which updates `self.context.entities["routing"]` with:
- `tier: 2`
- `confidence: <LLM confidence>`
- `llm_metadata: {"source": "llm_classify", "classification_confidence": <conf>}`

Then `_log_approval_trace()` fires. It reads `routing_info = self.context.entities.get("routing", {})` — which NOW contains the RECLASSIFIED routing metadata from the LLM. The data is right there. But `_log_approval_trace()` only writes `resolved_intent` to the `inferred` dict. It discards the rest.

**Glass** reads the `approval_kaizen` event, extracts `resolved_intent`, passes it to the recognition renderer for the arrow display. But Glass has no reclassified tier/method/cost because the event doesn't carry them.

**The gap is one step wide.** The data exists in `routing_info` when `_log_approval_trace()` runs. The event carries `resolved_intent` but not `resolved_tier`, `resolved_method`, or `resolved_confidence`. Glass reads the event but can only render what the event contains.

---

## Why the Architecture Already Solves This

This is not a Glass rendering problem. This is a telemetry completeness problem. The architecture's Feed-First principle means Glass doesn't compute anything — it reads telemetry and renders. Fix the telemetry, Glass renders the truth. That's the entire point.

**White Paper Part III §4 (Feed-First Telemetry):** "Every interaction generates structured telemetry as its primary output. This is not logging bolted onto the side. It is the mechanism through which the system learns, the Skill Flywheel turns, and the Cognitive Router improves."

The telemetry event is incomplete. Glass is faithfully rendering an incomplete event. The fix is in the event emission — where the architecture says it should be.

**White Paper Part V (Transparency as Architecture):** "Feed-first telemetry means every interaction generates structured metadata as the mechanism the system uses to learn. The audit trail isn't something you add. It's something the system produces as a byproduct of operating."

If the audit trail says $0.00 for an interaction that cost $0.003, the audit trail is wrong. Not because someone failed to instrument it — but because the telemetry event stopped one field short of complete.

**TCP/IP Paper §III (Hourglass Invariant):** "Each stage produces a structured trace." The Stage 4 trace for a reclassification should carry the complete reclassified routing metadata — not just the intent, but the tier, method, confidence, and cost that changed. The trace is incomplete.

---

## The Fix — Three Atomic Changes

All three changes follow the same pattern that V-010 already established for `resolved_intent`. We're extending the existing mechanism, not inventing a new one.

### Change 1: Enrich `approval_kaizen` telemetry event with reclassified routing metadata

**File:** `engine/pipeline.py`, inside `_log_approval_trace()` (~line 405)

**Current code (the V-010 block):**
```python
        # V-010: Include resolved_intent so Glass renders the arrow
        if kaizen_reclassified:
            inferred["resolved_intent"] = self.context.intent
```

**Replace with:**
```python
        # V-010 + V-020: Include full reclassified routing metadata so
        # Glass renders the truth — intent, tier, method, cost, confidence.
        # routing_info already contains the RECLASSIFIED values because
        # _apply_routing_result() updated context before this function runs.
        if kaizen_reclassified:
            inferred["resolved_intent"] = self.context.intent
            inferred["resolved_tier"] = routing_info.get("tier", 2)
            inferred["resolved_confidence"] = routing_info.get("confidence", 0.0)
            # Determine method from llm_metadata (same logic as Stage 2 trace)
            llm_meta = routing_info.get("llm_metadata", {})
            if llm_meta.get("classification_confidence") is not None:
                inferred["resolved_method"] = "llm"
            else:
                inferred["resolved_method"] = "keyword"
```

**Architectural justification:**

1. **Feed-First (White Paper Part III §4).** The telemetry event is the single source of truth. Glass, Cortex, the Flywheel, and the Ratchet all read from the same stream. If the event is incomplete, every downstream consumer sees an incomplete picture. Enriching the event fixes all consumers at once.

2. **The data is already in scope.** `routing_info` is read from `self.context.entities.get("routing", {})` at line ~365 of this function. `_apply_routing_result()` updated these values when the LLM classification succeeded. We are not computing anything new — we are passing data that already exists through a channel that already exists.

3. **Same pattern as V-010.** `resolved_intent` was added by V-010 using exactly this mechanism. V-020 extends it with `resolved_tier`, `resolved_confidence`, and `resolved_method`. Same event, same `inferred` dict, same `if kaizen_reclassified` guard.

4. **Method determination uses the same logic as Stage 2.** The recognition trace at line ~280 determines method with: `"llm" if llm_metadata.classification_confidence is not None else "keyword"`. The reclassification trace uses the same test. One rule, two locations, same result.

### Change 2: Extract reclassified metadata in Glass dispatcher

**File:** `engine/glass.py`, inside `display_glass_from_telemetry()` (~line 180)

**Current code:**
```python
    # V-010: Check if Kaizen reclassified the intent
    reclassified_intent = None
    for event in events:
        inf = event.get("inferred", {})
        if inf.get("stage") == "approval_kaizen" and inf.get("resolved_intent"):
            reclassified_intent = inf["resolved_intent"]
            break
```

**Replace with:**
```python
    # V-010 + V-020: Extract full reclassification metadata from approval_kaizen event.
    # When Kaizen reclassifies, the approval event carries the FINAL routing truth:
    # resolved_intent, resolved_tier, resolved_method, resolved_confidence.
    # Glass renders these on the recognition line so the trace shows what actually happened.
    reclassified_intent = None
    reclassified_meta = {}
    for event in events:
        inf = event.get("inferred", {})
        if inf.get("stage") == "approval_kaizen" and inf.get("resolved_intent"):
            reclassified_intent = inf["resolved_intent"]
            reclassified_meta = {
                "tier": inf.get("resolved_tier"),
                "method": inf.get("resolved_method"),
                "confidence": inf.get("resolved_confidence"),
            }
            break
```

Then update the render loop call (~line 197):

**Current:**
```python
        _render_stage_from_event(lines, event, stage, level, reclassified_intent)
```

**Replace with:**
```python
        _render_stage_from_event(lines, event, stage, level,
                                 reclassified_intent, reclassified_meta)
```

**Architectural justification:**

1. **Glass reads telemetry, not context (White Paper Part V).** Glass never touches PipelineContext. It reads telemetry events. The reclassified metadata was just added to the `approval_kaizen` event (Change 1). Glass extracts it from the same event, same loop, same `if` guard it already uses for `resolved_intent`.

2. **No new queries.** This is not a second telemetry read. It's extracting more fields from the same event Glass already reads. Zero additional I/O.

3. **The dict stays empty when no reclassification happened.** `reclassified_meta` defaults to `{}`. The renderer checks for presence. Normal keyword/cache flows are unaffected.

### Change 3: Render reclassified tier/method/cost on the recognition line

**File:** `engine/glass.py`, inside `_render_stage_from_event()` (~line 86)

**Update function signature:**
```python
def _render_stage_from_event(lines: list, event: dict,
                              stage: str, level: str,
                              reclassified_intent: str = None,
                              reclassified_meta: dict = None) -> None:
```

**Replace the recognition rendering block (lines ~100–120):**

Current:
```python
    elif stage == "recognition":
        intent = event.get("intent", "unknown")
        tier = event.get("tier", 0)
        conf = event.get("confidence", 0.0)
        method = inf.get("method", "unknown")
        is_cache = method == "cache"
        cost = "$0.00" if tier < 2 or is_cache else "~$0.003"
        cache_marker = f" {_c.GREEN}✓{_c.RESET}" if is_cache else ""
        # V-010: Show reclassification arrow if Kaizen changed the intent
        if reclassified_intent and reclassified_intent != intent:
            intent_display = f"{intent} {_c.DIM}→{_c.RESET} {reclassified_intent}"
        else:
            intent_display = intent
        lines.append(
            f"  {_c.DIM}│{_c.RESET} {_c.CYAN}2{_c.RESET} Recognition "
            f"{_c.DIM}intent:{_c.RESET}{intent_display} "
            f"{_c.DIM}T{tier}{_c.RESET} {method}{cache_marker} "
            f"{_c.DIM}{cost}{_c.RESET}")
        if level in ("medium", "full") and conf > 0:
            lines.append(
                f"  {_c.DIM}│{_c.RESET}             "
                f"{_c.DIM}confidence:{_c.RESET} {conf:.0%}")
```

Replace with:
```python
    elif stage == "recognition":
        intent = event.get("intent", "unknown")
        tier = event.get("tier", 0)
        conf = event.get("confidence", 0.0)
        method = inf.get("method", "unknown")

        # V-020: When Kaizen reclassified, use the FINAL routing truth
        # from the approval_kaizen event — not the original Stage 2 values.
        # The recognition line should show what the pipeline ACTUALLY did,
        # not what Stage 2 initially returned before Kaizen intervened.
        rm = reclassified_meta or {}
        if reclassified_intent and reclassified_intent != intent:
            intent_display = f"{intent} {_c.DIM}→{_c.RESET} {reclassified_intent}"
            tier = rm.get("tier") or tier
            method = rm.get("method") or method
            conf = rm.get("confidence") or conf
        else:
            intent_display = intent

        is_cache = method == "cache"
        cost = "$0.00" if tier < 2 or is_cache else "~$0.003"
        cache_marker = f" {_c.GREEN}✓{_c.RESET}" if is_cache else ""

        lines.append(
            f"  {_c.DIM}│{_c.RESET} {_c.CYAN}2{_c.RESET} Recognition "
            f"{_c.DIM}intent:{_c.RESET}{intent_display} "
            f"{_c.DIM}T{tier}{_c.RESET} {method}{cache_marker} "
            f"{_c.DIM}{cost}{_c.RESET}")
        if level in ("medium", "full") and conf > 0:
            lines.append(
                f"  {_c.DIM}│{_c.RESET}             "
                f"{_c.DIM}confidence:{_c.RESET} {conf:.0%}")
```

**Architectural justification:**

1. **Glass renders telemetry truth (White Paper Part V).** The recognition line must show what the pipeline ACTUALLY did. When Kaizen reclassified, the pipeline used the LLM at Tier 2 — that's the truth. Showing the original Stage 2 result after reclassification is showing a snapshot that was superseded. The override only fires when `reclassified_intent` is present AND differs from the original intent — normal keyword/cache flows are untouched.

2. **Cost must be auditable (White Paper Part III §4).** "The telemetry serves triple duty: learning, observability, and compliance." If an auditor reads `$0.00` for an interaction where the LLM was called, the compliance trail is wrong. The cost determination logic (`"$0.00" if tier < 2 or is_cache else "~$0.003"`) is unchanged — it just reads from the correct tier value now.

3. **The fallback preserves backward compatibility.** `rm.get("tier") or tier` means: use the reclassified tier if present, otherwise fall back to the original. Old telemetry events without `resolved_tier` (from before V-020) render exactly as before. No migration needed.

4. **Confidence shows the LLM's confidence, not 0%.** When `reclassified_meta` carries the LLM confidence, the confidence line shows the actual classification confidence (e.g., 85%) instead of the original Stage 2 confidence of 0%. This is critical for the Ratchet narrative — the operator needs to see that the LLM was confident enough to pass the quality gate.

---

## Files to Touch

| File | Action | Lines Changed |
|---|---|---|
| `engine/pipeline.py` (`_log_approval_trace`) | Add `resolved_tier`, `resolved_method`, `resolved_confidence` to `inferred` dict | +7 |
| `engine/glass.py` (`display_glass_from_telemetry`) | Extract `reclassified_meta` from same event already being read | +6 net |
| `engine/glass.py` (`_render_stage_from_event`) | Accept `reclassified_meta`, override tier/method/conf when present | +5 net, restructure |

**Net effect:** ~+15 lines enriching existing structures. No new functions. No new files. No new dependencies.

---

## What NOT to Touch

- **`pipeline.py` `_run_recognition()`** — The Stage 2 telemetry event is correct. It logged what Stage 2 did. The fix is in Stage 4's event, not Stage 2's.
- **`telemetry.py`** — The telemetry schema doesn't need changes. The `inferred` dict is schemaless by design — it accepts whatever the stage provides.
- **`cognitive_router.py`** — Pure lookup. No Glass awareness.
- **`ux.py`** — Display functions. No telemetry awareness.
- **Test suite** — Behavioral change is Glass-only (visual rendering). Existing telemetry tests validate event structure. If any test asserts specific Glass output for reclassified intents, update the expected tier/method/cost.

---

## Expected Result

After V-020, Smoke Test 3 (LLM classification with consent) renders:

```
│ 2 Recognition intent:unknown → explain_system T2 llm ~$0.003
│             confidence: 85%
```

Instead of:

```
│ 2 Recognition intent:unknown → explain_system T1 keyword $0.00
```

The arrow (V-010) was the intent truth. V-020 completes the picture: tier truth, method truth, cost truth, confidence truth. Glass now tells the full story of what the pipeline actually did.

---

## Acceptance Tests

### Structural Tests

1. In `_log_approval_trace()`: when `kaizen_reclassified`, the `inferred` dict contains `resolved_intent`, `resolved_tier`, `resolved_method`, `resolved_confidence`
2. In `display_glass_from_telemetry()`: `reclassified_meta` is extracted from the same event as `reclassified_intent`
3. In `_render_stage_from_event()`: function signature accepts `reclassified_meta: dict = None`
4. In recognition rendering: tier/method/conf are overridden ONLY when `reclassified_intent` is present and differs from original

### Functional Tests

5. `pytest` → all 234 tests pass
6. **Smoke Test 1** (`hello`): Glass shows `T1 keyword $0.00` — UNCHANGED (no reclassification happened)
7. **Smoke Test 2** (unknown → Option 2): Glass shows `intent:unknown T1 keyword $0.00` — UNCHANGED (no LLM called)
8. **Smoke Test 3** (unknown → Option 1 → LLM classify): Glass shows `intent:unknown → explain_system T2 llm ~$0.003` with LLM confidence — **FIXED**
9. **Smoke Test 4** (Ratchet cache hit): Glass shows `T0 cache ✓ $0.00` — UNCHANGED (cache path, no reclassification)
10. **Smoke Test 3a** (garbage → Option 1 → rejected): Glass should show `T1 keyword $0.00` for the original recognition, then the fallback fires — no reclassification arrow, no override

### Audit Test

11. Run Smoke Test 3. Type `show telemetry`. The `approval_kaizen` event contains `resolved_intent`, `resolved_tier`, `resolved_method`, `resolved_confidence`. An auditor reading the raw telemetry sees the complete reclassification with cost attribution. Glass and telemetry agree.

---

## Anti-Requirements

- Do NOT modify the Stage 2 recognition event. It correctly records what Stage 2 did. The reclassification happened in Stage 4 — that's where the data belongs.
- Do NOT add a new telemetry event for reclassification. The `approval_kaizen` event already exists for this purpose (V-010). Enrich it — don't duplicate it.
- Do NOT compute cost in Glass. Glass renders telemetry. The cost derivation (`"$0.00" if tier < 2 else "~$0.003"`) is a rendering rule, not a computation. It reads tier from telemetry and formats. That's correct. The tier just needs to be the right tier.
- Do NOT change the cost display format. `$0.00` / `~$0.003` is the established vocabulary. The fix is the tier value feeding the existing format logic, not the format itself.

---

## Spec-to-Change Traceability

| Change | White Paper Section | TCP/IP Paper Section | Principle |
|---|---|---|---|
| Enrich `approval_kaizen` event | Part III §4: Feed-First Telemetry — "every interaction generates structured telemetry as its primary output" | §III: Hourglass — "each stage produces a structured trace" | Telemetry completeness |
| Extract reclassified metadata in Glass | Part V: Transparency as Architecture — "the audit trail isn't something you add" | §III: End-to-End — Glass reads from the same stream as every other consumer | Feed-First rendering |
| Override tier/method/cost on recognition line | Part V: "No silent degradation" / Part III §5: "No confident output from an uncertain pipeline" | §VI: Governance — "every interaction... audit logs on demand" | Telemetry truth |

---

## The Architectural Lesson

This bug proves the Feed-First design is correct. Glass doesn't compute. Glass doesn't infer. Glass reads telemetry and renders. When the telemetry is complete, Glass tells the truth. When the telemetry is incomplete, Glass tells an incomplete story.

The fix is not in the renderer. The fix is in the telemetry emission. Enrich the event, and every downstream consumer — Glass, Cortex, the Flywheel, a future compliance dashboard — gets the complete picture for free. That's what Feed-First means. That's the architecture doing the work.

---

## Commit Message

`V-020-glass-reclassification-cost`

---

*Sprint authored: 2026-03-23*
*Audit basis: V-019 commit f25d59d*
*Spec reviewed against: Pattern Release Draft 1.3, TCP/IP Paper Working Draft*
