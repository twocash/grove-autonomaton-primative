"""
test_pit_crew.py - Tests for Pit Crew Autonomatonic Skill Generation

Sprint 4: The Pit Crew as Autonomatonic System

These tests verify:
1. LLM generates valid skill artifacts (config.yaml, prompt.md, SKILL.md)
2. Self-registration into routing.config after deployment
3. Red Zone Jidoka enforcement with actual code display
4. Hot reload of CognitiveRouter for immediate skill invocation

TDD: Write tests first, then implement to pass.
"""

import pytest
import json
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import shutil


class TestPitCrewGeneratesValidArtifacts:
    """Tests for LLM-powered skill artifact generation."""

    def test_pit_crew_generates_valid_artifacts(self):
        """
        Mock the LLM to return valid JSON and assert the Pit Crew
        correctly parses the LLM output into config.yaml, prompt.md, and SKILL.md.
        """
        from engine.pit_crew import PitCrew
        from engine.profile import set_profile

        set_profile("coach_demo")

        # Mock LLM response with structured skill artifacts
        mock_llm_response = json.dumps({
            "config_yaml": """name: "Tournament Prep"
description: "Prepare players for upcoming tournament"
zone: yellow
tier: 2
approval: one_thumb
triggers:
  commands:
    - "tournament-prep"
    - "prep tournament"
  intents:
    - "prepare for tournament"
requires:
  mcp_servers: []
  dock_sources:
    - "entities/players/"
""",
            "prompt_md": """# Tournament Prep - Prompt Template

## System Context
You are The Coach Autonomaton, executing the "tournament-prep" skill.

## Task
Analyze player performance data and create a tournament preparation plan.

## Instructions
1. Review recent practice scores for each player
2. Identify strengths and areas for improvement
3. Generate personalized preparation recommendations
4. Create a team-wide tournament strategy

## Voice Guidelines
- Encouraging and focused
- Data-driven but human
- Faith-centered motivation

## Output Format
Return a structured tournament prep document with:
- Individual player assessments
- Team strategy overview
- Mental preparation notes
""",
            "skill_md": """# Tournament Prep

## Description
Prepare players for upcoming tournament with personalized analysis and strategy.

## Usage
```
autonomaton> tournament-prep
```

## Zone Classification
**Default Zone:** Yellow (requires user approval)

## Triggers
- Command: `tournament-prep`, `prep tournament`
- Intent patterns: "prepare for tournament"

## Dependencies
- Player entity files from dock
- Recent practice/match data
"""
        })

        pit_crew = PitCrew()

        with patch('engine.llm_client.call_llm', return_value=mock_llm_response) as mock_llm:
            draft = pit_crew._generate_skill_draft("tournament-prep", "Prepare players for upcoming tournament")

        # Verify LLM was called
        mock_llm.assert_called_once()

        # Verify artifacts are populated
        assert draft.name == "tournament-prep"
        assert draft.description == "Prepare players for upcoming tournament"

        # Verify config_yaml is valid YAML
        config = yaml.safe_load(draft.config_yaml)
        assert config["name"] == "Tournament Prep"
        assert config["zone"] == "yellow"
        assert "tournament-prep" in config["triggers"]["commands"]

        # Verify prompt_md contains key sections
        assert "Tournament Prep" in draft.prompt_md
        assert "System Context" in draft.prompt_md
        assert "Instructions" in draft.prompt_md

        # Verify skill_md contains documentation
        assert "Tournament Prep" in draft.skill_md
        assert "tournament-prep" in draft.skill_md

    def test_pit_crew_llm_prompt_includes_context(self):
        """
        Verify the LLM prompt injects necessary context:
        - User's skill description
        - Existing routing.config format
        - Voice/pillar guidelines
        """
        from engine.pit_crew import PitCrew
        from engine.profile import set_profile

        set_profile("coach_demo")

        mock_llm_response = json.dumps({
            "config_yaml": "name: test\nzone: yellow\ntriggers:\n  commands:\n    - test",
            "prompt_md": "# Test Skill",
            "skill_md": "# Test"
        })

        pit_crew = PitCrew()
        captured_prompt = None

        def capture_llm_call(prompt, **kwargs):
            nonlocal captured_prompt
            captured_prompt = prompt
            return mock_llm_response

        with patch('engine.llm_client.call_llm', side_effect=capture_llm_call):
            pit_crew._generate_skill_draft("test-skill", "Test skill description")

        # Verify prompt contains required context
        assert captured_prompt is not None
        assert "test-skill" in captured_prompt.lower() or "Test skill description" in captured_prompt
        # Should reference routing.config format
        assert "yaml" in captured_prompt.lower() or "config" in captured_prompt.lower()

    def test_pit_crew_handles_llm_json_parsing_error(self):
        """
        If LLM returns invalid JSON, Pit Crew should handle gracefully.
        """
        from engine.pit_crew import PitCrew
        from engine.profile import set_profile

        set_profile("coach_demo")

        # Mock LLM returning malformed JSON
        mock_llm_response = "This is not valid JSON { broken"

        pit_crew = PitCrew()

        with patch('engine.llm_client.call_llm', return_value=mock_llm_response):
            # Should not crash - should return fallback or raise handled exception
            try:
                draft = pit_crew._generate_skill_draft("test-skill", "Test description")
                # If it returns a draft, it should have fallback content
                assert draft is not None
            except ValueError as e:
                # Acceptable to raise ValueError for parsing failure
                assert "parse" in str(e).lower() or "json" in str(e).lower()


