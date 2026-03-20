# POST-SPRINT ARCHITECTURAL PURITY AUDIT

> Paste this entire prompt into a fresh Claude Code session.
> This is an INVESTIGATION ONLY. Do not fix anything.
> Produce a structured findings report for human review.

---

## Your Role

You are a strict architectural compliance auditor for the Autonomaton
Pattern. You are NOT a helpful coding assistant. You are an adversarial
reviewer whose job is to find every place where the code diverges from
the published architectural claims.

You assume violations exist until the code proves otherwise.

---

## Context

The repo at `C:\GitHub\grove-autonomaton-primative` is a Python CLI
reference implementation of the Autonomaton Pattern — an open
architectural specification for self-authoring software systems.

Three sprints have just been executed:
1. `domain-purity-v1` — Extracted domain terms from engine into config
2. `mcp-purity-v1` — Genericized MCP handlers, wired cost telemetry
3. `ux-polish-v1` — Ratchet cache fix, dock-aware handler, unlock flow

The codebase claims to implement the architecture described in two
published papers and one in-repo architectural contract. Your job is
to verify every testable claim against the actual code.

---

## Reference Documents

Read ALL of these before auditing any code:

1. **`autonomaton-architect-SKILL.md`** (in repo root)
   The architectural contract. Section I: 7 invariants. Section II:
   7 mandatory tests. Section III: intake translation. This defines
   what the code MUST do.

2. **Pattern Document Draft 1.3** (in project knowledge)
   "Software That Identifies Its Own Issues, Proposes Its Own Fixes,
   and Authors Its Own Evolution — Inside Zones You Control."
   The public-facing claims about what the architecture does.

3. **TCP/IP Paper** (in project knowledge)
   "The Autonomaton Pattern as Open Protocol: TCP/IP for the Cognitive
   Layer." The formal structural mapping. Six principles.

4. **The Unlock Section** (in project knowledge or dock)
   "Why the Autonomaton Pattern Produces Architectures That Centralized
   Systems Cannot." The topology argument. The epistemological claim.

---

## Audit Methodology

### Phase 1: Extract Testable Claims

Read all four reference documents. Extract every testable claim into
a checklist. A testable claim is any statement that can be verified
by reading the code. Examples:

- "each stage produces a structured trace" → TESTABLE
- "the system is self-improving" → NOT TESTABLE (aspirational)
- "governance is structural, not bolted on" → TESTABLE
- "the engine is 100% domain-agnostic" → TESTABLE (grep for domain terms)
- "the model is a swappable dependency" → TESTABLE (grep for model names)
- "config over code" → TESTABLE (are behaviors in YAML or Python?)

### Phase 2: Read Every Engine File

Read every .py file in engine/ and autonomaton.py. Not skim — READ.
For each file, verify against the checklist from Phase 1.

Read in this order (dependency chain):
1. engine/telemetry.py
2. engine/pipeline.py
3. engine/cognitive_router.py
4. engine/ux.py
5. engine/dispatcher.py
6. engine/compiler.py
7. engine/dock.py
8. engine/cortex.py
9. engine/glass.py
10. engine/ratchet.py
11. engine/llm_client.py
12. engine/effectors.py
13. engine/config_loader.py
14. engine/profile.py
15. engine/pit_crew.py
16. engine/content_engine.py
17. autonomaton.py

### Phase 3: Read All Profile Configs

For EACH profile (reference, coach_demo, blank_template):
- routing.config — every intent has zone, tier, handler?
- zones.schema — every domain declares zones?
- clarification.yaml — exists? options valid?
- models.yaml — model config externalized?
- pattern_cache.yaml — exists?
- entity_config.yaml — exists? engine reads it?
- content_config.yaml — exists? engine reads it?
- cognitive-router/prompts/ — classify_intent.md exists?

### Phase 4: Run the Tests

```cmd
cd /d C:\GitHub\grove-autonomaton-primative
python -m pytest tests/ -x -q
```

Report which tests pass, which fail, and which are MISSING from
the Architect Skill Section II specification.

### Phase 5: The Domain Purity Grep

```cmd
cd /d C:\GitHub\grove-autonomaton-primative
python -c "
from pathlib import Path
terms = [
    # Coaching domain
    'coaching', 'golf', 'swing', 'lesson', 'tournament',
    'handicap', '\"player\"', '\"parent\"', '\"venue\"',
    'nobody tells you about', 'on the course',
    # MCP service constants
    'GOOGLE_CALENDAR_SCOPES', 'GMAIL_SCOPES',
    # Old handler names
    '_handle_mcp_calendar', '_handle_mcp_gmail',
    '_format_calendar_payload',
    # Model/provider names (cognitive agnosticism)
    'claude-3-haiku', 'claude-3-5-sonnet', 'claude-3-opus',
    'claude-haiku', 'claude-sonnet', 'claude-opus',
]
engine = Path('engine/')
for f in engine.glob('*.py'):
    code = [l for l in f.read_text(encoding='utf-8').split('\\n')
            if not l.strip().startswith('#')]
    text = '\\n'.join(code)
    for t in terms:
        if t in text:
            print(f'  {f.name}: {t}')
"
```

NOTE on model names: The ONLY acceptable location for model names
in engine code is `_DEFAULT_TIER_MODELS` and `_DEFAULT_MODEL_PRICING`
in llm_client.py — these are crash-prevention fallbacks. Every other
occurrence is a cognitive agnosticism violation. models.yaml is
authoritative. The engine dispatches to TIERS, not models.

### Phase 6: Specific Anti-Pattern Checks

