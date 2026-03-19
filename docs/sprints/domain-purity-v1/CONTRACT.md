# SPRINT CONTRACT: Domain Purity + Normalizer Enrichment

> Atomic execution contract generated from SPEC.md
> Generated: 2026-03-19
> Sprint: `domain-purity-v1`

---

## Pre-Sprint: Hygiene & Baseline

### Task 0.1: Create worktree
```bat
@echo off
cd /d C:\GitHub\grove-autonomaton-primative
git worktree add ..\grove-autonomaton-primative-domain-purity-v1 master
cd /d C:\GitHub\grove-autonomaton-primative-domain-purity-v1
```

### Task 0.2: Delete tmpclaude files, orphan profiles, stale cache (P10)
```cmd
cd /d C:\GitHub\grove-autonomaton-primative-domain-purity-v1
del tmpclaude-*-cwd 2>nul
rmdir /s /q profiles\demo 2>nul
rmdir /s /q profiles\demon 2>nul
rmdir /s /q __pycache__ 2>nul
```

Add to `.gitignore` if not already present:
```
tmpclaude-*
__pycache__/
*.pyc
.pytest_cache/
```

### Task 0.3: Verify clean baseline
```cmd
python -m pytest tests/ -x -q
```
ALL existing tests must pass before any edits. Stop if they don't.

---

## Epic A: Engine Purity — Entity System (P1, P3)

**Gate:** Zero coaching-domain terms in cortex.py and compiler.py.
Entity type taxonomy, exclude words, alias mapping, and gap detection
rules all come from profile config.

### Task A.1: Create entity_config.yaml for coach_demo

**File:** `profiles/coach_demo/config/entity_config.yaml` (NEW)

```yaml
# entity_config.yaml
# Entity extraction configuration for this profile.
# The engine reads this — zero domain terms in engine code.

entity_types:
  - name: "player"
    plural: "players"
    default_alias: "a player"
  - name: "parent"
    plural: "parents"
    default_alias: "a parent"
  - name: "client"
    plural: "clients"
    default_alias: "a client"
  - name: "venue"
    plural: "venues"
    default_alias: "a venue"

# Capitalized words to EXCLUDE from entity name detection.
# Domain terms the operator uses that are NOT entity names.
exclude_domain_words:
  - "Coach"
  - "Player"
  - "Parent"
  - "Client"
  - "Venue"
  - "Session"
  - "Practice"
  - "Lesson"
  - "Tournament"
  - "Team"
  - "Golf"
  - "Swing"
  - "Revenue"
  - "Goal"
  - "Target"
  - "Content"
  - "Email"
  - "Call"

# Fields that trigger Kaizen gap proposals when missing
required_entity_fields:
  player:
    - "handicap"
    - "grade"
  parent:
    - "contact_email"

# Content mining pillars (used by cortex content seed extraction)
content_pillars:
  - "training"
  - "coaching"
  - "community"
  - "surrender"

content_seed_prompts:
  look_for:
    - "Moments of progress or breakthrough"
    - "Coaching insights or wisdom"
    - "Community building opportunities"
    - "Stories of perseverance"
```

### Task A.2: Create entity_config.yaml for reference

**File:** `profiles/reference/config/entity_config.yaml` (NEW)

```yaml
# entity_config.yaml — Reference profile (minimal)
entity_types:
  - name: "contact"
    plural: "contacts"
    default_alias: "a contact"
exclude_domain_words: []
required_entity_fields: {}
content_pillars: []
content_seed_prompts: {}
```

### Task A.3: Create entity_config.yaml for blank_template

**File:** `profiles/blank_template/config/entity_config.yaml` (NEW)

```yaml
# entity_config.yaml — Blank template (absolute minimum)
entity_types: []
exclude_domain_words: []
required_entity_fields: {}
content_pillars: []
content_seed_prompts: {}
```

### Task A.4: Add entity config loader to config_loader.py

**File:** `engine/config_loader.py` — add function:

```python
def load_entity_config() -> dict:
    """Load entity_config.yaml from active profile.

    Returns dict with keys: entity_types, exclude_domain_words,
    required_entity_fields, content_pillars, content_seed_prompts.
    Falls back to empty defaults if missing. Zero domain logic.
    """
    from engine.profile import get_config_dir
    import yaml

    defaults = {
        "entity_types": [],
        "exclude_domain_words": [],
        "required_entity_fields": {},
        "content_pillars": [],
        "content_seed_prompts": {},
    }
    try:
        config_path = get_config_dir() / "entity_config.yaml"
        if not config_path.exists():
            return defaults
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {k: data.get(k, v) for k, v in defaults.items()}
    except Exception:
        return defaults
```

