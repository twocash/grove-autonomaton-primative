# EXPLORATION PROMPT: The Naked Autonomaton — Glass Pipeline & OOB Experience

> Paste this entire prompt into a fresh Claude context window.
> Purpose: Design the out-of-box experience for the publishable reference implementation.
> Generated: 2026-03-18

---

## Who You Are

You are working with Jim Calhoun, founder of The Grove Foundation. Jim builds
the governance layer for distributed AI — the Autonomaton Pattern. You are
designing the out-of-box experience for the "naked" version of the Autonomaton:
the domain-stripped reference implementation that ships alongside two published
papers as proof that the architecture works.

Jim's working style: stream-of-consciousness ideation that you shape into
structured artifacts. He provides voice and conceptual corrections. He works
one task at a time. He prefers the raw version of his thinking preserved
alongside the shaped version.

---

## What the Autonomaton Is

The Autonomaton is a domain-agnostic, declarative agentic system with a
five-stage invariant pipeline:

```
Stage 1: TELEMETRY   — Log the raw input before any processing
Stage 2: RECOGNITION — Cognitive Router classifies intent, domain, zone, tier
Stage 3: COMPILATION — Query local knowledge store for strategic context
Stage 4: APPROVAL    — Zone governance (Green=auto, Yellow=confirm, Red=explicit)
Stage 5: EXECUTION   — Dispatcher routes to handler
```

Every interaction traverses all five stages. No exceptions. This is the
"hourglass invariant" — the thin waist that makes everything composable.

