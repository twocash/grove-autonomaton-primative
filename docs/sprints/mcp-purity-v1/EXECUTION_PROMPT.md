# EXECUTION PROMPT: mcp-purity-v1

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
2. `docs/sprints/mcp-purity-v1/SPEC.md` — The architectural rationale
   and anti-pattern warnings. READ THE ANTI-PATTERNS CAREFULLY.
3. `docs/sprints/mcp-purity-v1/CONTRACT.md` — The atomic execution
   contract. Every task, every file edit, every gate.

**Execute the CONTRACT.md task-by-task. Do not skip gates.**

## Prerequisite

domain-purity-v1 MUST be merged before this sprint starts. Verify:
```cmd
python -c "from pathlib import Path; assert Path('profiles/reference/config/entity_config.yaml').exists()"
```
If that fails, this sprint cannot proceed.

## The Five Epics

| Epic | What | Risk |
|------|------|------|
| A | Cost telemetry via metadata cache | LOW — additive, no interface changes |
| B | Generic MCP formatter handler | HIGH — replaces 2 handlers, updates routing |
| C | Effector scopes from config | MEDIUM — removes constants, adds config reads |
| D | Entity gap prompt from config | LOW — one prompt change |
| E | Test hardening | LOW — additive tests |

## Critical Constraints

- **Windows CMD.** Git needs .bat files. Use `cd /d C:\...`.
- **Create a git worktree** before editing. Never work on master.
- **Run `python -m pytest tests/ -x -q` after EVERY epic.**
- **Do NOT change call_llm() return type.** 24 call sites. Use the
  metadata cache pattern specified in Epic A.
- **Do NOT rename old handlers.** Delete them after the generic
  handler is registered and routing.config is updated.
- **Do NOT delete Google API implementation code.** Only the
  CONFIGURATION (scope constants, if/elif routing) changes.
- **COGNITIVE AGNOSTICISM IS HARDCORE.** Zero model names in
  engine code. Zero provider names. Dispatch to tiers. models.yaml
  maps tiers to models. The engine is blind.

## Ship Gate

```bash
python -c "
from pathlib import Path
terms = [
    'GOOGLE_CALENDAR_SCOPES', 'GMAIL_SCOPES',
    '_handle_mcp_calendar', '_handle_mcp_gmail',
    '_format_calendar_payload',
    'coaching', 'golf', 'swing', 'lesson', 'tournament',
    'handicap', '\"player\"', '\"parent\"', '\"venue\"',
]
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
    print('SHIP GATE PASSED')
"
python -m pytest tests/ -x -q
```