class TestPitCrewUpdatesRoutingConfig:
    """Tests for self-registration into routing.config."""

    def test_pit_crew_updates_routing_config(self):
        """
        Assert that after files are written, the Pit Crew successfully
        appends a new, correctly formatted intent block to routing.config.
        """
        from engine.pit_crew import PitCrew
        from engine.profile import set_profile, get_config_dir

        set_profile("coach_demo")

        # Create a temp copy of routing.config for testing
        original_config_path = get_config_dir() / "routing.config"
        original_content = original_config_path.read_text(encoding="utf-8")

        mock_llm_response = json.dumps({
            "config_yaml": """name: "Tournament Prep"
description: "Prepare players for tournament"
zone: yellow
tier: 2
triggers:
  commands:
    - "tournament-prep"
  intents: []
""",
            "prompt_md": "# Tournament Prep Prompt",
            "skill_md": "# Tournament Prep Doc"
        })

        pit_crew = PitCrew()

        try:
            with patch('engine.llm_client.call_llm', return_value=mock_llm_response):
                with patch('engine.pit_crew.ask_jidoka', return_value="1"):  # Approve
                    # Use a temp skills directory
                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_skills = Path(temp_dir) / "skills"
                        temp_skills.mkdir()

                        with patch('engine.pit_crew.get_skills_dir', return_value=temp_skills):
                            result = pit_crew.propose_and_build_skill(
                                "tournament-prep",
                                "Prepare players for tournament"
                            )

            # Verify the skill was registered in routing.config
            updated_content = original_config_path.read_text(encoding="utf-8")

            # Should contain new intent block
            assert "tournament_prep:" in updated_content or "tournament-prep" in updated_content
            # Parse to verify it's valid YAML
            config = yaml.safe_load(updated_content)
            assert config is not None

        finally:
            # Restore original routing.config
            original_config_path.write_text(original_content, encoding="utf-8")

    def test_pit_crew_routing_entry_has_required_fields(self):
        """
        The new routing.config entry must have all required fields:
        tier, zone, domain, description, keywords, handler.
        """
        from engine.pit_crew import PitCrew
        from engine.profile import set_profile, get_config_dir

        set_profile("coach_demo")

        original_config_path = get_config_dir() / "routing.config"
        original_content = original_config_path.read_text(encoding="utf-8")

        mock_llm_response = json.dumps({
            "config_yaml": """name: "Test Skill"
description: "Test skill for validation"
zone: yellow
tier: 2
triggers:
  commands:
    - "test-skill"
  intents: []
""",
            "prompt_md": "# Test Prompt",
            "skill_md": "# Test Doc"
        })

        pit_crew = PitCrew()

        try:
            with patch('engine.llm_client.call_llm', return_value=mock_llm_response):
                with patch('engine.pit_crew.ask_jidoka', return_value="1"):
                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_skills = Path(temp_dir) / "skills"
                        temp_skills.mkdir()

                        with patch('engine.pit_crew.get_skills_dir', return_value=temp_skills):
                            pit_crew.propose_and_build_skill("test-skill", "Test skill")

            # Parse updated config
            updated_content = original_config_path.read_text(encoding="utf-8")
            config = yaml.safe_load(updated_content)

            # Find the new entry
            new_intent = None
            for intent_name, route_config in config.get("routes", {}).items():
                if "test-skill" in str(route_config.get("keywords", [])) or \
                   "test_skill" in intent_name or "test-skill" in intent_name:
                    new_intent = route_config
                    break

            assert new_intent is not None, "New intent not found in routing.config"
            assert "tier" in new_intent
            assert "zone" in new_intent
            assert "description" in new_intent
            assert "keywords" in new_intent
            assert "handler" in new_intent

        finally:
            original_config_path.write_text(original_content, encoding="utf-8")


