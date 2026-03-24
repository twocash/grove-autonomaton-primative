# The Grove Autonomaton — Reference Implementation

> *Software that identifies its own issues, proposes its own fixes, and authors its own evolution — inside zones you control.*

This is the reference implementation of the [Grove Autonomaton Pattern](https://the-grove.ai): an open architectural specification for self-authoring software systems. It demonstrates that a five-stage invariant pipeline, declarative governance, and a six-stage Skill Flywheel can produce software that improves itself — transparently, auditably, and under human sovereignty.

The codebase is a Python CLI. Three files define the system's behavior. One loop processes every interaction. The architecture does the rest.

---

## What This Proves

The Autonomaton Pattern makes specific, testable architectural claims. This implementation proves them with running code and an automated test suite. Every claim below maps to tests that assert against the system's own telemetry exhaust — if it's not in the audit trail, it didn't happen.

### The Invariant Pipeline

Every operator interaction traverses five stages in sequence: **Telemetry → Recognition → Compilation → Approval → Execution**. No exceptions. No shortcuts. No nested pipelines. The pipeline is the architectural hourglass — the thin waist through which all cognitive work passes, regardless of what sits above or below it.

**Proof:** `test_pipeline_invariant.py` and `test_pipeline_compliance.py` assert that every pipeline run emits exactly five stage traces sharing a single `pipeline_id`. These tests would catch any bypass, shortcut, or sub-pipeline.

### Declarative Governance

All behavior lives in configuration, not code. `routing.config` maps intents to handlers, tiers, and zones. `zones.schema` defines governance boundaries. The engine is a generic lookup machine — swap the config, change the behavior, no deploy required.

**Proof:** The `blank_template` profile demonstrates the engine runs with zero domain configuration. `test_profile_isolation.py` proves the engine needs nothing domain-specific.

### Zone Sovereignty (Green / Yellow / Red)

Every action has an explicit risk classification. Green auto-approves. Yellow requires operator confirmation. Red requires explicit approval with full context. Stage 4 is the sole governance gate — no other layer prompts the operator.

**Proof:** `test_andon_consent.py` and `test_consent_classification.py` verify that Yellow and Red zone actions fire the Andon Gate, that Green zone actions pass through, and that no handler bypasses Stage 4.

### The Ratchet (Reverse Tax)

When an LLM classifies an intent and the operator confirms it, the classification caches at Tier 0 — free, instant, private, no external dependency. The more you use the system, the cheaper it gets. This is the structural opposite of API subscription economics.

**Proof:** `test_ratchet.py` runs an LLM classification, verifies the cache write, then re-runs the same input and asserts Tier 0 resolution from the telemetry exhaust. The second call costs nothing.

### The Skill Flywheel (Self-Improvement)

The system observes every interaction (OBSERVE), detects recurring patterns in the telemetry (DETECT), proposes new skills as structured YAML specifications (PROPOSE), and deploys them to the pattern cache when the operator approves (APPROVE). Five of six Flywheel stages are operational. The system authors its own evolution — inside zones the operator controls.

**Proof:** `test_flywheel.py` Part F includes `test_full_flywheel_loop_exhaust_only` — an end-to-end integration test that drives OBSERVE → DETECT → PROPOSE → APPROVE → EXECUTE in sequence, asserting every stage from the telemetry exhaust alone. An auditor can reconstruct the entire self-improvement loop from the JSONL without reading a line of code.

### Feed-First Telemetry

Every stage emits a structured trace. The telemetry stream is the single source of truth for learning, observability, and compliance. The Skill Flywheel reads it to detect patterns. The Ratchet reads it to cache classifications. The audit trail is not something you add — it is something the system produces as a byproduct of operating.

**Proof:** `test_telemetry_schema.py` enforces schema validation at write time. Every architecture test asserts against telemetry entries, not internal state. The test suite treats the exhaust as the system's API.

### Transparency by Construction

The governance isn't bolted on. It's emergent from how the system works. Every routing decision traces to a config file. Every zone classification is a schema entry. Every approval is a logged trace with the `proposed_action` the operator reviewed. Every skill is a readable YAML file. The system's intelligence is a library with a card catalog, not a black box with a confidence score.

---

## Running the Demo

### Requirements

- Python 3.12+
- An Anthropic API key (for LLM classification — most interactions are Tier 0/1 and cost nothing)

### Setup

```bash
git clone https://github.com/twocash/atlas.git
cd atlas
pip install -r requirements.txt
cp .env.example .env  # Add your ANTHROPIC_API_KEY
```

### Boot

```bash
python autonomaton.py --profile reference
```

The reference profile is the naked engine — no domain, no context, no startup ceremony. Every pipeline stage announces itself as it runs.

### The Demo Walkthrough

**1. See the pipeline.** Type `hello`. Watch the Glass Pipeline render all five stages: Telemetry, Recognition (keyword match, Tier 1), Compilation, Approval (Green auto-approve), Execution.

**2. See the Andon Gate.** Type something the system doesn't recognize — `How does this handle regulatory compliance?` The system stops. Four options appear. This is the consent architecture: the operator decides whether to spend money on LLM classification, answer from local context, see config-driven options, or rephrase.

**3. See the Ratchet.** Choose Option 1 (LLM classify). The system classifies the intent, responds, and caches the result. Type the exact same question again. This time: Tier 0, $0.00, instant. THE RATCHET announcement fires. The system got cheaper because you used it.

**4. See the Flywheel.** After several interactions, type `show patterns` to see detected recurring patterns. Type `propose skills` to generate skill proposals from those patterns. Type `show proposals` to review them. Type `approve skill {hash}` to deploy one to the pattern cache. Ask the same question — Tier 0 forever. The system authored its own evolution.

**5. Inspect everything.** `show config` displays routing rules. `show zones` displays governance boundaries. `show cache` displays what the Ratchet learned. `show telemetry` displays the audit trail. Every decision is reconstructible.

---

## The Three Files

The Autonomaton Pattern requires three files. Everything else is enhancement.

**`routing.config`** — The Cognitive Router's brain. Maps intents to tiers, zones, and handlers via keyword matching. A reviewer reads this file and knows what the system can do, how it classifies input, and what governance applies to each action.

**`zones.schema`** — The sovereignty guardrail. Defines Green (autonomous), Yellow (requires confirmation), and Red (human-only) zones. An auditor reads this file and knows the system's governance boundaries without touching the codebase.

**`telemetry.jsonl`** — The feed-first audit trail. Every interaction writes a structured entry. The Skill Flywheel reads it to detect patterns. The Ratchet reads it to cache classifications. Compliance emerges from operation.

---

## Architecture

```
Operator Input
     │
     ▼
┌─────────────────────────────────────────┐
│  Stage 1: TELEMETRY                     │  Log before processing
├─────────────────────────────────────────┤
│  Stage 2: RECOGNITION                   │  Cache → Keyword → Unknown
│           Cognitive Router               │  Tier 0/1 (free) or Tier 2 (LLM)
├─────────────────────────────────────────┤
│  Stage 3: COMPILATION                   │  Dock context, enrichment
├─────────────────────────────────────────┤
│  Stage 4: APPROVAL                      │  Green: pass │ Yellow: confirm │ Red: review
│           Andon Gate / Kaizen            │  Sole governance checkpoint
├─────────────────────────────────────────┤
│  Stage 5: EXECUTION                     │  Dispatcher → Handler → Result
└─────────────────────────────────────────┘
     │
     ▼
  Telemetry Exhaust (structured JSONL)
     │
     ├── Ratchet (cache confirmed classifications → Tier 0)
     ├── Flywheel (detect patterns → propose skills → approve → deploy)
     └── Audit Trail (every decision reconstructible)
```

### Cognitive Router Tiers

| Tier | Name | Cost | How |
|------|------|------|-----|
| **0** | Pattern Cache | Free | Previously confirmed — cached by Ratchet or Flywheel |
| **1** | Keyword Match | Free | Config-driven lookup — no model call |
| **2** | Supervised | ~$0.001 | LLM classification — only with operator consent |
| **3** | Apex | ~$0.01+ | Frontier model — reserved for complex reasoning |

The architecture's natural dynamic is downward migration. Every Tier 2 classification that succeeds becomes a Tier 0 cache entry. The system gets cheaper, more private, more sovereign, and more traceable — simultaneously.

### Skill Flywheel

| Stage | Status | What It Does |
|-------|--------|--------------|
| **1. OBSERVE** | ✅ | Feed-first telemetry logs every interaction |
| **2. DETECT** | ✅ | Groups by `pattern_hash`, surfaces candidates at threshold |
| **3. PROPOSE** | ✅ | Generates structured YAML proposals — deterministic, Tier 0 |
| **4. APPROVE** | ✅ | Operator reviews, confirms (Yellow zone), deploys to cache |
| **5. EXECUTE** | ✅ | Approved skills resolve at Tier 0 via pattern cache |
| **6. REFINE** | Future | Usage data improves skills, stale skills deprecate |

---

## Test Suite

The test suite is the architectural proof. Every test asserts against the telemetry exhaust — the system's own audit trail. If a property isn't observable in the exhaust, it isn't auditable, and the governance claim fails.

```bash
pytest                          # Run all tests
pytest tests/test_flywheel.py   # Flywheel suite (DETECT + PROPOSE + APPROVE)
pytest tests/test_ratchet.py    # Ratchet cache proof
pytest -k "test_full_flywheel"  # The integration test
```

| Suite | What It Proves |
|-------|----------------|
| `test_pipeline_invariant.py` | One input = one traversal, five stages, correlated traces |
| `test_pipeline_compliance.py` | Per-stage traces, routing data, feed-first telemetry |
| `test_andon_consent.py` | Unknown input fires Andon Gate, operator chooses |
| `test_ratchet.py` | LLM → cache → Tier 0 on repeat, correct intent stored |
| `test_flywheel.py` | DETECT → PROPOSE → APPROVE → EXECUTE, exhaust-verified |
| `test_kaizen_ux.py` | Tier costs from config, unified Kaizen options |
| `test_profile_isolation.py` | `blank_template` proves engine needs no domain config |
| `test_telemetry_schema.py` | Malformed events rejected, required fields validated |

---

## Intellectual Lineage

The Autonomaton Pattern synthesizes five traditions:

- **Clark & Chalmers (1998)** — The Extended Mind. Cognition extends into the environment. The Autonomaton is not a tool the operator uses; it is part of how the operator thinks.
- **Toyota Production System** — Jidoka (stop when quality degrades) + Kaizen (propose the fix). The Andon Gate is Toyoda's andon cord, digitized.
- **IBM Autonomic Computing (2001)** — Self-configuring, self-healing, self-optimizing systems. The Skill Flywheel is MAPE-K with sovereignty guardrails.
- **Saltzer, Reed & Clark (1984)** — End-to-end argument. Governance at the endpoints, not in the network. The zone model is a freedom guarantee expressed as architecture.
- **RFC 1958 / RFC 3439** — Simplicity as scaling strategy. Three files and a loop. Complexity above the thin waist, not in it.

---

## Project Structure

```
├── autonomaton.py                  # Entry point / REPL
├── engine/
│   ├── pipeline.py                 # The invariant pipeline (5 stages)
│   ├── cognitive_router.py         # Stage 2: cache → keyword → unknown
│   ├── dispatcher.py               # Stage 5: handler dispatch
│   ├── flywheel.py                 # DETECT + PROPOSE + APPROVE
│   ├── telemetry.py                # Feed-first structured logging
│   ├── glass.py                    # Pipeline visualization (reads telemetry)
│   ├── ux.py                       # Andon Gate / Kaizen UX
│   ├── llm_client.py               # LLM adapter (model-agnostic)
│   ├── dock.py                     # Local RAG
│   └── pit_crew.py                 # Skill generation (Red zone)
├── profiles/
│   ├── reference/                  # The demo profile (architecture showcase)
│   │   └── config/
│   │       ├── routing.config      # ← The Cognitive Router's brain
│   │       ├── zones.schema        # ← The sovereignty guardrail
│   │       └── pattern_cache.yaml  # ← What the Ratchet learned
│   └── blank_template/             # Existence proof: engine needs nothing
└── tests/                          # Architectural proof suite
```

---

## Sprint History

This implementation was built through disciplined single-fix sprints, each producing a clean commit and updating the architectural compliance register.

| Sprint | Fix | What Changed |
|--------|-----|--------------|
| V-001 | Sub-pipeline removal | Eliminated nested pipelines that poisoned the Ratchet cache. -884 lines. |
| V-004 | Declarative Kaizen | Config-driven consent flow replaced hardcoded options. |
| V-009 | Telemetry-based tests | All architecture tests assert against the exhaust. |
| V-011 | Recognition trace truth | Tier, method, and cost in Stage 2 trace reflect reality. |
| V-013 | Flywheel DETECT | `pattern_hash` in telemetry, `detect_patterns()` operational. |
| V-014 | Config-driven tiers | Zero hardcoded tier assignments — all from `routing.config`. |
| V-016 | Flywheel PROPOSE | Structured YAML proposals from detected patterns. Tier 0. |
| V-018 | Kaizen UX truth | Real costs from `models.yaml`, unified tier display, Learning Mode. |
| V-019 | Flywheel APPROVE | Operator deploys skills to cache. Self-improvement loop closed. |

---

## The Pattern vs. The Implementation

This repository is the reference implementation. The Autonomaton Pattern itself is the set of architectural commitments described in the [Pattern Release document](https://the-grove.ai). Any person or team can implement the pattern with any tech stack. The test is structural:

- Does behavior governance live in declarative configuration?
- Does the Cognitive Router enable downward migration toward cheaper compute?
- Does every action have an explicit zone classification?
- Does the system learn from usage telemetry and propose improvements?
- Does the system fail honestly with diagnostic context?
- Can an auditor reconstruct any decision from the telemetry alone?

All yes → you built an Autonomaton. Any no → you know exactly what to fix.

---

## License

Pattern specification: CC BY 4.0 — the pattern is open because the thesis requires it.

Reference implementation: See LICENSE.

---

*The Grove AI Foundation — [the-grove.ai](https://the-grove.ai)*

*"Design is philosophy expressed through constraint."*
