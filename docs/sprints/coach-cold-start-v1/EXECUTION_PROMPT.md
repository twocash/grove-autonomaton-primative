# EXECUTION PROMPT: Coach Cold-Start v1

> Paste this entire prompt into a fresh Claude Code context window.
> Generated: 2026-03-19
> Sprint: `coach-cold-start-v1`
> Repo: `C:\github\grove-autonomaton-primative`

---

## PHASE 0: MANDATORY CODEBASE AUDIT

**Do this FIRST. Do not write any code until this is complete.**

The `reference-profile-v1` sprint just landed on main (commit `e0233cb`).
During that sprint's execution, a separate Claude session was editing sprint
doc files in `docs/sprints/` concurrently — which should never happen. There
may be file conflicts, stale references, or unexpected state.

### Audit Steps

1. **Pull latest and verify clean state:**
```bash
cd C:\github\grove-autonomaton-primative
git status
git log --oneline -5
```

2. **Verify three profiles exist and boot:**
```bash
python autonomaton.py --list-profiles
python autonomaton.py --profile coach_demo --skip-welcome --skip-queue
# Should boot with full coach_demo data (5+ dock sources, entities, etc.)
# Type "exit"

python autonomaton.py --profile reference --skip-welcome --skip-queue
# Should boot with glass pipeline, 0 dock sources
# Type "exit"

python autonomaton.py --profile blank_template --skip-welcome --skip-queue
# Should boot minimal
# Type "exit"
```

3. **Run full test suite:**
```bash
python -m pytest tests/ -v
```
Report: how many pass, how many fail, which fail.

4. **Verify key engine files are coherent:**
```bash
# Read these — look for anything broken or half-edited
```
Read (in this order):
- `CLAUDE.md` — the architectural invariants (constitution)
- `autonomaton.py` — entry point, REPL loop, startup sequence
- `engine/pipeline.py` — the five-stage invariant pipeline
- `engine/cognitive_router.py` — hybrid classification
- `engine/dispatcher.py` — handler registry
- `engine/compiler.py` — dock compilation + standing context
- `engine/cortex.py` — analytical lenses
- `engine/config_loader.py` — config loading including profile.yaml
- `engine/glass.py` — glass pipeline display (NEW from reference sprint)

5. **Verify the reference profile sprint artifacts:**
Read `docs/sprints/reference-profile-v1/` — check if SPEC.md, SPRINTS.md,
and EXECUTION_PROMPT.md are coherent or if they have artifacts from the
concurrent editing issue.

6. **Check for tmpclaude files that need cleanup:**
```bash
dir tmpclaude-* /b
```
These are Claude Code temp files that accumulate. Note them but don't
delete yet.

7. **Report findings before proceeding.** Tell me:
   - Test suite status (pass/fail count)
   - Any files that look half-edited or conflicted
   - Any profiles that fail to boot
   - Current state of `docs/sprints/` directory
   - Anything else that looks wrong

**Do NOT proceed to Phase 1 until I confirm the audit is clean.**

---

## PHASE 1: WHAT THIS SPRINT DOES

The `coach_demo` profile currently ships as a finished product: 5 dock
files, 6 player entities, 2 parent entities, 7+ content seeds, 3 pre-built
skills, a fully populated persona, pillars, zones, and routing config.

The Autonomaton Pattern's central claim is **self-authoring software**. The
demo must prove that by showing the growth journey, not the destination.

This sprint reworks `coach_demo` into a cold-start experience that begins
with a business plan and a toolbox, then grows through use.

### The Architectural Thesis: Autonomatons All the Way Down

Every "helper function" in this sprint — the entity scaffolder, the gap
alert, the pillar discoverer — is itself an autonomaton: a full five-stage
pipeline traversal. When the primary autonomaton detects a player name in
operator exhaust and invokes the scaffolder, that is one autonomaton calling
another. Same invariant pipeline. Same governance. Same telemetry.