class TestPitCrewRedZoneEnforced:
    """Tests for Red Zone Jidoka enforcement."""

    def test_pit_crew_red_zone_enforced(self):
        """
        Assert that the Red Zone Jidoka prompt fires, displaying the
        generated YAML and logic before any files are written to disk.
        """
        from engine.pit_crew import PitCrew
        from engine.profile import set_profile

        set_profile("coach_demo")

        mock_llm_response = json.dumps({
            "config_yaml": """name: "Test Skill"
description: "Test description"
zone: yellow
tier: 2
triggers:
  commands:
    - "test-skill"
""",
            "prompt_md": "# Test Prompt\n\nThis is the prompt logic.",
            "skill_md": "# Test Skill Doc"
        })

        pit_crew = PitCrew()
        jidoka_context = None

        def capture_jidoka(context_message, options):
            nonlocal jidoka_context
            jidoka_context = context_message
            return "2"  # Reject to prevent file writes

        with patch('engine.llm_client.call_llm', return_value=mock_llm_response):
            with patch('engine.pit_crew.ask_jidoka', side_effect=capture_jidoka):
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_skills = Path(temp_dir) / "skills"
                    temp_skills.mkdir()

                    with patch('engine.pit_crew.get_skills_dir', return_value=temp_skills):
                        pit_crew.propose_and_build_skill("test-skill", "Test description")

        # Verify Jidoka was called with actual code content
        assert jidoka_context is not None
        assert "RED ZONE" in jidoka_context

        # Should display the generated config.yaml content
        assert "zone: yellow" in jidoka_context or "config.yaml" in jidoka_context

        # Should show prompt logic summary
        assert "prompt" in jidoka_context.lower()

    def test_pit_crew_rejection_prevents_file_writes(self):
        """
        If user rejects at Red Zone, no files should be written.
        """
        from engine.pit_crew import PitCrew
        from engine.profile import set_profile

        set_profile("coach_demo")

        mock_llm_response = json.dumps({
            "config_yaml": "name: Test\nzone: yellow",
            "prompt_md": "# Test",
            "skill_md": "# Test"
        })

        pit_crew = PitCrew()

        with patch('engine.llm_client.call_llm', return_value=mock_llm_response):
            with patch('engine.pit_crew.ask_jidoka', return_value="2"):  # Reject
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_skills = Path(temp_dir) / "skills"
                    temp_skills.mkdir()

                    with patch('engine.pit_crew.get_skills_dir', return_value=temp_skills):
                        result = pit_crew.propose_and_build_skill("test-skill", "Test")

        assert result["status"] == "rejected"
        assert result["approved"] is False

    def test_pit_crew_approval_writes_files(self):
        """
        If user approves at Red Zone, files should be written.
        """
        from engine.pit_crew import PitCrew
        from engine.profile import set_profile, get_config_dir

        set_profile("coach_demo")

        # Save original routing.config
        original_config_path = get_config_dir() / "routing.config"
        original_content = original_config_path.read_text(encoding="utf-8")

        mock_llm_response = json.dumps({
            "config_yaml": """name: "Approved Skill"
description: "This skill was approved"
zone: yellow
tier: 2
triggers:
  commands:
    - "approved-skill"
""",
            "prompt_md": "# Approved Skill Prompt",
            "skill_md": "# Approved Skill Doc"
        })

        pit_crew = PitCrew()

        try:
            with patch('engine.llm_client.call_llm', return_value=mock_llm_response):
                with patch('engine.pit_crew.ask_jidoka', return_value="1"):  # Approve
                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_skills = Path(temp_dir) / "skills"
                        temp_skills.mkdir()

                        with patch('engine.pit_crew.get_skills_dir', return_value=temp_skills):
                            result = pit_crew.propose_and_build_skill(
                                "approved-skill",
                                "This skill was approved"
                            )

                        # Verify files were created
                        skill_dir = temp_skills / "approved-skill"
                        assert skill_dir.exists()
                        assert (skill_dir / "config.yaml").exists()
                        assert (skill_dir / "prompt.md").exists()
                        assert (skill_dir / "SKILL.md").exists()

            assert result["status"] == "deployed"
            assert result["approved"] is True

        finally:
            original_config_path.write_text(original_content, encoding="utf-8")


