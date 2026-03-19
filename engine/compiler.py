"""
compiler.py - Compilation Stage Utilities

Sprint 7: Privacy Mask for content generation.

The Privacy Mask ensures that when working with minors, real names
are never sent to external LLMs. Entity names are swapped with their
public_alias before any prompt is dispatched externally.
"""

import re
from pathlib import Path
from typing import Dict


def load_entity_aliases() -> Dict[str, str]:
    """
    Load all entity names and their public aliases from the entities directory.

    Scans all entity markdown files for name and public_alias fields.

    Returns:
        Dict mapping real names to their public aliases
    """
    # Import inside function to support monkeypatching in tests
    from engine.profile import get_entities_dir

    aliases = {}
    entities_dir = get_entities_dir()

    if not entities_dir.exists():
        return aliases

    # Scan all entity subdirectories (types from entity_config.yaml)
    for subdir in entities_dir.iterdir():
        if subdir.is_dir() and not subdir.name.startswith('.'):
            for entity_file in subdir.glob("*.md"):
                name, alias = _extract_name_and_alias(entity_file)
                if name:
                    aliases[name] = alias

    return aliases


def _extract_name_and_alias(filepath: Path) -> tuple[str, str]:
    """
    Extract the entity name and public_alias from a markdown entity file.

    Args:
        filepath: Path to the entity markdown file

    Returns:
        Tuple of (name, public_alias). If no alias found, uses default.
    """
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return ("", "")

    name = ""
    alias = ""

    # Extract name from the first H1 header
    name_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if name_match:
        name = name_match.group(1).strip()

    # Extract public_alias from profile section
    alias_match = re.search(r'\*\*public_alias:\*\*\s*(.+)$', content, re.MULTILINE)
    if alias_match:
        alias = alias_match.group(1).strip()
    else:
        # Default alias based on entity type from config
        from engine.config_loader import load_entity_config
        entity_config = load_entity_config()
        entity_types = entity_config.get("entity_types", [])

        # Build mapping from plural folder name to default alias
        alias_map = {t["plural"]: t.get("default_alias", "an entity") for t in entity_types}

        # Check filepath against known entity type folders
        path_str = str(filepath)
        alias = "an entity"  # Fallback
        for plural, default_alias in alias_map.items():
            if plural in path_str:
                alias = default_alias
                break

    return (name, alias)


def apply_privacy_mask(raw_text: str) -> str:
    """
    Apply the privacy mask to raw text before sending to external LLMs.

    Replaces all known entity names with their public aliases.
    This is the final step before any content generation prompt is dispatched.

    Args:
        raw_text: The raw text that may contain entity names

    Returns:
        Text with all entity names replaced by their aliases
    """
    aliases = load_entity_aliases()

    if not aliases:
        return raw_text

    masked_text = raw_text

    # Sort by name length (longest first) to handle "Marcus Henderson" before "Marcus"
    sorted_names = sorted(aliases.keys(), key=len, reverse=True)

    for name in sorted_names:
        alias = aliases[name]
        # Replace full name (case-insensitive)
        pattern = re.compile(re.escape(name), re.IGNORECASE)
        masked_text = pattern.sub(alias, masked_text)

        # Also replace first name only if it's a multi-word name
        parts = name.split()
        if len(parts) > 1:
            first_name = parts[0]
            # Only replace standalone first name (word boundary)
            first_pattern = re.compile(r'\b' + re.escape(first_name) + r'\b', re.IGNORECASE)
            masked_text = first_pattern.sub(alias, masked_text)

    return masked_text


def mask_content_for_llm(prompt: str) -> str:
    """
    Convenience wrapper for applying privacy mask to LLM prompts.

    This should be called as the final step before calling llm_client.

    Args:
        prompt: The full prompt to be sent to the LLM

    Returns:
        Privacy-masked prompt safe for external transmission
    """
    return apply_privacy_mask(prompt)


# ============================================================================
# Standing Context for Chief of Staff Awareness (Sprint: chief-of-staff-v1)
# ============================================================================

from typing import Optional

# Module-level standing context cache
_standing_context: Optional[str] = None