**Implementation rule:** If it changes state, it goes through all five
stages. No utility functions that silently create files. When the scaffolder
creates `entities/players/jake-sullivan.md`, that is a Yellow Zone pipeline
traversal visible in the glass, logged in telemetry, governed by zones.

### Key Decisions (already made — do not revisit)

1. **This becomes the new `coach_demo`.** Archive the current one to
   `coach_archive`.
2. **Compressed timeline — use top-tier cognition.** Session Zero, gap
   analysis, scaffolding all use Tier 2 (Sonnet) aggressively. The Ratchet
   demotes stable patterns over time.
3. **Glass pipeline via `--glass` CLI flag.** Works on any profile.
   Coach_demo defaults to glass OFF. Reference profile has glass ON via
   profile.yaml.
4. **No pre-loaded telemetry.** Clean telemetry. The demo runs live.
5. **Scaffolder creates its own directories.** No pre-created entity
   subdirectories. When the scaffolder needs `entities/players/`, it
   creates it as part of execution.

---

## PHASE 2: THE COLD-START PACKAGE

The new `coach_demo` ships with exactly this:

### Dock (2 files)

**`dock/business-plan.md`** — Extracted from raw coach brain dump (below).
Reads like a coach talking about his ministry, NOT a developer spec.
Contains: mission, revenue model, content strategy outline, tithing mandate,
privacy commitment. References team/calendar/content as GOALS, not as things
the system already has.

**`dock/system/vision-board.md`** — 3-4 aspirations:
```
- [2026-03-01] I wish I could track each player's scoring trends —
  even just a simple way to see who's improving week over week.
- [2026-03-01] It would be cool if tournament prep was automatic —
  lineup, scouting, course strategy, the whole package.
- [2026-03-01] Someday I want automatic lesson reminders sent to
  parents 24 hours before a scheduled lesson.
```

### Config (lean)

- `persona.yaml` — Same Gabe persona, vibe updated: knows system is new
  and growing. Doesn't pretend to know the roster or calendar. Add
  constraint: "When asked about things you don't have yet (roster,
  calendar, content history), be honest. Say what you need and offer to
  start building it."
- `zones.schema` — Identical to current. Zone governance is structural.
- `routing.config` — Stripped to ~15 essential intents (listed below).
- `pillars.yaml` — Empty pillar list with schema structure only.
- `voice.yaml` — Defaults only.
- `models.yaml`, `mcp.config`, `cortex.yaml` — Unchanged copies.
- `pattern_cache.yaml` — Empty cache.

**Routing intents that ship on Day 0:**

| Intent | Zone | Tier | Handler |
|--------|------|------|---------|
| `general_chat` | Green | 1 | `general_chat` |
| `welcome_card` | Green | 2 | `welcome_card` |
| `startup_brief` | Green | 2 | `startup_brief` |
| `generate_plan` | Yellow | 2 | `generate_plan` |
| `dock_status` | Green | 1 | `status_display` |
| `queue_status` | Green | 1 | `status_display` |
| `skills_list` | Green | 1 | `status_display` |
| `operator_guide` | Green | 1 | `skill_executor` |
| `strategy_session` | Green | 2 | `strategy_session` |
| `session_zero` | Yellow | 2 | `session_zero_handler` |
| `entity_scaffold` | Yellow | 2 | `skill_executor` (NEW) |
| `vision_capture` | Green | 1 | `vision_capture` |
| `plan_update` | Yellow | 2 | `plan_update` |
| `regenerate_plan` | Yellow | 2 | `regenerate_plan` |
| `clear_cache` | Yellow | 1 | `clear_cache` |
| `pit_crew_build` | Red | 3 | `pit_crew` |

Plus ratchet sub-intents: `ratchet_intent_classify`, `ratchet_entity_extract`,
`ratchet_correction_detect`, `ratchet_gap_detect`.

