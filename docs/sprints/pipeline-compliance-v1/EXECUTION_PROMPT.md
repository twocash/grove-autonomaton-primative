# EXECUTION PROMPT: pipeline-compliance-v1

> Copy this entire file into a fresh Claude Code session.
> It contains everything needed to execute the sprint.
> No prior context required.

---

## Context

You are working on `grove-autonomaton-primative` — a Python CLI
reference implementation of the Autonomaton Pattern (an AI governance
architecture). The repo is at `C:\GitHub\grove-autonomaton-primative`.

**Read these files IN ORDER before writing any code:**

1. `autonomaton-architect-SKILL.md` — The architectural contract.
   Section II defines 7 mandatory invariant tests. These tests
   are the acceptance criteria for this sprint.

2. `docs/sprints/pipeline-compliance-v1/SPEC.md` — The audit that
   identified 8 violations. Read the violations.

3. `docs/sprints/pipeline-compliance-v1/CONTRACT.md` — The atomic
   execution contract. Every task, every file edit, every gate.

**Execute the CONTRACT.md task-by-task. Do not skip gates.**

## The Eight Violations Being Fixed

| ID | What | Where |
|----|------|-------|
| V1 | Stages 2-4 emit no telemetry traces | engine/pipeline.py |
| V2 | Clarification has hardcoded coach_demo logic | engine/cognitive_router.py |
| V3 | Keyword gaps → false Jidoka on "my name is bob" | profiles/*/routing.config |
| V4 | Jidoka resolution not logged to telemetry | engine/pipeline.py |
| V5 | Smart clarification hallucinates options | engine/pipeline.py |
| V6 | Post-pipeline input() in skill build | autonomaton.py |
| V7 | LLM cost not in main telemetry stream | engine/pipeline.py |
| V8 | Clarification not declarative (no config) | engine/cognitive_router.py |

## Critical Constraints

- **Windows CMD.** Git needs .bat files. Use `cd /d C:\...`.
- **Create a git worktree** before editing. Never work on master.
- **Profile must be set before importing engine modules.**
- **Run `python -m pytest tests/ -x -q` after EVERY epic.**
- **The invariant test suite (Epic F) is the acceptance gate.**
  If invariant tests don't pass, the sprint is not done.

## Execution Order

### Pre-Sprint
```cmd
cd /d C:\GitHub\grove-autonomaton-primative
del tmpclaude-*-cwd
del nul
```
Add tmpclaude-* and __pycache__/ to .gitignore.
Run `python -m pytest tests/ -x -q` — all must pass.

### Epic A: Per-Stage Telemetry Traces
Each of the 5 stage methods in engine/pipeline.py must call
log_event() after writing to PipelineContext.

Stage 1: Add `"stage": "telemetry"` to existing log_event inferred dict.
Stage 2: NEW log_event() at end of _run_recognition() with intent,
         tier, confidence, and inferred.pipeline_id = Stage 1 event id.
Stage 3: NEW log_event() at end of _run_compilation() with dock info.
Stage 4: NEW _log_approval_trace() helper called before EVERY return
         path in _run_approval() (there are early returns for
         clarification jidoka and non-actionable green).
Stage 5: Modify _log_pipeline_completion() to use stage="execution"
         and add pipeline_id.

Also: log Jidoka resolution with human_feedback="clarified" in
_handle_clarification_jidoka().

Also: populate cost_usd from LLM metadata in completion trace.

**Gate:** Run pipeline, read telemetry, verify 5 stage events exist.
See CONTRACT.md Gate A for exact verification commands.

### Epic B: Declarative Clarification
Create clarification.yaml in profiles/reference/config/,
profiles/coach_demo/config/, profiles/blank_template/config/.

Rewrite get_clarification_options() to read from config.
Rewrite resolve_clarification() to read from config and validate
intents against the active profile's routing.config.

Remove ALL domain-specific terms from engine/cognitive_router.py:
calendar_schedule, mcp_calendar, google_calendar, content_draft,
lessons.

**Gate:** Grep engine/ for domain terms. All must be gone.
See CONTRACT.md Gate B.

### Epic C: Classification Accuracy
Expand general_chat keywords in ALL 3 profiles' routing.config.
Add: "my name is", "thanks", "thank you", "bye", "goodbye",
"nice to meet you", "what is this", "tell me about yourself",
"good evening".

Add ambiguity floor in _handle_clarification_jidoka(): if input
≤2 words AND confidence <0.2, skip LLM smart clarification and
use config-driven fallback.

**Gate:** classify_intent("my name is bob") → general_chat in
reference and coach_demo. See CONTRACT.md Gate C.

### Epic D: Skill Build Pipeline Compliance
Update pit_crew_build in routing.config to extract description
inline via extract_args (position 3).

Update pit_crew handler to read description from extracted_args.
If missing, return usage instructions. No input() call.

Delete handle_skill_build_interactive() from autonomaton.py.

**Gate:** ≤1 input() call in autonomaton.py (the REPL prompt).
See CONTRACT.md Gate D.

### Epic E: Glass Telemetry Consumer
Add read_pipeline_events(pipeline_id) to engine/glass.py.
Add display_glass_from_telemetry(pipeline_id) that reads
telemetry events and formats the glass box.

Wire in autonomaton.py: replace display_glass_pipeline(context)
with display_glass_from_telemetry(pipeline_id).

**Gate:** Manual test with --profile reference. Glass renders
from telemetry, not PipelineContext.

### Epic F: Invariant Test Suite
Create tests/test_pipeline_compliance.py with ALL 7 invariant
tests from autonomaton-architect-SKILL.md Section II.

This is the acceptance gate. If these tests pass, the sprint
is done. If they don't, go back and fix what's broken.

**Gate:** `python -m pytest tests/ -x -q` — ALL pass.

## Final Verification (ALL must pass before commit)

```bash
# Invariant tests
python -m pytest tests/test_pipeline_compliance.py -v

# Full test suite
python -m pytest tests/ -x -q

# Repo hygiene
python -c "
from pathlib import Path
assert len(list(Path('.').glob('tmpclaude-*'))) == 0
print('PASS: clean repo')
"

# Domain isolation spot-check
python -c "
content = open('engine/cognitive_router.py').read()
for t in ['calendar_schedule','mcp_calendar','google_calendar','lessons']:
    assert t not in content, f'Domain term \"{t}\" still in engine'
print('PASS: zero domain logic')
"

# Per-stage trace spot-check
python -c "
from engine.profile import set_profile
set_profile('reference')
from engine.pipeline import run_pipeline
import json
ctx = run_pipeline('hello', source='test')
pid = ctx.telemetry_event['id']
from engine.profile import get_telemetry_path
events = []
with open(get_telemetry_path()) as f:
    for line in f:
        if line.strip():
            events.append(json.loads(line))
stages = {e.get('inferred',{}).get('stage') for e in events
          if e.get('id')==pid or e.get('inferred',{}).get('pipeline_id')==pid}
assert {'telemetry','recognition','compilation','approval','execution'}.issubset(stages)
print(f'PASS: {len(stages)} stage traces')
"
```

## Manual Smoke Test (REQUIRED)

```cmd
cd /d C:\GitHub\grove-autonomaton-primative
python autonomaton.py --profile reference
```

Type each and verify:
- `hello` → Glass shows 5 stages. Routes to general_chat. No Jidoka.
- `my name is bob` → Same. No Jidoka.
- `show config` → Tier 0 keyword. Glass renders.
- `nuclear` → Jidoka fires with profile-appropriate options.
- `exit`

## Commit

```bat
@echo off
cd /d C:\GitHub\grove-autonomaton-primative
git add -A
git commit -m "pipeline-compliance-v1"
git push origin master
```
