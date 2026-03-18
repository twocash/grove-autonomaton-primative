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

    # Scan all entity subdirectories (players, parents, clients, etc.)
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
        # Default alias based on entity type
        if "players" in str(filepath):
            alias = "a player"
        elif "parents" in str(filepath):
            alias = "a parent"
        else:
            alias = "a team member"

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
