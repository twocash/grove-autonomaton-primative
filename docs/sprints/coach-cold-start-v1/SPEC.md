# SPRINT: Coach Cold-Start — Self-Evolving Profile Bootstrap

> *"Design is philosophy expressed through constraint."*
> Sprint Name: `coach-cold-start-v1`
> Generated: 2026-03-19
> Provenance: Autonomaton Play GTM — the demo must show growth, not a furnished house
> Dependency: Current master (post purity-audit-v2)

---

## Purpose

The coach_demo profile ships as a finished product: 5 dock files, 6 player
entities, 2 parent entities, 7+ content seeds, 3 pre-built skills, a fully
populated persona, pillars, zones, and routing config. This is Act 3
pretending to be Act 1.

The Autonomaton Pattern's central claim is self-authoring software. The demo
must prove that claim by showing the journey, not the destination.

This sprint reworks coach_demo into a cold-start experience that begins with
a plan and a toolbox, then grows through use.

---

## The Architectural Thesis: Autonomatons All the Way Down

Every "helper function" in this sprint — the entity scaffolder, the gap
alert, the pillar discoverer — is itself an autonomaton: a full five-stage
pipeline traversal that observes, classifies, compiles, approves, and
executes. When the primary autonomaton detects a player name in operator
exhaust and invokes the scaffolder, that is one autonomaton calling another.

This is the mesh. Same invariant pipeline. Same governance. Same telemetry.
Autonomatons composing with autonomatons — each one sovereign, each one
auditable, each one governed by zones.

**Implementation rule:** If it changes state, it goes through all five
stages. No utility functions that silently create files. When the scaffolder
creates `entities/players/jake-sullivan.md`, that is a Yellow Zone pipeline
traversal visible in the glass, logged in telemetry, governed by zones.

---

## Key Decisions

1. **This becomes the new `coach_demo`.** The current profile is archived
   to `coach_archive`. No expectation of keeping it in pushed git long-term.

2. **Compressed timeline — use top-tier cognition.** Session Zero intake,
   gap analysis, scaffolding all use Tier 2 (Sonnet) aggressively. The
   Ratchet demotes stable patterns to Tier 0 over time. Spending tokens
   on bootstrap is exactly the right use — the system gets cheaper with
   every interaction.

3. **Glass pipeline via feature flag.** `--glass` CLI flag enables glass
   annotations on ANY profile. No profile.yaml glass_pipeline field needed
   for coach_demo (it defaults to off). The reference profile has it on
   by default. Coach_demo users opt in with `--glass`.

4. **No pre-loaded telemetry.** Clean telemetry files. The demo runs live.

5. **Scaffolder creates its own directories.** No pre-created entity
   subdirectories beyond a top-level `entities/` with `.gitkeep`. When
   the scaffolder needs `entities/players/`, it creates it. More complex
   but more honest about self-authoring.

---

## The Cold-Start Package

The new `coach_demo` ships with:

### Dock (2 files)
- `dock/business-plan.md` — Extracted from raw coach brain dump. The
  system structured the coach's voice. Mission, revenue model, content
  strategy outline, tithing mandate, privacy commitment.
- `dock/system/vision-board.md` — 3-4 aspirations from the coach.

### Config (lean but functional)
- `persona.yaml` — Same Gabe, updated vibe: acknowledges system is new.
- `zones.schema` — Identical to current. Zone governance is structural.
- `routing.config` — Stripped to ~15 essential intents. No content_compilation,
  tournament_prep, weekly_report, email_parent, calendar_schedule, or
  performance_report. These emerge through the Skill Flywheel.
- `pillars.yaml` — Empty pillar list with schema structure only.
- `voice.yaml` — Defaults only.
- `models.yaml`, `mcp.config` — Unchanged.

### Skills (4 — house skills + scaffolder)
- `operator-guide` — Self-documentation (all profiles)
- `welcome-card` — Startup briefing (all profiles)
- `session-zero-intake` — **Reworked**: plan-driven bootstrap
- `entity-scaffolder` — **NEW**: creates structured records from observed data

### Everything else
Empty. `entities/` with `.gitkeep` only. No subdirectories. No content
seeds. No output. No pre-loaded telemetry.

---

## The Entity Scaffolder (Sub-Autonomaton)

A skill that creates structured entity records when the system discovers
it needs them. Domain-agnostic in mechanism, domain-aware through dock.

**Trigger paths:**
- Cortex Lens 1 detects named entity with no matching file → Kaizen proposal
- Session Zero gap analysis identifies missing entity category → direct invocation

**Self-authoring directories:** When the scaffolder needs `entities/players/`
and it doesn't exist, it creates the directory as part of execution. The
directory structure is discovered, not pre-configured.