### Task A.5: Refactor cortex.py — replace entity type taxonomy

**File:** `engine/cortex.py`

Find the hardcoded `type_map` (around line 431):
```python
type_map = {"player": "players", "parent": "parents", "client": "clients", "venue": "venues"}
subfolder = type_map.get(entity.entity_type, "players")
```

Replace with:
```python
from engine.config_loader import load_entity_config
entity_config = load_entity_config()
type_map = {t["name"]: t["plural"] for t in entity_config.get("entity_types", [])}
default_plural = list(type_map.values())[0] if type_map else "entities"
subfolder = type_map.get(entity.entity_type, default_plural)
```

### Task A.6: Refactor cortex.py — replace exclude words

Find the hardcoded exclude_words set (around line 291) containing
"Coach", "Player", "Parent", "Lesson", "Tournament", "Golf", "Swing".

KEEP the language-only words (days, months, pronouns, common verbs).
REMOVE every domain-specific term. LOAD domain terms from config:

```python
from engine.config_loader import load_entity_config
entity_config = load_entity_config()
domain_excludes = set(entity_config.get("exclude_domain_words", []))
exclude_words = COMMON_LANGUAGE_WORDS | domain_excludes
```

Where COMMON_LANGUAGE_WORDS is the existing set MINUS all domain terms.

### Task A.7: Refactor cortex.py — replace default entity type

Find `entity_type="player"` default (around line 313). Replace with:
```python
entity_config = load_entity_config()
default_type = entity_config["entity_types"][0]["name"] if entity_config.get("entity_types") else "entity"
```

### Task A.8: Refactor cortex.py — replace content pillars + seed prompts

Find hardcoded "training, coaching, community, surrender" and
"Coaching insights or wisdom" in the content seed mining prompt.
Replace with config-driven values from entity_config's
content_pillars and content_seed_prompts.

### Task A.9: Refactor cortex.py — replace gap detection rules

Find hardcoded gap detection for "handicap" field on "Player".
Replace with config-driven required_entity_fields lookup.

### Task A.10: Refactor compiler.py — replace entity alias mapping

Find the hardcoded alias logic (around line 73):
```python
if "players" in str(filepath): alias = "a player"
elif "parents" in str(filepath): alias = "a parent"
else: alias = "a team member"
```

Replace with config-driven lookup:
```python
from engine.config_loader import load_entity_config
entity_config = load_entity_config()
alias_map = {t["plural"]: t["default_alias"] for t in entity_config.get("entity_types", [])}
alias = "a contact"  # default
for plural, entity_alias in alias_map.items():
    if plural in str(filepath):
        alias = entity_alias
        break
```

### GATE A: Engine Purity (entity system)

```bash
python -c "
terms = ['\"player\"', '\"parent\"', '\"client\"', '\"venue\"',
         'coaching', 'golf', 'swing', 'handicap', 'Lesson',
         'Tournament', 'a team member']
for f in ['engine/cortex.py', 'engine/compiler.py']:
    content = open(f, encoding='utf-8').read()
    for t in terms:
        assert t not in content, f'{f} still contains {t}'
print('PASS: cortex.py + compiler.py domain-free')
"
python -m pytest tests/ -x -q
```

---

## Epic B: Engine Purity — Content Engine (P2)

### Task B.1: Create content_config.yaml for coach_demo

**File:** `profiles/coach_demo/config/content_config.yaml` (NEW)

```yaml
hooks:
  - "Here's the secret nobody tells you about golf..."
  - "Stop doing this on the course."
  - "Watch this transformation."
  - "The one thing that changed everything."
  - "Most players get this wrong."
signature_phrase_default: "Trust your practice."
platforms:
  tiktok: { max_length: 150, style: "hook-first" }
  instagram: { max_length: 300, style: "story-arc" }
  x: { max_length: 280, style: "thread-seed" }
```

### Task B.2: Create content_config.yaml for reference + blank

```yaml
# content_config.yaml — minimal
hooks: []
signature_phrase_default: ""
platforms: {}
```

### Task B.3: Add content_config loader to config_loader.py

```python
def load_content_config() -> dict:
    """Load content_config.yaml from active profile."""
    from engine.profile import get_config_dir
    import yaml
    defaults = {"hooks": [], "signature_phrase_default": "", "platforms": {}}
    try:
        path = get_config_dir() / "content_config.yaml"
        if not path.exists():
            return defaults
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {k: data.get(k, v) for k, v in defaults.items()}
    except Exception:
        return defaults
```