**NOT included:** `content_compilation`, `tournament_prep`, `weekly_report`,
`compile_content`, `cortex_analyze`, `cortex_ratchet`, `cortex_evolve`,
`fill_entity_gap`, `email_parent`, `calendar_schedule`, `performance_report`,
`roster_update`, `payment_reminder`, `fee_adjustment`. These emerge through
the Skill Flywheel.

### Skills (4)

| Skill | Purpose |
|-------|---------|
| `operator-guide` | Self-documentation (house skill) |
| `welcome-card` | Startup briefing — updated to handle thin dock context |
| `session-zero-intake` | **Reworked** — plan-driven gap analysis bootstrap |
| `entity-scaffolder` | **NEW** — creates structured records from observed data |

### Everything else
Empty. `entities/` with `.gitkeep` only — NO subdirectories. No content
seeds. No output. No pre-loaded telemetry.

---

## PHASE 3: RAW COACH CONTEXT (source material for dock seed)

Use this to extract the business plan and vision board items. The system
should structure this voice — it shouldn't read like a developer wrote it.

```
To make this a true Grove Autonomaton, we have to strip away the idea of
a "software application" entirely. An Autonomaton doesn't have features;
it has a starting configuration, a Socratic intake, and a Skill Flywheel
that authors new capabilities based on the coach's exhaust.

If he has to manually set up a roster database, build a travel schedule,
or configure a budget tracker on Day 1, the system has failed the Extended
Mind test. The system must grow around his natural behavior.

The brand is @ChristInTheFairway — "Where the fairway meets faith."
The mission: build multi-platform content channels that teach golf through
Catholic spirituality, generating revenue that tithes back to community.
This is not a business. This is a ministry with a business model.

Revenue streams: YouTube (long-form), TikTok (short-form hooks), Instagram
(visual storytelling). Monetization via YouTube Partner Program, affiliate
partnerships, private lesson referrals, speaking engagements, merch (future).

Tithing mandate: 20%+ of all gross revenue, non-negotiable. Primary
beneficiaries: First Tee - Indiana, Bishop Chatard High School Golf Program,
St. Vincent de Paul Society. First $500/month split equally.

Content pillars (themes that keep coming up): short-game devotionals,
real Chatard stories (privacy-protected), swing thoughts as spiritual
parallels, failure and redemption, course beauty, local Indy Catholic golf.

Weekly volume targets: TikTok 5/week, Instagram 3/week, YouTube 1/week.
Voice: warm, relatable, non-preachy. Golf-first with faith as undercurrent.

Privacy commitment: because we work with minors, no student names ever
used in public content. All players referenced by anonymous descriptors.
This is enforced at the system level.

The team: Bishop Chatard Catholic High School golf program. Spring 2026
season. First match March 29 vs Cathedral at Eagle Creek Golf Club.
6-player varsity roster. Strong senior leadership, two promising freshmen.

The goal is not fame. The goal is faithfulness. The revenue is a tool
for mission.

Coach's aspirations mentioned in passing:
- Wishes he could track player scoring trends week over week
- Wants tournament prep to be automatic when a match is coming up
- Wants lesson reminders sent to parents automatically
- Thinks a weekly text reminder about which content seeds are ready
  would help with consistency
```

---

## PHASE 4: EPIC-BY-EPIC EXECUTION

### Epic A: Archive & New Profile Setup

**A.1: Archive current coach_demo**
Rename `profiles/coach_demo/` → `profiles/coach_archive/`.
Search codebase for hardcoded `coach_demo` path references in tests
and update to `coach_archive` where they reference the old profile's
specific content (entities, dock files, etc.). The default profile name
in `autonomaton.py` stays `coach_demo` — it will point to the new lean
profile.
Verify: `python autonomaton.py --profile coach_archive` boots with full
old data intact.

