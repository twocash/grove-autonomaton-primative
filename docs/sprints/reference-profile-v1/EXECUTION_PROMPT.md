# EXECUTION PROMPT: Reference Profile v1 — The Glass Pipeline

> **Sprint:** `reference-profile-v1`
> **Repo:** `C:\GitHub\grove-autonomaton-primative`
> **Generated:** 2026-03-18
> **Predecessor:** Purity Audit v1 (landed), Purity Audit v2 (not yet landed)

---

## Context

You are executing a sprint on the Autonomaton — a domain-agnostic, declarative
agentic system with a five-stage invariant pipeline. The system has two existing
profiles: `coach_demo` (fully configured golf coach domain) and `blank_template`
(empty starting point).

You are building a THIRD profile — `reference` — the publishable reference
implementation that ships alongside two academic papers. The reference profile
makes the architecture VISIBLE through a "glass pipeline" that narrates every
pipeline stage as it executes.

**Read these files FIRST before writing any code:**
```
CLAUDE.md                              — 12 architectural invariants (the constitution)
engine/pipeline.py                     — The five-stage invariant pipeline
engine/cognitive_router.py             — Hybrid Tier 0/1/2 classification + Ratchet cache
engine/dispatcher.py                   — Handler registry
engine/ux.py                           — Digital Jidoka (stop-the-line UX)
engine/config_loader.py                — Config loading utilities
autonomaton.py                         — REPL entry point
profiles/blank_template/config/        — Template config files to base reference on
profiles/coach_demo/config/            — Full domain config for pattern reference
docs/sprints/reference-profile-v1/SPEC.md    — Full design specification
docs/sprints/reference-profile-v1/SPRINTS.md — Story-level breakdown
```

## CRITICAL CONSTRAINTS

These are non-negotiable. Violating any of these means the sprint has failed.

1. **The engine MUST NOT change for this profile.** All behavior is driven by
   config files in the profile directory. If you find yourself writing
   `if profile == "reference":` in engine code, STOP. That violates
   Invariant #10 (Profile Isolation).

2. **The glass pipeline is a presentation layer, not a pipeline modification.**
   It reads `PipelineContext` AFTER `run_pipeline()` returns. It does NOT
   inject probes into pipeline stages. It does NOT modify the pipeline.
   It is a pure observer in the REPL display layer.

3. **No forced experiences.** The operator can type anything as their first
   input. Tips suggest the next interesting thing to try. Nothing blocks.
   No modals. No "you must complete this before proceeding."

4. **Config over code.** Tips are in tips.yaml. Persona is in persona.yaml.
   Routes are in routing.config. Profile flags are in profile.yaml. If
   behavior needs to change, a config file changes — not Python code.

5. **The pattern cache ships EMPTY.** The Ratchet turning IS the demo.
   Do not pre-seed the cache.

6. **`show_file` handler MUST reject path traversal.** Validate that the
   resolved path is within the profile directory. `../engine/llm_client.py`
   must return an error, not file contents.

7. **Existing tests must not break.** Run the full test suite after every
   epic. Zero regressions.

---

## EXECUTION SEQUENCE

Execute epics in this order. Run the build gate after each epic before
proceeding to the next.

### EPIC A: Reference Profile Directory

**Goal:** Create `profiles/reference/` with all required config files so
`python autonomaton.py --profile reference` loads without errors.

**Step 1:** Create the directory structure:
```
profiles/reference/
├── config/
│   ├── profile.yaml        ← NEW config type (see below)
│   ├── routing.config       ← Based on blank_template + inspection intents
│   ├── zones.schema         ← Copy from blank_template
│   ├── pattern_cache.yaml   ← Empty: "cache: {}"
│   ├── persona.yaml         ← Architecture guide persona (see below)
│   ├── voice.yaml           ← Minimal (copy from blank_template)
│   ├── pillars.yaml         ← Empty (copy from blank_template)
│   ├── mcp.config           ← Empty (copy from blank_template)
│   └── tips.yaml            ← Tip definitions (Epic D, create empty stub now)
├── dock/
│   └── system/
│       └── vision-board.md  ← Empty
├── entities/
│   └── .gitkeep
├── skills/
│   └── operator-guide/
│       └── prompt.md        ← Adapted for reference audience
├── telemetry/
│   └── .gitkeep
├── queue/
│   └── .gitkeep
└── output/
    └── .gitkeep
```

