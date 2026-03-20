# SPRINT CONTRACT: Consent-Gated Classification

> Sprint: `consent-gated-classification-v1`
> Depends on: ux-polish-v1

---

## Pre-Sprint

### Task 0.1: Create worktree
```bat
cd /d C:\GitHub\grove-autonomaton-primative
git worktree add ..\grove-autonomaton-primative-consent-v1 master
cd /d C:\GitHub\grove-autonomaton-primative-consent-v1
```

### Task 0.2: Verify baseline
```cmd
python -m pytest tests/ -x -q
```

---

## Epic A: Remove Automatic LLM Escalation

**Gate:** classify() never calls the LLM. Keyword miss + cache
miss = return unknown. Zero money spent in Stage 2.

### Task A.1: READ cognitive_router.py classify()

Read the classify() method. Find the block (around line 284):
```python
if best_match is None or best_match[2] < self.LLM_ESCALATION_THRESHOLD:
    cache_result = self._check_pattern_cache(user_input)
    if cache_result is not None:
        return cache_result
    # Cache miss — escalate to LLM
    llm_result = self._escalate_to_llm(user_input)
    if llm_result is not None:
        return llm_result
    if best_match is None:
        return self._create_default_result()
```

### Task A.2: Remove LLM escalation from classify()

Replace that block with:
```python
if best_match is None or best_match[2] < self.LLM_ESCALATION_THRESHOLD:
    # THE RATCHET: Check pattern cache (Tier 0, free)
    cache_result = self._check_pattern_cache(user_input)
    if cache_result is not None:
        return cache_result
    # Cache miss — return unknown. Do NOT call LLM here.
    # LLM classification is an action that costs money.
    # Actions go through Stage 4 (Approval) before executing.
    # The pipeline handles consent. The router reports what it knows.
    if best_match is None:
        return self._create_default_result()
```

Do NOT delete _escalate_to_llm(). It moves from "automatic" to
"on-demand" — called by the pipeline after operator consent.

### GATE A

```bash
python -c "
content = open('engine/cognitive_router.py', encoding='utf-8').read()
# The classify method should not call _escalate_to_llm
classify_section = content[content.find('def classify('):content.find('def _create_default')]
assert '_escalate_to_llm' not in classify_section, \
    'classify() still calls _escalate_to_llm'
# But the method should still exist (moved to on-demand)
assert '_escalate_to_llm' in content, \
    '_escalate_to_llm was deleted — it should still exist for on-demand use'
print('PASS: LLM escalation removed from classify()')
"
python -m pytest tests/ -x -q
```

---

## Epic B: Kaizen Classification Prompt

**Gate:** When keywords and cache both miss, Stage 4 offers the
operator a choice. No money spent without consent.

### Task B.1: READ _handle_clarification_jidoka()

**File:** `engine/pipeline.py`

Read the entire method. Understand the current flow:
- Tier A: Shows LLM's best guess (but LLM already fired — WRONG)
- Tier B: Calls _generate_smart_clarification (another LLM — WRONG)
- Fallback: Config-driven options from clarification.yaml (CORRECT)

The Tier A and Tier B paths both assume the LLM has already fired
or should fire. After Epic A, the LLM has NOT fired. The method
needs to present the consent choice FIRST.

### Task B.2: Rewrite _handle_clarification_jidoka()

**File:** `engine/pipeline.py`

Replace the entire method with a Kaizen-style consent prompt:

