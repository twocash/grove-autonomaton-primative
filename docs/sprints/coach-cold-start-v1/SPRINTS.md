# SPRINTS.md — Coach Cold-Start v1: Story-Level Breakdown

> Sprint: `coach-cold-start-v1`
> Generated: 2026-03-19

---

## Epic A: Archive & New Profile Setup

### Story A.1: Archive current coach_demo
**Task:** Rename `profiles/coach_demo/` to `profiles/coach_archive/`.
Update any references in tests or docs that hardcode `coach_demo` paths
(search for `coach_demo` across the codebase). The archive profile must
still boot and function identically via `--profile coach_archive`.
**Acceptance:** `python autonomaton.py --profile coach_archive` produces
the same output as the current coach_demo. `--list-profiles` shows both
`coach_demo` and `coach_archive`.

### Story A.2: Create new coach_demo directory structure
**Task:** Create `profiles/coach_demo/` with:
```
config/
dock/
dock/system/
entities/          (with .gitkeep only — NO subdirectories)
skills/
skills/operator-guide/
skills/welcome-card/
skills/session-zero-intake/
skills/entity-scaffolder/
output/            (with .gitkeep)
queue/             (with .gitkeep, empty .processed_events)
telemetry/         (with .gitkeep, empty telemetry.jsonl, empty llm_calls.jsonl)
```
**Acceptance:** Directory structure exists. No entity subdirectories.
`--list-profiles` shows `coach_demo`.

### Story A.3: Extract business plan from raw coach context
**Task:** Write `dock/business-plan.md` extracted from the raw coach
context document (the brain dump supplied in the project instructions).
This should read like a coach talking about his ministry, NOT like a
developer-written specification. Include: mission statement ("this is
a ministry with a business model"), content strategy outline (TikTok,
Instagram, YouTube), tithing mandate (20% non-negotiable), privacy
commitment (minors — no real names), revenue path, beneficiary split.
Strip anything that assumes pre-existing system infrastructure (roster,
calendar, skills). The plan references these as GOALS, not as things
the system already has.
**Acceptance:** Document reads in the coach's voice. References team,
calendar, content as aspirational. No mention of system skills, entities,
or config that doesn't exist yet.

### Story A.4: Seed vision board
**Task:** Write `dock/system/vision-board.md` with 3-4 aspirations
extracted from the coach context:
```markdown
# Vision Board
> *A scratchpad for aspirations and future automation ideas*
---
## Aspirations
- [2026-03-01] I wish I could track each player's scoring trends —
  even just a simple way to see who's improving week over week.
- [2026-03-01] It would be cool if tournament prep was automatic —
  lineup, scouting, course strategy, the whole package.
- [2026-03-01] Someday I want automatic lesson reminders sent to
  parents 24 hours before a scheduled lesson.
```
**Acceptance:** 3-4 vision board items. Natural coach voice. Each maps
to a future skill the system could propose.

### Story A.5: Write lean persona.yaml
**Task:** Create `config/persona.yaml` using the existing Gabe persona
with an updated vibe section. Key addition: Gabe is aware the system is
new and growing. He doesn't pretend to know the roster, calendar, or
content pipeline. He knows the plan and starts from there. Same
constraints (no golf puns, no hype, no deference, no COS language).
Add constraint: "When asked about things you don't have yet (roster,
calendar, content history), be honest. Say what you need and offer to
start building it."
**Acceptance:** Persona loads. LLM responses acknowledge system is new
when dock context is thin.

### Story A.6: Write lean routing.config
**Task:** Create `config/routing.config` with ONLY these intents:

**Conversational:**
- `general_chat` — Green, Tier 1

**System (programmatic):**
- `welcome_card` — Green, Tier 2
- `startup_brief` — Green, Tier 2
- `generate_plan` — Yellow, Tier 2

**Informational:**
- `dock_status` — Green, Tier 1
- `queue_status` — Green, Tier 1
- `skills_list` — Green, Tier 1
- `operator_guide` — Green, Tier 1

**Operational:**
- `strategy_session` — Green, Tier 2
- `session_zero` — Yellow, Tier 2
- `entity_scaffold` — Yellow, Tier 2 (NEW)
- `vision_capture` — Green, Tier 1
- `plan_update` — Yellow, Tier 2
- `regenerate_plan` — Yellow, Tier 2
- `clear_cache` — Yellow, Tier 1
- `pit_crew_build` — Red, Tier 3

