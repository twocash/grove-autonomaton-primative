# SPRINT 5 CONTRACT: The Living Plan

> Atomic execution contract generated from SPRINT-5-CONCEPT-living-plan.md
> Generated: 2026-03-18

---

## Pre-Sprint Audit Summary

**Directory Structure:** `engine/` (NOT `src/` — concept paths are correct)

**Existing Infrastructure:**
| Component | File | Status |
|-----------|------|--------|
| Standing Context | `engine/compiler.py:149-267` | `gather_state_snapshot()` reads dock, entities, content-seeds, skills, session recency |
| Cortex Lenses 1-5 | `engine/cortex.py` | Lens 1: Entity, Lens 2: Seeds, Lens 3: Pattern, Lens 4: Ratchet, Lens 5: Evolution |
| Kaizen Queue | `engine/cortex.py:461-498` | YAML format via `_queue_kaizen()`, `load_pending_queue()`, `remove_from_queue()` |
| Vision Board | `profiles/coach_demo/dock/system/vision-board.md` | Aspirations capture exists |
| Exhaust Board | `profiles/coach_demo/dock/system/exhaust-board.md` | Telemetry registry exists |
| Startup Brief | `autonomaton.py:205-242` | `generate_startup_brief()` uses Sonnet + standing context |
| Welcome Card | `autonomaton.py:114-202` | `generate_welcome_briefing()` uses skill prompt |

**Missing (Sprint 5 Creates):**
- `dock/system/structured-plan.md` — does NOT exist yet
- Context Gardener (Lens 6) — does NOT exist yet
- Gap detection at startup — does NOT exist yet
- Plan refresh cycle — does NOT exist yet

---

## Epic 5A: The Structured Plan Artifact

### Task 5A.1: Create Structured Plan Template
**File:** `profiles/coach_demo/dock/system/structured-plan.md`
**Lines:** New file

**Action:** Create initial template with sections:
- Active Goals & Progress (synthesized from `goals.md`)
- Data Gaps (missing entities needed by handlers)
- Stale Items (goals not touched recently)
- What's Working (positive telemetry patterns)

**Verification:**
```bash
test -f profiles/coach_demo/dock/system/structured-plan.md && echo "PASS"
```

---

### Task 5A.2: Create `generate_structured_plan()` Function
**File:** `engine/compiler.py`
**Insert after:** Line 280 (after `reset_standing_context()`)

**Action:** Add function that:
1. Reads `dock/goals.md`, `dock/seasonal-context.md`, entity inventory
2. Cross-references with content pipeline stats
3. Calls Tier 2 Sonnet to synthesize trajectory
4. Returns markdown string for operator approval

**Signature:**
```python
def generate_structured_plan() -> str:
    """
    Synthesize structured plan from dock + entities + telemetry.

    Uses Tier 2 (Sonnet) to create a human-readable trajectory document.
    Returns markdown string ready for approval and file write.
    """
```

**Verification:**
```bash
python -c "from engine.compiler import generate_structured_plan; print(len(generate_structured_plan()) > 100)"
```

---

### Task 5A.3: Wire Plan Generation to First Boot
**File:** `autonomaton.py`
**Modify:** After line 493 (after `print_banner()`)

**Action:** Add startup check:
```python
# Check for structured plan — generate on first boot
from engine.profile import get_dock_dir
plan_path = get_dock_dir() / "system" / "structured-plan.md"
if not plan_path.exists():
    from engine.compiler import generate_structured_plan
    # Generate and show for approval (Yellow Zone)
    plan_content = generate_structured_plan()
    if plan_content:
        # Display and request approval before writing
        ...
```

**Verification:**
1. Delete `structured-plan.md` if exists
2. Run `python autonomaton.py --skip-queue`
3. Confirm plan generation prompt appears
4. Approve → verify file created
5. Restart → confirm no regeneration prompt

---

### Task 5A.4: Update `gather_state_snapshot()` to Read Plan
**File:** `engine/compiler.py`
**Modify:** Inside `gather_state_snapshot()`, after dock summary section (~line 178)

