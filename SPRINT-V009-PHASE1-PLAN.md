# V-009 Phase 1 Sprint Plan: Telemetry-Based Tests 1-7

**Violation:** V-009 (Test Suite Alignment)
**Phase:** 1 of 2 (Tests 1-7 only; Flywheel tests 8-10 deferred)
**Operator:** Awaiting approval

---

## Summary

Implement the V-009 spec's telemetry-based test architecture for Tests 1-7. The key architectural shift: **assert on telemetry traces, not PipelineContext attributes**.

The existing `test_pipeline_invariant.py` tests PipelineContext state. The spec requires tests that read the `log_event()` output stream and assert on trace properties like `inferred.stage`, `tier`, `intent`, `zone`, `cost_usd`.

---

## Files to Touch

| File | Action | Purpose |
|------|--------|---------|
| `tests/conftest.py` | MODIFY | Add 3 fixtures: `telemetry_sink`, `mock_llm`, `mock_ux_input` |
| `tests/test_pipeline_invariant.py` | REWRITE | Tests 1 (5 stages) and 7 (clean startup) per spec |
| `tests/test_jidoka_consent.py` | CREATE | Tests 2 (Jidoka stop) and 6 (config menu) per spec |
| `tests/test_ratchet.py` | CREATE | Tests 3 (consent LLM), 4 (cache hit), 5 (cache integrity) per spec |

---

## Fixture Design (conftest.py)

### 1. `telemetry_sink` Fixture

Captures `log_event()` calls in memory instead of writing to disk.

```python
@pytest.fixture
def telemetry_sink():
    """Captures telemetry entries in memory for assertion."""
    entries = []

    def capture_log_event(**kwargs):
        # Build the event dict (matching log_event signature)
        from engine.telemetry import create_event
        event = create_event(**kwargs)
        entries.append(event)
        return event

    with patch('engine.pipeline.log_event', side_effect=capture_log_event):
        with patch('engine.telemetry.log_event', side_effect=capture_log_event):
            yield entries
```

### 2. `mock_llm` Fixture

Returns deterministic classification results.

```python
@pytest.fixture
def mock_llm():
    """Returns deterministic LLM classification."""
    responses = []  # Queue of responses

    def _mock_call(prompt, tier=2, intent=""):
        if responses:
            return responses.pop(0)
        return '{"intent": "explain_system", "confidence": 0.85}'

    with patch('engine.llm_client.call_llm', side_effect=_mock_call):
        yield responses
```

### 3. `mock_ux_input` Fixture

Simulates operator choices at Kaizen prompts.

```python
@pytest.fixture
def mock_ux_input():
    """Simulates operator Kaizen menu choices."""
    choices = []  # Queue of choices

    def _mock_jidoka(context_message, options):
        if choices:
            return choices.pop(0)
        return "1"  # Default: first option

    with patch('engine.ux.ask_jidoka', side_effect=_mock_jidoka):
        yield choices
```

---

## Test 1: Pipeline Invariant (test_pipeline_invariant.py)

**Spec requirement:** "hello" input produces exactly 5 telemetry entries in stage order.

```python
def test_pipeline_five_stages_every_time(telemetry_sink):
    """INPUT: 'hello' (keyword match, no LLM)"""
    from engine.pipeline import run_pipeline

    run_pipeline(raw_input="hello", source="test")

    # Exactly 5 traces
    assert len(telemetry_sink) == 5

    # Stages in order
    stages = [e.get("inferred", {}).get("stage") for e in telemetry_sink]
    assert stages == ["telemetry", "recognition", "compilation", "approval", "execution"]

    # Recognition trace assertions
    recognition = next(e for e in telemetry_sink if e.get("inferred", {}).get("stage") == "recognition")
    assert recognition["intent"] == "general_chat"
    assert recognition["tier"] == 1
    assert recognition.get("inferred", {}).get("method") == "keyword"

    # Approval trace assertions
    approval = next(e for e in telemetry_sink if e.get("inferred", {}).get("stage") == "approval")
    assert approval["zone_context"] == "green"

    # Execution trace assertions
    execution = next(e for e in telemetry_sink if e.get("inferred", {}).get("stage") == "execution")
    assert execution.get("inferred", {}).get("handler") == "general_chat"
```

