"""
pipeline.py - The Invariant Pipeline

Every interaction MUST traverse these five stages in sequence.
Code that bypasses these stages to execute directly is FORBIDDEN.

Stages:
    1. Telemetry   - Log the raw input as structured data
    2. Recognition - Parse intent, entities, and domain
    3. Compilation - Query dock, draft proposed actions
    4. Approval    - Apply governance checks (zone-based)
    5. Execution   - Carry out action if approval is met
"""

from dataclasses import dataclass, field
from typing import Optional, Any

from engine.telemetry import log_event
from engine.ux import confirm_yellow_zone


@dataclass
class MCPAction:
    """
    Defines an MCP action to be executed in Stage 5.
    """
    server: str
    capability: str
    payload: dict


@dataclass
class PipelineContext:
    """
    Carries state through all pipeline stages.
    Each stage reads from and writes to this context.
    """
    # Stage 1: Telemetry
    raw_input: str = ""
    source: str = "operator_session"
    telemetry_event: dict = field(default_factory=dict)

    # Stage 2: Recognition
    intent: Optional[str] = None
    entities: dict = field(default_factory=dict)
    domain: Optional[str] = None

    # Stage 3: Compilation
    proposed_action: Optional[str] = None
    dock_context: list = field(default_factory=list)
    mcp_action: Optional[MCPAction] = None  # External capability to invoke

    # Stage 4: Approval
    zone: str = "green"
    approved: bool = False

    # Stage 5: Execution
    result: Any = None
    executed: bool = False
    mcp_result: Any = None  # Result from MCP execution