**Step 2:** Create `config/profile.yaml`:
```yaml
# profile.yaml — Reference Implementation
# Profile-level flags controlling REPL presentation and startup behavior.
# These flags are read by the REPL layer, not the engine.

display:
  glass_pipeline: true         # Show pipeline stage annotations
  glass_level: medium          # minimal | medium | full
  tips: true                   # Show contextual tips after interactions

startup:
  skip_welcome: true           # No welcome card at startup
  skip_startup_brief: true     # No strategic brief at startup
  skip_plan_generation: true   # No first-boot plan generation
  skip_queue: true             # No Kaizen queue processing at startup
```

**Step 3:** Create `config/persona.yaml`:
```yaml
name: "Engine"
role: "Architecture Guide"
tone: "Direct, technical, architecture-literate"
system_prompt_prefix: |
  You are the Autonomaton engine running as a reference implementation.
  Your profile has no domain context — the dock is empty, no skills are
  deployed, no entities exist. This is by design.

  When answering:
  - Explain what the architecture does, not what a domain system would do.
  - If dock context is empty, say so and explain what would be there
    in a configured system (goals, business plans, strategic context).
  - Be concise and technical. Your audience is CTOs, developers, and
    product leaders evaluating this architecture.
  - After the user's first interaction that triggers an LLM classification,
    mention the cost and suggest trying the same phrase again to see the
    Ratchet pattern cache in action.
  - After the Ratchet demo, suggest inspection commands: show cache,
    show telemetry, show config.
  - Never pretend to have domain knowledge you don't have.
```

**Step 4:** Create `config/routing.config` — start by copying
`profiles/blank_template/config/routing.config`, then ADD these routes
in the section after the existing system intents:

```yaml
  # --- Reference Profile: Inspection Commands ---
  show_config:
    tier: 0
    zone: green
    domain: system
    intent_type: informational
    description: "Display routing.config contents"
    keywords:
      - "show config"
      - "show routing"
      - "show routes"
    handler: "show_file"
    handler_args:
      target: "config/routing.config"

  show_zones:
    tier: 0
    zone: green
    domain: system
    intent_type: informational
    description: "Display zones.schema contents"
    keywords:
      - "show zones"
      - "show schema"
      - "show governance"
    handler: "show_file"
    handler_args:
      target: "config/zones.schema"

  show_telemetry:
    tier: 0
    zone: green
    domain: system
    intent_type: informational
    description: "Display recent telemetry events"
    keywords:
      - "show telemetry"
      - "show log"
      - "show events"
    handler: "show_file"
    handler_args:
      target: "telemetry/telemetry.jsonl"
      tail: 20

  show_cache:
    tier: 0
    zone: green
    domain: system
    intent_type: informational
    description: "Display pattern cache (the Ratchet)"
    keywords:
      - "show cache"
      - "show ratchet"
      - "show pattern cache"
    handler: "show_file"
    handler_args:
      target: "config/pattern_cache.yaml"

  show_engine:
    tier: 0
    zone: green
    domain: system
    intent_type: informational
    description: "Display engine source file manifest"
    keywords:
      - "show engine"
      - "show source"
      - "show code"
      - "show files"
    handler: "show_engine_manifest"
    handler_args: {}
```

**Step 5:** Copy remaining config files from blank_template:
- `zones.schema` — copy as-is
- `voice.yaml` — copy as-is
- `pillars.yaml` — copy as-is
- `mcp.config` — copy as-is
- `models.yaml` — copy as-is (Purity v2: model config externalized)

**Step 6:** Create `config/pattern_cache.yaml`:
```yaml
# Pattern Cache — The Ratchet
# Confirmed LLM classifications cached as Tier 0 lookups.
# This file starts empty. The Ratchet populates it through use.
cache: {}
```

**Step 7:** Create `skills/operator-guide/prompt.md` adapted for reference
audience. Focus on: the five pipeline stages, the three config files
(routing.config, zones.schema, pattern_cache.yaml), the zone model
(green/yellow/red), the Ratchet, inspection commands (show config, show
zones, show telemetry, show cache, show engine), and Session Zero. Write
it for CTOs/devs, not end users.

**Step 8:** Create `config/tips.yaml` as an empty stub for now:
```yaml
# tips.yaml — Contextual Tips
# Populated in Epic D
tips: []
```

**Build Gate A:**
```bash
python autonomaton.py --list-profiles
# Should list: blank_template, coach_demo, reference

python autonomaton.py --profile reference --skip-welcome --skip-queue
# Should load banner with "0 chunks from 0 sources"
# Type "hello" → general_chat responds
# Type "exit" → clean shutdown
# No errors
```