```python
def _handle_clarification_jidoka(self) -> None:
    """
    Handle unknown input with Kaizen classification proposal.

    The Cognitive Router couldn't classify this from keywords or cache.
    Instead of auto-firing the LLM (which costs money), we ask the
    operator what they'd like to do. This is Kaizen, not Jidoka —
    the system isn't broken, it's proposing an improvement.

    Options:
    1. Consent to LLM classification (costs money, Ratchet caches it)
    2. Answer from local context (dock + persona, free)
    3. Pick from known capabilities (clarification.yaml, free)
    4. Rephrase (free)
    """
    from engine.cognitive_router import (
        get_clarification_options, resolve_clarification,
        get_router
    )
    from engine.ux import ask_jidoka
    from engine.telemetry import log_event

    # Build the Kaizen prompt
    options = {
        "1": "Use the LLM to understand this (fractions of a cent, cached after)",
        "2": "Answer from what you already know (free)",
    }

    # Add config-driven options from clarification.yaml
    config_options = get_clarification_options()
    if config_options:
        options["3"] = "Show me what you can help with (free)"

    options[str(len(options) + 1)] = "I'll rephrase"

    choice = ask_jidoka(
        context_message=(
            "I don't recognize this from my current vocabulary.\n"
            "I can use the LLM to learn what you mean — the Ratchet "
            "will cache it so it's free next time."
        ),
        options=options
    )

    # --- Option 1: Consent to LLM classification ---
    if choice == "1":
        # NOW the LLM fires — with consent, through the pipeline
        from engine.cognitive_router import get_router
        router = get_router()
        llm_result = router._escalate_to_llm(self.context.raw_input)

        if llm_result is not None and llm_result.intent != "unknown":
            # LLM classified successfully — update context
            self.context.intent = llm_result.intent
            self.context.domain = llm_result.domain
            self.context.zone = llm_result.zone
            self.context.entities["routing"] = {
                "tier": llm_result.tier,
                "confidence": llm_result.confidence,
                "handler": llm_result.handler,
                "handler_args": llm_result.handler_args or {},
                "extracted_args": llm_result.extracted_args or {},
                "intent_type": llm_result.intent_type,
                "action_required": llm_result.action_required,
                "llm_metadata": llm_result.llm_metadata or {}
            }
            self.context.approved = True

            log_event(
                source="kaizen_classification",
                raw_transcript=self.context.raw_input[:200],
                zone_context=self.context.zone,
                intent=self.context.intent,
                human_feedback="approved_classification",
                inferred={
                    "stage": "approval_kaizen",
                    "pipeline_id": self.context.telemetry_event.get("id"),
                    "resolved_intent": self.context.intent,
                    "classification_consented": True,
                }
            )
            return
        else:
            # LLM couldn't classify either — fall through to option 3
            log_event(
                source="kaizen_classification",
                raw_transcript=self.context.raw_input[:200],
                zone_context="yellow",
                intent="unknown",
                human_feedback="approved_classification",
                inferred={
                    "stage": "approval_kaizen",
                    "pipeline_id": self.context.telemetry_event.get("id"),
                    "llm_classification_failed": True,
                }
            )
            # Fall through to config options below

    # --- Option 2: Answer from local context ---
    if choice == "2":
        # Route to general_chat with informational intent_type
        # Compilation already loaded dock context
        self.context.intent = "explain_system"
        self.context.domain = "system"
        self.context.zone = "green"
        self.context.entities["routing"]["handler"] = "general_chat"
        self.context.entities["routing"]["intent_type"] = "informational"
        self.context.entities["routing"]["action_required"] = False
        self.context.approved = True

        log_event(
            source="kaizen_classification",
            raw_transcript=self.context.raw_input[:200],
            zone_context="green",
            intent="explain_system",
            human_feedback="local_context",
            inferred={
                "stage": "approval_kaizen",
                "pipeline_id": self.context.telemetry_event.get("id"),
                "resolved_intent": "explain_system",
                "used_local_context": True,
            }
        )
        return

    # --- Option 3: Config-driven options ---
    if choice == "3" and config_options:
        sub_choice = ask_jidoka(
            context_message="Here's what I can help with:",
            options=config_options
        )
        resolved = resolve_clarification(sub_choice, self.context.raw_input)
        self.context.intent = resolved.intent
        self.context.domain = resolved.domain
        self.context.zone = resolved.zone
        self.context.entities["routing"] = {
            "tier": resolved.tier,
            "confidence": resolved.confidence,
            "handler": resolved.handler,
            "handler_args": resolved.handler_args or {},
            "extracted_args": resolved.extracted_args or {},
            "intent_type": resolved.intent_type,
            "action_required": resolved.action_required,
            "llm_metadata": resolved.llm_metadata or {}
        }
        self.context.approved = True

        log_event(
            source="kaizen_classification",
            raw_transcript=self.context.raw_input[:200],
            zone_context=self.context.zone,
            intent=self.context.intent,
            human_feedback="clarified",
            inferred={
                "stage": "approval_kaizen",
                "pipeline_id": self.context.telemetry_event.get("id"),
                "resolved_intent": self.context.intent,
            }
        )
        return

    # --- Option 4 (or any unhandled): Rephrase ---
    self.context.approved = False
    self.context.result = {
        "status": "cancelled",
        "message": "Go ahead — I'm listening."
    }
```

