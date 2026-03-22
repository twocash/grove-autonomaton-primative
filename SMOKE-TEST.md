# Smoke Test: The Autonomaton OOBE
## Reference Profile — Architecture Demo Walkthrough

> *"Design is philosophy expressed through constraint."*
>
> This test script IS the out-of-box experience. Each test demonstrates
> an architectural claim from the Pattern Release. A CTO running this
> sequence sees every commitment in action — pipeline invariant, zone
> governance, consent-gated classification, the Ratchet, the Flywheel,
> and transparency by construction. In order. In under ten minutes.
>
> **The meta-point:** this system creates, runs, and validates its own
> tests. The Skill Flywheel observes interactions, detects patterns,
> and proposes improvements — including improvements to this test
> script. The test suite is not external to the architecture.
> It is a product of the architecture operating on itself.

---

## Launch

```
cd /d C:\GitHub\grove-autonomaton-primative
python autonomaton.py --profile reference
```

### Expected Startup

Clean banner. No LLM calls. No prompts. The system waits for the operator.

```
============================================================
  THE AUTONOMATON
  Profile: reference
============================================================
  Dock: X chunks from 2 sources
  Cortex: 0 pending Kaizen item(s)
  Glass Pipeline: ACTIVE
============================================================
  This is the naked engine. No domain. No context. No skills.
  Every pipeline stage will announce itself as it runs.
  Type anything to see the architecture in motion.
  Ready.
autonomaton>
```

**What this proves (Deck Slide 4 — The Pipeline):**
The pipeline doesn't fire until the operator acts. No eager loading,
no background LLM calls, no hidden initialization. The system comes
to the human; the human never has to come to the system.

**FAIL if:** LLM calls during startup. Any prompt before `autonomaton>`.
Glass rendering before operator input. Dock count is 0.

---

## Test 1: The Glass Pipeline — Five Stages in Sequence

**Demonstrates:** Pipeline invariant, keyword classification, Green zone auto-approve, feed-first telemetry

**Type:** `hello`

### Expected Glass

```
  │ GLASS PIPELINE
  │ 1 Telemetry   id:XXXXXXXX src:operator_session
  │ 2 Recognition intent:general_chat T1 keyword $0.00
  │               confidence: 100%
  │ 3 Compilation Skipped — conversational
  │ 4 Approval    GREEN auto-approve
  │ 5 Execution   handler:general_chat [executed]
```

### Expected Response

Brief greeting from Engine persona. Conversational, not robotic.

### Expected Tip

`Try something the system won't recognize to see what happens.`

### What This Proves

**Pipeline Invariant (Deck Slide 4):** All five stages fire in sequence.
One input, one traversal, five traces. The pipeline is the thin waist of
the cognitive hourglass — every interaction passes through it regardless
of complexity.

**Keyword Classification (Deck Slide 5):** `hello` matches a keyword in
`routing.config` at Tier 1. No LLM call. No external dependency. The
Cognitive Router is a pure config lookup.

**Green Zone (Deck Slide 6):** `general_chat` is declared Green in
`routing.config`. Stage 4 auto-approves. No operator prompt. The system
earned this autonomy through declaration, not assertion.

**Feed-First Telemetry (Deck Slide 8):** Every stage emitted a trace.
The `[LOGGED]` confirmation means the telemetry stream captured a
structured event. This is not logging bolted on — it is the mechanism
through which the system learns.

**FAIL if:** Glass missing any stage. Tier is not 1. Method is not
keyword. Approval is not GREEN auto-approve. Any LLM call fired.

---

## Test 2: The Andon Gate — Jidoka Stops the Line

**Demonstrates:** Digital Jidoka (quality awareness), Andon Gate (stop mechanism), Kaizen (improvement proposal), consent-gated compute

**Type:** `How does this handle regulatory compliance?`

No keyword match. The Cognitive Router returns `unknown`. The pipeline
reaches Stage 4 and the Andon Gate fires — the system stops the line
rather than returning a confident-sounding answer it can't back up.

### Expected: Andon Gate Fires

