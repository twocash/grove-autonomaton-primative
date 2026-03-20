# SPRINT CONTRACT: MCP Purity + Cost Telemetry

> Atomic execution contract generated from SPEC.md
> Generated: 2026-03-19
> Sprint: `mcp-purity-v1`
> Depends on: domain-purity-v1 must be merged first

---

## Pre-Sprint

### Task 0.1: Create worktree
```bat
@echo off
cd /d C:\GitHub\grove-autonomaton-primative
git worktree add ..\grove-autonomaton-primative-mcp-purity-v1 master
cd /d C:\GitHub\grove-autonomaton-primative-mcp-purity-v1
```

### Task 0.2: Verify domain-purity-v1 landed
```cmd
python -c "
from pathlib import Path
assert Path('profiles/reference/config/entity_config.yaml').exists(), 'domain-purity-v1 not merged'
print('PASS: domain-purity-v1 present')
"
```
If this fails, STOP. Merge domain-purity-v1 first.

### Task 0.3: Verify clean baseline
```cmd
python -m pytest tests/ -x -q
```
ALL tests must pass before any edits.

---

## Epic A: Cost Telemetry Flow (P8)

**Gate:** cost_usd appears in Stage 5 telemetry events for
LLM-involved pipeline traversals.

**Approach:** call_llm() returns a string (no interface change).
It also writes metadata to a module-level cache. The pipeline
reads cost after each handler returns.

### Task A.1: READ engine/llm_client.py

Read the file. Locate:
- The `call_llm()` function (starts around line 278)
- The place where `cost` is calculated (after API response)
- The `log_llm_event()` call that writes to llm_calls.jsonl

Confirm these exist before proceeding.

### Task A.2: Add metadata cache to llm_client.py

**File:** `engine/llm_client.py`

Add ABOVE the `call_llm()` function:

```python
# =========================================================================
# Last-Call Metadata Cache
# =========================================================================
# Stores metadata from the most recent call_llm() invocation.
# The pipeline reads this to populate cost_usd in the main
# telemetry stream. This avoids changing call_llm()'s return
# type (string), which has 24 call sites.

_last_call_metadata: dict = {}


def get_last_call_metadata() -> dict:
    """Return metadata from the most recent call_llm() invocation.

    Returns dict with keys: cost_usd, model, tokens_in, tokens_out.
    Returns empty dict if no call has been made.
    """
    return _last_call_metadata.copy()
```

### Task A.3: Write metadata in call_llm()

**File:** `engine/llm_client.py`

In the `call_llm()` function, AFTER the cost is calculated and
BEFORE the return statement, add:

```python
        # Cache metadata for pipeline cost telemetry
        global _last_call_metadata
        _last_call_metadata = {
            "cost_usd": cost,
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }
```

Also add the same cache write in the EXCEPTION handler, with
zeroed values:
```python
        global _last_call_metadata
        _last_call_metadata = {
            "cost_usd": 0.0,
            "model": model,
            "tokens_in": 0,
            "tokens_out": 0,
            "error": str(e),
        }
```

### Task A.4: Pipeline reads cost from metadata cache

**File:** `engine/pipeline.py`
**Method:** `_log_pipeline_completion()`

Find where cost_usd is extracted (currently from llm_metadata).
Replace with a fallback chain that tries the metadata cache:

```python
        # Extract cost_usd: try routing metadata first, then LLM cache
        llm_metadata = routing_info.get("llm_metadata", {})
        cost = llm_metadata.get("cost_usd")
        if cost is None:
            try:
                from engine.llm_client import get_last_call_metadata
                last_meta = get_last_call_metadata()
                cost = last_meta.get("cost_usd")
            except ImportError:
                pass
```

Pass `cost_usd=cost` to the log_event() call.

### Task A.5: Reset metadata cache on profile switch

**File:** `engine/llm_client.py`

In the `reset_models_config()` function, also reset the metadata:
```python
def reset_models_config() -> None:
    global _models_config_cache, _last_call_metadata
    _models_config_cache = None
    _last_call_metadata = {}
```

### GATE A: Cost Telemetry