**Explicitly NOT included:** `content_compilation`, `tournament_prep`,
`weekly_report`, `compile_content`, `cortex_analyze`, `cortex_ratchet`,
`cortex_evolve`, `fill_entity_gap`, `email_parent`, `calendar_schedule`,
`performance_report`, `roster_update`, `payment_reminder`, `fee_adjustment`.

Include ratchet sub-intents: `ratchet_intent_classify`,
`ratchet_entity_extract`, `ratchet_correction_detect`, `ratchet_gap_detect`.

Copy tier definitions from current routing.config unchanged.

**Acceptance:** All 15+ intents route correctly. No routes reference
handlers or skills that don't exist in the lean profile.

### Story A.7: Copy structural configs
**Task:** Copy unchanged from current coach_demo (or blank_template):
- `config/zones.schema` — identical zone governance
- `config/models.yaml` — identical tier-to-model mapping
- `config/mcp.config` — identical MCP definitions
- `config/pattern_cache.yaml` — empty cache: `cache: {}`
- `config/cortex.yaml` — identical cortex config

**Acceptance:** All config files load without error.

### Story A.8: Write minimal pillars.yaml
**Task:** Create `config/pillars.yaml` with empty pillar list but correct
schema structure:
```yaml
# pillars.yaml — Content pillars (discovered through Session Zero and use)
pillars: {}
calendar:
  weekly_cadence: {}
  platform_priority: []
  weekly_volume: {}
```
**Acceptance:** Config loads. Content engine handles empty pillars gracefully
(no crash, returns "no pillars configured").

### Story A.9: Write minimal voice.yaml
**Task:** Create `config/voice.yaml` with defaults only:
```yaml
# voice.yaml — Voice calibration (populated during Session Zero)
tone: "warm, authentic, faith as undercurrent"
register: "peer to peer, not performer"
avoid:
  - religious clichés in casual conversation
  - golf puns
  - hype language
signature_phrases: []
```
**Acceptance:** Config loads. Content engine uses defaults until calibrated.

### Story A.10: Copy house skills
**Task:** Copy `skills/operator-guide/prompt.md` and
`skills/welcome-card/` from current coach_demo. Update the welcome-card
prompt to handle thin dock context — when the system has only a business
plan and vision board, the briefing should acknowledge what it knows and
what it doesn't, and offer to run Session Zero.
**Acceptance:** `help` works. Welcome card at startup announces system
is new and offers intake.

### Build Gate A
```bash
python autonomaton.py --profile coach_demo --skip-welcome
# Boots clean: "2 sources", "0 pending Kaizen item(s)"
# Type "dock" → shows 2 sources (business-plan.md, vision-board.md)
# Type "skills" → shows 4 skills (operator-guide, welcome-card,
#   session-zero-intake, entity-scaffolder)
# Type "exit" → clean shutdown
python autonomaton.py --profile coach_archive --skip-welcome
# Boots with full old coach_demo data intact
python -m pytest tests/ -v
# All existing tests pass (may need path updates for coach_archive)
```

---

## Epic B: Entity Scaffolder Skill

### Story B.1: Create entity-scaffolder skill files
**Task:** Create `skills/entity-scaffolder/` with three files:

**`SKILL.md`:**
```markdown
# Entity Scaffolder
Creates structured entity records when the system discovers it needs them.
Domain-agnostic mechanism, domain-aware through dock context.
## Trigger Paths
- Cortex Lens 1: named entity detected with no matching file
- Session Zero: gap analysis identifies missing entity category
- Operator request: "create a player profile for..."
## Zone: Yellow (creates files)
## Tier: 2 (Sonnet — needs to generate appropriate entity structure)
```

**`config.yaml`:**
```yaml
name: entity-scaffolder
zone: yellow
tier: 2
description: "Create structured entity records from observed data"
inputs:
  - entity_name      # required: "Jake Sullivan"
  - entity_type      # optional: "player", "parent", "venue" (inferred from dock if omitted)
  - attributes       # optional: dict of known attributes
  - source           # required: "session_zero", "cortex_lens_1", "operator"
outputs:
  - entity_file_path
  - gaps_identified
  - dependent_entities_proposed
```