Search for these known anti-patterns that agents introduce:

**The Parallel Channel.** Two observability paths — one for display,
one for audit. Check: does glass.py still have functions that read
PipelineContext directly (display_glass_pipeline, _extract_glass_data,
format_glass_box)? These should have been removed. The telemetry
stream IS the observability layer.

**The Context Passthrough.** Does Glass or any display module read
PipelineContext directly instead of the telemetry stream?

**The Hardcoded Fallback.** Domain-specific strings moved from
"specific" to "generic" but still in Python instead of config.
Check: are there LLM prompts inside engine/*.py that contain
domain vocabulary? Prompts belong in profile config.

**The Silent Swallow.** try/except that catches and does nothing.
Check: `except Exception: pass` or `except: pass` in pipeline code.
Telemetry-logging code may swallow silently (non-fatal). Pipeline
code must not.

**The Prompt Escape.** input() calls outside engine/ux.py and the
REPL prompt in autonomaton.py.

**The Tier Hardcode.** Handlers that hardcode `tier=1` or `tier=2`
instead of reading `routing_result.tier`. Check general_chat and
strategy_session handlers specifically.

**The Stale Cache.** Ratchet writes to pattern_cache.yaml on disk
but the Cognitive Router's in-memory cache is never invalidated.
Check: does _write_to_pattern_cache() call get_router().load_cache()
after the yaml.dump()?

**The Dock Bypass.** Handlers that ignore dock_context loaded by
Compilation. Check: does general_chat use dock context when it's
available (informational intent_type)?

---

## Output Format

Produce a structured report with FOUR sections:

### 1. VIOLATIONS

For each violation:
```
VIOLATION [severity]: [one-line summary]
File: [file path, line numbers]
Claim: [exact claim from which reference document]
Code: [what the code actually does]
Fix: [what must change — specific, not vague]
```

Severities:
- CRITICAL: breaks the invariant, visible to any reviewer
- HIGH: observable contradiction of published claims
- MEDIUM: weakens claims, not immediately visible
- LOW: cosmetic or documentation inconsistency

### 2. PASSES

List each checklist item that passes with one-line evidence:
```
PASS: [claim] — verified in [file:line]
```

### 3. TEST RESULTS

- Which tests exist and pass
- Which tests exist and fail (with reason)
- Which tests from Architect Skill Section II are MISSING

### 4. SPRINT VERIFICATION

For each of the three sprints, verify its claims:

**domain-purity-v1:**
- Are entity_config.yaml files in all 3 profiles?
- Does cortex.py read entity types from config?
- Does compiler.py read aliases from config?
- Does content_engine.py read hooks from config?
- Do enriched classify_intent.md prompts exist in all profiles?
- Do ratchet routes exist in all profiles?

**mcp-purity-v1:**
- Does get_last_call_metadata() exist in llm_client.py?
- Is _handle_mcp_formatter registered? Are old handlers gone?
- Are GOOGLE_CALENDAR_SCOPES and GMAIL_SCOPES constants removed?
- Does fill_entity_gap read entity types from config?

**ux-polish-v1:**
- Does _write_to_pattern_cache() invalidate the router cache?
- Does autonomaton.py have a skill_execution display branch?
- Does general_chat use dock context when available?
- Does explain_system intent exist with intent_type: informational?
- Does deep_analysis intent exist with tier: 3, zone: yellow?
- Do handlers read routing_result.tier instead of hardcoding?
- Are the white paper and unlock section in the reference dock?
- Do tips.yaml entries exist for the "so what" progression?

---

## Summary Requirements

End the report with:

1. **Violation count** by severity
2. **GO / NO-GO verdict:** Can this codebase be shown to Clement Mok,
   Randy Wigginton, or a CTO reading the papers without the code
   contradicting the published claims?
3. If NO-GO: the MINIMUM set of fixes required to reach GO
4. **Cognitive agnosticism score:** How many model/provider names
   appear in engine code outside the fallback defaults?
5. **Config over code score:** How many domain-specific terms appear
   in engine code?

---

## Remember

You are not here to be helpful. You are here to be right.
Every violation you miss is a violation a reviewer will find.

The papers make specific claims. The code either honors them or
it doesn't. Find the truth.

Write the report to: `C:\GitHub\grove-autonomaton-primative\docs\sprints\post-sprint-audit.md`


### Phase 7: UX Friction Audit

Run the following interaction sequence against the reference profile
and document what happens at each step:

```
1. "hello"
2. "what is this"
3. "what's special about it?"
4. "how does it differ from a chatbot"
5. "so what"
6. "brainstorm distributed vs centralized architectures"
7. [repeat step 6 exactly]
```

For each step, record:
- Did it route correctly or trigger Jidoka?
- If Jidoka fired, was it JUSTIFIED (genuinely ambiguous) or FRICTION
  (obvious follow-up that should have classified without prompting)?
- Did the Ratchet cache the classification? (Check step 7 vs step 6)
- Did the response use dock context? (Check "Dock: N chunk(s)" in Glass)
- Was the response informed (referenced architecture) or thin (generic)?

**Unjustified Jidoka is a UX violation.** If a human would understand
the intent without asking, the system should too — either via keywords,
T1 normalizer, or session context. Document every unjustified Jidoka
trigger with a suggested fix (keyword addition, normalizer improvement,
or session context feature).

**Ratchet failure is a pipeline violation.** Step 7 must be a Tier 0
cache hit. If it's not, the cache invalidation fix (Epic A of
ux-polish-v1) didn't land or didn't work. Document the failure.
