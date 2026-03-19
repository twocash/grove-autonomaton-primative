# SPRINT SPEC: Domain Purity + Normalizer Enrichment

> *"Design is philosophy expressed through constraint."*
> Sprint Name: `domain-purity-v1`
> Generated: 2026-03-19
> Provenance: Compliance audit against TCP/IP Paper, Pattern Doc 1.3, Architect Skill
> Dependency: Executes AFTER pipeline-compliance-v1 (commit 46e42b1)
> Domain Contract: Autonomaton Architect (Anti-Code-Party Protocol)

---

## Purpose

The pipeline compliance sprint fixed the pipeline invariant — 5 stages
emit traces, clarification is config-driven, Jidoka resolution is
logged. That work is solid.

This sprint fixes everything AROUND the pipeline: 6 of 16 engine
files contain coaching-domain terms hardcoded in Python. A reviewer
who runs `grep -r "player" engine/` falsifies the "config over code"
claim in under 30 seconds.

Simultaneously, this sprint enriches the Cognitive Router's normalizer
— the ONE Tier 1 call during Recognition that extracts intent,
entities, sentiment, and intent_type from raw input. This is the
"come to life" call. Every field it extracts lands in telemetry. Every
confirmed classification ratchets down to Tier 0 pattern cache. The
system learns the operator's vocabulary from a single function call,
then serves it back for free. This is the onboarding flywheel.

---

## The Two Thrusts

### Thrust 1: Domain Purity

Extract all domain-specific terms from engine/ into profile config.
The engine becomes fully domain-agnostic. A grep of engine/ for any
domain term returns zero results.

### Thrust 2: Normalizer Enrichment

The ratchet_interpreter handler and classify_intent prompt template
exist in coach_demo but not in other profiles. The prompt extracts
only intent + confidence + reasoning. This is the minimum.

The enriched normalizer extracts:
- **intent** — classified intent name
- **intent_type** — conversational / informational / actionable
- **confidence** — 0.0-1.0
- **entities** — extracted names, dates, amounts, references
- **sentiment** — neutral / positive / negative / urgent
- **reasoning** — brief explanation

ONE Tier 1 call. The Cognitive Router dispatches to whatever model
sits behind that tier — determined by models.yaml. The engine doesn't
know and doesn't care what model processes the request. All fields
land in the Stage 2 telemetry trace. The Ratchet captures the full
classification in pattern_cache.yaml. Next time the operator says the
same thing, Tier 0 returns ALL the enriched fields — instant, free.

---

## Violations Being Fixed

| ID | Severity | What | Where |
|----|----------|------|-------|
| P1 | CRITICAL | Coaching terms in cortex.py entity extraction | engine/cortex.py |
| P2 | CRITICAL | Golf hooks in content_engine.py | engine/content_engine.py |
| P3 | CRITICAL | Entity alias routing in compiler.py | engine/compiler.py |
| P4 | HIGH | MCP handler names hardcoded in dispatcher.py | engine/dispatcher.py |
| P5 | HIGH | Google service names in effectors.py | engine/effectors.py |
| P6 | HIGH | PipelineContext glass renderer (dead code) | engine/glass.py |
| P7 | HIGH | Domain term test only checks 1 of 16 files | tests/ |
| P8 | MEDIUM | LLM cost_usd not reliably in main stream | engine/pipeline.py |
| P9 | MEDIUM | Stale fallback model IDs | engine/llm_client.py |
| P10 | MEDIUM | tmpclaude-* files + orphan profiles | repo root |
| N1 | FEATURE | classify_intent prompt lacks entity/sentiment | profiles/*/config/ |
| N2 | FEATURE | Ratchet routes missing from reference + blank | profiles/ |

---

## Atomic Constraints

1. **Worktree.** Create git worktree before any edits.
2. **Gate per epic.** No epic starts until the previous gate passes.
3. **Tests on every edit.** `pytest tests/ -x -q` after every task.
4. **Zero domain terms.** The engine grep test is the ship gate.
5. **Profile isolation.** blank_template runs "hello" without errors.
6. **Normalizer is additive.** The enriched prompt returns a superset
   of the current schema. Existing ratchet behavior is preserved.
7. **Cognitive agnosticism.** Zero model names in engine code. Zero
   provider names. The system dispatches to tiers. models.yaml
   maps tiers to model IDs. The engine is blind to what sits behind
   a tier. This is not a preference — it is a sovereignty guarantee.

---

## The Normalizer Flywheel (Why This Matters)

Day 1: Operator says "schedule a lesson with Henderson on Thursday"
  → Keyword match fails (no exact keyword)
  → T1 Cognitive Router fires (ONE call, fractions of a cent)
  → Extracts: intent=calendar_schedule, entities={people:["Henderson"],
    dates:["Thursday"]}, intent_type=actionable, sentiment=neutral
  → ALL fields logged to Stage 2 telemetry trace
  → Operator approves, executes → Ratchet writes to pattern_cache

Day 2: Operator says "schedule a lesson with Henderson on Thursday"
  → Pattern cache HIT → Tier 0, $0.00, instant
  → Returns FULL enriched classification including entities
  → Glass shows: "T0 cache HIT ✓ $0.00"
  → The system remembers Henderson. The system knows Thursday. Free.

Day 30: The pattern cache contains the operator's entire vocabulary.
  Tier 2/3 calls approach zero. The system "came to life" through
  the normalizer — one Tier 1 call at a time, ratcheting down to free.

This is the Reverse Tax in architecture. The more you use it, the
cheaper it gets. The normalizer is the mechanism. The Cognitive Router
dispatches the minimum viable intelligence. models.yaml decides what
model sits behind each tier. The engine never knows. Cognitive
agnosticism is not a design preference — it is a sovereignty guarantee.
