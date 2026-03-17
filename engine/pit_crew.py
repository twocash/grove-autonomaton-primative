"""
pit_crew.py - The Self-Authoring Layer

The Pit Crew enables the system to generate new skills (capabilities)
for itself. This is the most sensitive operation in the Autonomaton
and MUST be strictly gated by Red Zone governance.

CRITICAL: All skill generation requires explicit Red Zone approval
before any files are written to the filesystem.

Sprint 6: Mock code generation with Red Zone governance.
Future: LLM-powered skill authoring.
"""

import re
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

from engine.ux import ask_jidoka
from engine.telemetry import log_event
from engine.profile import get_skills_dir


@dataclass
class SkillDraft:
    """A proposed skill awaiting approval."""
    name: str
    description: str
    skill_md: str
    prompt_md: str
    config_yaml: str
    created_at: str = ""
    approved: bool = False


class PitCrew:
    """
    The Self-Authoring Engine.

    The Pit Crew generates new skills (capabilities) for the Autonomaton.
    All skill creation is gated by Red Zone governance to prevent
    unauthorized modification of system capabilities.

    Usage:
        pit_crew = PitCrew()
        result = pit_crew.propose_and_build_skill("weekly-report", "Generate weekly player reports")
    """

    def __init__(self):
        self.pending_drafts: list[SkillDraft] = []

    def propose_and_build_skill(self, skill_name: str, description: str) -> dict:
        """
        Propose and build a new skill with Red Zone governance.

        This is a Tier 3 / Red Zone operation that:
        1. Generates boilerplate skill files in memory
        2. Requires explicit Red Zone approval via Jidoka
        3. Only writes to filesystem if approved
        4. Logs all outcomes to telemetry

        Args:
            skill_name: Name of the skill (used for directory name)
            description: Description of what the skill does

        Returns:
            Dict with status, message, and optional file paths
        """
        skills_dir = get_skills_dir()

        # Normalize skill name (lowercase, hyphens)
        normalized_name = self._normalize_skill_name(skill_name)

        # Log the proposal
        log_event(
            source="pit_crew_proposal",
            raw_transcript=f"Pit Crew proposal: {normalized_name}",
            zone_context="red",
            inferred={
                "skill_name": normalized_name,
                "description": description,
                "action": "propose"
            }
        )

        # Check if skill already exists
        skill_dir = skills_dir / normalized_name
        if skill_dir.exists():
            log_event(
                source="pit_crew_error",
                raw_transcript=f"Skill already exists: {normalized_name}",
                zone_context="red",
                inferred={"error": "skill_exists"}
            )
            return {
                "status": "error",
                "message": f"Skill '{normalized_name}' already exists in skills/",
                "approved": False
            }

        # Generate boilerplate files in memory
        draft = self._generate_skill_draft(normalized_name, description)

        # RED ZONE GOVERNANCE: Require explicit approval
        approval_granted = self._request_red_zone_approval(draft)

        if not approval_granted:
            # Log rejection
            log_event(
                source="pit_crew_rejection",
                raw_transcript=f"Skill rejected by user: {normalized_name}",
                zone_context="red",
                inferred={
                    "skill_name": normalized_name,
                    "action": "rejected"
                }
            )
            return {
                "status": "rejected",
                "message": f"Skill '{normalized_name}' rejected. No files written.",
                "approved": False
            }

        # Approval granted - write files to filesystem
        created_files = self._write_skill_files(draft, skills_dir)

        # Log successful deployment
        log_event(
            source="pit_crew_deployment",
            raw_transcript=f"Skill deployed: {normalized_name}",
            zone_context="red",
            inferred={
                "skill_name": normalized_name,
                "action": "deployed",
                "files_created": len(created_files)
            }
        )

        return {
            "status": "deployed",
            "message": f"Skill '{normalized_name}' deployed to skills/{normalized_name}/",
            "approved": True,
            "files": [str(f) for f in created_files]
        }

    def _normalize_skill_name(self, name: str) -> str:
        """Normalize skill name for filesystem use."""
        # Lowercase, replace spaces/underscores with hyphens
        normalized = name.lower().strip()
        normalized = re.sub(r'[\s_]+', '-', normalized)
        # Remove non-alphanumeric except hyphens
        normalized = re.sub(r'[^a-z0-9-]', '', normalized)
        # Remove multiple consecutive hyphens
        normalized = re.sub(r'-+', '-', normalized)
        return normalized.strip('-')

    def _generate_skill_draft(self, skill_name: str, description: str) -> SkillDraft:
        """
        Generate boilerplate skill files in memory.

        Creates:
        - SKILL.md: Documentation and usage
        - prompt.md: LLM prompt template
        - config.yaml: Skill configuration (defaults to Yellow Zone)
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        title = skill_name.replace('-', ' ').title()

        # Generate SKILL.md
        skill_md = f"""# {title}

