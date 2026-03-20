# EXECUTION PROMPT: ux-polish-v1

> Copy this entire file into a fresh Claude Code session.
> No prior context required.

---

## Context

You are working on `grove-autonomaton-primative` — a Python CLI
reference implementation of the Autonomaton Pattern. The repo is
at `C:\GitHub\grove-autonomaton-primative`.

Windows machine. `cd /d C:\...` for directories. .bat for git.

**Read these files before writing code:**

1. `autonomaton-architect-SKILL.md` — architectural invariants
2. `docs/sprints/ux-polish-v1/SPEC.md` — the four fixes
3. `docs/sprints/ux-polish-v1/CONTRACT.md` — task-by-task

**Execute CONTRACT.md task-by-task. Do not skip gates.**

## The Four Fixes

| Fix | What | Where |
|-----|------|-------|
| R1 | Ratchet never fires — cache write not visible to router | engine/pipeline.py |
| F1 | Skill responses swallowed | autonomaton.py |
| F2 | general_chat ignores dock context | engine/dispatcher.py |
| F3+F4 | explain_system intent + white paper dock | profiles/reference/ |

## The Ratchet Bug (MOST IMPORTANT)

The pipeline writes to pattern_cache.yaml on disk. The Cognitive
Router loaded it into memory at startup. It never re-reads. The
Ratchet writes but the Router doesn't see. Fix: after yaml.dump(),
call get_router().load_cache(). Config changed, engine re-reads.
One line. This is Invariant #3: Config Over Code.

## Constraints

- **Create a git worktree** before editing.
- **Run `python -m pytest tests/ -x -q` after every epic.**
- **Cognitive agnosticism.** Zero model or provider names in code.
- **Let the architecture work.** Don't hardwire tiers. Don't swap
  handlers. Fix the pipeline violations. Let the Flywheel propose
  upgrades. The operator decides.


## The Unlock Flow (Epic F — NEW)

The reference profile ships TWO dock files: a white paper
condensation and an "unlock" section about distributed vs
centralized architectures. Tips guide the operator through a
tier escalation:

1. "what is this?" → explain_system (T1, informational, dock)
2. Tip: "So what? Try asking 'so what'"
3. "so what" → explain_system (T1, unlock section from dock)
4. Tip: "Want to go deeper?"
5. "brainstorm distributed vs centralized" → deep_analysis
   (T3, Yellow zone, apex cognition)
6. Glass shows: T3, Yellow, requires approval. Operator sees cost.
7. Ratchet caches it. Next time: free.

FIX REQUIRED: Both general_chat and strategy_session hardcode
their LLM tier. Change `tier=1` and `tier=2` to
`tier=routing_result.tier` so config drives the dispatch.