---

### EPIC B: Glass Pipeline Presentation Layer

**Goal:** Create `engine/glass.py` — a display module that renders pipeline
stage annotations after each `run_pipeline()` call.

**Step 1:** Create `engine/glass.py` with these functions:

```python
"""
glass.py - Glass Pipeline Display

Renders pipeline stage annotations to terminal for architecture-literate
audiences. Pure observer — reads PipelineContext metadata only. Does not
modify or probe the pipeline. This is presentation, not instrumentation.

The glass pipeline is enabled via profile.yaml display flags or --glass CLI.
"""

import sys
import os
from engine.pipeline import PipelineContext


class _Colors:
    """ANSI color codes (matches autonomaton.py and ux.py patterns)."""
    ENABLED = sys.stdout.isatty() and os.environ.get("TERM", "") != "dumb"
    RESET = "\033[0m" if ENABLED else ""
    BOLD = "\033[1m" if ENABLED else ""
    DIM = "\033[2m" if ENABLED else ""
    GREEN = "\033[92m" if ENABLED else ""
    YELLOW = "\033[93m" if ENABLED else ""
    RED = "\033[91m" if ENABLED else ""
    CYAN = "\033[96m" if ENABLED else ""
    WHITE = "\033[97m" if ENABLED else ""

_c = _Colors
```

The main function `display_glass_pipeline(context, level)` should:

1. Extract data from PipelineContext (see data extraction map below)
2. Build annotation lines for each stage
3. Render in a bordered box using ANSI colors

**Data extraction map (medium level):**

```python
# Stage 1: Telemetry
event_id = context.telemetry_event.get("id", "unknown")[:8]
source = context.source

# Stage 2: Recognition
# Purity v2: tier, confidence, cost_usd are now flat telemetry fields (authoritative)
# context.entities["routing"] still needed for: handler, intent_type, llm_metadata
routing = context.entities.get("routing", {})
intent_type = routing.get("intent_type", "unknown")
llm_metadata = routing.get("llm_metadata", {})

# Use flat telemetry fields when available (Purity v2)
tier = context.telemetry_event.get("tier", routing.get("tier", 0))
confidence = context.telemetry_event.get("confidence", routing.get("confidence", 0.0))
cost_usd = context.telemetry_event.get("cost_usd")

# Determine classification method
if llm_metadata.get("source") == "pattern_cache":
    method = "cache HIT ✓"
    cost_str = "$0.00"
elif tier >= 2 and not llm_metadata.get("forced_route"):
    method = "LLM"
    cost_str = f"${cost_usd:.4f}" if cost_usd else "~$0.003"
elif llm_metadata.get("forced_route"):
    method = "forced"
    cost_str = "$0.00"
else:
    method = "keyword"
    cost_str = "$0.00"

# Stage 3: Compilation
if intent_type == "conversational":
    compilation_str = "Skipped — conversational intent"
elif not context.dock_context or (context.dock_context and not context.dock_context[0]):
    compilation_str = "Dock query: [empty — no context loaded]"
else:
    compilation_str = f"Dock query: {len(context.dock_context)} chunk(s)"

# Stage 4: Approval
zone = context.zone or "green"
if not context.approved and context.result and context.result.get("status") == "cancelled":
    approval_str = "CANCELLED"
elif zone == "green":
    if not routing.get("action_required", True):
        approval_str = "GREEN auto-approve │ no action required"
    else:
        approval_str = "GREEN auto-approve"
elif zone == "yellow":
    approval_str = "YELLOW — requires confirmation"
elif zone == "red":
    approval_str = "RED — explicit approval required"
else:
    approval_str = f"{zone.upper()}"

# Stage 5: Execution
handler = routing.get("handler", "passthrough")
```

**Step 2:** Add the Ratchet announcement logic. Track whether the Ratchet
announcement has fired this session with a module-level boolean. On the
FIRST cache hit per session, return a flag that the REPL layer uses to
print the announcement AFTER the glass box:

```
  ⚡ THE RATCHET: Classified by LLM last time → cache this time.
     Tier 0, $0.00. The system got cheaper because you used it.
```

Subsequent cache hits show HIT ✓ in the glass box but no announcement.
Implement this as a function `get_ratchet_announcement(context)` that
returns the announcement string or None.