def gather_state_snapshot() -> str:
    """
    Assemble a compact state snapshot for persistent persona awareness.

    Reads dock, entities, content pipeline, skills, and session recency.
    Target: 300-500 words — enough for specificity without bloating tokens.
    """
    from engine.profile import get_dock_dir, get_entities_dir, get_skills_dir, get_output_dir
    from engine.telemetry import log_event

    sections = []

    # --- Dock Summary ---
    try:
        dock_dir = get_dock_dir()
        dock_files = sorted(dock_dir.glob("*.md")) if dock_dir.exists() else []

        for md_file in dock_files:
            try:
                content = md_file.read_text(encoding="utf-8")
                sections.append(f"[{md_file.stem}]\n{content[:800]}")
            except Exception:
                sections.append(f"[{md_file.stem}] (unreadable)")
    except Exception as e:
        log_event(
            source="state_snapshot",
            raw_transcript="dock_read",
            zone_context="yellow",
            inferred={"error": str(e), "stage": "dock_read"}
        )

    # --- Structured Plan Summary (Sprint 5) ---
    try:
        plan_path = dock_dir / "system" / "structured-plan.md"
        if plan_path.exists():
            plan_content = plan_path.read_text(encoding="utf-8")
            # Extract key sections for compact summary
            # Include first 1200 chars which covers Active Goals & Progress
            sections.append(f"[structured-plan]\n{plan_content[:1200]}")
    except Exception as e:
        log_event(
            source="state_snapshot",
            raw_transcript="structured_plan_read",
            zone_context="yellow",
            inferred={"error": str(e), "stage": "structured_plan_read"}
        )

    # --- Entity Inventory ---
    try:
        entities_dir = get_entities_dir()
        if entities_dir.exists():
            for type_dir in sorted(entities_dir.iterdir()):
                if type_dir.is_dir() and not type_dir.name.startswith('.'):
                    files = list(type_dir.glob("*.md"))
                    names = [f.stem for f in files]
                    sections.append(
                        f"[entities/{type_dir.name}] {len(files)} entries: {', '.join(names[:15])}"
                    )
    except Exception as e:
        log_event(
            source="state_snapshot",
            raw_transcript="entity_inventory",
            zone_context="yellow",
            inferred={"error": str(e), "stage": "entity_inventory"}
        )

    # --- Content Pipeline ---
    try:
        entities_dir = get_entities_dir()
        seeds_dir = entities_dir / "content-seeds" if entities_dir.exists() else None
        output_dir = get_output_dir() / "content"

        if seeds_dir and seeds_dir.exists():
            seeds = [f.stem for f in seeds_dir.glob("*.md")]
            compiled_files = [f.stem for f in output_dir.glob("*.md")] if output_dir.exists() else []

            compiled_seeds = set()
            for c in compiled_files:
                parts = c.split("-", 1)
                if len(parts) > 1:
                    compiled_seeds.add(parts[1])

            uncompiled = [s for s in seeds if s not in compiled_seeds]
            sections.append(
                f"[content-pipeline] {len(seeds)} seeds, "
                f"{len(compiled_seeds)} compiled, "
                f"{len(uncompiled)} ready"
                + (f": {', '.join(uncompiled[:5])}" if uncompiled else "")
            )
    except Exception as e:
        log_event(
            source="state_snapshot",
            raw_transcript="content_pipeline",
            zone_context="yellow",
            inferred={"error": str(e), "stage": "content_pipeline"}
        )

    # --- Skills Inventory ---
    try:
        skills_dir = get_skills_dir()
        if skills_dir.exists():
            skill_names = []
            for skill_dir in sorted(skills_dir.iterdir()):
                if skill_dir.is_dir():
                    has_config = (skill_dir / "config.yaml").exists()
                    has_prompt = (skill_dir / "prompt.md").exists()
                    status = "ready" if (has_config and has_prompt) else "partial"
                    skill_names.append(f"{skill_dir.name}({status})")
            sections.append(f"[skills] {', '.join(skill_names)}")
    except Exception as e:
        log_event(
            source="state_snapshot",
            raw_transcript="skills_inventory",
            zone_context="yellow",
            inferred={"error": str(e), "stage": "skills_inventory"}
        )

    # --- Session Recency ---
    try:
        from engine.telemetry import read_recent_events
        recent = read_recent_events(limit=5)
        if not recent:
            sections.append("[session] Fresh session — no prior activity.")
        else:
            last_time = recent[-1].get("timestamp", "unknown")
            intents = [e.get("intent", "?") for e in recent if e.get("intent")]
            sections.append(f"[session] Last: {last_time}. Recent: {', '.join(intents[-5:])}")
    except Exception:
        sections.append("[session] Telemetry unavailable.")

    # --- Entity Gaps (Sprint 5) ---
    try:
        gaps_summary = get_entity_gaps_summary()
        if gaps_summary:
            sections.append(gaps_summary)
    except Exception as e:
        log_event(
            source="state_snapshot",
            raw_transcript="entity_gaps",
            zone_context="yellow",
            inferred={"error": str(e), "stage": "entity_gaps"}
        )

    if not sections:
        return ""

    return "STANDING CONTEXT (current system state):\n" + "\n\n".join(sections)


def get_standing_context(force_refresh: bool = False) -> str:
    """Get cached standing context, assembling on first call."""
    global _standing_context
    if _standing_context is None or force_refresh:
        _standing_context = gather_state_snapshot()
    return _standing_context


