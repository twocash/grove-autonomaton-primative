"""
Reference Profile UX Test Script
Run: python tests/test_reference_ux.py

Tests the demo flow a CTO would experience.
Each step checks: routing, tier, Andon Gate (should NOT fire), dock context, Ratchet.
"""

import json
import sys
import os

# Add repo root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.profile import set_profile, get_telemetry_path
from engine.cognitive_router import classify_intent, reset_router, get_router
from engine.pipeline import run_pipeline


def setup():
    set_profile("reference")
    reset_router()
    # Clear telemetry for clean test
    tpath = get_telemetry_path()
    if tpath.exists():
        tpath.write_text("")


def get_pipeline_events(ctx):
    """Read telemetry events for this pipeline traversal."""
    tpath = get_telemetry_path()
    if not tpath.exists():
        return []
    events = []
    with open(tpath) as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    pid = ctx.telemetry_event["id"]
    return [e for e in events
            if e.get("id") == pid
            or e.get("inferred", {}).get("pipeline_id") == pid]


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    mark = "✓" if condition else "✗"
    print(f"  {mark} {label}" + (f" — {detail}" if detail else ""))
    return condition


def run_step(step_num, input_text, expect_intent, expect_no_jidoka=True,
              expect_dock=False, expect_tier=None, expect_cache_hit=False):
    """Test one interaction step."""
    print(f"\n{'='*60}")
    print(f"Step {step_num}: \"{input_text}\"")
    print(f"{'='*60}")

    # First check: does classify_intent route correctly without Jidoka?
    result = classify_intent(input_text)
    routed_intent = result.intent
    tier = result.tier
    confidence = result.confidence
    is_cache = result.llm_metadata.get("source") == "pattern_cache"

    check("Intent", routed_intent == expect_intent,
          f"got {routed_intent}, expected {expect_intent}")

    if expect_no_jidoka:
        check("No Jidoka needed", routed_intent != "unknown",
              f"confidence={confidence:.0%}, tier={tier}")

    if expect_tier is not None:
        check("Tier", tier == expect_tier,
              f"got T{tier}, expected T{expect_tier}")

    if expect_cache_hit:
        check("Ratchet cache hit", is_cache,
              f"T{tier}, source={'cache' if is_cache else 'not cache'}")

    return result