```
============================================================
ANDON GATE: Stopping the line for human input
============================================================
I don't recognize this from my current vocabulary.
I can use the LLM to learn what you mean - the Ratchet
will cache it so it's free next time.

  [1] Use the LLM to classify this (fractions of a cent, cached after)
  [2] Answer from what you already know (free)
  [3] Show me what you can help with (free)
  [4] I'll rephrase

Enter choice [1/2/3/4]:
```

### Choose Option 2: Local Context (Free Path)

**Press:** `2`

### Expected Response

Engine answers from dock context (the Autonomaton Pattern white paper
and the Unlock document). Should reference zones, audit trails,
declarative governance, or regulatory timeline. Informed but not
LLM-classified — the system used what it already knows.

### Expected Glass

```
  │ 2 Recognition intent:unknown T1 keyword $0.00
  │ 4 Approval    GREEN kaizen → local context
```

### What This Proves

**Digital Jidoka (Deck Slide 2 — Self-Identifying):** The system detected
its own uncertainty. It didn't hallucinate. It didn't guess. It stopped.
This is Toyoda's "andon cord" digitized — the machine has the authority
to stop the world when it needs human judgment.

**Kaizen Proposal (Deck Slide 2 — Self-Fixing):** The four options ARE
the Kaizen proposal. The system doesn't just stop — it proposes
improvement paths. Option 1 would teach the system a new classification.
Option 2 uses existing knowledge. Option 3 shows what it can do.
Option 4 lets the operator rephrase. Each option is a different
cost/capability trade-off, declared in `kaizen.yaml`.

**Consent-Gated Compute (Deck Slide 5 — The Cognitive Router):** The
system will not spend money without consent. Option 1 costs fractions
of a cent. Options 2-4 are free. The operator decides. This is the
sovereignty guardrail in action — the system proposes, the human
makes the call.

**Config Over Code:** The Andon Gate prompt text comes from `kaizen.yaml`.
The four options come from `kaizen.yaml`. The clarification submenu
(Option 3) comes from `clarification.yaml`. A non-technical reviewer
can read these files and understand what the system does when it's
uncertain — without reading a single line of Python.

**FAIL if:** No Andon Gate fires. Fewer than 4 options. LLM call fires
before consent. Glass shows a classified intent (should be `unknown`).

---

## Test 3: Consent to LLM — The Ratchet Primes

**Demonstrates:** LLM classification with consent, the Ratchet write path, Glass reclassification arrow

**Type:** `What about enterprise data residency requirements?`

No keyword match. Andon Gate fires again.

**Press:** `1` (Use the LLM to classify this)

### Expected: LLM Classifies Successfully

The LLM reads the operator's input against the route descriptions in
`routing.config` and returns a structured classification (likely
`explain_system`). The pipeline updates its context with the classified
intent and proceeds through Stage 5.

### Expected Glass (with V-003 reclassification arrow)

```
  │ 2 Recognition intent:unknown → explain_system T1 keyword $0.00
  │ 4 Approval    GREEN kaizen → LLM classify
  │ 5 Execution   handler:general_chat [executed]
```

**CRITICAL:** Stage 2 must show the arrow notation
`intent:unknown → explain_system` (or whatever the LLM classified it
as). This proves Glass reads the `resolved_intent` from the Kaizen
approval trace — the system is transparent about what changed and why.

### Expected Response

Informed answer about data residency using dock context. The LLM
classified the intent, the dock provided context, and the Engine
persona synthesized an answer.

### Expected Tip

`That used the LLM. Try the exact same phrase again.`

### What This Proves

**The Ratchet Primes (Deck Slide 9):** Behind the scenes,
`_write_to_pattern_cache()` just fired. The LLM classification
(`explain_system`) was cached in `pattern_cache.yaml` with the
operator's input hash. Next time this exact input appears, it
resolves at Tier 0 — cached, free, instant. The system got cheaper
because the operator used it.

**Transparency by Construction (Deck Slide 8):** Glass shows the
reclassification arrow. The operator sees what happened: the input
was initially unknown, then the LLM classified it. No hidden state
changes. The audit trail captures the full journey.