def reset_standing_context() -> None:
    """Reset cache (call after profile switch or dock changes)."""
    global _standing_context
    _standing_context = None


# ============================================================================
# Entity Gap Detection (Sprint 5: The Living Plan)
# ============================================================================

def detect_entity_gaps() -> list[dict]:
    """
    Detect missing entity fields required by handlers.

    Cross-references:
    - Handler requirements (inferred from common patterns)
    - Entity fields (from entities/*.md files)

    Returns:
        List of gap dicts: {"entity": "...", "missing": "...", "handler": "...", "priority": "..."}
    """
    from engine.profile import get_entities_dir
    import re

    gaps = []
    entities_dir = get_entities_dir()

    if not entities_dir.exists():
        return gaps

    # Load required fields from config
    from engine.config_loader import load_entity_config
    entity_config = load_entity_config()
    required_entity_fields = entity_config.get("required_entity_fields", {})
    type_map = {t["name"]: t["plural"] for t in entity_config.get("entity_types", [])}

    # Build required_fields dict with patterns from config
    required_fields = {}
    for entity_type, fields in required_entity_fields.items():
        plural = type_map.get(entity_type, f"{entity_type}s")
        required_fields[plural] = {}
        for field in fields:
            # Generate patterns for field detection
            required_fields[plural][field] = {
                "patterns": [rf"\*\*{field}:\*\*", rf"{field}:"],
                "handler": "entity_report",
                "priority": "low"
            }

    # Scan entity directories
    for entity_type, fields in required_fields.items():
        type_dir = entities_dir / entity_type
        if not type_dir.exists():
            continue

        for entity_file in type_dir.glob("*.md"):
            try:
                content = entity_file.read_text(encoding="utf-8").lower()
                entity_name = entity_file.stem

                for field_name, field_config in fields.items():
                    # Check if any of the patterns match
                    field_present = any(
                        re.search(pattern, content, re.IGNORECASE)
                        for pattern in field_config["patterns"]
                    )

                    if not field_present:
                        gaps.append({
                            "entity": f"{entity_type}/{entity_name}",
                            "entity_file": str(entity_file),
                            "missing": field_name,
                            "handler": field_config["handler"],
                            "priority": field_config["priority"]
                        })

            except Exception:
                continue

    # Sort by priority (high first)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    gaps.sort(key=lambda g: priority_order.get(g.get("priority", "low"), 3))

    return gaps


def get_entity_gaps_summary() -> str:
    """
    Get a concise summary of entity gaps for standing context.

    Returns:
        String summary suitable for inclusion in standing context.
    """
    gaps = detect_entity_gaps()

    if not gaps:
        return ""

    # Group by priority
    high = [g for g in gaps if g.get("priority") == "high"]
    medium = [g for g in gaps if g.get("priority") == "medium"]

    summary_parts = []

    if high:
        entities = [g["entity"].split("/")[-1] for g in high]
        summary_parts.append(f"HIGH: {', '.join(entities[:5])} missing contact info")

    if medium:
        entities = [g["entity"].split("/")[-1] for g in medium]
        summary_parts.append(f"MEDIUM: {', '.join(entities[:5])} missing data")

    if summary_parts:
        return "[entity-gaps] " + "; ".join(summary_parts)

    return ""


# ============================================================================
# Structured Plan Generation (Sprint 5: The Living Plan)
# ============================================================================