class TestCognitiveRouterHotReload:
    """Tests for hot reload of CognitiveRouter after skill registration."""

    def test_cognitive_router_has_reload_method(self):
        """
        CognitiveRouter should have a method to reload its cached config.
        """
        from engine.cognitive_router import CognitiveRouter

        router = CognitiveRouter()
        assert hasattr(router, 'reload_config') or hasattr(router, 'load_config')

    def test_new_skill_immediately_invocable(self):
        """
        After skill deployment and routing registration, the new skill
        should be immediately invocable without restarting the application.
        """
        from engine.cognitive_router import get_router, reset_router
        from engine.profile import set_profile, get_config_dir

        set_profile("coach_demo")
        reset_router()

        original_config_path = get_config_dir() / "routing.config"
        original_content = original_config_path.read_text(encoding="utf-8")

        try:
            # Add a test route to routing.config
            config = yaml.safe_load(original_content)
            config["routes"]["test_hot_reload"] = {
                "tier": 2,
                "zone": "yellow",
                "domain": "system",
                "description": "Test hot reload",
                "keywords": ["hot-reload-test"],
                "handler": "test_handler"
            }

            # Write updated config
            original_config_path.write_text(
                yaml.dump(config, default_flow_style=False),
                encoding="utf-8"
            )

            # Force router reload
            reset_router()
            router = get_router()

            # New route should be recognized
            result = router.classify("hot-reload-test")
            assert result.intent == "test_hot_reload"
            assert result.handler == "test_handler"

        finally:
            original_config_path.write_text(original_content, encoding="utf-8")
            reset_router()


class TestComposabilityProtocol:
    """
    Sprint 4.5: The Composability Protocol

    These tests verify that the Pit Crew generates skills that are
    composable "nodes" capable of Chain, Branch, and Hierarchical composition.
    """

    def test_pit_crew_enforces_composability(self):
        """
        Assert that the Pit Crew's generation prompt explicitly injects
        constraints requiring the new skill to output structured, telemetry-ready
        data (enabling Chain Composition).

        The LLM prompt MUST include:
        1. Explicit instruction to output structured data (JSON/YAML)
        2. Reference to composability requirements
        3. Instruction that output becomes telemetry input for downstream nodes
        """
        from engine.pit_crew import PitCrew
        from engine.profile import set_profile

        set_profile("coach_demo")

        mock_llm_response = json.dumps({
            "config_yaml": "name: Test\nzone: yellow\ntriggers:\n  commands:\n    - test",
            "prompt_md": """# Test Skill

## Output Format
```json
{
  "status": "success",
  "data": {},
  "chain_context": {}
}
```
""",
            "skill_md": "# Test"
        })

        pit_crew = PitCrew()
        captured_prompt = None

        def capture_llm_call(prompt, **kwargs):
            nonlocal captured_prompt
            captured_prompt = prompt
            return mock_llm_response

        with patch('engine.llm_client.call_llm', side_effect=capture_llm_call):
            pit_crew._generate_skill_draft("test-skill", "Test skill description")

        # Verify prompt enforces composability constraints
        assert captured_prompt is not None

        # Must instruct LLM to generate composable output
        prompt_lower = captured_prompt.lower()
        assert "composable" in prompt_lower or "chain" in prompt_lower, \
            "Prompt must reference composability or chain composition"

        # Must require structured output format
        assert "json" in prompt_lower or "yaml" in prompt_lower or "structured" in prompt_lower, \
            "Prompt must require structured output format"

        # Must reference the Developer Guide or protocol constraints
        assert "developer guide" in prompt_lower or "protocol" in prompt_lower or "autonomaton" in prompt_lower, \
            "Prompt must reference Developer Guide or Autonomaton protocol"

    def test_developer_guide_ingestion(self):
        """
        Assert that the Pit Crew successfully reads and includes the
        autonomaton-developer-guide.md in its LLM context window.
        """
        from engine.pit_crew import PitCrew
        from engine.profile import set_profile, get_dock_dir

        set_profile("coach_demo")

        # Ensure developer guide exists (we'll create it in implementation)
        dock_dir = get_dock_dir()
        guide_path = dock_dir / "system" / "autonomaton-developer-guide.md"

        # Create guide if it doesn't exist (for test setup)
        if not guide_path.parent.exists():
            guide_path.parent.mkdir(parents=True, exist_ok=True)

        guide_content = """# Autonomaton Developer Guide

## The TCP/IP of Cognition
Protocol over Implementation. Skills are nodes in a composable pipeline.

## Composition Primitives
- Chain: Output of Node A becomes input telemetry for Node B
- Supervisor/Worker: Parent node dispatches to children

## Output Contract
All skills MUST return structured JSON with:
- status: success/failure
- data: payload for downstream nodes
- chain_context: metadata for composition
"""
        guide_path.write_text(guide_content, encoding="utf-8")

        mock_llm_response = json.dumps({
            "config_yaml": "name: Test\nzone: yellow\ntriggers:\n  commands:\n    - test",
            "prompt_md": "# Test",
            "skill_md": "# Test"
        })

        pit_crew = PitCrew()
        captured_prompt = None

        def capture_llm_call(prompt, **kwargs):
            nonlocal captured_prompt
            captured_prompt = prompt
            return mock_llm_response

        with patch('engine.llm_client.call_llm', side_effect=capture_llm_call):
            pit_crew._generate_skill_draft("guide-test", "Test guide ingestion")

        # Verify the developer guide content is included in the prompt
        assert captured_prompt is not None

        # The guide content or its key concepts must be in the prompt
        prompt_lower = captured_prompt.lower()
        assert "developer guide" in prompt_lower or "tcp/ip" in prompt_lower or "composition" in prompt_lower, \
            "Prompt must include developer guide content or concepts"

    def test_generated_prompt_includes_output_format(self):
        """
        Verify that generated prompt.md files include explicit
        structured output format instructions for composability.
        """
        from engine.pit_crew import PitCrew
        from engine.profile import set_profile

        set_profile("coach_demo")

        # Mock a response where prompt.md has proper composable output format
        mock_llm_response = json.dumps({
            "config_yaml": """name: "Composable Skill"
zone: yellow
tier: 2
triggers:
  commands:
    - "composable-test"
""",
            "prompt_md": """# Composable Test Skill

## System Context
You are executing a composable skill within the Autonomaton pipeline.

## Output Format
Your response MUST be valid JSON following this schema:
```json
{
  "status": "success|failure",
  "data": {
    // Skill-specific payload
  },
  "chain_context": {
    "can_chain": true,
    "output_type": "structured",
    "downstream_hints": []
  }
}
```

## Composability Contract
- Your output will be logged to telemetry
- Downstream skills may consume your output
- Always return structured, parseable data
""",
            "skill_md": "# Composable Test"
        })

        pit_crew = PitCrew()

        with patch('engine.llm_client.call_llm', return_value=mock_llm_response):
            draft = pit_crew._generate_skill_draft("composable-test", "Test composability")

        # Verify prompt.md contains composability instructions
        prompt_lower = draft.prompt_md.lower()
        assert "output format" in prompt_lower, "prompt.md must specify output format"
        assert "json" in prompt_lower, "prompt.md must reference JSON output"


