# Execution Prompt: V-017 TPS Three-Beat UX

**Sprint:** V-017-tps-three-beat-ux
**For:** Claude Code Executor
**Date:** 2026-03-22
**Status:** APPROVED WITH CORRECTIONS (see SPRINT-CONTRACT.md)

---

## Attention Anchoring Protocol

Before any major decision, re-read:
1. `SPEC.md` Live Status block
2. `SPEC.md` Attention Anchor block

After every 10 tool calls:
- Check: Am I still pursuing the stated goal?
- If uncertain: Re-read SPEC.md Goals and Acceptance Criteria

Before committing:
- Verify: Does this change satisfy Acceptance Criteria?

---

## Mission

Transform the Kaizen prompt from a single "ANDON GATE" block into three visually distinct beats (Jidoka, Andon, Kaizen) using ASCII art banners from config.

**Success looks like:** ASCII art banners from config render in distinct colors (cyan, yellow, white) with diagnostic data.

**We are NOT:** Creating new functions, restructuring config for diagnostics, hardcoding banners in Python.

---

## PM Corrections Incorporated

Six corrections from SPRINT-CONTRACT.md:

1. **FIGlet banners** — Generate fresh ASCII art at execution time, verify in PowerShell
2. **ux.yaml already current** — Verify tip, skip if correct (VERIFIED: already has three-TPS message)
3. **Delete dead code** — Remove `_present_kaizen_options()` from pipeline.py
4. **Dynamic diagnostic** — Build summary from actual routing_info, not static string
5. **Update SMOKE-TEST.md** — Add to file list, update Test 2 expected output
6. **"Andon" not "Andon Gate"** — Banner text should be just "Andon"

---

## File List (5 files)

| Order | File | Action | Est. Lines Changed |
|-------|------|--------|-------------------|
| 1 | `profiles/reference/config/kaizen.yaml` | REPLACE — three-beat structure with verified FIGlet banners | ~55 (full rewrite) |
| 2 | `engine/ux.py` | MODIFY — add optional params, conditional three-beat render | ~35 net addition |
| 3 | `engine/pipeline.py` | MODIFY — build diagnostic, pass config, delete dead helper | ~15 net |
| 4 | `profiles/reference/config/ux.yaml` | VERIFY — tip already current, skip if confirmed | 0 |
| 5 | `SMOKE-TEST.md` | MODIFY — update Test 2 expected output | ~8 |

---

## Pre-Execution Verification

```bash
# Verify current branch
git branch --show-current

# Create worktree for sprint
git worktree add ../grove-v017-three-beat v012-dispatcher-extraction

# Verify tests pass before starting
cd ../grove-v017-three-beat
python -m pytest
```

---

## Execution Steps

### Step 0: Generate and Verify Banners (CRITICAL)

**Why:** ASCII art in planning docs is corrupted. Fresh generation prevents the most visible failure mode.

```bash
pip install pyfiglet
python -c "import pyfiglet; print(pyfiglet.figlet_format('Digital Jidoka', font='slant'))"
python -c "import pyfiglet; print(pyfiglet.figlet_format('Andon', font='slant'))"
python -c "import pyfiglet; print(pyfiglet.figlet_format('Kaizen', font='slant'))"
```

**Verification checklist:**
- [ ] Each banner ≤67 characters wide (matches bar length)
- [ ] Renders legibly in PowerShell
- [ ] Survives `yaml.safe_load()` round-trip

If `slant` exceeds width, try `small` or `standard`.

### Step 1: Replace kaizen.yaml

Replace `profiles/reference/config/kaizen.yaml` with three-beat structure.

**Use the FIGlet output from Step 0** — do NOT copy from planning docs.

```yaml
# Three-Beat TPS Display
# Jidoka (watchman) → Andon (cord) → Kaizen (butler)

jidoka:
  banner: |
    [PASTE FIGLET OUTPUT FOR "Digital Jidoka" HERE]
  bar: "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
  label: "[ ACT ] DISCIPLINE                       [ DEF ] Quality awareness."

andon:
  banner: |
    [PASTE FIGLET OUTPUT FOR "Andon" HERE]
  bar: "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
  label: "[ ACT ] MECHANISM                        [ DEF ] The signal that fires."

kaizen:
  banner: |
    [PASTE FIGLET OUTPUT FOR "Kaizen" HERE]
  bar: "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
  label: "[ ACT ] RESPONSE                         [ DEF ] The improvement proposal."
  prompt: |
    I can suggest some options here. The LLM can learn
    what you mean — the Ratchet will cache it so it's
    free next time.
  options:
    "1":
      label: "Use the LLM to classify (cached after)"
      capability: llm_classify
    "2":
      label: "Answer from what you already know (free)"
      capability: local_context
    "3":
      label: "Show me what you can help with (free)"
      capability: config_menu
    "4":
      label: "I'll rephrase"
      capability: cancel
```