**Step 3:** Add a `format_glass_box()` helper that builds the bordered
box string. Use the `_Colors` pattern from ux.py. Zone names get their
matching color (GREEN/YELLOW/RED). Stage numbers in CYAN. Metadata in DIM.
Box border in DIM WHITE.

**Build Gate B:**
```bash
python autonomaton.py --profile reference
# Type "hello" → glass box renders with all 5 stages
# Type "what should I focus on" → glass box shows Tier 2 LLM, cost ~$0.003
# Type "what should I focus on" → glass box shows Tier 0 cache HIT ✓, $0.00
#   PLUS Ratchet announcement below box
# Type "hello" again → glass box shows Tier 0 keyword, no announcement
```

---

### EPIC C: Reference Profile Handlers

**Goal:** Implement two new handlers and register them in the dispatcher.

**Step 1:** Implement `show_file` handler.

Add to the dispatcher's handler registry. The handler function signature
must match the existing pattern — look at how `status_display` or
`general_chat` handlers are registered and called. Study `dispatcher.py`
for the exact pattern before implementing.

```python
def handle_show_file(raw_input: str, routing_result, **kwargs) -> DispatchResult:
    """Display contents of a profile config file.
    
    Security: validates target path is within profile directory.
    """
    from engine.profile import get_profile_dir
    from pathlib import Path
    
    target = routing_result.handler_args.get("target", "")
    tail = routing_result.handler_args.get("tail", None)
    
    if not target:
        return DispatchResult(success=False, message="No target file specified")
    
    profile_dir = get_profile_dir()
    target_path = (profile_dir / target).resolve()
    
    # SECURITY: Reject path traversal
    if not str(target_path).startswith(str(profile_dir.resolve())):
        return DispatchResult(
            success=False,
            message=f"Access denied: {target} is outside the profile directory"
        )
    
    if not target_path.exists():
        return DispatchResult(
            success=True,
            message=f"[{target}]\n(empty — file does not exist yet)",
            data={"type": "file_display"}
        )
    
    content = target_path.read_text(encoding="utf-8")
    
    if tail and isinstance(tail, int):
        lines = content.strip().split("\n")
        content = "\n".join(lines[-tail:])
    
    header = f"── {target} ──"
    return DispatchResult(
        success=True,
        message=f"{header}\n{content}",
        data={"type": "file_display"}
    )
```

**IMPORTANT:** The above is pseudocode showing the logic. Study the actual
`DispatchResult` dataclass and handler registration pattern in `dispatcher.py`
before implementing. Match the existing function signature exactly.

Also note: `get_profile_dir()` may not exist yet — check `engine/profile.py`
for the available functions. You may need to construct the profile directory
path from `get_config_dir()` by going up one level, or add a helper.

**Step 2:** Implement `show_engine_manifest` handler.

```python
def handle_show_engine_manifest(raw_input, routing_result, **kwargs):
    """Display engine source file manifest with line counts."""
    from pathlib import Path
    
    # Engine dir is always at repo_root/engine/
    engine_dir = Path(__file__).parent  # if this lives in engine/
    # OR calculate from repo root
    
    manifest_lines = []
    total_lines = 0
    
    # Core engine files in display order
    engine_files = [
        "pipeline.py",
        "cognitive_router.py",
        "dispatcher.py",
        "telemetry.py",
        "ux.py",
        "cortex.py",
        "compiler.py",
        "dock.py",
        "llm_client.py",
        "config_loader.py",
        "glass.py",  # New in this sprint
    ]
    
    for filename in engine_files:
        filepath = engine_dir / filename
        if filepath.exists():
            line_count = len(filepath.read_text(encoding="utf-8").splitlines())
            total_lines += line_count
            # Extract first line of module docstring
            desc = _extract_module_description(filepath)
            manifest_lines.append(
                f"  {filename:<24} {line_count:>4} lines   {desc}"
            )
    
    # Add entry point
    entry_point = engine_dir.parent / "autonomaton.py"
    if entry_point.exists():
        ep_lines = len(entry_point.read_text(encoding="utf-8").splitlines())
        total_lines += ep_lines
    
    header = f"ENGINE MANIFEST ({len(manifest_lines)} modules, ~{total_lines:,} lines)"
    separator = "─" * 55
    
    output = f"{header}\n{separator}\n"
    output += "\n".join(manifest_lines)
    output += f"\n{separator}\n"
    output += f"  Entry point: autonomaton.py  {ep_lines} lines"
    
    return DispatchResult(
        success=True, message=output,
        data={"type": "engine_manifest"}
    )
```