**FAIL if:** LLM error. No response. Glass shows `intent:unknown`
without the arrow. Glass shows `ratchet_intent_classify` as the
intent (cache poisoning — V-001 regression). Tip doesn't fire.

---

## Test 4: THE RATCHET — The System Got Cheaper

**Demonstrates:** Tier 0 pattern cache, the Reverse Tax, compounding economics

**Type the exact same thing:** `What about enterprise data residency requirements?`

### Expected: No Andon Gate. No Prompt. Instant.

The Ratchet cache resolves the input at Tier 0 before keyword matching
even runs. No LLM call. No consent prompt. Zero cost.

### Expected Glass

```
  │ 2 Recognition intent:explain_system T0 cache ✓ $0.00
  │               confidence: 75%
  │ 4 Approval    GREEN auto-approve
  │ 5 Execution   handler:general_chat [executed]
```

### Expected: THE RATCHET Announcement

```
  THE RATCHET: Classified by LLM last time → cache this time.
     Tier 0, $0.00. The system got cheaper because you used it.
```

### Expected Tip

`Type 'show cache' to see what the Ratchet stored.`

### What This Proves

**The Reverse Tax (Deck Slide 9):** Traditional cloud computing taxes
you for usage — the more you use, the more you pay. The Ratchet
inverts this. The LLM classified this input once (fractions of a cent).
Now it resolves for free. Forever. Every Tier 2 interaction that becomes
a Tier 0 cache hit is 100x cheaper, infinitely more private, zero
external dependency.

**Compounding Economics (Deck Slide 9):** Four things improved
simultaneously when this migrated from Tier 2 to Tier 0: cheaper
(free), more private (no external call), more sovereign (no API
dependency), more traceable (cached skill is maximally auditable).
These aren't trade-offs. They're co-benefits of the same event.

**FAIL if:** Andon Gate fires (cache miss). Glass shows T1 or T2.
Method is not `cache`. RATCHET announcement doesn't fire. Cost is
not $0.00.

---

## Test 5: Inspect the Cache — Transparency by Construction

**Demonstrates:** Declarative governance, inspectable intelligence, audit trail

**Type:** `show cache`

### Expected Output

Displays `pattern_cache.yaml`. Should show at least one entry from
Test 3 with:

```yaml
cache:
  [hash]:
    intent: explain_system        # NOT ratchet_intent_classify
    domain: system
    zone: green
    handler: general_chat
    confirmed_count: 1
    original_input: "What about enterprise data residency requirements?"
    confidence: [0.5-1.0]
```

### What This Proves

**Inspectable Intelligence (Deck Slide 7 — Skill Flywheel):** The
system's learned behaviors are not entombed in weights. They are
human-readable YAML files. A CTO can open this file, read what the
system learned, correct it if it's wrong, and delete it if it
shouldn't be there. The system's intelligence is a library with a
card catalog, not a black box with a confidence score.

**Declarative Governance (Deck Slide 8):** The cached classification
includes the zone (`green`), the handler (`general_chat`), and the
confidence score. An auditor can read this file and reconstruct
exactly what the system would do with this input — without running
the system.

**FAIL if:** Intent shows `ratchet_intent_classify` (V-001 regression).
No entry exists. Cache file is missing.

---

## Test 6: Inspect the Zones — Sovereignty as Schema

**Demonstrates:** Zone governance is a readable document, not a codebase walkthrough

**Type:** `show zones`

### Expected Output

Displays `zones.schema` contents — the Green/Yellow/Red governance
model with descriptions, examples, and Jidoka triggers.

### What This Proves

**Sovereignty Guardrails (Deck Slide 6):** When an auditor asks
"what can the agent do without human approval?" — you hand them
this file. Green zone actions execute autonomously. Yellow zone
actions require confirmation. Red zone actions require explicit
approval with full context. The boundaries are declared, not
hardcoded. The governance is the architecture.

**FAIL if:** File doesn't display. Zone definitions are missing.

---

## Test 7: Inspect the Telemetry — The Audit Trail

**Demonstrates:** Feed-first telemetry, audit trail as byproduct

**Type:** `show telemetry`

### Expected Output

