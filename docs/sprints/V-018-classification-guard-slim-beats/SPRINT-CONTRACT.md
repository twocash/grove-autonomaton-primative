# Sprint Contract: V-018 — Classification Confidence Gate

**Gate Decision: READY FOR EXECUTION**

**Author:** Claude Opus 4.6 (PM Review)
**Date:** 2026-03-23
**Severity:** CRITICAL (cache poisoning via Jidoka bypass)
**Depends On:** V-017 (committed: 4a83693)
**Supersedes:** First draft of V-018 (which proposed a hack, not architecture)

---

## Why This Sprint Exists

An operator typed `1`. Jidoka fired — correctly. The system was uncertain.
The operator consented to LLM classification. The LLM returned
`general_chat` at ~0.3 confidence. The system treated this as a
successful classification, overrode Jidoka's uncertainty determination,
routed to the general_chat handler, sent `"1"` to the LLM as a
conversation prompt, got nonsense back, and cached the garbage
classification in the Ratchet forever.

**The bug is not "missing confidence threshold." The bug is that the LLM
classification overrides Jidoka even when it doesn't resolve the
uncertainty.**

Jidoka stopped the line because the system was uncertain. The LLM's job
was to resolve that uncertainty. A 0.3 confidence classification doesn't
resolve anything. Jidoka's assessment was correct. The system should have
stayed stopped.

---

## The Architectural Fix

The architecture already has every mechanism needed. No new patterns. No
new guard types. The fix uses three things that already exist:

### 1. The Fallback Path in `_kaizen_llm_classify()`

Lines ~690-705 of pipeline.py already handle "LLM classification didn't
work":

```python
# LLM failed — offer fallback
fallback_options = {
    "1": "Answer from what you already know (free)",
    "2": "Show me what you can help with (free)",
    "3": "I'll rephrase",
}
fallback_choice = ask_jidoka(
    context_message="The LLM classification didn't return a confident result.",
    options=fallback_options
)
```

This fires today when the LLM throws an exception or returns invalid
JSON. It should ALSO fire when confidence is below threshold. The LLM
returned something, but it didn't resolve the uncertainty. Jidoka's
original determination stands. The system stays stopped.

**The fix:** Change the acceptance condition from "intent is valid" to
"intent is valid AND confidence meets threshold":

```python
# CURRENT (line ~660):
if classified_intent in valid_intents:

# FIX:
min_conf = config.get("classification", {}).get("min_confidence", 0.6)
if classified_intent in valid_intents and confidence >= min_conf:
```

When confidence is below threshold, the code falls through to the
EXISTING fallback path. No new mechanism. The fallback already says the
right thing: "The LLM classification didn't return a confident result."
The operator gets the same three options they'd get if the LLM had
crashed. Because from Jidoka's perspective, the outcome is the same: the
uncertainty was not resolved.

**Config Over Code:** The threshold lives in kaizen.yaml:

```yaml
classification:
  min_confidence: 0.6
```

**Note on config access:** `_kaizen_llm_classify()` doesn't currently
have the kaizen config loaded. Call `self._load_kaizen_config()` at the
top of the method. One line. The method is already Stage 4 infrastructure
— loading a Stage 4 config file is architecturally appropriate.

### 2. The Ratchet's Existing Guard Set

`_write_to_pattern_cache()` already guards against caching bad
classifications: tier < 2, not approved, not executed, red zone, already
cached. If the upstream fix works correctly, a low-confidence
classification never calls `_apply_routing_result()`, never sets
`approved = True`, and never executes. The Ratchet never sees it.

**Defense-in-depth:** Add the confidence check to the Ratchet guards too.
If a future code path somehow gets a low-confidence classification past
the upstream gate, the Ratchet still won't cache it. Same pattern as
the existing guards — same place, same style:

```python
# After existing guards in _write_to_pattern_cache():
confidence = routing_info.get("confidence", 0.0)
config = self._load_kaizen_config()
min_conf = config.get("classification", {}).get("min_confidence", 0.6)
if confidence < min_conf:
    return  # Don't cache low-confidence classifications
```

### 3. What This Means Architecturally

The white paper (Part II) says: "Jidoka transforms a machine from a
blind, repetitive engine into an active partner in quality control — one
that has the authority to stop the world the moment it needs human
intuition."

Before this fix: Jidoka stops the world, but then the LLM overrides
Jidoka with a garbage classification. Jidoka has the authority to stop
but not the authority to STAY stopped.

After this fix: Jidoka stops the world. The LLM tries to resolve the
uncertainty. If the LLM can't resolve it confidently, Jidoka's stop
holds. The system stays stopped until the uncertainty is actually
resolved. That's the discipline working as designed.