**Gap modeling:** Every scaffolded entity includes a `## Gaps` section
identifying what the system DOESN'T know. Player without parent contact =
flagged gap. The system models its own ignorance.

**Mesh composition:** Scaffolder detects dependent entity gaps → fires
Kaizen proposal for related entities. Player → parent. Venue → schedule.
Autonomaton calling autonomaton.

---

## Plan-Driven Session Zero (Reworked)

**Current:** 3 fixed Socratic questions (mission, voice, tithing).
**New:** Gap analysis of business plan drives the intake.

Phase 1: Plan Analysis (Green Zone) — system reads dock, builds gap map
identifying referenced entity categories, capabilities, timelines, and
governance requirements that have no backing structure.

Phase 2: Priority Intake (Yellow Zone) — asks questions in operational
urgency order. Each answer triggers the scaffolder or writes to dock/config
through the pipeline.

Phase 3: Voice Calibration (unchanged) — story and tithing questions for
content engine and mission alignment.

Session state persists in `queue/session-zero-state.yaml`. Interruptible
and resumable across sessions.

---

## What Success Looks Like

**Boot:** System announces it has a plan but no people, calendar, or content
themes. Offers to run intake.

**Minutes 1-10:** Coach describes team. Each player triggers the scaffolder
(visible with `--glass`). By end of intake: 4-6 player entities, content
pillars configured, seasonal context seeded.

**Week 1:** Coach uses system naturally. Cortex detects patterns, proposes
skills. Tournament prep emerges from vision board match. Content seeds
captured from coaching exhaust.

**Week 2-3:** System output indistinguishable from current pre-loaded
coach_demo. But every piece of infrastructure was proposed, approved, and
built through the pipeline. The architecture compounded.

---

## Epic Structure

### Epic A: Archive & New Profile Setup
Archive current coach_demo. Create lean new profile with dock seed,
minimal config, and directory structure.

### Epic B: Entity Scaffolder Skill
Build the sub-autonomaton that creates structured entity records,
including self-authoring directory creation and gap modeling.

### Epic C: Plan-Driven Session Zero
Rework session-zero-intake from scripted questionnaire to gap-driven
bootstrap that reads the business plan and discovers what's missing.

### Epic D: Cortex Growth Triggers
Wire Cortex lenses to detect growth opportunities from operator exhaust
and cross-reference against existing entities, skills, and config.

### Epic E: Test Suite
Scaffolder tests, session zero tests, cortex growth tests, integration
test for the full cold-start → growth arc.

---

## Sequencing & Gates

```
Epic A (Profile Setup) ──→ GATE: coach_demo boots lean, 2 dock sources, 0 entities
        │
Epic B (Scaffolder) ─────→ GATE: entity_scaffold creates file through pipeline with approval
        │
Epic C (Session Zero) ───→ GATE: gap analysis → intake → scaffolder → entities populated
        │
Epic D (Cortex Growth) ──→ GATE: exhaust triggers entity/skill/config proposals
        │
Epic E (Tests) ──────────→ GATE: all new + existing tests pass, zero regressions
```

Epics A→B→C are sequential (each depends on the prior). Epic D can
partially parallel with C (Lens 1 integration only requires B). Epic E
runs last.

---

## Files Touched

| File | Epic | Change Type |
|------|------|-------------|
| `profiles/coach_archive/` | A | Move — renamed from coach_demo |
| `profiles/coach_demo/` | A | New — lean cold-start profile |
| `profiles/coach_demo/dock/business-plan.md` | A | New — extracted from raw coach voice |
| `profiles/coach_demo/dock/system/vision-board.md` | A | New — 3-4 aspirations |
| `profiles/coach_demo/config/*.yaml` | A | New — lean configs |
| `profiles/coach_demo/config/routing.config` | A | New — ~15 essential intents |
| `profiles/coach_demo/skills/entity-scaffolder/` | B | New — skill files |
| `engine/dispatcher.py` | B | Modify — register entity_scaffold handler |
| `profiles/coach_demo/skills/session-zero-intake/` | C | Rework — dynamic prompt |
| `engine/compiler.py` | C | Modify — add gap_analyzer() |
| `engine/cortex.py` | D | Modify — growth triggers in Lenses 1, 2, 5, 6 |
| `autonomaton.py` | A | Modify — default profile stays coach_demo |
| `QUICKSTART.md` | A | Modify — cold-start walkthrough |
| `tests/test_entity_scaffolder.py` | E | New |
| `tests/test_session_zero_v2.py` | E | New |
| `tests/test_cortex_growth.py` | E | New |

---

## Domain Contract

**Applicable contract:** Autonomaton Architect (Anti-Code-Party Protocol)
**Contract version:** 1.0
**Additional requirements:** Config over code. No new imperative patterns.
Every state change through the pipeline. Sub-autonomatons are pipeline
traversals, not function calls.