### Task B.4: Refactor content_engine.py — load hooks from config

Replace ALL hardcoded hooks with config-driven loading. Remove every
golf/coaching reference from the file.

### GATE B

```bash
python -c "
content = open('engine/content_engine.py', encoding='utf-8').read()
for t in ['golf', 'course', 'players get this']:
    assert t.lower() not in content.lower(), f'content_engine still has \"{t}\"'
print('PASS: content_engine.py domain-free')
"
python -m pytest tests/ -x -q
```

---

## Epic C: Normalizer Enrichment (N1, N2)

**Gate:** The T1 Cognitive Router classify_intent prompt extracts
intent + entities + intent_type + sentiment. Ratchet routes exist
in ALL profiles. Pattern cache stores and returns enriched fields.

### The Architecture

The Cognitive Router's keyword classifier handles known patterns
at Tier 0. When confidence is below threshold, it escalates to
the ratchet_intent_classify route, which dispatches through the
invariant pipeline to the ratchet_interpreter handler. That handler
loads a prompt template from the profile's config, calls the LLM
at whatever tier is configured (the engine is blind to which model
sits behind the tier — that's models.yaml's job), parses the
structured response, and returns it.

The enrichment: that prompt template now asks for entities and
sentiment alongside intent. ONE call. Same cost. More signal.
Everything lands in telemetry. Everything ratchets to Tier 0.

### Task C.1: Create enriched classify_intent.md for reference

**Dir:** `profiles/reference/config/cognitive-router/prompts/` (NEW)
**File:** `classify_intent.md`

```markdown
# Intent Classification + Entity Extraction

You are an intent classifier and entity extractor for an Autonomaton.
Classify the user's input AND extract any mentioned entities.

## Available Intents

{available_intents}

## User Input

"{user_input}"

## Instructions

1. Classify to the most specific matching intent
2. Extract entities: names, dates, amounts, or references mentioned
3. Determine intent_type: conversational (chat), informational (query), actionable (do something)
4. Assess sentiment: neutral, positive, negative, or urgent
5. If genuinely ambiguous, return intent="unknown" with low confidence
6. Greetings and small talk → general_chat, conversational, no entities

## Response Format (ONLY valid JSON, no markdown fences)

{
  "intent": "<intent_name>",
  "confidence": <0.0-1.0>,
  "intent_type": "conversational|informational|actionable",
  "action_required": true|false,
  "entities": {
    "people": [],
    "dates": [],
    "amounts": [],
    "references": []
  },
  "sentiment": "neutral|positive|negative|urgent",
  "reasoning": "<brief explanation>"
}
```

### Task C.2: Copy enriched prompt to coach_demo and blank_template

Replace `profiles/coach_demo/config/cognitive-router/prompts/classify_intent.md`
with the enriched version. Create the directory structure for
blank_template and copy the same prompt.

### Task C.3: Add ratchet routes to reference profile

**File:** `profiles/reference/config/routing.config` — append:

```yaml
  # --- Ratchet Classification Sub-Intents ---
  ratchet_intent_classify:
    tier: 2
    zone: green
    domain: system
    intent_type: actionable
    description: "T1 interpret layer for intent classification"
    handler: "ratchet_interpreter"
    handler_args:
      classifier: "intent"
      prompt_template: "classify_intent"
```

### Task C.4: Add ratchet routes to blank_template

Same as C.3 in `profiles/blank_template/config/routing.config`.

### Task C.5: Wire enriched fields through Recognition

**File:** `engine/cognitive_router.py`
**Method:** `_escalate_to_llm()`

Find the block that builds `llm_metadata` after successful
classification. Add entities and sentiment:

```python
llm_metadata = {
    "reasoning": classification.get("reasoning", ""),
    "classification_confidence": confidence,
    "via_pipeline": True,
    "entities": classification.get("entities", {}),
    "sentiment": classification.get("sentiment", "neutral"),
}
```

### Task C.6: Wire enriched fields into Stage 2 telemetry trace

**File:** `engine/pipeline.py` — `_run_recognition()` Stage 2 trace.

Add to the inferred dict of the log_event call:
```python
"entities": routing_info.get("llm_metadata", {}).get("entities", {}),
"sentiment": routing_info.get("llm_metadata", {}).get("sentiment"),
```

### Task C.7: Wire enriched fields into pattern cache writes

**File:** `engine/pipeline.py` — `_write_to_pattern_cache()`