Displays the last 20 entries from `telemetry.jsonl`. Each entry is
a structured JSON object with `id`, `source`, `intent`, `zone`,
`tier`, `confidence`, and `inferred` stage metadata.

### What This Proves

**Feed-First Telemetry (Deck Slide 8):** Every stage of every
interaction produced a structured trace. The telemetry stream
serves triple duty: learning (feeds the Skill Flywheel),
observability (surfaces system health), and compliance (produces
audit trails). You don't maintain three systems. You maintain one.

**Governance Comes Free (Deck Slide 8):** An auditor can reconstruct
any system decision from the telemetry alone. "Why did the system
route this to Tier 2?" — the trace shows the recognition stage,
the Andon Gate event, the operator's consent, and the execution
result. Every property regulators demand is a structural consequence
of how the system works.

**FAIL if:** Telemetry is empty. Entries lack structured fields.
Stage traces are missing for any test interaction.

---

## Test 8: The Flywheel Detects Patterns

**Demonstrates:** Skill Flywheel Stage 2 (DETECT), self-improvement claim

To properly trigger the Flywheel, we need 3+ occurrences of the same
pattern within the detection window. If you've run Tests 1-4, the
`general_chat` and `explain_system` patterns should have enough hits.

**Type:** `show patterns`

### Expected Output

Displays detected patterns with occurrence counts, last-seen timestamps,
and candidate status. Patterns appearing 3+ times within the Flywheel
detection window are flagged as skill candidates.

### What This Proves

**Self-Authoring (Deck Slide 2):** The system observed its own telemetry,
detected recurring patterns, and surfaced them as improvement candidates.
This is Flywheel Stage 2 (DETECT) — the mechanism behind "authors its
own evolution." The system didn't wait to be told what to improve. It
observed, detected, and proposed.

**Config Over Code:** The detection threshold (3 occurrences) and window
(14 days) are declared in `routing.config` under the `flywheel` section.
Change the config, change the detection behavior. No code change required.

**FAIL if:** Command not recognized. No patterns detected after multiple
test interactions. Error or crash.

---

## Test 9: Inspect the Config — The Cognitive Router's Brain

**Demonstrates:** Config over code, the three-files-and-a-loop story

**Type:** `show config`

### Expected Output

Displays `routing.config` contents — the complete Cognitive Router
configuration including router strategy, matching rules, cache settings,
Flywheel thresholds, route definitions, and tier descriptions.

### What This Proves

**Config Over Code (Deck Slide 10 — Build It This Weekend):** This
single file IS the Cognitive Router. The engine reads it and does
exactly what it says. A non-technical domain expert can alter the
system's behavior by editing this file, without a deploy. Add a
route, the system recognizes a new intent. Change a zone, the
governance changes. Change a tier, the economics change.

**Three Files and a Loop (Deck Slide 10):** `routing.config`,
`zones.schema`, and `telemetry.jsonl` — these are the three files
the spec requires. Everything else is enhancement. A CTO reading
this config understands what the system does without reading any
code.

**FAIL if:** Config doesn't display. Routes are missing.

---

## Test 10: Kaizen Option 3 — Config-Driven Clarification

**Demonstrates:** Declarative clarification menu, config-driven UX

**Type:** `xyzzy plugh nothing`

Gibberish. No keyword match, no cache hit. Andon Gate fires.

**Press:** `3` (Show me what you can help with)

### Expected Submenu

```
  [1] Learn how this system works
  [2] Start a conversation
  [3] Check system status
  [4] I'll rephrase with more context
```

**Press:** `1`

### Expected Response

Routes to `explain_system` → `general_chat` handler with dock context.
Architectural overview of the system.

### What This Proves

**Config Over Code:** The submenu options come from `clarification.yaml`.
Each option maps to a route in `routing.config`. The UX is declared,
not hardcoded. Change `clarification.yaml`, change the fallback menu.

**Kaizen as Architecture (Deck Slide 2):** Option 3 is a Kaizen
improvement path — when the system doesn't know, it shows what it
CAN do. The options are structured, not random. They guide the
operator toward a productive interaction without demanding the
operator figure out the system's vocabulary.