class TestEndToEndSkillCreation:
    """End-to-end integration tests for skill creation workflow."""

    def test_build_skill_full_workflow(self):
        """
        Full workflow: build skill command -> LLM generation -> approval -> deployment -> invocation
        """
        from engine.pit_crew import PitCrew
        from engine.cognitive_router import reset_router, get_router
        from engine.profile import set_profile, get_config_dir

        set_profile("coach_demo")
        reset_router()

        original_config_path = get_config_dir() / "routing.config"
        original_content = original_config_path.read_text(encoding="utf-8")

        mock_llm_response = json.dumps({
            "config_yaml": """name: "E2E Test Skill"
description: "End to end test skill"
zone: yellow
tier: 2
triggers:
  commands:
    - "e2e-test"
  intents: []
""",
            "prompt_md": "# E2E Test Skill Prompt\n\nExecute end-to-end test.",
            "skill_md": "# E2E Test Skill\n\nThis is an end-to-end test skill."
        })

        pit_crew = PitCrew()

        try:
            with patch('engine.llm_client.call_llm', return_value=mock_llm_response):
                with patch('engine.pit_crew.ask_jidoka', return_value="1"):  # Approve
                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_skills = Path(temp_dir) / "skills"
                        temp_skills.mkdir()

                        with patch('engine.pit_crew.get_skills_dir', return_value=temp_skills):
                            result = pit_crew.propose_and_build_skill(
                                "e2e-test",
                                "End to end test skill"
                            )

                        assert result["status"] == "deployed"

            # Force router reload
            reset_router()
            router = get_router()

            # New skill should be immediately invocable
            routing_result = router.classify("e2e-test")
            assert routing_result.intent != "unknown", \
                f"New skill should be recognized, got intent: {routing_result.intent}"

        finally:
            original_config_path.write_text(original_content, encoding="utf-8")
            reset_router()
