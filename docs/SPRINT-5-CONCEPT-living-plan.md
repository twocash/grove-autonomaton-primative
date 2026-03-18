# SPRINT 5 CONCEPT: The Living Plan

> "The system doesn't just know where you are. It knows where you're going,
> how fast you're moving, and what's in the way."

---

## What Sprint 4 Delivers

Sprint 4 gives the Chief of Staff a **nervous system** — persistent awareness
of the current state. It reads the dock, entities, content pipeline, skills,
and recent telemetry. It carries that awareness in every interaction. The
persona stops being amnesiac.

But Sprint 4's awareness is a snapshot. It answers "what do I know right now?"
It doesn't answer "what has changed," "what's working," "what's stalled," or
"what should we do about it."

## What Sprint 5 Delivers

Sprint 5 gives the Chief of Staff a **trajectory** — not just where are we,
but where are we going, how fast, and what's in the way. And critically: the
system WRITES this understanding into a human-readable artifact that the
operator can review, correct, and trust.

---

## The Structured Plan

A new dock artifact: `dock/system/structured-plan.md`

This is the Chief of Staff's externalized mental model. Not telemetry (machine-
only). Not goals.md (hand-written, static). A living document that the SYSTEM
writes and maintains, through the Kaizen queue, with operator approval.

### What It Contains

```markdown
# Structured Plan
> Last updated: 2026-03-22 (auto-generated, operator-approved)

## Active Goals & Progress

### Goal 1: YouTube — 1,000 Subscribers
- **Target:** 1,000 in 6 months (by September 2026)
- **Current:** ~45 subscribers (Week 3)
- **Trajectory:** On pace for ~120 by Month 2 (below 250 target)
- **Observation:** Only 1 YouTube video uploaded. TikTok volume is strong
  (4/week) but cross-posting to YouTube is not happening.
- **Recommended action:** "compile content" for YouTube-length formats,
  not just TikTok/Instagram.

### Goal 2: TikTok — 5/week
- **Target:** 5 TikToks per week
- **Current:** Averaging 4.2/week over last 3 weeks
- **Trajectory:** Close. Missing Monday posts consistently.
- **Observation:** Content seeds for Monday pillar (short-game devotionals)
  exist but aren't being compiled. 2 uncompiled seeds match this pillar.
- **Recommended action:** "compile content" on Sunday evenings.

### Goal 3: First Match — March 29
- **Status:** 7 days away
- **Completed:** Roster set (6 players). Eagle Creek venue loaded.
- **Pending:** Lineup not posted. Tournament prep not generated.
- **Blocking:** No parent contact info for Martinez, Cho, or Brennan
  families. Can't send tournament logistics email.
- **Recommended action:** "tournament prep" then manually add parent
  entities before sending schedule.

## Data Gaps (System Needs)

| What's Missing | Why It Matters | How to Fix |
|----------------|----------------|------------|
| Martinez family entity | Can't email tournament schedule | Add to entities/parents/ |
| Cho family entity | Same | Same |
| Brennan family entity | Same | Same |
| Player handicaps | Can't generate performance reports | Add to player entities |
| Post-match scoring data | Can't track Goal 5 (scoring trends) | Need data entry after matches |

## Stale Items

- Revenue/tithing goals not referenced in 14 days
- Vision board item re: lesson reminders — no progress
- Exhaust board entry for weekly-report drill tracking — not activated

## What's Working

- Content seed generation is strong (7 seeds, 4 compiled)
- Jake Sullivan's leadership content is the highest-engagement pillar
- Tournament prep skill is ready and loaded
- Standing context is active (Sprint 4)
```

### Why This Matters

1. **It's human-readable.** The coach can open this file, read it, and say
   "that's wrong, we actually posted 5 TikToks last week" or "ignore the
   YouTube goal for now, we're focused on the match." Corrections get written
   back through the pipeline.

2. **It feeds the standing context.** Sprint 4's `gather_state_snapshot()`
   reads dock files. The structured plan IS a dock file. So the Chief of
   Staff's ambient awareness now includes trajectory, not just state.

3. **It goes through the pipeline.** Every update to the structured plan is
   a Kaizen proposal → operator approval → dock write → telemetry log. The
   Ratchet sees these patterns. The system learns what kinds of observations
   the operator approves vs. dismisses. Over time, the Context Gardener gets
   smarter about what's worth proposing.