**`prompt.md`:**
Instruct the LLM to:
1. Read the dock context (business plan) to understand domain entity types
2. Determine appropriate entity structure for this domain
3. Generate markdown entity file with extracted attributes
4. Identify gaps — fields the business plan implies are needed but weren't
   provided (e.g., parent contact for a player entity when business plan
   mentions "parent communication")
5. Identify dependent entities (player → parent family)
6. Return structured JSON with: file_content, file_path, gaps[], dependents[]

**Acceptance:** Skill files exist and parse correctly. Prompt produces
well-structured entity markdown when tested manually.

### Story B.2: Add entity_scaffold route to routing.config
**Task:** Add the `entity_scaffold` intent to the lean routing.config:
```yaml
entity_scaffold:
  tier: 2
  zone: yellow
  domain: entities
  intent_type: actionable
  description: "Create structured entity record from observed data"
  keywords:
    - "create profile"
    - "create entity"
    - "add player"
    - "add parent"
    - "new entity"
  handler: "skill_executor"
  handler_args:
    skill_name: "entity-scaffolder"
```
Also register as a `force_route` target so Cortex and Session Zero can
invoke it programmatically.
**Acceptance:** "add player Jake Sullivan" routes to entity_scaffold.
`force_route="entity_scaffold"` dispatches correctly.

### Story B.3: Self-authoring directory creation
**Task:** In the skill_executor handler (or in a pre-execution hook within
the scaffolder flow), when the target entity path requires a directory that
doesn't exist, create it. Example: scaffolder wants to write
`entities/players/jake-sullivan.md` but `entities/players/` doesn't exist.
The handler creates the directory, logs the creation in telemetry as a
sub-event ("directory entities/players/ created"), then writes the file.

**Implementation:** The scaffolder's LLM response includes `file_path`
(e.g., `entities/players/jake-sullivan.md`). The execution step checks
if the parent directory exists. If not, creates it. This is NOT a separate
pipeline traversal — it's part of Stage 5 execution for the entity_scaffold
intent. The directory creation is logged in the telemetry event's `inferred`
dict.

**Acceptance:** Scaffolder creates `entities/players/` when it doesn't
exist. Telemetry event records directory creation. Second player entity
written to same directory without re-creation.

### Story B.4: Gap section generation
**Task:** The scaffolder prompt instructs the LLM to generate a `## Gaps`
section in every entity file. Gaps are fields the dock context implies are
needed but weren't provided. The LLM reads the business plan and determines
what's missing.

For a player entity created with only name and grade:
```markdown
## Gaps
- [ ] Handicap not recorded
- [ ] Parent/family contact info not captured
- [ ] Public alias not set (required for external content)
```

For a parent entity created as a stub:
```markdown
## Gaps
- [ ] Email address not captured
- [ ] Phone number not captured
- [ ] Preferred contact method unknown
```

**Acceptance:** Every scaffolded entity has a Gaps section. Gaps are
contextually appropriate to the domain (derived from business plan, not
hardcoded).

### Story B.5: Dependent entity Kaizen proposals
**Task:** When the scaffolder creates an entity and identifies dependent
entities (player → parent family), it writes a Kaizen proposal to the
queue:
```yaml
- id: scaffold-dep-{timestamp}
  trigger: entity_scaffolder
  type: dependent_entity
  proposal: "Jake Sullivan's family has no contact entity. Business plan
    requires parent communication for tournament logistics. Create a
    Sullivan family contact profile?"
  action: "entity_scaffold"
  priority: medium
  metadata:
    parent_entity: "entities/players/jake-sullivan.md"
    proposed_entity_type: "parent"
    proposed_entity_name: "Sullivan Family"
```

The Kaizen proposal fires through the existing queue mechanism. When
approved at next startup (or during session via `queue` command), it
invokes the scaffolder again — autonomaton calling autonomaton.

**Acceptance:** Scaffolder writes Kaizen for dependent entities. Queue
shows proposal. Approval triggers scaffolder for the dependent.

### Build Gate B
```bash
python autonomaton.py --profile coach_demo --skip-welcome
# Type: "add player Jake Sullivan, senior, team captain"
# → Yellow Zone approval prompt
# → Approve
# → entities/players/jake-sullivan.md created
# → Gaps section present
# → Kaizen proposal for Sullivan family in queue
# Type: "queue"
# → Shows pending Sullivan family proposal
python -m pytest tests/test_entity_scaffolder.py -v
```

