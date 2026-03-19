# SPRINT: Reference Profile v1 — The Glass Pipeline & OOB Experience

> *"Design is philosophy expressed through constraint."*
> Sprint Name: `reference-profile-v1`
> Generated: 2026-03-18
> Provenance: Naked Autonomaton exploration session
> Dependency: Executes AFTER `purity-audit-v1` lands (confirmed landed)
> Recommended: Execute AFTER `purity-audit-v2` for full observability

---

## Purpose

The Autonomaton has two profiles: `coach_demo` (fully configured domain)
and `blank_template` (empty starting point). Neither serves the audience
that matters most for publication: the CTO who read the TCP/IP paper, the
mid-career dev who read the Pattern Release, the product leader evaluating
the architecture, or the potential advisor scanning a QR code at a conference.

This sprint creates a third profile — `reference` — the publishable
reference implementation that ships alongside both papers. The reference
profile is not a productivity tool. It is the architecture explaining
itself by running.

**The design problem:** The blank_template technically runs but the
experience is: nothing happens, nothing is explained, you leave. The
coach_demo hides the architecture because the operator doesn't care about
it. The reference profile makes the architecture VISIBLE — not through
prose, but through a designed terminal experience where the pipeline
narrates its own structure as it executes.

**The central feature:** The Glass Pipeline — a profile-driven presentation
mode where every pipeline stage announces itself, showing tier, zone,
confidence, cost, and cache status. Same engine. Different config. That's
Invariant #10 (Profile Isolation) proved.


## Domain Contract

**Applicable contract:** Autonomaton Architect (Anti-Code-Party Protocol)
**Contract version:** 1.0
**Additional requirements:**
- The engine MUST NOT change for this profile. All behavior is config-driven.
- Glass pipeline narration is a presentation concern in the REPL layer, not
  a pipeline modification.
- No naked-profile-specific code paths in the engine. If the engine needs
  a change, it must be a profile-driven flag that any profile can use.
- The same five stages. The glass pipeline annotates stages; it doesn't add
  new ones. The pipeline is invariant. The narration is presentation.
- Declarative sovereignty: the operator must be able to turn off glass,
  skip the self-tour, and use the reference profile as a blank starting
  point. No forced experiences.


---

## What Success Looks Like

After this sprint:

1. **Clone to "oh, I get it" in under 90 seconds.** Someone clones the
   repo, runs `python autonomaton.py --profile reference`, types "hello",
   sees the glass pipeline annotate all five stages, types something
   ambiguous, sees the LLM classification with cost, types it again,
   sees the Ratchet cache hit at $0.00. Under 90 seconds. The central
   claims of both papers — hourglass invariant, zone governance, the
   Ratchet — are proved by running, not by reading.

2. **Three files on display.** The operator can type `show config`,
   `show zones`, and `show telemetry` to inspect every file the system
   reads. Transparency as architecture. Every file the engine reads is
   something the operator can read. They never leave the REPL to
   understand the architecture.

3. **Zone governance is experienced.** The operator sees green auto-approve,
   yellow Jidoka prompt, and (via tips) understands that red exists. The
   zone model isn't just classification — it's felt as different behavior.

4. **The engine manifest is reachable.** A `show engine` command displays
   the file paths, sizes, and one-line descriptions of every engine
   module. The dev goes from glass pipeline → source files → "the pipeline
   really is one function" → fork.

5. **Session Zero bootstrapping works.** The operator can run `session zero`
   and answer five questions that write routing.config and zones.schema.
   The glass pipeline shows every config write. The path from naked demo
   to configured system is visible and reachable.

6. **Quality gate holds.** The CTO finds the auditability claim proved
   (telemetry + glass pipeline). The mid-career dev finds the config-over-code
   principle tangible (three inspectable files, Session Zero writing config).
   The product leader finds the governance model demonstrated (zone
   differentiation without friction in safe zones).


---

## The First Five Minutes (Design Specification)

This is the designed OOB experience for the reference profile. Every beat
is intentional. The quality gate from the papers applies: "CTO, mid-career
dev, and product leader each find something that changes how they think."