```bash
python -c "
from engine.llm_client import get_last_call_metadata
meta = get_last_call_metadata()
assert isinstance(meta, dict), 'get_last_call_metadata must return dict'
print('PASS: metadata cache function exists')
"
python -m pytest tests/ -x -q
```

---

## Epic B: Generic MCP Formatter Handler (P4)

**Gate:** _handle_mcp_calendar and _handle_mcp_gmail are replaced
by _handle_mcp_formatter. Formatting prompts live in profile config.
Zero calendar/email domain logic in the handler.

**CRITICAL ANTI-PATTERN WARNING:** The agent will be tempted to
rename the existing handlers while keeping the LLM prompts inside
Python. THIS IS THE HARDCODED FALLBACK ANTI-PATTERN. The prompt
text MUST move to config files. The handler MUST be generic —
it reads a prompt template, substitutes {user_input}, calls the
configured tier, parses JSON, returns an MCP action. Nothing else.

### Task B.1: Create MCP formatter prompt templates for coach_demo

**Dir:** `profiles/coach_demo/config/mcp-formatters/` (NEW)

**File:** `google_calendar_create_event.md`
```markdown
# Calendar Event Extraction

Extract scheduling parameters from the user's request.

## User Input
"{user_input}"

## Instructions
Return ONLY valid JSON with these fields:
- event_type: Type of event (lesson, practice, tournament, meeting)
- participant: Name of person/group involved
- date: Date in ISO format (YYYY-MM-DD)
- time: Time in 24-hour format (HH:MM)
- duration_minutes: Duration in minutes (default 60)
- location: Location if mentioned (optional)

JSON:
```

**File:** `gmail_send_email.md`
```markdown
# Email Extraction

Extract email parameters and draft content from the user's request.

## User Input
"{user_input}"

## Instructions
Return ONLY valid JSON with these fields:
- recipient: Name of the recipient
- subject: Email subject line
- body: Full email body text (professional, friendly tone)

JSON:
```

### Task B.2: Create empty mcp-formatters for reference and blank

**Dir:** `profiles/reference/config/mcp-formatters/` (NEW)
**Dir:** `profiles/blank_template/config/mcp-formatters/` (NEW)

Create empty directories. No formatters needed for profiles without
MCP servers. The handler gracefully fails when no template exists.

### Task B.3: Write the generic _handle_mcp_formatter

**File:** `engine/dispatcher.py`

Add a NEW handler method. Do NOT modify the existing handlers yet:

```python
def _handle_mcp_formatter(
    self,
    routing_result: RoutingResult,
    raw_input: str
) -> DispatchResult:
    """
    Generic MCP payload formatter.

    Reads a prompt template from profile config, calls the
    configured tier to extract structured parameters, and
    returns an MCP action for the effector layer.

    handler_args must specify:
    - server: MCP server name (e.g., "google_calendar")
    - capability: MCP capability (e.g., "create_event")
    - formatter_template: Prompt template name (without .md)

    The template is loaded from:
    profiles/{profile}/config/mcp-formatters/{formatter_template}.md
    """
    import json
    from engine.llm_client import call_llm
    from engine.profile import get_config_dir
    from engine.telemetry import log_event

    server = routing_result.handler_args.get("server", "")
    capability = routing_result.handler_args.get("capability", "")
    template_name = routing_result.handler_args.get(
        "formatter_template", f"{server}_{capability}"
    )

    if not server or not capability:
        return DispatchResult(
            success=False,
            message="MCP formatter requires server and capability in handler_args",
            data={"type": "mcp_formatter", "error": "missing_args"}
        )

    # Load prompt template
    config_dir = get_config_dir()
    template_path = config_dir / "mcp-formatters" / f"{template_name}.md"

    if not template_path.exists():
        return DispatchResult(
            success=False,
            message=f"MCP formatter template not found: {template_name}",
            data={"type": "mcp_formatter", "error": "template_not_found"}
        )

    try:
        template = template_path.read_text(encoding="utf-8")
    except Exception as e:
        return DispatchResult(
            success=False,
            message=f"Failed to read template: {e}",
            data={"type": "mcp_formatter", "error": "read_failed"}
        )

    # Substitute {user_input} in template
    prompt = template.replace("{user_input}", raw_input)

    # Determine tier from routing config
    tier = routing_result.tier if hasattr(routing_result, 'tier') else 1

    try:
        response = call_llm(
            prompt=prompt,
            tier=tier,
            intent=f"mcp_format:{server}_{capability}"
        )

        # Parse JSON payload
        json_str = response.strip()
        start = json_str.find('{')
        end = json_str.rfind('}')
        if start != -1 and end != -1:
            json_str = json_str[start:end + 1]
        payload = json.loads(json_str)

        return DispatchResult(
            success=True,
            message=f"MCP payload formatted: {server}.{capability}",
            data={
                "type": "mcp_action",
                "server": server,
                "capability": capability,
                "payload": payload,
            },
            requires_approval=True,
            approval_context=f"{server}.{capability}: {json.dumps(payload, indent=2)[:200]}"
        )

    except json.JSONDecodeError as e:
        return DispatchResult(
            success=False,
            message=f"Failed to parse MCP payload: {e}",
            data={"type": "mcp_formatter", "error": "json_parse"}
        )
    except Exception as e:
        log_event(
            source="dispatcher",
            raw_transcript=raw_input[:200],
            zone_context="yellow",
            intent=f"mcp_format:{server}_{capability}",
            inferred={"error": str(e), "handler": "mcp_formatter", "stage": "error"}
        )
        return DispatchResult(
            success=False,
            message=f"MCP formatting failed: {e}",
            data={"type": "mcp_formatter", "error": str(e)}
        )
```

