# EXECUTION PROMPT: domain-purity-v1

> Copy this entire file into a fresh Claude Code session.
> It contains everything needed to execute the sprint.
> No prior context required.

---

## Context

You are working on `grove-autonomaton-primative` — a Python CLI
reference implementation of the Autonomaton Pattern (an AI governance
architecture). The repo is at `C:\GitHub\grove-autonomaton-primative`.

This is a Windows machine. Use `cd /d C:\...` for directory changes.
Write .bat files for git commit/push operations.

**Read these files IN ORDER before writing any code:**

1. `autonomaton-architect-SKILL.md` — The architectural contract.
   Section I defines 7 invariants. Section II defines mandatory tests.

2. `docs/sprints/domain-purity-v1/SPEC.md` — The audit findings
   and architectural rationale. Read the violation table and the
   Normalizer Flywheel section.

3. `docs/sprints/domain-purity-v1/CONTRACT.md` — The atomic
   execution contract. Every task, every file edit, every gate.

**Execute the CONTRACT.md task-by-task. Do not skip gates.**

## The Twelve Items Being Fixed

| ID | What | Where |
|----|------|-------|
| P1 | Coaching terms in cortex.py entity extraction | engine/cortex.py |
| P2 | Golf hooks in content_engine.py | engine/content_engine.py |
| P3 | Entity alias routing in compiler.py | engine/compiler.py |
| P4 | MCP handler names in dispatcher.py | DEFERRED |
| P5 | Google service names in effectors.py | DEFERRED |
| P6 | PipelineContext glass renderer dead code | engine/glass.py |
| P7 | Domain term test only checks 1 file | tests/ |
| P8 | cost_usd not in main stream | PARTIALLY ADDRESSED |
| P9 | Stale fallback model IDs | engine/llm_client.py |
| P10 | tmpclaude-* + orphan profiles | repo root |
| N1 | Classify_intent prompt lacks entities/sentiment | profiles/*/config/ |
| N2 | Ratchet routes missing from reference + blank | profiles/ |

## Two Thrusts

**Thrust 1 (Purity):** Extract ALL domain-specific terms from engine/
into profile-level YAML config files. After this sprint, `grep -r
"player\|coaching\|golf" engine/` returns zero results.

**Thrust 2 (Normalizer):** Enrich the T1 Cognitive Router classify_intent
prompt to extract entities, intent_type, and sentiment from user input.
ONE function call that creates telemetric clues which ratchet down
to Tier 0 deterministic over time. This is the "come to life" call.

## Critical Constraints

- **Windows CMD.** Git needs .bat files. Use `cd /d C:\...`.
- **Create a git worktree** before editing. Never work on master.
- **Profile must be set before importing engine modules.**
- **Run `python -m pytest tests/ -x -q` after EVERY epic.**
- **The engine grep test (Epic E) is the acceptance gate.**
  If domain terms remain in engine/, the sprint is not done.
- **Do not genericize MCP handlers.** P4 and P5 are deferred.
  The mcp_calendar/mcp_gmail handlers stay for now. Focus is on
  analytical code (cortex, content_engine, compiler) where domain
  terms are most visible to a reviewer.
- **COGNITIVE AGNOSTICISM IS HARDCORE.** The engine dispatches to
  TIERS, not models. Zero model names in engine code except the
  fallback defaults in llm_client.py (crash prevention only).
  Zero provider names anywhere. models.yaml maps tiers to model
  IDs. The engine is blind to what sits behind a tier. If you
  find yourself typing a model name in engine code, you are
  violating the architecture. Stop. Put it in models.yaml.

## The Normalizer Insight

The classify_intent prompt currently extracts: intent, confidence,
reasoning. Three fields. The minimum.

The enriched prompt extracts: intent, confidence, reasoning, PLUS
intent_type, entities (people/dates/amounts/references), sentiment,
and action_required. Seven fields. Same cost. Massively more signal.

This is ONE Tier 1 Cognitive Router call — fractions of a cent — that
fires when keyword matching can't classify the input. The engine
dispatches to whatever model sits behind Tier 1 in models.yaml.
The engine doesn't know what model that is. Doesn't care. Every
field lands in the Stage 2 telemetry trace. When the classification
is confirmed (approved + executed), the Ratchet writes ALL enriched
fields to pattern_cache.yaml.

Next time the same input appears: Tier 0 cache hit. $0.00. Instant.
With entities and sentiment preserved. The system remembers who was
mentioned, what dates were referenced, whether the tone was urgent.
All from a cached pattern that costs nothing.

This is how the system "comes to life" — it learns the operator's
vocabulary from the first few interactions, then serves it back free.
The normalizer is the mechanism. The Ratchet makes it permanent.
The Cognitive Router dispatches the minimum viable intelligence.
The tier determines the cost. The model is a swappable dependency.

## File Creation Checklist

New files this sprint must create:
- [ ] profiles/reference/config/entity_config.yaml
- [ ] profiles/coach_demo/config/entity_config.yaml
- [ ] profiles/blank_template/config/entity_config.yaml
- [ ] profiles/reference/config/content_config.yaml
- [ ] profiles/coach_demo/config/content_config.yaml
- [ ] profiles/blank_template/config/content_config.yaml
- [ ] profiles/reference/config/cognitive-router/prompts/classify_intent.md
- [ ] profiles/blank_template/config/cognitive-router/prompts/classify_intent.md
- [ ] Updated profiles/coach_demo/config/cognitive-router/prompts/classify_intent.md

## Ship Gate

```bash
# This command must return zero results
python -c "
from pathlib import Path
terms = ['coaching', 'golf', 'swing', 'lesson', 'tournament',
         'handicap', '\"player\"', '\"parent\"', '\"venue\"',
         'nobody tells you about', 'on the course',
         'google_calendar', 'GOOGLE_CALENDAR', 'GMAIL_SCOPES']
engine = Path('engine/')
fails = []
for f in engine.glob('*.py'):
    code = [l for l in f.read_text(encoding='utf-8').split('\n')
            if not l.strip().startswith('#')]
    text = '\n'.join(code)
    for t in terms:
        if t in text:
            fails.append(f'{f.name}: {t}')
if fails:
    print('FAIL:')
    for f in fails: print(f'  {f}')
else:
    print('SHIP GATE PASSED: Zero domain terms in engine/')
"

# Full test suite
python -m pytest tests/ -x -q
```
