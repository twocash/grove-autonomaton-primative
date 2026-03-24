# V-017: TPS Three-Beat UX — Jidoka, Andon, Kaizen

> *Sprint spec for Claude Code. One session. One fix. Clean commit.*
>
> **Commit message:** `V-017-tps-three-beat-ux`

---

## The Problem

The current Andon Gate display collapses three distinct Toyota Production
System roles into one undifferentiated UX block. A CTO watching the demo
sees a wall of text under "ANDON GATE" — they don't see the architecture
in action. The three TPS concepts that make this pattern distinctive are
invisible in the interaction.

### Current (collapsed) display:

```
============================================================
ANDON GATE: Stopping the line for human input
============================================================

I don't recognize this from my current vocabulary.
I can use the LLM to learn what you mean - the Ratchet
will cache it so it's free next time.

  [1] Use the LLM to classify this (fractions of a cent, cached after)
  [2] Answer from what you already know (free)
  [3] Show me what you can help with (free)
  [4] I'll rephrase

Enter choice [1/2/3/4]:
```

**What's wrong:**
- **Jidoka is invisible.** The watchman detected the issue but there's
  no diagnostic — WHAT did it detect? What failed? What does it know?
- **Andon and Kaizen are collapsed.** The cord pull and the butler's
  arrival happen in the same visual block. Two distinct moments blur.
- **No diagnostic context.** The white paper says the system "surfaces
  diagnostic context: which subsystem failed, what the expected behavior
  was." The current display surfaces nothing — just a generic message.

---

## The Mental Model

These are three characters in a factory drama. Each has a distinct role.
The UX must make all three visible.

**Jidoka — The Watchman.**
Always watching the line. Detected a quality issue in Stage 2
(Recognition). The watchman's job is to report what it saw: no keyword
match, no cache hit, confidence at 0%. The watchman does not propose
solutions. It reports the diagnostic.

**Andon Gate — The Cord.**
The watchman pulls the cord. The line stops. One line. Decisive.
"Line stopped." This is the structural moment — the system has the
authority to halt rather than produce a confident-sounding answer
from an uncertain pipeline.

**Kaizen — The Butler.**
Arrives after the line stops. The butler is calm, informed, helpful.
It suggests options: "I can help. Here's what we can do." The four
options are Kaizen's proposals — each a different cost/capability
trade-off. But the butler's proposals need human guidance. The
operator decides.

---

## The Fix: Three-Beat Display

### Target UX:

```
  ┌─ JIDOKA ──────────────────────────────────────────────┐
  │ No keyword match. No cache hit. Intent: unknown.       │
  │ Confidence: 0%  •  Cost so far: $0.00                  │
  └────────────────────────────────────────────────────────┘

  ⚡ ANDON GATE — Line stopped.

  ┌─ KAIZEN ──────────────────────────────────────────────┐
  │                                                        │
  │  I can suggest some options here. The LLM can learn     │
  │  what you mean — the Ratchet will cache it so it's     │
  │  free next time.                                       │
  │                                                        │
  │    [1] Use the LLM to classify (cached after)          │
  │    [2] Answer from what you already know (free)        │
  │    [3] Show me what you can help with (free)           │
  │    [4] I'll rephrase                                   │
  │                                                        │
  └────────────────────────────────────────────────────────┘

  Enter choice [1/2/3/4]:
```

### Three beats, three roles:

**Beat 1 — JIDOKA (diagnostic).** What the watchman detected. Shows:
match methods attempted (keyword, cache), result (no match), current
intent (unknown), confidence (0%), cost so far ($0.00). This is the
"surfaces diagnostic context" claim from the white paper (Part III §5).
Data comes from the RoutingResult already available in pipeline context.

**Beat 2 — ANDON GATE (the stop).** One line. The cord pull.
"Line stopped." Brief and decisive. This is the structural authority
the white paper describes: "the system has the authority to stop the
world the moment it needs human intuition."