In the cache entry dict, add:
```python
"entities": llm_metadata.get("entities", {}),
"sentiment": llm_metadata.get("sentiment", "neutral"),
```

### Task C.8: Wire enriched fields from cache hits

**File:** `engine/cognitive_router.py` — `_check_pattern_cache()`

Add to the llm_metadata in the returned RoutingResult:
```python
llm_metadata={
    "source": "pattern_cache",
    "cache_hash": input_hash,
    "entities": entry.get("entities", {}),
    "sentiment": entry.get("sentiment", "neutral"),
}
```

### GATE C: Normalizer Enrichment

```bash
python -c "
import yaml
for p in ['reference', 'coach_demo', 'blank_template']:
    path = f'profiles/{p}/config/routing.config'
    with open(path) as f:
        config = yaml.safe_load(f)
    assert 'ratchet_intent_classify' in config.get('routes', {}), f'{p}: missing ratchet route'
print('PASS: Ratchet routes in all profiles')
"
python -c "
from pathlib import Path
for p in ['reference', 'coach_demo', 'blank_template']:
    path = Path(f'profiles/{p}/config/cognitive-router/prompts/classify_intent.md')
    assert path.exists(), f'{p}: missing classify_intent.md'
    content = path.read_text()
    assert 'entities' in content, f'{p}: prompt missing entity extraction'
print('PASS: Enriched prompts in all profiles')
"
python -m pytest tests/ -x -q
```

---

## Epic D: Dead Code + Housekeeping (P6, P9)

### Task D.1: Remove PipelineContext-based glass renderer

**File:** `engine/glass.py`

Remove these functions (Context Passthrough anti-pattern):
- `_extract_glass_data(context: PipelineContext)`
- `format_glass_box(data: dict, level: str)`
- `display_glass_pipeline(context: PipelineContext, level: str)`

Keep:
- `read_pipeline_events()` — telemetry consumer (correct)
- `display_glass_from_telemetry()` — correct renderer
- `_render_stage_from_event()` — telemetry-based
- `TipEngine` — keep, refactor evaluate() to take dict not PipelineContext

Verify autonomaton.py calls `display_glass_from_telemetry` only.

### Task D.2: Update stale fallback model IDs (P9)

**File:** `engine/llm_client.py`

Update `_DEFAULT_TIER_MODELS` and `_DEFAULT_MODEL_PRICING` to match
current models.yaml values. Update module docstring.

CRITICAL: Do NOT hardcode model names anywhere they don't already
exist. The fallback defaults exist ONLY as crash prevention for
missing config. models.yaml is the authority. The engine dispatches
to tiers, not models. Model IDs in _DEFAULT are the ONLY acceptable
place for model names in engine code — and even there, the comment
must say "fallback only, models.yaml is authoritative."

### GATE D

```bash
python -c "
content = open('engine/glass.py', encoding='utf-8').read()
assert 'def display_glass_pipeline' not in content
assert 'def _extract_glass_data' not in content
print('PASS: Dead glass code removed')
"
python -m pytest tests/ -x -q
```

---

## Epic E: Test Suite Hardening (P7)

**Gate:** Engine grep test covers ALL 16 .py files. blank_template
runs "hello" without errors.

### Task E.1: Replace domain term test to scan ALL engine files

**File:** `tests/test_pipeline_compliance.py`

Replace `test_no_domain_terms_in_cognitive_router` with:

```python
def test_no_domain_terms_in_engine(self):
    """Scan ALL engine files for domain-specific terms."""
    domain_terms = [
        "coaching", "golf", "swing", "lesson", "tournament",
        "handicap", '"player"', '"parent"', '"venue"',
        "google_calendar", "GOOGLE_CALENDAR", "GMAIL_SCOPES",
        "nobody tells you about", "on the course",
    ]
    engine_dir = Path("engine/")
    violations = []
    for py_file in engine_dir.glob("*.py"):
        code_lines = [l for l in py_file.read_text(encoding="utf-8").split("\n")
                      if not l.strip().startswith("#")]
        code = "\n".join(code_lines)
        for term in domain_terms:
            if term in code:
                violations.append(f"{py_file.name}: contains '{term}'")
    assert not violations, "Domain terms in engine:\n" + "\n".join(violations)
```

### Task E.2: Add blank_template pipeline run test

**File:** `tests/test_pipeline_compliance.py`

