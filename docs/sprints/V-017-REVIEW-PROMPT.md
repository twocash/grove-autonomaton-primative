# Sprint Contract Review Prompt — V-017

> Paste this into a fresh Claude Desktop session. It will review the
> sprint spec CC produced and generate an atomic sprint contract.

---

## Prompt

You are reviewing a sprint specification for the Grove Autonomaton reference implementation. Your job is to produce an **atomic sprint contract** — a document tight enough that a Claude Code session can execute it without ambiguity, and narrow enough that it cannot drift into scope creep.

### Context

The Grove Autonomaton is a Python CLI that demonstrates the Autonomaton Pattern — a five-stage invariant pipeline for self-authoring software systems. The codebase is at `C:\GitHub\grove-autonomaton-primative`.

The sprint (V-017) transforms the Kaizen consent prompt from a single undifferentiated block into three visually distinct beats that make the Toyota Production System lineage visible in the UX:

- **Jidoka** — the watchman. Quality awareness discipline. Detects uncertainty. Reports the diagnostic.
- **Andon Gate** — the cord. The mechanism that stops the line. One beat. Decisive.
- **Kaizen** — the butler. Arrives after the line stops. Proposes improvement options. Needs human guidance.

### Your Task

1. **Read the sprint spec** at `C:\GitHub\grove-autonomaton-primative\docs\sprints\V-017-tps-three-beat-ux.md`

2. **Read the current implementation files** that will be modified:
   - `C:\GitHub\grove-autonomaton-primative\engine\ux.py` (the UX rendering module)
   - `C:\GitHub\grove-autonomaton-primative\engine\pipeline.py` (the invariant pipeline — specifically `_handle_kaizen_proposal()`)
   - `C:\GitHub\grove-autonomaton-primative\profiles\reference\config\kaizen.yaml` (the config file)
   - `C:\GitHub\grove-autonomaton-primative\profiles\reference\config\ux.yaml` (the tip config)

3. **Cross-reference against the architectural spec.** Read:
   - The white paper (Draft 1.3) — load from Google Drive if available, or from `profiles/reference/dock/autonomaton-pattern.md`
   - The Autonomaton HTML deck at `C:\GitHub\grove-autonomaton-primative\autonomaton.html` (the file is also in the Claude project)
   - `C:\GitHub\grove-autonomaton-primative\CLAUDE.md` for the architectural invariants

4. **Validate the sprint spec against these criteria:**

   **Invariant compliance:**
   - Does the change preserve the pipeline invariant? (UX only, no stage logic changes)
   - Does it respect Config Over Code? (All presentation strings in YAML, zero in Python)
   - Does it preserve Profile Isolation? (blank_template works without banners)
   - Does it preserve backward compatibility? (Yellow zone, Red zone, entity resolution callers unaffected)

   **Scope discipline:**
   - Is the diff small? (~30 lines across 2 Python files + config changes)
   - Does it touch ONLY the files listed? No surprise refactors?
   - Does it change any pipeline stage logic? (FAIL if yes)
   - Does it restructure any capability dispatch? (FAIL if yes)
   - Does it modify keystroke capture? (FAIL if yes)

   **TPS fidelity:**
   - Are the three roles correctly mapped? (Jidoka=diagnostic, Andon=stop, Kaizen=proposals)
   - Does the Jidoka beat show diagnostic context from the routing result?
   - Is the Andon beat one line / one moment?
   - Does the Kaizen beat contain the prompt and options (not the diagnostic)?
   - Are the ASCII art banners, bars, and labels in config (kaizen.yaml), not Python?

   **OOBE quality:**
   - Will a CTO seeing this for the first time understand three distinct architectural roles?
   - Does the visual treatment feel designed, not generated?
   - Do the `▰▰▰` bars and `[ ACT ] / [ DEF ]` paired labels survive the config?

5. **Produce the sprint contract.** The contract must include:

   **GATE DECISION:** APPROVED / APPROVED WITH CORRECTIONS / BLOCKED

   **If APPROVED:**
   - Restate the exact file list and expected line counts
   - Restate the acceptance test (what to type, what to see)
   - Restate the anti-requirements (what NOT to touch)
   - Include the commit message

   **If APPROVED WITH CORRECTIONS:**
   - List each correction with: what's wrong, why it violates the spec, what to do instead
   - Restate the corrected plan

   **If BLOCKED:**
   - Explain what's fundamentally wrong
   - Suggest whether to re-spec or abandon

### Format

Write the sprint contract as a markdown document. Keep it tight. A CC session reads this document and executes — nothing else needed. Every decision justified in terms of architectural compliance and how it exemplifies the benefits of the pattern.

### Quality bar

The contract is ready when a Claude Code session can read it, implement the change, run `python -m pytest`, run `python autonomaton.py --profile reference`, type an unknown input, see three distinct TPS beats, and commit — all without asking a single clarifying question.
