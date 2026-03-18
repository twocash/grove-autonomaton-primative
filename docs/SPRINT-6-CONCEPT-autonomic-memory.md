# SPRINT 6 CONCEPT: Autonomic Memory & Standardized Exhaust

> "The system is a system of systems. Every subprocess that emerges
> gets built as an autonomic connection. The pipeline is fractal."

---

## The Architectural Insight

The Autonomaton isn't one pipeline. It's a NETWORK of pipelines.

The top-level REPL runs the five-stage invariant pipeline on operator input.
Inside that, each Cortex lens runs its own recognition → compilation →
proposal cycle. The Pit Crew runs its own pipeline when building skills.
The Context Gardener runs its own observation → synthesis → proposal cycle.

What Jim is naming: **the pattern is fractal.** Every subprocess that emerges
— memory accumulation, correction detection, goal tracking, plan synthesis —
should be built as its own autonomic subprocess with the same five stages.
And every subprocess produces STANDARDIZED EXHAUST that any other subprocess
(or any other autonomaton instance entirely) can read.

This is how the system becomes a system of interconnected autonomatons.
Hub-and-spoke. Mesh. Whatever topology emerges from the domain.

---

## The Three Missing Pieces

Sprint 4 gave the persona a nervous system (standing context).
Sprint 5 gave it a trajectory (structured plan) and foresight (gap detection).

What's missing to close the cognitive loop:

### 1. MEMORY — The Learning Layer

Atlas has `atlas.memory` — an append-only correction log. When Jim says
"that's wrong," Atlas persists the learning. It compounds across sessions.

The primitive has no equivalent. The coach says "Danny's issue is alignment,
not confidence" — that correction hits telemetry as a raw event, but nothing
reads it back as a LEARNING. The standing context reads dock files. The
Cortex reads telemetry for patterns. Nobody reads telemetry for CORRECTIONS.

### 2. STANDARDIZED EXHAUST — The Translation Layer

Right now, telemetry is a flat JSONL file. Events have different shapes
depending on their source. Classification events look different from content
compilation events look different from Cortex proposals. There's no common
schema that says "this is an observation" vs. "this is a correction" vs.
"this is a pattern."

The standardized exhaust format is what makes autonomatons interoperable.
If every subprocess produces exhaust in the same schema, any other subprocess
can read it. And more importantly: the Haiku normalization layer can translate
the MANY ways humans express things into the ONE way the system stores them.

### 3. AUTONOMIC CONNECTIONS — The Network Layer

Right now, subprocesses are hardwired. The Context Gardener is called from
the tail pass. The Ratchet is called explicitly. There's no protocol for
"subprocess A wants to observe the exhaust of subprocess B."

The connection protocol is what enables hub-and-spoke or mesh topologies.
Each subprocess declares what exhaust it produces and what exhaust it
consumes. The system wires them together at startup based on configuration.

---

## The Standardized Exhaust Schema

Every autonomic subprocess produces exhaust in this format:

```yaml
# An exhaust entry — the atomic unit of system learning
exhaust_entry:
  id: "exh-20260318-001"
  timestamp: "2026-03-18T15:30:00Z"
  source: "context_gardener"         # Which subprocess produced this
  type: "observation"                # observation | correction | pattern | gap
  tier_produced: 1                   # Which LLM tier generated this (0 = deterministic)
  
  # The normalized content — what the system learned
  content:
    category: "entity_attribute"     # entity_attribute | priority_shift | timing_pattern
                                     # capability_gap | goal_progress | correction
    subject: "danny-cho"             # What entity/concept this is about
    observation: "Primary development area is approach shot alignment, not confidence"
    confidence: 0.9                  # How confident the system is
    evidence: "Operator corrected strategy_session output at 15:28"
  
  # Provenance — where this came from
  provenance:
    triggering_event: "tel-20260318-042"   # The telemetry event that caused this
    operator_approved: true                 # Did the operator confirm this?
    approval_event: "tel-20260318-045"      # The approval telemetry event
  
  # Ratchet metadata — for cost optimization
  ratchet:
    times_confirmed: 1              # How many times operator has confirmed this
    last_confirmed: "2026-03-18"
    tier_candidate: false           # True when confirmed enough for Tier 0 demotion
    demotion_proposed: false        # True when Ratchet has proposed demotion
```

### Why This Schema Matters