4. **It makes synthesis cheaper.** Without the structured plan, the Chief of
   Staff has to re-derive priorities from raw dock content every time. With
   it, the priorities are already synthesized. The startup brief reads the
   plan and says "here's what's changed since yesterday" instead of rebuilding
   the whole picture from scratch. That's fewer Sonnet tokens per interaction.

---

## The Context Gardener (Cortex Lens 6)

A new Cortex lens that runs as a tail pass (like Lenses 1-5) and proposes
dock updates based on observed patterns.

### What It Reads

- **Telemetry:** What intents fire most? What gets approved vs. cancelled?
  Where does classification fail repeatedly?
- **Standing context:** What's loaded, what's missing, what's stale?
- **Structured plan:** What goals exist, what progress has been made?
- **Vision board:** What aspirations has the operator expressed?
- **Exhaust board:** What telemetry potential exists but isn't being used?

### What It Proposes

Three types of Kaizen proposals, all through the existing queue:

**Type 1: Gap Alerts**
```yaml
- id: gap-001
  trigger: context_gardener
  type: gap_alert
  proposal: "3 player families have no parent entity. Email handler
    can't fire without contact info. Families needed: Martinez, Cho, Brennan."
  action: "prompt_operator"
  priority: high  # Match is in 7 days
```

**Type 2: Observation Updates (to structured-plan.md)**
```yaml
- id: obs-001
  trigger: context_gardener
  type: plan_update
  proposal: "Update Goal 2 (TikTok volume): averaging 4.2/week, missing
    Mondays consistently. 2 uncompiled seeds match Monday pillar."
  target_file: "dock/system/structured-plan.md"
  target_section: "Goal 2: TikTok"
  priority: medium
```

**Type 3: Stale Item Detection**
```yaml
- id: stale-001
  trigger: context_gardener
  type: stale_alert
  proposal: "Revenue/tithing goals not referenced in 14 days. Last
    interaction with money-related intent: March 4. Goal 3 targets
    $500/month by Month 6."
  priority: low
```

### When It Runs

