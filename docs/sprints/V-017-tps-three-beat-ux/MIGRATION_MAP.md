# Migration Map: V-017 TPS Three-Beat UX

**Sprint:** V-017-tps-three-beat-ux
**Author:** Claude Code
**Date:** 2026-03-22

---

## Execution Order

Files must be modified in this order to maintain a working system:

| Order | File | Type | Reason |
|-------|------|------|--------|
| 1 | `profiles/reference/config/kaizen.yaml` | MODIFY | Add three-beat structure (banners, bars, labels) |
| 2 | `engine/ux.py` | MODIFY | Add optional params, conditional three-beat render |
| 3 | `engine/pipeline.py` | MODIFY | Build diagnostic dict, pass config to ask_jidoka |
| 4 | `profiles/reference/config/ux.yaml` | MODIFY | Update tip message |

---

## File 1: `profiles/reference/config/kaizen.yaml`

**Type:** MODIFY (replace flat structure with three-beat sections)

### Current State

```yaml
prompt: |
  I don't recognize this from my current vocabulary.
  I can use the LLM to learn what you mean - the Ratchet
  will cache it so it's free next time.

options:
  "1":
    label: "Use the LLM to classify this (fractions of a cent, cached after)"
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

### Target State

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

### Verification

```bash
python -c "import yaml; c = yaml.safe_load(open('profiles/reference/config/kaizen.yaml')); print('jidoka banner lines:', len(c['jidoka']['banner'].splitlines()))"
```

---

## File 2: `engine/ux.py`

**Type:** MODIFY (add optional parameters, conditional rendering)

### Change 1: Function Signature

**Location:** `ask_jidoka()` definition (around line 150)

**Before:**
```python
def ask_jidoka(context_message: str, options: dict) -> str:
    """
    Present a Jidoka prompt requiring single-keystroke numeric response.
    """
```

**After:**
```python
def ask_jidoka(
    context_message: str,
    options: dict,
    diagnostic: dict = None,
    config: dict = None
) -> str:
    """
    Present a Jidoka prompt requiring single-keystroke numeric response.

    When diagnostic and config are provided, renders three-beat TPS display.
    Otherwise, renders legacy single-block display for backward compatibility.

    Args:
        context_message: The prompt text to display
        options: Dict of {key: label} for user choices
        diagnostic: Optional dict with {summary, confidence, cost}
        config: Optional dict with {jidoka, andon, kaizen} sections

    Returns:
        The selected option key as string
    """
```

### Change 2: Three-Beat Rendering

**Location:** Inside `ask_jidoka()`, before existing print statements

**Insert:**
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
        # Legacy display (existing code)
        print()
        print(f"{_c.YELLOW}{'=' * 60}{_c.RESET}")
        print(f"{_c.BOLD}{_c.YELLOW}ANDON GATE: Stopping the line for human input{_c.RESET}")
        print(f"{_c.YELLOW}{'=' * 60}{_c.RESET}")

    # Continue with context_message and options (existing code)
```

---

## File 3: `engine/pipeline.py`

**Type:** MODIFY (`_handle_kaizen_proposal()` method)

### Change 1: Build Diagnostic Dict

**Location:** `_handle_kaizen_proposal()` (around line 520)

**Before:**
```python
def _handle_kaizen_proposal(self) -> None:
    config = self._load_kaizen_config()
    prompt = config.get("prompt", "I don't recognize this input.")
    options_config = config.get("options", {})
    options = {k: v.get("label", k) for k, v in options_config.items()}
    choice = ask_jidoka(context_message=prompt, options=options)
```

**After:**
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

    # Get prompt and options from kaizen section (not top-level for new structure)
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
```

**Notes:**
- Falls back to top-level `prompt` and `options` for backward compatibility
- Diagnostic data comes from `routing_info` in context
- Full config passed for banner rendering

---

## File 4: `profiles/reference/config/ux.yaml`

**Type:** MODIFY (update tip message)

### Change: kaizen_fired Tip

**Location:** `kaizen_fired` section

**Before:**
```yaml
kaizen_fired:
  priority: 3
  message: "Kaizen prompt fired. The system needs clarification."
```

**After:**
```yaml
kaizen_fired:
  priority: 3
  message: "Jidoka detected uncertainty. Andon stopped the line. Kaizen proposed options. Three TPS roles in one interaction."
```

---

## Files NOT to Modify

| File | Reason |
|------|--------|
| `engine/dispatcher.py` | Uses `ask_jidoka()` for cache clear — no change needed (optional params) |
| Yellow zone prompts | Pass `context_message, options` only — works unchanged |
| Red zone prompts | Pass `context_message, options` only — works unchanged |
| Entity resolution prompts | Pass `context_message, options` only — works unchanged |
| `_kaizen_llm_classify()` | Internal implementation, not display |
| `_kaizen_local_context()` | Internal implementation, not display |
| `_dispatch_kaizen_capability()` | Dispatch logic, not display |

---

## Rollback Plan

If issues arise:

1. Revert `kaizen.yaml` to flat structure (top-level `prompt` and `options`)
2. Remove conditional three-beat block from `ask_jidoka()`
3. Revert `_handle_kaizen_proposal()` to not pass `diagnostic` or `config`
4. Revert ux.yaml tip message

All changes are additive with backward-compatible defaults, so partial rollback is possible.

---

## Verification Sequence

```bash
# 1. YAML validation
python -c "import yaml; yaml.safe_load(open('profiles/reference/config/kaizen.yaml'))"

# 2. Unit tests
python -m pytest

# 3. Manual smoke test
python autonomaton.py --profile reference
# Type: "How does this handle regulatory compliance?"
# Expect: Three ASCII art banners
# Press: 2 (local context)
# Expect: Normal response
```