1. **Any subprocess can produce it.** The Context Gardener produces
   `type: observation`. The Memory Accumulator produces `type: correction`.
   The Ratchet produces `type: pattern`. Same schema, different sources.

2. **Any subprocess can consume it.** The standing context can read all
   exhaust entries to build awareness. The structured plan can filter for
   `type: goal_progress`. The Memory Accumulator can filter for
   `type: correction` to build the learning log.

3. **Any autonomaton can read it.** Atlas could read the coach_demo's
   exhaust and vice versa. A new autonomaton fork could import exhaust
   from a template. The schema IS the interoperability layer.

4. **The Ratchet optimizes across it.** Every exhaust entry tracks which
   LLM tier produced it. When `times_confirmed` crosses a threshold, the
   Ratchet proposes demotion. The observation becomes a Tier 0 fact — zero
   cost to maintain.

---

## The Haiku Normalization Layer

This is the translation engine. Humans say things many ways:

- "Danny's issue is alignment, not confidence"
- "Actually his real problem is approach shots"
- "No — it's more about his setup on approaches"
- "That's not right about Danny"

All of these are the SAME correction: entity `danny-cho`, field
`development_area`, new value `approach_shot_alignment`.

The Haiku layer (Tier 1, cheap and fast) translates varied human
expression into normalized exhaust entries. The prompt:

```
You are a correction normalizer. The operator said something that
corrects the system's understanding. Extract:

1. What entity is being corrected? (player, family, venue, goal, etc.)
2. What attribute is being changed?
3. What was the old understanding?
4. What is the new understanding?

Operator said: "{raw_input}"
System previously said: "{system_output_being_corrected}"

Return ONLY JSON:
{
  "category": "<entity_attribute|priority_shift|timing_pattern|correction>",
  "subject": "<entity_name>",
  "old_value": "<what the system thought>",
  "new_value": "<what the operator is saying>",
  "confidence": <0.0-1.0>
}
```

The Ratchet watches these normalizations. When "Danny" + "alignment"
appears 3+ times with operator confirmation, the Ratchet proposes a
Tier 0 rule: any mention of Danny + development → alignment. No more
Haiku call needed. The learning is now FREE.

THIS is the multidimensional exercise Jim is describing:
- The operator teaches the system (correction)
- Haiku normalizes the correction (Tier 1 cost)
- The Ratchet observes the normalization pattern (Tier 2 analysis)
- The pattern gets demoted to Tier 0 (zero cost)
- The system now knows this fact without ANY LLM call
- Every future interaction is cheaper because of this one correction

The investment in cognition pays down its own cost.

---

## The Memory Accumulator (Autonomic Subprocess)

Memory isn't a flat file. It's a subprocess with its own pipeline:

```
MEMORY ACCUMULATOR PIPELINE:
┌─────────────────────────────────────────────────────────────┐
│  Telemetry:  Operator output detected as correction/feedback│
│              (disagreement, "actually...", "no, it's...")    │
├─────────────────────────────────────────────────────────────┤
│  Recognition: Haiku classifies correction type              │
│              (entity_attribute, priority_shift, timing, etc.)│
├─────────────────────────────────────────────────────────────┤
│  Compilation: Compare against existing memory entries        │
│              (duplicate? update? new learning?)              │
├─────────────────────────────────────────────────────────────┤
│  Approval:   Kaizen queue — operator confirms the learning  │
│              "I noticed you corrected Danny's development    │
│               area. Save this to memory?"                   │
├─────────────────────────────────────────────────────────────┤
│  Execution:  Write standardized exhaust entry               │
│              Update standing context                        │
│              Update entity if applicable                    │
└─────────────────────────────────────────────────────────────┘
```

### Detection Signals

How does the system know the operator is correcting it?

**Signal 1: Jidoka rejection + follow-up input.** The operator rejects a
strategy_session output (via Jidoka "cancel") and then provides a correction.
The correction arrives as the next pipeline input. The Memory Accumulator
reads the telemetry pair (rejection event + follow-up event) and proposes
a learning.

**Signal 2: Explicit correction language.** "Actually...", "No, it's...",
"That's wrong...", "Not confidence, alignment." Haiku can detect these
patterns at near-zero cost. When detected, the Accumulator fires.

**Signal 3: Entity edit detection.** The operator (or Pit Crew) modifies
an entity file directly. The system detects the change on next dock reload
and proposes a memory entry: "danny-cho entity updated: development_area
changed from 'confidence' to 'alignment_approach_shots'."