After the Cortex tail pass in the REPL loop. Not every cycle — gated by:
- Minimum 10 new telemetry events since last run (avoid thrashing)
- Maximum once per session (don't spam Kaizen queue)
- Configurable in a new `cortex.config` or section in `routing.config`

### The Flywheel

Here's the multidimensional part:

```
Operator interacts
    → Telemetry logs (Stage 1)
    → Classification happens (Stage 2, maybe Tier 2 Sonnet)
    → Cortex tail pass runs
        → Context Gardener observes patterns
        → Proposes dock updates via Kaizen
    → Operator approves/dismisses
        → Approved updates write to dock/structured-plan.md
        → Standing context refreshes
    → Next interaction is informed by updated plan
        → Classification is easier (Ratchet demotes to Tier 0)
        → Synthesis is cheaper (plan already has priorities)
        → Persona is smarter (knows trajectory, not just state)
```

Every loop through this flywheel:
1. Makes ROUTING cheaper (Ratchet learns keyword patterns from Tier 2 classifications)
2. Makes AWARENESS cheaper (structured plan caches synthesized priorities)
3. Makes OBSERVATION more accurate (the Gardener learns which proposals get approved)
4. Makes the OPERATOR more effective (the system pulls them toward their goals)

This is the Skill Flywheel from the Autonomaton pattern — but applied to the
persona's understanding rather than to operational skills. The system doesn't
just get better at executing tasks. It gets better at understanding what the
operator is trying to accomplish.

---

## The Onboarding Arc

With Sprint 4 + Sprint 5, the onboarding journey becomes:

**Day 0: Bootstrap**
Operator forks blank_template. Runs Session Zero. The Socratic intake seeds
dock/ and entities/ with initial context. The structured plan generates its
first version: "Here's what I understand about what you're trying to do."

**Week 1: Observation**
Normal use. The operator compiles content, preps for events, chats about
priorities. The Context Gardener watches. Proposes its first dock updates:
"You seem to prioritize content compilation on Mondays. You mention Player X
more than anyone else. You haven't touched Goal Y in 5 days." Operator
approves the ones that are right, dismisses the ones that aren't.

**Week 2: Refinement**
The structured plan has been updated 3-4 times with approved observations.
The Chief of Staff's startup brief now says "Last week you hit 4/5 TikToks
but missed YouTube again. The match is Saturday — tournament prep takes
priority. After the match, let's get the parent emails sorted." That's not
a pre-written script. That's synthesized from the living plan.

**Month 1: Self-Authoring**
The structured plan is now a genuine strategic document that neither the
operator nor the system could have written alone. It's the operator's goals,
filtered through the system's observations, refined by the operator's
corrections. The Chief of Staff has learned the coach's rhythms, priorities,
and blind spots — not through configuration, but through use.

**Month 3: The Demo Moment**
Someone forks the blank_template. Runs Session Zero. Within a week, their
autonomaton is generating structured plans specific to their domain. The
coach_demo is just one instance. The architecture is domain-agnostic. The
Context Gardener reads telemetry patterns and proposes dock updates regardless
of whether the domain is golf coaching, content production, legal research,
or startup operations.

THIS is the autonomaton that builds autonomatons.

---

## Sprint 5 Scope (Epics)

### Epic 5A: The Structured Plan Artifact
- Create `dock/system/structured-plan.md` template
- Create `generate_structured_plan()` in compiler.py that synthesizes
  goals.md + seasonal-context.md + entity inventory + content pipeline
  into the initial plan (Tier 2 Sonnet call)
- Wire to startup: if structured-plan.md doesn't exist, generate it
  on first boot and present for operator approval
- Wire to standing context: `gather_state_snapshot()` reads it
- Ensure the plan goes through the pipeline (write = Yellow Zone)

### Epic 5B: Context Gardener (Cortex Lens 6)
- New Cortex lens that reads telemetry + standing context + plan
- Proposes three types of Kaizen: gap alerts, plan updates, stale items
- Gated: minimum 10 events since last run, max once per session
- Proposals go through existing Kaizen queue with operator approval
- Approved plan_update proposals write to structured-plan.md

### Epic 5C: Gap Detection at Startup
- After standing context assembles, detect entity gaps vs. handler
  requirements (e.g., email handler needs parent emails that don't exist)
- Surface gaps in the startup brief: "I can't send tournament schedules
  until I have contact info for 3 families."
- Optionally propose gap-filling during conversation: "You mentioned
  the Cho family — do you have an email for them?"

### Epic 5D: Plan Refresh Cycle
- After Cortex tail pass, if approved proposals updated the plan,
  refresh the standing context
- Weekly (or configurable) full plan regeneration: Sonnet re-synthesizes
  the entire plan from current dock + telemetry, producing a fresh
  trajectory assessment
- Track plan versions in telemetry so the Ratchet can observe how
  the operator's priorities shift over time

---

## Architectural Constraints

1. **Everything through the pipeline.** Plan reads are compilation
   (Stage 3). Plan writes are Yellow Zone (Stage 4 approval). No
   backdoor writes to dock files.

2. **Kaizen queue is the gate.** The system NEVER writes to the dock
   without operator approval. The Context Gardener proposes. The
   operator decides. This is non-negotiable.

3. **Human-readable is a requirement, not a preference.** The structured
   plan must be a markdown file that makes sense when opened in a text
   editor. If the operator can't read it and say "yes, that's right"
   or "no, that's wrong," it's not done.

4. **Profile isolation.** The Context Gardener is engine code. The
   structured plan is profile content. A blank_template fork gets the
   gardener for free — it just has nothing to garden yet until Session
   Zero seeds the dock.

5. **Cost discipline.** The full plan regeneration is a Tier 2 call.
   The Context Gardener's individual proposals should be Tier 1 (Haiku)
   for pattern matching, escalating to Tier 2 only for synthesis.
   The Ratchet tracks all of this.

---

## Sequencing

Sprint 4 (in progress): Standing context. The nervous system.
Sprint 5A first: The structured plan artifact. The memory.
Sprint 5B second: The Context Gardener. The learning.
Sprint 5C third: Gap detection. The foresight.
Sprint 5D last: Plan refresh cycle. The evolution.

5A can ship independently and deliver immediate value — the startup
brief becomes dramatically better when it reads a structured plan
instead of re-deriving priorities from raw dock content.

---

## The Lodestar Test

> "Design is philosophy expressed through constraint."

The structured plan expresses the philosophy that **the system should
understand the operator's journey, not just their commands.** The
constraint is that every update goes through the invariant pipeline,
every observation is logged, every change is approved, and every
artifact is human-readable.

The system doesn't just do what you ask. It understands what you're
trying to accomplish and helps you get there — not by guessing, but
by observing, proposing, and learning from your corrections.

That's a self-authoring system.