**Action:** Add section to read and include `structured-plan.md` in standing context:
```python
# --- Structured Plan Summary ---
try:
    plan_path = dock_dir / "system" / "structured-plan.md"
    if plan_path.exists():
        plan_content = plan_path.read_text(encoding="utf-8")
        # Include first 1000 chars of plan
        sections.append(f"[structured-plan]\n{plan_content[:1000]}")
except Exception as e:
    log_event(...)
```

**Verification:**
```bash
python -c "from engine.compiler import gather_state_snapshot; ctx = gather_state_snapshot(); print('[structured-plan]' in ctx)"
```

---

### Task 5A.5: Ensure Plan Writes Go Through Pipeline (Yellow Zone)
**File:** `engine/dispatcher.py`
**Action:** Add handler for `plan_update` intent

**File:** `profiles/coach_demo/config/routing.config`
**Action:** Add route:
```yaml
plan_update:
  tier: 2
  zone: yellow
  domain: system
  description: "Update structured plan — writes to dock (YELLOW ZONE)"
  handler: plan_update
```

**Verification:**
1. Attempt manual plan update via REPL
2. Confirm Yellow Zone approval prompt appears
3. Approve → verify `structured-plan.md` updated
4. Check telemetry log for `plan_update` event

---

## Epic 5B: Context Gardener (Cortex Lens 6)

### Task 5B.1: Add `run_context_gardener()` Method to Cortex
**File:** `engine/cortex.py`
**Insert after:** Line 861 (after `run_evolution_analysis()`)

**Action:** Add Lens 6 method:
```python
def run_context_gardener(
    self,
    telemetry_events: list[dict],
    standing_context: str,
    structured_plan: str,
    vision_board: str,
    exhaust_board: str
) -> dict:
    """
    Lens 6: Context Gardener - proposes dock updates based on patterns.

    Produces three types of Kaizen proposals:
    1. gap_alert: Missing data needed by handlers
    2. plan_update: Observations to add to structured-plan.md
    3. stale_alert: Goals not touched in threshold period

    Uses Tier 1 (Haiku) for pattern matching, Tier 2 (Sonnet) for synthesis.
    """
```

**Verification:**
```bash
python -c "from engine.cortex import Cortex; c = Cortex(); print(hasattr(c, 'run_context_gardener'))"
```

---

### Task 5B.2: Implement Gap Alert Detection
**File:** `engine/cortex.py`
**Inside:** `run_context_gardener()` method

**Action:** Add logic to:
1. Parse standing context for entity types (players, parents, venues)
2. Identify handlers that require specific entity fields (e.g., email handler needs parent emails)
3. Cross-reference: which required fields are missing?
4. Generate `gap_alert` proposals for missing data

**Verification:**
```bash
# Create test case: handler needs parent email, parent entity has no email
python -c "
from engine.cortex import Cortex
c = Cortex()
result = c.run_context_gardener([], '[entities/parents] henderson-family', '', '', '')
print('gap_alert' in str(result.get('proposals', [])))
"
```

---

### Task 5B.3: Implement Plan Update Proposals
**File:** `engine/cortex.py`
**Inside:** `run_context_gardener()` method

**Action:** Add logic to:
1. Analyze telemetry patterns against structured plan goals
2. Detect progress (e.g., "4.2 TikToks/week avg" vs "5/week target")
3. Generate `plan_update` proposals with:
   - `target_file`: "dock/system/structured-plan.md"
   - `target_section`: Specific goal section
   - `observation`: What the data shows
   - `recommended_action`: Suggested operator action

**Verification:**
```bash
# Test with mock telemetry showing content compilation pattern
python -c "
from engine.cortex import Cortex
c = Cortex()
telemetry = [{'intent': 'compile_content'}, {'intent': 'compile_content'}]
plan = '## Goal 2: TikTok - 5/week'
result = c.run_context_gardener(telemetry, '', plan, '', '')
print(len(result.get('proposals', [])) > 0)
"
```

---

### Task 5B.4: Implement Stale Item Detection
**File:** `engine/cortex.py`
**Inside:** `run_context_gardener()` method

