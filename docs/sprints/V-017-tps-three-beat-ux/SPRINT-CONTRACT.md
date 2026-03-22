# Sprint Contract: V-017 — TPS Three-Beat UX

**Gate Decision: APPROVED WITH CORRECTIONS**

**Reviewer:** Claude Opus 4.6 (PM Review)
**Date:** 2026-03-22
**Sprint Artifacts Reviewed:** INDEX, SPEC, ARCHITECTURE, MIGRATION_MAP, DECISIONS, SPRINTS, EXECUTION_PROMPT, REPO_AUDIT
**Cross-Referenced Against:** Pattern Release Draft 1.3, TCP/IP Paper, autonomaton.html deck, SMOKE-TEST.md, current source code (ux.py, pipeline.py, kaizen.yaml, ux.yaml)

---

## Why This Sprint Matters

The HTML deck (slides 2-3) makes three architectural promises: Self-Identifying, Self-Fixing, Self-Authoring. The Kaizen prompt is where a CTO sees the first two happen live. Right now, the terminal renders a single yellow "ANDON GATE" block that conflates three distinct Toyota Production System roles into one undifferentiated wall of text. That's like a factory floor where the quality sensor, the stop cord, and the repair crew all wear the same uniform.

This sprint makes the TPS lineage visible. A CTO types something the system doesn't recognize and watches three deliberate beats unfold: Jidoka reports what it detected, Andon pulls the cord, Kaizen proposes next steps. Three colors. Three roles. Three seconds of architecture teaching itself. The deck's promise becomes terminal reality.