**Beat 3 — KAIZEN (the butler's proposals).** The improvement options.
Warm, helpful, structured. Each option shows its cost implication.
The butler doesn't decide — it proposes. The operator makes the call.
This is Kaizen as described in the white paper: "proposes a specific
improvement" as a Yellow-zone action.

---

## Architectural Justification

### Why this matters for the Pattern Release

The TPS lineage is the pattern's most distinctive differentiator. Every
competing agent framework has guardrails. None of them have Jidoka,
Andon, and Kaizen as named, visible architectural roles. If a CTO
can't SEE these three roles operating in the demo, the lineage claim
is marketing — not architecture. This fix makes the claim visible.

### White Paper compliance

**Part II (Foundations):** "Jidoka transforms a machine from a blind,
repetitive engine into an active partner in quality control — one that
has the authority to stop the world the moment it needs human intuition."
The Jidoka box surfaces the diagnostic. The Andon line exercises the
authority. Currently both are invisible.

**Part III §5 (Digital Jidoka):** "The failure includes diagnostic
context: which subsystem failed, what error occurred, what the expected
behavior was, and what to check." The Jidoka box delivers this.
Currently the display shows zero diagnostic context.

**Part VI (Compounding):** "Kaizen means the system doesn't just stop.
It analyzes the failure pattern, generates a proposed repair, and
surfaces it as a Yellow-zone action." The Kaizen box is the proposed
repair. Separating it from the Andon stop makes the Kaizen role visible
as a distinct architectural contribution.

### TCP/IP Paper compliance

**§VI (Governance Innovation):** "The Autonomaton Pattern includes
governance as a first-class architectural commitment, not an afterthought."
Three-beat display makes governance visible in the interaction itself —
not just in config files and telemetry, but in the moment the operator
experiences it.

---

## Implementation Guide

### Config changes

**kaizen.yaml** — Split into three sections:

```yaml
# kaizen.yaml — Three-Beat TPS Display
# Jidoka (watchman) → Andon (cord) → Kaizen (butler)

# Beat 1: Jidoka diagnostic (rendered from pipeline context)
jidoka:
  template: |
    No keyword match. No cache hit. Intent: {intent}.
    Confidence: {confidence}%  •  Cost so far: ${cost}

# Beat 2: Andon Gate (the stop — always the same)
andon:
  message: "Line stopped."

# Beat 3: Kaizen proposals (the butler)
kaizen:
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

### ux.py changes

**Rename `ask_jidoka()` → `ask_tps_three_beat()`** (or add a new
function and deprecate the old one). The new function takes:

- `diagnostic`: dict with `{intent, confidence, cost, methods_tried}`
- `andon_message`: str (default "Line stopped.")
- `kaizen_prompt`: str (from kaizen.yaml)
- `kaizen_options`: dict (from kaizen.yaml)

Renders three visually distinct sections with box-drawing characters.
Colors: Jidoka in CYAN (diagnostic), Andon in YELLOW (alert), Kaizen
in WHITE/DIM (the butler is calm).

### pipeline.py changes

**`_handle_kaizen_proposal()`** — Pass diagnostic context from the
pipeline's current state to the UX function. The data is already
available:

```python
diagnostic = {
    "intent": self.context.intent,           # "unknown"
    "confidence": routing_info.get("confidence", 0.0),
    "cost": 0.00,                             # nothing spent yet
    "methods_tried": ["keyword", "cache"],    # what the router checked
}
```

Load the three-section config from kaizen.yaml and pass it to the
new UX function.

### Tips update

**ux.yaml** — Update the `kaizen_fired` tip:

```yaml
kaizen_fired:
  priority: 3
  message: >
    Jidoka detected uncertainty. The Andon Gate stopped the line.
    Kaizen proposed options. Three TPS roles — visible in one interaction.
```

This tip names all three roles and explains what just happened
architecturally.

---

## Files to Touch

| File | Action |
|---|---|
| `profiles/reference/config/kaizen.yaml` | Restructure into jidoka/andon/kaizen sections |
| `engine/ux.py` | New three-beat render function |
| `engine/pipeline.py` | Pass diagnostic context to UX |
| `profiles/reference/config/ux.yaml` | Update tip text |
| `SMOKE-TEST.md` | Update expected output for three-beat display |

---

## Acceptance Test

1. Type unknown input → see three distinct visual beats (Jidoka box, Andon line, Kaizen box)
2. Jidoka box shows: intent, confidence, cost, methods tried
3. Andon line is one line, visually distinct
4. Kaizen box shows prompt + numbered options
5. All four Kaizen options work (1=LLM, 2=local, 3=menu, 4=cancel)
6. Glass Pipeline still renders correctly after each option
7. The Ratchet still fires on repeated input after Option 1
8. All existing tests pass (the three-beat display is a UX change, not a pipeline change)

---

## CC Session Guardrails

**The correct implementation is ~40 lines of print() statements.**
If your diff adds more than 80 lines to ux.py, you over-engineered it.

### What CC MUST NOT do:
- Do NOT create a `TPSDisplayManager` class or any new abstraction
- Do NOT create a `RenderStrategy` or `BoxDrawer` utility
- Do NOT refactor the existing `ask_jidoka()` into something "better"
- Do NOT touch the keystroke capture logic (`_get_single_keystroke`)
- Do NOT touch pipeline stage logic — this is a DISPLAY change only
- Do NOT use Unicode box-drawing characters (they break in some Windows terminals). Use ASCII: dashes, pipes, plus signs

### What CC SHOULD do:
- Add a `diagnostic` parameter (dict, optional) to `ask_jidoka()`
- When `diagnostic` is provided, render three beats before the keystroke prompt
- When `diagnostic` is None, render the existing single-block display (backward compatible)
- Use the existing `_c` color constants — CYAN for Jidoka, YELLOW for Andon, DIM for Kaizen
- Keep the Kaizen prompt and options rendering exactly as-is, just visually separated

### The implementation is this simple:

```python
# In ask_jidoka(), BEFORE the existing prompt rendering:
if diagnostic:
    # Beat 1: Jidoka (watchman diagnostic)
    print(f"\n  {_c.CYAN}-- JIDOKA {'-' * 49}{_c.RESET}")
    print(f"  {_c.CYAN}|{_c.RESET} {diagnostic.get('summary', 'Unknown input detected.')}")
    print(f"  {_c.CYAN}|{_c.RESET} {_c.DIM}Confidence: {diagnostic.get('confidence', 0):.0%}  •  Cost so far: ${diagnostic.get('cost', 0):.2f}{_c.RESET}")
    print(f"  {_c.CYAN}{'-' * 60}{_c.RESET}")
    # Beat 2: Andon (the cord)
    print(f"\n  {_c.YELLOW}{_c.BOLD}ANDON GATE — Line stopped.{_c.RESET}\n")
    # Beat 3: Kaizen header (butler arrives)
    print(f"  {_c.DIM}-- KAIZEN {'-' * 49}{_c.RESET}")
```

Then the existing `context_message` and options rendering follows as-is.
That's the whole change to ux.py. ~12 lines.

### In pipeline.py, the change is:

```python
# In _handle_kaizen_proposal(), construct diagnostic from existing context:
diagnostic = {
    "summary": "No keyword match. No cache hit. Intent: unknown.",
    "confidence": self.context.entities.get("routing", {}).get("confidence", 0.0),
    "cost": 0.00,
}
# Pass to ask_jidoka:
choice = ask_jidoka(context_message=prompt, options=options, diagnostic=diagnostic)
```

That's ~5 lines in pipeline.py.

### Total diff: ~20 lines added across 2 files.

If the diff is larger than this, CC drifted from spec.

---

## Anti-Requirements

- Do NOT change pipeline logic. This is a UX rendering change only.
- Do NOT add new pipeline stages. Jidoka detection happens in Stage 2.
  The three-beat display happens in Stage 4 when the Andon Gate fires.
- Do NOT change the Kaizen capability dispatch. The `_kaizen_{capability}`
  methods are correct. Only the DISPLAY changes.
- The correct direction for line count is DOWN in pipeline.py. The UX
  rendering moves to ux.py where it belongs.

---

## Commit Message

`V-017-tps-three-beat-ux`

---

*"Jidoka transforms a machine from a blind, repetitive engine into an
active partner in quality control — one that has the authority to stop
the world the moment it needs human intuition."*

— Grove Autonomaton Pattern, Part II