**Signal 4: Plan correction.** The operator edits the structured plan
directly (opens the .md file, changes a line). The system detects the
diff on next plan reload and proposes a memory entry capturing what changed
and why the system's original assessment was wrong.

### Storage: The Exhaust Log

Memory entries are stored as standardized exhaust in a new file:

`profiles/{profile}/telemetry/exhaust.jsonl`

NOT in the dock. The dock is for human-curated strategic context. The exhaust
log is for machine-generated observations that have been operator-approved.
The standing context reads BOTH — dock files for strategy, exhaust log for
learned patterns.

Why JSONL and not markdown? Because the exhaust log is consumed by machines
(the Ratchet, the Context Gardener, other autonomatons). It needs to be
parseable, queryable, and appendable. The structured-plan.md stays markdown
because humans need to read it. The exhaust log serves a different audience.

### The Human-Readable View: memory-digest.md

For operator transparency, the system periodically generates a human-readable
digest of the exhaust log: `dock/system/memory-digest.md`

```markdown
# Memory Digest
> Auto-generated from exhaust log. 12 confirmed learnings.

## Entity Corrections (4)
- Danny Cho: Development focus is alignment on approach shots, not confidence
- Cathedral team: Strength is #3-#5 lineup depth, not top players
- Eagle Creek: Wind from west affects holes 4, 7, 14 (not just 7)
- Marcus Henderson: Leaving putts short is a distance control issue, not nerves

## Timing Patterns (3)
- Coach batches content compilation on Sunday evenings, not Monday mornings
- Tournament prep requests spike 5-7 days before matches
- Strategy sessions happen most often at morning boot (first interaction)

## Priority Learnings (3)
- Match composure matters more than winning for early-season matches
- Content about Jake's leadership consistently outperforms other pillars
- Revenue/tithing goals are intentionally deferred until subscriber base grows

## Dismissed Observations (2)
- "Coach prefers TikTok over Instagram" — dismissed, equal priority
- "Danny needs extra attention" — dismissed, all players get equal focus
```

The digest is regenerated when the exhaust log changes. The standing
context reads it. The persona carries these learnings at all times.

---

## Autonomic Connection Protocol

How subprocesses discover and consume each other's exhaust.

### The Registry: exhaust-manifest.yaml

Each profile declares what exhaust its subprocesses produce and consume:

```yaml
# profiles/coach_demo/config/exhaust-manifest.yaml

subprocesses:
  main_pipeline:
    produces:
      - type: interaction
        location: telemetry/telemetry.jsonl
    consumes: []  # Top-level — consumes operator input directly

  context_gardener:
    produces:
      - type: observation
        location: telemetry/exhaust.jsonl
      - type: gap_alert
        location: telemetry/exhaust.jsonl
      - type: stale_alert
        location: telemetry/exhaust.jsonl
    consumes:
      - source: main_pipeline
        type: interaction
      - source: memory_accumulator
        type: correction

  memory_accumulator:
    produces:
      - type: correction
        location: telemetry/exhaust.jsonl
      - type: pattern
        location: telemetry/exhaust.jsonl
    consumes:
      - source: main_pipeline
        type: interaction  # Watches for correction signals

  ratchet:
    produces:
      - type: pattern
        location: telemetry/exhaust.jsonl
      - type: demotion_proposal
        location: queue/pending.yaml
    consumes:
      - source: main_pipeline
        type: interaction
      - source: context_gardener
        type: observation
      - source: memory_accumulator
        type: correction
```

### How Connections Work at Runtime

At startup, the system reads `exhaust-manifest.yaml` and wires
subprocess consumers to their declared sources. This is CONFIGURATION,
not code. A new subprocess gets connected by adding an entry to the
manifest — the engine reads it and routes exhaust accordingly.

For Sprint 6, the wiring is simple: the Memory Accumulator reads from
`telemetry/telemetry.jsonl` (main pipeline exhaust) and writes to
`telemetry/exhaust.jsonl` (standardized exhaust). The Context Gardener
already reads telemetry — it just ALSO reads the exhaust log now.
The manifest makes this explicit and configurable.

### Cross-Autonomaton Vision (Sprint 7+)

The exhaust-manifest.yaml can declare EXTERNAL sources:

