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
