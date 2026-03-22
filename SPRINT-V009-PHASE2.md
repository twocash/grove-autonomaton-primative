# V-009 Phase 2: Deprecate Coach-Specific Tests

## Context
V-009 Phase 1 is complete (commit bcd4132). All 14 architecture tests pass against the reference profile. But `pytest tests/` shows 16 failures — all coach_demo domain assumptions hitting the reference profile (which conftest now sets as default).

The coach_demo profile is deferred. These tests validate domain-specific routing (content_compilation, session_zero, vision_capture) that doesn't exist in the reference profile. They are not architecture tests. They are domain tests for a profile we're not shipping yet.

## The One Rule
Architecture tests enforce the pattern. Domain tests enforce a profile. This sprint removes domain tests that block `pytest tests/` from running green.

## Exact Changes

### 1. DELETE `tests/test_content_engine.py`
The entire file tests the content engine — a coach_demo domain feature. Every test references coach_demo routes, voice config, pillar context, and content seeds. None of this exists in the reference profile. None of it tests architectural invariants.

Delete the file. Zero ambiguity.

### 2. STRIP coach-specific tests from `tests/test_cognitive_router.py`
These specific tests fail because they reference routes that only exist in coach_demo:

**Delete these test classes/methods:**
- `TestRouterConfigLoading::test_router_loads_config` — asserts `content_compilation` route exists
- `TestRouterClassification::test_router_classifies_compile_content` — expects `content_compilation` intent
- `TestRouterClassification::test_router_classifies_build_skill` — expects `extract_args` behavior specific to coach_demo's `build skill` keyword pattern
- `TestSessionZeroIntake` (entire class, 4 tests) — expects `session_zero` route
- `TestConversationalRouting::test_actionable_intent_type` — expects `content_compilation` as an actionable intent example

**Keep everything else.** The remaining tests in this file (unknown intents, handler mapping, router reset, LLM escalation, conversational routing basics, clarification Jidoka, LLM structured classification) all work against the reference profile and test genuine architectural behavior.

### 3. FIX `tests/test_ux_formatting.py`
One test fails: `TestChiefOfStaffPersona::test_translation_prompt_includes_chief_of_staff`

This test asserts the persona name contains "Chief of Staff" — that's the coach_demo persona. The reference profile persona is "Engine" with role "Architecture Guide."

**Fix:** Change the assertion to check for the reference profile's persona name OR delete the test if it's testing coach-specific persona behavior rather than the translation mechanism itself. The translation mechanism (translate_action_for_approval) works regardless of persona — the test should validate that the persona is INCLUDED in the prompt, not that it's a SPECIFIC persona. If you fix it, assert that the persona name from config appears in the prompt (config-driven, not hardcoded).

### 4. VERIFY: `tests/test_cortex.py` 
V-001 noted that `test_cortex.py` imports deleted `engine.ratchet`. Check if this file exists and if it crashes on import. If it does, delete it — the cortex evolution tests in `test_cortex_evolution.py` already cover Cortex behavior and they all pass.

## What NOT to Touch
- `tests/conftest.py` — already correct (reference profile, clean fixtures)
- `tests/test_pipeline_invariant.py` — V-009 Phase 1, all passing
- `tests/test_jidoka_consent.py` — V-009 Phase 1, all passing
- `tests/test_ratchet.py` — V-009 Phase 1, all passing
- `tests/test_pipeline_compliance.py` — all passing
- `tests/test_mcp_governance.py` — all passing
- `tests/test_telemetry_schema.py` — all passing
- `tests/test_purity_invariants.py` — all passing
- `tests/test_purity_v2.py` — all passing
- `tests/test_dispatcher.py` — all passing
- `tests/test_reference_profile.py` — all passing
- `tests/test_profile_isolation.py` — all passing
- `tests/test_pit_crew.py` — all passing
- `tests/test_llm_client.py` — all passing
- `tests/test_consent_classification.py` — all passing
- `tests/test_cortex_evolution.py` — all passing
- `tests/test_privacy_mask.py` — all passing
- Engine code — do not modify any engine files

## Acceptance Test
```
cd /d C:\GitHub\grove-autonomaton-primative
python -m pytest tests/ -v
```

**Expected: 0 failures. All remaining tests pass.** The exact count will be ~222 minus the deleted tests. Every remaining test validates architectural behavior, not domain-specific routing.

## Commit
Single commit. Message: `V-009-phase2-deprecate-coach-tests`

Branch: `v009-telemetry-tests` (same branch as Phase 1)

## Architectural Justification
Profile Isolation (Invariant #6, white paper Part IX Principle 6 "Composable"): "The engine is 100% domain-agnostic. All domain behavior comes from the profile's config directory." Tests that hardcode domain routes violate this principle — they couple the test suite to a specific profile's config. Architecture tests must work against ANY valid profile. The reference profile is the proof: naked engine, no domain, every invariant enforced.
