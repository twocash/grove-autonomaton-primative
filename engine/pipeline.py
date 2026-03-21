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
from engine.ux import confirm_yellow_zone, confirm_red_zone_with_context


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
    force_route: Optional[str] = None  # Sprint 6: Force routing to specific handler

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

    def run(
        self,
        raw_input: str,
        source: str = "operator_session",
        zone: str = "yellow",
        force_route: Optional[str] = None
    ) -> PipelineContext:
        """
        Execute the full invariant pipeline.

        Args:
            raw_input: The user's raw input string
            source: Origin identifier for telemetry
            zone: Zone classification (green/yellow/red)
            force_route: Optional - Force routing to a specific intent (Sprint 6)
                        Used by ratchet_classify() for classification sub-intents

        Returns:
            PipelineContext with all stages populated

        Sprint 3.5: Exception Telemetry
        All exceptions are caught, logged to telemetry, and returned
        in the context. No ghost failures - every crash leaves a trail.
        """
        self.context = PipelineContext(
            raw_input=raw_input,
            source=source,
            zone=zone,
            force_route=force_route
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
        Purity v2: Flat fields for grep-able audit trail.
        """
        routing_info = self.context.entities.get("routing", {})
        log_event(
            source="pipeline_failure",
            raw_transcript=self.context.raw_input[:200] if self.context.raw_input else "",
            zone_context=self.context.zone,
            intent=self.context.intent,
            tier=routing_info.get("tier"),
            inferred={
                "error": str(exception),
                "error_type": type(exception).__name__,
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

    def _log_pipeline_completion(self) -> None:
        """Log pipeline completion with flat routing fields for auditability.

        Purity v2: First-class routing fields make pipeline decisions grep-able
        without parsing the inferred dict.
        """
        routing_info = self.context.entities.get("routing", {})

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

        log_event(
            source=self.context.source,
            raw_transcript=self.context.raw_input[:200],
            zone_context=self.context.zone,
            intent=self.context.intent,
            tier=routing_info.get("tier"),
            confidence=routing_info.get("confidence"),
            human_feedback="approved" if self.context.approved else "rejected",
            cost_usd=cost,
            inferred={
                "stage": "execution",
                "pipeline_id": self.context.telemetry_event.get("id"),
                "handler": routing_info.get("handler"),
                "intent_type": routing_info.get("intent_type"),
            }
        )

    def _run_telemetry(self) -> None:
        """
        Stage 1: Telemetry
        Log the raw input before any processing.
        """
        self.context.telemetry_event = log_event(
            source=self.context.source,
            raw_transcript=self.context.raw_input,
            zone_context=self.context.zone,
            inferred={"stage": "telemetry"}
        )

    def _run_recognition(self) -> None:
        """
        Stage 2: Recognition
        Parse intent, entities, and domain from input.

        Sprint 1: Tier 0 keyword-based classification via Cognitive Router.
        Sprint 6: Support force_route for ratchet_classify() pipeline traversals.

        CRITICAL: The router's zone classification overrides the caller's zone.
        Unknown intents default to yellow zone per Digital Jidoka principle.
        """
        from engine.cognitive_router import classify_intent, get_router

        # Sprint 6: Handle forced routing for ratchet_classify()
        # This allows classification sub-intents to traverse the pipeline
        if self.context.force_route:
            router = get_router()
            route_config = router.routes.get(self.context.force_route, {})

            # Build routing result from the forced route's config
            self.context.intent = self.context.force_route
            self.context.domain = route_config.get("domain", "system")
            self.context.zone = route_config.get("zone", "green")

            self.context.entities = {
                "routing": {
                    "tier": route_config.get("tier", 1),
                    "confidence": 1.0,  # Forced route = full confidence
                    "handler": route_config.get("handler"),
                    "handler_args": route_config.get("handler_args", {}),
                    "extracted_args": {},
                    "intent_type": route_config.get("intent_type", "actionable"),
                    "action_required": route_config.get("intent_type") != "conversational",
                    "llm_metadata": {"forced_route": True}
                }
            }

            # Stage 2 trace for forced route path
            routing_info = self.context.entities.get("routing", {})
            log_event(
                source=self.context.source,
                raw_transcript=self.context.raw_input[:200],
                zone_context=self.context.zone,
                intent=self.context.intent,
                tier=routing_info.get("tier"),
                confidence=routing_info.get("confidence"),
                inferred={
                    "stage": "recognition",
                    "pipeline_id": self.context.telemetry_event.get("id"),
                    "domain": self.context.domain,
                    "handler": routing_info.get("handler"),
                    "intent_type": routing_info.get("intent_type"),
                    "method": "forced",
                }
            )
            return

        # Normal classification path
        routing_result = classify_intent(self.context.raw_input)

        # Set context from routing result - router is authoritative
        self.context.intent = routing_result.intent
        self.context.domain = routing_result.domain
        self.context.zone = routing_result.zone  # Override caller's zone

        # Store routing metadata for Stage 5 dispatcher
        # Sprint 8: Include intent_type, action_required, llm_metadata for
        # Compilation gating and Approval UX decisions
        self.context.entities = {
            "routing": {
                "tier": routing_result.tier,
                "confidence": routing_result.confidence,
                "handler": routing_result.handler,
                "handler_args": routing_result.handler_args or {},
                "extracted_args": routing_result.extracted_args or {},
                "intent_type": routing_result.intent_type,
                "action_required": routing_result.action_required,
                "llm_metadata": routing_result.llm_metadata or {}
            }
        }

        # --- End of _run_recognition ---
        # Stage 2 trace: recognition complete
        routing_info = self.context.entities.get("routing", {})
        log_event(
            source=self.context.source,
            raw_transcript=self.context.raw_input[:200],
            zone_context=self.context.zone,
            intent=self.context.intent,
            tier=routing_info.get("tier"),
            confidence=routing_info.get("confidence"),
            inferred={
                "stage": "recognition",
                "pipeline_id": self.context.telemetry_event.get("id"),
                "domain": self.context.domain,
                "handler": routing_info.get("handler"),
                "intent_type": routing_info.get("intent_type"),
                "method": "forced" if self.context.force_route else (
                    "cache" if routing_info.get("llm_metadata", {}).get("source") == "pattern_cache"
                    else ("llm" if routing_info.get("tier", 0) >= 2 else "keyword")
                ),
                "entities": routing_info.get("llm_metadata", {}).get("entities", {}),
                "sentiment": routing_info.get("llm_metadata", {}).get("sentiment"),
            }
        )

    def _run_compilation(self) -> None:
        """
        Stage 3: Compilation
        Query the dock (RAG) and draft proposed actions.

        Sprint 8: Compilation Gating
        - conversational intents: Skip dock query entirely (no context needed)
        - informational intents: Optional dock query (lightweight context)
        - actionable intents: Full dock query (strategic context)

        The dock provides strategic context from local knowledge files.
        This context informs the proposed action sent to Approval.
        """
        # Get intent_type from routing metadata
        routing_info = self.context.entities.get("routing", {})
        intent_type = routing_info.get("intent_type", "actionable")

        # Conversational intents skip dock entirely
        if intent_type == "conversational":
            self.context.dock_context = []
            self.context.proposed_action = self.context.raw_input

            # Stage 3 trace for skipped compilation
            log_event(
                source=self.context.source,
                raw_transcript=self.context.raw_input[:200],
                zone_context=self.context.zone,
                intent=self.context.intent,
                inferred={
                    "stage": "compilation",
                    "pipeline_id": self.context.telemetry_event.get("id"),
                    "intent_type": "conversational",
                    "dock_chunks": 0,
                    "skipped": True,
                }
            )
            return

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

        # --- End of _run_compilation ---
        routing_info = self.context.entities.get("routing", {})
        log_event(
            source=self.context.source,
            raw_transcript=self.context.raw_input[:200],
            zone_context=self.context.zone,
            intent=self.context.intent,
            inferred={
                "stage": "compilation",
                "pipeline_id": self.context.telemetry_event.get("id"),
                "intent_type": routing_info.get("intent_type", "actionable"),
                "dock_chunks": len(self.context.dock_context) if self.context.dock_context else 0,
                "skipped": False,
            }
        )

    def _log_approval_trace(self) -> None:
        """Log Stage 4 approval trace. Called before every return."""
        routing_info = self.context.entities.get("routing", {})
        log_event(
            source=self.context.source,
            raw_transcript=self.context.raw_input[:200],
            zone_context=self.context.zone,
            intent=self.context.intent,
            human_feedback="approved" if self.context.approved else "rejected",
            inferred={
                "stage": "approval",
                "pipeline_id": self.context.telemetry_event.get("id"),
                "effective_zone": self.context.zone,
                "action_required": routing_info.get("action_required", True),
            }
        )

    def _run_approval(self) -> None:
        """
        Stage 4: Approval
        Apply governance checks based on zone classification.

        Sprint 8: action_required Check
        - If action_required=False AND zone=green: auto-approve, no UX
        - This allows conversational intents to skip approval prompts entirely

        Sprint 8: Clarification Jidoka
        - If intent is unknown with low confidence: ask user to clarify
        - This prevents blanket yellow approval for ambiguous input

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
        from engine.cognitive_router import (
            get_clarification_options,
            resolve_clarification,
            CognitiveRouter
        )

        # Get routing metadata for action_required check
        routing_info = self.context.entities.get("routing", {})
        action_required = routing_info.get("action_required", True)
        confidence = routing_info.get("confidence", 0.0)

        # Compute effective zone for MCP actions
        effective_zone = self._compute_effective_zone()

        # Update context with effective zone
        self.context.zone = effective_zone

        # Sprint 8: Clarification Jidoka for unknown intents
        if (self.context.intent == "unknown" and
            confidence < CognitiveRouter.CLARIFICATION_THRESHOLD):
            # Ask user to clarify instead of blanket yellow approval
            self._handle_clarification_jidoka()
            self._log_approval_trace()
            return

        # Sprint 8: Skip approval UX for non-actionable green zone intents
        if not action_required and effective_zone == "green":
            self.context.approved = True
            self._log_approval_trace()
            return

        if effective_zone == "green":
            # Green zone: Autonomous execution allowed
            self.context.approved = True

        elif effective_zone == "yellow":
            # Yellow zone: One-thumb approval required
            self.context.approved = confirm_yellow_zone(
                action_description=self.context.proposed_action or "Unknown action"
            )

        elif effective_zone == "red":
            # Red zone: Explicit approval with full context (Purity v2)
            routing_info = self.context.entities.get("routing", {})
            payload = {
                "action": self.context.proposed_action or "Unknown action",
                "intent": self.context.intent,
                "handler": routing_info.get("handler"),
                "handler_args": routing_info.get("handler_args", {}),
                "extracted_args": routing_info.get("extracted_args", {}),
            }
            self.context.approved = confirm_red_zone_with_context(
                action_description=self.context.proposed_action or "Unknown action",
                payload=payload
            )

        else:
            # Unknown zone: Fail safe, require approval
            self.context.approved = confirm_yellow_zone(
                action_description=f"[UNKNOWN ZONE: {effective_zone}] {self.context.proposed_action}"
            )

        # --- End of _run_approval ---
        self._log_approval_trace()

    def _handle_clarification_jidoka(self) -> None:
        """
        Kaizen classification proposal for unknown input.

        The router couldn't classify this from keywords or cache.
        Instead of auto-firing the LLM, ask the operator.

        This is Kaizen (propose improvement), not Jidoka (stop for error).
        Nothing is broken. The system just doesn't know this phrase yet.
        """
        from engine.cognitive_router import (
            get_clarification_options, resolve_clarification, get_router
        )
        from engine.ux import ask_jidoka
        from engine.telemetry import log_event

        # Build the 4-option Kaizen prompt
        rephrase_key = "4"
        options = {
            "1": "Use the LLM to classify this (fractions of a cent, cached after)",
            "2": "Answer from what you already know (free)",
            "3": "Show me what you can help with (free)",
        }

        # Option 4 is always rephrase
        options[rephrase_key] = "I'll rephrase"

        choice = ask_jidoka(
            context_message=(
                "I don't recognize this from my current vocabulary.\n"
                "I can use the LLM to learn what you mean — the Ratchet\n"
                "will cache it so it's free next time."
            ),
            options=options
        )

        # ---- Option 1: Consent to LLM classification ----
        if choice == "1":
            router = get_router()
            llm_result = router._escalate_to_llm(self.context.raw_input)

            if llm_result is not None and llm_result.intent != "unknown":
                # LLM classified successfully — update context and proceed
                self.context.intent = llm_result.intent
                self.context.domain = llm_result.domain
                self.context.zone = llm_result.zone
                self.context.entities["routing"] = {
                    "tier": llm_result.tier,
                    "confidence": llm_result.confidence,
                    "handler": llm_result.handler,
                    "handler_args": llm_result.handler_args or {},
                    "extracted_args": llm_result.extracted_args or {},
                    "intent_type": llm_result.intent_type,
                    "action_required": llm_result.action_required,
                    "llm_metadata": llm_result.llm_metadata or {}
                }
                self.context.approved = True
                log_event(
                    source="kaizen_classification",
                    raw_transcript=self.context.raw_input[:200],
                    zone_context=self.context.zone,
                    intent=self.context.intent,
                    human_feedback="approved_classification",
                    inferred={
                        "stage": "approval_kaizen",
                        "pipeline_id": self.context.telemetry_event.get("id"),
                        "resolved_intent": self.context.intent,
                        "classification_consented": True,
                    }
                )
                return

            # LLM couldn't classify either — fall to option 3
            log_event(
                source="kaizen_classification",
                raw_transcript=self.context.raw_input[:200],
                zone_context="yellow",
                intent="unknown",
                inferred={
                    "stage": "approval_kaizen",
                    "pipeline_id": self.context.telemetry_event.get("id"),
                    "llm_classification_failed": True,
                }
            )
            # Show config options as fallback
            choice = "3"

        # ---- Option 2: Answer from local context (free) ----
        if choice == "2":
            self.context.intent = "general_chat"
            self.context.domain = "system"
            self.context.zone = "green"
            self.context.entities["routing"]["handler"] = "general_chat"
            self.context.entities["routing"]["handler_args"] = {}
            self.context.entities["routing"]["intent_type"] = "informational"
            self.context.entities["routing"]["action_required"] = False
            self.context.entities["routing"]["tier"] = 1
            self.context.approved = True
            log_event(
                source="kaizen_classification",
                raw_transcript=self.context.raw_input[:200],
                zone_context="green",
                intent="general_chat",
                human_feedback="local_context",
                inferred={
                    "stage": "approval_kaizen",
                    "pipeline_id": self.context.telemetry_event.get("id"),
                    "used_local_context": True,
                }
            )
            return

        # ---- Option 3: Config-driven options (free) ----
        if choice == "3":
            config_options = get_clarification_options()
            if config_options:
                sub_choice = ask_jidoka(
                    context_message="Here's what I can help with:",
                    options=config_options
                )
                resolved = resolve_clarification(
                    sub_choice, self.context.raw_input
                )
                self.context.intent = resolved.intent
                self.context.domain = resolved.domain
                self.context.zone = resolved.zone
                self.context.entities["routing"] = {
                    "tier": resolved.tier,
                    "confidence": resolved.confidence,
                    "handler": resolved.handler,
                    "handler_args": resolved.handler_args or {},
                    "extracted_args": resolved.extracted_args or {},
                    "intent_type": resolved.intent_type,
                    "action_required": resolved.action_required,
                    "llm_metadata": resolved.llm_metadata or {}
                }
                self.context.approved = True
                log_event(
                    source="kaizen_classification",
                    raw_transcript=self.context.raw_input[:200],
                    zone_context=self.context.zone,
                    intent=self.context.intent,
                    human_feedback="clarified",
                    inferred={
                        "stage": "approval_kaizen",
                        "pipeline_id": self.context.telemetry_event.get("id"),
                        "resolved_intent": self.context.intent,
                    }
                )
                return

        # ---- Option 4 (or fallthrough): Rephrase ----
        self.context.approved = False
        self.context.result = {
            "status": "cancelled",
            "message": "Go ahead — I'm listening."
        }

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

        # Purity v2: Log completion with flat routing fields for auditability
        # THE RATCHET: Cache confirmed LLM classifications for Tier 0 lookup (purity-audit-v1)
        if self.context.executed:
            self._log_pipeline_completion()
            self._write_to_pattern_cache()

    def _write_to_pattern_cache(self) -> None:
        """Write confirmed LLM classification to pattern cache.

        THE RATCHET WRITE PATH:
        When an LLM-classified intent is approved AND executed successfully,
        cache the classification so it resolves at Tier 0 next time.

        Only caches when:
        - Classification came from LLM (tier >= 2 in routing metadata)
        - Action was approved (Stage 4 passed)
        - Action was executed successfully (Stage 5 succeeded)
        - Zone is NOT red (red zone actions should always require human judgment)
        """
        import hashlib
        import yaml
        from datetime import datetime, timezone
        from engine.profile import get_config_dir

        routing_info = self.context.entities.get("routing", {})
        tier = routing_info.get("tier", 0)
        llm_metadata = routing_info.get("llm_metadata", {})

        # Only cache LLM classifications that were confirmed by execution
        if tier < 2:
            return  # Already Tier 0/1 — no demotion needed
        if not self.context.approved:
            return
        if not self.context.executed:
            return
        if self.context.zone == "red":
            return  # Red zone: always require human judgment
        if llm_metadata.get("source") == "pattern_cache":
            return  # Already from cache — don't re-cache

        input_hash = hashlib.sha256(
            self.context.raw_input.lower().strip().encode()
        ).hexdigest()[:16]

        try:
            cache_path = get_config_dir() / "pattern_cache.yaml"
        except RuntimeError:
            return  # No profile set

        try:
            if cache_path.exists():
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            else:
                data = {}

            cache = data.get("cache", {})

            existing = cache.get(input_hash)
            if existing:
                # Increment confirmation count
                existing["confirmed_count"] = existing.get("confirmed_count", 1) + 1
                existing["last_confirmed"] = datetime.now(timezone.utc).isoformat()
            else:
                # New cache entry
                cache[input_hash] = {
                    "intent": self.context.intent,
                    "domain": self.context.domain,
                    "zone": self.context.zone,
                    "handler": routing_info.get("handler"),
                    "handler_args": routing_info.get("handler_args", {}),
                    "intent_type": routing_info.get("intent_type", "actionable"),
                    "confirmed_count": 1,
                    "last_confirmed": datetime.now(timezone.utc).isoformat(),
                    "original_input": self.context.raw_input[:100],
                    "confidence": routing_info.get("confidence", 0.0),
                    "entities": llm_metadata.get("entities", {}),
                    "sentiment": llm_metadata.get("sentiment", "neutral"),
                }

            data["cache"] = cache

            with open(cache_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)

            # Invalidate router's in-memory cache — config changed, re-read it
            # This is Invariant #3: Config Over Code. The file is authoritative.
            from engine.cognitive_router import get_router
            get_router().load_cache()

        except Exception as e:
            # Cache write failure is non-fatal — log and continue
            log_event(
                source="pattern_cache",
                raw_transcript=self.context.raw_input[:200],
                zone_context="green",
                inferred={"error": str(e), "stage": "cache_write"}
            )

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
def run_pipeline(
    raw_input: str,
    source: str = "operator_session",
    zone: str = "yellow",
    force_route: Optional[str] = None
) -> PipelineContext:
    """
    Execute the invariant pipeline on the given input.

    This is the primary entry point for processing user interactions.

    Args:
        raw_input: The user's raw input string
        source: Origin identifier for telemetry
        zone: Zone classification (green/yellow/red)
        force_route: Optional - Force routing to a specific intent (Sprint 6)
                    Used by ratchet_classify() for classification sub-intents
    """
    pipeline = InvariantPipeline()
    return pipeline.run(raw_input, source, zone, force_route)


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

    # Execute stages in strict sequence with exception handling (Purity v2)
    try:
        pipeline._run_telemetry()
        pipeline._run_recognition()
        pipeline._run_compilation()
        pipeline._run_approval()
        pipeline._run_execution()
    except Exception as e:
        # Log failure to telemetry — zero ghost failures
        pipeline._log_pipeline_failure(e)
        pipeline.context.executed = False
        pipeline.context.result = {
            "status": "failed",
            "message": f"Pipeline failure: {str(e)}",
            "error_type": type(e).__name__
        }

    return pipeline.context
