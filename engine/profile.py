"""
profile.py - Profile Management System

Manages the active profile context for the Autonomaton.
The profile determines which domain-specific directories (config, dock,
entities, skills, telemetry, queue, output) are used at runtime.

This module implements "Protocol over Implementation" - the invariant
engine code remains unchanged while domain payloads are swapped via profiles.
"""

from pathlib import Path
from typing import Optional


# =========================================================================
# Module Constants
# =========================================================================

# The profiles directory (relative to repo root)
PROFILES_DIR = Path(__file__).parent.parent / "profiles"


# Global profile state
_active_profile: Optional[str] = None
_profile_base_path: Optional[Path] = None

# V-015: Session-scoped enrichment mode (Learning Mode vs Free Mode)
# Set by startup mode selection, not persisted to disk.
_session_enrichment_enabled: Optional[bool] = None


def set_profile(profile_name: str, repo_root: Optional[Path] = None) -> None:
    """
    Set the active profile for this session.

    Args:
        profile_name: Name of the profile (e.g., 'reference')
        repo_root: Repository root path (defaults to parent of engine/)
    """
    global _active_profile, _profile_base_path

    if repo_root is None:
        repo_root = Path(__file__).parent.parent

    _active_profile = profile_name
    _profile_base_path = repo_root / "profiles" / profile_name

    # Ensure profile directory exists
    _profile_base_path.mkdir(parents=True, exist_ok=True)

    # Reset config caches when profile changes
    try:
        from engine.config_loader import reset_persona_cache
        reset_persona_cache()
    except ImportError:
        pass  # config_loader not available yet


def get_profile() -> str:
    """Get the active profile name."""
    if _active_profile is None:
        raise RuntimeError(
            "No profile set. Call set_profile() before using the engine."
        )
    return _active_profile


def get_profile_path() -> Path:
    """Get the base path for the active profile."""
    if _profile_base_path is None:
        raise RuntimeError(
            "No profile set. Call set_profile() before using the engine."
        )
    return _profile_base_path


# =========================================================================
# Profile-Aware Path Accessors
# =========================================================================

def get_config_dir() -> Path:
    """Get the config directory for the active profile."""
    return get_profile_path() / "config"


def get_dock_dir() -> Path:
    """Get the dock directory for the active profile."""
    return get_profile_path() / "dock"


def get_skills_dir() -> Path:
    """Get the skills directory for the active profile."""
    return get_profile_path() / "skills"


def get_telemetry_dir() -> Path:
    """Get the telemetry directory for the active profile."""
    return get_profile_path() / "telemetry"


def get_output_dir() -> Path:
    """Get the output directory for the active profile."""
    return get_profile_path() / "output"


def get_telemetry_path() -> Path:
    """Get the path to telemetry.jsonl for the active profile."""
    return get_telemetry_dir() / "telemetry.jsonl"


def list_available_profiles(repo_root: Optional[Path] = None) -> list[str]:
    """List all available profiles."""
    if repo_root is None:
        repo_root = Path(__file__).parent.parent

    profiles_dir = repo_root / "profiles"
    if not profiles_dir.exists():
        return []

    return [d.name for d in profiles_dir.iterdir() if d.is_dir()]


# =========================================================================
# V-015: Session Enrichment State
# =========================================================================

def set_session_enrichment(enabled: bool) -> None:
    """
    Set session-scoped enrichment mode (Learning Mode vs Free Mode).

    V-015: This is set by startup mode selection and persists for the session.
    Not written to disk — the operator controls persistence via routing.config.
    """
    global _session_enrichment_enabled
    _session_enrichment_enabled = enabled


def get_session_enrichment() -> Optional[bool]:
    """
    Get session-scoped enrichment override.

    Returns:
        True: Learning Mode (enrichment enabled)
        False: Free Mode (enrichment disabled)
        None: No session override — use routing.config default
    """
    return _session_enrichment_enabled
