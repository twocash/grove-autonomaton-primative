# SPRINTS.md — Reference Profile v1: Story-Level Breakdown

> Sprint: `reference-profile-v1`
> Generated: 2026-03-18

---

## Epic A: Reference Profile Directory

### Story A.1: Create profile directory structure
**Task:** Create `profiles/reference/` with the full directory tree matching
the existing profile pattern (config/, dock/, dock/system/, entities/,
skills/, telemetry/, queue/, output/).
**Acceptance:** `--list-profiles` shows `reference` as available.

### Story A.2: Create profile.yaml (new config type)
**Task:** Create `profiles/reference/config/profile.yaml` with display and
startup flags. This is a NEW config file type — no other profile has it yet.
```yaml
display:
  glass_pipeline: true
  glass_level: medium      # minimal | medium | full
  tips: true
startup:
  skip_welcome: true
  skip_startup_brief: true
  skip_plan_generation: true
  skip_queue: true
```
**Acceptance:** File loads without error. Other profiles operate unchanged
(they simply don't have profile.yaml and get default behavior).

### Story A.3: Create reference routing.config
**Task:** Start from blank_template's routing.config. Add six inspection
intents: `show_config`, `show_zones`, `show_telemetry`, `show_cache`,
`show_engine`. All Tier 0, Green zone, informational intent_type.
Keep all existing system intents (general_chat, welcome_card, startup_brief,
generate_plan, clear_cache, dock_status, queue_status, skills_list,
operator_guide, vision_capture, session_zero, pit_crew_build).
**Acceptance:** All inspection keywords route correctly at Tier 0.

### Story A.4: Create reference zones.schema
**Task:** Copy from blank_template. No domain-specific additions needed.
**Acceptance:** Zone governance loads correctly for the reference profile.

### Story A.5: Create reference persona.yaml
**Task:** Create persona for the reference profile. Name: "The Engine" or
similar. Role: architecture guide. The persona instructs the LLM to respond
as an architecture narrator when dock is empty — explaining what the system
WOULD do if context were loaded. This is how general_chat becomes
architecture-aware without code branching.
```yaml
name: "Engine"
role: "Architecture Guide"
tone: "Direct, technical, architecture-literate. No hand-holding."
context: |
  You are the Autonomaton engine running with an empty profile.
  When answering, explain what the architecture does, not what a
  domain-specific system would do. If dock context is empty, say so
  and explain what would be there in a configured system.
  After the user's first LLM-classified interaction, mention the cost
  and suggest trying the same phrase again to see the Ratchet.
  After the Ratchet demo, suggest `show cache` or `show telemetry`.
```
**Acceptance:** general_chat handler produces architecture-aware responses.

### Story A.6: Create remaining config stubs
**Task:** Create empty/minimal versions of: `voice.yaml`, `pillars.yaml`,
`mcp.config`, `pattern_cache.yaml` (with empty `cache: {}` block),
`dock/system/vision-board.md`, `.gitkeep` files in entities/, skills/,
telemetry/, queue/, output/.
**Acceptance:** Profile loads with zero errors, zero dock chunks, zero
pending queue items.

### Story A.7: Create reference operator-guide skill
**Task:** Create `skills/operator-guide/prompt.md` adapted for the reference
audience. Focus on: the five stages, the three files, the zone model, the
Ratchet, inspection commands, Session Zero. Not a user manual — an
architecture walkthrough.
**Acceptance:** `help` command returns reference-specific operator guide.

### Build Gate A
```bash
python autonomaton.py --profile reference --skip-welcome --skip-queue
# Should load banner, show "0 chunks from 0 sources", accept input
# Type "hello" → general_chat handler responds
# Type "exit" → clean shutdown
```

---

## Epic B: Glass Pipeline Presentation Layer

### Story B.1: Create engine/glass.py module
**Task:** Create a new module `engine/glass.py` with a single public function:
```python
def display_glass_pipeline(context: PipelineContext, level: str = "medium") -> None:
    """Render pipeline stage annotations to terminal.
    
    Pure observer — reads PipelineContext metadata only.
    Does not inject probes into pipeline stages.
    """
```

**Data extraction map for medium level:**
- Stage 1 (Telemetry): `context.telemetry_event.get("id", "")[:8]`,
  `context.source`
- Stage 2 (Recognition): `context.raw_input[:40]`, `context.intent`,
  `context.entities["routing"]["tier"]`, `context.entities["routing"]["confidence"]`,
  `context.zone`, `context.entities["routing"]["intent_type"]`,
  cache status from `context.entities["routing"]["llm_metadata"]`
  (check for `"source": "pattern_cache"` = HIT, tier >= 2 = LLM call,
  else = keyword match)
- Stage 3 (Compilation): `len(context.dock_context)` — show "Skipped"
  for conversational, "Dock query: [empty]" if no context, "Dock query:
  {n} chunks" if populated
- Stage 4 (Approval): `context.zone` + `context.approved` — "GREEN
  auto-approve", "YELLOW — requires confirmation", "RED — explicit
  approval", "CANCELLED"
- Stage 5 (Execution): `context.entities["routing"]["handler"]`,
  `context.executed`

**Cost display logic:**
- If `routing.tier >= 2` AND `llm_metadata.source != "pattern_cache"`:
  show estimated cost (pull from telemetry or use tier-based estimate)
- If `routing.tier == 0` AND `llm_metadata.source == "pattern_cache"`:
  show "Cost: $0.00" with cache HIT indicator ✓
- If `routing.tier == 0` AND keyword match: show "Cost: $0.00" (no special indicator)

**Rendering format:**
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
Use ANSI colors: zone colors match existing (green/yellow/red), stage
numbers in cyan, metadata in dim. The box border in dim white.

**Acceptance:** Glass annotations render correctly for: keyword match,
LLM escalation, cache hit, conversational skip, yellow zone approval,
cancelled action.

### Story B.2: Handle the Ratchet annotation
**Task:** When a cache hit is detected (tier 0, llm_metadata.source ==
"pattern_cache"), add a prominent Ratchet announcement AFTER the glass
pipeline box:
```
  ⚡ THE RATCHET: Classified by LLM last time → cache this time.
     Tier 0, $0.00. The system got cheaper because you used it.
```
This only fires on the FIRST cache hit per session (tracked in-memory).
Subsequent cache hits show the HIT ✓ in the glass box but no announcement.
**Acceptance:** First cache hit shows announcement. Second does not.

### Build Gate B
```bash
python autonomaton.py --profile reference
# Type "hello" → glass box with 5 stages renders
# Type "what should I focus on" → glass box shows LLM escalation + cost
# Type "what should I focus on" again → glass box shows cache HIT, $0.00
#   + Ratchet announcement below the box
```


---

## Epic C: Reference Profile Handlers

### Story C.1: Implement `show_file` handler
**Task:** Add a `show_file` handler to the dispatcher registry. The handler:
1. Reads `handler_args["target"]` (relative path from profile root)
2. Validates path is within the profile directory (reject `../` traversal)
3. Reads file contents
4. If `handler_args.get("tail")` is set, show only last N lines
5. Returns file contents as the result message
6. Formats output with a header showing the file path

**Security constraint:** Use `pathlib.Path.resolve()` and verify the resolved
path starts with the profile directory path. Reject with clear error if not.

**Acceptance:** `show config`, `show zones`, `show telemetry`, `show cache`
all display correct file contents through the pipeline. Path traversal
attempts return an error message.

### Story C.2: Implement `show_engine_manifest` handler
**Task:** Add a `show_engine_manifest` handler. The handler:
1. Reads the `engine/` directory (hardcoded relative to repo root — this
   is the ONE place the engine's location is known)
2. For each `.py` file: count lines, extract first line of module docstring
3. Format as manifest table
4. Include `autonomaton.py` entry point separately

**Output format:**
```
ENGINE MANIFEST
───────────────────────────────────────────
pipeline.py          888 lines   The Invariant Pipeline
cognitive_router.py  616 lines   Hybrid Intent Classification
dispatcher.py        xxx lines   Handler Registry and Execution
telemetry.py         xxx lines   Feed-First Structured Telemetry
ux.py                347 lines   Digital Jidoka
cortex.py            xxx lines   Analytical Lenses
───────────────────────────────────────────
Entry point: autonomaton.py  503 lines
```
**Acceptance:** `show engine` displays manifest with accurate line counts.

### Story C.3: Register new handlers in dispatcher
**Task:** Register `show_file` and `show_engine_manifest` in the dispatcher's
handler registry alongside existing handlers. Follow the existing registration
pattern in `dispatcher.py`.
**Acceptance:** Both handlers dispatch correctly when routing.config maps to them.

### Build Gate C
```bash
python autonomaton.py --profile reference
# Type "show config" → displays routing.config contents
# Type "show zones" → displays zones.schema contents
# Type "show telemetry" → displays last 20 telemetry events (or empty)
# Type "show cache" → displays pattern_cache.yaml (empty cache: {})
# Type "show engine" → displays engine manifest with line counts
```

---

## Epic D: Contextual Tips System

### Story D.1: Create tips.yaml for reference profile
**Task:** Create `profiles/reference/config/tips.yaml` with the tip
definitions from the SPEC. Eight tips, each with trigger conditions and
display text. Triggers based on: `after_intent`, `after_tier`,
`after_cache_hit`, `after_zone`.
**Acceptance:** File loads without error. Tip definitions parse correctly.

### Story D.2: Implement tip engine
**Task:** Create a lightweight tip evaluator (can live in `engine/glass.py`
or a separate `engine/tips.py`). The engine:
1. Loads `config/tips.yaml` at startup (if file exists; no-op if missing)
2. Maintains an in-memory set of shown tip IDs (session-scoped, not persisted)
3. After each pipeline run, evaluates tip triggers against the PipelineContext
4. Returns at most ONE tip text (the first matching unshown tip)
5. Marks the tip as shown

**Trigger evaluation:**
- `after_intent: "general_chat"` → matches when `context.intent == "general_chat"`
- `after_tier: 2` → matches when `context.entities["routing"]["tier"] == 2`
- `after_cache_hit: true` → matches when `llm_metadata.source == "pattern_cache"`
- `after_zone: "yellow"` → matches when `context.zone == "yellow"`
- `shown_count: 0` → matches when tip has not been shown yet

**Display format:** Single dim line with lightbulb:
```
  💡 Try `clear cache` to see what happens when the zone changes.
```
**Acceptance:** Tips fire in correct sequence during the designed OOB flow.
Each tip shows at most once per session.

### Build Gate D
```bash
python autonomaton.py --profile reference
# Type "hello" → result + tip: "Try something the system won't recognize..."
# Type "what should I focus on" → result + tip about trying same phrase
# Type "what should I focus on" → Ratchet fires + tip about show cache
# Type "show cache" → result + tip about clear cache
# Type "clear cache" → Jidoka fires + tip about show telemetry
# Each tip appears only once
```

---

## Epic E: REPL Integration

### Story E.1: Add profile.yaml loader to config_loader.py
**Task:** Add a `load_profile_config()` function to `engine/config_loader.py`
that reads `config/profile.yaml` from the active profile. Returns a dict
with sensible defaults if the file doesn't exist:
```python
DEFAULT_PROFILE_CONFIG = {
    "display": {
        "glass_pipeline": False,
        "glass_level": "medium",
        "tips": False
    },
    "startup": {
        "skip_welcome": False,
        "skip_startup_brief": False,
        "skip_plan_generation": False,
        "skip_queue": False
    }
}
```
Existing profiles (coach_demo, blank_template) don't have profile.yaml
and get defaults — zero behavior change.
**Acceptance:** Reference profile returns glass_pipeline=True. Coach_demo
returns glass_pipeline=False (default). No existing tests break.

### Story E.2: Wire startup gating in autonomaton.py
**Task:** In `main()`, after `set_profile()`, load profile config. Use
startup flags to gate:
- Plan generation (first-boot check)
- Queue processing
- Welcome card
- Startup brief

CLI flags (`--skip-welcome`, `--skip-queue`) override profile.yaml.
Both CLI flags and profile.yaml flags should be OR'd (either can suppress).
**Acceptance:** Reference profile skips all startup sequences. Coach_demo
unchanged.

### Story E.3: Wire glass pipeline display in REPL loop
**Task:** In the main REPL loop, after `run_pipeline()` returns and before
`display_result()`, check if glass is enabled (profile config OR `--glass`
CLI flag). If yes, call `display_glass_pipeline(context, level)`.

Add `--glass` to the argument parser:
```python
parser.add_argument("--glass", action="store_true",
    help="Enable glass pipeline display for any profile")
```
**Acceptance:** Glass annotations appear before result for reference profile.
`--glass` flag works with coach_demo.

### Story E.4: Wire tip engine in REPL loop
**Task:** After `display_result()`, if tips are enabled (profile config),
evaluate tips against context and display at most one tip.
**Acceptance:** Tips appear after results in reference profile. No tips
in coach_demo.

### Story E.5: Modify banner for reference profile
**Task:** When glass_pipeline is active, add `Glass Pipeline: ACTIVE` line
to banner. When profile is `reference`, add the three-line intro block:
```
  This is the naked engine. No domain. No context. No skills.
  Every pipeline stage will announce itself as it runs.
  Type anything to see the architecture in motion.
```
**Acceptance:** Reference profile banner matches the design spec.

### Build Gate E (Full OOB Flow)
```bash
python autonomaton.py --profile reference
# Banner shows "Glass Pipeline: ACTIVE" and intro block
# No welcome card, no startup brief, no plan generation
# Type "hello" → glass box + result + tip
# Type "what should I focus on" → glass box with LLM + cost + tip
# Type "what should I focus on" → glass box with cache HIT + Ratchet + tip
# Type "show cache" → glass box + cache contents + tip
# Type "clear cache" → glass box + Jidoka prompt + tip
# Approve → cache cleared + tip about telemetry
# Type "show telemetry" → glass box + telemetry log + tip about engine
# Type "show engine" → glass box + manifest + tip about session zero
# The full designed flow works end-to-end
```

---

## Epic F: Test Suite

### Story F.1: Profile loading tests
**Task:** Test that reference profile loads all config files without error.
Test that missing profile.yaml in other profiles returns defaults.
Test that --list-profiles includes "reference".

### Story F.2: Glass pipeline unit tests
**Task:** Test `display_glass_pipeline()` with mocked PipelineContext objects:
- Keyword match context → correct tier/method annotation
- LLM classification context → shows cost, tier 2
- Cache hit context → shows $0.00, HIT ✓
- Conversational intent → shows "Skipped" for compilation
- Yellow zone → shows "requires confirmation"
- Cancelled action → shows "CANCELLED"

### Story F.3: Handler tests
**Task:** Test show_file handler with valid paths, test path traversal
rejection (../../engine/secrets), test show_engine_manifest returns
correct file list and line counts.

### Story F.4: Tips engine tests
**Task:** Test tip trigger evaluation. Test tips show once each. Test
tips disabled when `display.tips: false`. Test no tips file = no tips.

### Story F.5: Integration test — full OOB flow
**Task:** Script the designed first-five-minutes flow programmatically.
Verify glass output, tip sequence, Ratchet announcement, and handler
results at each step. This is the acceptance test for the entire sprint.

### Build Gate F
```bash
python -m pytest tests/test_reference_profile.py -v
# All tests pass
python -m pytest tests/ -v
# All existing tests still pass — zero regressions
```

---

## Summary: File Manifest

**New files (16):**
```
profiles/reference/config/profile.yaml
profiles/reference/config/routing.config
profiles/reference/config/zones.schema
profiles/reference/config/pattern_cache.yaml
profiles/reference/config/persona.yaml
profiles/reference/config/voice.yaml
profiles/reference/config/pillars.yaml
profiles/reference/config/mcp.config
profiles/reference/config/tips.yaml
profiles/reference/dock/system/vision-board.md
profiles/reference/skills/operator-guide/prompt.md
profiles/reference/entities/.gitkeep
profiles/reference/telemetry/.gitkeep
profiles/reference/queue/.gitkeep
profiles/reference/output/.gitkeep
engine/glass.py
tests/test_reference_profile.py
```

**Modified files (3):**
```
engine/dispatcher.py      — register show_file, show_engine_manifest
engine/config_loader.py   — add load_profile_config()
autonomaton.py            — glass hook, CLI flag, startup gating, tip hook, banner
```