### Beat 0: Clone and Run (0:00)
README says: `python autonomaton.py --profile reference`. One line.

### Beat 1: The Banner (0:05)
```
============================================================
  THE AUTONOMATON — Reference Implementation
  Profile: reference
============================================================
  Dock: 0 chunks from 0 sources
  Cortex: 0 pending Kaizen item(s)
  Glass Pipeline: ACTIVE
============================================================

  This is the naked engine. No domain. No context. No skills.
  Every pipeline stage will announce itself as it runs.
  Type anything to see the architecture in motion.
```

No welcome card. No startup brief. No plan generation. The operator's
first interaction is THEIR input, not the system talking to itself.

### Beat 2: First Input — "hello" (0:15)
Glass pipeline shows five stages. Tier 0 keyword match. Green auto-approve.
Conversational intent skips compilation. Handler responds conversationally
with a nudge: "Try something I won't recognize to see what happens."

### Beat 3: Ambiguous Input (0:45)
Glass pipeline shows: keyword miss → cache MISS → LLM escalation with
cost → classification with confidence → empty dock → handler with graceful
degradation. Response includes: "That cost $0.003. Try the same phrase
again to see the Ratchet."

### Beat 4: The Ratchet Moment (1:15)
Same input. Glass pipeline shows: keyword miss → cache HIT ✓ → Tier 0,
$0.00. System announces: "THE RATCHET: classified by LLM last time,
resolved from cache this time. Zero cost. The system just got cheaper
because you used it."

### Beat 5: Inspection (2:00)
`show config`, `show zones`, `show telemetry`. Glass pipeline annotates
each as a green-zone informational query. The three files from the paper
are readable from inside the REPL.

### Beat 6: The Yellow Zone (3:00)
Tip after inspection: "Try `clear cache` to see what happens when the
zone changes." Glass pipeline shows yellow classification. Jidoka fires.
The operator approves or cancels. They've now experienced the zone model
as behavioral differentiation, not just classification.

### Beat 7: The Engine Manifest (3:30)
`show engine` displays the engine file manifest: 6 files, ~3,000 lines,
one-line descriptions. The dev sees the path from running system to
source code.

### Beat 8: Session Zero (optional, 4:00+)
`session zero` begins the Socratic bootstrap. Five questions. Each answer
writes config through the pipeline. Glass pipeline shows every write.
The path from demo to configured system is visible.


---

## Epic Structure

### Epic A: Reference Profile Directory
Create the `profiles/reference/` directory with all required config files.

**Files to create:**
- `config/profile.yaml` — NEW config file type with profile-level flags
- `config/routing.config` — System intents + reference-specific intents
- `config/zones.schema` — Minimal zone definitions
- `config/pattern_cache.yaml` — Empty (the Ratchet starts blank)
- `config/persona.yaml` — Reference implementation persona
- `config/voice.yaml` — Minimal voice config
- `config/pillars.yaml` — Empty
- `config/mcp.config` — Empty
- `dock/` — Empty (no strategic context)
- `skills/operator-guide/prompt.md` — Adapted for reference audience

**profile.yaml (new file type):**
```yaml
# Profile-level configuration flags
# These control REPL presentation, not engine behavior.
display:
  glass_pipeline: true         # Show pipeline stage annotations
  glass_level: medium          # minimal | medium | full
  tips: true                   # Show contextual tips after interactions
startup:
  skip_welcome: true           # No welcome card
  skip_startup_brief: true     # No strategic brief
  skip_plan_generation: true   # No first-boot plan
  skip_queue: true             # No Kaizen queue processing
```