---

## Test 2: Digital Jidoka (test_jidoka_consent.py)

**Spec requirement:** Unknown input stops the line, Kaizen Option 2 answers from local context.

```python
def test_jidoka_stops_for_unknown_input(telemetry_sink, mock_ux_input):
    """INPUT: 'How does this handle regulatory compliance?' (no keyword match)"""
    from engine.pipeline import run_pipeline

    mock_ux_input.append("2")  # Option 2: local context

    run_pipeline(raw_input="How does this handle regulatory compliance?", source="test")

    # Recognition shows unknown
    recognition = next(e for e in telemetry_sink if e.get("inferred", {}).get("stage") == "recognition")
    assert recognition["intent"] == "unknown"

    # Approval shows Kaizen fired
    approval = next(e for e in telemetry_sink if e.get("inferred", {}).get("stage") == "approval")
    assert "kaizen" in approval.get("inferred", {}).get("label", "").lower()

    # Execution cost is zero (local context, no LLM)
    execution = next(e for e in telemetry_sink if e.get("inferred", {}).get("stage") == "execution")
    assert execution.get("cost_usd") is None or execution.get("cost_usd") == 0.0
```

---

## Test 3: Consent-Gated LLM Classification (test_ratchet.py)

**Spec requirement:** Option 1 uses LLM, caches the CLASSIFIED intent (not the mechanism).

```python
def test_consent_gated_llm_classification(telemetry_sink, mock_ux_input, mock_llm):
    """INPUT: 'What about enterprise data residency requirements?'"""
    from engine.pipeline import run_pipeline

    mock_ux_input.append("1")  # Option 1: consent to LLM
    mock_llm.append('{"intent": "explain_system", "confidence": 0.85}')

    context = run_pipeline(
        raw_input="What about enterprise data residency requirements?",
        source="test"
    )

    # Post-classification intent is explain_system, NOT ratchet_intent_classify
    assert context.intent == "explain_system"

    # Exactly one pipeline traversal (count stage=telemetry entries)
    telemetry_starts = [e for e in telemetry_sink if e.get("inferred", {}).get("stage") == "telemetry"]
    assert len(telemetry_starts) == 1, "One operator input = one pipeline traversal"
```

---

## Test 4: The Ratchet Cache Hit (test_ratchet.py)

**Spec requirement:** Repeat input resolves at T0 from cache, zero cost.

```python
def test_ratchet_cache_hit_on_repeat(telemetry_sink, mock_ux_input, mock_llm):
    """SETUP: Run Test 3 first, then same input again."""
    from engine.pipeline import run_pipeline
    from engine.cognitive_router import reset_router

    # First run: LLM classification (Test 3 scenario)
    mock_ux_input.append("1")
    mock_llm.append('{"intent": "explain_system", "confidence": 0.85}')
    run_pipeline(raw_input="What about enterprise data residency requirements?", source="test")

    # Clear sink for second run
    telemetry_sink.clear()
    reset_router()  # Force cache reload

    # Second run: same input
    context = run_pipeline(
        raw_input="What about enterprise data residency requirements?",
        source="test"
    )

    # Should hit cache (T0)
    recognition = next(e for e in telemetry_sink if e.get("inferred", {}).get("stage") == "recognition")
    assert recognition["tier"] == 0
    assert recognition.get("inferred", {}).get("method") == "cache"

    # No Kaizen prompt (no approval trace with kaizen label)
    approval = next(e for e in telemetry_sink if e.get("inferred", {}).get("stage") == "approval")
    assert "kaizen" not in approval.get("inferred", {}).get("label", "").lower()

    # Zero cost
    execution = next(e for e in telemetry_sink if e.get("inferred", {}).get("stage") == "execution")
    cost = execution.get("cost_usd")
    assert cost is None or cost == 0.0
```

---

## Test 5: Cache Integrity (test_ratchet.py)