```yaml
external_sources:
  - name: atlas
    type: correction
    location: "notion://atlas.memory"  # Or a shared file path
    sync: pull  # This autonomaton reads, doesn't write
```

When Atlas learns "Jim prefers to batch content on Sunday evenings,"
that learning exists in Atlas's memory. If the coach_demo's manifest
declares Atlas as an external source, the standing context picks it
up. The learning transfers WITHOUT either system being aware of the
other's internals. The exhaust schema IS the interoperability layer.

This is how the hub-and-spoke or mesh emerges: not through centralized
orchestration, but through declared exhaust connections. Each autonomaton
is sovereign. Each publishes standardized exhaust. Each subscribes to
the sources it needs. The topology emerges from the configuration.

---

## The Multidimensional Flywheel

Every layer optimizes every other layer:

```
OPERATOR CORRECTS THE SYSTEM
    │
    ▼
MEMORY ACCUMULATOR detects correction (Tier 1 Haiku)
    │  → Produces exhaust: type=correction
    │  → Proposes Kaizen: "Save this learning?"
    │
    ▼
OPERATOR APPROVES → exhaust.jsonl entry confirmed
    │
    ▼
STANDING CONTEXT refreshes → persona now carries the learning
    │
    ▼
NEXT INTERACTION is smarter (correction already in context)
    │
    ▼
CONTEXT GARDENER reads exhaust + telemetry
    │  → Observes: "3 corrections about Danny in 2 weeks"
    │  → Proposes plan update: "Danny is primary development focus"
    │
    ▼
RATCHET reads exhaust across ALL subprocesses
    │  → Observes: "Danny + development → alignment" confirmed 3x
    │  → Proposes Tier 0 demotion: deterministic routing rule
    │
    ▼
CORRECTION IS NOW FREE (Tier 0, no LLM call)
    │
    ▼
SYSTEM IS PERMANENTLY SMARTER AT ZERO MARGINAL COST
```

Dimensions being optimized simultaneously:
1. **Routing cost** — Ratchet demotes classification patterns
2. **Awareness cost** — Standing context caches synthesized knowledge
3. **Memory cost** — Confirmed learnings become Tier 0 facts
4. **Observation cost** — Context Gardener learns what's worth proposing
5. **Operator effort** — System pulls toward goals, catches drift, fills gaps

---

## Sprint 6 Scope (Epics)

### Epic 6.0: ADR-001 — Ratchet Classification Function (PREREQUISITE)

**See:** `docs/ADR-001-ratchet-classification.md`

Before building the Memory Accumulator or standardized exhaust, codify
the universal classification pattern that's been reinvented 7 times:

1. Create `engine/ratchet.py` with `ratchet_classify()`, `RatchetConfig`,
   and `RatchetResult` types
2. Refactor `cognitive_router.py:classify()` onto `ratchet_classify()`
   (extract keyword logic into a deterministic function, Sonnet escalation
   into an interpret function)
3. Refactor `cortex.py:_extract_entities()` + `_extract_entities_llm()`
   into a single `ratchet_classify()` call
4. Add `ratchet_classify()` configs for gap detection and plan update detection
5. Update `CLAUDE.md` with Invariant #12: Ratchet Classification
6. Standardized telemetry schema for ALL classification events — the Ratchet
   can now systematically read every classifier's exhaust and propose demotions

**Why first:** The Memory Accumulator's correction detection (Epic 6B) IS a
classification task. Without the universal function, it would be the eighth
reinvention. The exhaust schema (Epic 6A) depends on the classification
telemetry schema defined in the ADR. Everything downstream builds on this.

### Epic 6A: Standardized Exhaust Schema + Log

- Define the exhaust entry schema (YAML spec in `docs/`)
- Create `telemetry/exhaust.jsonl` as the standardized exhaust log
- Add `write_exhaust()` and `read_exhaust()` to `engine/telemetry.py`
- Add exhaust type filtering: `read_exhaust(type="correction")`
- Update `gather_state_snapshot()` to read exhaust log summaries
- All existing Cortex proposals migrate to exhaust format
  (Context Gardener outputs become exhaust entries on approval)

### Epic 6B: Memory Accumulator (Cortex Lens 7)

- New Cortex lens: correction detection from telemetry patterns
- Signal detection: Jidoka rejection + follow-up, explicit correction
  language ("actually", "no, it's"), entity edit detection