### Task B.4: Register the new handler

**File:** `engine/dispatcher.py`
**Method:** `_register_handlers()`

Add to the handler registry dict:
```python
"mcp_formatter": self._handle_mcp_formatter,
```

Do NOT remove the old handlers yet. Both old and new must coexist
until routing.config is updated and tested.

### Task B.5: Update coach_demo routing.config — MCP intents

**File:** `profiles/coach_demo/config/routing.config`

Find the calendar_schedule route. It currently has:
```yaml
    handler: "mcp_calendar"
    handler_args:
      server: "google_calendar"
      capability: "create_event"
```

Change to:
```yaml
    handler: "mcp_formatter"
    handler_args:
      server: "google_calendar"
      capability: "create_event"
      formatter_template: "google_calendar_create_event"
```

Find the email_send route (or equivalent). Change handler from
"mcp_gmail" to "mcp_formatter" with:
```yaml
    handler: "mcp_formatter"
    handler_args:
      server: "gmail"
      capability: "send_email"
      formatter_template: "gmail_send_email"
```

### Task B.6: Verify new handler works before removing old

```bash
python -c "
from engine.profile import set_profile
set_profile('coach_demo')
from engine.dispatcher import Dispatcher
d = Dispatcher()
assert 'mcp_formatter' in d._handlers, 'mcp_formatter not registered'
print('PASS: mcp_formatter registered')
"
python -m pytest tests/ -x -q
```

If this fails, STOP. Fix the handler before proceeding.

### Task B.7: Remove old MCP handlers

**File:** `engine/dispatcher.py`

NOW remove:
- The entire `_handle_mcp_calendar()` method
- The entire `_handle_mcp_gmail()` method
- The entire `_format_calendar_payload()` method
- The handler registry entries for "mcp_calendar" and "mcp_gmail"

ANTI-PATTERN: Do NOT rename them. Do NOT comment them out. DELETE.
The generic handler replaces them. Two handlers doing the same job
is the Parallel Channel anti-pattern applied to dispatch.

### Task B.8: Verify no references to old handlers remain

```bash
python -c "
content = open('engine/dispatcher.py', encoding='utf-8').read()
assert '_handle_mcp_calendar' not in content, 'Old calendar handler remains'
assert '_handle_mcp_gmail' not in content, 'Old gmail handler remains'
assert '_format_calendar_payload' not in content, 'Calendar formatter remains'
# Check registry
assert '\"mcp_calendar\"' not in content, 'mcp_calendar in registry'
assert '\"mcp_gmail\"' not in content, 'mcp_gmail in registry'
print('PASS: Old MCP handlers fully removed')
"
```

### GATE B: Generic MCP Formatter