def run_all():
    setup()
    passes = 0
    fails = 0

    print("\n" + "="*60)
    print("  REFERENCE PROFILE UX TEST")
    print("  Testing the demo flow a reviewer would experience")
    print("="*60)

    # ── PHASE 1: Basic greeting ──────────────────────────────
    r = run_step(1, "hello",
                  expect_intent="general_chat",
                  expect_tier=1)

    # ── PHASE 2: Architecture questions (should NOT trigger Jidoka) ──
    phrases_that_must_route = [
        ("what is this",                "explain_system"),
        ("how does this work",          "explain_system"),
        ("what makes this special",     "explain_system"),
        ("what makes this different",   "explain_system"),
        ("how is this different from a chatbot", "explain_system"),
        ("isn't this just another agent", "explain_system"),
        ("so what",                     "explain_system"),
        ("why should I care",           "explain_system"),
        ("what's the ratchet",          "explain_system"),
        ("what's the pipeline",         "explain_system"),
        ("what are the zones",          "explain_system"),
        ("tell me more",               "explain_system"),
        ("eli5",                        "explain_system"),
        ("how does it differ from agents", "explain_system"),
        ("what's actually new",         "explain_system"),
        ("convince me",                 "explain_system"),
        ("what problem does this solve", "explain_system"),
        ("break it down",              "explain_system"),
        ("vs a chatbot",               "explain_system"),
        ("what is jidoka",             "explain_system"),
        # Competitive / skeptical
        ("does this compete with openai", "explain_system"),
        ("why not just use an api",     "explain_system"),
        ("sounds like hype",            "explain_system"),
        ("we already use copilot",      "explain_system"),
        ("vs langchain",               "explain_system"),
        # Conversational follow-ups
        ("ok but what about security",  "explain_system"),
        ("yeah but how is this different", "explain_system"),
        ("give me an example",          "explain_system"),
        ("who is this for",             "explain_system"),
        ("use cases",                   "explain_system"),
    ]

    print(f"\n{'='*60}")
    print(f"Phase 2: Architecture questions — keyword routing")
    print(f"Every phrase must route to explain_system without Jidoka")
    print(f"{'='*60}")

    phase2_pass = 0
    phase2_fail = 0
    for phrase, expected in phrases_that_must_route:
        result = classify_intent(phrase)
        ok = result.intent == expected
        mark = "✓" if ok else "✗"
        tier_str = f"T{result.tier}"
        conf_str = f"{result.confidence:.0%}"
        if ok:
            phase2_pass += 1
            print(f"  {mark} \"{phrase}\" → {result.intent} ({tier_str}, {conf_str})")
        else:
            phase2_fail += 1
            print(f"  {mark} \"{phrase}\" → {result.intent} (EXPECTED {expected}, {tier_str}, {conf_str})")

    print(f"\n  Phase 2 result: {phase2_pass}/{phase2_pass + phase2_fail} passed")


    # ── PHASE 3: Deep analysis routing ───────────────────────
    deep_phrases = [
        ("brainstorm distributed vs centralized", "deep_analysis"),
        ("go deeper",                             "deep_analysis"),
        ("deep dive",                             "deep_analysis"),
        ("the recursive case",                    "deep_analysis"),
    ]

    print(f"\n{'='*60}")
    print(f"Phase 3: Deep analysis — must route to T3 Yellow")
    print(f"{'='*60}")

    phase3_pass = 0
    phase3_fail = 0
    for phrase, expected in deep_phrases:
        result = classify_intent(phrase)
        ok = result.intent == expected
        zone_ok = result.zone == "yellow" if ok else True
        tier_ok = result.tier == 3 if ok else True
        mark = "✓" if (ok and zone_ok and tier_ok) else "✗"
        if ok and zone_ok and tier_ok:
            phase3_pass += 1
        else:
            phase3_fail += 1
        detail = f"T{result.tier} {result.zone}"
        if not ok:
            detail = f"EXPECTED {expected}, got {result.intent}"
        elif not zone_ok:
            detail = f"EXPECTED yellow, got {result.zone}"
        elif not tier_ok:
            detail = f"EXPECTED T3, got T{result.tier}"
        print(f"  {mark} \"{phrase}\" → {result.intent} ({detail})")

    print(f"\n  Phase 3 result: {phase3_pass}/{phase3_pass + phase3_fail} passed")


    # ── PHASE 4: Greetings still route correctly ─────────────
    greetings = [
        "hi", "hey", "good morning", "thanks", "goodbye",
        "my name is bob", "nice to meet you",
    ]

    print(f"\n{'='*60}")
    print(f"Phase 4: Greetings — must stay general_chat (conversational)")
    print(f"{'='*60}")

    phase4_pass = 0
    for phrase in greetings:
        result = classify_intent(phrase)
        ok = result.intent == "general_chat"
        mark = "✓" if ok else "✗"
        if ok:
            phase4_pass += 1
        print(f"  {mark} \"{phrase}\" → {result.intent}")

    print(f"\n  Phase 4 result: {phase4_pass}/{len(greetings)} passed")

    # ── PHASE 5: Operator guide still fires on explicit command ─
    print(f"\n{'='*60}")
    print(f"Phase 5: Explicit commands still work")
    print(f"{'='*60}")

    explicit = [
        ("help",           "operator_guide"),
        ("show config",    "show_config"),
        ("show telemetry", "show_telemetry"),
        ("show cache",     "show_cache"),
        ("dock",           "dock_status"),
        ("build skill test-skill does something", "pit_crew_build"),
    ]

    phase5_pass = 0
    for phrase, expected in explicit:
        result = classify_intent(phrase)
        ok = result.intent == expected
        mark = "✓" if ok else "✗"
        if ok:
            phase5_pass += 1
        else:
            print(f"  {mark} \"{phrase}\" → {result.intent} (EXPECTED {expected})")
            continue
        print(f"  {mark} \"{phrase}\" → {result.intent}")

    print(f"\n  Phase 5 result: {phase5_pass}/{len(explicit)} passed")


    # ── PHASE 6: Ratchet test ────────────────────────────────
    print(f"\n{'='*60}")
    print(f"Phase 6: Ratchet — cache invalidation after pipeline write")
    print(f"{'='*60}")

    import hashlib
    import yaml
    from engine.profile import get_config_dir

    # Also verify: smart_clarification is disabled for reference profile
    rc_path = get_config_dir() / "routing.config"
    with open(rc_path) as f:
        rc = yaml.safe_load(f) or {}
    smart = rc.get("settings", {}).get("smart_clarification", True)
    check("Smart clarification disabled",
          smart == False,
          f"smart_clarification={smart} — must be false for demo")

    # Simulate: write a known entry to cache, then check if router sees it
    cache_path = get_config_dir() / "pattern_cache.yaml"
    test_input = "ratchet_ux_test_unique_phrase"
    input_hash = hashlib.sha256(
        test_input.lower().strip().encode()
    ).hexdigest()[:16]

    # Save current cache
    old_cache = ""
    if cache_path.exists():
        old_cache = cache_path.read_text(encoding="utf-8")

    # Write test entry
    data = {"cache": {input_hash: {
        "intent": "general_chat",
        "domain": "system",
        "zone": "green",
        "handler": "general_chat",
        "handler_args": {},
        "intent_type": "conversational",
        "confirmed_count": 1,
    }}}
    with open(cache_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)

    # Reload cache (this is what the fix does after yaml.dump)
    router = get_router()
    router.load_cache()

    # Check if router sees the entry
    cache_result = router._check_pattern_cache(test_input)
    ratchet_ok = cache_result is not None and cache_result.tier == 0
    check("Cache write → router sees it",
          ratchet_ok,
          f"T{cache_result.tier if cache_result else '?'}, "
          f"{'cache hit' if cache_result else 'MISS'}")

    # Restore original cache
    if old_cache:
        cache_path.write_text(old_cache, encoding="utf-8")
    else:
        cache_path.write_text("cache: {}\n", encoding="utf-8")
    router.load_cache()


    # ── PHASE 7: Dock content loaded ─────────────────────────
    print(f"\n{'='*60}")
    print(f"Phase 7: Dock — white paper and unlock section loaded")
    print(f"{'='*60}")

    from engine.dock import get_dock
    dock = get_dock()
    sources = dock.list_sources()
    chunk_count = dock.get_chunk_count()
    check("Dock has sources", len(sources) >= 1,
          f"{len(sources)} source(s), {chunk_count} chunks")

    # Query for architecture content
    result = dock.query("five stage pipeline", top_k=2)
    check("Dock returns pipeline content",
          len(result) > 0 and ("pipeline" in result.lower() or "stage" in result.lower()),
          f"{len(result)} chars returned")

    result2 = dock.query("star node topology distributed", top_k=2)
    check("Dock returns unlock content",
          len(result2) > 0 and ("topology" in result2.lower() or "distributed" in result2.lower() or "spiral" in result2.lower()),
          f"{len(result2)} chars returned")

    # ── SUMMARY ──────────────────────────────────────────────
    total_pass = phase2_pass + phase3_pass + phase4_pass + phase5_pass
    total_tests = (phase2_pass + phase2_fail + phase3_pass + phase3_fail
                   + len(greetings) + len(explicit))

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Phase 2 (architecture questions): {phase2_pass}/{phase2_pass + phase2_fail}")
    print(f"  Phase 3 (deep analysis):          {phase3_pass}/{phase3_pass + phase3_fail}")
    print(f"  Phase 4 (greetings):              {phase4_pass}/{len(greetings)}")
    print(f"  Phase 5 (explicit commands):       {phase5_pass}/{len(explicit)}")
    print(f"  Phase 6 (ratchet):                {'PASS' if ratchet_ok else 'FAIL'}")
    print(f"  Phase 7 (dock content):           {len(sources)} sources, {chunk_count} chunks")
    print(f"{'='*60}")

    all_pass = (phase2_fail == 0 and phase3_fail == 0
                and phase4_pass == len(greetings)
                and phase5_pass == len(explicit)
                and ratchet_ok)

    if all_pass:
        print(f"  ✓ ALL PHASES PASSED — ready for reviewer demo")
    else:
        print(f"  ✗ FAILURES DETECTED — fix before demo")

    print(f"{'='*60}\n")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(run_all())