**FAIL if:** No submenu appears. Fewer than 4 options. Selection
doesn't route correctly. Error or crash.

---

## Test 11: Clean Exit

**Type:** `exit`

### Expected

`Session complete. Engine standing by.`

No errors, no tracebacks, no orphan processes.

**FAIL if:** Error on exit. Traceback. Process hangs.

---

## Results Checklist

After running all tests, verify:

| # | Test | Key Assertion | Pass? |
|---|------|--------------|-------|
| — | Startup | No LLM calls before `autonomaton>` | |
| 1 | `hello` | Glass: 5 stages, T1 keyword, GREEN auto-approve | |
| 2 | Unknown → Option 2 | Andon Gate fires, 4 options, dock-informed answer | |
| 3 | Unknown → Option 1 | LLM classifies with consent, Glass shows arrow | |
| 4 | Same input again | RATCHET fires, T0 cache ✓, $0.00 | |
| 5 | `show cache` | Correct intent cached (not `ratchet_intent_classify`) | |
| 6 | `show zones` | Zone schema displays correctly | |
| 7 | `show telemetry` | Structured traces for all interactions | |
| 8 | `show patterns` | Flywheel detects recurring patterns | |
| 9 | `show config` | Full routing config displays | |
| 10 | Gibberish → Option 3 | Config-driven submenu routes correctly | |
| 11 | `exit` | Clean shutdown | |

### Critical Regression Checks

These specific assertions guard against known architectural violations:

- **V-001 (Cache Poisoning):** Test 5 cache entry shows `intent: explain_system`, NEVER `ratchet_intent_classify`
- **V-003 (Glass Arrow):** Test 3 Glass Stage 2 shows `intent:unknown → explain_system` arrow notation
- **V-010 (Pipeline Invariant):** `grep -r "run_pipeline_with_mcp" .` returns zero results
- **V-011 (Tier Truth):** Test 2 Glass shows `T1 keyword $0.00` for the free path, not `T2 llm`

---

## Why This Test Script Matters

This is not a QA checklist. It is the OOBE — the first experience a
technical evaluator has with the Autonomaton Pattern. Every test maps
to an architectural claim from the Pattern Release:

| Test | Architectural Claim | Deck Slide |
|------|-------------------|-----------|
| Startup | Pipeline waits for operator | 4: The Pipeline |
| 1 | Five-stage invariant pipeline | 4: The Pipeline |
| 1 | Config-driven keyword routing | 5: Cognitive Router |
| 1 | Green zone auto-approve | 6: Sovereignty Guardrails |
| 2 | Digital Jidoka — stop on uncertainty | 2: The Promise |
| 2 | Kaizen — propose improvement paths | 2: The Promise |
| 2 | Consent-gated compute | 5: Cognitive Router |
| 3 | LLM classification with consent | 5: Cognitive Router |
| 3 | Glass reclassification transparency | 8: Transparency |
| 4 | The Ratchet — Reverse Tax | 9: The Ratchet |
| 4 | Compounding co-benefits | 9: The Ratchet |
| 5 | Inspectable intelligence | 7: Skill Flywheel |
| 6 | Sovereignty as schema | 6: Sovereignty Guardrails |
| 7 | Feed-first audit trail | 8: Transparency |
| 8 | Flywheel pattern detection | 7: Skill Flywheel |
| 9 | Config over code / three files | 10: Build It |
| 10 | Config-driven UX | 2: The Promise |

The test script walks the deck's narrative arc:
**Problem** (the system is honest about uncertainty) →
**Promise** (self-identifying, self-fixing, self-authoring) →
**Architecture** (pipeline, router, zones, flywheel, telemetry) →
**Ratchet** (compounding economics) →
**Transparency** (inspect everything) →
**Build It** (three files, readable config).

A CTO who runs these eleven tests in sequence has seen every
architectural commitment demonstrated, not described. That's the OOBE.

---

*Last updated: 2026-03-22*
*Author: Jim Calhoun / Grove Architecture*
*Validates against: Pattern Release Draft 1.3, Autonomaton Deck v1*