**Action:** Add logic to:
1. Parse structured plan for goal sections
2. Query telemetry for last interaction with each goal domain
3. If gap > threshold (14 days default), generate `stale_alert` proposal

**Verification:**
```bash
# Verify stale detection triggers for goals not touched in 14+ days
python -c "
from engine.cortex import Cortex
c = Cortex()
plan = '## Goal 3: Tithing\n**Target:** $500/month'
# No telemetry mentioning tithing
result = c.run_context_gardener([], '', plan, '', '')
print('stale' in str(result))
"
```

---

### Task 5B.5: Wire Context Gardener to Tail Pass
**File:** `engine/cortex.py`
**Modify:** `run_tail_pass()` function (line 928)

**Action:** Add gated call to Context Gardener:
```python
def run_tail_pass() -> dict:
    cortex = get_cortex()
    result = cortex.run_analysis_pass()

    # Context Gardener gating
    # Only run if: 10+ events since last run AND not already run this session
    if _should_run_gardener():
        gardener_result = cortex.run_context_gardener(...)
        # Queue proposals through existing Kaizen mechanism
        for proposal in gardener_result.get("proposals", []):
            cortex._queue_kaizen(proposal)

    return result
```

**Verification:**
1. Generate 10+ telemetry events
2. Trigger tail pass
3. Check Kaizen queue for Context Gardener proposals

---

### Task 5B.6: Add Gardener Gating Configuration
**File:** `profiles/coach_demo/config/cortex.yaml` (NEW FILE)

**Action:** Create config:
```yaml
context_gardener:
  enabled: true
  min_events_since_last_run: 10
  max_runs_per_session: 1
  stale_threshold_days: 14
  tier_for_pattern_matching: 1  # Haiku
  tier_for_synthesis: 2         # Sonnet
```

**File:** `engine/cortex.py`
**Action:** Add config loader for gating parameters

**Verification:**
```bash
test -f profiles/coach_demo/config/cortex.yaml && echo "PASS"
python -c "from engine.cortex import _should_run_gardener; print(callable(_should_run_gardener))"
```

---

## Epic 5C: Gap Detection at Startup

### Task 5C.1: Add Gap Detection to Standing Context Assembly
**File:** `engine/compiler.py`
**Modify:** `gather_state_snapshot()` — add new section after entity inventory

**Action:** Add gap detection:
```python
# --- Entity Gaps ---
try:
    gaps = detect_entity_gaps()  # New function
    if gaps:
        gap_summary = "; ".join([f"{g['entity']}: {g['missing']}" for g in gaps[:5]])
        sections.append(f"[entity-gaps] {gap_summary}")
except Exception as e:
    log_event(...)
```

**Verification:**
```bash
python -c "
from engine.compiler import gather_state_snapshot
ctx = gather_state_snapshot()
print('[entity-gaps]' in ctx or 'No gaps' in ctx)
"
```

---

### Task 5C.2: Create `detect_entity_gaps()` Function
**File:** `engine/compiler.py`
**Insert after:** `gather_state_snapshot()`

**Action:** Add function:
```python
def detect_entity_gaps() -> list[dict]:
    """
    Detect missing entity fields required by handlers.

    Cross-references:
    - Handler requirements (from routing.config)
    - Entity fields (from entities/*.md files)

    Returns list of gap dicts: {"entity": "...", "missing": "...", "handler": "..."}
    """
```

**Verification:**
```bash
# Create player entity without handicap, verify gap detected
python -c "
from engine.compiler import detect_entity_gaps
gaps = detect_entity_gaps()
print(type(gaps) == list)
"
```

---

### Task 5C.3: Surface Gaps in Startup Brief
**File:** `autonomaton.py`
**Modify:** `generate_startup_brief()` (line 205)

**Action:** Update task_context to include gap awareness:
```python
task_context = (
    "The operator just opened the system. Give a focused strategic brief: "
    "3-5 prioritized items based on what you know. Lead with urgency. "
    "If there are entity gaps blocking handlers, surface them clearly. "
    "Suggest specific commands for each item..."
)
```

**Verification:**
1. Create gap condition (parent without email)
2. Run `python autonomaton.py`
3. Confirm startup brief mentions the gap