**Reference routing.config additions (beyond blank_template):**
```yaml
  # --- Reference Profile: Inspection Commands ---
  show_config:
    tier: 0
    zone: green
    domain: system
    intent_type: informational
    description: "Display routing.config contents"
    keywords:
      - "show config"
      - "show routing"
      - "show routes"
    handler: "show_file"
    handler_args:
      target: "config/routing.config"

  show_zones:
    tier: 0
    zone: green
    domain: system
    intent_type: informational
    description: "Display zones.schema contents"
    keywords:
      - "show zones"
      - "show schema"
      - "show governance"
    handler: "show_file"
    handler_args:
      target: "config/zones.schema"

  show_telemetry:
    tier: 0
    zone: green
    domain: system
    intent_type: informational
    description: "Display recent telemetry events"
    keywords:
      - "show telemetry"
      - "show log"
      - "show events"
    handler: "show_file"
    handler_args:
      target: "telemetry/telemetry.jsonl"
      tail: 20

  show_cache:
    tier: 0
    zone: green
    domain: system
    intent_type: informational
    description: "Display pattern cache contents (the Ratchet)"
    keywords:
      - "show cache"
      - "show ratchet"
      - "show pattern cache"
    handler: "show_file"
    handler_args:
      target: "config/pattern_cache.yaml"

  show_engine:
    tier: 0
    zone: green
    domain: system
    intent_type: informational
    description: "Display engine file manifest with descriptions"
    keywords:
      - "show engine"
      - "show source"
      - "show code"
      - "show files"
    handler: "show_engine_manifest"
    handler_args: {}
```


### Epic B: Glass Pipeline Presentation Layer
Implement the glass pipeline as a display function in the REPL layer.

**Architecture decision:** The glass pipeline is NOT a pipeline modification.
It is a post-stage display function that reads `PipelineContext` metadata
and renders annotations. The engine doesn't know it's being observed.

**Implementation approach:**

1. Add a `display_glass_pipeline()` function to `autonomaton.py` (or a new
   `engine/glass.py` module — presentation code, not engine logic).

2. The function reads `PipelineContext` after `run_pipeline()` returns and
   renders the stage-by-stage annotation box.

3. Glass level `medium` (default for reference profile) shows:
   - Stage numbers and names
   - Tier, zone, confidence, intent_type
   - Cost when > 0 (from telemetry or routing metadata)
   - Cache hit/miss status on recognition
   - Dock status (empty/populated — not content)
   - Approval outcome (auto-approve / Jidoka triggered / cancelled)
   - Handler name at execution

4. The `profile.yaml` → `display.glass_pipeline` flag controls whether
   glass annotations render. The `--glass` CLI flag overrides for any profile.

**Key constraint:** The glass pipeline reads ONLY from `PipelineContext` and
profile config. It does not inject probes into the pipeline stages. It is
a pure observer.

**The glass annotation format:**
```
  ┌─ PIPELINE ──────────────────────────────────────────────┐
  │ [01 TELEMETRY]  Logged: evt-{id}... │ source: {source}  │
  │ [02 RECOGNITION] "{input}" → {intent}                   │
  │                  Tier {n} ({method}) │ confidence: {c}   │
  │                  Zone: {ZONE} │ Type: {type}             │
  │ [03 COMPILATION] {dock_status}                           │
  │ [04 APPROVAL]    {zone_action}                           │
  │ [05 EXECUTION]   Handler: {handler}                      │
  └─────────────────────────────────────────────────────────┘
```

**Data sources for glass annotations:**
- Stage 1: `context.telemetry_event` (event ID, source)
- Stage 2: `context.intent`, `context.entities["routing"]` (tier,
  confidence, intent_type, llm_metadata for cache hit/miss)
- Stage 3: `context.dock_context` (populated or empty)
- Stage 4: `context.zone`, `context.approved`
- Stage 5: `context.entities["routing"]["handler"]`, `context.result`

**Cost display:** When tier >= 2 and the classification was an LLM call,
display estimated cost. When tier == 0 and `llm_metadata.source == "pattern_cache"`,
display "$0.00" and the cache hit indicator. This makes the Ratchet's
economic argument visible at every interaction.


### Epic C: Reference Profile Handlers
Implement the reference-specific handlers that don't exist in the current
dispatcher.

**New handlers:**

1. **`show_file` handler** — Reads a file from the active profile directory
   and displays its contents. The `target` arg is a relative path from the
   profile root. Optional `tail` arg shows last N lines (for telemetry).
   Green zone. Informational. The pipeline still fires — telemetry logs the
   inspection, glass pipeline annotates it.