Helper for docstring extraction:
```python
def _extract_module_description(filepath: Path) -> str:
    """Extract first meaningful line from module docstring."""
    lines = filepath.read_text(encoding="utf-8").splitlines()
    in_docstring = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('"""') and not in_docstring:
            # Single-line docstring
            if stripped.endswith('"""') and len(stripped) > 6:
                return stripped[3:-3].strip()
            in_docstring = True
            content = stripped[3:].strip()
            if content:
                return content
            continue
        if in_docstring:
            if stripped.endswith('"""'):
                return stripped[:-3].strip() if stripped[:-3].strip() else "No description"
            if stripped:
                return stripped
    return "No description"
```

**Step 3:** Register both handlers in `dispatcher.py`.

Study the existing handler registration pattern. Handlers are registered
in a dict mapping handler name strings to functions. Add:
- `"show_file"` → `handle_show_file`
- `"show_engine_manifest"` → `handle_show_engine_manifest`

Place the handler functions in the appropriate location — either in
`dispatcher.py` itself (if that's where other handlers live) or in a
new module that dispatcher imports. Follow the existing pattern.

**Build Gate C:**
```bash
python autonomaton.py --profile reference
# Type "show config" → displays routing.config with header
# Type "show zones" → displays zones.schema with header
# Type "show telemetry" → displays last 20 telemetry events (or "empty")
# Type "show cache" → displays pattern_cache.yaml (should show cache: {})
# Type "show engine" → displays engine manifest table with line counts
# All five go through the pipeline (glass box shows for each)
```

---

### EPIC D: Contextual Tips System

**Goal:** Implement the declarative tip system that guides the OOB tour.

**Step 1:** Write the full `config/tips.yaml` for the reference profile:
```yaml
# tips.yaml — Contextual Tips for Reference Profile
# Each tip fires once per session based on trigger conditions.
# The tip engine evaluates triggers against PipelineContext after each run.

tips:
  - id: first_greeting
    trigger:
      after_intent: "general_chat"
    text: "Try something the system won't recognize to see what happens."

  - id: first_llm
    trigger:
      after_tier: 2
    text: "That used the LLM. Try the exact same phrase again."

  - id: ratchet_seen
    trigger:
      after_cache_hit: true
    text: "Type `show cache` to see what the Ratchet stored."

  - id: after_cache_inspect
    trigger:
      after_intent: "show_cache"
    text: "Try `clear cache` to see what happens when the zone changes."

  - id: first_yellow
    trigger:
      after_zone: "yellow"
    text: "Type `show telemetry` to see the full audit trail."

  - id: after_telemetry
    trigger:
      after_intent: "show_telemetry"
    text: "Type `show engine` to see the source code manifest."

  - id: after_engine
    trigger:
      after_intent: "show_engine"
    text: "Type `session zero` to start building your own Autonomaton."

  - id: after_session_zero
    trigger:
      after_intent: "session_zero"
    text: "To build your own, copy this profile directory and customize."
```

**Step 2:** Implement the tip engine. This can live in `engine/glass.py`
(alongside the glass pipeline display) or a separate `engine/tips.py`.
Recommend keeping it in `glass.py` since both are presentation concerns.

```python
class TipEngine:
    """Declarative contextual tip system.
    
    Loads tip definitions from config/tips.yaml.
    Tracks shown tips in-memory (session-scoped, not persisted).
    Evaluates triggers against PipelineContext after each run.
    Returns at most one tip per interaction.
    """
    
    def __init__(self):
        self.tips = []
        self.shown_ids = set()
        self._loaded = False
    
    def load(self) -> None:
        """Load tips.yaml from active profile."""
        import yaml
        from engine.profile import get_config_dir
        
        tips_path = get_config_dir() / "tips.yaml"
        if not tips_path.exists():
            self._loaded = True
            return
        
        try:
            with open(tips_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self.tips = data.get("tips", [])
        except Exception:
            self.tips = []
        self._loaded = True
    
    def evaluate(self, context) -> str | None:
        """Evaluate tip triggers against PipelineContext.
        
        Returns tip text string or None.
        """
        if not self._loaded:
            self.load()
        
        routing = context.entities.get("routing", {})
        llm_meta = routing.get("llm_metadata", {})
        
        for tip in self.tips:
            tip_id = tip.get("id", "")
            if tip_id in self.shown_ids:
                continue
            
            trigger = tip.get("trigger", {})
            if self._matches(trigger, context, routing, llm_meta):
                self.shown_ids.add(tip_id)
                return tip.get("text", "")
        
        return None
```

```python
    def _matches(self, trigger, context, routing, llm_meta) -> bool:
        """Check if all trigger conditions are met."""
        if "after_intent" in trigger:
            if context.intent != trigger["after_intent"]:
                return False
        
        if "after_tier" in trigger:
            if routing.get("tier", 0) != trigger["after_tier"]:
                return False
        
        if "after_cache_hit" in trigger:
            is_cache_hit = llm_meta.get("source") == "pattern_cache"
            if is_cache_hit != trigger["after_cache_hit"]:
                return False
        
        if "after_zone" in trigger:
            if context.zone != trigger["after_zone"]:
                return False
        
        return True
```

**Step 3:** Add a display function for tips:
```python
def display_tip(tip_text: str) -> None:
    """Display a contextual tip line."""
    if tip_text:
        print(f"\n  {_c.DIM}💡 {tip_text}{_c.RESET}")
```

**Build Gate D:**
```bash
python autonomaton.py --profile reference
# Type "hello" → tip: "Try something the system won't recognize..."
# Type "what should I focus on" → tip: "That used the LLM..."
# Type "what should I focus on" → Ratchet + tip: "Type `show cache`..."
# Type "show cache" → tip: "Try `clear cache`..."
# Type "clear cache" → Jidoka + tip: "Type `show telemetry`..."
# Each tip appears ONCE — repeating any command shows no tip
```

---

### EPIC E: REPL Integration

**Goal:** Wire everything into `autonomaton.py` — profile flags, glass
display, tips, CLI flag, and banner.

**Step 1:** Add `load_profile_config()` to `engine/config_loader.py`:
```python
def load_profile_config() -> dict:
    """Load profile.yaml from active profile. Returns defaults if missing.
    
    Profile config controls REPL presentation and startup behavior.
    It is NOT engine config — the engine doesn't read this file.
    """
    import yaml
    from engine.profile import get_config_dir
    
    defaults = {
        "display": {
            "glass_pipeline": False,
            "glass_level": "medium",
            "tips": False
        },
        "startup": {
            "skip_welcome": False,
            "skip_startup_brief": False,
            "skip_plan_generation": False,
            "skip_queue": False
        }
    }
    
    try:
        config_path = get_config_dir() / "profile.yaml"
    except RuntimeError:
        return defaults
    
    if not config_path.exists():
        return defaults
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        # Merge with defaults (profile.yaml can be partial)
        for section in defaults:
            if section in data:
                defaults[section].update(data[section])
        return defaults
    except Exception:
        return defaults
```

**Step 2:** Modify `autonomaton.py` — add `--glass` to argument parser:
```python
parser.add_argument(
    "--glass",
    action="store_true",
    help="Enable glass pipeline display for any profile"
)
```

**Step 3:** Modify `main()` in `autonomaton.py`. After `set_profile(args.profile)`,
load profile config and initialize glass/tips:

```python
# Load profile config (presentation layer flags)
from engine.config_loader import load_profile_config
profile_config = load_profile_config()

# Glass pipeline: enabled by profile.yaml OR --glass CLI flag
glass_enabled = profile_config["display"]["glass_pipeline"] or args.glass
glass_level = profile_config["display"]["glass_level"]

# Tips engine: enabled by profile.yaml
tips_enabled = profile_config["display"]["tips"]
tip_engine = None
if tips_enabled:
    from engine.glass import TipEngine
    tip_engine = TipEngine()

# Startup gating: profile.yaml flags OR CLI flags (either can suppress)
startup = profile_config["startup"]
skip_welcome = startup["skip_welcome"] or args.skip_welcome
skip_queue = startup["skip_queue"] or args.skip_queue
skip_plan = startup["skip_plan_generation"]
skip_brief = startup["skip_startup_brief"]
```

**Step 4:** Gate the startup sequences using those flags. Currently in
`main()`, the plan generation, queue processing, welcome card, and startup
brief each have their own block. Wrap each with the appropriate flag:

- Plan generation block → gate with `if not skip_plan:`
- Queue processing → gate with `if not skip_queue and pending:`
  (already partially gated by `args.skip_queue`)
- Welcome card → gate with `if not skip_welcome:`
  (already partially gated by `args.skip_welcome`)
- Startup brief → gate with `if not skip_brief:`
  (currently nested inside the welcome card block)

Be careful with the existing `args.skip_welcome` logic — merge, don't
duplicate. The cleanest approach: replace `args.skip_welcome` with the
computed `skip_welcome` variable (which already OR's both sources).

**Step 5:** Wire glass pipeline display into the REPL loop. In the main
`while True` loop, after `context = run_pipeline(...)` and before
`display_result(context, verbose)`, add:

```python
# Glass pipeline display (if enabled)
if glass_enabled:
    from engine.glass import display_glass_pipeline
    display_glass_pipeline(context, glass_level)
```

**Step 6:** Wire tip engine into the REPL loop. After `display_result()`:

```python
# Contextual tips (if enabled)
if tip_engine:
    tip_text = tip_engine.evaluate(context)
    if tip_text:
        from engine.glass import display_tip
        display_tip(tip_text)
```

**Step 7:** Modify `print_banner()` to accept profile config and show
glass pipeline status. When `glass_enabled`, add a line after cortex_info:
```
  Glass Pipeline: ACTIVE
```

When profile is `reference`, add the intro block after the banner:
```
  This is the naked engine. No domain. No context. No skills.
  Every pipeline stage will announce itself as it runs.
  Type anything to see the architecture in motion.
```

**Build Gate E (Full OOB Flow):**
```bash
python autonomaton.py --profile reference
# 1. Banner shows "Glass Pipeline: ACTIVE" + intro block
# 2. No welcome card, no brief, no plan generation, no queue
# 3. Type "hello"
#    → Glass box (5 stages, Tier 0 keyword, GREEN auto-approve)
#    → general_chat response (architecture-aware)
#    → Tip: "Try something the system won't recognize..."
# 4. Type "what should I focus on"
#    → Glass box (Tier 2 LLM, cost ~$0.003)
#    → Handler response
#    → Tip: "That used the LLM. Try the exact same phrase again."
# 5. Type "what should I focus on"
#    → Glass box (Tier 0 cache HIT ✓, $0.00)
#    → ⚡ THE RATCHET announcement
#    → Tip: "Type `show cache` to see what the Ratchet stored."
# 6. Type "show cache"
#    → Glass box (Tier 0 keyword, GREEN)
#    → Cache file contents
#    → Tip: "Try `clear cache` to see what happens..."
# 7. Type "clear cache"
#    → Glass box stops at YELLOW zone
#    → Jidoka prompt fires
#    → Approve → cache cleared
#    → Tip: "Type `show telemetry`..."
# 8. Type "show telemetry"
#    → Glass box + telemetry log
#    → Tip: "Type `show engine`..."
# 9. Type "show engine"
#    → Glass box + engine manifest
#    → Tip: "Type `session zero`..."

# Also verify glass works on other profiles:
python autonomaton.py --profile coach_demo --glass --skip-welcome
# Glass annotations appear for coach_demo interactions
```


---

### EPIC F: Test Suite

**Goal:** Create `tests/test_reference_profile.py` verifying all sprint
deliverables. Run the full suite to confirm zero regressions.

**Step 1:** Study the existing test files in `tests/` to understand the
test patterns, imports, and fixtures used. Match the existing style.

**Step 2:** Write tests for these categories:

**Profile loading:**
- `test_reference_profile_loads` — set_profile("reference") succeeds
- `test_profile_config_defaults` — missing profile.yaml returns defaults
- `test_profile_config_reference` — reference profile.yaml returns
  glass_pipeline=True, skip_welcome=True, etc.
- `test_list_profiles_includes_reference` — list_available_profiles()
  includes "reference"

**Glass pipeline:**
- `test_glass_keyword_match` — mock PipelineContext with tier 0 keyword
  match, verify glass output contains "Tier 0" and "keyword"
- `test_glass_llm_classification` — mock context with tier 2, verify
  glass output contains cost estimate
- `test_glass_cache_hit` — mock context with tier 0 + pattern_cache
  source, verify output contains "HIT ✓" and "$0.00"
- `test_glass_conversational_skip` — mock conversational intent, verify
  compilation shows "Skipped"
- `test_glass_yellow_zone` — mock yellow zone, verify output contains
  "requires confirmation"
- `test_ratchet_announcement_once` — verify Ratchet announcement fires
  on first cache hit, not on second

**Handlers:**
- `test_show_file_valid_target` — show_file with "config/routing.config"
  returns file contents
- `test_show_file_path_traversal` — show_file with "../engine/pipeline.py"
  returns access denied error
- `test_show_file_nonexistent` — show_file with nonexistent path returns
  graceful empty message
- `test_show_engine_manifest` — returns correct file list with line counts

**Tips engine:**
- `test_tip_fires_on_matching_trigger` — after_intent trigger matches
  correct intent
- `test_tip_fires_once` — same trigger condition doesn't repeat
- `test_tips_disabled` — when display.tips=False, no tips returned
- `test_no_tips_file` — missing tips.yaml produces no errors, no tips

**Integration (profile isolation):**
- `test_engine_unchanged` — run_pipeline with reference profile produces
  same PipelineContext structure as with blank_template for identical input
- `test_coach_demo_unaffected` — coach_demo loads and runs without any
  change in behavior

**Build Gate F:**
```bash
python -m pytest tests/test_reference_profile.py -v
# All new tests pass

python -m pytest tests/ -v
# ALL tests pass — zero regressions
```

---

## FINAL VERIFICATION

After all epics are complete, run this full acceptance script:

```bash
# 1. All tests pass
python -m pytest tests/ -v

# 2. All three profiles load
python autonomaton.py --list-profiles
# Expected: blank_template, coach_demo, reference

# 3. Coach demo is unchanged
python autonomaton.py --profile coach_demo --skip-welcome --skip-queue
# Type "hello" → normal response, NO glass pipeline
# Type "exit"

# 4. Glass flag works cross-profile
python autonomaton.py --profile coach_demo --glass --skip-welcome --skip-queue
# Type "hello" → glass pipeline annotations appear
# Type "exit"

# 5. Reference profile full OOB flow
python autonomaton.py --profile reference
# Banner: "Glass Pipeline: ACTIVE" + intro block
# Step through the designed first-five-minutes flow:
#   hello → glass + tip
#   ambiguous input → glass with LLM + cost + tip
#   same input → glass with cache HIT + Ratchet announcement + tip
#   show cache → glass + cache contents + tip
#   clear cache → glass + Jidoka + tip
#   show telemetry → glass + telemetry log + tip
#   show engine → glass + manifest + tip
#   exit
```

**If any step fails:** Check the DEVLOG, fix, and re-run from the failed
epic's build gate. Do not proceed past a failed gate.

---

## TROUBLESHOOTING

**"Module not found" on glass import:**
Make sure `engine/glass.py` exists and has no syntax errors. Run
`python -c "from engine.glass import display_glass_pipeline"` to test.

**Handler not dispatching:**
Verify the handler is registered in `dispatcher.py` with the exact string
name used in `routing.config`. Common mistake: registering as `"show-file"`
when config says `"show_file"`.

**Tips not appearing:**
Check that `config/tips.yaml` loads correctly:
`python -c "import yaml; print(yaml.safe_load(open('profiles/reference/config/tips.yaml')))"`.
Verify `profile.yaml` has `display.tips: true`.

**Glass pipeline not rendering:**
Verify `profile.yaml` has `display.glass_pipeline: true`. Check that
the glass display call is placed BEFORE `display_result()` in the REPL
loop (so it appears above the handler response).

**Pattern cache not writing (Ratchet not turning):**
The Ratchet write path is in `pipeline.py._write_to_pattern_cache()`.
It only fires for tier >= 2 classifications that are approved AND executed.
If the handler fails (e.g., empty dock), `context.executed` may be False.
Check that the handler returns `success=True` even with empty dock context.

**Path traversal test failing:**
`pathlib.Path.resolve()` behavior differs on Windows vs Unix. Test with
both forward and back slashes: `../engine/pipeline.py` and
`..\engine\pipeline.py`.


---

## REMINDERS

Before starting each epic, re-read:
- `CLAUDE.md` — The 12 invariants. Especially #1 (pipeline), #2 (config
  over code), #4 (Digital Jidoka), #10 (profile isolation).
- The relevant section of `SPEC.md` and `SPRINTS.md` for that epic.

**The engine does not change.** New behavior comes from:
- New config files (profile.yaml, tips.yaml)
- New handlers registered in dispatcher (show_file, show_engine_manifest)
- New presentation module (engine/glass.py)
- Modified REPL layer (autonomaton.py)

**The pipeline is invariant.** Glass observes it. Glass does not modify it.

**The lodestar applies.** "Design is philosophy expressed through constraint."
If the reference demo explains the pattern through prose instead of
demonstrating it through structure, it's not done.

---

*End of execution prompt. Start with Epic A. Run the build gate after
each epic. Do not skip gates.*
