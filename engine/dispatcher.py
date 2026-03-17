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