**This is not a new guardrail. This is the existing guardrail being
respected.**

---

## Also In This Sprint: Three-Beat Slim

Uncommitted changes from the PM review session are in the working tree.
These replace FIGlet walls with single-line headers and add timing
between beats. The executor must verify and include these.

### Uncommitted File State

**engine/ux.py:**
- `import time` added
- FIGlet banner rendering replaced with slim single-line headers
- Config fields changed: `header` and `role` (not `banner` and `label`)
- `sys.stdout.flush()` + `time.sleep(beat_delay)` between beats
- Legacy fallback preserved for non-Kaizen callers

**profiles/reference/config/kaizen.yaml:**
- FIGlet `banner` replaced with `header` ("JIDOKA", "ANDON", "KAIZEN")
- `label` replaced with `role` ("The watchman detected something.", etc.)
- `bar` changed to single char for dynamic-width rendering
- `timing.beat_delay: 0.8` added
- Options/prompt structure unchanged

### Target Terminal Experience

```
  ▰ JIDOKA ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  The watchman detected something.
  No keyword match. No cache hit. Intent: unknown
  Confidence: 0%  |  Cost: $0.00
                                              [0.8s pause]
  ▰ ANDON ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  The line is stopped.
                                              [0.8s pause]
  ▰ KAIZEN ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  The improvement proposal.

  [prompt and options]
```

---

## Execution Sequence

1. Read uncommitted working tree state (ux.py, kaizen.yaml) — verify
   slim header rendering is correct
2. Add `classification.min_confidence: 0.6` to kaizen.yaml (merge with
   existing uncommitted changes)
3. In `_kaizen_llm_classify()`: load config, add confidence check to the
   existing acceptance condition. Low confidence falls through to the
   EXISTING fallback path. No new code paths.
4. In `_write_to_pattern_cache()`: add confidence guard after existing
   guards. Same pattern. Same place.
5. Run pytest — all tests pass
6. Clear pattern cache (remove any poisoned test entries)
7. Manual smoke test: type `1`, select LLM classify, verify fallback
   fires instead of garbage response
8. Manual smoke test: type real question, verify classification +
   Ratchet work normally
9. Manual smoke test: verify slim three-beat display with timing
10. Commit

---

## Acceptance Tests

```bash
# 1. Tests pass
python -m pytest

# 2. Garbage rejected — Jidoka holds
python autonomaton.py --profile reference
# Type: 1
# Kaizen fires -> select option 1 (LLM classify)
# EXPECTED: "The LLM classification didn't return a confident result."
#           (existing fallback prompt, not a new message)
# NOT EXPECTED: "Not sure what you're looking for with '1'"

# 3. Cache clean
# Type: show cache
# EXPECTED: No entry for "1"

# 4. Real questions still work
# Type: How does the pipeline handle compliance?
# Kaizen fires -> select option 1
# EXPECTED: Confident classification, coherent response, Ratchet caches
# Type same question again
# EXPECTED: T0 cache hit

# 5. Slim beats render with timing
# EXPECTED: Three single-line headers, pauses between them
```

---

## Files to Touch

| File | Action |
|------|--------|
| `engine/ux.py` | VERIFY uncommitted slim rendering |
| `engine/pipeline.py` | MODIFY `_kaizen_llm_classify()` acceptance condition, ADD confidence guard to `_write_to_pattern_cache()` |
| `profiles/reference/config/kaizen.yaml` | VERIFY uncommitted slim format, ADD `classification.min_confidence` |
| `SMOKE-TEST.md` | UPDATE for slim headers, ADD garbage rejection test |

---

## Anti-Requirements

- Do NOT create new fallback paths — the existing one is correct
- Do NOT modify `_run_recognition()` or Glass
- Do NOT add new functions
- Do NOT modify keystroke capture or dispatch logic
- Do NOT modify tests unless threshold changes expectations

---

## Commit

```
V-018-classification-confidence-gate
```

---

## Quality Gate

1. Does a garbage input (`1`) trigger the EXISTING fallback path?
2. Is the confidence threshold in kaizen.yaml, not hardcoded?
3. Does a real question still classify and cache correctly?
4. Do the slim beats render with visible timing between them?
5. Does the blank_template profile still work?
6. Can you explain the fix as "Jidoka's determination holds until the
   LLM actually resolves the uncertainty" — without mentioning a
   threshold hack?

If #6 is no, the fix isn't architectural.

---

*The loom already stopped. The fix is: don't restart it until the
problem is actually resolved.*