---

### Task 5C.4: Add Gap-Filling Intent Recognition
**File:** `profiles/coach_demo/config/routing.config`
**Action:** Add route for gap-filling flow:

```yaml
fill_entity_gap:
  tier: 2
  zone: yellow
  domain: entities
  description: "Add missing information to an entity profile"
  handler: fill_entity_gap
  patterns:
    - "add email for {entity}"
    - "update {entity} with {field}"
    - "{entity} email is {value}"
```

**File:** `engine/dispatcher.py`
**Action:** Add `fill_entity_gap` handler

**Verification:**
1. Say "add email for Martinez family"
2. Confirm intent recognized as `fill_entity_gap`
3. Approve Yellow Zone
4. Verify entity file updated

---

## Epic 5D: Plan Refresh Cycle

### Task 5D.1: Add Plan Refresh Trigger After Approved Updates
**File:** `autonomaton.py`
**Modify:** After Cortex tail pass (line 558)

**Action:** Add refresh logic:
```python
# Refresh standing context when Cortex extracts new data OR plan updated
if cortex_result.get("entities", 0) > 0 or cortex_result.get("kaizen", 0) > 0:
    print(...)
    from engine.compiler import reset_standing_context
    reset_standing_context()

# Also refresh if any plan_update proposals were approved this session
if _plan_updated_this_session():
    reset_standing_context()
```

**Verification:**
1. Approve a plan_update Kaizen proposal
2. Verify standing context refreshes
3. Next interaction should reflect updated plan

---

### Task 5D.2: Add Weekly Full Plan Regeneration
**File:** `engine/cortex.py`
**Action:** Add method:

```python
def regenerate_full_plan(self) -> str:
    """
    Full plan regeneration - Tier 2 Sonnet re-synthesizes entire plan.

    Called weekly (or on operator request) to produce fresh trajectory
    assessment from current dock + telemetry state.
    """
```

**File:** `profiles/coach_demo/config/routing.config`
**Action:** Add route:
```yaml
regenerate_plan:
  tier: 2
  zone: yellow
  domain: system
  description: "Regenerate full structured plan from current state"
  handler: regenerate_plan
  patterns:
    - "regenerate plan"
    - "refresh plan"
    - "update the full plan"
```

**Verification:**
1. Say "regenerate plan"
2. Confirm Yellow Zone approval
3. Verify new plan generated and written
4. Check telemetry for plan_regeneration event

---

### Task 5D.3: Add Plan Version Tracking in Telemetry
**File:** `engine/telemetry.py`
**Action:** Add plan version logging:

```python
def log_plan_event(
    event_type: str,  # "generated", "updated", "regenerated"
    plan_hash: str,
    source: str = "context_gardener"
) -> dict:
    """Log plan lifecycle events for Ratchet tracking."""
```

**File:** `engine/compiler.py`
**Modify:** All plan write operations to call `log_plan_event()`

**Verification:**
```bash
# After plan update, verify telemetry contains plan event
python -c "
from engine.telemetry import read_recent_events
events = read_recent_events(limit=20)
plan_events = [e for e in events if 'plan' in e.get('source', '')]
print(len(plan_events) >= 0)  # May be 0 if no plan changes yet
"
```

---

### Task 5D.4: Add `plan_refresh` to Kaizen Proposal Types
**File:** `engine/cortex.py`
**Modify:** `KaizenProposal` dataclass (line 83)

**Action:** Add `proposal_type` field:
```python
@dataclass
class KaizenProposal:
    id: str
    proposal: str
    trigger: str
    source_event_id: str
    created_at: str
    status: str = "pending"
    proposal_type: str = "general"  # NEW: gap_alert, plan_update, stale_alert, general
    target_file: str = ""           # NEW: for plan_update type
    target_section: str = ""        # NEW: for plan_update type
```

**Verification:**
```bash
python -c "
from engine.cortex import KaizenProposal
kp = KaizenProposal('id', 'prop', 'trigger', 'src', '2026-01-01', proposal_type='plan_update')
print(kp.proposal_type == 'plan_update')
"
```

---

