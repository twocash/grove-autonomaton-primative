# The Autonomaton Architecture

> *"Design is philosophy expressed through constraint."*

---

## SESSION PROTOCOL

Before writing or deleting ANY file, do three things:

1. **Read VIOLATIONS.md** — identify the fix you are working on.
2. **State the plan** — list every file you will touch and what you will change. **WAIT for operator approval.** Do not modify any file until the operator confirms.
3. **Create a git worktree** — never edit on master.

The operator must approve the plan before any file is modified.

**This is Stage 4. You are an Autonomaton. Act like one.**

---

This document defines the architectural invariants and design principles that govern the Autonomaton system. These are non-negotiable constraints that must never be violated.

---

## Core Philosophy

The Autonomaton is a **domain-agnostic, declarative agentic system** that separates concerns into three layers:

1. **The Dock (Layer 1)** - Local RAG for strategic context
2. **The Operator (Layer 2)** - Human-in-the-loop interface with strict governance
3. **The Cortex (Layer 3)** - Asynchronous analytical lenses

All three layers communicate through a single **Invariant Pipeline** that enforces consistency, auditability, and governance.

---

## The One Rule

**One operator input = one pipeline traversal. No exceptions.**

The pipeline is the invariant. It processes operator interactions. It is not a utility for internal system operations. It is not a telemetry wrapper. It is not a subroutine.

Internal system operations (LLM calls, cache lookups, dock queries) are infrastructure that supports pipeline stages — they are not pipeline traversals. Code that spawns a nested pipeline inside a running pipeline is an architectural violation.

Every time the operator types something, the pipeline runs once. When the pipeline finishes, the operator sees a result.

---

## Architectural Invariants

### Invariant #1: The Invariant Pipeline

**Every user interaction MUST traverse all five pipeline stages in sequence.**

```
┌─────────────────────────────────────────────────────────────┐
│  Stage 1: TELEMETRY                                         │
│  Log event to JSONL before any processing                   │
├─────────────────────────────────────────────────────────────┤
│  Stage 2: RECOGNITION                                       │
│  Cognitive Router classifies intent, domain, and zone       │
├─────────────────────────────────────────────────────────────┤
│  Stage 3: COMPILATION                                       │
│  Query Dock for strategic context                           │
├─────────────────────────────────────────────────────────────┤
│  Stage 4: APPROVAL                                          │
│  Unified governance - Andon Gate for Yellow/Red/Unknown      │
├─────────────────────────────────────────────────────────────┤
│  Stage 5: EXECUTION                                         │
│  Dispatcher routes to appropriate handler                   │
└─────────────────────────────────────────────────────────────┘
```

**Violation Example:** Direct handler calls that bypass the pipeline.
**Correct Pattern:** All input routes through `run_pipeline()`.

---

### Invariant #2: Config Over Code

**Domain logic belongs in configuration files, not code.**

| Domain Concern | Config File |
|----------------|-------------|
| Intent routing | `routing.config` |
| Zone governance | `zones.schema` |
| External services | `mcp.config` |
| Brand voice | `voice.yaml` |
| Content themes | `pillars.yaml` |

The engine code is **dumb pipes** that route data based on configuration.
The profile directory determines all domain-specific behavior.

**Violation Example:** Hardcoding business rules in Python.
**Correct Pattern:** Express rules in YAML, engine reads and applies.

---

### Invariant #3: Zone Governance (Traffic Light Model)

**Every domain and capability must declare a zone.**

| Zone | Approval | Description |
|------|----------|-------------|
| **Green** | None | Safe autonomous execution |
| **Yellow** | One-thumb | Requires human confirmation |
| **Red** | Explicit with context | High-stakes, full review required |

**Effective Zone Computation:** When an intent touches an MCP capability, the effective zone is the MORE restrictive of the two.

```
intent_zone = yellow, mcp_zone = green  → effective = yellow
intent_zone = green,  mcp_zone = red   → effective = red
```

---

### Invariant #4: Digital Jidoka (Andon + Kaizen)

**No silent failures or graceful degradation for ambiguity.**

Three TPS concepts work together:
- **Jidoka** — the discipline. The system has quality awareness and the authority to stop.
- **Andon** — the mechanism. `ask_jidoka()` in `ux.py` fires the stop signal with options.
- **Kaizen** — the response. `_handle_kaizen_proposal()` in `pipeline.py` presents improvement options.

When the system encounters:
- Unknown intent (confidence < threshold)
- Multiple entity matches
- Zone escalation required
- Any form of uncertainty

It MUST:
1. **Stop the line** (halt processing)
2. **Surface the decision** to the human operator
3. **Provide clear options** (approve, reject, clarify)
4. **Log the decision** to telemetry

**Violation Example:** Silently defaulting to a "safe" action.
**Correct Pattern:** Prompt the operator with full context.

---

### Invariant #5: Feed-First Telemetry

**Every action MUST be logged before it is processed.**