2. **`show_engine_manifest` handler** — Reads the `engine/` directory and
   displays each Python file with line count and the first docstring line.
   Format:
   ```
   ENGINE MANIFEST (6 files, ~3,100 lines)
   ─────────────────────────────────────────
   pipeline.py      (888 lines)  The Invariant Pipeline
   cognitive_router.py (616 lines)  Hybrid Intent Classification
   dispatcher.py    (xxx lines)  Handler Registry and Execution
   telemetry.py     (xxx lines)  Feed-First Structured Telemetry
   ux.py            (347 lines)  Digital Jidoka
   cortex.py        (xxx lines)  Analytical Lenses
   ─────────────────────────────────────────
   Entry point: autonomaton.py (503 lines)
   ```

3. **Modified `general_chat` handler response for reference profile** —
   When the profile is `reference` and dock is empty, the general_chat
   handler returns architecture-aware responses instead of generic chat.
   First interaction: "Type anything to see the architecture in motion."
   After LLM classification: "That cost ${cost}. Try the same phrase
   again to see the Ratchet." After Ratchet demo: "Type `show telemetry`
   to see the audit trail, or `session zero` to start building your own."

   **Implementation:** This is NOT a code branch in the handler. The
   general_chat handler already reads persona.yaml. The reference profile's
   persona.yaml instructs the LLM to respond as an architecture guide.
   Config over code.


### Epic D: Contextual Tips System
A lightweight tip engine that surfaces one-line contextual suggestions
after interactions, driven by profile config.

**The tip is the teaching mechanism.** Instead of a tutorial, the system
offers one relevant suggestion at a time based on what just happened:

- After first `hello`: "Try something the system won't recognize."
- After first LLM classification: "Try the same phrase again to see the Ratchet."
- After Ratchet demo: "Type `show cache` to see what the Ratchet stored."
- After `show cache`: "Try `clear cache` to see what happens when the zone changes."
- After first yellow zone: "Type `show telemetry` to see the full audit trail."
- After `show telemetry`: "Type `show engine` to see the source code manifest."
- After `show engine`: "Type `session zero` to start building your own Autonomaton."
- After Session Zero: "To build your own, copy this profile directory and run Session Zero."

**Implementation:** A `tips.yaml` config file in the reference profile
maps trigger conditions to tip text. The tip engine is a simple state
tracker — it records which tips have been shown and which conditions have
been met. Tips are shown ONCE each. The tip engine reads the profile's
`tips.yaml`; profiles without `tips.yaml` show no tips.

```yaml
# config/tips.yaml
tips:
  - id: first_hello
    trigger: { after_intent: "general_chat", shown_count: 0 }
    text: "Try something the system won't recognize to see what happens."

  - id: first_llm_classification
    trigger: { after_tier: 2, shown_count: 0 }
    text: "That classification used the LLM. Try the same phrase again."

  - id: ratchet_demo
    trigger: { after_cache_hit: true, shown_count: 0 }
    text: "Type `show cache` to see what the Ratchet stored."

  - id: after_show_cache
    trigger: { after_intent: "show_cache", shown_count: 0 }
    text: "Try `clear cache` to see what happens when the zone changes."

  - id: first_yellow
    trigger: { after_zone: "yellow", shown_count: 0 }
    text: "Type `show telemetry` to see the full audit trail."

  - id: after_telemetry
    trigger: { after_intent: "show_telemetry", shown_count: 0 }
    text: "Type `show engine` to see the source code manifest."

  - id: after_engine
    trigger: { after_intent: "show_engine", shown_count: 0 }
    text: "Type `session zero` to start building your own Autonomaton."

  - id: after_session_zero
    trigger: { after_intent: "session_zero", shown_count: 0 }
    text: "To build your own, copy this profile directory and customize."
```

**Display format:** A single dim line after the result:
```
  💡 Try `clear cache` to see what happens when the zone changes.
```

Tips only fire when `display.tips: true` in profile.yaml. Silent for
coach_demo and blank_template.


