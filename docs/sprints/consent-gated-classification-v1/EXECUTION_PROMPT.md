# EXECUTION PROMPT: consent-gated-classification-v1

> Copy this entire file into a fresh Claude Code session.
> No prior context. No improvisation. Execute verbatim.

---

## READ THESE FIRST. DO NOT SKIP.

```
1. autonomaton-architect-SKILL.md          (the invariants)
2. docs/sprints/consent-gated-classification-v1/SPEC.md  (why)
3. This file                                (how)
```

## THE RULE

One immutable pipeline. Some text files. That's it.

An LLM call costs money. Money is an action. Actions go through
Stage 4 (Approval). The LLM currently fires in Stage 2 without
consent. Fix this. Nothing else.

## CONSTRAINTS — MEMORIZE THESE

1. **Do NOT add code.** This sprint mostly REMOVES code.
2. **Do NOT add workarounds.** If a test fails, the test is wrong
   or the architecture is wrong. Fix the right thing.
3. **Do NOT rename methods, restructure files, or refactor anything
   not explicitly listed below.** Scope creep is the enemy.
4. **Verify after every step.** If verify fails, STOP. Do not proceed.
5. **Windows.** `cd /d C:\...` for dirs. `.bat` files for git commits.

---

## STEP 0: SETUP

```bat
cd /d C:\GitHub\grove-autonomaton-primative
git worktree add ..\grove-autonomaton-primative-consent-v1 master
cd /d C:\GitHub\grove-autonomaton-primative-consent-v1
python -m pytest tests/ -x -q
```

If tests fail, STOP. Fix nothing. Report what failed.

---

## STEP 1: REMOVE LLM FROM classify()

**File:** `engine/cognitive_router.py`
**Method:** `classify()`

Find this block (the if-branch after keyword matching):

```python
        if best_match is None or best_match[2] < self.LLM_ESCALATION_THRESHOLD:
            # THE RATCHET: Check pattern cache before calling LLM (purity-audit-v1)
            cache_result = self._check_pattern_cache(user_input)
            if cache_result is not None:
                return cache_result
            # Cache miss — escalate to LLM
            llm_result = self._escalate_to_llm(user_input)
            if llm_result is not None:
                return llm_result
            # If LLM fails and we had no keyword match, return default
            if best_match is None:
                return self._create_default_result()
```

Replace with:

```python
        if best_match is None or best_match[2] < self.LLM_ESCALATION_THRESHOLD:
            # THE RATCHET: Check pattern cache (Tier 0, free)
            cache_result = self._check_pattern_cache(user_input)
            if cache_result is not None:
                return cache_result
            # No keyword match, no cache hit. Return unknown.
            # The LLM is NOT called here. LLM calls cost money.
            # Money is an action. Actions go through Stage 4.
            # Stage 4 will offer the Kaizen prompt.
            if best_match is None:
                return self._create_default_result()
```

**DO NOT delete `_escalate_to_llm()`.** It still exists. It's
called from Stage 4 after consent, not from classify().

**VERIFY:**

```bash
python -c "
content = open('engine/cognitive_router.py', encoding='utf-8').read()
classify_start = content.find('def classify(')
classify_end = content.find('def _create_default')
classify_body = content[classify_start:classify_end]
assert '_escalate_to_llm' not in classify_body, \
    'FAIL: classify() still calls _escalate_to_llm'
assert 'def _escalate_to_llm' in content, \
    'FAIL: _escalate_to_llm was deleted — keep it for on-demand use'
print('STEP 1 PASS')
"
```

---

## STEP 2: DELETE _generate_smart_clarification()

**File:** `engine/pipeline.py`

Find the entire method `_generate_smart_clarification` and DELETE
it. The method starts with:

```python
    def _generate_smart_clarification(self, user_input: str) -> dict | None:
```

And ends just before the next method (`_compute_effective_zone`).

Delete the entire method. Nothing else references it after Step 3.

**VERIFY:**

```bash
python -c "
content = open('engine/pipeline.py', encoding='utf-8').read()
assert '_generate_smart_clarification' not in content, \
    'FAIL: _generate_smart_clarification still exists'
print('STEP 2 PASS')
"
```