**A.2: Create new coach_demo directory structure**
```
profiles/coach_demo/
  config/
  dock/
  dock/system/
  entities/          (.gitkeep only — NO subdirectories)
  skills/
  skills/operator-guide/
  skills/welcome-card/
  skills/session-zero-intake/
  skills/entity-scaffolder/
  output/            (.gitkeep)
  queue/             (.gitkeep, empty .processed_events)
  telemetry/         (.gitkeep, empty telemetry.jsonl, empty llm_calls.jsonl)
```

**A.3: Write dock/business-plan.md**
Extract from the raw coach context in Phase 3 above. Coach's voice.
References team/calendar/content as goals, not existing infrastructure.

**A.4: Write dock/system/vision-board.md**
3-4 aspirations from Phase 3 source material.

**A.5: Write config/persona.yaml**
Same Gabe persona from `coach_archive`, updated vibe: system is new and
growing. Add constraint about honesty when roster/calendar don't exist yet.

**A.6: Write config/routing.config**
Only the ~15 intents from the table in Phase 2. Include ratchet sub-intents.
Copy tier definitions from coach_archive routing.config.

**A.7: Copy structural configs**
From `coach_archive`: zones.schema, models.yaml, mcp.config, cortex.yaml.
Write empty pattern_cache.yaml.

**A.8: Write minimal pillars.yaml**
Empty pillar list, correct schema structure:
```yaml
pillars: {}
calendar:
  weekly_cadence: {}
  platform_priority: []
  weekly_volume: {}
```

**A.9: Write minimal voice.yaml**
Defaults only. Will be populated during Session Zero.

**A.10: Copy and update house skills**
Copy operator-guide and welcome-card from coach_archive. Update
welcome-card prompt to handle thin dock — announce what system knows
and doesn't, offer Session Zero.

**Build Gate A:**
```bash
python autonomaton.py --profile coach_demo --skip-welcome
# "2 sources", "0 pending Kaizen"
python autonomaton.py --profile coach_archive --skip-welcome
# Full old data
python -m pytest tests/ -v
# All pass
```

---

### Epic B: Entity Scaffolder Skill

