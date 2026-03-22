# Decisions: V-017 TPS Three-Beat UX

**Sprint:** V-017-tps-three-beat-ux
**Author:** Claude Code
**Date:** 2026-03-22

---

## ADR-001: Extend ask_jidoka() Instead of Creating New Function

### Status
**ACCEPTED**

### Context
The sprint requires rendering three distinct TPS beats (Jidoka, Andon, Kaizen) in the Kaizen prompt. Two approaches were considered:

1. Create a new function `ask_jidoka_three_beat()` for the new display
2. Extend existing `ask_jidoka()` with optional parameters

### Decision
**Extend existing `ask_jidoka()` with optional `diagnostic` and `config` parameters.**

### Rationale
- **Single responsibility:** One function handles all Jidoka prompts
- **Backward compatibility:** Existing callers (Yellow zone, Red zone, entity resolution) continue working unchanged
- **No code duplication:** Shared keystroke capture logic remains in one place
- **Pattern alignment:** Matches the "extend, don't replace" philosophy

### Consequences
- Function signature grows (4 params instead of 2)
- Must handle `None` defaults gracefully
- All rendering logic in one function (could become complex)

---

## ADR-002: Banners as Config, Not Code (Config Over Code)

### Status
**ACCEPTED**

### Context
ASCII art banners need to be defined somewhere. Options:

1. Define as Python string constants in `ux.py`
2. Define in `kaizen.yaml` configuration file
3. Define in a separate `banners.yaml` file

### Decision
**Define banners in `kaizen.yaml` alongside the content they label.**

### Rationale
- **Invariant #2 (Config Over Code):** Domain logic belongs in configuration files, not code
- **Single source of truth:** Each TPS beat section contains its own banner, bar, and label
- **Operator customization:** Non-technical operators could modify banners without touching Python
- **No presentation strings in engine:** Engine code is "dumb pipes" that render config values

### Consequences
- YAML multiline strings require careful escaping
- Larger config file
- Must validate YAML loads correctly before committing

### Validation
```bash
python -c "import yaml; print(yaml.safe_load(open('profiles/reference/config/kaizen.yaml'))['jidoka']['banner'])"
```

---

## ADR-003: Diagnostic Data from Pipeline Context, Not Config

### Status
**ACCEPTED**

### Context
The Jidoka beat displays diagnostic information (summary, confidence, cost). This data could come from:

1. Config file (static values)
2. Pipeline context (dynamic, runtime values)

### Decision
**Diagnostic data is built from pipeline context in `_handle_kaizen_proposal()`.**

### Rationale
- **Dynamic data:** Confidence and cost vary per interaction
- **Separation of concerns:** Config holds presentation, pipeline holds runtime state
- **Accurate diagnostics:** Shows what the system actually detected, not placeholder text
- **Available data:** `routing_info` already contains confidence; cost is 0 pre-LLM

### Consequences
- `_handle_kaizen_proposal()` must build the diagnostic dict
- Diagnostic structure is defined in code (not config)
- Config structure remains focused on presentation

---

## ADR-004: Three Color Scheme (Cyan, Yellow, White)

### Status
**ACCEPTED**

### Context
Each TPS beat needs a distinct visual identity. Options:

1. All yellow (current monolithic style)
2. Traffic light (green, yellow, red)
3. Semantic (cyan = info, yellow = warning, white = neutral)

### Decision
**Semantic color scheme: Jidoka (cyan), Andon (yellow), Kaizen (white).**

### Rationale
- **Jidoka (cyan):** Informational — the watchman is reporting what was detected
- **Andon (yellow):** Warning — the cord has been pulled, attention required
- **Kaizen (white):** Neutral — presenting options without bias
- **Existing constants:** `_c.CYAN`, `_c.YELLOW`, `_c.WHITE` already defined in `ux.py`
- **Not traffic light:** Red reserved for high-stakes Red Zone prompts

### Consequences
- Clear visual hierarchy in terminal
- Consistent with existing color usage in the system

---

## ADR-005: Fallback to Legacy Display When Params Missing

### Status
**ACCEPTED**

### Context
When `diagnostic` or `config` is `None`, the function must still work.

### Decision
**When `diagnostic` and `config` are both provided, render three-beat. Otherwise, render legacy "ANDON GATE" block.**

### Rationale
- **Backward compatibility:** Yellow zone, Red zone, entity resolution prompts continue working
- **Explicit opt-in:** Only Kaizen proposal explicitly enables three-beat mode
- **Graceful degradation:** If config fails to load, falls back to working display

### Consequences
- Two rendering paths in one function
- Must test both paths

---

## ADR-006: Progress Bar from Config (Not Computed)

### Status
**ACCEPTED**

### Context
The progress bar between banner and label could be:

1. Static string from config
2. Computed based on terminal width
3. Unicode block characters at fixed length

### Decision
**Static Unicode block character string from config.**

```yaml
bar: "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
```

### Rationale
- **Simplicity:** No terminal width detection needed
- **Consistency:** Always same length regardless of terminal
- **Config Over Code:** Visual element lives in config
- **Unicode support:** PowerShell and modern terminals handle ▰ correctly

### Consequences
- May not fill full terminal width on wide terminals
- May wrap on narrow terminals (67 characters)

---

## Decision Summary

| Decision | Choice | Key Rationale |
|----------|--------|---------------|
| Function approach | Extend existing | Backward compatibility, no duplication |
| Banner location | kaizen.yaml | Config Over Code (Invariant #2) |
| Diagnostic source | Pipeline context | Dynamic runtime values |
| Color scheme | Cyan/Yellow/White | Semantic meaning, existing constants |
| Missing params | Legacy fallback | Backward compatibility |
| Progress bar | Static config string | Simplicity, Config Over Code |
