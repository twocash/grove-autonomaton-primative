# Architecture: V-017 TPS Three-Beat UX

**Sprint:** V-017-tps-three-beat-ux
**Author:** Claude Code
**Date:** 2026-03-22

---

## Target State Overview

The Kaizen prompt will render as three visually distinct beats, each representing a TPS role. Visual elements (banners, bars, labels) are **config-driven** — they live in `kaizen.yaml`, not Python code.

```
┌─────────────────────────────────────────────────────────────┐
│  BEAT 1: JIDOKA (CYAN)                                      │
│  - ASCII art banner from config                             │
│  - Progress bar from config                                 │
│  - Label from config                                        │
│  - Diagnostic: summary, confidence, cost (from pipeline)    │
├─────────────────────────────────────────────────────────────┤
│  BEAT 2: ANDON (YELLOW)                                     │
│  - ASCII art banner from config                             │
│  - Progress bar from config                                 │
│  - Label from config                                        │
├─────────────────────────────────────────────────────────────┤
│  BEAT 3: KAIZEN (WHITE)                                     │
│  - ASCII art banner from config                             │
│  - Progress bar from config                                 │
│  - Label from config                                        │
│  - Prompt text from config                                  │
│  - Options from config (existing structure)                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│    pipeline.py   │────▶│     ux.py        │────▶│    Terminal      │
│                  │     │                  │     │                  │
│ _handle_kaizen_  │     │ ask_jidoka()     │     │ ANSI-colored     │
│ proposal()       │     │                  │     │ output           │
│                  │     │ diagnostic: dict │     │                  │
│ builds:          │     │ config: dict     │     │ Three beats:     │
│ - diagnostic     │     │                  │     │ - Jidoka (cyan)  │
│ - loads config   │────▶│ Reads banners    │────▶│ - Andon (yellow) │
│ - passes both    │     │ from config dict │     │ - Kaizen (white) │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

---

## Configuration Schema

### Target: `profiles/reference/config/kaizen.yaml`

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

---

## Function Signatures

### Current: `engine/ux.py:ask_jidoka()`

```python
def ask_jidoka(context_message: str, options: dict) -> str:
    """Present a Jidoka prompt requiring single-keystroke numeric response."""
```

### Target: `engine/ux.py:ask_jidoka()`

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

---

## Diagnostic Data Structure

Built by `pipeline.py:_handle_kaizen_proposal()`:

```python
diagnostic = {
    "summary": str,      # e.g., "No keyword match. No cache hit. Intent: unknown."
    "confidence": float, # e.g., 0.0 (from routing_info)
    "cost": float,       # e.g., 0.00 (pre-LLM, always 0)
}
```

---

## Rendering Logic

### Three-Beat Mode (when diagnostic and config provided)

```python
if diagnostic and config:
    # Beat 1: JIDOKA (cyan)
    jidoka = config.get("jidoka", {})
    print(f"{_c.CYAN}{jidoka.get('banner', '')}{_c.RESET}")
    print(f"{_c.CYAN}{jidoka.get('bar', '')}{_c.RESET}")
    print(f"  {jidoka.get('label', '')}")
    print(f"  {diagnostic.get('summary', '')}")
    print(f"  Confidence: {diagnostic.get('confidence', 0):.0%}  |  Cost: ${diagnostic.get('cost', 0):.2f}")
    print()

    # Beat 2: ANDON (yellow)
    andon = config.get("andon", {})
    print(f"{_c.YELLOW}{andon.get('banner', '')}{_c.RESET}")
    print(f"{_c.YELLOW}{andon.get('bar', '')}{_c.RESET}")
    print(f"  {andon.get('label', '')}")
    print()

    # Beat 3: KAIZEN (white/default)
    kaizen = config.get("kaizen", {})
    print(f"{_c.WHITE}{kaizen.get('banner', '')}{_c.RESET}")
    print(f"{_c.WHITE}{kaizen.get('bar', '')}{_c.RESET}")
    print(f"  {kaizen.get('label', '')}")
    print()

# Then existing context_message and options rendering...
```

### Legacy Mode (when diagnostic is None)

Existing behavior unchanged. Renders single "ANDON GATE" block.

---

## Color Constants

Uses existing `_c` (Colors) class in `ux.py`:

| Beat | Color | Constant |
|------|-------|----------|
| Jidoka | Cyan | `_c.CYAN` |
| Andon | Yellow | `_c.YELLOW` |
| Kaizen | White | `_c.WHITE` |

---

## Backward Compatibility Matrix

| Caller | Location | Current Args | After V-017 |
|--------|----------|--------------|-------------|
| Kaizen proposal | `pipeline.py:_handle_kaizen_proposal()` | `context_message, options` | `context_message, options, diagnostic, config` |
| Yellow zone | `pipeline.py` | `context_message, options` | No change |
| Red zone | `pipeline.py` | `context_message, options` | No change |
| Entity resolution | `pipeline.py` | `context_message, options` | No change |
| Clear cache | `dispatcher.py` | `context_message, options` | No change |

Only `_handle_kaizen_proposal()` passes the new parameters. All other callers continue working unchanged.

---

## File Dependencies

```
profiles/reference/config/kaizen.yaml
    │
    ▼ (loaded by)
engine/pipeline.py:_load_kaizen_config()
    │
    ├──▶ diagnostic dict (built from context)
    │
    ▼ (passed to)
engine/ux.py:ask_jidoka()
    │
    ▼ (reads banners, bars, labels from config)
Terminal output (ANSI colors)
```

---

## Constraints

1. **No new functions** — Extend `ask_jidoka()` only
2. **Config Over Code** — Zero presentation strings in Python
3. **Optional parameters** — `None` defaults for backward compatibility
4. **Existing callers unchanged** — Only `_handle_kaizen_proposal()` uses new params
