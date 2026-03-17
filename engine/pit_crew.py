"""
pit_crew.py - The Self-Authoring Layer

The Pit Crew enables the system to generate new skills (capabilities)
for itself. This is the most sensitive operation in the Autonomaton
and MUST be strictly gated by Red Zone governance.

CRITICAL: All skill generation requires explicit Red Zone approval
before any files are written to the filesystem.

Sprint 4: LLM-powered skill authoring with self-registration.
The Pit Crew is now an Autonomatonic sub-system that:
1. Uses Tier 2 (Sonnet) to generate functional skill artifacts
2. Displays generated code in Red Zone Jidoka for approval
3. Self-registers new skills into routing.config
4. Triggers hot reload for immediate invocation
"""

import re
import json
import yaml
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

from engine.ux import ask_jidoka
from engine.telemetry import log_event
from engine.profile import get_skills_dir, get_config_dir


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

        # Register skill in routing.config for immediate invocation
        registration_success = self._register_skill_in_routing(draft)

        # Log successful deployment
        log_event(
            source="pit_crew_deployment",
            raw_transcript=f"Skill deployed: {normalized_name}",
            zone_context="red",
            inferred={
                "skill_name": normalized_name,
                "action": "deployed",
                "files_created": len(created_files),
                "registered": registration_success
            }
        )

        status_msg = f"Skill '{normalized_name}' deployed to skills/{normalized_name}/"
        if registration_success:
            status_msg += f" and registered in routing.config. You can now invoke it with '{normalized_name}'."
        else:
            status_msg += " (Warning: routing registration failed - manual registration required)"

        return {
            "status": "deployed",
            "message": status_msg,
            "approved": True,
            "registered": registration_success,
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
        Generate skill files using LLM (Tier 2 - Sonnet).

        Sprint 4: Uses LLM to create functional skill artifacts:
        - config.yaml: Valid YAML with triggers, zone, handler
        - prompt.md: Actual LLM prompt for skill execution
        - SKILL.md: Documentation and usage guide

        The LLM prompt includes context from:
        - User's skill description
        - Existing routing.config format (for consistency)
        - Voice and pillar guidelines
        """
        from engine.llm_client import call_llm

        timestamp = datetime.now(timezone.utc).isoformat()
        title = skill_name.replace('-', ' ').title()

        # Load context for LLM
        routing_context = self._load_routing_context()
        voice_context = self._load_voice_context()
        pillar_context = self._load_pillar_context()

        # Build the generation prompt
        prompt = f"""You are the Pit Crew, a sub-system of The Autonomaton that generates new skill capabilities.

Generate a complete, functional skill based on this request:

SKILL NAME: {skill_name}
SKILL TITLE: {title}
DESCRIPTION: {description}

You must return a JSON object with exactly three keys:
- "config_yaml": The skill configuration in YAML format
- "prompt_md": The LLM prompt template for executing this skill
- "skill_md": The documentation markdown file

ROUTING CONFIG FORMAT (follow this structure for consistency):
{routing_context}

VOICE GUIDELINES:
{voice_context}

CONTENT PILLARS:
{pillar_context}

REQUIREMENTS FOR config_yaml:
- Must be valid YAML
- Must include: name, description, zone (yellow default), tier (2 default)
- Must include triggers.commands with at least the skill name
- Must include triggers.intents for natural language patterns
- Handler should be "skill_executor" with handler_args.skill_name set

REQUIREMENTS FOR prompt_md:
- Must include System Context explaining the skill's role
- Must include clear Instructions for the LLM
- Must include Voice Guidelines matching the profile
- Must include Output Format specification
- Should include relevant Examples

REQUIREMENTS FOR skill_md:
- Must document the skill usage
- Must list triggers and zone classification
- Must explain dependencies and requirements

Return ONLY valid JSON with the three keys. No markdown code blocks, no explanations.

Example structure:
{{"config_yaml": "name: ...\\nzone: yellow\\n...", "prompt_md": "# Title\\n\\n## System Context\\n...", "skill_md": "# Title\\n\\n## Description\\n..."}}
"""

        try:
            response = call_llm(
                prompt=prompt,
                tier=2,  # Use Sonnet for quality skill generation
                intent="pit_crew_skill_generation",
                max_tokens=4000
            )

            # Parse the JSON response
            artifacts = json.loads(response)

            config_yaml = artifacts.get("config_yaml", "")
            prompt_md = artifacts.get("prompt_md", "")
            skill_md = artifacts.get("skill_md", "")

            # Validate we got content
            if not config_yaml or not prompt_md or not skill_md:
                raise ValueError("LLM returned incomplete artifacts")

            # Ensure config_yaml has required fields
            config_yaml = self._ensure_config_fields(config_yaml, skill_name, description, timestamp)

            return SkillDraft(
                name=skill_name,
                description=description,
                skill_md=skill_md,
                prompt_md=prompt_md,
                config_yaml=config_yaml,
                created_at=timestamp
            )

        except json.JSONDecodeError as e:
            log_event(
                source="pit_crew_error",
                raw_transcript=f"LLM returned invalid JSON: {str(e)}",
                zone_context="red",
                inferred={"error": "json_parse_failed", "skill_name": skill_name}
            )
            raise ValueError(f"Failed to parse LLM response as JSON: {e}")

        except Exception as e:
            log_event(
                source="pit_crew_error",
                raw_transcript=f"Skill generation failed: {str(e)}",
                zone_context="red",
                inferred={"error": str(e), "skill_name": skill_name}
            )
            raise

    def _load_routing_context(self) -> str:
        """Load example routing.config entries for context."""
        try:
            config_path = get_config_dir() / "routing.config"
            if config_path.exists():
                content = config_path.read_text(encoding="utf-8")
                # Extract a sample route for format reference
                lines = content.split('\n')
                sample = []
                in_route = False
                for line in lines:
                    if line.strip().startswith('session_zero:'):
                        in_route = True
                    if in_route:
                        sample.append(line)
                        if len(sample) > 15:
                            break
                return '\n'.join(sample) if sample else "tier: 2\nzone: yellow\ndomain: system"
        except Exception:
            pass
        return "tier: 2\nzone: yellow\ndomain: system"

    def _load_voice_context(self) -> str:
        """Load voice.yaml for LLM context."""
        try:
            voice_path = get_config_dir() / "voice.yaml"
            if voice_path.exists():
                content = voice_path.read_text(encoding="utf-8")
                # Return first ~30 lines for context
                lines = content.split('\n')[:30]
                return '\n'.join(lines)
        except Exception:
            pass
        return "tone: professional\nstyle: clear and direct"

    def _load_pillar_context(self) -> str:
        """Load pillars.yaml for LLM context."""
        try:
            pillar_path = get_config_dir() / "pillars.yaml"
            if pillar_path.exists():
                content = pillar_path.read_text(encoding="utf-8")
                # Return first ~20 lines for context
                lines = content.split('\n')[:20]
                return '\n'.join(lines)
        except Exception:
            pass
        return "Focus on the domain-specific context."

    def _ensure_config_fields(self, config_yaml: str, skill_name: str, description: str, timestamp: str) -> str:
        """Ensure config.yaml has all required fields."""
        try:
            config = yaml.safe_load(config_yaml)
            if not isinstance(config, dict):
                config = {}

            # Ensure required fields
            config.setdefault("name", skill_name.replace('-', ' ').title())
            config.setdefault("description", description)
            config.setdefault("zone", "yellow")
            config.setdefault("tier", 2)
            config.setdefault("triggers", {})
            config["triggers"].setdefault("commands", [skill_name])
            config["triggers"].setdefault("intents", [])
            config.setdefault("handler", "skill_executor")
            config.setdefault("handler_args", {"skill_name": skill_name})
            config.setdefault("created", timestamp)
            config.setdefault("author", "pit_crew")

            return yaml.dump(config, default_flow_style=False, sort_keys=False)
        except Exception:
            # Return original if parsing fails
            return config_yaml

    def _request_red_zone_approval(self, draft: SkillDraft) -> bool:
        """
        Request Red Zone approval via Jidoka.

        Sprint 4: Displays the actual generated code/config for review.

        This is a CRITICAL governance gate. The system cannot modify
        its own capabilities without explicit user approval.
        """
        # Extract zone from config for display
        try:
            config = yaml.safe_load(draft.config_yaml)
            zone = config.get("zone", "yellow")
            triggers = config.get("triggers", {}).get("commands", [draft.name])
        except Exception:
            zone = "yellow"
            triggers = [draft.name]

        # Extract prompt summary (first few sections)
        prompt_lines = draft.prompt_md.split('\n')
        prompt_summary = '\n'.join(prompt_lines[:20])
        if len(prompt_lines) > 20:
            prompt_summary += f"\n... [{len(prompt_lines) - 20} more lines]"

        # Build detailed preview with actual generated code
        preview = f"""
================================================================================
SKILL: {draft.name}
DESCRIPTION: {draft.description}
================================================================================

--- GENERATED config.yaml ---
{draft.config_yaml}
--- END config.yaml ---

--- GENERATED prompt.md (summary) ---
{prompt_summary}
--- END prompt.md ---

ACTIONS UPON APPROVAL:
1. Create skills/{draft.name}/ directory
2. Write config.yaml (zone: {zone})
3. Write prompt.md (LLM execution template)
4. Write SKILL.md (documentation)
5. Register in routing.config with triggers: {triggers}
6. Hot reload CognitiveRouter for immediate invocation

"""

        result = ask_jidoka(
            context_message=(
                f"RED ZONE: Pit Crew proposes building a new skill: {draft.name}\n"
                f"This will MODIFY SYSTEM CAPABILITIES.\n"
                f"Review the generated code below before approving.\n"
                f"{preview}"
            ),
            options={
                "1": "APPROVE: Deploy skill and register in routing",
                "2": "REJECT: Cancel without writing files"
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

    def _register_skill_in_routing(self, draft: SkillDraft) -> bool:
        """
        Register the new skill in routing.config for immediate invocation.

        Sprint 4: Self-registration enables the skill to be invoked
        immediately after deployment without restarting.

        Args:
            draft: The approved skill draft

        Returns:
            True if registration successful, False otherwise
        """
        try:
            config_path = get_config_dir() / "routing.config"

            if not config_path.exists():
                log_event(
                    source="pit_crew_error",
                    raw_transcript="routing.config not found",
                    zone_context="red",
                    inferred={"error": "routing_config_not_found"}
                )
                return False

            # Load existing config
            content = config_path.read_text(encoding="utf-8")
            config = yaml.safe_load(content) or {}

            if "routes" not in config:
                config["routes"] = {}

            # Parse the skill config to extract routing info
            skill_config = yaml.safe_load(draft.config_yaml) or {}

            # Create intent name (snake_case from skill name)
            intent_name = draft.name.replace('-', '_')

            # Build the route entry
            triggers = skill_config.get("triggers", {})
            commands = triggers.get("commands", [draft.name])
            intents = triggers.get("intents", [])

            # Combine commands and intents as keywords
            keywords = list(commands)
            for intent in intents:
                if intent and intent not in keywords:
                    keywords.append(intent)

            route_entry = {
                "tier": skill_config.get("tier", 2),
                "zone": skill_config.get("zone", "yellow"),
                "domain": skill_config.get("domain", "system"),
                "description": draft.description,
                "keywords": keywords,
                "handler": "skill_executor",
                "handler_args": {
                    "skill_name": draft.name
                }
            }

            # Add to routes
            config["routes"][intent_name] = route_entry

            # Write back to file, preserving comments where possible
            # We'll append the new route as YAML at the end of routes section
            new_route_yaml = f"""
  # --- {draft.name} (Pit Crew Generated) ---
  {intent_name}:
    tier: {route_entry['tier']}
    zone: {route_entry['zone']}
    domain: {route_entry['domain']}
    description: "{draft.description}"
    keywords:
{self._format_keywords_yaml(keywords)}
    handler: "skill_executor"
    handler_args:
      skill_name: "{draft.name}"
"""

            # Find where to insert (before "# Tier Definitions" or at end of routes)
            if "# Tier Definitions" in content:
                insert_pos = content.find("# Tier Definitions")
                new_content = content[:insert_pos] + new_route_yaml + "\n" + content[insert_pos:]
            else:
                # Append at end
                new_content = content + new_route_yaml

            config_path.write_text(new_content, encoding="utf-8")

            log_event(
                source="pit_crew_registration",
                raw_transcript=f"Registered skill in routing: {intent_name}",
                zone_context="red",
                inferred={
                    "skill_name": draft.name,
                    "intent_name": intent_name,
                    "keywords": keywords
                }
            )

            # Hot reload the cognitive router
            self._trigger_router_reload()

            return True

        except Exception as e:
            log_event(
                source="pit_crew_error",
                raw_transcript=f"Failed to register skill: {str(e)}",
                zone_context="red",
                inferred={"error": str(e), "skill_name": draft.name}
            )
            return False

    def _format_keywords_yaml(self, keywords: list) -> str:
        """Format keywords list as YAML."""
        lines = []
        for keyword in keywords:
            lines.append(f'      - "{keyword}"')
        return '\n'.join(lines)

    def _trigger_router_reload(self) -> None:
        """
        Trigger hot reload of the CognitiveRouter.

        This ensures the new skill is immediately invocable
        without restarting the application.
        """
        try:
            from engine.cognitive_router import reset_router
            reset_router()

            log_event(
                source="pit_crew_reload",
                raw_transcript="CognitiveRouter hot reloaded",
                zone_context="green",
                inferred={"action": "router_reload"}
            )
        except Exception as e:
            log_event(
                source="pit_crew_warning",
                raw_transcript=f"Router reload failed: {str(e)}",
                zone_context="yellow",
                inferred={"warning": str(e)}
            )

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