---

## Epic C: Plan-Driven Session Zero

### Story C.1: Implement gap_analyzer in compiler.py
**Task:** Add a `gap_analyzer()` function to `engine/compiler.py` that:
1. Reads all dock files (business plan is the primary source)
2. Scans for references to entity categories (people, locations,
   organizations, timelines, financial entities)
3. Cross-references against existing `entities/` directory contents
4. Scans for references to capabilities (content creation, scheduling,
   reporting, communication)
5. Cross-references against deployed `skills/` directory
6. Scans for timeline references (dates, seasons, deadlines)
7. Cross-references against `dock/seasonal-context.md` existence
8. Returns a prioritized gap map:
```python
{
    "entity_gaps": [
        {"category": "players", "evidence": "mentions 'golf team', 'roster'",
         "priority": "high", "reason": "blocks roster management"},
        {"category": "parents", "evidence": "mentions 'parent communication'",
         "priority": "medium", "reason": "blocks tournament logistics"},
    ],
    "capability_gaps": [
        {"capability": "content_compilation", "evidence": "mentions TikTok, Instagram, YouTube",
         "priority": "medium", "reason": "blocks content pipeline"},
    ],
    "context_gaps": [
        {"context": "seasonal", "evidence": "mentions 'first match', 'season'",
         "priority": "high", "reason": "blocks calendar awareness"},
    ]
}
```

This is a Tier 2 (Sonnet) call — the LLM reads the business plan and
produces the structured gap analysis. Route through `run_pipeline` with
`force_route="session_zero"` sub-traversal.

**Acceptance:** Gap analyzer reads business plan, returns prioritized
gaps. Empty entities/ = entity gaps detected. No seasonal-context.md =
context gap detected.

### Story C.2: Rework session-zero-intake prompt.md
**Task:** Replace the current fixed 3-question prompt with a dynamic
framework. The prompt receives the gap map (from C.1) as context and
constructs intake questions specific to what's missing.

**Prompt structure:**
```markdown
# Session Zero: Plan-Driven Bootstrap

You are helping the operator set up their system. You have read
their business plan and identified what's missing.

## Gap Map (injected at runtime)
{gap_map}

## Intake Priorities

For each gap category, ask ONE focused question in priority order.
Do not ask about categories that have no gaps.

### Entity Gaps (ask first — blocks operations)
Ask about the highest-priority entity gap. Let the operator describe
multiple entities in a single response. For each entity mentioned,
output a structured entity block that the scaffolder can consume.

### Context Gaps (ask second — blocks awareness)
Ask about timelines, calendar, seasonal context. Extract dates,
opponents, venues, deadlines.

### Capability Gaps (mention, don't ask — builds trust)
Don't ask "do you want a content compilation skill?" Instead, note:
"Your plan mentions a content strategy across three platforms. Once
we have your team and calendar set up, I'll be able to start helping
with content. One thing at a time."

### Voice Calibration (ask last — enriches content)
"Tell me a quick story about a player moment that stuck with you."
Extract voice characteristics, signature phrases, storytelling patterns.

## Output Format
For each intake answer, return JSON:
{
  "entities_to_scaffold": [...],
  "dock_updates": {...},
  "config_updates": {...},
  "voice_notes": {...}
}
```

**Acceptance:** Session Zero generates contextually appropriate questions
based on gap map. Player intake → entity JSON. Calendar intake → seasonal
context. Voice intake → voice calibration notes.

### Story C.3: Session Zero state persistence
**Task:** Create `queue/session-zero-state.yaml` that tracks intake
progress:
```yaml
status: in_progress  # not_started | in_progress | complete
started: 2026-03-19T10:00:00Z
last_interaction: 2026-03-19T10:15:00Z
phases_complete:
  plan_analysis: true
  entity_intake: false
  context_intake: false
  voice_calibration: false
gap_map_snapshot: {...}  # Frozen at session start
entities_scaffolded: []
```

When session-zero is invoked and state exists with `in_progress`,
resume from the next incomplete phase. When all phases complete,
set status to `complete` and trigger `generate_plan`.

**Acceptance:** Session Zero interrupted mid-intake → resumes on next
invocation. Completed Session Zero triggers plan generation.