**Verify:**
```bash
python -c "import yaml; c = yaml.safe_load(open('profiles/reference/config/kaizen.yaml')); print('jidoka:', 'banner' in c.get('jidoka', {}))"
```

### Step 2: Modify ask_jidoka() in ux.py

**Location:** `engine/ux.py`

**Change signature:**
```python
def ask_jidoka(
    context_message: str,
    options: dict,
    diagnostic: dict = None,
    config: dict = None
) -> str:
```

**Add three-beat rendering before existing print statements:**
```python
    # Three-beat TPS display when diagnostic and config provided
    if diagnostic and config:
        print()
        # Beat 1: JIDOKA (cyan)
        jidoka = config.get("jidoka", {})
        if jidoka.get("banner"):
            print(f"{_c.CYAN}{jidoka['banner']}{_c.RESET}")
        if jidoka.get("bar"):
            print(f"{_c.CYAN}{jidoka['bar']}{_c.RESET}")
        if jidoka.get("label"):
            print(f"  {jidoka['label']}")
        print(f"  {diagnostic.get('summary', '')}")
        conf = diagnostic.get('confidence', 0)
        cost = diagnostic.get('cost', 0)
        print(f"  Confidence: {conf:.0%}  |  Cost: ${cost:.2f}")
        print()

        # Beat 2: ANDON (yellow)
        andon = config.get("andon", {})
        if andon.get("banner"):
            print(f"{_c.YELLOW}{andon['banner']}{_c.RESET}")
        if andon.get("bar"):
            print(f"{_c.YELLOW}{andon['bar']}{_c.RESET}")
        if andon.get("label"):
            print(f"  {andon['label']}")
        print()

        # Beat 3: KAIZEN (white)
        kaizen = config.get("kaizen", {})
        if kaizen.get("banner"):
            print(f"{_c.WHITE}{kaizen['banner']}{_c.RESET}")
        if kaizen.get("bar"):
            print(f"{_c.WHITE}{kaizen['bar']}{_c.RESET}")
        if kaizen.get("label"):
            print(f"  {kaizen['label']}")
        print()
    else:
        # Legacy display (keep existing code)
        print()
        print(f"{_c.YELLOW}{'=' * 60}{_c.RESET}")
        print(f"{_c.BOLD}{_c.YELLOW}ANDON GATE: Stopping the line for human input{_c.RESET}")
        print(f"{_c.YELLOW}{'=' * 60}{_c.RESET}")
```

### Step 3: Modify pipeline.py

**Location:** `engine/pipeline.py`

#### 3a: Delete dead code `_present_kaizen_options()` (lines 546-550)

This helper becomes dead code after we inline the logic. Delete it entirely.

#### 3b: Update `_handle_kaizen_proposal()` with dynamic diagnostic

**Replace the method with:**
```python
def _handle_kaizen_proposal(self) -> None:
    config = self._load_kaizen_config()
    routing_info = self.context.entities.get("routing", {})

    # Build DYNAMIC diagnostic from what the pipeline actually observed
    tier = routing_info.get("tier", "unknown")
    confidence = routing_info.get("confidence", 0.0)
    source = self.context.classification_source if hasattr(self.context, 'classification_source') else None

    parts = []
    if source == "keyword":
        parts.append("Keyword matched but below confidence threshold.")
    elif source == "cache":
        parts.append("Cache hit but below confidence threshold.")
    else:
        parts.append("No keyword match. No cache hit.")
    parts.append(f"Intent: {self.context.intent or 'unknown'}")

    diagnostic = {
        "summary": " ".join(parts),
        "confidence": confidence,
        "cost": 0.00,
    }

    # Get prompt and options from kaizen section (fallback to top-level for backward compat)
    kaizen_section = config.get("kaizen", {})
    prompt = kaizen_section.get("prompt", config.get("prompt", "I don't recognize this input."))
    options_config = kaizen_section.get("options", config.get("options", {}))
    options = {k: v.get("label", k) for k, v in options_config.items()}

    choice = ask_jidoka(
        context_message=prompt,
        options=options,
        diagnostic=diagnostic,
        config=config
    )
    # ... rest of method unchanged (capability dispatch)
```

