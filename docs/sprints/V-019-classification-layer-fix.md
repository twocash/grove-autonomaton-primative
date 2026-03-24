# Sprint: V-019 — Classification Confidence Layer Fix

> *Corrects V-018's layer violations. Every change justified against the published spec.*

**Priority:** HIGH — Layer boundary violation in the pipeline's thin waist
**Complexity:** LOW — Config relocation + 3 surgical code edits
**Net line delta:** NEGATIVE (removes redundant code)
**Session discipline:** ONE fix. ONE commit. No feature additions.

---

## The Problem

V-018 introduced a sound architectural concept (confidence gating on LLM classification) but implemented it with three layer violations that, left uncorrected, create cross-layer coupling in the pipeline's thin waist.

### Violation 1: Classification threshold lives in the wrong config file

**Current state:** `classification.min_confidence: 0.6` lives in `kaizen.yaml`.

**Why this is wrong:** The white paper Part III §1 (Declarative Behavior Governance) explicitly enumerates what lives in declarative config: "routing rules, prompt composition, **classification thresholds**, skill definitions, approval patterns." Classification thresholds are behavior governance — they belong to the Cognitive Router's config domain.

Kaizen is the *improvement response* — the proposal flow after Jidoka detects a problem. Classification confidence is a *quality detection* concern — it decides whether the LLM's classification meets the bar. These are architecturally distinct TPS concepts:

- **Jidoka** = quality awareness discipline (detects the problem)
- **Andon** = stop mechanism (fires the gate)
- **Kaizen** = improvement response (proposes the options)

A classification confidence threshold is Jidoka — quality awareness. Putting it in `kaizen.yaml` conflates the detection discipline with the response flow. This is exactly the terminology drift that the Architectural Compliance Roadmap (V-011) was created to prevent.

**The TCP/IP paper §III (Layered Independence):** "Each layer can evolve without disrupting the others." If kaizen.yaml is reorganized tomorrow — renamed sections, restructured options — the classification gate breaks. A layer boundary was crossed.

**Where it belongs:** `routing.config` already has a `router.matching` section that governs classification quality thresholds for keyword matching. It already has `router.matching.min_confidence: 0.7` for keyword matches. The LLM classification confidence threshold is the same architectural concern at a different tier. It belongs in the same config section.

### Violation 2: The Ratchet cache writer depends on Kaizen config

**Current state:** `_write_to_pattern_cache()` (pipeline.py ~line 880) calls `self._load_kaizen_config()` to read the min_confidence threshold. This means the Ratchet's post-execution cache-write logic has a runtime dependency on Kaizen configuration.

**Why this is wrong:** The Ratchet is a Stage 5 post-execution operation. Kaizen is a Stage 4 approval-flow mechanism. These are different pipeline stages with different responsibilities.

**TCP/IP paper §III (Layered Independence):** The Ratchet cache writer should not know that `kaizen.yaml` exists. Its job is to decide "should I cache this confirmed classification?" It should read from its own config domain — the `cache` section of `routing.config`, which already exists and already governs Ratchet behavior.

**The deeper issue:** This dependency is also *unnecessary*. The confidence value is already computed during classification and stored in `self.context.entities["routing"]["confidence"]`. And the classification gate in `_kaizen_llm_classify()` already rejected anything below threshold before execution could occur. The cache writer doesn't need a second threshold check at all.

### Violation 3: Redundant confidence check (dead code)

**Current state:** `_write_to_pattern_cache()` reads the confidence from routing info AND re-reads the threshold from kaizen config, then checks `if confidence < min_conf: return`.

**Why this is redundant:** Trace the control flow:

1. `_kaizen_llm_classify()` calls the LLM → gets confidence back
2. V-018's quality gate checks `confidence >= min_conf` → rejects if below threshold
3. If rejected → fallback prompt fires → pipeline never reaches execution
4. If accepted → routing result applied → pipeline proceeds through Stage 5
5. `_write_to_pattern_cache()` fires post-execution

**If execution happened, confidence already passed the gate.** The second check in `_write_to_pattern_cache()` can never trigger in the current architecture. It's dead code that:
- Creates a false dependency on kaizen.yaml
- Makes a CTO reading the Ratchet think the threshold could be different in two places
- Obscures the actual invariant: "if you reached cache-write, classification already passed"

**White Paper Part IX, Principle 1 (Extended Mind):** "Every design decision must reduce cognitive load, never add to it." Redundant guards in a reference implementation add cognitive load for the reader without adding safety for the operator.

---

## The Fix — Four Atomic Changes

### Change 1: Add `classification.min_confidence` to `routing.config`

**File:** `profiles/reference/config/routing.config`