### Epic E: REPL Integration — Profile Flags & CLI Extension
Wire the profile.yaml flags into the REPL startup sequence and add
the `--glass` CLI flag.

**Changes to autonomaton.py:**

1. **Load profile.yaml** at startup, after `set_profile()`. Store in a
   module-level config dict accessible to display functions.

2. **Startup sequence gating:** Read `startup.skip_welcome`,
   `startup.skip_startup_brief`, `startup.skip_plan_generation`,
   `startup.skip_queue` from profile.yaml. Existing `--skip-welcome`
   and `--skip-queue` CLI flags become overrides for these config values.

3. **Fix startup force_route bug:** Three startup `run_pipeline()` calls
   pass `raw_input` strings like `"welcome_card"` without `force_route`.
   These intents have `keywords: []` — the cognitive router can't classify
   them and triggers clarification Jidoka instead of dispatching. Add
   `force_route` to all three calls: `generate_plan`, `welcome_card`,
   `startup_brief`. This fixes a purity-audit-v1 implementation gap.

4. **Glass pipeline display:** After every `run_pipeline()` call, check
   `display.glass_pipeline` (or `--glass` CLI flag). If true, call
   `display_glass_pipeline(context)` before `display_result(context)`.

5. **Banner modification:** When glass_pipeline is active, add
   `Glass Pipeline: ACTIVE` to the banner. When profile is `reference`,
   add the three-line intro block.

6. **CLI flag addition:**
   ```
   --glass         Enable glass pipeline for any profile
   ```

7. **Tip engine hook:** After `display_result()`, if tips are enabled,
   evaluate tip triggers against the context and display at most one tip.


### Epic F: Test Suite
New test file: `tests/test_reference_profile.py`

**Tests:**
- Reference profile loads without errors (profile.yaml, routing.config, zones.schema)
- Glass pipeline function produces correct annotation format
- Glass pipeline reads only from PipelineContext (no pipeline probes)
- `show_file` handler reads and returns file contents for valid targets
- `show_file` handler rejects paths outside the profile directory (security)
- `show_engine_manifest` returns correct file list and line counts
- Tips engine shows each tip at most once
- Tips engine respects `display.tips: false`
- Startup sequence skips welcome/brief/plan when profile.yaml says to
- `--glass` CLI flag works for non-reference profiles
- Profile-level flags don't affect engine behavior (pipeline runs identically)
- Cache hit/miss annotation matches actual Ratchet state


---

## Sequencing & Gates

```
Epic A (Profile Directory) ────→ GATE: `--profile reference` loads without errors
        │
Epic B (Glass Pipeline) ───────→ GATE: Pipeline annotations render for all 5 stages
        │
Epic C (Handlers) ─────────────→ GATE: show_file, show_engine_manifest, persona-driven chat
        │                              all return correct output through the pipeline
        │
Epic D (Tips System) ──────────→ GATE: Tips trigger on correct conditions, show once each
        │
Epic E (REPL Integration) ─────→ GATE: Full OOB flow matches "First Five Minutes" spec
        │
Epic F (Tests) ────────────────→ GATE: All new + existing tests pass
```

**Epic A** is the foundation — everything depends on the profile existing.
**Epics B, C, D** are independent of each other but depend on A.
**Epic E** integrates B, C, and D into the REPL. Depends on all three.
**Epic F** runs after all five.


---

## Files Touched

