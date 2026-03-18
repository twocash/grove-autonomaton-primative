"""
config_loader.py - Profile Configuration Loader

Loads declarative configuration files from the active profile.
Implements Invariant #2: Config Over Code.

Configuration files:
- persona.yaml: System persona (name, role, vibe, constraints)
- routing.config: Intent routing table
- voice.yaml: Voice configuration for content generation
- pillars.yaml: Content pillars
"""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from engine.profile import get_config_dir


@dataclass
class PersonaConfig:
    """
    System persona configuration.

    Defines how the system presents itself in conversational contexts.
    Used by general_chat handler and Conversational Jidoka.
    """
    name: str = "System Operator"
    role: str = "Your sovereign cognitive assistant."
    vibe: str = "Crisp, professional, and highly capable."
    constraints: list[str] = field(default_factory=lambda: [
        "Keep responses brief and operational.",
        "Do not use flowery or subservient language."
    ])

    def build_system_prompt(self, task_context: str = "", include_state: bool = False) -> str:
        """
        Build a system prompt from the persona configuration.

        Args:
            task_context: Additional context for the specific task
            include_state: If True, include the standing context snapshot

        Returns:
            Complete system prompt string
        """
        constraints_text = "\n".join(f"- {c}" for c in self.constraints)

        prompt = f"""You are {self.name}.

Role: {self.role}

Vibe: {self.vibe}

CONSTRAINTS (you MUST follow these):
{constraints_text}"""

        if include_state:
            try:
                from engine.compiler import get_standing_context
                state = get_standing_context()
                if state:
                    prompt += f"\n\n{state}"
            except Exception:
                pass  # Standing context is enrichment, not critical path

        if task_context:
            prompt += f"\n\nTask Context:\n{task_context}"

        return prompt


# Module-level cache
_persona_cache: Optional[PersonaConfig] = None


def _log_config_error(error: Exception, config_file: str, stage: str) -> None:
    """Log config load errors to telemetry (handles circular import)."""
    try:
        from engine.telemetry import log_event
        log_event(
            source="config_loader",
            raw_transcript=config_file,
            zone_context="yellow",
            inferred={"error": str(error), "error_type": type(error).__name__,
                      "config_file": config_file, "stage": stage, "fallback": "defaults"}
        )
    except (ImportError, RuntimeError):
        pass  # Telemetry not available during early bootstrap or no profile set


def load_persona() -> PersonaConfig:
    """
    Load persona.yaml from the active profile.

    Returns PersonaConfig with defaults if file doesn't exist.
    Caches result for performance.
    """
    global _persona_cache

    if _persona_cache is not None:
        return _persona_cache

    try:
        config_dir = get_config_dir()
    except RuntimeError as e:
        _log_config_error(e, "persona.yaml", "profile_resolution")
        return PersonaConfig()

    persona_path = config_dir / "persona.yaml"

    if not persona_path.exists():
        _persona_cache = PersonaConfig()
        return _persona_cache

    try:
        with open(persona_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        _log_config_error(e, "persona.yaml", "yaml_parse")
        _persona_cache = PersonaConfig()
        return _persona_cache

    _persona_cache = PersonaConfig(
        name=data.get("name", "System Operator"),
        role=data.get("role", "Your sovereign cognitive assistant."),
        vibe=data.get("vibe", "Crisp, professional, and highly capable."),
        constraints=data.get("constraints", [
            "Keep responses brief and operational.",
            "Do not use flowery or subservient language."
        ])
    )

    return _persona_cache


def reset_persona_cache() -> None:
    """
    Reset the persona cache.

    Call after profile switch to reload persona.yaml.
    """
    global _persona_cache
    _persona_cache = None


def get_persona() -> PersonaConfig:
    """
    Get the current persona configuration.

    Convenience alias for load_persona().
    """
    return load_persona()
