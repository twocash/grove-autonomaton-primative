# SPRINT SPEC: Consent-Gated Classification

> *"Design is philosophy expressed through constraint."*
> Sprint Name: `consent-gated-classification-v1`
> Dependency: Executes AFTER ux-polish-v1
> Domain Contract: Autonomaton Architect

---

## The Violation

An LLM call is an action. It costs money. Every action goes through
the five-stage pipeline. Stage 4 (Approval) gates actions before
they execute.

The Cognitive Router calls `_escalate_to_llm()` INSIDE Stage 2
(Recognition). This is a pipeline bypass. Money is spent before
Approval can gate it. The operator is surprised by the bill. The
architecture says this cannot happen.

This is not a UX problem. This is an invariant violation. The
pipeline is the invariant. The pipeline governs all actions. An
LLM call is an action. Therefore the pipeline governs LLM calls.
The Cognitive Router does not get to bypass Stage 4 because it's
"just classification."

---

## The Correct Flow

Per the architecture — five stages, no exceptions:

**Stage 2 (Recognition):** Keywords match → done. Cache hits → done.
Both miss → return `unknown` with low confidence. Recognition
reports what it knows. It does not fix what it doesn't know.

**Stage 3 (Compilation):** Loads dock context. Even unknown intents
get context. The system has information to offer.

**Stage 4 (Approval):** Sees unknown intent. Kaizen proposes:

  "I don't recognize this yet. I can use the LLM to understand
  what you mean — costs fractions of a cent, and the Ratchet
  caches it so it's free next time. Or I can answer from what
  I already know."

  [1] Yes, use the LLM to classify this
  [2] Answer from local context (dock + config)
  [3] Here's what I can help with (config options)
  [4] I'll rephrase

Option 1: LLM fires. THROUGH the pipeline. Governed. Consented.
Visible in Glass. Ratchet caches it. Next time: T0, free.

Option 2: The dock-aware general_chat handler answers from whatever
Compilation assembled. No LLM for classification. The operator
gets an answer from local resources. Maybe it's thin. The Flywheel
notices and proposes upgrading the tier later.

Option 3: Standard clarification from clarification.yaml. Free.

Option 4: Operator rephrases. System learns nothing. That's fine.

---

## What Changes

### cognitive_router.py

**Remove** the automatic LLM escalation from `classify()`. Currently:

```
keyword miss → cache check → _escalate_to_llm() → if fails, return unknown
```

After:

```
keyword miss → cache check → return unknown
```

The `_escalate_to_llm()` method stays in the codebase. It moves
from "automatic" to "on-demand" — called only when the operator
consents through Stage 4.

### pipeline.py — _handle_clarification_jidoka()

**Rewrite** the Jidoka handler for unknown intents. Currently it
has Tier A (show LLM's guess — but the LLM already fired) and
Tier B (smart clarification — another LLM call). Both spend money
before consent.

After: a single Kaizen-style prompt with four options. Option 1
triggers the LLM classification through the pipeline. Options 2-4
are free.

When the operator picks Option 1:
1. Call `_escalate_to_llm()` with the original input
2. If it succeeds: update context with the classified intent,
   log "human_feedback=approved_classification" to telemetry,
   proceed to execution
3. Ratchet caches the classification (the existing write path)
4. Next time: T0 cache hit, no Jidoka, no LLM, no cost

### smart_clarification setting

**Remove** the `smart_clarification` config gate I added earlier.
It was a workaround for the wrong problem. The real fix is consent-
gated classification. Smart clarification (LLM-generated options)
can stay for production profiles where the operator has opted in —
but it fires ONLY after consent, not automatically.

---

## Also in Scope

### Cortex.py domain contamination

The audit found "Coach's ACCOUNTABILITY PARTNER", "tithing goals",
"First Tee donation", hardcoded goal categories. Move lens prompts
to profile config. Same pattern as entity_config.yaml.

### Missing ratchet routes

Add ratchet_intent_classify to reference and blank_template profiles.
The LLM classification still needs a pipeline route — it just fires
after consent instead of automatically.

### Test script dock.query fix

The test script calls `dock.query()` but the method is named
differently. Fix the test to use the correct API.

---

## The Demo After This Sprint

Operator: "Does this compete with OpenAI?"

Glass shows:
```
│ 1 Telemetry   id:abc123 src:operator_session
│ 2 Recognition intent:unknown T0 keyword $0.00
│             confidence: 0%
│ 3 Compilation Dock: 2 chunk(s)
│ 4 Approval    KAIZEN — classification proposal
```

Kaizen prompt:
  "I don't recognize this yet. I can use the LLM to understand
  what you mean — fractions of a cent, cached after. Or I can
  answer from the architecture docs I have loaded."

  [1] Use the LLM to classify
  [2] Answer from what you know
  [3] Show me what you can help with
  [4] I'll rephrase

Operator picks [2]. The dock-aware general_chat handler fires with
the unlock section and white paper as context. Gives an informed
answer about how the Autonomaton relates to model providers. $0.00.

OR: Operator picks [1]. Glass updates:
```
│ 4 Approval    APPROVED — LLM classification
│ 5 Execution   handler:general_chat [executed]
```

LLM classifies it as explain_system. Ratchet caches it.
Next time: T0 cache hit. No Jidoka. No LLM. No cost. Forever.

The operator consented. The cost was visible. The Ratchet made
it permanent. The architecture worked. No surprises.
