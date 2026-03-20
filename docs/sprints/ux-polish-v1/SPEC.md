# SPRINT SPEC: UX Polish + Self-Describing Architecture

> *"Design is philosophy expressed through constraint."*
> Sprint Name: `ux-polish-v1`
> Dependency: Executes AFTER mcp-purity-v1

---

## Purpose

Four issues degrade the reference profile demo experience. All four
are fixed by making the architecture work the way the papers say.

**Bug 1: The Ratchet doesn't ratchet.** The pipeline writes confirmed
classifications to pattern_cache.yaml on disk. The Cognitive Router
loaded the cache into memory at startup. It never re-reads the file.
The Ratchet writes. The Router doesn't see it. Same input, same cost,
same Jidoka — forever. This is a Config Over Code violation: config
changed, the engine didn't re-read it.

**Bug 2: Skill responses are swallowed.** The REPL shows "executed
successfully" instead of the LLM-generated content.

**Bug 3: general_chat ignores Compilation output.** The handler was
written for conversational intents (which skip dock). When routed with
intent_type: informational, Compilation loads dock — and the handler
throws it away. Stage 5 must use what the pipeline prepared.

**Opportunity: The architecture explains itself.** Ship the white
paper as dock content. Create an explain_system intent. Compilation
loads it. The handler uses it. Glass shows every stage. The system
explains itself through itself.

---

## Fixes

| ID | What | Where |
|----|------|-------|
| R1 | Ratchet cache invalidation — re-read after write | engine/pipeline.py |
| F1 | Skill execution display — show data["response"] | autonomaton.py |
| F2 | general_chat handler — use dock context when available | engine/dispatcher.py |
| F3 | explain_system intent + keyword cleanup | routing.config |
| F4 | White paper as dock content | profiles/reference/dock/ |


---

## The Unlock Flow

The reference profile's dock ships two documents: the white paper
condensation and the unlock section ("Why the Autonomaton Pattern
Produces Architectures That Centralized Systems Cannot"). These
feed the "so what?" progression:

1. "what is this?" → explain_system (T1) → white paper context
2. "so what?" → explain_system (T1) → unlock section context
3. "brainstorm distributed vs centralized" → deep_analysis (T3,
   Yellow zone) → both documents as context, apex synthesis

Tips guide the operator through this progression naturally. The
Glass Pipeline shows every tier escalation. The Jidoka prompt
explains the cost of T3. The Ratchet caches every confirmed
classification. The system gets cheaper because they used it.

This IS the Glass Pipeline demo described in the unlock section
itself. The operator reads about the experience while having it.
The medium is the message.

### Handler Tier Fix

Both general_chat and strategy_session hardcode their LLM tier
(T1 and T2 respectively) instead of reading from routing_result.
This sprint fixes both to read routing_result.tier. Config
determines the tier. The handler is a dumb pipe. After the fix:

- explain_system (tier: 1 in config) → T1 call
- deep_analysis (tier: 3 in config) → T3 call
- Same handler. Different tiers. Driven by config.
