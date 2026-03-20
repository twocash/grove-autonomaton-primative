# The Autonomaton Pattern

## What Is an Autonomaton?

An Autonomaton is an extended cognition system, not a chatbot. It combines human judgment with machine capability through a governed pipeline. The human operator remains in control; the system provides leverage. Think of it as a cognitive exoskeleton: it amplifies your capabilities without replacing your decision-making.

The key distinction: chatbots respond to prompts. Autonomatons collaborate through structured governance. Every action is visible, auditable, and reversible.

---

## The Five-Stage Invariant Pipeline

Every interaction traverses five stages in sequence. No shortcuts, no bypasses.

### Stage 1: Telemetry
The system logs every input before processing. This creates an immutable audit trail. Schema validation ensures data integrity. If logging fails, processing stops.

### Stage 2: Recognition
The Cognitive Router classifies intent, domain, and zone. It uses a two-layer approach: deterministic rules first (keywords, patterns), then LLM interpretation for ambiguous cases. Classification determines the tier and governance requirements.

### Stage 3: Compilation
The system queries the Dock (local RAG) for relevant context. Strategic documents, entity information, and prior decisions inform the response. Compilation adapts based on intent_type: conversational intents skip context loading; informational and actionable intents load relevant chunks.

### Stage 4: Approval
Unified governance happens here. Green zone actions auto-approve. Yellow zone requires one-thumb confirmation. Red zone requires explicit approval with full context review. The operator always has final say.

### Stage 5: Execution
The Dispatcher routes to the appropriate handler. Handlers are dumb pipes—they execute based on what earlier stages decided. All side effects (API calls, file writes) happen here, after approval.

---

## Tiered Classification

The system uses four tiers to balance cost, speed, and capability.

**Tier 0 (Deterministic):** Keyword matches and cached patterns. Free, instant. No LLM required.

**Tier 1 (Haiku):** Fast, cheap classification and entity extraction. For routine operations.

**Tier 2 (Sonnet):** Capable synthesis and content generation. For substantive work.

**Tier 3 (Opus):** Architectural judgment and complex reasoning. Reserved for high-stakes decisions.

The Ratchet demotes intents to lower tiers as patterns stabilize. What starts as Tier 2 becomes Tier 0 through confirmed usage.

---

## The Zone Model

Every action declares a governance zone.

**Green Zone:** Safe autonomous execution. Greetings, status queries, reading data. No approval needed.

**Yellow Zone:** Reversible actions requiring confirmation. Sending emails, scheduling events, modifying records. One-thumb approval.

**Red Zone:** High-stakes or irreversible actions. System modification, financial transactions, external commitments. Full context review required.

The effective zone is always the MORE restrictive of the intent zone and capability zone. A green intent calling a yellow API becomes yellow.

---

## The Skill Flywheel

The system evolves through observation, not specification.

1. **Observe:** Telemetry captures operator patterns
2. **Detect:** Cortex lenses identify workflow gaps
3. **Propose:** System suggests new skills or upgrades
4. **Approve:** Operator reviews proposals (Yellow/Red zone)
5. **Execute:** Pit Crew generates approved skills
6. **Refine:** Usage data feeds back to observation

No one writes requirements documents. The system learns what you need by watching what you do.

---

## The Ratchet (Reverse Tax)

Every use makes the next use cheaper.

When an LLM classifies an intent, the system records the pattern. Next time, deterministic rules handle it. Tier 2 becomes Tier 1 becomes Tier 0. The Ratchet only tightens—it never loosens without explicit operator approval.

This is the Reverse Tax: unlike software that demands more as you use it, an Autonomaton demands less. Your investment compounds.

---

## Digital Jidoka

Ambiguity stops the line.

When the system encounters:
- Unknown intent (low confidence)
- Multiple entity matches
- Zone escalation required
- Any form of uncertainty

It MUST:
1. Stop processing
2. Surface the decision to the operator
3. Provide clear options
4. Log the decision

No silent failures. No graceful degradation. The operator sees everything and decides everything.

---

## Minimum Viable Autonomaton

Three files and a loop:

1. **routing.config:** Maps intents to handlers and zones
2. **persona.yaml:** Defines identity and constraints
3. **dock/:** Strategic context documents

The loop: input → pipeline → output → repeat.

Everything else—Cortex analysis, skill generation, MCP integrations—builds on this foundation without changing it.

---

## The Seven Principles

1. **Never bypass the pipeline.** All roads lead through `run_pipeline()`.
2. **Config first, code last.** Express intent in YAML before writing handlers.
3. **Zones are non-negotiable.** Every action has a zone, always.
4. **Telemetry is sacred.** Schema validation protects data integrity.
5. **The human decides.** Jidoka surfaces decisions, never hides them.
6. **Skills compose.** Output data, not prose.
7. **The system teaches itself.** Through the Ratchet and Flywheel, not hardcoding.

---

## Architecture Summary

The Autonomaton Pattern separates concerns:

- **Dock (Layer 1):** Local RAG for strategic memory
- **Operator (Layer 2):** Human-in-the-loop with governance
- **Cortex (Layer 3):** Asynchronous analytical lenses

All three communicate through the Invariant Pipeline. The engine is domain-agnostic; the profile provides domain-specific configuration. This separation enables reuse: one engine, many Autonomatons.