### Story C.4: Wire Session Zero to scaffolder
**Task:** When Session Zero's entity intake phase produces
`entities_to_scaffold`, invoke the entity scaffolder for each entity
via `run_pipeline(force_route="entity_scaffold")`. Each scaffolder
invocation is a sub-autonomaton — full pipeline traversal with Yellow
Zone approval.

For UX efficiency: batch approval. After the LLM extracts multiple
entities from a single operator response, present them as a batch:
```
I'd like to create profiles for:
  • Jake Sullivan — Senior, Team Captain
  • Marcus Henderson — Freshman, putting focus
  • Tommy Reeves — Junior, #2 player

These will be stored in your private roster.
No real names appear in public content. OK?

[1] Approve all  [2] Review individually  [3] Cancel
```

Option 1 = approve all as a batch (single Yellow Zone approval covering
multiple entity_scaffold pipeline traversals). Option 2 = individual
approval for each. Each traversal still gets its own telemetry event.

**Acceptance:** Operator describes 3 players → 3 entity files created
after single batch approval. 3 telemetry events logged. 3 dependent
entity Kaizen proposals (for families) written to queue.

### Story C.5: Session Zero dock/config writes
**Task:** When Session Zero produces `dock_updates` or `config_updates`:
- Calendar/timeline answers write to `dock/seasonal-context.md` via
  `plan_update` route (Yellow Zone)
- Content theme answers write to `config/pillars.yaml` via a new
  `config_update` sub-route (Yellow Zone)
- Voice calibration writes to `config/voice.yaml` via `config_update`
  (Yellow Zone)

Each write is a pipeline traversal. Each requires approval. The system
is writing its own configuration through governance.

**Acceptance:** Session Zero calendar answer → seasonal-context.md created.
Theme answer → pillars.yaml populated. Voice answer → voice.yaml updated.
All writes appear in telemetry.

### Story C.6: Post-Session Zero plan generation
**Task:** When Session Zero completes (all phases marked complete in state
file), automatically invoke `generate_plan` via `run_pipeline(
force_route="generate_plan")`. The structured plan now reads a dock with
real entities, seasonal context, and content pillars — not just a business
plan. First plan should reflect: "Here's what we built during intake,
here's what's still missing, here's what to focus on this week."

**Acceptance:** Session Zero completion triggers plan generation. Generated
plan references scaffolded entities, seasonal context, and identified gaps.

### Build Gate C
```bash
python autonomaton.py --profile coach_demo
# Welcome card announces system is new, offers Session Zero
# Type: "session zero" or "start intake"
# → Gap analysis runs (Green Zone)
# → First question about team roster
# → Operator describes players
# → Batch approval for entity scaffolding
# → Entity files created with gaps
# → Next question about calendar
# → seasonal-context.md created
# → Next question about content themes
# → pillars.yaml populated
# → Voice calibration question
# → voice.yaml updated
# → Session Zero complete → plan generated
# → Startup brief reflects newly built context
python -m pytest tests/test_session_zero_v2.py -v
```

---

## Epic D: Cortex Growth Triggers

### Story D.1: Lens 1 — Entity extraction → scaffolder Kaizen
**Task:** In `engine/cortex.py`, modify Lens 1 (Entity Extraction) to
cross-reference extracted entities against existing files in `entities/`.
When a named entity is detected in telemetry that has no corresponding
file, write a Kaizen proposal:
```yaml
- id: lens1-entity-{timestamp}
  trigger: cortex_lens_1
  type: entity_discovery
  proposal: "You mentioned 'Eagle Creek' — no venue entity exists.
    Want me to create a venue profile for Eagle Creek Golf Club?"
  action: "entity_scaffold"
  priority: medium
  metadata:
    entity_name: "Eagle Creek Golf Club"
    entity_type: "venue"
    source_event: "{telemetry_event_id}"
```

**Implementation detail:** Lens 1 currently extracts entities and writes
them to entity files. Change behavior: when entity file doesn't exist,
write a Kaizen proposal INSTEAD of creating the file directly. The
scaffolder (via Kaizen approval) handles creation through the pipeline.
This is critical — Lens 1 must not bypass governance.

**Acceptance:** Operator mentions a name not in entities/ → Kaizen
proposal appears. Approval triggers scaffolder. No direct entity writes
from Cortex.