def generate_structured_plan() -> str:
    """
    Synthesize structured plan from dock + entities + telemetry.

    Uses Tier 2 (Sonnet) to create a human-readable trajectory document
    that tracks goal progress, identifies data gaps, and surfaces stale items.

    Returns:
        Markdown string ready for operator approval and file write.
        Empty string on failure.
    """
    from engine.profile import get_dock_dir, get_entities_dir
    from engine.llm_client import call_llm
    from engine.telemetry import log_event, read_recent_events

    dock_dir = get_dock_dir()
    entities_dir = get_entities_dir()

    # Gather inputs for synthesis
    inputs = {}

    # Load goals.md
    goals_path = dock_dir / "goals.md"
    if goals_path.exists():
        try:
            inputs["goals"] = goals_path.read_text(encoding="utf-8")
        except Exception as e:
            log_event(
                source="plan_generation",
                raw_transcript="goals_read",
                zone_context="yellow",
                inferred={"error": str(e), "stage": "goals_read"}
            )
            inputs["goals"] = ""
    else:
        inputs["goals"] = ""

    # Load seasonal-context.md
    seasonal_path = dock_dir / "seasonal-context.md"
    if seasonal_path.exists():
        try:
            inputs["seasonal"] = seasonal_path.read_text(encoding="utf-8")
        except Exception:
            inputs["seasonal"] = ""
    else:
        inputs["seasonal"] = ""

    # Entity inventory
    entity_summary = []
    if entities_dir.exists():
        for type_dir in sorted(entities_dir.iterdir()):
            if type_dir.is_dir() and not type_dir.name.startswith('.'):
                files = list(type_dir.glob("*.md"))
                names = [f.stem for f in files]
                entity_summary.append(f"{type_dir.name}: {', '.join(names)}")
    inputs["entities"] = "\n".join(entity_summary) if entity_summary else "No entities yet"

    # Content pipeline status
    seeds_dir = entities_dir / "content-seeds" if entities_dir.exists() else None
    if seeds_dir and seeds_dir.exists():
        seeds = list(seeds_dir.glob("*.md"))
        inputs["content_seeds"] = f"{len(seeds)} content seeds"
    else:
        inputs["content_seeds"] = "No content seeds"

    # Recent telemetry summary
    try:
        recent = read_recent_events(limit=20)
        intents = [e.get("intent", "?") for e in recent if e.get("intent")]
        inputs["recent_activity"] = f"Recent intents: {', '.join(intents[-10:])}" if intents else "No recent activity"
    except Exception:
        inputs["recent_activity"] = "Telemetry unavailable"

    # Vision board aspirations
    vision_path = dock_dir / "system" / "vision-board.md"
    if vision_path.exists():
        try:
            inputs["vision"] = vision_path.read_text(encoding="utf-8")
        except Exception:
            inputs["vision"] = ""
    else:
        inputs["vision"] = ""

    # Build synthesis prompt
    prompt = f"""Generate a Structured Plan document that synthesizes the operator's goals with current system state.

GOALS DOCUMENT:
{inputs['goals'][:2000]}

SEASONAL CONTEXT:
{inputs['seasonal'][:1000]}

ENTITY INVENTORY:
{inputs['entities']}

CONTENT PIPELINE:
{inputs['content_seeds']}

RECENT ACTIVITY:
{inputs['recent_activity']}

VISION BOARD (aspirations):
{inputs['vision'][:500]}

Generate a markdown document with these EXACT sections:

# Structured Plan
> Last updated: [today's date] (auto-generated, operator-approved)

## Active Goals & Progress
For each goal in the goals document:
- **Target:** The goal target
- **Current:** Best estimate of current state
- **Trajectory:** On pace / behind / ahead
- **Observation:** What the data shows
- **Recommended action:** Specific next step

## Data Gaps (System Needs)
Table of missing entity data that blocks handlers:
| What's Missing | Why It Matters | How to Fix |

## Stale Items
Goals or vision items not touched recently

## What's Working
Positive patterns from telemetry and content pipeline

## Next Actions (Prioritized)
1-4 prioritized actions based on urgency

End with: *This plan is maintained by the Context Gardener...*

Be specific. Reference actual entity names and goals. This must be human-readable and correctable.

Generate the plan now:"""

    try:
        response = call_llm(
            prompt=prompt,
            tier=2,  # Sonnet for synthesis quality
            intent="plan_generation"
        )
        return response.strip()
    except Exception as e:
        log_event(
            source="plan_generation",
            raw_transcript="llm_synthesis",
            zone_context="yellow",
            inferred={"error": str(e), "error_type": type(e).__name__, "stage": "synthesis"}
        )
        return ""


def write_structured_plan(content: str) -> bool:
    """
    Write structured plan to dock/system/structured-plan.md.

    This should only be called AFTER operator approval (Yellow Zone).

    Args:
        content: The plan markdown content to write

    Returns:
        True if written successfully, False otherwise
    """
    from engine.profile import get_dock_dir
    from engine.telemetry import log_event

    dock_dir = get_dock_dir()
    plan_path = dock_dir / "system" / "structured-plan.md"

    # Ensure directory exists
    plan_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import hashlib
        plan_hash = hashlib.md5(content.encode()).hexdigest()[:8]

        plan_path.write_text(content, encoding="utf-8")
        log_event(
            source="plan_write",
            raw_transcript="structured-plan.md",
            zone_context="yellow",
            inferred={
                "status": "written",
                "length": len(content),
                "plan_hash": plan_hash,
                "event_type": "plan_updated"
            }
        )
        return True
    except Exception as e:
        log_event(
            source="plan_write",
            raw_transcript="structured-plan.md",
            zone_context="yellow",
            inferred={"error": str(e), "error_type": type(e).__name__}
        )
        return False


def get_structured_plan() -> str:
    """
    Read the current structured plan from dock.

    Returns:
        Plan content as string, or empty string if not found.
    """
    from engine.profile import get_dock_dir

    dock_dir = get_dock_dir()
    plan_path = dock_dir / "system" / "structured-plan.md"

    if plan_path.exists():
        try:
            return plan_path.read_text(encoding="utf-8")
        except Exception:
            return ""
    return ""
