# V-017 TPS Three-Beat UX

**Status:** 🟢 Planning Complete — Ready for Execution
**Branch:** `v017-tps-three-beat-ux` (to be created)
**Date:** 2026-03-22

---

## Mission

Transform the Kaizen prompt from a single "ANDON GATE" block into three visually distinct beats (Jidoka, Andon, Kaizen) using ASCII art banners from config.

---

## Artifacts

| Artifact | Purpose |
|----------|---------|
| [REPO_AUDIT.md](./REPO_AUDIT.md) | Current state analysis |
| [SPEC.md](./SPEC.md) | Goals, acceptance criteria, attention anchor |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Target state design |
| [MIGRATION_MAP.md](./MIGRATION_MAP.md) | File-by-file changes |
| [DECISIONS.md](./DECISIONS.md) | ADRs (6 decisions) |
| [SPRINTS.md](./SPRINTS.md) | Epic/story breakdown (4 epics, 8 stories) |
| [EXECUTION_PROMPT.md](./EXECUTION_PROMPT.md) | Self-contained executor handoff |
| [DEVLOG.md](./DEVLOG.md) | Execution tracking |
| [CONTINUATION_PROMPT.md](./CONTINUATION_PROMPT.md) | Session handoff |

---

## Quick Start

**For Executor:**
```bash
# Read the execution prompt
cat docs/sprints/V-017-tps-three-beat-ux/EXECUTION_PROMPT.md

# Or resume from continuation
cat docs/sprints/V-017-tps-three-beat-ux/CONTINUATION_PROMPT.md
```

**For PM Review:**
```bash
# Read spec with acceptance criteria
cat docs/sprints/V-017-tps-three-beat-ux/SPEC.md
```

---

## Key Constraints

1. **No new function** — Extend `ask_jidoka()` only
2. **Config Over Code** — Banners in kaizen.yaml
3. **Backward compatible** — Optional params with None defaults

---

## Files to Modify

1. `profiles/reference/config/kaizen.yaml`
2. `engine/ux.py`
3. `engine/pipeline.py`
4. `profiles/reference/config/ux.yaml`