- Haiku normalization: translate varied human expression into
  standardized exhaust entries
- Kaizen proposal: "I noticed you corrected X. Save to memory?"
- On approval: write to `telemetry/exhaust.jsonl`, refresh standing
  context, optionally update entity file
- Wire to tail pass alongside Context Gardener

### Epic 6C: Memory Digest Generator

- Create `dock/system/memory-digest.md` — human-readable view of
  the exhaust log's confirmed learnings
- Regenerated when exhaust log changes (after Kaizen approval)
- Standing context reads the digest for persona awareness
- Categorized: entity corrections, timing patterns, priority learnings
- Includes dismissed observations (so the system learns from rejections
  too — what the operator says "no" to is as informative as "yes")

### Epic 6D: Exhaust Manifest (Connection Protocol)

- Create `config/exhaust-manifest.yaml` — declares subprocess
  producers and consumers
- Engine reads manifest at startup, wires connections
- Context Gardener updated to consume from exhaust.jsonl as well as
  telemetry.jsonl
- Ratchet updated to read exhaust entries for demotion candidates
- Foundation for Sprint 7+ cross-autonomaton connections

---

## Sequencing

6.0 ships first — the universal `ratchet_classify()` function codifies
the two-layer pattern and standardizes classification telemetry. Without
this, every new classifier (including the Memory Accumulator) reinvents
the same shape. See `docs/ADR-001-ratchet-classification.md`.

6A ships second — the exhaust schema and log are infrastructure that
6B, 6C, and 6D all depend on. The exhaust schema builds ON TOP of the
classification telemetry schema from 6.0. Without the standardized
format, the Memory Accumulator has no target.

6B and 6C can run in parallel — the Accumulator writes exhaust, the
Digest reads exhaust. They're independent consumers of the same format.
The Accumulator's correction detection uses `ratchet_classify()` from 6.0.

6D ships last — it's the configuration layer that makes the connections
explicit. The connections already WORK after 6A-C (hardwired in code).
6D makes them CONFIGURABLE (declared in YAML). Config over code.

---

## Architectural Constraints

1. **Everything through the pipeline.** Memory writes go through the
   Kaizen queue. No direct writes to exhaust.jsonl without approval.

2. **Standardized exhaust is the ONLY interop format.** Subprocesses
   don't read each other's internals. They read each other's exhaust.
   This is the sovereignty guarantee — each subprocess is a black box
   that publishes standardized observations.

3. **Haiku normalizes, Sonnet synthesizes.** Correction detection and
   normalization are Tier 1 (cheap, fast). Digest generation and plan
   updates are Tier 2 (quality synthesis). The Ratchet demotes stable
   patterns to Tier 0. Cost discipline at every layer.

4. **Append-only exhaust.** Like Atlas's memory: never delete, never
   overwrite. Only append new entries. The digest is regenerated from
   the full log — it's a view, not a store.

5. **Operator approval is non-negotiable.** The system proposes
   learnings. The operator confirms or dismisses. Dismissed items are
   logged too — the system learns from "no" as much as "yes."

6. **Profile isolation.** The exhaust log, manifest, and digest live
   in the profile directory. Engine code is domain-agnostic. A blank
   template fork gets the infrastructure for free.

---

## The Lodestar Test

> "Design is philosophy expressed through constraint."

The Memory Accumulator expresses the philosophy that **a system should
learn from its mistakes and compound that learning over time.** The
constraint is that every learning goes through the invariant pipeline,
gets normalized into standardized exhaust, requires operator approval,
and becomes cheaper to maintain as it's confirmed.

The Standardized Exhaust Schema expresses the philosophy that
**autonomatons are sovereign but interoperable.** The constraint is
that no subprocess reads another's internals — only its published
exhaust. Topology emerges from configuration, not coupling.

The Haiku Normalization Layer expresses the philosophy that **diverse
human expression should converge on structured understanding.** The
constraint is that the Ratchet watches these normalizations and demotes
stable patterns to zero cost. The investment in cognition is finite;
the benefit compounds forever.

Sprint 4 was the nervous system.
Sprint 5 was the memory and foresight.
Sprint 6 is the learning — the system that gets smarter from use,
cheaper from learning, and more connected from standardized exhaust.

This is not far from the finish line. This is the autonomaton that
builds autonomatons.

---

*"The measure of intelligence is the ability to change."*
— Albert Einstein