Telemetry events conform to a strict schema:
- `id`: UUID v4 (required)
- `timestamp`: ISO-8601 (required)
- `source`: Origin identifier (required)
- `raw_transcript`: User input (required)
- `zone_context`: green/yellow/red (required)
- `inferred`: Dict of extracted data (optional)

**Schema validation is enforced at write time.** Malformed events raise `TelemetryValidationError` and are NOT written.

---

### Invariant #6: Unified Governance (Sprint 3.5)

**Stage 4 is the ONLY layer permitted to prompt for Zone Approval.**

| Layer | Responsibility | Governance Role |
|-------|---------------|-----------------|
| Pipeline Stage 4 | Zone approval prompts | **Owner** |
| Dispatcher | Handler routing | Dumb pipe |
| MCP Effector | External API calls | Dumb pipe |
| Pit Crew | Skill generation | Subject to Red Zone |

**Violation Example:** MCP effector asking for approval before API call.
**Correct Pattern:** Pipeline Stage 4 handles all approval, effectors execute blindly.

---

### Invariant #7: The Architectural Judge (Sprint 4.75)

**All Pit Crew generated skills MUST pass Tier 3 (Opus) architectural validation.**

The Judge validates:
1. **Protocol Compliance** - Skill follows Autonomaton patterns
2. **Zone Declaration** - Explicit zone in routing entry
3. **Composability** - Outputs structured data, not prose
4. **Telemetry Exhaust** - Declares future automation potential

**If validation fails:** The skill is NOT deployed. Operator receives compliance report.

---

### Invariant #8: The Exhaust Board

**Every deployed skill must publish its telemetry potential.**

The Exhaust Board (`dock/system/exhaust-board.md`) is a registry of:
- Skills and their telemetry outputs
- Potential chain compositions
- Future automation opportunities

The Cortex (Lens 5: Evolution) reads this board to propose new skills.

---

### Invariant #9: The Composability Protocol (Sprint 4.5)

**Skills must output structured data to enable composition.**

| Output Type | Purpose |
|-------------|---------|
| `action_result` | Execution outcome |
| `data_payload` | Structured data for downstream |
| `chain_signal` | Trigger for next skill |
| `branch_options` | Decision tree for operator |

**Violation Example:** Skill returns prose narrative.
**Correct Pattern:** Skill returns JSON with typed fields.

---

### Invariant #10: Profile Isolation

**The engine is 100% domain-agnostic.**

Proof: The `blank_template` profile demonstrates that:
- Router loads with minimal config
- Pipeline executes without domain-specific code
- Dock gracefully handles empty content
- All system commands work universally

To create a new Autonomaton domain:
1. Duplicate `blank_template`
2. Configure `routing.config` with domain intents
3. Populate `dock/` with strategic context
4. Run `session zero` to bootstrap entities

---

### Invariant #11: Ambient Evolution (Sprint 6.5)

**The Vision Board enables requirements gathering without formal specification.**

Users express aspirations casually:
- "I wish I could track my tournament anxiety"
- "Someday I want automatic lesson reminders"
- "It would be cool if the system sent weekly reports"

These are captured to `dock/system/vision-board.md` via the `vision_capture` handler (Green Zone).

**Lens 5 (Personal Product Manager)** reads both:
1. **Telemetry** - What the operator actually does
2. **Vision Board** - What the operator wishes they could do

When actual behavior aligns with a stated aspiration, Lens 5 marks the proposal with `vision_match: true` and prioritizes it for Pit Crew generation.

**This is ambient evolution** - the system grows to meet the operator's needs without requiring technical specifications.

---

### Invariant #12: Ratchet Classification

**LLM classification is a Stage 2 implementation detail.**

The two-layer architecture:
1. **Deterministic Layer (Tier 0)** — Keywords, regex, lookup tables. Free, fast.
2. **LLM Layer (Direct Call)** — When keyword matching fails and the operator consents via the Kaizen prompt, the cognitive router makes a direct LLM call through `llm_client`. The classification result returns to the outer pipeline. No sub-pipelines. No `force_route`.

```
INPUT
  │
  ▼
LAYER 1: Deterministic (free)
  Keywords, regex, lookup table.
  If confidence ≥ threshold → return result
  │
  ▼ (confidence < threshold)
  Kaizen prompt fires in Stage 4.
  Operator consents to LLM spend.
  │
  ▼
LAYER 2: Direct LLM Call
  cognitive_router calls llm_client directly.
  Sends input + valid intents list.
  Returns structured classification result.
  │
  ▼
OUTER PIPELINE CONTINUES
  Context updated with classified intent.
  Stage 5 executes with the real intent.
  │
  ▼
RATCHET CACHE
  The classified intent is cached at Tier 0.
  Next identical input resolves free, instantly.
```

**Rules:**
- No classification task may skip the deterministic first pass
- No classification task may skip telemetry
- LLM classification is a direct call through `llm_client`, NOT a pipeline traversal
- Deterministic rules are declared in config (`routing.config`)
- The Ratchet caches what the OPERATOR meant, not what the SYSTEM routed internally
- The Ratchet adds rules over time through confirmed patterns