**Spec requirement:** Cache stores `intent: explain_system`, not `intent: ratchet_intent_classify`.

```python
def test_cache_stores_classified_intent_not_mechanism(mock_ux_input, mock_llm):
    """Read pattern_cache.yaml directly after Test 3."""
    import yaml
    from engine.pipeline import run_pipeline
    from engine.profile import get_config_dir

    # Run classification
    mock_ux_input.append("1")
    mock_llm.append('{"intent": "explain_system", "confidence": 0.85}')
    run_pipeline(raw_input="What about enterprise data residency requirements?", source="test")

    # Read cache file
    cache_path = get_config_dir() / "pattern_cache.yaml"
    with open(cache_path, "r") as f:
        data = yaml.safe_load(f)

    # Find the entry (by scanning for matching original_input)
    cache = data.get("cache", {})
    entry = None
    for k, v in cache.items():
        if "enterprise data residency" in v.get("original_input", "").lower():
            entry = v
            break

    assert entry is not None, "Cache entry should exist"
    assert entry["intent"] == "explain_system", f"Cache stores classified intent, got {entry['intent']}"
    assert entry["intent"] != "ratchet_intent_classify", "V-001 regression: cache poisoning"
```

---

## Test 6: Config-Driven Routing (test_jidoka_consent.py)

**Spec requirement:** Option 3 sub-menu options come from `clarification.yaml`.

```python
def test_config_driven_submenu(telemetry_sink, mock_ux_input):
    """INPUT: 'xyzzy plugh nothing' (guaranteed no match)"""
    from engine.pipeline import run_pipeline

    mock_ux_input.append("3")  # Option 3: show what you can help with
    mock_ux_input.append("1")  # First option from sub-menu

    context = run_pipeline(raw_input="xyzzy plugh nothing", source="test")

    # Recognition shows unknown
    recognition = next(e for e in telemetry_sink if e.get("inferred", {}).get("stage") == "recognition")
    assert recognition["intent"] == "unknown"

    # After sub-menu, context.intent is resolved from clarification.yaml mapping
    assert context.intent != "unknown", "Sub-menu should resolve to a known intent"
    assert context.approved is True
```

---

## Test 7: Clean Startup (test_pipeline_invariant.py)

**Spec requirement:** Zero telemetry/LLM before first operator input.

```python
def test_clean_startup_no_llm_before_input(telemetry_sink):
    """Initialize engine, verify zero LLM calls before operator input."""
    from engine.profile import set_profile
    from engine.cognitive_router import reset_router
    from engine.dock import get_dock

    # Track LLM calls
    llm_calls = []

    with patch('engine.llm_client.call_llm', side_effect=lambda *a, **k: llm_calls.append(1)):
        # Initialize
        set_profile("coach_demo")
        reset_router()
        dock = get_dock()
        dock.ingest()

    # Zero telemetry entries
    assert len(telemetry_sink) == 0, "No telemetry before operator input"

    # Zero LLM calls
    assert len(llm_calls) == 0, "No LLM calls during initialization"
```

---

## Execution Sequence

1. Modify `tests/conftest.py` with the 3 new fixtures
2. Rewrite `tests/test_pipeline_invariant.py` with Tests 1 and 7
3. Create `tests/test_jidoka_consent.py` with Tests 2 and 6
4. Create `tests/test_ratchet.py` with Tests 3, 4, and 5
5. Run `pytest tests/test_pipeline_invariant.py tests/test_jidoka_consent.py tests/test_ratchet.py -v`
6. Document which tests fail (expected: Tests 3, 4, 5 may fail until V-001 fully verified)

---

## What This Does NOT Touch

- `tests/test_flywheel.py` (Phase 2, Tests 8-10)
- Existing test files other than `test_pipeline_invariant.py`
- Any engine code (this sprint is test-only)

---

## Approval Request

**Files to modify:**
1. `tests/conftest.py` — add fixtures
2. `tests/test_pipeline_invariant.py` — rewrite per spec
3. `tests/test_jidoka_consent.py` — create new
4. `tests/test_ratchet.py` — create new

**Waiting for operator approval before proceeding.**