**Architectural justification:** Config Over Code (Invariant #2) demands that all presentation strings live in YAML. The current implementation hardcodes the "ANDON GATE" header in Python. This sprint fixes a standing violation while delivering the visual upgrade.

---

## Corrections Required Before Execution

The Foundation Loop artifacts are structurally sound. Six corrections prevent execution-time surprises.

### Correction 1: ASCII Art Banners Need Fresh Generation

**What's wrong:** The ASCII art in ARCHITECTURE.md and MIGRATION_MAP.md appears corrupted — character alignment is broken, especially in the "Andon Gate" banner where underscores and slashes don't form legible letters. Copy-pasting through YAML multiline boundaries and markdown code blocks introduces invisible whitespace damage.

**Why it matters:** If the banners don't render as readable words in a monospace terminal, the entire visual experience breaks. A CTO sees garbled characters instead of "Digital Jidoka."

**What to do instead:** The executor must generate fresh ASCII art using a FIGlet tool (or Python `pyfiglet` library) at execution time. Render each word, verify in PowerShell, then paste into kaizen.yaml. Suggested font: `slant` or `standard` (both produce clean, narrow output suitable for 80-column terminals).

```bash
pip install pyfiglet
python -c "import pyfiglet; print(pyfiglet.figlet_format('Digital Jidoka', font='slant'))"
python -c "import pyfiglet; print(pyfiglet.figlet_format('Andon', font='slant'))"
python -c "import pyfiglet; print(pyfiglet.figlet_format('Kaizen', font='slant'))"
```

Verify each banner is ≤67 characters wide (matches the bar length) and renders correctly when loaded through `yaml.safe_load()`. This is a five-minute step that prevents the most visible failure mode.

### Correction 2: ux.yaml Tip Is Already Current — Verify, Don't Modify

**What's wrong:** Story 1.2 says "Update kaizen_fired tip message." The current ux.yaml already contains:

```yaml
kaizen_fired:
  priority: 3
  message: "Jidoka detected uncertainty. Andon stopped the line. Kaizen proposed options. Three TPS roles in one interaction."
```

This is the exact target text from the spec. Story 1.2 is already done.

**What to do instead:** Verify the tip is present. Skip the modification. Note in DEVLOG that this was pre-completed (likely during V-011 or a previous planning session).

### Correction 3: Dead Code — `_present_kaizen_options()` Must Be Addressed

**What's wrong:** `pipeline.py` line 546 contains `_present_kaizen_options()`, a helper that extracts options from config. The spec's changes to `_handle_kaizen_proposal()` duplicate this logic inline (building `options` dict from `options_config`). After V-017, the helper becomes dead code.

**Why it matters:** Dead code in a reference implementation signals architectural drift. A CTO reading the pipeline sees two paths to the same result.

**What to do instead:** Delete `_present_kaizen_options()` (lines 546-549) and use the inline extraction in `_handle_kaizen_proposal()` as the spec describes. This is a net-negative line count change. Correct direction.

### Correction 4: Diagnostic Summary Should Be Dynamic, Not Static

**What's wrong:** The spec hardcodes: `"summary": "No keyword match. No cache hit. Intent: unknown."` This is accurate for the common case but ignores the actual routing result. If the router found a partial match or the cache had a near-miss, the summary should reflect what actually happened.

**Why it matters:** The Jidoka beat's purpose is diagnostic transparency. A static string undermines the "system tells you what it detected" promise from the deck (slide 2, card 01: "Detects its own quality degradation... surfaces diagnostic context").

**What to do instead:** Build the summary dynamically from `routing_info`:

```python
routing_info = self.context.entities.get("routing", {})
tier = routing_info.get("tier", "unknown")
confidence = routing_info.get("confidence", 0.0)
source = self.context.classification_source or "unknown"

# Build diagnostic from what the pipeline actually observed
parts = []
if source == "keyword":
    parts.append("Keyword matched but below confidence threshold")
elif source == "cache":
    parts.append("Cache hit but below confidence threshold")
else:
    parts.append("No keyword match. No cache hit.")
parts.append(f"Intent: {self.context.intent or 'unknown'}")

diagnostic = {
    "summary": " ".join(parts),
    "confidence": confidence,
    "cost": 0.00,
}
```

If `classification_source` doesn't exist on PipelineContext yet, fall back to the static string. But check first — the REPO_AUDIT lists it as available data.

### Correction 5: SMOKE-TEST.md Expectations Will Break

**What's wrong:** SMOKE-TEST.md Test 2 expects:

```
JIDOKA: Stopping the line for human input
```

After V-017, this becomes three ASCII art banners. The test expectations are stale.

**Why it matters:** Anyone running the smoke test after this sprint will see "different from expected" and flag it as a failure.

**What to do instead:** Add SMOKE-TEST.md to the file list. Update Test 2's "Expected Kaizen prompt" section to describe the three-beat display:

```
**Expected:** Three distinct TPS beats:
  - JIDOKA banner (cyan) with diagnostic: confidence, cost
  - ANDON banner (yellow) — line stopped
  - KAIZEN banner (white) with prompt and 4 numbered options
```

This is ~5 lines of change. Config Over Code still holds because SMOKE-TEST.md is documentation, not code.

### Correction 6: Banner Text Should Read "Andon" Not "Andon Gate"

**What's wrong:** The spec's Andon banner renders "Andon Gate" as the FIGlet text. But the white paper (Part II) and V-011 explicitly distinguish: Andon is the mechanism (the cord), the Gate is the implementation name for the UX pattern. The banner should say just "Andon" — the pure TPS concept. The `[ ACT ] MECHANISM` label already provides the role context.

**Why it matters:** Terminology precision is what makes the TPS lineage credible. The deck's slide 3 labels the three foundations cleanly. The terminal should match.

**What to do instead:** Generate FIGlet for "Andon" not "Andon Gate".

---

## Corrected Execution Plan

### File List (5 files, not 4)

| Order | File | Action | Est. Lines Changed |
|-------|------|--------|-------------------|
| 1 | `profiles/reference/config/kaizen.yaml` | REPLACE — three-beat structure with verified FIGlet banners | ~55 (full rewrite) |
| 2 | `engine/ux.py` | MODIFY — add optional params, conditional three-beat render | ~35 net addition |
| 3 | `engine/pipeline.py` | MODIFY — build diagnostic, pass config, delete dead helper | ~15 net (add diagnostic, delete `_present_kaizen_options`) |
| 4 | `profiles/reference/config/ux.yaml` | VERIFY — tip already current, skip if confirmed | 0 |
| 5 | `SMOKE-TEST.md` | MODIFY — update Test 2 expected output | ~8 |

**Total estimated diff:** ~50 lines added, ~15 removed. Net ~35 lines. Acceptable for a UX rendering change.

### Execution Sequence

**Step 0: Generate and verify banners (pre-implementation)**

```bash
pip install pyfiglet
python -c "import pyfiglet; print(pyfiglet.figlet_format('Digital Jidoka', font='slant'))"
python -c "import pyfiglet; print(pyfiglet.figlet_format('Andon', font='slant'))"
python -c "import pyfiglet; print(pyfiglet.figlet_format('Kaizen', font='slant'))"
```

Verify each banner: ≤67 chars wide, renders legibly in PowerShell, survives `yaml.safe_load()` round-trip. If `slant` exceeds width, try `small` or `standard`.

**Step 1: Replace kaizen.yaml** — per MIGRATION_MAP with verified banners from Step 0.

**Step 2: Modify ux.py** — extend `ask_jidoka()` signature, add three-beat conditional rendering block. Legacy path preserved for Yellow/Red zone callers.

**Step 3: Modify pipeline.py** — build dynamic diagnostic dict in `_handle_kaizen_proposal()`, pass config + diagnostic to `ask_jidoka()`. Delete `_present_kaizen_options()`. Update `kaizen_section` fallback logic for nested config structure.

**Step 4: Verify ux.yaml** — confirm tip already reads "Jidoka detected uncertainty. Andon stopped the line. Kaizen proposed options." If yes, skip. If no, update.

**Step 5: Update SMOKE-TEST.md** — revise Test 2 expected output to describe three-beat display.

**Step 6: Test and verify.**

### Acceptance Test

```bash
# 1. YAML validates
python -c "import yaml; c = yaml.safe_load(open('profiles/reference/config/kaizen.yaml')); assert all(k in c for k in ['jidoka','andon','kaizen'])"

# 2. Signature correct
python -c "from engine.ux import ask_jidoka; import inspect; sig = inspect.signature(ask_jidoka); assert 'diagnostic' in sig.parameters and 'config' in sig.parameters"

# 3. Dead code removed
# grep -r "_present_kaizen_options" engine/ returns zero results

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
# Press: 1 on next unknown input
# EXPECT: LLM classifies. Three beats still render before options.
```

### Anti-Requirements — What NOT to Touch

- `_kaizen_llm_classify()` — internal LLM dispatch, not display
- `_kaizen_local_context()` — internal dock query, not display
- `_dispatch_kaizen_capability()` — routing logic, not display
- Keystroke capture (`_get_single_keystroke`, `_get_keystroke_windows`, `_get_keystroke_unix`) — zero changes
- `confirm_yellow_zone()`, `confirm_red_zone_with_context()`, `resolve_entity_ambiguity()` — zero changes, backward compat via None defaults
- Pipeline stage logic (Stages 1-5 sequencing) — zero changes
- `blank_template` profile — must still work with no kaizen.yaml (legacy fallback handles this)
- Any test file — tests should pass as-is; no test modifications

### Commit

Single atomic commit after all steps verified:

```
V-017-tps-three-beat-ux
```

Use a .bat file for the commit on Windows.

---

## Invariant Compliance Verification

| Invariant | Impact | Status |
|-----------|--------|--------|
| Pipeline Invariant (5 stages) | Zero stage logic changes. UX rendering only. | PRESERVED |
| Config Over Code | Banners, bars, labels move FROM Python TO YAML. Net reduction of hardcoded strings. | ADVANCED |
| Zone Governance | Yellow/Red callers unchanged. Three-beat is Kaizen-only (Yellow zone prompt). | PRESERVED |
| Digital Jidoka | Diagnostic data now VISIBLE — the system tells the operator what it detected. | ADVANCED |
| Feed-First Telemetry | No telemetry changes. `kaizen_fired` event already logged. | PRESERVED |
| Profile Isolation | Banners in profile config. blank_template has no kaizen.yaml — legacy fallback fires. | PRESERVED |
| The Ratchet | No Ratchet changes. Cache write path unaffected. | PRESERVED |

---

## How This Exemplifies the Pattern

This sprint is a small change that validates three big claims from the deck:

**Claim 1 — "Self-Identifying" (Slide 2, Card 01).** The Jidoka beat shows diagnostic data: what the system detected, its confidence level, and the cost incurred. Before this sprint, the system knew why it stopped but didn't tell the operator. Now it does. Digital Jidoka becomes visible.

**Claim 2 — "Transparency as Architecture" (Slide 8).** The three-beat display is a miniature audit trail rendered in real time. A CTO watching the demo sees the system explain its own uncertainty — not because someone bolted on an observability layer, but because the pipeline's quality discipline has a visual surface. The governance comes free with the architecture.

**Claim 3 — "Config Over Code" (Slide 10, File 1).** Every visual element — banners, bars, labels, prompt text, option labels — lives in kaizen.yaml. A non-technical operator can change the Kaizen experience by editing a config file. No deploy. No code review. This is the "three files and a loop" story made tangible: the system's behavior is declared, not programmed.

The three-beat Kaizen prompt is the first moment in the demo where the Autonomaton stops being an abstract pattern and becomes a designed experience. It's where the TPS lineage earns its place in the architecture — not as a metaphor in a white paper, but as three distinct colors on a terminal screen.

---

## Quality Gate

Before the executor commits, these questions must all answer YES:

1. Does each banner render as legible ASCII art in PowerShell?
2. Can a non-engineer reading kaizen.yaml understand what the three beats are?
3. Does the diagnostic line show what the system actually detected?
4. Does typing `hello` (keyword match) skip the three-beat display entirely?
5. Does the blank_template profile still start without errors?
6. Would a CTO watching this demo understand three distinct TPS roles without explanation?

If any answer is NO, the sprint is not done.

---

*"Design is philosophy expressed through constraint."*
*This sprint expresses the TPS philosophy through terminal constraint.*
