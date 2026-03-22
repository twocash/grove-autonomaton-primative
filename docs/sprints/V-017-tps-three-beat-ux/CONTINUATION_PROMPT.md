# Continuation Prompt: V-017 TPS Three-Beat UX

## Instant Orientation

| Field | Value |
|-------|-------|
| **Project** | `C:\github\grove-autonomaton-primative` |
| **Sprint** | V-017-tps-three-beat-ux |
| **Current Phase** | Planning Complete → Ready for Execution |
| **Status** | 🟢 Ready for handoff |
| **Next Action** | Execute EXECUTION_PROMPT.md |

---

## Context Reconstruction

### Read These First (In Order)
1. `docs/sprints/V-017-tps-three-beat-ux/SPEC.md` — Live Status + Attention Anchor + Goals
2. `docs/sprints/V-017-tps-three-beat-ux/DEVLOG.md` — Last entry
3. `docs/sprints/V-017-tps-three-beat-ux/SPRINTS.md` — Epic breakdown

### Key Decisions Made
1. **Extend, don't create:** Add optional params to `ask_jidoka()`, no new function
2. **Config Over Code:** ASCII art banners live in `kaizen.yaml`, not Python
3. **Diagnostic from context:** Pipeline builds diagnostic dict from `routing_info`
4. **Three colors:** Jidoka (cyan), Andon (yellow), Kaizen (white)
5. **Backward compatible:** Existing callers continue working unchanged

### What's Done
- [x] REPO_AUDIT.md — Current state analysis
- [x] SPEC.md — Goals, acceptance criteria, attention anchor
- [x] ARCHITECTURE.md — Target state design
- [x] MIGRATION_MAP.md — File-by-file changes
- [x] DECISIONS.md — 6 ADRs
- [x] SPRINTS.md — 4 epics, 8 stories
- [x] EXECUTION_PROMPT.md — Self-contained handoff
- [x] DEVLOG.md — Execution tracking template
- [x] CONTINUATION_PROMPT.md — This file

### What's Pending
- [ ] Epic 1: Update kaizen.yaml with three-beat structure
- [ ] Epic 2: Modify ask_jidoka() in ux.py
- [ ] Epic 3: Modify _handle_kaizen_proposal() in pipeline.py
- [ ] Epic 4: Run tests and manual verification
- [ ] Commit: V-017-tps-three-beat-ux

---

## Resume Instructions

1. Read files listed above
2. Run: `python -m pytest` to verify current state (expect 234+ pass)
3. Follow EXECUTION_PROMPT.md step by step
4. Log progress in DEVLOG.md after each epic

---

## Attention Anchor

**We are building:** Three-beat TPS UX for Kaizen prompts (Jidoka → Andon → Kaizen)

**Success looks like:** ASCII art banners from config render in distinct colors with diagnostic data

**We are NOT:**
- Creating new functions
- Restructuring config for diagnostics
- Hardcoding banners in Python

**Current phase:** Planning Complete

**Next action:** Execute Epic 1 — Update kaizen.yaml

---

## Files to Modify (Summary)

| File | Change |
|------|--------|
| `profiles/reference/config/kaizen.yaml` | Three-beat structure with banners |
| `engine/ux.py` | Add diagnostic/config params, conditional render |
| `engine/pipeline.py` | Build diagnostic, pass config |
| `profiles/reference/config/ux.yaml` | Update tip message |

---

## Verification Commands

```bash
# YAML validation
python -c "import yaml; yaml.safe_load(open('profiles/reference/config/kaizen.yaml'))"

# Full test suite
python -m pytest

# Manual smoke test
python autonomaton.py --profile reference
# Type: "How does this handle regulatory compliance?"
# Expect: Three ASCII art banners
```