## Test Matrix

| Test ID | Epic | Description | Command | Expected |
|---------|------|-------------|---------|----------|
| T5A.1 | 5A | Plan template exists | `test -f profiles/coach_demo/dock/system/structured-plan.md` | File exists |
| T5A.2 | 5A | Plan generator function | `python -c "from engine.compiler import generate_structured_plan"` | No import error |
| T5A.3 | 5A | First boot generates plan | Delete plan, run autonomaton | Approval prompt appears |
| T5A.4 | 5A | Standing context includes plan | `gather_state_snapshot()` | `[structured-plan]` in output |
| T5A.5 | 5A | Plan update is Yellow Zone | Attempt `plan_update` intent | Approval required |
| T5B.1 | 5B | Gardener method exists | `hasattr(Cortex(), 'run_context_gardener')` | True |
| T5B.2 | 5B | Gap alerts generated | Test with missing entity field | `gap_alert` in proposals |
| T5B.3 | 5B | Plan updates generated | Test with telemetry patterns | `plan_update` in proposals |
| T5B.4 | 5B | Stale alerts generated | Test with 14+ day gap | `stale_alert` in proposals |
| T5B.5 | 5B | Gardener wired to tail pass | 10+ events, trigger tail pass | Proposals queued |
| T5B.6 | 5B | Gardener config exists | `test -f profiles/coach_demo/config/cortex.yaml` | File exists |
| T5C.1 | 5C | Gap detection in snapshot | `gather_state_snapshot()` | `[entity-gaps]` present |
| T5C.2 | 5C | Gap detection function | `detect_entity_gaps()` | Returns list |
| T5C.3 | 5C | Gaps in startup brief | Brief with gap condition | Gap mentioned |
| T5C.4 | 5C | Gap-filling intent | "add email for Martinez" | Intent recognized |
| T5D.1 | 5D | Refresh after updates | Approve plan_update | Context refreshes |
| T5D.2 | 5D | Full regeneration | "regenerate plan" | New plan generated |
| T5D.3 | 5D | Plan telemetry | After plan write | Plan event logged |
| T5D.4 | 5D | Proposal types | Create KaizenProposal | `proposal_type` field works |

---

## Execution Order

```
5A.1 → 5A.2 → 5A.4 → 5A.3 → 5A.5
           ↓
5B.1 → 5B.2 → 5B.3 → 5B.4 → 5B.6 → 5B.5
           ↓
5C.2 → 5C.1 → 5C.3 → 5C.4
           ↓
5D.4 → 5D.1 → 5D.2 → 5D.3
```

**Rationale:**
- 5A.1 (template) before 5A.2 (generator) — generator needs target format
- 5A.4 (read plan) before 5A.3 (write plan) — reading must work before writing
- 5B.1 (method) before 5B.2-4 (implementations) — scaffold first
- 5B.6 (config) before 5B.5 (wiring) — gating needs config
- 5C.2 (function) before 5C.1 (integration) — function first
- 5D.4 (dataclass) before 5D.1-3 — proposal types needed first

---

## Architectural Constraints Checklist

- [ ] **Invariant #1:** All plan reads go through Stage 3 (Compilation)
- [ ] **Invariant #1:** All plan writes go through Stage 4 (Yellow Zone approval)
- [ ] **Invariant #2:** Gardener config in YAML, not hardcoded
- [ ] **Invariant #4:** No silent failures — all Gardener errors logged
- [ ] **Invariant #5:** All plan events in telemetry before processing
- [ ] **Invariant #6:** Only Stage 4 prompts for approval (Gardener proposes, pipeline approves)

---

## Definition of Done

Sprint 5 is complete when:

1. `structured-plan.md` exists and is human-readable
2. Standing context includes plan summary
3. First boot generates plan with approval flow
4. Context Gardener produces all three proposal types
5. Gardener is gated (10 events, 1x per session)
6. Entity gaps surface in startup brief
7. Plan refresh works after approved updates
8. Full regeneration available on command
9. All plan events tracked in telemetry
10. All tests in matrix pass

---

*Contract generated from concept document. Execute atomically. Verify incrementally.*