### Step 4: Verify ux.yaml (Skip if correct)

**Already verified:** The tip reads:
```yaml
kaizen_fired:
  priority: 3
  message: "Jidoka detected uncertainty. Andon stopped the line. Kaizen proposed options. Three TPS roles in one interaction."
```

**Action:** Skip. Note in DEVLOG that this was pre-completed.

### Step 5: Update SMOKE-TEST.md

**Location:** `SMOKE-TEST.md`, Test 2 section

Update the "Expected Kaizen prompt" to describe three-beat display:

```markdown
**Expected:** Three distinct TPS beats:
  - JIDOKA banner (cyan) with diagnostic: confidence, cost
  - ANDON banner (yellow) — line stopped
  - KAIZEN banner (white) with prompt and 4 numbered options
```

---

## Post-Epic Verification

After each step:

```bash
# Run tests
python -m pytest

# Update DEVLOG
echo "Step N complete. Tests: PASS/FAIL" >> docs/sprints/V-017-tps-three-beat-ux/DEVLOG.md

# ATTENTION ANCHOR: Re-read SPEC.md before next step
```

---

## Acceptance Test

```bash
# 1. YAML validates
python -c "import yaml; c = yaml.safe_load(open('profiles/reference/config/kaizen.yaml')); assert all(k in c for k in ['jidoka','andon','kaizen'])"

# 2. Signature correct
python -c "from engine.ux import ask_jidoka; import inspect; sig = inspect.signature(ask_jidoka); assert 'diagnostic' in sig.parameters and 'config' in sig.parameters"

# 3. Dead code removed (should return nothing)
grep -r "_present_kaizen_options" engine/

# 4. Full test suite
python -m pytest

# 5. Manual smoke test
python autonomaton.py --profile reference
# Type: "How does this handle regulatory compliance?"
# EXPECT: Three ASCII art banners render sequentially:
#   - "Digital Jidoka" in CYAN with diagnostic line (confidence, cost)
#   - "Andon" in YELLOW with mechanism label
#   - "Kaizen" in WHITE with prompt and 4 numbered options
# Press: 2 (local context)
# EXPECT: Normal dock-informed response. Glass shows kaizen flow.
```

---

## Quality Gate

Before committing, ALL must be YES:

1. Does each banner render as legible ASCII art in PowerShell?
2. Can a non-engineer reading kaizen.yaml understand what the three beats are?
3. Does the diagnostic line show what the system actually detected?
4. Does typing `hello` (keyword match) skip the three-beat display entirely?
5. Does the blank_template profile still start without errors?
6. Would a CTO watching this demo understand three distinct TPS roles without explanation?

---

## What NOT to Touch

- `_kaizen_llm_classify()` — internal LLM dispatch, not display
- `_kaizen_local_context()` — internal dock query, not display
- `_dispatch_kaizen_capability()` — routing logic, not display
- Keystroke capture functions — zero changes
- `confirm_yellow_zone()`, `confirm_red_zone_with_context()`, `resolve_entity_ambiguity()` — zero changes
- Pipeline stage logic (Stages 1-5) — zero changes
- `blank_template` profile — must still work with no kaizen.yaml
- Any test file — tests should pass as-is

---

## Commit

Single atomic commit after all steps verified:

```bash
git add profiles/reference/config/kaizen.yaml engine/ux.py engine/pipeline.py SMOKE-TEST.md
git commit -m "$(cat <<'EOF'
V-017-tps-three-beat-ux: Transform Kaizen prompt into three TPS beats

- kaizen.yaml: Three-beat structure with FIGlet ASCII art banners
- ux.py: Add diagnostic/config params to ask_jidoka(), conditional render
- pipeline.py: Build dynamic diagnostic dict, pass config, delete dead helper
- SMOKE-TEST.md: Update Test 2 expected output for three-beat display

Config Over Code: Banners live in YAML, not Python.
TPS lineage made visible: Jidoka (watchman) → Andon (cord) → Kaizen (butler)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Artifacts Location

All sprint artifacts in: `docs/sprints/V-017-tps-three-beat-ux/`

- `INDEX.md` — Sprint navigation
- `SPRINT-CONTRACT.md` — PM review with corrections
- `SPEC.md` — Goals, acceptance criteria (re-read frequently!)
- `EXECUTION_PROMPT.md` — This file