```bash
python -c "
from engine.dispatcher import Dispatcher
d = Dispatcher()
assert 'mcp_formatter' in d._handlers
assert 'mcp_calendar' not in d._handlers
assert 'mcp_gmail' not in d._handlers
print('PASS: Generic formatter only')
"
python -m pytest tests/ -x -q
```

---

## Epic C: Effector Config (P5, P5b)

**Gate:** Zero hardcoded scope constants. Zero `if server ==` routing.
Service config read from mcp.config.

**ANTI-PATTERN WARNING:** The agent will be tempted to delete the
Google API integration code (OAuth flow, API calls). DO NOT DO THIS.
The implementation is correct. What's wrong is the CONFIGURATION
being hardcoded. Scopes move to mcp.config. Service routing becomes
config-driven. Implementation stays.

### Task C.1: READ engine/effectors.py + mcp.config

Read both files. Confirm:
1. `GOOGLE_CALENDAR_SCOPES` and `GMAIL_SCOPES` are module constants
2. `if self.server == "google_calendar"` routes in execute()
3. mcp.config already has `auth.scopes` per server

The scopes in mcp.config are the AUTHORITY. The Python constants
must be removed and replaced with config reads.

### Task C.2: Add scope loader to ConfigLoader

**File:** `engine/effectors.py`

Add a method to the existing ConfigLoader class:

```python
@classmethod
def get_server_scopes(cls, server: str) -> list:
    """Load OAuth scopes for a server from mcp.config.

    Returns list of scope strings, or empty list if not configured.
    """
    if cls._mcp_config is None:
        cls._load_config()
    if cls._mcp_config is None:
        return []
    servers = cls._mcp_config.get("servers", {})
    server_config = servers.get(server, {})
    return server_config.get("auth", {}).get("scopes", [])
```

### Task C.3: Replace hardcoded scopes with config reads

**File:** `engine/effectors.py`

DELETE these module-level constants:
```python
GOOGLE_CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar']
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
```

In `get_google_calendar_service()`, replace all references to
`GOOGLE_CALENDAR_SCOPES` with:
```python
scopes = ConfigLoader.get_server_scopes("google_calendar")
if not scopes:
    scopes = ['https://www.googleapis.com/auth/calendar']  # fallback
```

In `get_gmail_service()`, replace all references to `GMAIL_SCOPES` with:
```python
scopes = ConfigLoader.get_server_scopes("gmail")
if not scopes:
    scopes = ['https://www.googleapis.com/auth/gmail.modify']  # fallback
```

NOTE: The inline fallback is acceptable here — it's a crash-prevention
default for missing config, same pattern as models.yaml fallbacks in
llm_client.py. The constant is gone. Config is authoritative.

### Task C.4: Add service registry to ConfigLoader

**File:** `engine/effectors.py`

Add to ConfigLoader:
```python
@classmethod
def get_configured_servers(cls) -> list:
    """Return list of server names from mcp.config."""
    if cls._mcp_config is None:
        cls._load_config()
    if cls._mcp_config is None:
        return []
    return list(cls._mcp_config.get("servers", {}).keys())

@classmethod
def get_server_status(cls, server: str) -> str:
    """Return server status from mcp.config (active/stub/not_implemented)."""
    if cls._mcp_config is None:
        cls._load_config()
    if cls._mcp_config is None:
        return "unknown"
    servers = cls._mcp_config.get("servers", {})
    return servers.get(server, {}).get("status", "unknown")
```

### Task C.5: Replace if/elif server routing with registry

**File:** `engine/effectors.py`
**Class:** `MCPServerConnection` (or equivalent)
**Method:** `execute()`

Find the routing block:
```python
if self.server == "google_calendar":
    return self._execute_calendar(capability, payload)
elif self.server == "gmail":
    return self._execute_gmail(capability, payload)
```

Replace with a registry pattern:
```python
# Service implementation registry — maps server names to methods.
# The registry is internal to the effector layer. The server NAMES
# come from mcp.config. The IMPLEMENTATIONS are engine code.
_service_registry = {
    "google_calendar": self._execute_calendar,
    "gmail": self._execute_gmail,
}

handler = _service_registry.get(self.server)
if handler:
    return handler(capability, payload)
```