**Action:** Add a `classification` subsection under `router` that governs LLM classification quality thresholds. This is the same architectural pattern already used for keyword matching (`router.matching.min_confidence`).

**Add after the `matching` section (after `word_boundary_min_length: 4`):**

```yaml

  # LLM classification quality gate (Jidoka).
  # When the operator consents to LLM classification (Kaizen option 1),
  # the LLM returns a confidence score. Classifications below this
  # threshold are rejected — the line stops, the fallback fires.
  # This prevents garbage classifications from reaching execution
  # or poisoning the Ratchet cache.
  classification:
    min_confidence: 0.6
```

**Architectural justification:** White Paper Part III §1 (Declarative Behavior Governance): "routing rules, prompt composition, classification thresholds" live in declarative config. `routing.config` is the Cognitive Router's brain. Classification confidence is a routing quality concern. This is where it lives.

**Secondary justification:** The `router` section now governs quality thresholds at BOTH tiers — keyword matching (`router.matching.min_confidence: 0.7`) and LLM classification (`router.classification.min_confidence: 0.6`). A reviewer reading `routing.config` sees the complete classification quality picture in one place.

### Change 2: Update `_kaizen_llm_classify()` to read from `routing.config`

**File:** `engine/pipeline.py`, inside `_kaizen_llm_classify()` (~line 658)

**Replace:**
```python
            # V-018: Classification quality gate — reject low-confidence classifications
            config = self._load_kaizen_config()
            min_conf = config.get("classification", {}).get("min_confidence", 0.6)
```

**With:**
```python
            # Classification quality gate (Jidoka): reject low-confidence LLM results
            # Threshold declared in routing.config → router.classification.min_confidence
            min_conf = router.config.get("router", {}).get("classification", {}).get("min_confidence", 0.6)
```

**Architectural justification:** The `router` object is already in scope (line ~612: `router = get_router()`). Its `.config` dict contains the parsed `routing.config`. Reading the threshold from the router's own config eliminates the cross-layer dependency on kaizen.yaml. No new file reads. No new imports. The router owns its own quality thresholds.

### Change 3: Remove the redundant confidence check from `_write_to_pattern_cache()`

**File:** `engine/pipeline.py`, inside `_write_to_pattern_cache()` (~line 880)

**Delete these lines entirely:**
```python
        # V-018: Don't cache low-confidence classifications (garbage doesn't compound)
        confidence = routing_info.get("confidence", 0.0)
        config = self._load_kaizen_config()
        min_conf = config.get("classification", {}).get("min_confidence", 0.6)
        if confidence < min_conf:
            return  # Jidoka: garbage doesn't compound
```

**Replace with a single comment explaining why no check is needed:**
```python
        # Classification quality gate already enforced in _kaizen_llm_classify().
        # If execution reached this point, confidence passed the threshold.
        # The Ratchet caches confirmed results — not re-validates them.
```

**Architectural justification:**

1. **Control flow guarantees it.** `_kaizen_llm_classify()` rejects low-confidence results before they reach execution. `_write_to_pattern_cache()` only fires post-execution. The check is unreachable.

2. **Layered Independence (TCP/IP Paper §III).** The Ratchet cache writer's job is to persist confirmed classifications. Quality enforcement belongs upstream in the classification gate. Each layer does its job; no layer re-does another's.

3. **Simplicity Principle (RFC 3439, TCP/IP Paper §III).** "Complexity is the primary mechanism that impedes efficient scaling." Dead code in the pipeline's thin waist is complexity that serves no purpose. A CTO reading this function should see cache logic, not redundant quality gates.

4. **Eliminates the kaizen.yaml dependency.** This was the only call to `_load_kaizen_config()` in `_write_to_pattern_cache()`. Removing it restores layer independence between the Ratchet and the Kaizen flow.

### Change 4: Remove `classification` section from `kaizen.yaml`

**File:** `profiles/reference/config/kaizen.yaml`

**Delete these lines:**
```yaml
# Classification quality gate
# LLM classifications below this confidence are rejected (Jidoka stops the line)
# and not cached by the Ratchet (garbage doesn't compound)
classification:
  min_confidence: 0.6
```

**Replace with a pointer comment:**
```yaml
# Classification quality thresholds live in routing.config
# (router.classification.min_confidence) — not here.
# Kaizen governs the improvement RESPONSE. Classification
# quality is a Cognitive Router concern (Jidoka, not Kaizen).
```

**Architectural justification:** Kaizen config should contain kaizen config — the improvement proposal UX: beat timing, header text, role descriptions, option labels, capability mappings. Classification quality thresholds are a different TPS concept (Jidoka) in a different architectural layer (Cognitive Router). Removing the misplaced section and leaving a pointer comment prevents future sessions from re-introducing the violation.

---

## Files to Touch

