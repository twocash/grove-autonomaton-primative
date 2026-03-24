"""
dispatcher.py - Action Dispatch and Execution Coordinator

Maps classified intents to execution handlers.
All handlers return standardized results for pipeline integration.

Architectural Invariants Enforced:
- #1 Invariant Pipeline: Handlers only execute during Stage 5
- #2 Config Over Code: Handler mapping driven by routing.config
- #5 Feed-First Telemetry: Execution results logged after completion
- #10 Profile Isolation: Domain handlers live in profiles/

V-012: Engine-core handlers only. Domain handlers load from profile.
"""

from dataclasses import dataclass
from typing import Any, Optional, Callable
from pathlib import Path

from engine.cognitive_router import RoutingResult


@dataclass
class DispatchResult:
    """
    Result of dispatched action.

    Provides standardized output format for pipeline Stage 5.
    """
    success: bool
    message: str
    data: Any = None
    requires_approval: bool = False
    approval_context: Optional[str] = None


class Dispatcher:
    """
    Maps classified intents to execution handlers.

    Engine-Core Handlers (11):
    - status_display: dock, queue, skills display (Green Zone)
    - general_chat: conversational responses (Green Zone)
    - strategy_session: strategic synthesis (Green Zone)
    - clear_cache: pattern cache management (Yellow Zone)
    - show_file: display profile files (Green Zone)
    - show_engine_manifest: display engine structure (Green Zone)
    - show_patterns: display Flywheel DETECT patterns (Green Zone)
    - propose_skills: generate Flywheel PROPOSE proposals (Green Zone)
    - show_proposals: display pending proposals (Green Zone)
    - skill_executor: run Pit Crew generated skills (Zone from config)
    - pit_crew: skill building (Red Zone)
    - mcp_formatter: MCP payload formatting (Yellow Zone)

    Domain handlers are registered by profile modules via register_handler().
    """

    def __init__(self):
        self._handlers: dict[str, Callable] = {}
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register engine-core handlers only."""
        self._handlers = {
            # Core display handlers
            "status_display": self._handle_status_display,
            "show_file": self._handle_show_file,
            "show_engine_manifest": self._handle_show_engine_manifest,
            "show_patterns": self._handle_show_patterns,
            # Flywheel handlers (V-016, V-019)
            "propose_skills": self._handle_propose_skills,
            "show_proposals": self._handle_show_proposals,
            "approve_skill": self._handle_approve_skill,  # V-019: Stage 4 APPROVE
            # Core execution handlers
            "general_chat": self._handle_general_chat,
            "strategy_session": self._handle_strategy_session,
            "skill_executor": self._handle_skill_executor,
            "pit_crew": self._handle_pit_crew,
            "mcp_formatter": self._handle_mcp_formatter,
            # Core system handlers
            "clear_cache": self._handle_clear_cache,
            "toggle_learning_mode": self._handle_toggle_learning_mode,  # V-018
        }

    def register_handler(self, name: str, handler: Callable) -> None:
        """
        Register a domain handler from a profile module.

        Called by profile handlers.py during startup.
        Enables profile-specific handlers without engine modification.

        Args:
            name: Handler name as referenced in routing.config
            handler: Callable following handler contract (RoutingResult, str) -> DispatchResult
        """
        self._handlers[name] = handler

    def dispatch(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Dispatch to appropriate handler based on routing result.

        Args:
            routing_result: Result from cognitive router
            raw_input: Original user input

        Returns:
            DispatchResult with execution outcome
        """
        handler_name = routing_result.handler

        if not handler_name:
            # No handler specified - pass-through execution
            return DispatchResult(
                success=True,
                message=f"Processed: {raw_input[:50]}..." if len(raw_input) > 50 else f"Processed: {raw_input}",
                data={"type": "passthrough"},
                requires_approval=False
            )

        handler = self._handlers.get(handler_name)

        if not handler:
            return DispatchResult(
                success=False,
                message=f"Unknown handler: {handler_name}",
                data={"type": "error", "error": "unknown_handler"}
            )

        return handler(routing_result, raw_input)

    # =========================================================================
    # Engine-Core Handler Implementations
    # =========================================================================

    def _handle_status_display(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Handle status display requests (dock, queue, skills).

        Green Zone - no approval required.
        """
        display_type = routing_result.handler_args.get("display_type", "unknown")

        if display_type == "dock":
            return self._display_dock()
        elif display_type == "queue":
            return self._display_queue()
        elif display_type == "skills":
            return self._display_skills()
        else:
            return DispatchResult(
                success=False,
                message=f"Unknown display type: {display_type}",
                data={"type": "error", "error": "unknown_display_type"}
            )

    def _display_dock(self) -> DispatchResult:
        """Display dock status."""
        from engine.dock import get_dock

        dock = get_dock()
        sources = dock.list_sources()
        source_names = [Path(s).name for s in sources]

        return DispatchResult(
            success=True,
            message="Dock status retrieved",
            data={
                "type": "dock_status",
                "chunks": dock.get_chunk_count(),
                "sources": source_names
            }
        )

    def _display_queue(self) -> DispatchResult:
        """Display Kaizen queue status.

        Queue is read from YAML if it exists.
        """
        import yaml
        from engine.profile import get_profile_path

        pending = []
        queue_path = get_profile_path() / "queue" / "kaizen.yaml"
        if queue_path.exists():
            try:
                with open(queue_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                pending = data.get("pending", [])
            except Exception:
                pass

        return DispatchResult(
            success=True,
            message="Queue status retrieved",
            data={
                "type": "queue_status",
                "count": len(pending),
                "items": [
                    {
                        "trigger": item.get("trigger", "?"),
                        "proposal": item.get("proposal", "?")[:50]
                    }
                    for item in pending
                ]
            }
        )

    def _display_skills(self) -> DispatchResult:
        """Display deployed skills."""
        from engine.pit_crew import list_deployed_skills

        skills = list_deployed_skills()

        return DispatchResult(
            success=True,
            message="Skills list retrieved",
            data={
                "type": "skills_list",
                "count": len(skills),
                "skills": skills
            }
        )

    def _handle_pit_crew(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Handle pit crew operations (skill building).

        Red Zone - requires explicit approval with context.
        Pipeline-compliant: no operator prompts.
        """
        action = routing_result.handler_args.get("action", "build")

        if action == "build":
            skill_name = routing_result.extracted_args.get("skill_name", "")
            description = routing_result.extracted_args.get("description", "")

            if not skill_name:
                return DispatchResult(
                    success=False,
                    message="Usage: build skill [name] [description]\n"
                            "Example: build skill weekly-report generates a weekly summary from telemetry",
                    data={"type": "pit_crew_usage"}
                )

            if not description:
                return DispatchResult(
                    success=False,
                    message="Usage: build skill [name] [description]\n"
                            "Example: build skill weekly-report generates a weekly summary from telemetry\n\n"
                            f"Got skill name '{skill_name}' but missing description.",
                    data={"type": "pit_crew_usage"}
                )

            # All arguments present — proceed with build
            from engine.pit_crew import build_skill
            result = build_skill(skill_name, description)

            return DispatchResult(
                success=result.get("success", False),
                message=result.get("message", "Skill build complete"),
                data={
                    "type": "pit_crew_build",
                    "skill_name": skill_name,
                    "description": description,
                    "result": result
                }
            )

        return DispatchResult(
            success=False,
            message=f"Unknown pit crew action: {action}",
            data={"type": "error", "error": "unknown_action"}
        )

    def _handle_skill_executor(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Handle execution of Pit Crew generated skills.

        Sprint 4: Executes skills created by the Pit Crew.
        Reads the prompt.md from the skill directory and
        sends it to the LLM with the user's input.
        """
        from engine.llm_client import call_llm
        from engine.profile import get_skills_dir

        skill_name = routing_result.handler_args.get("skill_name", "")

        if not skill_name:
            return DispatchResult(
                success=False,
                message="No skill name specified",
                data={"type": "skill_error", "error": "missing_skill_name"}
            )

        # Load the skill's prompt template
        skill_dir = get_skills_dir() / skill_name
        prompt_path = skill_dir / "prompt.md"

        if not prompt_path.exists():
            return DispatchResult(
                success=False,
                message=f"Skill prompt not found: {skill_name}",
                data={"type": "skill_error", "error": "prompt_not_found", "skill_name": skill_name}
            )

        try:
            prompt_template = prompt_path.read_text(encoding="utf-8")
        except Exception as e:
            return DispatchResult(
                success=False,
                message=f"Failed to read skill prompt: {e}",
                data={"type": "skill_error", "error": "read_failed"}
            )

        # Build the execution prompt with persona + standing context
        from engine.config_loader import get_persona
        persona = get_persona()
        system_prompt = persona.build_system_prompt(
            task_context=f"Executing skill: {skill_name}",
            include_state=True
        )

        execution_prompt = f"""{prompt_template}

---

USER REQUEST: {raw_input}

Please execute the skill based on the above instructions and user request.
"""

        try:
            response = call_llm(
                prompt=execution_prompt,
                system=system_prompt,
                tier=routing_result.tier,  # Tier from routing.config
                intent=f"skill_execution:{skill_name}"
            )

            return DispatchResult(
                success=True,
                message=f"Skill '{skill_name}' executed successfully",
                data={
                    "type": "skill_execution",
                    "skill_name": skill_name,
                    "response": response
                }
            )

        except Exception as e:
            return DispatchResult(
                success=False,
                message=f"Skill execution failed: {e}",
                data={"type": "skill_error", "error": str(e), "skill_name": skill_name}
            )

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

    def _handle_general_chat(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Handle conversational greetings and informational queries.

        Sprint ux-polish-v1: Dock-aware handler. If Compilation loaded dock
        context (intent_type=informational), include it in the prompt.
        Otherwise, respond conversationally.

        Green Zone - Persona responds according to config/persona.yaml.
        Uses Tier 1 (Haiku) for low latency responses.

        Implements Invariant #2: Config Over Code - persona loaded from YAML.
        """
        from engine.llm_client import call_llm
        from engine.config_loader import get_persona
        from engine.dock import query_dock

        # Load persona from config
        persona = get_persona()

        # Query dock for relevant context (Approach 2 from ux-polish-v1)
        dock_context = query_dock(raw_input, top_k=2)

        # Build task context based on whether dock has relevant content
        if dock_context and dock_context.strip():
            task_context = f"""The user is asking a question. Use the following
reference material to inform your response. Be conversational but
knowledgeable. If the reference material answers their question,
synthesize it naturally — don't quote it back verbatim.

Reference material:
{dock_context[:2000]}"""
        else:
            task_context = """The user is saying hello or making casual conversation.
Respond naturally and briefly. You're aware of the context but don't dump it —
reference it naturally if relevant."""

        system_prompt = persona.build_system_prompt(task_context, include_state=True)

        prompt = f"""User: {raw_input}

Respond (1-2 sentences only):"""

        try:
            response = call_llm(
                prompt=prompt,
                system=system_prompt,
                tier=routing_result.tier,  # Use tier from routing config
                intent="general_chat"
            )

            return DispatchResult(
                success=True,
                message=response.strip(),
                data={
                    "type": "general_chat",
                    "response": response.strip()
                }
            )

        except Exception as e:
            from engine.telemetry import log_event
            log_event(
                source="dispatcher",
                raw_transcript=raw_input[:200],
                zone_context="yellow",
                intent="general_chat",
                inferred={"error": str(e), "error_type": type(e).__name__,
                          "handler": "general_chat", "fallback": True, "stage": "handler_error"}
            )
            # Fallback response if LLM fails - use persona name
            fallback_msg = f"{persona.name} here. What do you need?"
            return DispatchResult(
                success=True,  # Still success - we have a usable response
                message=fallback_msg,
                data={
                    "type": "general_chat",
                    "response": fallback_msg,
                    "fallback": True
                }
            )

    def _handle_strategy_session(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Chief of Staff strategic synthesis.

        The persona carries the standing context. This handler asks it
        to synthesize what matters right now.

        Green Zone — advisory, no side effects.
        Uses tier from routing_result for appropriate quality level.
        """
        from engine.llm_client import call_llm
        from engine.config_loader import get_persona
        from engine.telemetry import log_event

        persona = get_persona()

        task_context = (
            "The operator is asking what to focus on right now. "
            "Synthesize the standing context into 3-5 prioritized action items. "
            "Lead with urgency (dates, deadlines). Be specific (names, numbers). "
            "For each item, suggest what the operator can say to start working on it. "
            "Sound like a colleague briefing them over coffee, not a dashboard."
        )

        system_prompt = persona.build_system_prompt(
            task_context=task_context,
            include_state=True  # THE ARCHITECTURAL FIX
        )

        prompt = f"""Operator: {raw_input}

Generate a focused strategic brief (3-5 items, natural language):"""

        try:
            response = call_llm(
                prompt=prompt,
                system=system_prompt,
                tier=routing_result.tier,  # Use tier from routing config
                intent="strategy_session"
            )

            return DispatchResult(
                success=True,
                message=response.strip(),
                data={"type": "strategy_session", "response": response.strip()}
            )

        except Exception as e:
            log_event(
                source="dispatcher",
                raw_transcript=raw_input[:200],
                zone_context="yellow",
                intent="strategy_session",
                inferred={"error": str(e), "handler": "strategy_session", "stage": "handler_error"}
            )
            return DispatchResult(
                success=False,
                message=f"Strategic briefing failed: {str(e)}",
                data={"type": "strategy_session", "error": str(e)}
            )

    def _handle_clear_cache(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Clear the pattern cache. Yellow Zone — modifies system behavior.

        The pattern cache stores confirmed LLM classifications for Tier 0 lookup.
        Clearing it resets the Ratchet - all classifications revert to LLM.
        """
        import yaml
        from engine.profile import get_config_dir

        cache_path = get_config_dir() / "pattern_cache.yaml"

        if not cache_path.exists():
            return DispatchResult(
                success=True,
                message="Pattern cache is already empty.",
                data={"type": "cache_clear", "entries_cleared": 0}
            )

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            count = len(data.get("cache", {}))
            data["cache"] = {}
            with open(cache_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)

            # Reset router cache
            from engine.cognitive_router import get_router
            router = get_router()
            if hasattr(router, 'pattern_cache'):
                router.pattern_cache = {}

            return DispatchResult(
                success=True,
                message=f"Pattern cache cleared. {count} entries removed.",
                data={"type": "cache_clear", "entries_cleared": count}
            )
        except Exception as e:
            return DispatchResult(
                success=False,
                message=f"Failed to clear cache: {e}",
                data={"type": "cache_clear", "error": str(e)}
            )

    def _handle_toggle_learning_mode(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Toggle Learning Mode (semantic enrichment).

        V-018: Learning Mode enables Haiku-based semantic annotation on
        keyword matches. This accelerates Flywheel pattern detection at
        ~$0.0004/turn. Toggle is Yellow Zone — affects session behavior.

        handler_args:
            enable: True to enable Learning Mode, False to disable (Free Mode)
        """
        from engine.profile import set_session_enrichment, get_session_enrichment
        from engine.llm_client import estimate_turn_cost

        enable = routing_result.handler_args.get("enable", True)
        set_session_enrichment(enable)

        if enable:
            cost = estimate_turn_cost(1)
            return DispatchResult(
                success=True,
                message=(
                    f"Learning Mode enabled.\n"
                    f"  Semantic enrichment via Haiku (~${cost:.4f}/turn).\n"
                    f"  Faster Flywheel pattern detection. The system learns as you use it."
                ),
                data={"type": "learning_mode", "enabled": True}
            )
        else:
            return DispatchResult(
                success=True,
                message=(
                    "Learning Mode disabled. Back to Free Mode.\n"
                    "  No per-turn cost. Keyword matching only."
                ),
                data={"type": "learning_mode", "enabled": False}
            )

    # =========================================================================
    # Reference Profile Handlers (Sprint: reference-profile-v1)
    # =========================================================================

    def _handle_show_file(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Display contents of a profile config file.

        Security: validates target path is within profile directory.
        """
        from engine.profile import get_profile_path

        target = routing_result.handler_args.get("target", "")
        tail = routing_result.handler_args.get("tail", None)

        if not target:
            return DispatchResult(
                success=False,
                message="No target file specified",
                data={"type": "file_display", "error": "no_target"}
            )

        profile_dir = get_profile_path()
        target_path = (profile_dir / target).resolve()

        # SECURITY: Reject path traversal
        if not str(target_path).startswith(str(profile_dir.resolve())):
            return DispatchResult(
                success=False,
                message=f"Access denied: {target} is outside the profile directory",
                data={"type": "file_display", "error": "path_traversal"}
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

    def _handle_show_engine_manifest(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """Display engine source file manifest with line counts."""
        engine_dir = Path(__file__).parent

        manifest_lines = []
        total_lines = 0

        # Core engine files in display order
        engine_files = [
            "pipeline.py",
            "cognitive_router.py",
            "dispatcher.py",
            "telemetry.py",
            "ux.py",
            "compiler.py",
            "dock.py",
            "llm_client.py",
            "config_loader.py",
            "profile.py",
            "glass.py",
        ]

        for filename in engine_files:
            filepath = engine_dir / filename
            if filepath.exists():
                line_count = len(filepath.read_text(encoding="utf-8").splitlines())
                total_lines += line_count
                desc = self._extract_module_description(filepath)
                manifest_lines.append(
                    f"  {filename:<24} {line_count:>4} lines   {desc}"
                )

        # Add entry point
        entry_point = engine_dir.parent / "autonomaton.py"
        ep_lines = 0
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
            success=True,
            message=output,
            data={"type": "engine_manifest"}
        )

    def _extract_module_description(self, filepath: Path) -> str:
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

    def _handle_show_patterns(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Display detected Flywheel patterns.

        Flywheel Stage 2 (DETECT): reads telemetry, groups by
        pattern_hash, surfaces candidates meeting threshold.

        White Paper Part III S3: "Same intent pattern 3+ times in
        14 days -> surface as potential skill."
        """
        from engine.flywheel import detect_patterns

        patterns = detect_patterns()

        if not patterns:
            return DispatchResult(
                success=True,
                message="No patterns detected yet. Use the system - the Flywheel observes every interaction.",
                data={"type": "flywheel_patterns", "patterns": []}
            )

        # Format output
        lines = []
        candidates = [p for p in patterns if p["is_candidate"]]
        others = [p for p in patterns if not p["is_candidate"]]

        if candidates:
            lines.append(f"  SKILL CANDIDATES ({len(candidates)} patterns meet threshold):")
            lines.append("")
            for p in candidates:
                label = p["pattern_label"] or p["intent"]
                lines.append(f"    * {label}  [{p['pattern_hash']}]")
                lines.append(f"      {p['count']}x in window | intent: {p['intent']} | domain: {p['domain']}")
                if p["sample_inputs"]:
                    lines.append(f"      samples: {p['sample_inputs'][0]}")
                    if len(p["sample_inputs"]) > 1:
                        lines.append(f"               {p['sample_inputs'][1]}")
                lines.append("")

        if others:
            lines.append(f"  OBSERVED ({len(others)} patterns below threshold):")
            lines.append("")
            for p in others[:10]:  # Cap display
                label = p["pattern_label"] or p["intent"]
                lines.append(f"    . {label}  {p['count']}x | {p['intent']}")

        # V-016: Hint to generate proposals when candidates exist
        if candidates:
            lines.append("")
            lines.append(f"  {len(candidates)} pattern(s) meet the skill candidate threshold.")
            lines.append("  Type 'propose skills' to generate proposals.")

        return DispatchResult(
            success=True,
            message="\n".join(lines),
            data={"type": "flywheel_patterns", "patterns": patterns}
        )

    def _handle_propose_skills(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Generate Flywheel skill proposals from detected patterns.

        Flywheel Stage 3 (PROPOSE): reads candidates from DETECT,
        generates structured YAML proposals for human review.

        Green Zone — proposals are inert documents until approved.
        Tier 0 — no LLM, purely deterministic assembly.
        """
        from engine.flywheel import propose_skills

        proposals = propose_skills()

        if not proposals:
            # Check if there are candidates but all already proposed
            from engine.flywheel import detect_patterns, load_proposals
            patterns = detect_patterns()
            candidates = [p for p in patterns if p.get("is_candidate")]
            existing = load_proposals()

            if not candidates:
                return DispatchResult(
                    success=True,
                    message="No patterns meet the skill candidate threshold yet.\n"
                            "Use the system — the Flywheel observes every interaction.",
                    data={"type": "flywheel_propose", "proposals": []}
                )
            else:
                return DispatchResult(
                    success=True,
                    message=f"All {len(candidates)} candidate(s) already have pending proposals.\n"
                            f"Type 'show proposals' to review them.",
                    data={"type": "flywheel_propose", "proposals": [], "existing": len(existing)}
                )

        # Format output
        lines = [f"  {len(proposals)} new proposal(s) generated:"]
        lines.append("")
        for p in proposals:
            lines.append(f"    * {p['name']}")
            lines.append(f"      {p['description']}")
            lines.append(f"      File: queue/flywheel/{p['file']}")
            lines.append("")

        lines.append("  Type 'show proposals' to review.")

        return DispatchResult(
            success=True,
            message="\n".join(lines),
            data={"type": "flywheel_propose", "proposals": proposals}
        )

    def _handle_show_proposals(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Display pending Flywheel skill proposals.

        Reads YAML files from queue/flywheel/ and formats for display.
        Green Zone — purely informational.
        """
        from engine.flywheel import load_proposals

        proposals = load_proposals()

        if not proposals:
            return DispatchResult(
                success=True,
                message="No pending proposals.\n"
                        "Type 'propose skills' to generate proposals from detected patterns.",
                data={"type": "flywheel_proposals", "proposals": []}
            )

        # Format output
        lines = [f"  PENDING PROPOSALS ({len(proposals)}):"]
        lines.append("")

        for p in proposals:
            data = p.get("data", {})
            skill = data.get("skill", {})
            trigger = skill.get("trigger", {})
            provenance = skill.get("provenance", {})
            response = skill.get("response", {})

            lines.append(f"  ── {p['name']} ──")
            lines.append(f"  {skill.get('description', '')}")
            lines.append("")
            lines.append(f"    Pattern: {trigger.get('pattern_hash', '')[:12]}...")
            if trigger.get("pattern_label"):
                lines.append(f"    Label: {trigger.get('pattern_label')}")
            lines.append(f"    Occurrences: {provenance.get('occurrences', 0)}")
            lines.append(f"    First seen: {provenance.get('first_seen', '')[:10]}")
            lines.append(f"    Last seen: {provenance.get('last_seen', '')[:10]}")
            lines.append(f"    Zone: {response.get('zone', 'green')} | Tier: {response.get('tier', 0)}")

            examples = trigger.get("example_inputs", [])
            if examples:
                lines.append("    Examples:")
                for ex in examples[:3]:
                    lines.append(f"      - \"{ex}\"")

            lines.append(f"    File: {p['file']}")
            lines.append("")

        # V-019: Show approval command for each proposal
        lines.append("  To approve a proposal:")
        for p in proposals:
            ph = p.get("pattern_hash", "")[:12]
            lines.append(f"    → approve skill {ph}")

        return DispatchResult(
            success=True,
            message="\n".join(lines),
            data={"type": "flywheel_proposals", "proposals": proposals}
        )

    def _handle_approve_skill(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Approve a Flywheel skill proposal. Yellow-zone.

        V-019: Flywheel Stage 4 (APPROVE). By the time this handler
        executes, Stage 4 has already obtained operator confirmation.
        The handler is a dumb pipe. Governance lives in the pipeline.

        If no pattern_hash provided, lists available proposals.
        If pattern_hash provided, calls approve_skill() from flywheel.
        """
        from engine.flywheel import approve_skill, load_proposals

        # Get pattern_hash from extracted_args
        pattern_hash = routing_result.extracted_args.get("pattern_hash", "").strip()

        if not pattern_hash:
            # No hash provided — show available proposals
            proposals = load_proposals()

            if not proposals:
                return DispatchResult(
                    success=True,
                    message="No pending proposals to approve.\n"
                            "Type 'propose skills' to generate proposals from detected patterns.",
                    data={"type": "approve_skill", "action": "list_empty"}
                )

            lines = ["Usage: approve skill <pattern_hash>", ""]
            lines.append("Available proposals:")
            for p in proposals:
                ph = p.get("pattern_hash", "")[:12]
                name = p.get("name", "unknown")
                lines.append(f"  {ph}  {name}")

            return DispatchResult(
                success=True,
                message="\n".join(lines),
                data={"type": "approve_skill", "action": "list", "proposals": proposals}
            )

        # Hash provided — execute approval
        result = approve_skill(pattern_hash)

        if result.get("approved"):
            return DispatchResult(
                success=True,
                message=(
                    f"Skill '{result['skill_name']}' approved.\n"
                    f"  {result['entries_written']} input(s) deployed to pattern cache.\n"
                    f"  Resolves at Tier 0 from now on."
                ),
                data={"type": "approve_skill", "action": "approved", "result": result}
            )
        else:
            return DispatchResult(
                success=False,
                message=f"Approval failed: {result.get('error', 'Unknown error')}",
                data={"type": "approve_skill", "action": "failed", "result": result}
            )


# =========================================================================
# Module-level Singleton and Interface
# =========================================================================

_dispatcher_instance: Optional[Dispatcher] = None


def get_dispatcher() -> Dispatcher:
    """Get the shared Dispatcher instance."""
    global _dispatcher_instance
    if _dispatcher_instance is None:
        _dispatcher_instance = Dispatcher()
    return _dispatcher_instance


def reset_dispatcher() -> None:
    """Reset the dispatcher instance. Used for testing and profile reloads."""
    global _dispatcher_instance
    _dispatcher_instance = None


def dispatch_action(
    routing_result: RoutingResult,
    raw_input: str
) -> DispatchResult:
    """
    Dispatch action based on routing result.

    This is the primary interface for pipeline integration.

    Args:
        routing_result: Result from cognitive router
        raw_input: Original user input

    Returns:
        DispatchResult with execution outcome
    """
    dispatcher = get_dispatcher()
    return dispatcher.dispatch(routing_result, raw_input)