**Three files and a loop:**
- `routing.config` — maps intents to tiers and zones (the Cognitive Router's brain)
- `zones.schema` — defines governance boundaries (Green/Yellow/Red)
- `telemetry.log` — structured JSONL audit trail (the system's memory)

**The Ratchet:** A pattern cache (`pattern_cache.yaml`) stores confirmed LLM
classifications as Tier 0 deterministic lookups. Every confirmed classification
becomes free on repeat. The system literally gets cheaper with use.

**Key principle:** The engine reads the map; the map is never built into the
engine. ALL domain behavior lives in declarative config files. The engine code
is dumb pipes. Swap the profile directory and you have a completely different
Autonomaton.


## The Repo

**Location:** `C:\GitHub\grove-autonomaton-primative`

**Key files to read for context:**
- `CLAUDE.md` — 11 architectural invariants (the system's constitution)
- `engine/pipeline.py` — The five-stage invariant pipeline
- `engine/cognitive_router.py` — Hybrid Tier 0/1/2 intent classification
- `engine/dispatcher.py` — Handler registry and execution
- `engine/telemetry.py` — Feed-first structured telemetry
- `engine/ux.py` — Digital Jidoka (stop-the-line approval UX)
- `autonomaton.py` — The REPL entry point
- `profiles/coach_demo/config/` — A working domain profile (golf coach)
- `profiles/blank_template/config/` — The empty starting point

**Two published papers (in Google Docs, referenced but not in repo):**
- "The Autonomaton Pattern as Open Protocol: TCP/IP for the Cognitive Layer"
  — Maps TCP/IP design principles to Autonomaton architecture
- "Grove Autonomaton Pattern Release — Draft 1.3"
  — The practitioner-facing pattern document ("build one in a weekend")


## The Design Problem

The Autonomaton currently has two profiles:
- `coach_demo` — A fully configured domain (Catholic high school golf coach).
  Rich dock context, entities, skills, welcome briefing, strategic brief.
  The operator is the USER. The architecture is invisible by design.
- `blank_template` — Empty config files. The system technically runs but
  the experience is: nothing happens, nothing is explained, you leave.

We need a THIRD profile: `naked` (or whatever name we land on). This is the
**publishable reference implementation** that ships alongside the papers.

**The audience is NOT an end user.** The audience is:
- A CTO who read the TCP/IP paper and wants to see if it's real
- A mid-career dev who read the Pattern Release and wants to build one
- A product leader evaluating whether this architecture fits their problem
- A potential Grove advisor or reviewer (Randy Wigginton, Susan Kare)
- A conference attendee who scanned a QR code

These people don't need a productivity tool. They need to SEE the pattern
operating. The architecture must be legible — not because we explain it,
but because the system shows its own structure as it runs.


## Design Concepts Already Discussed

These emerged from the session that generated this prompt. They're starting
points, not decisions. Push back on any of them.

### 1. The Glass Pipeline (flag in profile config)

The naked profile runs with `glass_pipeline: true` in its config. When
enabled, every pipeline stage announces itself in the terminal output:

```
autonomaton> schedule a meeting with the team

  [01 TELEMETRY]  Logged: event-a3f2...
  [02 RECOGNITION] Intent: unknown → LLM escalation → "calendar_schedule" (0.82)
  [03 COMPILATION] Dock context: [empty — no strategic context loaded]
  [04 APPROVAL]    Zone: YELLOW — requires confirmation

  JIDOKA: The system wants to create a calendar event...
  [1] Approve  [2] Cancel
```

This is NOT a debug mode. It's a designed experience — the pipeline narrating
itself for an architecture-literate audience. The coach demo hides this because
the operator doesn't care about architecture. The naked demo shows it because
the audience IS the architecture.

**Same engine. Different config. That's Invariant #10 (Profile Isolation) proved.**

### 2. The Self-Tour (first-run interactive walkthrough)

Instead of a welcome briefing that requires dock context, the naked profile's
first interaction is a guided walk-through. The operator types "hello" and
the glass pipeline shows every stage processing that greeting. They type
something ambiguous and they SEE the LLM classification fire, the Jidoka
prompt surface, the zone governance operate.

Not a help page. Not a tutorial document. A live system explaining itself
by running.

### 3. The Ratchet Demo (live cost-avoidance demonstration)

The naked profile should include just enough routing.config to leave
deliberate ambiguity. When the operator types something that hits the LLM
classifier, the glass pipeline shows the Tier 2 call with cost. When they
type the SAME thing again, the glass pipeline shows the Tier 0 cache hit
with $0.00 cost. "The system just got cheaper because you used it."

This is the central economic argument of both papers. It needs to be
visible in under 60 seconds.

### 4. Three Files on Display (inspectable from inside the REPL)

The Pattern Release says "three files and a loop." The naked profile should
make those files readable from inside the system: `show config`, `show zones`,
`show telemetry`. The operator never leaves the REPL to understand the
architecture. Every file the system reads is something the operator can read.
Transparency as architecture.

### 5. Session Zero as Domain Bootstrap

The naked profile's Session Zero isn't domain-specific. It's the universal
bootstrap: "What should this system do? What are the high-stakes actions?
What should be autonomous?" The Socratic intake writes a routing.config and
zones.schema through the pipeline. The naked Autonomaton configures itself
via the same governance it enforces.

This is the "build one in a weekend" promise made concrete. You don't read
documentation. You answer questions. The system writes its own config.


## What I Need From You

This is an exploration session, not a sprint spec. I want to think through
the design before committing to a build plan. Specifically:

### The First Five Minutes

Walk me through what happens when someone clones the repo and types
`python autonomaton.py --profile naked`. Every screen, every prompt,
every interaction. What do they see? What do they type? What do they
understand at each step? Where do they go "oh, I get it"?

The quality gate from the papers: "CTO, mid-career dev, and product
leader each find something that changes how they think." Map those
three personas through the first five minutes.

### The Glass Pipeline Design

How thick should the narration be? Options range from:
- Minimal: just stage numbers and one-line summaries
- Medium: stage numbers, key metadata (tier, zone, confidence), timing
- Full: everything including dock context snippets and telemetry event IDs

The coach demo is fully opaque. The naked demo is fully transparent.
Is there a middle ground, or does the proof require full transparency?
Should the glass pipeline be the default for naked, or opt-in via a
`--glass` flag on top of the profile selection?

### Session Zero Bootstrapping

How far does the Socratic intake go? Options:
- Light: asks 3-5 questions, writes a minimal routing.config
- Medium: asks domain questions, writes routing.config + zones.schema
- Full: full Session Zero that populates dock, entities, and skills scaffold

The "build one in a weekend" promise suggests the intake should get you
to a RUNNING, USEFUL system by the end of the conversation. But the
naked demo might just need to show the mechanism, not complete it.

### The Ratchet Moment

What's the fastest path to showing the Ratchet turning? The operator
needs to type something ambiguous, see it classified by LLM, then type
something similar and see the cache hit. How do we engineer that moment
without it feeling scripted? Should the system prompt the operator to
try it ("Try typing something similar to see the Ratchet in action")?

### The Rename Question

"Naked" is our internal name. What ships? Options:
- `reference` — accurate but clinical
- `demo` — too small
- `playground` — too unserious
- `pattern_demo` — connects to the paper
- `naked` — honest, provocative, might confuse

### What Else Am I Missing?

What aspects of the OOB experience haven't I thought about? What would
make someone SHARE this with a colleague? What's the "I have to show
you this" moment?


## Constraints

- **The engine doesn't change.** The naked profile proves the engine is
  domain-agnostic by running WITHOUT domain-specific code. If we need
  engine changes, they must be profile-driven (flags in config that the
  engine reads), not naked-specific code paths.

- **Same five stages.** The glass pipeline annotates the stages; it doesn't
  add new ones. The pipeline is invariant. The narration is presentation.

- **Declarative sovereignty.** The operator must be able to turn off the
  glass pipeline, skip the self-tour, and use the naked profile as a
  genuinely blank starting point. No forced experiences.

- **The lodestar applies.** "Design is philosophy expressed through
  constraint." If the naked demo explains the pattern through prose
  instead of demonstrating it through structure, it's not done.

## Key References

Read these files from the repo for full context:

```
C:\GitHub\grove-autonomaton-primative\CLAUDE.md
C:\GitHub\grove-autonomaton-primative\autonomaton.py
C:\GitHub\grove-autonomaton-primative\engine\pipeline.py
C:\GitHub\grove-autonomaton-primative\engine\cognitive_router.py
C:\GitHub\grove-autonomaton-primative\engine\ux.py
C:\GitHub\grove-autonomaton-primative\engine\dispatcher.py
C:\GitHub\grove-autonomaton-primative\profiles\coach_demo\config\routing.config
C:\GitHub\grove-autonomaton-primative\profiles\coach_demo\config\zones.schema
C:\GitHub\grove-autonomaton-primative\profiles\blank_template\config\
```

Also read the two sprint specs from the purity audit for current system state:
```
C:\GitHub\grove-autonomaton-primative\docs\sprints\purity-audit-v1\SPEC.md
C:\GitHub\grove-autonomaton-primative\docs\sprints\purity-audit-v2\SPEC.md
```

---

*Start by reading CLAUDE.md and the two SPEC files, then let's explore
the first five minutes.*