| File | Epic | Change Type |
|------|------|-------------|
| `profiles/reference/config/profile.yaml` | A | **New** — profile-level display/startup flags |
| `profiles/reference/config/routing.config` | A | **New** — system + inspection intents |
| `profiles/reference/config/zones.schema` | A | **New** — minimal zone definitions |
| `profiles/reference/config/pattern_cache.yaml` | A | **New** — empty |
| `profiles/reference/config/persona.yaml` | A | **New** — architecture guide persona |
| `profiles/reference/config/voice.yaml` | A | **New** — minimal |
| `profiles/reference/config/pillars.yaml` | A | **New** — empty |
| `profiles/reference/config/mcp.config` | A | **New** — empty |
| `profiles/reference/config/tips.yaml` | D | **New** — contextual tip definitions |
| `profiles/reference/dock/` | A | **New** — empty directory tree |
| `profiles/reference/skills/operator-guide/prompt.md` | A | **New** — adapted for reference audience |
| `engine/glass.py` | B | **New** — glass pipeline display module |
| `engine/dispatcher.py` | C | **Modified** — register show_file, show_engine_manifest handlers |
| `engine/config_loader.py` | E | **Modified** — add profile.yaml loading |
| `autonomaton.py` | E | **Modified** — glass display hook, CLI flag, startup gating, tip hook |
| `tests/test_reference_profile.py` | F | **New** — test file |


---

## Anti-Patterns to Watch For

Per the Autonomaton Architect protocol:

1. **Do NOT add glass pipeline logic inside the pipeline stages.** The
   pipeline doesn't know it's being observed. The glass module reads the
   PipelineContext after each run and formats the output. If the glass
   module needs data that isn't in PipelineContext, the correct fix is to
   ensure the pipeline writes that data to the context (which benefits all
   profiles, not just reference).

2. **Do NOT create reference-specific code paths in the engine.** The
   reference profile proves Invariant #10 by being ONLY config files. If
   you find yourself writing `if profile == "reference":` in engine code,
   you're violating the architecture.

3. **Do NOT hardcode tip logic.** Tips are declarative (tips.yaml). The
   tip engine reads the file. New tips are added by editing YAML, not code.
   Config over code applies to the tip system too.

4. **Do NOT force the self-tour.** The operator should be able to type
   anything as their first input. The tips system suggests the next
   interesting thing to try, but the operator is sovereign. No forced
   sequences. No modals. No "you must complete this before proceeding."

5. **Do NOT show handler internals in the glass pipeline.** The glass
   pipeline shows the five stages and their metadata. What happens INSIDE
   a handler is the handler's business. The glass observes the pipeline,
   not the handlers. The boundary is: telemetry, recognition, compilation,
   approval, execution. Period.

6. **Do NOT make the `show_file` handler a security hole.** The `target`
   arg must be validated as a relative path WITHIN the profile directory.
   Path traversal (`../engine/llm_client.py`) must be rejected. The
   handler shows profile files, not engine files — that's what
   `show_engine_manifest` is for.

7. **Do NOT pre-seed the pattern cache.** The reference profile ships
   with an empty cache. The Ratchet turning is the demo. If the cache
   is pre-seeded, we're asserting instead of demonstrating. The lodestar:
   "Design is philosophy expressed through constraint." The empty cache
   IS the constraint that forces the demonstration.


---

## Dependency Note: Purity Audit v2

This sprint can execute after purity-audit-v1 (confirmed landed). However,
the glass pipeline's medium-level display benefits significantly from the
flat telemetry schema (v2 Epic A) — first-class `intent`, `tier`,
`confidence`, and `cost_usd` fields make the glass annotations trivial to
render instead of digging into the `inferred` dict.

**Recommendation:** Land purity-audit-v2 Epic A (Flat Telemetry Schema)
before starting Epic B (Glass Pipeline) of this sprint. The other v2 epics
(model config, zone UX) are independent.

If v2 is not landed, the glass module can extract data from
`context.entities["routing"]` instead, which works but is uglier.


---

## What Ships

The reference profile is the artifact that ships alongside both papers:

- **"The Autonomaton Pattern as Open Protocol: TCP/IP for the Cognitive Layer"**
  → The reference profile proves the protocol claims (hourglass invariant,
  zone governance, the Ratchet, profile isolation)

- **"Grove Autonomaton Pattern Release — Draft 1.3"**
  → The reference profile IS the "build one in a weekend" path (clone,
  run, Session Zero, fork)

The README links both papers and says: "Run the reference profile to see
the architecture in motion. Run Session Zero to build your own."

The `--glass` flag means anyone can apply glass to the coach_demo too —
showing the architecture operating THROUGH a real domain. Two perspectives
on the same engine. That's the proof.