class InvariantPipeline:
    """
    The five-stage pipeline that all interactions must traverse.
    Bypass is architecturally forbidden.
    """

    def __init__(self):
        self.context: Optional[PipelineContext] = None

    def run(self, raw_input: str, source: str = "operator_session", zone: str = "yellow") -> PipelineContext:
        """
        Execute the full invariant pipeline.

        Args:
            raw_input: The user's raw input string
            source: Origin identifier for telemetry
            zone: Zone classification (green/yellow/red)

        Returns:
            PipelineContext with all stages populated

        Sprint 3.5: Exception Telemetry
        All exceptions are caught, logged to telemetry, and returned
        in the context. No ghost failures - every crash leaves a trail.
        """
        self.context = PipelineContext(
            raw_input=raw_input,
            source=source,
            zone=zone
        )

        try:
            # Execute stages in strict sequence
            self._run_telemetry()
            self._run_recognition()
            self._run_compilation()
            self._run_approval()
            self._run_execution()

        except Exception as e:
            # Log failure to telemetry (Invariant #5: No ghost failures)
            self._log_pipeline_failure(e)

            # Set context to reflect failure state
            self.context.executed = False
            self.context.result = {
                "status": "failed",
                "message": f"Pipeline failure: {str(e)}",
                "error_type": type(e).__name__
            }

        return self.context

    def _log_pipeline_failure(self, exception: Exception) -> None:
        """
        Log a pipeline failure to telemetry.

        Sprint 3.5: No ghost failures - every crash leaves an audit trail.
        """
        log_event(
            source="pipeline_failure",
            raw_transcript=self.context.raw_input[:200] if self.context.raw_input else "",
            zone_context=self.context.zone,
            inferred={
                "error": str(exception),
                "error_type": type(exception).__name__,
                "intent": self.context.intent,
                "domain": self.context.domain,
                "stage": self._get_current_stage()
            }
        )

    def _get_current_stage(self) -> str:
        """Determine which stage was active when failure occurred."""
        if self.context.telemetry_event is None:
            return "telemetry"
        if self.context.intent is None:
            return "recognition"
        if self.context.proposed_action is None:
            return "compilation"
        if not hasattr(self.context, 'approved') or self.context.approved is None:
            return "approval"
        return "execution"

    def _run_telemetry(self) -> None:
        """
        Stage 1: Telemetry
        Log the raw input before any processing.
        """
        self.context.telemetry_event = log_event(
            source=self.context.source,
            raw_transcript=self.context.raw_input,
            zone_context=self.context.zone,
            inferred={}
        )

    def _run_recognition(self) -> None:
        """
        Stage 2: Recognition
        Parse intent, entities, and domain from input.

        Sprint 1: Tier 0 keyword-based classification via Cognitive Router.
        Future: LLM-powered intent classification.

        CRITICAL: The router's zone classification overrides the caller's zone.
        Unknown intents default to yellow zone per Digital Jidoka principle.
        """
        from engine.cognitive_router import classify_intent

        # Classify intent using the cognitive router
        routing_result = classify_intent(self.context.raw_input)

        # Set context from routing result - router is authoritative
        self.context.intent = routing_result.intent
        self.context.domain = routing_result.domain
        self.context.zone = routing_result.zone  # Override caller's zone

        # Store routing metadata for Stage 5 dispatcher
        self.context.entities = {
            "routing": {
                "tier": routing_result.tier,
                "confidence": routing_result.confidence,
                "handler": routing_result.handler,
                "handler_args": routing_result.handler_args or {},
                "extracted_args": routing_result.extracted_args or {}
            }
        }

    def _run_compilation(self) -> None:
        """
        Stage 3: Compilation
        Query the dock (RAG) and draft proposed actions.

        The dock provides strategic context from local knowledge files.
        This context informs the proposed action sent to Approval.
        """
        # Import here to avoid circular dependency at module load
        from engine.dock import query_dock

        # Query the dock with the raw transcript
        # Future: Use parsed intent/entities for more targeted retrieval
        query = self.context.raw_input
        if self.context.intent and self.context.intent != "unknown":
            query = f"{self.context.intent}: {self.context.raw_input}"

        dock_context = query_dock(query, top_k=2)
        self.context.dock_context = [dock_context]

        # Compose the proposed action with dock context
        self.context.proposed_action = (
            f"[ACTION] Process: {self.context.raw_input}\n\n"
            f"[STRATEGIC CONTEXT]\n{dock_context}"
        )

    def _run_approval(self) -> None:
        """
        Stage 4: Approval
        Apply governance checks based on zone classification.

        SPRINT 3.5: Unified Governance
        For MCP handlers, compute effective zone by combining:
        - Router zone (from intent classification)
        - Domain zone (from zones.schema)
        - Capability zone (from mcp.config)

        The most restrictive zone wins.

        Green zone: Auto-approve
        Yellow zone: Require Jidoka confirmation
        Red zone: Require explicit approval with context
        """
        # Compute effective zone for MCP actions
        effective_zone = self._compute_effective_zone()

        # Update context with effective zone
        self.context.zone = effective_zone

        if effective_zone == "green":
            # Green zone: Autonomous execution allowed
            self.context.approved = True

        elif effective_zone == "yellow":
            # Yellow zone: One-thumb approval required
            self.context.approved = confirm_yellow_zone(
                action_description=self.context.proposed_action or "Unknown action"
            )

        elif effective_zone == "red":
            # Red zone: Explicit approval with full context
            self.context.approved = confirm_yellow_zone(
                action_description=f"[RED ZONE] {self.context.proposed_action or 'Unknown action'}"
            )

        else:
            # Unknown zone: Fail safe, require approval
            self.context.approved = confirm_yellow_zone(
                action_description=f"[UNKNOWN ZONE: {effective_zone}] {self.context.proposed_action}"
            )

    def _compute_effective_zone(self) -> str:
        """
        Compute the effective zone for this action.

        For MCP handlers (mcp_calendar, mcp_gmail), combines:
        - Router zone (from intent)
        - Domain zone (from zones.schema)
        - Capability zone (from mcp.config)

        The most restrictive zone always wins.
        """
        from engine.effectors import ConfigLoader, compute_effective_zone

        router_zone = self.context.zone

        # Check if this is an MCP handler
        routing_info = self.context.entities.get("routing", {})
        handler = routing_info.get("handler", "")
        handler_args = routing_info.get("handler_args", {})

        if not handler or not handler.startswith("mcp_"):
            # Not an MCP handler, use router zone directly
            return router_zone

        # MCP handler: compute effective zone
        server = handler_args.get("server", "")
        capability = handler_args.get("capability", "")
        domain = self.context.domain or "general"

        if not server:
            # No server info, use router zone
            return router_zone

        # Get zone from mcp.config (server/capability)
        capability_zone = ConfigLoader.get_capability_zone(server, capability)

        # Get zone from zones.schema (domain)
        domain_zone = ConfigLoader.get_domain_zone(domain)

        # Compute most restrictive: router vs capability vs domain
        mcp_zone = compute_effective_zone(capability_zone, domain_zone)
        effective_zone = compute_effective_zone(router_zone, mcp_zone)

        return effective_zone

    def _run_execution(self) -> None:
        """
        Stage 5: Execution
        Carry out the action if approval was granted.

        Routes through:
        1. Dispatcher - for classified intents with handlers
        2. MCP effectors - for external capabilities
        3. Local execution - fallback for passthrough
        """
        if not self.context.approved:
            self.context.executed = False
            self.context.result = {
                "status": "cancelled",
                "message": "Action not approved"
            }
            return

        # Check for routing info from Stage 2
        routing_info = self.context.entities.get("routing", {})
        handler = routing_info.get("handler")

        if handler:
            # Use dispatcher for classified intents with handlers
            self._execute_via_dispatcher(routing_info)
        elif self.context.mcp_action is not None:
            # MCP action path
            self._execute_mcp_action()
        else:
            # Local execution (no handler, no MCP)
            self.context.executed = True
            self.context.result = {
                "status": "executed",
                "message": f"Processed input: {self.context.raw_input[:50]}..."
                           if len(self.context.raw_input) > 50
                           else f"Processed input: {self.context.raw_input}",
                "data": {"type": "passthrough"}
            }

    def _execute_via_dispatcher(self, routing_info: dict) -> None:
        """
        Execute action via the dispatcher.

        Reconstructs the RoutingResult from stored metadata and
        dispatches to the appropriate handler.

        If dispatcher returns an MCP action, execute it through the
        governed effector layer.
        """
        from engine.dispatcher import dispatch_action
        from engine.cognitive_router import RoutingResult

        # Reconstruct routing result from stored metadata
        routing_result = RoutingResult(
            intent=self.context.intent or "unknown",
            domain=self.context.domain or "general",
            zone=self.context.zone,
            tier=routing_info.get("tier", 2),
            confidence=routing_info.get("confidence", 0.0),
            handler=routing_info.get("handler"),
            handler_args=routing_info.get("handler_args", {}),
            extracted_args=routing_info.get("extracted_args", {})
        )

        # Dispatch the action
        dispatch_result = dispatch_action(routing_result, self.context.raw_input)

        # Check if dispatcher returned an MCP action to execute
        data = dispatch_result.data or {}
        if data.get("type") == "mcp_action" and dispatch_result.success:
            # Wire MCP action and execute through governed effector layer
            self.context.mcp_action = MCPAction(
                server=data.get("server", ""),
                capability=data.get("capability", ""),
                payload=data.get("payload", {})
            )
            self._execute_mcp_action()
            return

        # Standard dispatcher result handling
        self.context.executed = dispatch_result.success
        self.context.result = {
            "status": "executed" if dispatch_result.success else "failed",
            "message": dispatch_result.message,
            "data": dispatch_result.data
        }

    def _execute_mcp_action(self) -> None:
        """
        Execute an MCP action through the effector layer.

        The effector layer enforces its own zone governance:
        - Compares domain zone with server/capability zone
        - Most restrictive zone wins
        - Yellow/Red zones trigger Jidoka approval
        """
        # Import here to avoid circular dependency
        from engine.effectors import execute_mcp_action

        action = self.context.mcp_action
        domain = self.context.domain or "general"

        # Execute through the governed effector layer
        mcp_result = execute_mcp_action(
            server=action.server,
            capability=action.capability,
            payload=action.payload,
            domain=domain
        )

        # Store the MCP result
        self.context.mcp_result = mcp_result

        if mcp_result.success:
            self.context.executed = True
            self.context.result = {
                "status": "executed",
                "message": f"MCP action completed: {action.server}.{action.capability}",
                "mcp_result": mcp_result.result
            }
        elif not mcp_result.approved:
            # User rejected at the effector governance layer
            self.context.executed = False
            self.context.result = {
                "status": "rejected",
                "message": f"MCP action rejected by user: {action.server}.{action.capability}",
                "zone": mcp_result.effective_zone
            }
        else:
            # Execution failed after approval
            self.context.executed = False
            self.context.result = {
                "status": "failed",
                "message": f"MCP action failed: {mcp_result.error}",
                "error": mcp_result.error
            }


