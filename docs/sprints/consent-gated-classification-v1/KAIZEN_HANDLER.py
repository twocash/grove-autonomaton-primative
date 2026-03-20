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
            "message": "Go ahead \u2014 I'm listening."
        }
