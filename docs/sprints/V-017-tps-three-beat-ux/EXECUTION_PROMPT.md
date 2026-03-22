# Execution Prompt: V-017 TPS Three-Beat UX

**Sprint:** V-017-tps-three-beat-ux
**For:** Claude Code Executor
**Date:** 2026-03-22

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

### Step 1: Update kaizen.yaml

Replace `profiles/reference/config/kaizen.yaml` with three-beat structure:

```yaml
# Three-Beat TPS Display
# Jidoka (watchman) → Andon (cord) → Kaizen (butler)

jidoka:
  banner: |
       ___  _       _ __        __         ___     __      __
      / _ \(_)___ _(_) /_____ _/ /        / (_)___/ /___  / /______ _
     / // / / __ `/ / __/ __ `/ /    __  / / / __  / __ \/ //_/ __ `/
    /____/_/\__, /_/\__/\__,_/_/    /___/_/\__,_/\____/_/|_|\__,_/
           /____/
  bar: "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
  label: "[ ACT ] DISCIPLINE                       [ DEF ] Quality awareness."

andon:
  banner: |
       ___              __               ______      __
      / _ | ___  ___/ /___  ___     / ____/___ _/ /____
     / __ |/ _ \/ __  / __ \/ _ \  / / __/ __ `/ __/ _ \
    /_/ |_/_/ /_/\__,_/\____/_/ /_/ \____/\__,_/\__/\___/
  bar: "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
  label: "[ ACT ] MECHANISM                        [ DEF ] The signal that fires."

kaizen:
  banner: |
       __ __       _
      / //_/____ _(_)___  ___  ____
     / ,<  / __ `/ /_  / / _ \/ __ \
    / /| |/ /_/ / / / /_/  __/ / / /
    /_/ |_|\__,_/_/ /___/\___/_/ /_/
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

### Step 3: Modify _handle_kaizen_proposal() in pipeline.py

**Location:** `engine/pipeline.py` (around line 520)

**Replace:**
```python
def _handle_kaizen_proposal(self) -> None:
    config = self._load_kaizen_config()
    routing_info = self.context.entities.get("routing", {})

    # Build diagnostic from pipeline context
    diagnostic = {
        "summary": "No keyword match. No cache hit. Intent: unknown.",
        "confidence": routing_info.get("confidence", 0.0),
        "cost": 0.00,
    }

    # Get prompt and options from kaizen section (fallback to top-level)
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
    # ... rest of method unchanged
```

### Step 4: Update ux.yaml tip

**Location:** `profiles/reference/config/ux.yaml`

**Change kaizen_fired message:**
```yaml
kaizen_fired:
  priority: 3
  message: "Jidoka detected uncertainty. Andon stopped the line. Kaizen proposed options. Three TPS roles in one interaction."
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

## Final Verification

```bash
# Full test suite
python -m pytest

# YAML validation
python -c "import yaml; yaml.safe_load(open('profiles/reference/config/kaizen.yaml'))"

# Manual smoke test
python autonomaton.py --profile reference
# Type: "How does this handle regulatory compliance?"
# Expect: Three ASCII art banners (JIDOKA cyan, ANDON yellow, KAIZEN white)
# Press: 2
# Expect: Normal response
```

---

## Commit

```bash
git add profiles/reference/config/kaizen.yaml engine/ux.py engine/pipeline.py profiles/reference/config/ux.yaml
git commit -m "$(cat <<'EOF'
V-017-tps-three-beat-ux: Transform Kaizen prompt into three TPS beats

- kaizen.yaml: Three-beat structure with ASCII art banners
- ux.py: Add diagnostic/config params to ask_jidoka(), conditional render
- pipeline.py: Build diagnostic dict, pass config to ask_jidoka()
- ux.yaml: Update tip message for three TPS roles

Config Over Code: Banners live in YAML, not Python.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## What NOT to Touch

- `_kaizen_llm_classify()`, `_kaizen_local_context()`, etc.
- `_dispatch_kaizen_capability()`
- Keystroke capture logic
- Any pipeline stage logic
- Yellow zone, Red zone, entity resolution callers

---

## Artifacts Location

All sprint artifacts in: `docs/sprints/V-017-tps-three-beat-ux/`

- `REPO_AUDIT.md` — Current state analysis
- `SPEC.md` — Goals, acceptance criteria (re-read frequently!)
- `ARCHITECTURE.md` — Target state design
- `MIGRATION_MAP.md` — File-by-file changes
- `DECISIONS.md` — ADRs
- `SPRINTS.md` — Epic/story breakdown
- `EXECUTION_PROMPT.md` — This file
- `DEVLOG.md` — Execution tracking
- `CONTINUATION_PROMPT.md` — Session handoff