# Module-level convenience functions
def run_pipeline(raw_input: str, source: str = "operator_session", zone: str = "yellow") -> PipelineContext:
    """
    Execute the invariant pipeline on the given input.

    This is the primary entry point for processing user interactions.
    """
    pipeline = InvariantPipeline()
    return pipeline.run(raw_input, source, zone)


def run_pipeline_with_mcp(
    raw_input: str,
    mcp_server: str,
    mcp_capability: str,
    mcp_payload: dict,
    domain: str = "general",
    source: str = "operator_session"
) -> PipelineContext:
    """
    Execute the pipeline with a pre-defined MCP action.

    This is useful for testing MCP governance or when the intent
    and action are already known (e.g., from a skill or command).

    The MCP action will go through full zone governance at execution time.
    """
    pipeline = InvariantPipeline()
    pipeline.context = PipelineContext(
        raw_input=raw_input,
        source=source,
        zone="green",  # Initial zone; MCP governance computes effective zone
        domain=domain,
        mcp_action=MCPAction(
            server=mcp_server,
            capability=mcp_capability,
            payload=mcp_payload
        )
    )

    # Execute stages in strict sequence
    pipeline._run_telemetry()
    pipeline._run_recognition()
    pipeline._run_compilation()
    pipeline._run_approval()
    pipeline._run_execution()

    return pipeline.context