### Story D.2: Lens 5 — Vision board match → skill proposal
**Task:** Modify Lens 5 (Evolution/PPM) to read
`dock/system/vision-board.md` and cross-reference against telemetry
patterns. When operator behavior aligns with a stated aspiration, mark
the proposal with `vision_match: true` and prioritize for Pit Crew.

Example: Vision board says "I wish I could track scoring trends."
Telemetry shows 3+ mentions of scores in the last 10 events. Lens 5
proposes:
```yaml
- id: lens5-vision-{timestamp}
  trigger: cortex_lens_5
  type: skill_proposal
  proposal: "You keep mentioning match scores, and you wished for
    scoring trend tracking. Want me to build a score tracker skill?"
  vision_match: true
  priority: high
```

**Acceptance:** Telemetry pattern matching vision board aspiration →
proposal with `vision_match: true`. Priority elevated above non-matched
proposals.

### Story D.3: Lens 6 — Calendar signals → seasonal dock update
**Task:** Modify Lens 6 (Context Gardener) to detect calendar/timeline
references in telemetry that aren't reflected in `dock/seasonal-context.md`
(or when the file doesn't exist at all). Propose dock updates.

Example: Operator says "Brebeuf match is April 5 at Riverside." Seasonal
context doesn't mention Brebeuf. Lens 6 proposes:
```yaml
- id: lens6-calendar-{timestamp}
  trigger: cortex_lens_6
  type: plan_update
  proposal_type: seasonal_update
  proposal: "You mentioned a match vs. Brebeuf on April 5 at Riverside.
    Update seasonal context with this event?"
  target_file: "dock/seasonal-context.md"
  priority: medium
```

**Acceptance:** Calendar reference in exhaust → seasonal update proposal.
Approval writes to dock through pipeline.

### Story D.4: Lens 2 — Content themes → pillar expansion
**Task:** Modify Lens 2 (Content Seed Mining) to check extracted content
themes against `config/pillars.yaml`. When a theme recurs in telemetry
but doesn't map to any configured pillar, propose adding it:
```yaml
- id: lens2-pillar-{timestamp}
  trigger: cortex_lens_2
  type: config_update
  proposal: "Your coaching conversations keep touching on 'patience
    under pressure.' This could be a strong content pillar. Add it?"
  target_file: "config/pillars.yaml"
  priority: low
```

**Acceptance:** Recurring theme with no matching pillar → pillar
expansion proposal. Approval writes to pillars.yaml.

### Build Gate D
```bash
python autonomaton.py --profile coach_demo
# (Assumes Session Zero has run — some entities exist)
# Type: "Practice was rough. Danny and Marcus both left putts short
#   at Eagle Creek. Also, Brebeuf match is April 5 at Riverside."
# → Cortex tail pass detects:
#   - "Eagle Creek" → no venue entity → scaffolder Kaizen (Lens 1)
#   - "Brebeuf match April 5" → not in seasonal context → dock update Kaizen (Lens 6)
#   - Score mention pattern → if matches vision board → skill proposal (Lens 5)
# Type: "queue" → shows pending proposals
python -m pytest tests/test_cortex_growth.py -v
```

---

## Epic E: Test Suite

### Story E.1: Entity scaffolder tests
**Task:** Create `tests/test_entity_scaffolder.py`:
- Scaffolder creates entity file at correct path through pipeline
- Scaffolder creates directory when it doesn't exist
- Scaffolder generates contextually appropriate Gaps section
- Scaffolder fires Kaizen for dependent entities
- Scaffolder respects Yellow Zone (requires approval)
- Scaffolder telemetry includes all 5 pipeline stages
- Privacy: player entities include `public_alias` field
- Batch approval creates multiple entities with individual telemetry
**Tests:** 8 test cases minimum.

### Story E.2: Session Zero v2 tests
**Task:** Create `tests/test_session_zero_v2.py`:
- Gap analyzer produces correct priorities from business plan
- Gap analyzer detects empty entities/ as entity gap
- Gap analyzer detects missing seasonal-context.md as context gap
- Session Zero generates contextually appropriate intake questions
- Entity intake triggers scaffolder for each entity
- Calendar intake writes seasonal-context.md through pipeline
- Theme intake writes pillars.yaml through pipeline
- Session Zero state persists across interruptions
- Completed Session Zero triggers plan generation
**Tests:** 9 test cases minimum.

### Story E.3: Cortex growth trigger tests
**Task:** Create `tests/test_cortex_growth.py`:
- Lens 1: unknown entity in telemetry → scaffolder Kaizen (not direct write)
- Lens 2: recurring theme with no pillar match → pillar expansion Kaizen
- Lens 5: telemetry pattern matching vision board → `vision_match: true`
- Lens 6: calendar reference not in seasonal context → dock update Kaizen
- All Kaizen proposals have correct format and priority
- Approved Kaizen proposals trigger correct sub-autonomaton
**Tests:** 6 test cases minimum.

### Story E.4: Integration test — cold start to growth
**Task:** Create integration test that scripts the full arc:
1. Boot coach_demo → verify 2 dock sources, 0 entities
2. Run Session Zero with mocked operator responses
3. Verify entities created, config updated, plan generated
4. Simulate operator exhaust with entity/calendar/theme mentions
5. Verify Cortex produces correct Kaizen proposals
6. Approve proposals, verify growth (new entities, updated dock)
**Tests:** 1 comprehensive integration test.

### Story E.5: Regression tests
**Task:** Run full existing test suite against new profile structure.
Fix any tests that reference `coach_demo` paths that now point to
`coach_archive`. Verify coach_archive profile passes all tests that
the old coach_demo passed.
**Tests:** All existing tests pass. Zero regressions.

### Build Gate E
```bash
python -m pytest tests/test_entity_scaffolder.py -v    # 8+ pass
python -m pytest tests/test_session_zero_v2.py -v      # 9+ pass
python -m pytest tests/test_cortex_growth.py -v        # 6+ pass
python -m pytest tests/ -v                              # ALL pass
```

---

## Summary: File Manifest

**New files (~20):**
```
profiles/coach_demo/config/persona.yaml
profiles/coach_demo/config/routing.config
profiles/coach_demo/config/zones.schema
profiles/coach_demo/config/models.yaml
profiles/coach_demo/config/mcp.config
profiles/coach_demo/config/cortex.yaml
profiles/coach_demo/config/pattern_cache.yaml
profiles/coach_demo/config/pillars.yaml
profiles/coach_demo/config/voice.yaml
profiles/coach_demo/dock/business-plan.md
profiles/coach_demo/dock/system/vision-board.md
profiles/coach_demo/skills/operator-guide/prompt.md
profiles/coach_demo/skills/welcome-card/prompt.md
profiles/coach_demo/skills/welcome-card/config.yaml
profiles/coach_demo/skills/session-zero-intake/prompt.md
profiles/coach_demo/skills/session-zero-intake/config.yaml
profiles/coach_demo/skills/session-zero-intake/SKILL.md
profiles/coach_demo/skills/entity-scaffolder/prompt.md
profiles/coach_demo/skills/entity-scaffolder/config.yaml
profiles/coach_demo/skills/entity-scaffolder/SKILL.md
tests/test_entity_scaffolder.py
tests/test_session_zero_v2.py
tests/test_cortex_growth.py
```

**Moved files:**
```
profiles/coach_demo/ → profiles/coach_archive/  (entire directory)
```

**Modified files (4):**
```
engine/compiler.py     — add gap_analyzer()
engine/cortex.py       — growth triggers in Lenses 1, 2, 5, 6
engine/dispatcher.py   — register entity_scaffold if not already via skill_executor
QUICKSTART.md          — cold-start walkthrough
```

---

## The Mesh: Sub-Autonomatons Created by This Sprint

| Sub-Autonomaton | Triggered By | Zone | Pipeline Path |
|-----------------|-------------|------|---------------|
| Entity Scaffolder | Session Zero, Cortex Lens 1, Operator | Yellow | `force_route="entity_scaffold"` → `skill_executor` |
| Gap Alert | Scaffolder (dependent entity) | Green | Kaizen queue → operator approval → scaffolder |
| Pillar Discovery | Session Zero, Cortex Lens 2 | Yellow | `config_update` sub-route |
| Seasonal Updater | Session Zero, Cortex Lens 6 | Yellow | `plan_update` route |
| Skill Proposer | Cortex Lens 5 + Vision Board | Red | Kaizen queue → Pit Crew |

Every row is a pipeline traversal. Every row generates telemetry. Every
row is governed by zones. Autonomatons all the way down.
