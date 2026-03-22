# Repository Audit: V-017 TPS Three-Beat UX

**Sprint:** V-017-tps-three-beat-ux
**Auditor:** Claude Code
**Date:** 2026-03-22
**Scope:** Kaizen prompt UX rendering, TPS role visualization

---

## Current State Analysis

### 1. Kaizen Prompt Implementation

**File:** `engine/ux.py`

```python
def ask_jidoka(context_message: str, options: dict) -> str:
    """
    Present a Jidoka prompt requiring single-keystroke numeric response.
    """
    print()
    print(f"{_c.YELLOW}{'=' * 60}{_c.RESET}")
    print(f"{_c.BOLD}{_c.YELLOW}ANDON GATE: Stopping the line for human input{_c.RESET}")
    print(f"{_c.YELLOW}{'=' * 60}{_c.RESET}")
    print(f"\n{context_message}\n")
    # ... options and keystroke handling
```

**Assessment:**
- Single monolithic header ("ANDON GATE")
- Conflates three distinct TPS roles into one visual block
- Context message rendered as plain text
- No diagnostic information displayed
- No ASCII art banners

### 2. Kaizen Configuration

**File:** `profiles/reference/config/kaizen.yaml`

```yaml
prompt: |
  I don't recognize this from my current vocabulary.
  I can use the LLM to learn what you mean - the Ratchet
  will cache it so it's free next time.

options:
  "1":
    label: "Use the LLM to classify this (fractions of a cent, cached after)"
    capability: llm_classify
  # ... other options
```

**Assessment:**
- Flat structure with prompt + options
- No separation of TPS roles
- No banner configuration
- No diagnostic template

### 3. Pipeline Handler

**File:** `engine/pipeline.py` (lines 513-544)

```python
def _handle_kaizen_proposal(self) -> None:
    config = self._load_kaizen_config()
    prompt = config.get("prompt", "I don't recognize this input.")
    options_config = config.get("options", {})
    options = {k: v.get("label", k) for k, v in options_config.items()}
    choice = ask_jidoka(context_message=prompt, options=options)
    # ...
```

**Assessment:**
- Loads config correctly
- Passes flat prompt and options to ask_jidoka()
- Does NOT pass diagnostic data (intent, confidence, cost)
- Diagnostic data IS available in `self.context` and `routing_info`

### 4. Available Diagnostic Data

**In PipelineContext and routing_info:**

| Data | Location | Current Use |
|------|----------|-------------|
| `intent` | `self.context.intent` | Not shown to user |
| `confidence` | `routing_info.get("confidence")` | Not shown to user |
| `cost` | `self.context.cost` | Not shown to user |
| `classification_source` | `self.context.classification_source` | Not shown to user |
| `tier` | `routing_info.get("tier")` | Not shown to user |

**Assessment:** All diagnostic data exists but is not surfaced in the Kaizen prompt.

### 5. Other ask_jidoka() Callers

**Must maintain backward compatibility:**

| Caller | Location | Usage |
|--------|----------|-------|
| Yellow zone approval | `engine/pipeline.py` | General zone prompts |
| Red zone approval | `engine/pipeline.py` | High-stakes prompts |
| Entity resolution | `engine/pipeline.py` | Disambiguation prompts |
| Clear cache | `engine/dispatcher.py` | Confirmation prompt |

**Assessment:** These callers pass `context_message` and `options` only. New `diagnostic` and `config` parameters must be optional with `None` defaults.

---

## Technical Debt Identified

1. **UX/Logic Conflation:** Presentation strings in Python code
2. **TPS Role Invisibility:** Three distinct roles rendered as one block
3. **Diagnostic Opacity:** System knows why it stopped but doesn't tell user
4. **No Config for Banners:** Visual identity hardcoded in ux.py

---

## Pattern Check

**Existing Pattern to Extend:** `ask_jidoka()` function signature
**Extension Approach:** Add optional `diagnostic` and `config` parameters

**Canonical Source Audit:**

| Capability | Canonical Home | Recommendation |
|------------|----------------|----------------|
| Kaizen prompt rendering | `engine/ux.py:ask_jidoka()` | EXTEND |
| Kaizen configuration | `profiles/*/config/kaizen.yaml` | EXTEND |
| Pipeline diagnostic data | `PipelineContext` | INVOKE (already exists) |

---

## Files to Modify

| File | Type | Description |
|------|------|-------------|
| `engine/ux.py` | MODIFY | Add diagnostic/config params, three-beat render |
| `engine/pipeline.py` | MODIFY | Build diagnostic dict, pass config |
| `profiles/reference/config/kaizen.yaml` | MODIFY | Three-beat structure with banners |
| `profiles/reference/config/ux.yaml` | MODIFY | Update tip message |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Banner rendering issues | MEDIUM | LOW | Test in PowerShell before commit |
| Backward compatibility break | LOW | HIGH | Optional params with None defaults |
| YAML multiline escaping | MEDIUM | LOW | Verify with yaml.safe_load() |
| Test failures | LOW | MEDIUM | Run full pytest after changes |

---

## Provenance

- **Source:** Manual code review + Task agent exploration
- **Validated:** 2026-03-22
- **Related:** V-011 (TPS terminology), SMOKE-TEST.md Test 2
