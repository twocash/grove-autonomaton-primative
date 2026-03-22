# Sprints: V-017 TPS Three-Beat UX

**Sprint:** V-017-tps-three-beat-ux
**Author:** Claude Code
**Date:** 2026-03-22

---

## Epic Overview

| Epic | Description | Stories |
|------|-------------|---------|
| Epic 1 | Config: Three-Beat Structure | 2 |
| Epic 2 | Engine: UX Rendering | 2 |
| Epic 3 | Engine: Pipeline Integration | 2 |
| Epic 4 | Verification | 2 |

**Total Stories:** 8

---

## Epic 1: Config — Three-Beat Structure

### Attention Checkpoint
Before starting this epic, verify:
- [ ] SPEC.md Live Status shows correct phase
- [ ] Goal alignment confirmed: banners in config, not code

### Story 1.1: Replace kaizen.yaml with Three-Beat Structure

**Task:** Replace flat `prompt`/`options` structure with `jidoka`/`andon`/`kaizen` sections containing banners, bars, labels.

**File:** `profiles/reference/config/kaizen.yaml`

**Acceptance:**
- [ ] `jidoka` section with banner, bar, label
- [ ] `andon` section with banner, bar, label
- [ ] `kaizen` section with banner, bar, label, prompt, options
- [ ] YAML loads without error

**Tests:**
```bash
python -c "import yaml; c = yaml.safe_load(open('profiles/reference/config/kaizen.yaml')); assert 'jidoka' in c and 'andon' in c and 'kaizen' in c"
```

### Story 1.2: Update ux.yaml Tip Message

**Task:** Update `kaizen_fired` tip to reference three TPS roles.

**File:** `profiles/reference/config/ux.yaml`

**Acceptance:**
- [ ] Tip message mentions Jidoka, Andon, Kaizen

**Tests:**
```bash
python -c "import yaml; c = yaml.safe_load(open('profiles/reference/config/ux.yaml')); assert 'Jidoka' in c.get('kaizen_fired', {}).get('message', '')"
```

### Build Gate (Epic 1)

```bash
python -c "import yaml; yaml.safe_load(open('profiles/reference/config/kaizen.yaml'))"
python -c "import yaml; yaml.safe_load(open('profiles/reference/config/ux.yaml'))"
```

---

## Epic 2: Engine — UX Rendering

### Attention Checkpoint
Before starting this epic, verify:
- [ ] Epic 1 complete (config exists)
- [ ] SPEC.md Attention Anchor reviewed
- [ ] No new function — extending ask_jidoka()

### Story 2.1: Extend ask_jidoka() Signature

**Task:** Add optional `diagnostic: dict = None` and `config: dict = None` parameters.

**File:** `engine/ux.py`

**Acceptance:**
- [ ] Function accepts 4 parameters
- [ ] Docstring updated
- [ ] Default values are `None`

**Tests:**
```bash
python -c "from engine.ux import ask_jidoka; import inspect; sig = inspect.signature(ask_jidoka); assert 'diagnostic' in sig.parameters and 'config' in sig.parameters"
```

### Story 2.2: Implement Three-Beat Rendering

**Task:** When `diagnostic` and `config` provided, render three beats with ANSI colors. Otherwise, render legacy display.

**File:** `engine/ux.py`

**Acceptance:**
- [ ] Jidoka beat renders in CYAN
- [ ] Andon beat renders in YELLOW
- [ ] Kaizen beat renders in WHITE
- [ ] Diagnostic data (summary, confidence, cost) displayed
- [ ] Legacy display when params missing

**Tests:**
```bash
python -m pytest tests/ -k "jidoka or kaizen" -v
```

### Build Gate (Epic 2)

```bash
python -m pytest tests/test_ux.py -v
```

---

## Epic 3: Engine — Pipeline Integration

### Attention Checkpoint
Before starting this epic, verify:
- [ ] Epic 2 complete (ux.py updated)
- [ ] SPEC.md Attention Anchor reviewed
- [ ] Diagnostic comes from pipeline context, not config

### Story 3.1: Build Diagnostic Dict in _handle_kaizen_proposal()

**Task:** Extract confidence from `routing_info`, build diagnostic dict.

**File:** `engine/pipeline.py`

**Acceptance:**
- [ ] `diagnostic` dict with `summary`, `confidence`, `cost`
- [ ] Confidence from `routing_info.get("confidence", 0.0)`
- [ ] Cost is `0.00` (pre-LLM)

### Story 3.2: Pass Config and Diagnostic to ask_jidoka()

**Task:** Load kaizen config, pass to `ask_jidoka()` along with diagnostic.

**File:** `engine/pipeline.py`

**Acceptance:**
- [ ] Config passed as `config` parameter
- [ ] Diagnostic passed as `diagnostic` parameter
- [ ] Prompt/options extracted from `kaizen` section with fallback to top-level

**Tests:**
```bash
python -m pytest tests/test_pipeline.py -v
```

### Build Gate (Epic 3)

```bash
python -m pytest -v
```

---

## Epic 4: Verification

### Attention Checkpoint
Before starting this epic, verify:
- [ ] All code changes complete
- [ ] Unit tests pass
- [ ] SPEC.md Acceptance Criteria ready to verify

### Story 4.1: Run Full Test Suite

**Task:** Verify all 234+ tests pass.

**Command:**
```bash
python -m pytest
```

**Acceptance:**
- [ ] All tests pass
- [ ] No new test failures

### Story 4.2: Manual Smoke Test (SMOKE-TEST.md Test 2)

**Task:** Execute manual verification per SMOKE-TEST.md.

**Steps:**
1. Clear cache: `python -c "from pathlib import Path; p = Path('profiles/reference/config/pattern_cache.yaml'); p.write_text('cache: {}')"`
2. Launch: `python autonomaton.py --profile reference`
3. Type: `How does this handle regulatory compliance?`
4. **Verify:** Three ASCII art banners display (Jidoka cyan, Andon yellow, Kaizen white)
5. Press: `2` (local context)
6. **Verify:** Normal response, Glass shows `kaizen → local context`

**Acceptance:**
- [ ] Three beats render with correct colors
- [ ] Diagnostic info (confidence, cost) displayed
- [ ] Option selection works
- [ ] Glass shows correct flow

### Build Gate (Epic 4)

```bash
python -m pytest && echo "All tests pass - ready for commit"
```

---

## Commit Sequence

| Order | Files | Message |
|-------|-------|---------|
| 1 | All files | `V-017-tps-three-beat-ux: Transform Kaizen prompt into three TPS beats` |

Single atomic commit after all epics complete and verified.

---

## Definition of Done

- [ ] All 4 epics complete
- [ ] All acceptance criteria met
- [ ] All tests pass (234+)
- [ ] Manual smoke test verified
- [ ] SPEC.md Live Status updated to Complete
- [ ] Committed with message `V-017-tps-three-beat-ux`