| File | Action | Lines Changed |
|---|---|---|
| `profiles/reference/config/routing.config` | Add `router.classification.min_confidence` section | +8 |
| `engine/pipeline.py` (`_kaizen_llm_classify`) | Read threshold from `router.config` instead of kaizen.yaml | ~0 net (replace 2 lines with 2 lines) |
| `engine/pipeline.py` (`_write_to_pattern_cache`) | Delete redundant confidence check + kaizen dependency | -5, +3 (comment) |
| `profiles/reference/config/kaizen.yaml` | Remove `classification` section, add pointer comment | -4, +4 |

**Net effect:** ~-2 lines of executable code, one eliminated cross-layer dependency, one eliminated dead code path, one config relocation.

---

## What NOT to Touch

- `ux.py` — The three-beat display is correctly implemented. No changes.
- `cognitive_router.py` — The router class already exposes `.config` dict. No changes needed.
- `_load_kaizen_config()` — Still used by `_handle_kaizen_proposal()` for its legitimate purpose (loading Kaizen UX config). Do not remove the method.
- `SMOKE-TEST.md` — Test 3a (garbage rejection) still works because the quality gate still exists; it just reads from a different config file. Test descriptions may reference "kaizen.yaml" for the threshold — update the specific line if so, but do NOT restructure the test.
- Test suite — The confidence gate behavior is unchanged. All 234 tests should pass without modification. If any test hardcodes a kaizen.yaml path for the classification threshold, update the path reference.

---

## Acceptance Tests

### Structural Tests (verify before running anything)

1. `grep -r "classification.*min_confidence" profiles/reference/config/kaizen.yaml` → **zero results**
2. `grep -r "_load_kaizen_config" engine/pipeline.py` → appears ONLY in `_handle_kaizen_proposal()`, NOT in `_write_to_pattern_cache()` or `_kaizen_llm_classify()`
3. `grep -r "classification.*min_confidence" profiles/reference/config/routing.config` → **one result** under `router.classification`
4. In `_write_to_pattern_cache()`: no reference to kaizen, no reference to `_load_kaizen_config`, no confidence threshold check

### Functional Tests

5. `pytest` → all 234 tests pass
6. Smoke Test 3a (type `"1"`, consent to LLM): garbage classification still rejected, fallback fires — behavior unchanged
7. Smoke Test 3 (type real question, consent to LLM): classification succeeds if confidence >= 0.6
8. Smoke Test 4 (repeat same question): Ratchet cache hit, T0, $0.00 — cache write still works
9. `show config` → reviewer sees `router.classification.min_confidence: 0.6` alongside `router.matching.min_confidence: 0.7` — complete quality picture in one file

### Architectural Audit

10. A reviewer reading `routing.config` sees ALL classification quality thresholds in one place (keyword + LLM)
11. A reviewer reading `kaizen.yaml` sees ONLY Kaizen UX config (beats, options, timing)
12. A reviewer reading `_write_to_pattern_cache()` sees ONLY cache logic — no quality gate, no config loading, no cross-layer dependency
13. A reviewer reading `_kaizen_llm_classify()` sees the quality gate reading from the router's own config — same source as keyword matching thresholds

---

## Anti-Requirements

- Do NOT add a new config file. The threshold belongs in `routing.config` where all other classification quality settings already live.
- Do NOT add a cache-specific confidence threshold. The Ratchet caches what passed the classification gate. One gate, one threshold, one location.
- Do NOT add defensive re-checks "just in case." If the control flow guarantees a condition, document the guarantee with a comment — don't add a redundant check. Redundant checks in a reference implementation teach bad architecture.
- Do NOT modify the three-beat UX. That's correct as-is.
- Do NOT modify `_load_kaizen_config()`. It's still needed by the Kaizen flow for its legitimate UX config purpose.

---

## Commit Message

`V-019-classification-layer-fix`

---

## Spec-to-Change Traceability

| Change | White Paper Section | TCP/IP Paper Section | Principle |
|---|---|---|---|
| Threshold → routing.config | Part III §1: "classification thresholds" in declarative config | §III: Hourglass — router is the thin waist | Declarative Behavior Governance |
| Read from router.config | Part III §1: engine reads config | §III: Layered Independence | Config Over Code |
| Remove cache confidence check | Part VI: "Gets smarter with use" (Ratchet caches confirmed results) | §III: Simplicity Principle (RFC 3439) | No dead code in thin waist |
| Remove kaizen.yaml section | Part III (Jidoka ≠ Kaizen distinction) | §III: Layered Independence | TPS terminology alignment |

---

*Sprint authored: 2026-03-23*
*Audit basis: V-018 commit a0b2cc5*
*Spec reviewed against: Pattern Release Draft 1.3, TCP/IP Paper Working Draft*
