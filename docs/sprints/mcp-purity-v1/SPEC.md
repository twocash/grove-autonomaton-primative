# SPRINT SPEC: MCP Purity + Cost Telemetry

> *"Design is philosophy expressed through constraint."*
> Sprint Name: `mcp-purity-v1`
> Generated: 2026-03-19
> Dependency: Executes AFTER domain-purity-v1
> Domain Contract: Autonomaton Architect (Anti-Code-Party Protocol)

---

## Purpose

domain-purity-v1 extracted coaching terms from the analytical engine
(cortex, compiler, content_engine). This sprint finishes the job:
the MCP dispatch layer and effector layer still contain service-
specific handler names, Google API constants, and domain-specific
payload formatting logic hardcoded in Python.

Simultaneously, this sprint wires cost_usd reliably through the main
telemetry stream — the missing piece that makes the Ratchet's
economic claims auditable.

---

## Design Context for Agentic Execution

This contract will be executed by an agentic coding session. The
agent has never seen this codebase. It will read the contract
line-by-line and execute task-by-task. The contract is designed
for this execution model:

1. **Every task starts with a READ.** The agent reads the target
   file and confirms the pattern exists before editing.
2. **Every gate is automated.** Python one-liners that exit 0 or 1.
   No manual verification. No "check that it looks right."
3. **Anti-patterns are explicit.** The agent will try to take
   shortcuts. The contract names them in advance.
4. **Tasks are context-window sized.** No task requires the agent
   to hold more than one file in working memory.
5. **Cognitive agnosticism is enforced.** The engine dispatches to
   TIERS. Zero model names, zero provider names in engine code.
   models.yaml maps tiers to model IDs. The engine is blind.

---

## Violations Being Fixed

| ID | Severity | What | Where |
|----|----------|------|-------|
| P4 | HIGH | mcp_calendar, mcp_gmail handler names in dispatcher | engine/dispatcher.py |
| P5 | HIGH | GOOGLE_CALENDAR_SCOPES, GMAIL_SCOPES in effectors | engine/effectors.py |
| P5b | HIGH | `if server == "google_calendar"` routing in effectors | engine/effectors.py |
| P8 | MEDIUM | cost_usd not reliably in main telemetry stream | engine/llm_client.py → pipeline.py |
| P4b | MEDIUM | Calendar payload formatting logic in dispatcher | engine/dispatcher.py |
| P4c | MEDIUM | Email drafting prompt hardcoded in dispatcher | engine/dispatcher.py |
| D1 | MEDIUM | Entity types hardcoded in fill_entity_gap prompt | engine/dispatcher.py |

---

## Architectural Approach

### Cost Telemetry (P8): Metadata Cache, Not Interface Change

call_llm() has 24 call sites. Changing the return type from string
to structured dict would require updating every caller — high
regression risk for agentic execution.

Instead: call_llm() continues returning a string. It also writes
metadata (cost_usd, model, tokens_in, tokens_out) to a module-level
cache. A new function get_last_call_metadata() retrieves it. The
pipeline reads cost after each handler returns.

This is pragmatic, not pure. A future sprint can do the clean
interface change (LLMResult dataclass). This sprint gets cost
flowing through telemetry without touching 24 call sites.

ANTI-PATTERN WARNING: The agent may try to change the call_llm()
return type. This breaks 24 callers. Do not do this. The metadata
cache approach is specified. Follow it.

### MCP Handlers (P4): Generic Formatter, Not Named Handlers

The current pattern: _handle_mcp_calendar contains a calendar-
specific LLM prompt that extracts event parameters and formats a
Google Calendar API payload. _handle_mcp_gmail does the same for
email drafting.

The correct pattern: a SINGLE generic handler _handle_mcp_formatter
that reads a prompt template from profile config and dispatches to
the configured tier. The prompt template defines what to extract.
The handler is domain-blind. This is the same pattern as
ratchet_interpreter — config-driven LLM dispatch.

Prompt templates live at:
`profiles/{profile}/config/mcp-formatters/{server}_{capability}.md`

Example: `mcp-formatters/google_calendar_create_event.md` contains
the extraction prompt for calendar event parameters. The engine
reads the template, substitutes {user_input}, calls the tier, and
returns the structured payload as an MCP action.

ANTI-PATTERN WARNING: The agent may try to "rename" the existing
handlers from _handle_mcp_calendar to _handle_mcp_formatter while
keeping the domain logic inside. This is the Hardcoded Fallback
anti-pattern. The prompt text moves to config. The handler becomes
generic. It reads config and dispatches. Nothing else.

### Effector Layer (P5): Read Config, Not Constants

The current pattern: GOOGLE_CALENDAR_SCOPES and GMAIL_SCOPES are
Python module constants. `if server == "google_calendar"` routes
to _execute_calendar().

The correct pattern: effectors.py reads auth.scopes from mcp.config
per server. Service routing uses a registry pattern that reads
mcp.config instead of an if/elif chain. The Google API integration
code stays (it's the implementation, not the config) but the SERVICE
SELECTION and SCOPE CONFIGURATION become config-driven.

ANTI-PATTERN WARNING: The agent may try to remove the Google API
integration code entirely. Do not do this. The implementation
(OAuth flow, API calls) is correct. What's wrong is the CONFIGURATION
(hardcoded scopes, hardcoded routing). Config moves to mcp.config.
Implementation stays.

---

## Epic Structure

### Epic A: Cost Telemetry Flow (P8)
Add metadata cache to llm_client.py. Pipeline reads cost after
handler returns. cost_usd lands in main telemetry for every
LLM-involved traversal.

### Epic B: Generic MCP Formatter (P4, P4b, P4c)
Create prompt templates for calendar and email formatting. Replace
_handle_mcp_calendar and _handle_mcp_gmail with _handle_mcp_formatter.
Remove _format_calendar_payload. Update routing.config handler names.

### Epic C: Effector Config (P5, P5b)
Remove hardcoded scope constants. Read from mcp.config. Replace
if/elif server routing with config-driven dispatch.

### Epic D: Entity Gap Purity (D1)
Replace hardcoded entity types in fill_entity_gap prompt with
values loaded from entity_config.yaml.

### Epic E: Test Hardening
Extend domain term grep. Add test for mcp.config/effector
consistency. Verify cost_usd appears in pipeline telemetry.