## Description
{description}

## Usage
```
autonomaton> {skill_name}
```

## Zone Classification
**Default Zone:** Yellow (requires user approval)

## Triggers
- Command: `{skill_name}`
- Intent patterns: TBD

## Created
- **Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
- **Author:** Pit Crew (auto-generated)

## Notes
_This skill was auto-generated by the Pit Crew. Review and customize as needed._
"""

        # Generate prompt.md
        prompt_md = f"""# {title} - Prompt Template

## System Context
You are The Autonomaton, executing the "{skill_name}" skill.

## Task
{description}

## Instructions
1. Analyze the user's request
2. Apply the skill logic
3. Return structured output

## Voice Guidelines
- Clear and direct
- Context-aware
- Professional

## Output Format
[Define expected output structure here]

## Examples
[Add example inputs and outputs here]
"""

        # Generate config.yaml (defaults to Yellow Zone)
        config_yaml = f"""# {skill_name} Skill Configuration
# Auto-generated by Pit Crew

name: "{title}"
description: "{description}"

# Governance
zone: yellow
tier: 2
approval: one_thumb

# Triggers
triggers:
  commands:
    - "{skill_name}"
  intents: []

# Dependencies
requires:
  mcp_servers: []
  dock_sources: []

# Metadata
created: "{timestamp}"
author: "pit_crew"
version: "0.1.0"
status: "draft"
"""

        return SkillDraft(
            name=skill_name,
            description=description,
            skill_md=skill_md,
            prompt_md=prompt_md,
            config_yaml=config_yaml,
            created_at=timestamp
        )

    def _request_red_zone_approval(self, draft: SkillDraft) -> bool:
        """
        Request Red Zone approval via Jidoka.

        This is a CRITICAL governance gate. The system cannot modify
        its own capabilities without explicit user approval.
        """
        # Show what will be created
        preview = f"""
Skill Name: {draft.name}
Description: {draft.description}

Files to be created:
  - skills/{draft.name}/SKILL.md (documentation)
  - skills/{draft.name}/prompt.md (LLM template)
  - skills/{draft.name}/config.yaml (zone: yellow)
"""

        result = ask_jidoka(
            context_message=(
                f"RED ZONE: Pit Crew proposes building a new skill: {draft.name}\n"
                f"This will modify system capabilities.\n"
                f"{preview}"
            ),
            options={
                "1": "Approve deployment to skills/",
                "2": "Reject"
            }
        )

        return result == "1"

    def _write_skill_files(self, draft: SkillDraft, skills_dir: Path) -> list[Path]:
        """Write approved skill files to the filesystem."""
        skill_dir = skills_dir / draft.name
        skill_dir.mkdir(parents=True, exist_ok=True)

        created_files = []

        # Write SKILL.md
        skill_md_path = skill_dir / "SKILL.md"
        skill_md_path.write_text(draft.skill_md, encoding="utf-8")
        created_files.append(skill_md_path)

        # Write prompt.md
        prompt_md_path = skill_dir / "prompt.md"
        prompt_md_path.write_text(draft.prompt_md, encoding="utf-8")
        created_files.append(prompt_md_path)

        # Write config.yaml
        config_yaml_path = skill_dir / "config.yaml"
        config_yaml_path.write_text(draft.config_yaml, encoding="utf-8")
        created_files.append(config_yaml_path)

        return created_files

    def list_skills(self) -> list[dict]:
        """List all deployed skills."""
        skills_dir = get_skills_dir()

        if not skills_dir.exists():
            return []

        skills = []
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir():
                config_path = skill_dir / "config.yaml"
                if config_path.exists():
                    skills.append({
                        "name": skill_dir.name,
                        "path": str(skill_dir),
                        "has_config": True
                    })
                else:
                    skills.append({
                        "name": skill_dir.name,
                        "path": str(skill_dir),
                        "has_config": False
                    })

        return skills


# Module-level convenience functions
_pit_crew_instance: Optional[PitCrew] = None


def get_pit_crew() -> PitCrew:
    """Get the shared PitCrew instance."""
    global _pit_crew_instance
    if _pit_crew_instance is None:
        _pit_crew_instance = PitCrew()
    return _pit_crew_instance


def build_skill(skill_name: str, description: str) -> dict:
    """
    Build a new skill with Red Zone governance.

    This is the primary interface for skill creation.
    """
    pit_crew = get_pit_crew()
    return pit_crew.propose_and_build_skill(skill_name, description)


def list_deployed_skills() -> list[dict]:
    """List all deployed skills."""
    pit_crew = get_pit_crew()
    return pit_crew.list_skills()
