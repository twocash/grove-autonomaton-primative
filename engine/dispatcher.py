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
            "mcp_calendar": self._handle_mcp_calendar,
            "mcp_gmail": self._handle_mcp_gmail,
            "skill_executor": self._handle_skill_executor,
            "cortex_batch": self._handle_cortex_batch,
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
        """
        action = routing_result.handler_args.get("action", "build")

        if action == "build":
            skill_name = routing_result.extracted_args.get("skill_name", "")

            if not skill_name:
                return DispatchResult(
                    success=False,
                    message="Usage: build skill <name>",
                    data={"type": "pit_crew_build", "error": "missing_name"}
                )

            # Return that this requires interactive input
            # The actual build happens after description is collected by REPL
            return DispatchResult(
                success=True,
                message=f"Ready to build skill: {skill_name}",
                data={
                    "type": "pit_crew_build",
                    "skill_name": skill_name,
                    "requires_description": True
                },
                requires_approval=True,  # Red Zone
                approval_context=f"Build new skill: {skill_name}"
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

    def _handle_mcp_calendar(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Handle calendar scheduling via MCP (Google Calendar).

        Uses LLM (Tier 1) to extract scheduling parameters from raw input
        and format them into a calendar API payload.

        Yellow Zone - requires Jidoka approval at MCP execution layer.
        """
        import json
        from engine.llm_client import call_llm

        server = routing_result.handler_args.get("server", "google_calendar")
        capability = routing_result.handler_args.get("capability", "create_event")

        # Use LLM to extract calendar parameters from raw input
        prompt = f"""Extract calendar event parameters from this request.
Return JSON with these fields:
- event_type: Type of event (lesson, practice, tournament, meeting)
- participant: Name of person/group involved
- date: Date in ISO format (YYYY-MM-DD)
- time: Time in 24-hour format (HH:MM)
- duration_minutes: Duration in minutes (default 60)
- location: Location if mentioned (optional)

Request: "{raw_input}"

Return ONLY valid JSON, no explanations:"""

        try:
            response = call_llm(
                prompt=prompt,
                tier=1,  # Haiku for extraction
                intent="mcp_payload_formatting"
            )

            payload = json.loads(response)

            # Format for Google Calendar API
            calendar_payload = self._format_calendar_payload(payload)

            return DispatchResult(
                success=True,
                message=f"Ready to schedule: {payload.get('event_type', 'event')} with {payload.get('participant', 'unknown')}",
                data={
                    "type": "mcp_action",
                    "server": server,
                    "capability": capability,
                    "payload": calendar_payload,
                    "raw_extraction": payload
                },
                requires_approval=True,
                approval_context=f"Schedule {payload.get('event_type', 'event')} for {payload.get('participant', 'unknown')} on {payload.get('date', '?')} at {payload.get('time', '?')}"
            )

        except json.JSONDecodeError:
            return DispatchResult(
                success=False,
                message="Failed to parse calendar parameters",
                data={"type": "mcp_action", "error": "parse_failed"}
            )
        except Exception as e:
            return DispatchResult(
                success=False,
                message=f"Calendar extraction failed: {e}",
                data={"type": "mcp_action", "error": str(e)}
            )

    def _format_calendar_payload(self, extracted: dict) -> dict:
        """
        Format extracted parameters into Google Calendar API payload.
        """
        from datetime import datetime, timedelta

        # Build summary
        event_type = extracted.get("event_type", "Event")
        participant = extracted.get("participant", "")
        summary = f"{event_type.title()} - {participant}" if participant else event_type.title()

        # Parse date and time
        date_str = extracted.get("date", datetime.now().strftime("%Y-%m-%d"))
        time_str = extracted.get("time", "09:00")
        duration = extracted.get("duration_minutes", 60)

        # Build start/end datetime
        try:
            start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            end_dt = start_dt + timedelta(minutes=duration)
        except ValueError:
            start_dt = datetime.now()
            end_dt = start_dt + timedelta(hours=1)

        payload = {
            "summary": summary,
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "America/New_York"
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": "America/New_York"
            },
            "participant": participant,
            "event_type": event_type
        }

        # Add location if present
        if extracted.get("location"):
            payload["location"] = extracted["location"]

        return payload

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

        # Build the execution prompt
        execution_prompt = f"""{prompt_template}

---

USER REQUEST: {raw_input}

Please execute the skill based on the above instructions and user request.
"""

        try:
            response = call_llm(
                prompt=execution_prompt,
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

    def _handle_mcp_gmail(
        self,
        routing_result: RoutingResult,
        raw_input: str
    ) -> DispatchResult:
        """
        Handle email sending via MCP (Gmail).

        Uses LLM (Tier 2) to draft email content from raw input
        and format into Gmail API payload.

        Yellow Zone - requires Jidoka approval at MCP execution layer.
        """
        import json
        from engine.llm_client import call_llm

        server = routing_result.handler_args.get("server", "gmail")
        capability = routing_result.handler_args.get("capability", "send_email")

        # Use LLM to extract and draft email from raw input
        prompt = f"""Extract email parameters and draft the email content.
Return JSON with these fields:
- recipient: Name of the recipient (e.g., "Henderson Parent")
- subject: Email subject line
- body: Full email body text (professional, friendly tone)

Request: "{raw_input}"

Return ONLY valid JSON, no explanations:"""

        try:
            response = call_llm(
                prompt=prompt,
                tier=2,  # Sonnet for quality email drafting
                intent="mcp_payload_formatting"
            )

            payload = json.loads(response)

            return DispatchResult(
                success=True,
                message=f"Email ready to send: {payload.get('subject', 'No subject')}",
                data={
                    "type": "mcp_action",
                    "server": server,
                    "capability": capability,
                    "payload": {
                        "to": payload.get("recipient", ""),
                        "subject": payload.get("subject", ""),
                        "body": payload.get("body", "")
                    },
                    "raw_extraction": payload
                },
                requires_approval=True,
                approval_context=f"Send email to {payload.get('recipient', 'unknown')}: {payload.get('subject', 'No subject')}"
            )

        except json.JSONDecodeError:
            return DispatchResult(
                success=False,
                message="Failed to parse email parameters",
                data={"type": "mcp_action", "error": "parse_failed"}
            )
        except Exception as e:
            return DispatchResult(
                success=False,
                message=f"Email extraction failed: {e}",
                data={"type": "mcp_action", "error": str(e)}
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

            result = cortex.run_evolution_analysis(telemetry_events, exhaust_board)

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
