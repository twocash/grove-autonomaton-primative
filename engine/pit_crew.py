"""
pit_crew.py - The Self-Authoring Layer

The Pit Crew enables the system to generate new skills (capabilities)
for itself. This is the most sensitive operation in the Autonomaton
and MUST be strictly gated by Red Zone governance.

CRITICAL: All skill generation requires explicit Red Zone approval
before any files are written to the filesystem.

Sprint 4: LLM-powered skill authoring with self-registration.
Sprint 4.5: Composability Protocol enforcement.
Sprint 4.75: Architectural Judge & Exhaust Board with Apex Upgrade.

The Pit Crew is now an Autonomatonic sub-system that:
1. Uses Tier 3 (Opus/Apex) for maximum reasoning in skill generation
2. Runs Architectural Judge for protocol compliance validation
3. Updates Exhaust Board with telemetry unlock potentials
4. Displays generated code + future potentials in Red Zone Jidoka
5. Self-registers new skills into routing.config
6. Triggers hot reload for immediate invocation
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
from engine.profile import get_skills_dir, get_config_dir, get_dock_dir


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


@dataclass
class JudgmentResult:
    """
    Result from the Architectural Judge.

    Sprint 4.75: CI/CD-style quality gate for protocol compliance.
    """
    compliant: bool
    violations: list = field(default_factory=list)
    telemetry_exhaust_unlocks: list = field(default_factory=list)


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

        # Generate boilerplate files in memory (Tier 3 - Apex)
        draft = self._generate_skill_draft(normalized_name, description)

        # ARCHITECTURAL JUDGE: CI/CD quality gate (Tier 3 - Apex)
        judgment = self._run_architectural_judgment(draft)

        if not judgment.compliant:
            # Halt and surface violations via Jidoka
            compliance_rejected = self._surface_compliance_failure(draft, judgment)
            log_event(
                source="pit_crew_compliance_failed",
                raw_transcript=f"Skill failed compliance: {normalized_name}",
                zone_context="red",
                inferred={
                    "skill_name": normalized_name,
                    "violations": judgment.violations,
                    "action": "compliance_failed"
                }
            )
            return {
                "status": "compliance_failed",
                "message": f"Skill '{normalized_name}' failed Architectural Judge compliance check.",
                "violations": judgment.violations,
                "approved": False
            }

        # Compliance passed - update Exhaust Board
        self._update_exhaust_board(draft, judgment)

        # RED ZONE GOVERNANCE: Require explicit approval (now with telemetry unlocks)
        approval_granted = self._request_red_zone_approval(draft, judgment)

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
        Generate skill files using LLM (Tier 3 - Opus/Apex).

        Sprint 4: Uses LLM to create functional skill artifacts:
        - config.yaml: Valid YAML with triggers, zone, handler
        - prompt.md: Actual LLM prompt for skill execution
        - SKILL.md: Documentation and usage guide

        Sprint 4.5: Enforces Composability Protocol:
        - Injects Developer Guide constraints
        - Requires structured JSON output format
        - Ensures chain composition compatibility

        Sprint 4.75: Upgraded to Tier 3 (Opus/Apex) for maximum reasoning.
        The Pit Crew writes the code that runs the system, so we need
        apex intelligence for skill generation.

        The LLM prompt includes context from:
        - User's skill description
        - Existing routing.config format (for consistency)
        - Voice and pillar guidelines
        - Developer Guide (Composability Protocol)
        """
        from engine.llm_client import call_llm

        timestamp = datetime.now(timezone.utc).isoformat()
        title = skill_name.replace('-', ' ').title()

        # Load context for LLM
        routing_context = self._load_routing_context()
        voice_context = self._load_voice_context()
        pillar_context = self._load_pillar_context()
        developer_guide = self._load_developer_guide()

        # Build the generation prompt with composability constraints
        prompt = f"""You are an Autonomaton building Autonomatons. You are the Pit Crew, a sub-system that generates new skill capabilities.

You must STRICTLY adhere to the principles in the Developer Guide below. Every skill you generate is a composable node in a larger pipeline. Ensure your generated prompt.md forces its output into a structured, composable format (JSON) so that downstream Autonomatons can chain off of this skill.

=== DEVELOPER GUIDE (MANDATORY ADHERENCE) ===
{developer_guide}
=== END DEVELOPER GUIDE ===

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

REQUIREMENTS FOR prompt_md (COMPOSABILITY CRITICAL):
- Must include System Context explaining the skill's role as a COMPOSABLE NODE
- Must include clear Instructions for the LLM
- Must include Voice Guidelines matching the profile
- Must include MANDATORY Output Format section with this JSON schema:
  {{"status": "success|failure", "data": {{}}, "chain_context": {{"can_chain": true, "output_type": "structured"}}}}
- The prompt MUST instruct the LLM to return structured JSON (NOT plain text)
- Should include relevant Examples showing the JSON output format
- Must acknowledge that output will be logged to telemetry and may be consumed by downstream skills

REQUIREMENTS FOR skill_md:
- Must document the skill usage
- Must list triggers and zone classification
- Must explain that the skill outputs structured JSON for chain composition
- Must explain dependencies and requirements

COMPOSABILITY ENFORCEMENT:
- The skill is a NODE in a chain, not an isolated script
- Output must be parseable JSON that downstream skills can consume
- The prompt.md MUST specify a structured output format section
- Plain text responses are NOT acceptable - always return JSON

Return ONLY valid JSON with the three keys. No markdown code blocks, no explanations.

Example structure:
{{"config_yaml": "name: ...\\nzone: yellow\\n...", "prompt_md": "# Title\\n\\n## System Context\\nYou are executing a composable skill...\\n\\n## Output Format\\nReturn JSON with status, data, chain_context...", "skill_md": "# Title\\n\\n## Description\\n..."}}
"""

        try:
            response = call_llm(
                prompt=prompt,
                tier=3,  # Sprint 4.75: Use Opus/Apex for maximum reasoning
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

    def _load_developer_guide(self) -> str:
        """
        Load the Autonomaton Developer Guide for LLM context.

        Sprint 4.5: The Developer Guide defines the Composability Protocol
        that all generated skills must adhere to.
        """
        try:
            guide_path = get_dock_dir() / "system" / "autonomaton-developer-guide.md"
            if guide_path.exists():
                content = guide_path.read_text(encoding="utf-8")
                # Return key sections for context (not the entire guide)
                # Focus on: Output Contract, Composition Primitives, Anti-Patterns
                lines = content.split('\n')
                # Extract first 100 lines which cover the critical sections
                return '\n'.join(lines[:100])
        except Exception:
            pass
        return ""

    def _run_architectural_judgment(self, draft: SkillDraft) -> JudgmentResult:
        """
        Run the Architectural Judge for protocol compliance validation.

        Sprint 4.75: CI/CD-style quality gate that:
        1. Reviews generated artifacts against Developer Guide
        2. Returns compliance status with violations
        3. Brainstorms telemetry exhaust unlocks for compliant skills

        Uses Tier 3 (Opus/Apex) for maximum reasoning capability.
        """
        from engine.llm_client import call_llm

        developer_guide = self._load_developer_guide()

        prompt = f"""You are the Architectural Judge, a QA gate within the Autonomaton Pit Crew.

Your task is to validate that a newly generated skill strictly adheres to the Autonomaton Protocol as defined in the Developer Guide.

=== DEVELOPER GUIDE ===
{developer_guide}
=== END DEVELOPER GUIDE ===

=== SKILL DRAFT TO VALIDATE ===

config.yaml:
{draft.config_yaml}

prompt.md:
{draft.prompt_md}

=== END SKILL DRAFT ===

VALIDATION CRITERIA:
1. prompt.md MUST have an "Output Format" section with JSON schema
2. The JSON output MUST include: status, data, chain_context
3. prompt.md must acknowledge composability (output logged to telemetry, consumed by downstream)
4. config.yaml must have valid zone, tier, triggers
5. The skill must NOT bypass pipeline stages (no direct telemetry, no direct MCP calls)

Return a JSON object with exactly these keys:
- "compliant": boolean - true if ALL criteria pass, false if ANY fail
- "violations": array of strings - specific violations found (empty if compliant)
- "telemetry_exhaust_unlocks": array of 2-3 strings - IF compliant, describe specific ways the telemetry data emitted by this skill could be consumed by future Autonomatons or the Cortex. Be creative and specific.

Return ONLY valid JSON. No markdown code blocks.

Example for a compliant skill:
{{"compliant": true, "violations": [], "telemetry_exhaust_unlocks": ["Cortex can track skill usage frequency for load balancing", "Chain with reporting-skill for weekly summaries", "Feed output to dashboard for real-time visualization"]}}

Example for a non-compliant skill:
{{"compliant": false, "violations": ["prompt.md missing Output Format section", "No chain_context in output schema"], "telemetry_exhaust_unlocks": []}}
"""

        try:
            response = call_llm(
                prompt=prompt,
                tier=3,  # Apex for judgment
                intent="architectural_judgment",
                max_tokens=1500
            )

            result = json.loads(response)

            return JudgmentResult(
                compliant=result.get("compliant", False),
                violations=result.get("violations", []),
                telemetry_exhaust_unlocks=result.get("telemetry_exhaust_unlocks", [])
            )

        except json.JSONDecodeError as e:
            log_event(
                source="pit_crew_judge_error",
                raw_transcript=f"Judge returned invalid JSON: {str(e)}",
                zone_context="red",
                inferred={"error": "judge_json_parse_failed"}
            )
            # Default to non-compliant on parse failure
            return JudgmentResult(
                compliant=False,
                violations=["Architectural Judge failed to return valid JSON response"],
                telemetry_exhaust_unlocks=[]
            )

        except Exception as e:
            log_event(
                source="pit_crew_judge_error",
                raw_transcript=f"Judge failed: {str(e)}",
                zone_context="red",
                inferred={"error": str(e)}
            )
            return JudgmentResult(
                compliant=False,
                violations=[f"Architectural Judge error: {str(e)}"],
                telemetry_exhaust_unlocks=[]
            )

    def _surface_compliance_failure(self, draft: SkillDraft, judgment: JudgmentResult) -> bool:
        """
        Surface compliance violations to the user via Jidoka.

        Sprint 4.75: When the Architectural Judge rejects a skill,
        we halt and show the violations before any files are written.
        """
        violations_list = "\n".join(f"  - {v}" for v in judgment.violations)

        result = ask_jidoka(
            context_message=(
                f"COMPLIANCE FAILURE: Skill '{draft.name}' failed Architectural Judge validation.\n\n"
                f"The generated skill violates the Autonomaton Protocol:\n\n"
                f"VIOLATIONS:\n{violations_list}\n\n"
                f"The skill cannot be deployed until these violations are resolved.\n"
                f"Please refine the skill description or regenerate."
            ),
            options={
                "1": "ACKNOWLEDGE: Abort this build",
                "2": "ABORT: Cancel without action"
            }
        )

        return result == "1"

    def _update_exhaust_board(self, draft: SkillDraft, judgment: JudgmentResult) -> bool:
        """
        Update the Exhaust Board with telemetry unlock potentials.

        Sprint 4.75: After a skill passes compliance, the Judge's
        telemetry_exhaust_unlocks are appended to the global registry.
        This serves as a strategic resource for the Cortex.
        """
        try:
            exhaust_path = get_dock_dir() / "system" / "exhaust-board.md"

            if not exhaust_path.exists():
                # Initialize if missing
                exhaust_path.parent.mkdir(parents=True, exist_ok=True)
                exhaust_path.write_text("# Exhaust Board\n\n", encoding="utf-8")

            # Format the new entry
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            unlocks_list = "\n".join(f"- {u}" for u in judgment.telemetry_exhaust_unlocks)

            entry = f"""
### {draft.name} - {timestamp}

**Description:** {draft.description}

**Telemetry Unlocks:**
{unlocks_list}

---
"""

            # Append to exhaust board
            with open(exhaust_path, "a", encoding="utf-8") as f:
                f.write(entry)

            log_event(
                source="pit_crew_exhaust_board",
                raw_transcript=f"Updated exhaust board for skill: {draft.name}",
                zone_context="green",
                inferred={
                    "skill_name": draft.name,
                    "unlocks_count": len(judgment.telemetry_exhaust_unlocks)
                }
            )

            return True

        except Exception as e:
            log_event(
                source="pit_crew_exhaust_error",
                raw_transcript=f"Failed to update exhaust board: {str(e)}",
                zone_context="yellow",
                inferred={"error": str(e)}
            )
            return False

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

    def _request_red_zone_approval(self, draft: SkillDraft, judgment: Optional[JudgmentResult] = None) -> bool:
        """
        Request Red Zone approval via Jidoka.

        Sprint 4: Displays the actual generated code/config for review.
        Sprint 4.75: Now includes telemetry unlocks from Architectural Judge.

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

        # Build telemetry unlocks section (Sprint 4.75)
        telemetry_section = ""
        if judgment and judgment.telemetry_exhaust_unlocks:
            unlocks_list = "\n".join(f"  - {u}" for u in judgment.telemetry_exhaust_unlocks)
            telemetry_section = f"""
--- FUTURE POTENTIALS (Telemetry Unlocks) ---
The Architectural Judge identified these automation opportunities:
{unlocks_list}
--- END FUTURE POTENTIALS ---
"""

        # Build detailed preview with actual generated code
        preview = f"""
================================================================================
SKILL: {draft.name}
DESCRIPTION: {draft.description}
COMPLIANCE: PASSED (Architectural Judge validated)
================================================================================

--- GENERATED config.yaml ---
{draft.config_yaml}
--- END config.yaml ---

--- GENERATED prompt.md (summary) ---
{prompt_summary}
--- END prompt.md ---
{telemetry_section}
ACTIONS UPON APPROVAL:
1. Create skills/{draft.name}/ directory
2. Write config.yaml (zone: {zone})
3. Write prompt.md (LLM execution template)
4. Write SKILL.md (documentation)
5. Register in routing.config with triggers: {triggers}
6. Hot reload CognitiveRouter for immediate invocation
7. Update Exhaust Board with telemetry unlocks

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