---

## STEP 3: REPLACE _handle_clarification_jidoka()

**File:** `engine/pipeline.py`

Delete the ENTIRE current `_handle_clarification_jidoka()` method.
It starts with:

```python
    def _handle_clarification_jidoka(self) -> None:
        """
        Handle ambiguous input with diagnostic + smart clarification.
```

And ends just before `_generate_smart_clarification` (which you
already deleted) or `_compute_effective_zone`.

Replace it with the EXACT contents of:

```
docs/sprints/consent-gated-classification-v1/KAIZEN_HANDLER.py
```

Copy that file's contents VERBATIM into pipeline.py at the same
location. Do not modify, improve, or restructure it. Copy. Paste.

**VERIFY:**

```bash
python -c "
content = open('engine/pipeline.py', encoding='utf-8').read()
assert 'kaizen_classification' in content, \
    'FAIL: Kaizen handler not found'
assert 'approved_classification' in content, \
    'FAIL: Consent telemetry not found'
assert 'smart_clarification' not in content, \
    'FAIL: smart_clarification references remain'
assert 'Tier A' not in content, \
    'FAIL: Old Tier A/B logic remains'
assert 'Tier B' not in content, \
    'FAIL: Old Tier A/B logic remains'
print('STEP 3 PASS')
"
```

---

## STEP 4: REMOVE smart_clarification CONFIG LOADING

**File:** `profiles/reference/config/routing.config`

At the bottom, find and delete:

```yaml
settings:
  # Smart clarification uses LLM to generate context-aware options
  # when Jidoka fires. Costs money (T2 call per ambiguous input).
  # Set to false for demo profiles — use free clarification.yaml
  # options instead. The operator is never surprised by a bill.
  smart_clarification: false
```

Replace with:

```yaml
settings: {}
```

Do the same for `profiles/blank_template/config/routing.config`
and `profiles/coach_demo/config/routing.config` if they have it.

**VERIFY:**

```bash
python -c "
import yaml
for p in ['reference', 'blank_template', 'coach_demo']:
    try:
        with open(f'profiles/{p}/config/routing.config') as f:
            config = yaml.safe_load(f) or {}
        s = config.get('settings', {})
        assert 'smart_clarification' not in s, \
            f'FAIL: {p} still has smart_clarification setting'
    except FileNotFoundError:
        pass
print('STEP 4 PASS')
"
```

---

## STEP 5: ADD RATCHET ROUTE TO ALL PROFILES

**Files:**
- `profiles/reference/config/routing.config`
- `profiles/blank_template/config/routing.config`

Check if `ratchet_intent_classify` already exists in the routes
section. If not, add it inside the `routes:` block:

```yaml
  ratchet_intent_classify:
    tier: 2
    zone: green
    domain: system
    intent_type: actionable
    description: "Consent-gated LLM intent classification"
    keywords: []
    handler: "ratchet_interpreter"
    handler_args:
      classifier: "intent"
      prompt_template: "classify_intent"
```

Also verify the prompt template file exists:
- `profiles/reference/config/cognitive-router/prompts/classify_intent.md`
- `profiles/blank_template/config/cognitive-router/prompts/classify_intent.md`

If missing, copy from `profiles/coach_demo/config/cognitive-router/prompts/classify_intent.md`.
If that's also missing, create a minimal one:

```markdown
You are a Cognitive Router classifying user intent.

Given this input: "{user_input}"

Available intents:
{intent_list}

Return ONLY valid JSON:
{{"intent": "<intent_name>", "confidence": <0.0-1.0>, "reasoning": "<why>", "intent_type": "<conversational|informational|actionable>", "action_required": <true|false>}}
```

**VERIFY:**

```bash
python -c "
import yaml
for p in ['reference', 'blank_template', 'coach_demo']:
    try:
        with open(f'profiles/{p}/config/routing.config') as f:
            config = yaml.safe_load(f) or {}
        routes = config.get('routes', {})
        assert 'ratchet_intent_classify' in routes, \
            f'FAIL: {p} missing ratchet_intent_classify'
    except FileNotFoundError:
        pass
print('STEP 5 PASS')
"
```

