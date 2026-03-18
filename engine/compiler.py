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
