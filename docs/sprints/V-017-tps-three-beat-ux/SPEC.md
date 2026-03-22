# Specification: V-017 TPS Three-Beat UX

**Sprint:** V-017-tps-three-beat-ux
**Author:** Claude Code
**Date:** 2026-03-22
**Tier:** Sprint (1-3 days)

---

## Live Status

| Field | Value |
|-------|-------|
| **Current Phase** | Phase 7: Planning Complete |
| **Status** | 🟢 Ready for Execution |
| **Blocking Issues** | None |
| **Last Updated** | 2026-03-22T16:00:00Z |
| **Next Action** | Execute EXECUTION_PROMPT.md |
| **Attention Anchor** | Re-read before proceeding |

---

## Attention Anchor

**Re-read this block before every major decision.**

- **We are building:** Three-beat TPS UX rendering for Kaizen prompts (Jidoka → Andon → Kaizen)
- **Success looks like:** ASCII art banners from config render in distinct colors with diagnostic data
- **We are NOT:** Creating new functions, restructuring config for diagnostics, hardcoding banners in Python
- **Current phase:** Planning Complete
- **Next action:** Execute Epic 1 (update kaizen.yaml)

---

## Pattern Check

**Existing pattern to extend:** `ask_jidoka()` function in `engine/ux.py`
**Extension approach:** Add optional `diagnostic` and `config` parameters

**Canonical Source Audit:**

| Capability | Canonical Home | Recommendation |
|------------|----------------|----------------|
| Kaizen prompt rendering | `engine/ux.py:ask_jidoka()` | EXTEND |
| Kaizen configuration | `profiles/*/config/kaizen.yaml` | EXTEND |
| Pipeline diagnostic data | `PipelineContext` | INVOKE (exists) |

---

## Goal

Transform the Kaizen prompt from a single monolithic "ANDON GATE" block into three visually distinct beats that teach the TPS philosophy while surfacing diagnostic information. Each beat represents a distinct TPS role:

1. **Jidoka (Watchman)** — The discipline. Shows what the system detected.
2. **Andon (Cord)** — The mechanism. Signals the line has stopped.
3. **Kaizen (Butler)** — The response. Presents improvement options.

**Config Over Code:** All visual elements (banners, bars, labels) live in `kaizen.yaml`, not Python.

---

## Non-Goals

- ❌ Creating a new function for three-beat rendering
- ❌ Restructuring kaizen.yaml to hold diagnostic data (diagnostic comes from pipeline context)
- ❌ Hardcoding ASCII art banners in Python code
- ❌ Modifying existing callers of `ask_jidoka()` (Yellow zone, Red zone, entity resolution)
- ❌ Changing the keystroke capture logic
- ❌ Modifying pipeline stage logic

---

## Acceptance Criteria

- [ ] `ask_jidoka()` accepts optional `diagnostic: dict = None` and `config: dict = None` parameters
- [ ] When `diagnostic` and `config` are provided, three ASCII art banners render:
  - Jidoka banner in CYAN
  - Andon banner in YELLOW
  - Kaizen banner in WHITE
- [ ] Banners, bars, and labels are read from `kaizen.yaml`, not hardcoded
- [ ] Diagnostic data (summary, confidence, cost) displays under Jidoka beat
- [ ] Existing callers of `ask_jidoka()` (passing only `context_message` and `options`) continue to work unchanged
- [ ] `_handle_kaizen_proposal()` in pipeline.py builds diagnostic dict from context
- [ ] UX tip in `ux.yaml` updated to reference three TPS roles
- [ ] All 234+ existing tests pass
- [ ] SMOKE-TEST.md Test 2 verifies three-beat display

---

## Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| `engine/ux.py` | Available | Contains `ask_jidoka()` |
| `engine/pipeline.py` | Available | Contains `_handle_kaizen_proposal()` |
| `profiles/reference/config/kaizen.yaml` | Available | Flat structure, needs three-beat sections |
| `profiles/reference/config/ux.yaml` | Available | Contains tip messages |
| V-011 (TPS terminology) | Complete | Established Jidoka/Andon/Kaizen naming |
| SMOKE-TEST.md | Available | Test 2 covers Kaizen flow |

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Banner rendering issues in PowerShell | MEDIUM | LOW | Test in PowerShell before commit |
| Backward compatibility break | LOW | HIGH | Optional params with None defaults |
| YAML multiline escaping | MEDIUM | LOW | Verify with yaml.safe_load() |
| Test failures | LOW | MEDIUM | Run full pytest after changes |

---

## Implementation Notes

### Key Constraint: Config Over Code

The ASCII art banners MUST live in `kaizen.yaml`:

```yaml
jidoka:
  banner: |
       ___  _       _ __        __         ___     __      __
      / _ \(_)___ _(_) /_____ _/ /        / (_)___/ /___  / /______ _
     ...
  bar: "▰▰▰▰▰▰▰▰..."
  label: "[ ACT ] DISCIPLINE..."
```

The engine reads these strings and applies ANSI colors. Python contains no presentation strings.

### Backward Compatibility

```python
def ask_jidoka(context_message: str, options: dict, diagnostic: dict = None, config: dict = None) -> str:
```

When `diagnostic` is `None`, the function behaves exactly as before.

### Diagnostic Data Source

Diagnostic comes from pipeline context in `_handle_kaizen_proposal()`:

```python
diagnostic = {
    "summary": "No keyword match. No cache hit. Intent: unknown.",
    "confidence": routing_info.get("confidence", 0.0),
    "cost": 0.00,
}
```

---

## Verification Commands

```bash
# Pre-commit YAML validation
python -c "import yaml; print(yaml.safe_load(open('profiles/reference/config/kaizen.yaml'))['jidoka']['banner'])"

# Full test suite
python -m pytest

# Manual smoke test
python autonomaton.py --profile reference
# Type: "How does this handle regulatory compliance?"
# Expect: Three ASCII art banners (JIDOKA cyan, ANDON yellow, KAIZEN white)
```

---

## Provenance

- **Source:** REPO_AUDIT.md analysis + user corrections
- **Related:** V-011 (TPS terminology), SMOKE-TEST.md Test 2
- **Plan File:** `~/.claude/plans/recursive-waddling-marble.md`