---

## STEP 6: RUN ALL TESTS

```bash
python -m pytest tests/ -x -q
```

If tests fail, read the failure. The most likely failures:

1. **Tests that expected LLM escalation in classify()** — update
   them to expect `unknown` intent instead.
2. **Tests that reference smart_clarification** — delete those tests.
3. **Tests that test the old Tier A/B jidoka flow** — delete or
   rewrite to test the new 4-option Kaizen flow.

Fix ONLY test files. Do NOT change engine code to make tests pass.
If engine code is wrong, STOP and report.

**VERIFY:**

```bash
python -m pytest tests/ -x -q
```

Must exit 0.

---

## STEP 7: ADD CONSENT TEST

**File:** `tests/test_consent_classification.py` (new file)

```python
"""
Tests for consent-gated classification.

The LLM must never fire without operator consent.
classify() returns unknown for unrecognized input.
The Kaizen prompt in Stage 4 offers the operator a choice.
"""

from engine.profile import set_profile
from engine.cognitive_router import classify_intent, reset_router


class TestConsentGatedClassification:

    def setup_method(self):
        set_profile("reference")
        reset_router()

    def test_classify_returns_unknown_for_unrecognized_input(self):
        """classify() must return unknown, not call the LLM."""
        result = classify_intent("xyzzy foobarbaz nonexistent gibberish")
        assert result.intent == "unknown", \
            f"Expected unknown, got {result.intent}"
        assert result.confidence == 0.0, \
            f"Expected 0.0 confidence, got {result.confidence}"

    def test_classify_still_matches_keywords(self):
        """Keyword matching still works normally."""
        result = classify_intent("hello")
        assert result.intent == "general_chat"
        assert result.confidence >= 0.5

    def test_classify_still_hits_cache(self):
        """Pattern cache still works at Tier 0."""
        # This tests the Ratchet read path — if cache has an
        # entry, it returns at Tier 0 without LLM
        result = classify_intent("hello")
        assert result.tier in (0, 1)  # keyword or cache

    def test_smart_clarification_removed(self):
        """_generate_smart_clarification must not exist in pipeline."""
        content = open("engine/pipeline.py", encoding="utf-8").read()
        assert "_generate_smart_clarification" not in content

    def test_classify_does_not_call_escalate(self):
        """The classify method body must not reference _escalate_to_llm."""
        content = open("engine/cognitive_router.py", encoding="utf-8").read()
        classify_start = content.find("def classify(")
        classify_end = content.find("def _create_default")
        classify_body = content[classify_start:classify_end]
        assert "_escalate_to_llm" not in classify_body

    def test_escalate_method_still_exists(self):
        """_escalate_to_llm must still exist for on-demand use."""
        content = open("engine/cognitive_router.py", encoding="utf-8").read()
        assert "def _escalate_to_llm" in content
```

**VERIFY:**

```bash
python -m pytest tests/test_consent_classification.py -v
```

All 6 tests must pass.

---

## STEP 8: SHIP GATE

```bash
python -m pytest tests/ -x -q

python -c "
from pathlib import Path
terms = [
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
    print('SHIP GATE FAILED:')
    for f in fails: print(f'  {f}')
    exit(1)
else:
    print('SHIP GATE PASSED')
"
```

Both must pass.

---

## STEP 9: COMMIT AND MERGE

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

## WHAT YOU JUST DID

Before: LLM fires automatically in Stage 2. Operator surprised.
After: Stage 2 returns "unknown." Stage 4 asks the operator.
Operator says yes → LLM fires with consent → Ratchet caches it.
Operator says no → local context answers for free.

That's Jidoka (stop), Kaizen (propose), Ratchet (cache), sovereignty
(you consented). The whole thesis in one interaction.

## WHAT YOU DID NOT DO

- You did not refactor the dispatcher
- You did not restructure the pipeline
- You did not add new features
- You did not "improve" anything
- You removed bad code and replaced it with simple code

That's the sprint.
