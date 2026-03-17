# Session Zero Intake Skill

## Overview

Session Zero is the Cortex's **first act of learning**. Before the Autonomaton can effectively assist an operator, it must understand their world: who they are, who they work with, what they do, and how they communicate.

This skill conducts a guided **Socratic interview** to seed the knowledge base with foundational context.

## Purpose

Without Session Zero, the Autonomaton operates blindly:
- No entity profiles (players, parents, venues)
- No business context (goals, constraints, priorities)
- No voice calibration (how to communicate appropriately)

Session Zero transforms the system from a generic tool into a **contextual partner**.

## Trigger Commands

```
session zero
run session zero
start session zero
intake
onboarding
```

## Governance

| Attribute | Value | Rationale |
|-----------|-------|-----------|
| Zone | Yellow | Writes to entities/ and dock/ |
| Tier | 2 (Supervised) | Requires one-thumb approval |
| LLM Tier | Sonnet | Conversational depth needed |

## Interview Phases

### Phase 1: Identity & Role
Understand who the operator is and what they do. This grounds all future context.

### Phase 2: Key Relationships
Map the people in the operator's world. These become entity profiles.

### Phase 3: Daily Workflows
Understand routines, schedules, and recurring responsibilities.

### Phase 4: Friction Points
Identify where the operator struggles. These become improvement opportunities.

### Phase 5: Voice Calibration
Learn communication preferences to match the operator's style.

## Output Artifacts

| Type | Location | Description |
|------|----------|-------------|
| Entities | `entities/` | Player, parent, venue profiles |
| Dock | `dock/` | Business context documents |
| Voice | `config/voice.yaml` | Communication preferences |

## Usage Flow

```
1. Operator triggers "session zero"
2. Yellow Zone approval requested
3. Upon approval, Cortex begins interview
4. Multi-turn conversation gathers context
5. Artifacts generated and saved
6. Summary presented to operator for confirmation
```

## Implementation Status

- [x] Skill directory created
- [x] config.yaml defined
- [x] prompt.md template written
- [ ] LLM client integration (Sprint 2)
- [ ] Entity extraction pipeline
- [ ] Voice configuration writer

## Notes

Session Zero should be run:
- When a new profile is created
- When significant changes occur (new players, new season)
- When the operator feels the system has "drifted"

The interview is designed to be **conversational, not clinical**. The Cortex should feel like a thoughtful colleague, not an intake form.