NOTE: This keeps the implementation methods (_execute_calendar,
_execute_gmail) intact. They're the API integration code — correct
and tested. What changes is the ROUTING: from hardcoded if/elif
to a lookup dict. Adding a new MCP server means adding one line
to the registry, not a new elif branch.

### GATE C: Effector Config

```bash
python -c "
content = open('engine/effectors.py', encoding='utf-8').read()
assert 'GOOGLE_CALENDAR_SCOPES' not in content, 'Scope constant remains'
assert 'GMAIL_SCOPES' not in content, 'Scope constant remains'
# Verify config loader has scope method
from engine.effectors import ConfigLoader
assert hasattr(ConfigLoader, 'get_server_scopes')
print('PASS: Scopes from config, not constants')
"
python -m pytest tests/ -x -q
```

---

## Epic D: Entity Gap Purity (D1)

**Gate:** fill_entity_gap handler reads entity types from
entity_config.yaml, not hardcoded strings.

### Task D.1: READ the fill_entity_gap handler

**File:** `engine/dispatcher.py`
**Method:** `_handle_fill_entity_gap()`

Find the LLM prompt that contains:
```python
- entity_type: One of "players", "parents", "venues"
```

This is a domain-specific term list hardcoded in the prompt.

### Task D.2: Replace with config-driven entity types

Replace the hardcoded entity type list with a dynamic one
loaded from entity_config.yaml:

```python
from engine.config_loader import load_entity_config
entity_config = load_entity_config()
entity_types = [t["plural"] for t in entity_config.get("entity_types", [])]
type_list = ', '.join(f'"{t}"' for t in entity_types) if entity_types else '"entities"'
```

Then in the prompt, replace the hardcoded line with:
```python
f'- entity_type: One of {type_list}'
```

### GATE D

```bash
python -c "
content = open('engine/dispatcher.py', encoding='utf-8').read()
# The exact hardcoded string should be gone
assert '\"players\", \"parents\", \"venues\"' not in content, 'Hardcoded entity types remain'
print('PASS: Entity types from config')
"
python -m pytest tests/ -x -q
```

---

## Epic E: Test Hardening

**Gate:** Domain grep covers all violations. Cost telemetry tested.
MCP config consistency verified.

### Task E.1: Extend domain term list in engine grep test

**File:** `tests/test_pipeline_compliance.py`
**Test:** `test_no_domain_terms_in_engine` (from domain-purity-v1)

Add these terms to the domain_terms list:
```python
# MCP service names (should be in mcp.config, not engine code)
"GOOGLE_CALENDAR_SCOPES",
"GMAIL_SCOPES",
# Handler names (should be generic)
"_handle_mcp_calendar",
"_handle_mcp_gmail",
"_format_calendar_payload",
# Entity types in prompts
'"players", "parents", "venues"',
```

### Task E.2: Add cost_usd telemetry test

**File:** `tests/test_pipeline_compliance.py`

```python
class TestCostTelemetry:
    """P8: cost_usd flows through main telemetry stream."""

    def test_metadata_cache_exists(self):
        from engine.llm_client import get_last_call_metadata
        meta = get_last_call_metadata()
        assert isinstance(meta, dict)

    def test_metadata_populated_after_call(self):
        """After any LLM call, metadata cache has cost_usd."""
        # This test requires ANTHROPIC_API_KEY. Skip if not set.
        import os
        if not os.environ.get("ANTHROPIC_API_KEY"):
            import pytest
            pytest.skip("No API key — cannot test live LLM call")

        from engine.llm_client import call_llm, get_last_call_metadata
        call_llm(prompt="Say hello", tier=1, intent="test_cost")
        meta = get_last_call_metadata()
        assert "cost_usd" in meta, "cost_usd missing from metadata"
        assert meta["cost_usd"] >= 0, "cost_usd must be non-negative"
```

### Task E.3: Add MCP config consistency test

**File:** `tests/test_pipeline_compliance.py`

