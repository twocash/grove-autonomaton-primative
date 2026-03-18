# The Autonomaton Architecture

> *"Design is philosophy expressed through constraint."*

This document defines the architectural invariants and design principles that govern the Autonomaton system. These are non-negotiable constraints that must never be violated.

---

## Core Philosophy

The Autonomaton is a **domain-agnostic, declarative agentic system** that separates concerns into three layers:

1. **The Dock (Layer 1)** - Local RAG for strategic context
2. **The Operator (Layer 2)** - Human-in-the-loop interface with strict governance
3. **The Cortex (Layer 3)** - Asynchronous analytical lenses

All three layers communicate through a single **Invariant Pipeline** that enforces consistency, auditability, and governance.

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
│  Unified governance - Yellow/Red zones require Jidoka       │
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

### Invariant #4: Digital Jidoka

**No silent failures or graceful degradation for ambiguity.**

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
- Surfaces Jidoka prompts for Yellow/Red zones
- Displays results and telemetry

The Operator answers: *"What does the human want to do?"*

### Layer 3: The Cortex (Analytical Engine)

Asynchronous analytical lenses:
- **Lens 1:** Entity Extraction (Tier 1 - Haiku)
- **Lens 2:** Content Seed Mining (Tier 1 - Haiku)
- **Lens 3:** Pattern Analysis (Tier 2 - Sonnet)
- **Lens 4:** Ratchet Analysis (Tier 2 - Sonnet)
- **Lens 5:** Evolution/PPM (Tier 2 - Sonnet)

The Cortex answers: *"What patterns and improvements exist in the telemetry?"*

---

## The Tier System

| Tier | Model | Cost | Use Case |
|------|-------|------|----------|
| **Tier 0** | Deterministic | Free | Keyword routing, known patterns |
| **Tier 1** | Haiku | Low | Entity extraction, quick classification |
| **Tier 2** | Sonnet | Medium | Skill execution, content generation |
| **Tier 3** | Opus | High | Architectural judgment, complex reasoning |

**Ratchet Principle:** Intents should be demoted to lower tiers as patterns stabilize.

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
2. **Config first, code last** - Express intent in YAML before writing handlers
3. **Zones are non-negotiable** - Every action has a zone, always
4. **Telemetry is sacred** - Schema validation protects data integrity
5. **The human decides** - Jidoka surfaces decisions, never hides them
6. **Skills compose** - Output data, not prose
7. **The Judge validates** - No unchecked generative code

---

*This architecture was forged through six sprints of disciplined, test-driven development.*