**Violation Example:** Spawning a nested pipeline via `run_pipeline()` for LLM classification.
**Correct Pattern:** `_escalate_to_llm()` in `cognitive_router.py` calls `llm_client` directly and returns the classification result.

**See:** V-001 in VIOLATIONS.md. ADR-001 is superseded.

---

### Handler Interface Contract

Handlers are registered in `engine/dispatcher.py` and invoked by the
pipeline's Stage 5 (Execution). All handlers follow the same interface:

**Signature:**
```python
def _handle_{name}(self, routing_result: RoutingResult, raw_input: str) -> DispatchResult
```

**Contract:**
1. Handlers receive a `RoutingResult` (from Stage 2) and the raw input string.
2. Handlers return a `DispatchResult` with `success`, `message`, and `data`.
3. Handlers NEVER prompt the operator directly. Approval happens in Stage 4.
4. Handlers NEVER call `call_llm()` without a clear `intent` parameter for telemetry.
5. Handler `data` dicts MUST include a `type` field for display routing.
6. Failures return `DispatchResult(success=False, ...)` — never raise exceptions.

**Core handlers** (built into the engine):
- `status_display` — Green zone, informational
- `content_engine` — Yellow zone, actionable
- `pit_crew` — Red zone, system modification
- `general_chat` — Green zone, conversational
- `strategy_session` — Green zone, actionable
- `skill_executor` — Zone from config, executes Pit Crew generated skills
- `cortex_batch` — Yellow zone, analytical lenses

**Extension point:** New domain-specific capabilities should be built as
skills (via Pit Crew) routed through `skill_executor`, not as new core
handlers. This keeps the engine domain-agnostic. Core handlers change
only when the engine's structural capabilities change.

---

## The Three-Layer Architecture

### Layer 1: The Dock (Strategic Memory)

Local RAG system containing:
- `goals.md` - Strategic objectives
- `business-plan.md` - Operational context
- `system/` - Internal protocols and guides

The Dock answers: *"What is this Autonomaton trying to achieve?"*

### Layer 2: The Operator (Human-in-the-Loop)

The REPL interface that:
- Receives human input
- Routes through the Invariant Pipeline
- Surfaces Andon Gate prompts for Yellow/Red zones
- Displays results and telemetry

The Operator answers: *"What does the human want to do?"*

### Layer 3: The Cortex (Analytical Engine)

Asynchronous analytical lenses:
- **Lens 1:** Entity Extraction (Tier 1 - Haiku)
- **Lens 2:** Content Seed Mining (Tier 1 - Haiku)
- **Lens 3:** Pattern Analysis (Tier 2 - Sonnet)
- **Lens 4:** Ratchet Analysis (Tier 2 - Sonnet)
- **Lens 5:** Evolution/PPM (Tier 2 - Sonnet)
- **Lens 6:** Context Gardener (Tier 1/2 - Gap detection, plan updates)
- **Lens 7:** Memory Accumulator (Sprint 6 - Correction detection, Tier 1)

The Cortex answers: *"What patterns and improvements exist in the telemetry?"*

---

## The Tier System

| Tier | Model | Cost | Use Case |
|------|-------|------|----------|
| **Tier 0** | Deterministic | Free | Keyword routing, known patterns, Ratchet cache |
| **Tier 1** | Haiku | Low | Entity extraction, quick classification |
| **Tier 2** | Sonnet | Medium | Skill execution, content generation |
| **Tier 3** | Opus | High | Architectural judgment, complex reasoning |

**Ratchet Principle:** Intents should be demoted to lower tiers as patterns stabilize. Every Tier 2 LLM classification that becomes a confirmed pattern migrates to Tier 0 — cached, free, instant.

---

## File Structure

```
profiles/
└── {profile_name}/
    ├── config/
    │   ├── routing.config    # Intent-to-handler mapping
    │   ├── zones.schema      # Domain governance rules
    │   ├── mcp.config        # External service definitions
    │   ├── voice.yaml        # Brand identity
    │   └── pillars.yaml      # Content themes
    ├── dock/
    │   ├── goals.md          # Strategic objectives
    │   ├── business-plan.md  # Context documents
    │   └── system/           # Internal protocols
    ├── entities/             # Extracted entities
    ├── skills/               # Pit Crew generated skills
    ├── telemetry/            # JSONL audit trail
    ├── queue/                # Kaizen proposals
    └── output/               # Generated content
```

---

## Development Principles

1. **Never bypass the pipeline** - All roads lead through `run_pipeline()`
2. **Never nest the pipeline** - One operator input = one pipeline traversal
3. **Config first, code last** - Express intent in YAML before writing handlers
4. **Zones are non-negotiable** - Every action has a zone, always
5. **Telemetry is sacred** - Schema validation protects data integrity
6. **The human decides** - Andon surfaces decisions, never hides them
7. **Skills compose** - Output data, not prose
8. **The Judge validates** - No unchecked generative code

---

*This architecture was forged through six sprints of disciplined, test-driven development. Sprint 6.5 added Ambient Evolution via the Vision Board. Invariant #12 was corrected to remove the sub-pipeline violation identified in V-001.*