```python
class TestBlankTemplateIsolation:
    """Architect §II Test 6: blank_template runs without errors."""

    def test_blank_template_hello(self):
        from engine.profile import set_profile
        from engine.cognitive_router import reset_router
        from engine.pipeline import run_pipeline
        set_profile("blank_template")
        reset_router()
        ctx = run_pipeline("hello", source="test_blank")
        assert ctx.telemetry_event is not None, "Stage 1 failed"
        assert ctx.intent is not None, "Stage 2 failed"
```

### Task E.3: Add cross-profile classification accuracy test

```python
class TestCrossProfileClassification:
    """Architect §II Test 4: accuracy across ALL profiles."""

    @pytest.mark.parametrize("profile",
        ["reference", "coach_demo", "blank_template"])
    def test_hello_classifies_across_profiles(self, profile):
        from engine.profile import set_profile
        from engine.cognitive_router import classify_intent, reset_router
        set_profile(profile)
        reset_router()
        for text in ["hello", "hi", "thanks", "goodbye"]:
            result = classify_intent(text)
            assert result.intent == "general_chat", \
                f"{profile}: '{text}' -> {result.intent}"
            assert result.confidence >= 0.5
```

### GATE E: Final Ship Gate

```bash
# 1. Full test suite
python -m pytest tests/ -x -q

# 2. The engine grep — ultimate check
python -c "
from pathlib import Path
terms = ['coaching', 'golf', 'swing', 'lesson', 'tournament',
         'handicap', '\"player\"', '\"parent\"', '\"venue\"',
         'nobody tells you about', 'on the course',
         'google_calendar', 'GOOGLE_CALENDAR', 'GMAIL_SCOPES']
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
    print('SHIP GATE PASSED: Zero domain terms in engine/')
"

# 3. Clean repo
python -c "
from pathlib import Path
assert len(list(Path('.').glob('tmpclaude-*'))) == 0
assert not Path('profiles/demo').exists()
assert not Path('profiles/demon').exists()
print('PASS: Clean repo')
"
```

---

## Post-Sprint: Commit & Merge

```bat
@echo off
cd /d C:\GitHub\grove-autonomaton-primative-domain-purity-v1
git add -A
git commit -m "domain-purity-v1"
```

Then merge to master:
```bat
cd /d C:\GitHub\grove-autonomaton-primative
git merge grove-autonomaton-primative-domain-purity-v1
git push origin master
git worktree remove ..\grove-autonomaton-primative-domain-purity-v1
```

---

## Verification Summary

After this sprint, the following must be true:

| Claim | Test |
|-------|------|
| Zero domain terms in engine/ | grep returns nothing |
| Entity taxonomy from config | entity_config.yaml in all 3 profiles |
| Content hooks from config | content_config.yaml in all 3 profiles |
| Normalizer extracts entities | classify_intent.md requests entities + sentiment |
| Ratchet routes in all profiles | routing.config has ratchet_intent_classify |
| Cache stores enriched fields | pattern_cache entries include entities/sentiment |
| Cache hits return enriched fields | _check_pattern_cache returns entities |
| No dead glass code | display_glass_pipeline removed |
| Model IDs updated in fallbacks | llm_client.py defaults match models.yaml |
| blank_template runs clean | test passes |
| Cognitive agnosticism | Zero model names outside _DEFAULT fallbacks and models.yaml |

## What's NOT In Scope

- **MCP handler genericization (P4, P5)** — deferred. The mcp_calendar
  and mcp_gmail handlers are functional and tested. Genericizing
  them is an architectural improvement but not a reviewer-visible
  violation at the same severity as domain terms in analytical code.
  Tracked for next sprint.

- **cost_usd reliability (P8)** — partially addressed by normalizer
  enrichment (enriched fields flow through telemetry). Full fix
  requires the LLM abstraction layer returning cost in its response
  object (not just logging to side channel). Tracked.

## Cognitive Agnosticism Enforcement

The engine dispatches to TIERS, not models. No engine file, no sprint
document, no test, and no prompt template may reference a specific
model name or provider name. The mapping from tier to model ID lives
in one place: `models.yaml`. The fallback defaults in `llm_client.py`
exist solely as crash prevention — and must carry a comment stating
"fallback only, models.yaml is authoritative."

This is not a naming convention. This is Invariant #4 from the TCP/IP
paper: Layered Independence. The governance layer is independent of
the cognitive layer. The cognitive layer is independent of the execution
layer. Swap the model behind Tier 1 — the governance doesn't change.
Swap the provider — the routing doesn't change. The system is blind
to what it dispatches to, and that blindness is the sovereignty guarantee.

If you find yourself typing a model name in engine code, you are
violating the architecture. Stop. Put it in models.yaml.
