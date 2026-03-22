"""
handlers.py - Coach Demo Profile Domain Handlers

V-012: Domain handlers extracted from engine/dispatcher.py
These handlers are specific to the coach_demo persona and domain.
Engine-core handlers remain in engine/dispatcher.py.

Architectural Invariant #10: Profile Isolation
The engine is 100% domain-agnostic. Domain logic lives in profiles.
"""

from engine.cognitive_router import RoutingResult
from engine.dispatcher import DispatchResult


# =========================================================================
# Domain Handler Implementations
# =========================================================================

def _handle_session_zero(
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


def _handle_content_engine(
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


def _handle_cortex_batch(
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
        telemetry_events = _load_recent_telemetry(limit=50)

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
            approval_context=_format_kaizen_proposals(result.get("kaizen_proposals", []))
        )

    elif lens == "ratchet_analysis":
        # Lens 4: Ratchet Analysis
        llm_telemetry = _load_llm_telemetry(limit=100)
        routing_patterns = _aggregate_routing_patterns()

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
            approval_context=_format_ratchet_proposals(result.get("ratchet_proposals", []))
        )

    elif lens == "evolution_analysis":
        # Lens 5: Evolution / Personal Product Manager
        telemetry_events = _load_recent_telemetry(limit=50)
        exhaust_board = _load_exhaust_board()
        vision_board = _load_vision_board()

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
            approval_context=_format_evolution_proposals(result.get("evolution_proposals", []))
        )

    else:
        return DispatchResult(
            success=False,
            message=f"Unknown cortex lens: {lens}",
            data={"type": "cortex_error", "error": "unknown_lens"}
        )


def _handle_vision_capture(
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


def _handle_plan_update(
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


# =========================================================================
# Internal Startup Handlers (purity-audit-v1)
# These were moved from autonomaton.py to route through the pipeline.
# =========================================================================

def _handle_welcome_card(
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


# =========================================================================
# Helper Methods (support cortex_batch and other domain handlers)
# =========================================================================

def _load_recent_telemetry(limit: int = 50) -> list[dict]:
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


def _load_llm_telemetry(limit: int = 100) -> list[dict]:
    """Load LLM-specific telemetry for ratchet analysis."""
    # Filter telemetry for LLM calls
    all_events = _load_recent_telemetry(limit=limit * 2)
    return [
        e for e in all_events
        if e.get("intent", "").startswith(("cortex_", "mcp_", "skill_"))
        or "model" in e
    ][-limit:]


def _aggregate_routing_patterns() -> list[dict]:
    """Aggregate routing patterns for ratchet analysis."""
    from collections import defaultdict

    events = _load_recent_telemetry(limit=500)

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


def _load_exhaust_board() -> str:
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


def _load_vision_board() -> str:
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


def _format_kaizen_proposals(proposals: list[dict]) -> str:
    """Format Kaizen proposals for approval display."""
    if not proposals:
        return "No Kaizen proposals."

    lines = ["KAIZEN PROPOSALS:"]
    for p in proposals:
        lines.append(f"  [{p.get('priority', '?').upper()}] {p.get('proposal', 'Unknown')}")
        lines.append(f"        Trigger: {p.get('trigger', '?')}")
    return "\n".join(lines)


def _format_ratchet_proposals(proposals: list[dict]) -> str:
    """Format Ratchet proposals for approval display."""
    if not proposals:
        return "No Ratchet proposals."

    lines = ["RATCHET DEMOTIONS:"]
    for p in proposals:
        lines.append(f"  [{p.get('intent', '?')}] {p.get('proposed_action', 'Unknown')}")
        lines.append(f"        Confidence: {p.get('confidence', 0):.0%}, Samples: {p.get('sample_count', 0)}")
    return "\n".join(lines)


def _format_evolution_proposals(proposals: list[dict]) -> str:
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
# Profile Handler Registration
# =========================================================================

def register(dispatcher):
    """
    Register coach_demo domain handlers with the dispatcher.

    Called by autonomaton.py after profile is set.
    Uses dispatcher.register_handler() to add domain-specific handlers.
    """
    dispatcher.register_handler("session_zero_handler", _handle_session_zero)
    dispatcher.register_handler("content_engine", _handle_content_engine)
    dispatcher.register_handler("cortex_batch", _handle_cortex_batch)
    dispatcher.register_handler("vision_capture", _handle_vision_capture)
    dispatcher.register_handler("plan_update", _handle_plan_update)
    dispatcher.register_handler("regenerate_plan", _handle_regenerate_plan)
    dispatcher.register_handler("fill_entity_gap", _handle_fill_entity_gap)
    dispatcher.register_handler("welcome_card", _handle_welcome_card)
    dispatcher.register_handler("startup_brief", _handle_startup_brief)
    dispatcher.register_handler("generate_plan", _handle_generate_plan)