### Task B.3: Remove _generate_smart_clarification()

**File:** `engine/pipeline.py`

Delete the entire `_generate_smart_clarification()` method. It
generated LLM-powered clarification options without consent.
The Kaizen prompt replaces it — with consent-gated LLM and
free config-driven options.

### Task B.4: Remove smart_clarification config gate

**File:** `engine/pipeline.py`

Delete the config-reading code I added for `smart_clarification`.
It was a workaround. The real fix is consent-gated classification.

**File:** `profiles/reference/config/routing.config`

Remove the `settings.smart_clarification: false` entry. No longer
needed.

### GATE B

```bash
python -c "
content = open('engine/pipeline.py', encoding='utf-8').read()
assert '_generate_smart_clarification' not in content, \
    'Smart clarification not removed'
assert 'kaizen_classification' in content, \
    'Kaizen classification prompt not added'
assert 'approved_classification' in content, \
    'Consent telemetry not added'
print('PASS: Consent-gated classification implemented')
"
python -m pytest tests/ -x -q
```

---

## Epic C: Cortex Domain Contamination

**Gate:** Zero coaching-domain terms in cortex.py lens prompts.

### Task C.1: Create cortex_config.yaml for coach_demo

**File:** `profiles/coach_demo/config/cortex_config.yaml`

If this file already exists (from domain-purity-v1), add the
missing lens prompts. If not, create it with:

```yaml
# Lens prompt configuration
lens_prompts:
  accountability_partner:
    role: "Coach's ACCOUNTABILITY PARTNER"
    goals: ["tithing", "revenue", "money"]
    donation_target: "First Tee donation"
  goal_categories:
    - "tithing"
    - "revenue"
    - "money"
```

### Task C.2: Create cortex_config.yaml for reference + blank

Minimal — no domain-specific lens prompts:
```yaml
lens_prompts: {}
goal_categories: []
```

### Task C.3: Refactor cortex.py to load from config

Find hardcoded "Coach's ACCOUNTABILITY PARTNER", "tithing goals",
"First Tee donation", and goal categories {"tithing", "revenue",
"money"}. Replace with config-driven loading from cortex_config.yaml.

### GATE C

```bash
python -c "
content = open('engine/cortex.py', encoding='utf-8').read()
for t in ['ACCOUNTABILITY PARTNER', 'tithing', 'First Tee']:
    assert t not in content, f'cortex.py still contains \"{t}\"'
print('PASS: Cortex domain-free')
"
python -m pytest tests/ -x -q
```

---

## Epic D: Missing Ratchet Routes

**Gate:** ratchet_intent_classify exists in all profiles.

### Task D.1: Add ratchet routes to reference and blank_template

Both profiles need the ratchet_intent_classify route. Without it,
the LLM classification (when operator consents) has no pipeline
route to execute through.

**Files:**
- `profiles/reference/config/routing.config`
- `profiles/blank_template/config/routing.config`

Add:
```yaml
  ratchet_intent_classify:
    tier: 2
    zone: green
    domain: system
    intent_type: actionable
    description: "Consent-gated LLM classification"
    handler: "ratchet_interpreter"
    handler_args:
      classifier: "intent"
      prompt_template: "classify_intent"
```