```python
class TestMCPConfigConsistency:
    """MCP handlers resolve to config-declared servers."""

    def test_mcp_formatter_templates_exist(self):
        """Every MCP route with mcp_formatter handler must have a template."""
        import yaml
        from pathlib import Path
        for profile in ["coach_demo"]:
            config_path = Path(f"profiles/{profile}/config/routing.config")
            with open(config_path) as f:
                config = yaml.safe_load(f)
            for intent, route in config.get("routes", {}).items():
                if route.get("handler") == "mcp_formatter":
                    args = route.get("handler_args", {})
                    template = args.get("formatter_template", "")
                    if template:
                        tpath = Path(f"profiles/{profile}/config/mcp-formatters/{template}.md")
                        assert tpath.exists(), \
                            f"{profile}/{intent}: template {template}.md not found"
```

### GATE E: Final Ship Gate

```bash
# 1. Full test suite
python -m pytest tests/ -x -q

# 2. Extended engine grep
python -c "
from pathlib import Path
terms = [
    # Domain terms (from domain-purity-v1)
    'coaching', 'golf', 'swing', 'lesson', 'tournament',
    'handicap', '\"player\"', '\"parent\"', '\"venue\"',
    'nobody tells you about', 'on the course',
    # MCP service constants (this sprint)
    'GOOGLE_CALENDAR_SCOPES', 'GMAIL_SCOPES',
    # Old handler names (this sprint)
    '_handle_mcp_calendar', '_handle_mcp_gmail',
    '_format_calendar_payload',
]
engine = Path('engine/')
fails = []
for f in engine.glob('*.py'):
    code = [l for l in f.read_text(encoding='utf-8').split('\n')
            if not l.strip().startswith('#')]
    text = '\n'.join(code)
    for t in terms:
        if t in text:
            fails.append(f'{f.name}: {t}')
if fails:
    print('FAIL:')
    for f in fails: print(f'  {f}')
else:
    print('SHIP GATE PASSED: Engine fully domain-free')
"
```

---

## Post-Sprint: Commit & Merge

```bat
@echo off
cd /d C:\GitHub\grove-autonomaton-primative-mcp-purity-v1
git add -A
git commit -m "mcp-purity-v1"
```

Merge to master:
```bat
cd /d C:\GitHub\grove-autonomaton-primative
git merge grove-autonomaton-primative-mcp-purity-v1
git push origin master
git worktree remove ..\grove-autonomaton-primative-mcp-purity-v1
```

---

## Verification Summary

| Claim | Test |
|-------|------|
| cost_usd in main telemetry | get_last_call_metadata() returns cost |
| Generic MCP formatter | mcp_formatter in registry, old handlers gone |
| MCP prompt templates in config | mcp-formatters/*.md in coach_demo |
| Scopes from mcp.config | GOOGLE_CALENDAR_SCOPES constant removed |
| Service routing config-driven | No if/elif server chain in execute() |
| Entity types from config | fill_entity_gap reads entity_config.yaml |
| Extended grep passes | All old handler/constant names absent |
| All tests pass | pytest exits 0 |

---

## Notes for Agentic Execution

This contract is designed to be executed 4-5 times by different
agentic coding sessions. Each session gets a clean worktree and
no prior context. The contract is self-contained.

**Things the agent will try that are WRONG:**

1. **Change call_llm() return type.** 24 call sites break. The
   metadata cache pattern is specified. Follow it.

2. **Rename old handlers instead of replacing.** The generic handler
   reads config. The old handlers had domain logic in Python. Moving
   a string from "specific" to "generic" doesn't fix the invariant.
   Config over code means config, not "generic code."

3. **Delete Google API implementation code.** The OAuth flow and
   API calls are correct implementation. The CONFIGURATION (scopes,
   routing) is what moves to config. Implementation stays.

4. **Add new domain terms while removing old ones.** Any domain-
   specific string that appears in a prompt INSIDE engine code is
   a violation. Prompts live in profile config. Engine code builds
   the prompt from config. It never contains domain vocabulary.

5. **Skip a gate.** Gates exist because the next epic depends on
   the previous one. Skipping a gate means building on a broken
   foundation. The agent MUST run the gate check and confirm PASS
   before proceeding to the next epic.

6. **Write model names in engine code.** Cognitive agnosticism is
   an invariant. The engine dispatches to tiers. models.yaml maps
   tiers to models. If the agent types a model name or provider
   name anywhere in engine/, it's a violation.