**B.1: Create entity-scaffolder skill files**
`skills/entity-scaffolder/SKILL.md`, `config.yaml`, `prompt.md`.
The prompt instructs the LLM to:
1. Read dock context to understand domain entity types
2. Generate markdown entity file with extracted attributes
3. Generate `## Gaps` section (fields business plan implies are needed
   but weren't provided)
4. Identify dependent entities (player → parent family)
5. Return structured JSON: file_content, file_path, gaps[], dependents[]

**B.2: Add entity_scaffold route to routing.config**
Yellow zone, Tier 2, handler: `skill_executor`, skill_name: `entity-scaffolder`.
Keywords: "create profile", "create entity", "add player", "add parent", "new entity".
Register as force_route target.

**B.3: Self-authoring directory creation**
When scaffolder writes to `entities/players/jake-sullivan.md` and
`entities/players/` doesn't exist, create the directory as part of
Stage 5 execution. Log directory creation in telemetry event.
NOT a separate pipeline traversal — part of the entity_scaffold execution.

**B.4: Gap section generation**
Scaffolder prompt generates contextually appropriate `## Gaps` from dock.
Player without parent contact = flagged gap. Player without handicap =
flagged gap. Gaps derived from business plan, not hardcoded.

**B.5: Dependent entity Kaizen proposals**
When scaffolder creates a player and detects no parent entity, write
Kaizen proposal to queue. Proposal triggers scaffolder again when approved
(autonomaton → autonomaton).

**Build Gate B:**
```bash
python autonomaton.py --profile coach_demo --skip-welcome
# "add player Jake Sullivan, senior, team captain"
# → Yellow Zone approval
# → entities/players/jake-sullivan.md created (directory auto-created)
# → Gaps section present
# → Kaizen for Sullivan family in queue
python -m pytest tests/test_entity_scaffolder.py -v
```

---

### Epic C: Plan-Driven Session Zero

**C.1: Implement gap_analyzer() in compiler.py**
Reads dock, identifies: entity categories referenced with no entities,
capabilities referenced with no skills, timelines with no seasonal context.
Returns prioritized gap map. This is a Tier 2 Sonnet call routed through
the pipeline.

**C.2: Rework session-zero-intake prompt.md**
Dynamic framework with slots. Receives gap map. Constructs intake questions
by operational urgency:
1. Entity gaps first (blocks operations)
2. Context gaps second (blocks awareness)
3. Capability gaps mentioned but not asked (builds trust)
4. Voice calibration last (enriches content)

Each answer returns structured JSON: entities_to_scaffold, dock_updates,
config_updates, voice_notes.

**C.3: Session Zero state persistence**
`queue/session-zero-state.yaml` tracks: status, phases_complete,
entities_scaffolded. Resumable across sessions.

**C.4: Wire Session Zero to scaffolder**
Entity intake answers → batch scaffolder invocation. Present batch approval:
"Approve all / Review individually / Cancel". Each entity gets own telemetry
event. Batch = single Yellow Zone approval covering multiple traversals.

**C.5: Session Zero dock/config writes**
Calendar answers → `dock/seasonal-context.md` via plan_update (Yellow).
Theme answers → `config/pillars.yaml` via config_update (Yellow).
Voice answers → `config/voice.yaml` via config_update (Yellow).
Each write is a pipeline traversal with approval.

**C.6: Post-Session Zero plan generation**
When all phases complete → auto-invoke `generate_plan`. First structured
plan reflects intake results: scaffolded entities, seasonal context, gaps.

**Build Gate C:**
```bash
python autonomaton.py --profile coach_demo
# Welcome card says system is new, offers Session Zero
# "session zero" → gap analysis → roster questions → entity scaffolding
# → calendar questions → seasonal context created
# → theme questions → pillars populated
# → voice calibration → voice.yaml updated
# → plan generated from new context
python -m pytest tests/test_session_zero_v2.py -v
```

---

### Epic D: Cortex Growth Triggers

**D.1: Lens 1 — entity extraction → scaffolder Kaizen**
When Lens 1 extracts a named entity with no file in entities/, write
Kaizen proposal instead of creating file directly. Scaffolder handles
creation through governance. Critical change: Cortex proposes, pipeline
executes.

**D.2: Lens 5 — vision board match → skill proposal**
Read vision-board.md. When telemetry pattern matches a stated aspiration
(e.g., repeated score mentions + "wish I could track scoring trends"),
propose skill with `vision_match: true`, elevated priority.

**D.3: Lens 6 — calendar signals → seasonal dock update**
Detect calendar/timeline references in telemetry not reflected in
seasonal-context.md. Propose dock updates.

**D.4: Lens 2 — content themes → pillar expansion**
When extracted themes recur but don't map to any configured pillar,
propose adding it to pillars.yaml.

**Build Gate D:**
```bash
python autonomaton.py --profile coach_demo
# (After Session Zero has run)
# Type coaching brain dump mentioning venues, dates, themes
# → Cortex tail pass fires Kaizen proposals for each detected gap
python -m pytest tests/test_cortex_growth.py -v
```

---

### Epic E: Test Suite

**E.1: Entity scaffolder tests** (8+ cases)
- Creates file through pipeline at correct path
- Creates directory when needed
- Generates contextual Gaps section
- Fires dependent entity Kaizen
- Respects Yellow Zone
- Telemetry includes all 5 stages
- Player entities include public_alias
- Batch approval creates multiple entities

**E.2: Session Zero v2 tests** (9+ cases)
- Gap analyzer priorities from business plan
- Empty entities/ detected as gap
- Missing seasonal-context.md detected as gap
- Contextual intake questions from gap map
- Entity intake triggers scaffolder
- Calendar intake writes seasonal-context.md
- Theme intake writes pillars.yaml
- State persists across interruptions
- Completion triggers plan generation

**E.3: Cortex growth tests** (6+ cases)
- Lens 1: unknown entity → scaffolder Kaizen (not direct write)
- Lens 2: recurring theme → pillar expansion Kaizen
- Lens 5: pattern + vision board → vision_match proposal
- Lens 6: calendar reference → seasonal update Kaizen
- All proposals have correct format
- Approved proposals trigger correct sub-autonomaton

**E.4: Integration test** (1 comprehensive)
Boot → Session Zero → entities → config → plan → exhaust → Cortex proposals

**E.5: Regression**
All existing tests pass. Fix any coach_demo path references → coach_archive.

**Build Gate E:**
```bash
python -m pytest tests/ -v
# ALL pass, zero regressions
```

---

## PHASE 5: ARCHITECTURAL CONSTRAINTS (NON-NEGOTIABLE)

1. **Everything through the pipeline.** The scaffolder is a skill routed
   through `skill_executor`. Stage 5 handles the write after Stage 4
   governance. No backdoor file writes.

2. **No pre-loaded entities.** The new coach_demo proves Profile Isolation
   by shipping with zero entities and growing a full roster through use.

3. **Session Zero is restartable.** State in queue, not engine memory.

4. **coach_archive is preserved.** Must still boot and function via
   `--profile coach_archive`.

5. **The scaffolder is domain-agnostic.** It reads the dock to understand
   entity types. A legal autonomaton would scaffold case files using the
   same skill pointed at a different business plan.

6. **The business plan is coach-voiced.** Not a developer spec.

7. **Sub-autonomatons are pipeline traversals.** Entity scaffolder, gap
   alert, pillar discovery, seasonal updater — each is a full five-stage
   traversal with telemetry and zone governance. This is the mesh.

---

## PHASE 6: KEY FILES TO READ

Before writing any code, read these for current architectural context:

```
CLAUDE.md                               — 12 invariants (the constitution)
autonomaton.py                          — REPL, startup sequence
engine/pipeline.py                      — five-stage invariant pipeline
engine/cognitive_router.py              — hybrid Tier 0/1/2 classification
engine/dispatcher.py                    — handler registry
engine/compiler.py                      — dock compilation, standing context
engine/cortex.py                        — analytical lenses (1-7)
engine/pit_crew.py                      — skill generation
engine/glass.py                         — glass pipeline display (NEW)
engine/config_loader.py                 — config loading, profile.yaml
engine/ux.py                            — Digital Jidoka approval UX
profiles/coach_demo/config/             — CURRENT coach config (will be archived)
profiles/coach_demo/skills/             — CURRENT skills (reference for rework)
profiles/reference/config/profile.yaml  — glass/tips/startup flag pattern
```

---

## PHASE 7: GIT DISCIPLINE

- Create a git worktree or work on a branch, NOT directly on main
- Commit after each epic's build gate passes
- Commit message format: `feat: coach-cold-start-v1 epic-{letter}`
- Final merge to main after all build gates pass
- Write .bat files for git operations (inline git commit with spaces
  fails on Windows cmd)

---

## Sub-Autonomaton Reference Table

| Sub-Autonomaton | Triggered By | Zone | Pipeline Path |
|-----------------|-------------|------|---------------|
| Entity Scaffolder | Session Zero, Cortex Lens 1, Operator | Yellow | `force_route="entity_scaffold"` → `skill_executor` |
| Gap Alert | Scaffolder (dependent entity) | Green | Kaizen queue → approval → scaffolder |
| Pillar Discovery | Session Zero, Cortex Lens 2 | Yellow | config_update sub-route |
| Seasonal Updater | Session Zero, Cortex Lens 6 | Yellow | plan_update route |
| Skill Proposer | Cortex Lens 5 + Vision Board | Red | Kaizen queue → Pit Crew |

Every row is a pipeline traversal. Every row generates telemetry.
Autonomatons all the way down.