Ensure `profiles/reference/config/cognitive-router/prompts/classify_intent.md`
exists. Same for blank_template.

### GATE D

```bash
python -c "
import yaml
for p in ['reference', 'coach_demo', 'blank_template']:
    with open(f'profiles/{p}/config/routing.config') as f:
        config = yaml.safe_load(f)
    assert 'ratchet_intent_classify' in config.get('routes', {}), \
        f'{p}: missing ratchet route'
print('PASS: Ratchet routes in all profiles')
"
```

---

## Epic E: Test Fixes + New Tests

### Task E.1: Fix dock.query in test script

**File:** `tests/test_reference_ux.py`

Find `dock.query("five stage pipeline", top_k=2)`. The method
name may be different (query_dock, search, etc.). Read engine/dock.py
to find the correct method and fix the test.

### Task E.2: Add consent-gated classification test

```python
class TestConsentGatedClassification:
    """LLM classification must not fire without operator consent."""

    def test_classify_never_calls_llm(self):
        """classify() must return unknown, not call the LLM."""
        from engine.profile import set_profile
        from engine.cognitive_router import classify_intent, reset_router
        set_profile("reference")
        reset_router()
        # This phrase has no keyword match
        result = classify_intent("xyzzy foobarbaz nonexistent")
        assert result.intent == "unknown", \
            f"Expected unknown, got {result.intent} — LLM may have fired"
        assert result.tier != 2 or result.llm_metadata.get("source") == "pattern_cache", \
            "T2 classification without consent"

    def test_smart_clarification_removed(self):
        """No smart clarification method in pipeline."""
        content = open("engine/pipeline.py", encoding="utf-8").read()
        assert "_generate_smart_clarification" not in content
```

### Task E.3: Extend domain grep with cortex terms

Add to the domain term list in test_no_domain_terms_in_engine:
```python
"ACCOUNTABILITY PARTNER", "tithing", "First Tee",
```

### GATE E: Final

```bash
python -m pytest tests/ -x -q

python -c "
from pathlib import Path
terms = [
    'coaching', 'golf', 'swing', 'lesson', 'tournament',
    'handicap', 'ACCOUNTABILITY PARTNER', 'tithing', 'First Tee',
    'GOOGLE_CALENDAR_SCOPES', 'GMAIL_SCOPES',
    '_handle_mcp_calendar', '_handle_mcp_gmail',
    '_generate_smart_clarification',
]
engine = Path('engine/')
fails = []
for f in engine.glob('*.py'):
    code = [l for l in f.read_text(encoding='utf-8').split('\n')
            if not l.strip().startswith('#')]
    text = '\n'.join(code)
    for t in terms:
        if t in text:
            fails.append(f'{f.name}: {t}')
if fails:
    print('FAIL:')
    for f in fails: print(f'  {f}')
else:
    print('SHIP GATE PASSED')
"
```

---

## Post-Sprint: Commit & Merge

```bat
@echo off
cd /d C:\GitHub\grove-autonomaton-primative-consent-v1
git add -A
git commit -m "consent-gated-classification-v1"
cd /d C:\GitHub\grove-autonomaton-primative
git merge grove-autonomaton-primative-consent-v1
git push origin master
git worktree remove ..\grove-autonomaton-primative-consent-v1
```

---

## Verification Summary

| Claim | Test |
|-------|------|
| classify() never calls LLM | _escalate_to_llm removed from classify flow |
| Stage 4 offers Kaizen prompt | Unknown intent → 4 options, operator decides |
| Option 1 fires LLM with consent | Logged as approved_classification |
| Option 2 uses local context | Routes to dock-aware general_chat |
| Ratchet caches consented classification | Next time T0, no prompt |
| Smart clarification removed | _generate_smart_clarification deleted |
| Cortex domain-free | Zero coaching terms in lens prompts |
| Ratchet routes in all profiles | ratchet_intent_classify everywhere |
| No regressions | pytest exits 0 |
