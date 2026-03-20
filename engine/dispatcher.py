"""
dispatcher.py - Action Dispatch and Execution Coordinator

Maps classified intents to execution handlers.
All handlers return standardized results for pipeline integration.

Architectural Invariants Enforced:
- #1 Invariant Pipeline: Handlers only execute during Stage 5
- #2 Config Over Code: Handler mapping driven by routing.config
- #5 Feed-First Telemetry: Execution results logged after completion
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

    Handler Registry:
    - status_display: dock, queue, skills display (Green Zone)
    - content_engine: content compilation (Yellow Zone)
    - pit_crew: skill building (Red Zone)

    Handlers are registered at initialization and looked up by name
    from the routing.config handler field.
    """

    def __init__(self):
        self._handlers: dict[str, Callable] = {}
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register all available handlers."""
        self._handlers = {
            "status_display": self._handle_status_display,
            "content_engine": self._handle_content_engine,
            "pit_crew": self._handle_pit_crew,
            "session_zero_handler": self._handle_session_zero,
            "mcp_formatter": self._handle_mcp_formatter,
            "skill_executor": self._handle_skill_executor,
            "cortex_batch": self._handle_cortex_batch,
            "vision_capture": self._handle_vision_capture,
            "general_chat": self._handle_general_chat,
            "strategy_session": self._handle_strategy_session,
            "plan_update": self._handle_plan_update,
            "regenerate_plan": self._handle_regenerate_plan,
            "fill_entity_gap": self._handle_fill_entity_gap,
            "ratchet_interpreter": self._handle_ratchet_interpreter,
            # Internal startup handlers (purity-audit-v1)
            "welcome_card": self._handle_welcome_card,
            "startup_brief": self._handle_startup_brief,
            "generate_plan": self._handle_generate_plan,
            "clear_cache": self._handle_clear_cache,
            # Reference profile handlers (reference-profile-v1)
            "show_file": self._handle_show_file,
            "show_engine_manifest": self._handle_show_engine_manifest,
        }

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
    # Handler Implementations
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
        """Display Kaizen queue status."""
        from engine.cortex import load_pending_queue

        pending = load_pending_queue()

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

    def _handle_content_engine(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Handle content engine operations.

        Yellow Zone - requires approval (handled by pipeline Stage 4).
        """
        action = routing_result.handler_args.get("action", "compile")

        if action == "compile":
            from engine.content_engine import compile_content, format_for_approval

            drafts = compile_content()

            if not drafts:
                return DispatchResult(
                    success=True,
                    message="No content seeds found",
                    data={"type": "content_compilation", "drafts": [], "draft_count": 0}
                )

            # Format for approval display
            approval_text = format_for_approval(drafts)

            return DispatchResult(
                success=True,
                message=f"Compiled {len(drafts)} draft(s)",
                data={
                    "type": "content_compilation",
                    "drafts": drafts,
                    "draft_count": len(drafts)
                },
                requires_approval=True,
                approval_context=approval_text
            )

        return DispatchResult(
            success=False,
            message=f"Unknown content action: {action}",
            data={"type": "error", "error": "unknown_action"}
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

    def _handle_session_zero(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Handle Session Zero intake skill.

        Yellow Zone - requires approval before execution.
        Until Sprint 2 (LLM client), this handler reads the prompt.md
        from the skill directory and returns its contents as proof of wiring.
        """
        from engine.profile import get_skills_dir

        skill_name = routing_result.handler_args.get("skill_name", "session-zero-intake")
        skill_path = get_skills_dir() / skill_name
        prompt_path = skill_path / "prompt.md"

        if not prompt_path.exists():
            return DispatchResult(
                success=False,
                message=f"Skill prompt not found: {prompt_path}",
                data={
                    "type": "session_zero",
                    "error": "prompt_not_found",
                    "skill_path": str(skill_path)
                }
            )

        # Read the prompt template
        try:
            prompt_content = prompt_path.read_text(encoding="utf-8")
        except Exception as e:
            return DispatchResult(
                success=False,
                message=f"Failed to read prompt: {e}",
                data={
                    "type": "session_zero",
                    "error": "read_failed"
                }
            )

        # Return the prompt content
        # Sprint 2: This will be sent to the LLM client for interactive session
        return DispatchResult(
            success=True,
            message="Session Zero intake ready",
            data={
                "type": "session_zero",
                "skill_name": skill_name,
                "prompt_content": prompt_content,
                "note": "Sprint 2 will integrate LLM client for interactive session"
            }
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
                tier=2,  # Use Sonnet for skill execution
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

    def _handle_cortex_batch(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Handle Cortex batch analysis operations (Lenses 3, 4, 5).

        Sprint 5: Evolutionary Cortex - batch-cycle analytical processes
        that analyze telemetry to propose improvements, demotions, and new skills.

        Yellow Zone - proposals require approval before implementation.
        """
        import json
        from engine.cortex import Cortex
        from engine.profile import get_telemetry_path, get_dock_dir

        lens = routing_result.handler_args.get("lens", "unknown")
        cortex = Cortex()

        if lens == "pattern_analysis":
            # Lens 3: Pattern Analysis
            telemetry_events = self._load_recent_telemetry(limit=50)

            result = cortex.run_pattern_analysis(telemetry_events)

            patterns_count = len(result.get("patterns_detected", []))
            proposals_count = len(result.get("kaizen_proposals", []))

            return DispatchResult(
                success=True,
                message=f"Pattern analysis complete: {patterns_count} patterns, {proposals_count} proposals",
                data={
                    "type": "cortex_pattern_analysis",
                    "lens": "pattern_analysis",
                    "patterns_detected": result.get("patterns_detected", []),
                    "kaizen_proposals": result.get("kaizen_proposals", [])
                },
                requires_approval=proposals_count > 0,
                approval_context=self._format_kaizen_proposals(result.get("kaizen_proposals", []))
            )

        elif lens == "ratchet_analysis":
            # Lens 4: Ratchet Analysis
            llm_telemetry = self._load_llm_telemetry(limit=100)
            routing_patterns = self._aggregate_routing_patterns()

            result = cortex.run_ratchet_analysis(llm_telemetry, routing_patterns)

            proposals_count = len(result.get("ratchet_proposals", []))
            savings = result.get("total_potential_savings", "$0.00/month")

            return DispatchResult(
                success=True,
                message=f"Ratchet analysis complete: {proposals_count} demotions proposed, {savings} potential savings",
                data={
                    "type": "cortex_ratchet_analysis",
                    "lens": "ratchet_analysis",
                    "ratchet_proposals": result.get("ratchet_proposals", []),
                    "total_potential_savings": savings
                },
                requires_approval=proposals_count > 0,
                approval_context=self._format_ratchet_proposals(result.get("ratchet_proposals", []))
            )

        elif lens == "evolution_analysis":
            # Lens 5: Evolution / Personal Product Manager
            telemetry_events = self._load_recent_telemetry(limit=50)
            exhaust_board = self._load_exhaust_board()
            vision_board = self._load_vision_board()

            result = cortex.run_evolution_analysis(telemetry_events, exhaust_board, vision_board)

            proposals_count = len(result.get("evolution_proposals", []))

            return DispatchResult(
                success=True,
                message=f"Evolution analysis complete: {proposals_count} skill proposals",
                data={
                    "type": "cortex_evolution_analysis",
                    "lens": "evolution_analysis",
                    "evolution_proposals": result.get("evolution_proposals", [])
                },
                requires_approval=proposals_count > 0,
                approval_context=self._format_evolution_proposals(result.get("evolution_proposals", []))
            )

        else:
            return DispatchResult(
                success=False,
                message=f"Unknown cortex lens: {lens}",
                data={"type": "cortex_error", "error": "unknown_lens"}
            )

    def _load_recent_telemetry(self, limit: int = 50) -> list[dict]:
        """Load recent telemetry events for Cortex analysis."""
        import json
        from engine.profile import get_telemetry_path

        telemetry_path = get_telemetry_path()
        if not telemetry_path.exists():
            return []

        events = []
        try:
            with open(telemetry_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception:
            return []

        return events[-limit:]

    def _load_llm_telemetry(self, limit: int = 100) -> list[dict]:
        """Load LLM-specific telemetry for ratchet analysis."""
        # Filter telemetry for LLM calls
        all_events = self._load_recent_telemetry(limit=limit * 2)
        return [
            e for e in all_events
            if e.get("intent", "").startswith(("cortex_", "mcp_", "skill_"))
            or "model" in e
        ][-limit:]

    def _aggregate_routing_patterns(self) -> list[dict]:
        """Aggregate routing patterns for ratchet analysis."""
        from collections import defaultdict

        events = self._load_recent_telemetry(limit=500)

        # Aggregate by intent
        intent_stats = defaultdict(lambda: {"count": 0, "confidences": []})
        for event in events:
            intent = event.get("intent", "unknown")
            confidence = event.get("confidence", 0.5)
            intent_stats[intent]["count"] += 1
            intent_stats[intent]["confidences"].append(confidence)

        # Build aggregated patterns
        patterns = []
        for intent, stats in intent_stats.items():
            if stats["count"] > 0:
                avg_confidence = sum(stats["confidences"]) / len(stats["confidences"])
                patterns.append({
                    "intent": intent,
                    "confidence": round(avg_confidence, 2),
                    "count": stats["count"]
                })

        return sorted(patterns, key=lambda x: x["count"], reverse=True)

    def _load_exhaust_board(self) -> str:
        """Load the exhaust board content."""
        from engine.profile import get_dock_dir

        dock_dir = get_dock_dir()
        exhaust_path = dock_dir / "system" / "exhaust-board.md"

        if exhaust_path.exists():
            try:
                return exhaust_path.read_text(encoding="utf-8")
            except Exception:
                return "# Exhaust Board\n\nNo entries yet."
        return "# Exhaust Board\n\nNo entries yet."

    def _format_kaizen_proposals(self, proposals: list[dict]) -> str:
        """Format Kaizen proposals for approval display."""
        if not proposals:
            return "No Kaizen proposals."

        lines = ["KAIZEN PROPOSALS:"]
        for p in proposals:
            lines.append(f"  [{p.get('priority', '?').upper()}] {p.get('proposal', 'Unknown')}")
            lines.append(f"        Trigger: {p.get('trigger', '?')}")
        return "\n".join(lines)

    def _format_ratchet_proposals(self, proposals: list[dict]) -> str:
        """Format Ratchet proposals for approval display."""
        if not proposals:
            return "No Ratchet proposals."

        lines = ["RATCHET DEMOTIONS:"]
        for p in proposals:
            lines.append(f"  [{p.get('intent', '?')}] {p.get('proposed_action', 'Unknown')}")
            lines.append(f"        Confidence: {p.get('confidence', 0):.0%}, Samples: {p.get('sample_count', 0)}")
        return "\n".join(lines)

    def _format_evolution_proposals(self, proposals: list[dict]) -> str:
        """Format Evolution proposals for approval display."""
        if not proposals:
            return "No Evolution proposals."

        lines = ["SKILL PROPOSALS (Pit Crew Work Orders):"]
        for p in proposals:
            lines.append(f"  [{p.get('skill_name', '?')}] {p.get('description', 'Unknown')}")
            spec = p.get('spec', {})
            lines.append(f"        Zone: {spec.get('zone', '?')}, Tier: {spec.get('tier', '?')}")
            if p.get('pit_crew_ready'):
                lines.append("        Status: READY FOR PIT CREW")
        return "\n".join(lines)

    def _handle_vision_capture(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Handle Vision Board capture (Sprint 6.5).

        Green Zone - no approval required.
        Appends user aspiration to vision-board.md for future Lens 5 consideration.
        """
        from datetime import datetime
        from engine.profile import get_dock_dir

        dock_dir = get_dock_dir()
        vision_board_path = dock_dir / "system" / "vision-board.md"

        # Ensure parent directory exists
        vision_board_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize if doesn't exist
        if not vision_board_path.exists():
            vision_board_path.write_text(
                "# Vision Board\n\n"
                "> *A scratchpad for aspirations and future automation ideas*\n\n"
                "---\n\n"
                "## Aspirations\n\n"
                "<!-- New aspirations are appended below automatically -->\n\n",
                encoding="utf-8"
            )

        # Format the aspiration entry
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"- [{timestamp}] {raw_input}\n"

        # Append to vision board
        try:
            with open(vision_board_path, "a", encoding="utf-8") as f:
                f.write(entry)

            return DispatchResult(
                success=True,
                message="Aspiration captured to Vision Board",
                data={
                    "type": "vision_capture",
                    "aspiration": raw_input,
                    "timestamp": timestamp
                }
            )

        except Exception as e:
            return DispatchResult(
                success=False,
                message=f"Failed to capture aspiration: {e}",
                data={"type": "vision_capture", "error": str(e)}
            )

    def _load_vision_board(self) -> str:
        """Load the vision board content for Lens 5."""
        from engine.profile import get_dock_dir

        dock_dir = get_dock_dir()
        vision_path = dock_dir / "system" / "vision-board.md"

        if vision_path.exists():
            try:
                return vision_path.read_text(encoding="utf-8")
            except Exception:
                return "# Vision Board\n\nNo entries yet."
        return "# Vision Board\n\nNo entries yet."

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

    def _handle_plan_update(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Handle structured plan updates (Sprint 5).

        Yellow Zone - requires approval before writing to dock.
        Accepts specific updates or suggestions to the structured plan.
        """
        from engine.llm_client import call_llm
        from engine.config_loader import get_persona
        from engine.compiler import get_structured_plan, write_structured_plan
        from engine.telemetry import log_event

        persona = get_persona()
        current_plan = get_structured_plan()

        if not current_plan:
            return DispatchResult(
                success=False,
                message="No structured plan exists. Use 'regenerate plan' to create one.",
                data={"type": "plan_update", "error": "no_plan"}
            )

        task_context = (
            "The operator wants to update the structured plan. "
            "Apply their requested changes while maintaining the plan's structure. "
            "Keep all existing sections but update the relevant content."
        )

        system_prompt = persona.build_system_prompt(
            task_context=task_context,
            include_state=True
        )

        prompt = f"""Current structured plan:
{current_plan}

---

Operator's requested update: {raw_input}

Apply the update and return the COMPLETE updated plan (not just the changes).
Maintain the markdown structure. Update the "Last updated" timestamp to today."""

        try:
            updated_plan = call_llm(
                prompt=prompt,
                system=system_prompt,
                tier=2,  # Sonnet for quality
                intent="plan_update"
            )

            # Write the updated plan
            if write_structured_plan(updated_plan.strip()):
                # Reset standing context to pick up changes
                from engine.compiler import reset_standing_context
                reset_standing_context()

                return DispatchResult(
                    success=True,
                    message="Structured plan updated successfully",
                    data={
                        "type": "plan_update",
                        "status": "updated"
                    }
                )
            else:
                return DispatchResult(
                    success=False,
                    message="Failed to write updated plan",
                    data={"type": "plan_update", "error": "write_failed"}
                )

        except Exception as e:
            log_event(
                source="dispatcher",
                raw_transcript=raw_input[:200],
                zone_context="yellow",
                intent="plan_update",
                inferred={"error": str(e), "handler": "plan_update", "stage": "handler_error"}
            )
            return DispatchResult(
                success=False,
                message=f"Plan update failed: {str(e)}",
                data={"type": "plan_update", "error": str(e)}
            )

    def _handle_regenerate_plan(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Handle full structured plan regeneration (Sprint 5).

        Yellow Zone - requires approval before writing to dock.
        Re-synthesizes the entire plan from current dock + telemetry state.
        """
        from engine.compiler import generate_structured_plan, write_structured_plan
        from engine.telemetry import log_event

        try:
            new_plan = generate_structured_plan()

            if not new_plan:
                return DispatchResult(
                    success=False,
                    message="Plan generation failed - check telemetry for details",
                    data={"type": "regenerate_plan", "error": "generation_failed"}
                )

            # Write the new plan
            if write_structured_plan(new_plan):
                # Reset standing context to pick up changes
                from engine.compiler import reset_standing_context
                reset_standing_context()

                return DispatchResult(
                    success=True,
                    message="Structured plan regenerated successfully",
                    data={
                        "type": "regenerate_plan",
                        "status": "regenerated"
                    }
                )
            else:
                return DispatchResult(
                    success=False,
                    message="Failed to write regenerated plan",
                    data={"type": "regenerate_plan", "error": "write_failed"}
                )

        except Exception as e:
            log_event(
                source="dispatcher",
                raw_transcript=raw_input[:200],
                zone_context="yellow",
                intent="regenerate_plan",
                inferred={"error": str(e), "handler": "regenerate_plan", "stage": "handler_error"}
            )
            return DispatchResult(
                success=False,
                message=f"Plan regeneration failed: {str(e)}",
                data={"type": "regenerate_plan", "error": str(e)}
            )

    def _handle_fill_entity_gap(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Handle entity gap filling (Sprint 5).

        Yellow Zone - requires approval before modifying entity files.
        Uses LLM to extract the entity name and field value from raw input,
        then updates the entity file.
        """
        import json
        import re
        from engine.llm_client import call_llm
        from engine.profile import get_entities_dir
        from engine.telemetry import log_event

        # Use LLM to extract entity and field info
        # Load entity types from config
        from engine.config_loader import load_entity_config
        entity_config = load_entity_config()
        entity_types = [t["plural"] for t in entity_config.get("entity_types", [])]
        entity_types_str = ", ".join(f'"{t}"' for t in entity_types) if entity_types else '"entities"'

        prompt = f"""Extract entity update information from this request.
Return JSON with:
- entity_type: One of {entity_types_str}
- entity_name: Name of the entity
- field_name: Field to add (e.g., "email", "phone")
- field_value: Value to set

Request: "{raw_input}"

Return ONLY valid JSON, no explanations:"""

        try:
            response = call_llm(
                prompt=prompt,
                tier=1,  # Haiku for extraction
                intent="entity_gap_extraction"
            )

            data = json.loads(response)
            entity_type = data.get("entity_type", "")
            entity_name = data.get("entity_name", "")
            field_name = data.get("field_name", "")
            field_value = data.get("field_value", "")

            if not all([entity_type, entity_name, field_name, field_value]):
                return DispatchResult(
                    success=False,
                    message="Could not extract entity update details. Try: 'add email for martinez family: email@example.com'",
                    data={"type": "fill_entity_gap", "error": "extraction_incomplete"}
                )

            # Find the entity file
            entities_dir = get_entities_dir()
            entity_dir = entities_dir / entity_type

            if not entity_dir.exists():
                return DispatchResult(
                    success=False,
                    message=f"Entity type not found: {entity_type}",
                    data={"type": "fill_entity_gap", "error": "type_not_found"}
                )

            # Normalize entity name for file lookup
            normalized_name = entity_name.lower().replace(" ", "-")
            entity_file = None

            for f in entity_dir.glob("*.md"):
                if normalized_name in f.stem.lower():
                    entity_file = f
                    break

            if not entity_file:
                return DispatchResult(
                    success=False,
                    message=f"Entity not found: {entity_name} in {entity_type}",
                    data={"type": "fill_entity_gap", "error": "entity_not_found"}
                )

            # Read current content
            content = entity_file.read_text(encoding="utf-8")

            # Add the new field after the Profile section
            field_line = f"- **{field_name}:** {field_value}"

            # Check if field already exists
            if f"**{field_name}:**" in content.lower():
                # Update existing field
                pattern = rf'(\*\*{re.escape(field_name)}:\*\*)\s*[^\n]*'
                content = re.sub(pattern, f"**{field_name}:** {field_value}", content, flags=re.IGNORECASE)
            else:
                # Add new field after ## Profile section
                if "## Profile" in content:
                    content = content.replace("## Profile\n", f"## Profile\n{field_line}\n", 1)
                elif "## Notes" in content:
                    content = content.replace("## Notes", f"{field_line}\n\n## Notes", 1)
                else:
                    content += f"\n{field_line}\n"

            # Write updated content
            entity_file.write_text(content, encoding="utf-8")

            # Reset standing context to pick up changes
            from engine.compiler import reset_standing_context
            reset_standing_context()

            return DispatchResult(
                success=True,
                message=f"Updated {entity_name}: added {field_name}",
                data={
                    "type": "fill_entity_gap",
                    "entity": f"{entity_type}/{entity_file.stem}",
                    "field": field_name,
                    "value": field_value
                }
            )

        except json.JSONDecodeError:
            return DispatchResult(
                success=False,
                message="Could not parse entity update request",
                data={"type": "fill_entity_gap", "error": "parse_failed"}
            )
        except Exception as e:
            log_event(
                source="dispatcher",
                raw_transcript=raw_input[:200],
                zone_context="yellow",
                intent="fill_entity_gap",
                inferred={"error": str(e), "handler": "fill_entity_gap", "stage": "handler_error"}
            )
            return DispatchResult(
                success=False,
                message=f"Entity update failed: {str(e)}",
                data={"type": "fill_entity_gap", "error": str(e)}
            )

    def _handle_ratchet_interpreter(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Generic ratchet classification interpreter (Sprint 6 - ADR-001).

        This handler reads a prompt template from config and executes
        LLM classification. It's the interpret layer for ratchet_classify().

        The handler_args specify:
        - classifier: Name of the classification task (for telemetry)
        - prompt_template: Name of the prompt template file

        Green Zone - classification doesn't modify state.
        Tier determined by routing.config entry.
        """
        import json
        from engine.llm_client import call_llm
        from engine.profile import get_config_dir
        from engine.telemetry import log_event

        classifier = routing_result.handler_args.get("classifier", "unknown")
        template_name = routing_result.handler_args.get("prompt_template", "")

        if not template_name:
            return DispatchResult(
                success=False,
                message=f"Ratchet interpreter missing prompt_template for {classifier}",
                data={"type": "ratchet_interpreter", "error": "missing_template"}
            )

        # Load prompt template from cognitive-router/prompts/
        config_dir = get_config_dir()
        template_path = config_dir / "cognitive-router" / "prompts" / f"{template_name}.md"

        if not template_path.exists():
            return DispatchResult(
                success=False,
                message=f"Prompt template not found: {template_name}",
                data={"type": "ratchet_interpreter", "error": "template_not_found"}
            )

        try:
            template_content = template_path.read_text(encoding="utf-8")
        except Exception as e:
            return DispatchResult(
                success=False,
                message=f"Failed to read prompt template: {e}",
                data={"type": "ratchet_interpreter", "error": "template_read_failed"}
            )

        # Build context for template substitution
        context = self._build_ratchet_context(classifier, raw_input)

        # Substitute placeholders in template
        prompt = template_content
        for key, value in context.items():
            placeholder = "{" + key + "}"
            if placeholder in prompt:
                prompt = prompt.replace(placeholder, str(value))

        # Determine tier from routing config
        tier = routing_result.tier if hasattr(routing_result, 'tier') else 1

        try:
            response = call_llm(
                prompt=prompt,
                tier=tier,
                intent=f"ratchet_{classifier}"
            )

            # Parse JSON response
            json_str = response.strip()
            start_idx = json_str.find('{')
            end_idx = json_str.rfind('}')
            if start_idx != -1 and end_idx != -1:
                json_str = json_str[start_idx:end_idx + 1]

            result = json.loads(json_str)

            # Extract classification from result based on classifier type
            classification = self._extract_classification(classifier, result)
            confidence = result.get("confidence", 0.5)

            return DispatchResult(
                success=True,
                message=f"Classification complete: {classifier}",
                data={
                    "type": "ratchet_interpreter",
                    "classifier": classifier,
                    "classification": classification,
                    "confidence": confidence,
                    "raw_result": result
                }
            )

        except json.JSONDecodeError as e:
            log_event(
                source="dispatcher",
                raw_transcript=raw_input[:200],
                zone_context="yellow",
                intent="ratchet_interpreter",
                inferred={
                    "error": str(e),
                    "handler": "ratchet_interpreter",
                    "classifier": classifier,
                    "stage": "json_parse_error"
                }
            )
            return DispatchResult(
                success=False,
                message=f"Failed to parse {classifier} classification response",
                data={"type": "ratchet_interpreter", "error": "json_parse_failed"}
            )
        except Exception as e:
            log_event(
                source="dispatcher",
                raw_transcript=raw_input[:200],
                zone_context="yellow",
                intent="ratchet_interpreter",
                inferred={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "handler": "ratchet_interpreter",
                    "classifier": classifier,
                    "stage": "handler_error"
                }
            )
            return DispatchResult(
                success=False,
                message=f"Classification failed: {str(e)}",
                data={"type": "ratchet_interpreter", "error": str(e)}
            )

    def _build_ratchet_context(self, classifier: str, raw_input: str) -> dict:
        """
        Build context dict for prompt template substitution.

        Different classifiers need different context.
        """
        context = {
            "user_input": raw_input
        }

        if classifier == "intent":
            # Load available intents from routing config
            from engine.cognitive_router import get_router
            router = get_router()
            intent_descriptions = []
            for intent_name, config in router.routes.items():
                if not intent_name.startswith("ratchet_"):
                    desc = config.get("description", intent_name)
                    intent_descriptions.append(f"- {intent_name}: {desc[:80]}")
            context["available_intents"] = "\n".join(intent_descriptions[:20])

        elif classifier == "entity_extraction":
            # Load known entities
            from engine.profile import get_entities_dir
            entities_dir = get_entities_dir()
            known = []
            if entities_dir.exists():
                for type_dir in entities_dir.iterdir():
                    if type_dir.is_dir() and not type_dir.name.startswith('.'):
                        for entity_file in type_dir.glob("*.md"):
                            known.append(f"- {type_dir.name}: {entity_file.stem}")
            context["known_entities"] = "\n".join(known[:30]) or "No entities registered yet."

        elif classifier == "correction_detection":
            # Include previous system output if available
            from engine.telemetry import read_recent_events
            recent = read_recent_events(limit=3)
            prev_output = ""
            for event in reversed(recent):
                if event.get("source") == "dispatcher":
                    prev_output = event.get("raw_transcript", "")[:300]
                    break
            context["previous_output"] = prev_output or "No previous output available."

        elif classifier == "gap_detection":
            # Entity profile should be passed in handler_args
            # For now, provide placeholder
            context["entity_profile"] = "Entity profile not provided."

        return context

    def _extract_classification(self, classifier: str, result: dict) -> Any:
        """
        Extract the classification value from the LLM result.

        Different classifiers return different structures.
        """
        if classifier == "intent":
            return result.get("intent")
        elif classifier == "entity_extraction":
            return result.get("entities", [])
        elif classifier == "correction_detection":
            if result.get("is_correction"):
                return {
                    "type": result.get("correction_type"),
                    "subject": result.get("subject"),
                    "old_value": result.get("old_value"),
                    "new_value": result.get("new_value")
                }
            return None
        elif classifier == "gap_detection":
            return result.get("gaps", [])
        else:
            # Generic fallback
            return result

    # =========================================================================
    # Internal Startup Handlers (purity-audit-v1)
    # These were moved from autonomaton.py to route through the pipeline.
    # =========================================================================

    def _handle_welcome_card(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Generate contextual welcome briefing at startup.

        Moved from autonomaton.py to route through the pipeline.
        Green Zone - informational, no side effects.
        """
        from engine.profile import get_skills_dir, get_dock_dir
        from engine.config_loader import get_persona
        from engine.llm_client import call_llm
        from engine.telemetry import log_event

        # Load the welcome card prompt template
        skill_prompt_path = get_skills_dir() / "welcome-card" / "prompt.md"
        if not skill_prompt_path.exists():
            return DispatchResult(
                success=False,
                message="Welcome card skill not found.",
                data={"type": "welcome_card", "error": "skill_not_found"}
            )

        try:
            skill_prompt = skill_prompt_path.read_text(encoding="utf-8")
        except Exception as e:
            log_event(
                source="welcome_card",
                raw_transcript=str(skill_prompt_path),
                zone_context="green",
                intent="welcome_card",
                inferred={"error": str(e), "stage": "prompt_load"}
            )
            return DispatchResult(
                success=False,
                message=f"Failed to load welcome card prompt: {e}",
                data={"type": "welcome_card", "error": "prompt_load_failed"}
            )

        # Load dock context for the briefing
        dock_dir = get_dock_dir()
        dock_context_parts = []

        for filename in ["seasonal-context.md", "goals.md", "content-strategy.md"]:
            filepath = dock_dir / filename
            if filepath.exists():
                try:
                    content = filepath.read_text(encoding="utf-8")
                    dock_context_parts.append(f"--- {filename} ---\n{content}")
                except Exception as e:
                    log_event(
                        source="welcome_card",
                        raw_transcript=str(filepath),
                        zone_context="green",
                        intent="welcome_card",
                        inferred={"error": str(e), "stage": "dock_context"}
                    )
                    continue

        if not dock_context_parts:
            dock_context = "[No dock context loaded yet.]"
        else:
            dock_context = "\n\n".join(dock_context_parts)

        # Build persona system prompt with standing context
        persona = get_persona()
        system_prompt = persona.build_system_prompt(
            "You are generating a startup welcome briefing. "
            "Read the skill instructions carefully and follow them exactly.",
            include_state=True
        )

        # Build the user prompt
        prompt = f"""{skill_prompt}

---

DOCK CONTEXT (use this to generate a specific, timely greeting):

{dock_context}

Generate the welcome card now:"""

        try:
            response = call_llm(
                prompt=prompt,
                system=system_prompt,
                tier=2,
                intent="welcome_card"
            )
            return DispatchResult(
                success=True,
                message=response.strip(),
                data={"type": "welcome_card", "response": response.strip()}
            )
        except Exception as e:
            log_event(
                source="welcome_card",
                raw_transcript="",
                zone_context="green",
                intent="welcome_card",
                inferred={"error": str(e), "stage": "llm_generation"}
            )
            return DispatchResult(
                success=False,
                message=f"Welcome briefing generation failed: {e}",
                data={"type": "welcome_card", "error": str(e)}
            )

    def _handle_startup_brief(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Generate Chief of Staff strategic brief at startup.

        Moved from autonomaton.py to route through the pipeline.
        Green Zone - informational, no side effects.
        """
        from engine.config_loader import get_persona
        from engine.llm_client import call_llm
        from engine.telemetry import log_event

        persona = get_persona()

        task_context = (
            "The operator just opened the system. Give a focused strategic brief: "
            "3-5 prioritized items based on what you know. Lead with urgency. "
            "If there are entity gaps (missing contact info, missing data) that block "
            "handlers, surface them clearly as blockers. "
            "Suggest specific commands for each item. Keep it to one short paragraph "
            "per item. Sound like a colleague, not a report."
        )

        system_prompt = persona.build_system_prompt(
            task_context=task_context,
            include_state=True
        )

        prompt = "Generate the startup strategic brief now:"

        try:
            response = call_llm(
                prompt=prompt,
                system=system_prompt,
                tier=2,
                intent="startup_brief"
            )
            return DispatchResult(
                success=True,
                message=response.strip(),
                data={"type": "startup_brief", "response": response.strip()}
            )
        except Exception as e:
            log_event(
                source="startup_brief",
                raw_transcript="startup",
                zone_context="green",
                intent="startup_brief",
                inferred={"error": str(e), "error_type": type(e).__name__}
            )
            return DispatchResult(
                success=False,
                message=f"Strategic brief generation failed: {e}",
                data={"type": "startup_brief", "error": str(e)}
            )

    def _handle_generate_plan(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Generate structured plan from dock context (first boot).

        Yellow Zone - creates/modifies a system file.
        Pipeline Stage 4 handles approval. If approved, this handler
        generates and writes the plan to dock/system/structured-plan.md.
        """
        from engine.compiler import generate_structured_plan, write_structured_plan
        from engine.telemetry import log_event

        try:
            # Generate the plan using existing compiler function
            plan_content = generate_structured_plan()

            if not plan_content:
                return DispatchResult(
                    success=False,
                    message="Failed to generate structured plan - no content returned.",
                    data={"type": "generate_plan", "error": "no_content"}
                )

            # Write the plan to dock/system/structured-plan.md
            write_success = write_structured_plan(plan_content)

            return DispatchResult(
                success=True,
                message="Structured plan generated and saved to dock/system/structured-plan.md",
                data={
                    "type": "generate_plan",
                    "plan_written": write_success,
                    "plan_preview": plan_content[:500] + "..." if len(plan_content) > 500 else plan_content
                }
            )
        except Exception as e:
            log_event(
                source="generate_plan",
                raw_transcript=raw_input[:200],
                zone_context="yellow",
                intent="generate_plan",
                inferred={"error": str(e), "error_type": type(e).__name__}
            )
            return DispatchResult(
                success=False,
                message=f"Plan generation failed: {e}",
                data={"type": "generate_plan", "error": str(e)}
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
            "cortex.py",
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
