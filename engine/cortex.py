"""
cortex.py - The LLM-Powered Analytical Engine (Layer 3)

The Cortex runs a "tail-pass" after each Operator interaction,
extracting knowledge without slowing down the conversation.

Lens 1: Entity Extraction
    - LLM-based NER using Tier 1 (Haiku)
    - New entities marked with is_new=True trigger Jidoka validation
    - Existing entities skip validation

Lens 2: Content Seed Mining
    - LLM identifies potential content moments
    - Seeds saved to entities/content-seeds/

Uses Tier 1 (Haiku) for speed/cost efficiency on every interaction.
"""

import re
import json
import yaml
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional, Any

from engine.profile import (
    get_telemetry_path,
    get_entities_dir,
    get_queue_dir,
    get_pending_queue_path
)


def create_entity_validation_proposal(
    entity_name: str,
    entity_type: str,
    context: str
) -> dict:
    """
    Create an entity validation proposal for the Kaizen queue.

    The Cortex is a pure analytical layer. It NEVER prompts the operator
    directly. All proposals go to the queue and are processed through
    the pipeline at startup or via the 'queue' command.

    Invariant #6: Stage 4 is the ONLY layer permitted to prompt for approval.

    Args:
        entity_name: The extracted entity name
        entity_type: The inferred entity type
        context: Surrounding context from transcript

    Returns:
        Proposal dict for queue insertion
    """
    import uuid
    from datetime import datetime, timezone

    return {
        "id": f"entity-{uuid.uuid4().hex[:8]}",
        "trigger": "entity_extraction",
        "proposal_type": "entity_validation",
        "proposal": f"New {entity_type} detected: {entity_name}",
        "entity_name": entity_name,
        "entity_type": entity_type,
        "context": context[:200],
        "priority": "medium",
        "created": datetime.now(timezone.utc).isoformat(),
        "status": "pending"
    }


@dataclass
class ExtractedEntity:
    """An entity extracted from a transcript."""
    name: str
    entity_type: str  # Loaded from profile entity_config.yaml
    source_event_id: str
    confidence: float = 0.5
    context: str = ""
    is_new: bool = False  # New entities trigger Jidoka validation


@dataclass
class KaizenProposal:
    """A continuous improvement proposal."""
    id: str
    proposal: str
    trigger: str
    source_event_id: str
    created_at: str
    status: str = "pending"
    # Sprint 5: Additional fields for Context Gardener proposals
    proposal_type: str = "general"  # general, gap_alert, plan_update, stale_alert
    target_file: str = ""           # For plan_update type
    target_section: str = ""        # For plan_update type
    priority: str = "medium"        # high, medium, low


class Cortex:
    """
    The Analytical Engine that processes telemetry in the background.

    The Cortex runs after each interaction to:
    1. Extract entities (types defined in entity_config.yaml)
    2. Generate Kaizen proposals for improvement
    3. Update knowledge graphs (future)

    Usage:
        cortex = Cortex()
        cortex.run_analysis_pass()  # Process latest telemetry
    """

    def __init__(self):
        self.processed_event_ids: set[str] = set()
        self._load_processed_ids()

    def _load_processed_ids(self) -> None:
        """Load IDs of previously processed events to avoid duplicates."""
        queue_dir = get_queue_dir()
        processed_file = queue_dir / ".processed_events"
        if processed_file.exists():
            self.processed_event_ids = set(
                processed_file.read_text(encoding="utf-8").strip().split("\n")
            )

    def _save_processed_id(self, event_id: str) -> None:
        """Mark an event as processed."""
        self.processed_event_ids.add(event_id)
        queue_dir = get_queue_dir()
        processed_file = queue_dir / ".processed_events"
        processed_file.parent.mkdir(parents=True, exist_ok=True)
        with open(processed_file, "a", encoding="utf-8") as f:
            f.write(event_id + "\n")

    def run_analysis_pass(self, telemetry_file: Optional[str] = None) -> dict:
        """
        Run a tail-pass analysis on recent telemetry.

        Args:
            telemetry_file: Path to telemetry JSONL (default: profile's telemetry.jsonl)

        Returns:
            Summary of extraction results
        """
        telemetry_path = Path(telemetry_file) if telemetry_file else get_telemetry_path()

        if not telemetry_path.exists():
            return {"status": "no_telemetry", "entities": 0, "kaizen": 0}

        # Read recent events
        events = self._read_recent_events(telemetry_path, limit=10)

        # Filter to unprocessed operator_session events
        new_events = [
            e for e in events
            if e.get("id") not in self.processed_event_ids
            and e.get("source") == "operator_session"
        ]

        if not new_events:
            return {"status": "no_new_events", "entities": 0, "kaizen": 0}

        entities_created = 0
        kaizen_created = 0

        for event in new_events:
            # Run entity extraction
            entities = self._extract_entities(event)
            for entity in entities:
                if self._create_entity_profile(entity):
                    entities_created += 1

            # Run Kaizen analysis
            proposals = self._generate_kaizen(event)
            for proposal in proposals:
                if self._queue_kaizen(proposal):
                    kaizen_created += 1

            # Mark as processed
            self._save_processed_id(event.get("id", ""))

        return {
            "status": "complete",
            "events_processed": len(new_events),
            "entities": entities_created,
            "kaizen": kaizen_created
        }

    def _read_recent_events(self, path: Path, limit: int = 10) -> list[dict]:
        """Read the most recent telemetry events."""
        events = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return events[-limit:]

    # =========================================================================
    # Entity Extraction (Sprint 6 - ADR-001 Ratchet Pattern)
    # =========================================================================

    def _extract_entities(self, event: dict) -> list[ExtractedEntity]:
        """
        Extract entities from a telemetry event.

        V-001: Uses deterministic regex extraction directly.
        LLM escalation for entity extraction removed with ratchet.py.
        """
        transcript = event.get("raw_transcript", "")
        event_id = event.get("id", "unknown")

        if not transcript.strip():
            return []

        try:
            result = self._regex_extract_entities(transcript, event_id)
        except Exception as e:
            from engine.telemetry import log_event
            log_event(
                source="cortex:entity_extraction",
                raw_transcript=transcript[:200],
                zone_context="yellow",
                intent="entity_extraction",
                inferred={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "stage": "regex_extract"
                }
            )
            return []

        if result is None:
            return []

        entities, confidence = result
        return entities if isinstance(entities, list) else []

    def _regex_extract_entities(self, transcript: str, event_id: str) -> Optional[tuple]:
        """
        Deterministic entity extraction using regex patterns.

        Returns (entities_list, confidence) or None if no entities found.
        This is the free layer - no API calls.
        """
        entities = []

        # Pattern: Capitalized words that look like names
        # Matches: "Henderson", "Marcus", "St. Mary's"
        # Excludes: Common words, single letters, all-caps
        name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'

        # Common words to exclude (sentence starters, days, months)
        # Domain-specific excludes loaded from profile config
        from engine.config_loader import load_entity_config
        entity_config = load_entity_config()
        domain_excludes = set(entity_config.get("exclude_domain_words", []))

        common_excludes = {
            # Sentence starters / common words
            "The", "This", "That", "What", "When", "Where", "Why", "How",
            "Need", "Want", "Help", "Show", "Get", "Make", "Take", "Give",
            "Let", "Can", "Will", "Would", "Could", "Should", "May", "Might",
            "Have", "Has", "Had", "Been", "Being", "Are", "Was", "Were",
            "Just", "Also", "Still", "Even", "Only", "Very", "Really",
            # Days and months
            "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
            "January", "February", "March", "April", "May", "June", "July",
            "August", "September", "October", "November", "December",
            # System terms (not domain-specific)
            "Green", "Yellow", "Red", "Zone", "Dock", "Action", "Status",
            # Common verbs that might be capitalized
            "Schedule", "Send", "Create", "Update", "Delete", "Draft"
        }
        exclude_words = common_excludes | domain_excludes

        matches = re.findall(name_pattern, transcript)

        for match in matches:
            if match not in exclude_words and len(match) > 2:
                # Extract surrounding context
                context_match = re.search(
                    rf'.{{0,30}}{re.escape(match)}.{{0,30}}',
                    transcript
                )
                context = context_match.group(0) if context_match else ""

                # Default entity type from config (first type or generic)
                default_type = entity_config["entity_types"][0]["name"] if entity_config.get("entity_types") else "entity"
                entities.append(ExtractedEntity(
                    name=match,
                    entity_type=default_type,
                    source_event_id=event_id,
                    confidence=0.6,
                    context=context
                ))

        if entities:
            # Return entities with average confidence
            avg_confidence = sum(e.confidence for e in entities) / len(entities)
            return (entities, avg_confidence)

        # No matches - return None to trigger LLM escalation
        return None

    def _parse_llm_entities(
        self,
        llm_result: Any,
        event_id: str,
        transcript: str
    ) -> list[ExtractedEntity]:
        """
        Parse LLM extraction result into ExtractedEntity list.

        Converts raw entity extraction results to ExtractedEntity dataclass instances.
        """
        entities = []

        # Handle different result formats
        if isinstance(llm_result, list):
            entities_data = llm_result
        elif isinstance(llm_result, dict):
            entities_data = llm_result.get("entities", [])
        else:
            return []

        for e in entities_data:
            if isinstance(e, dict):
                name = e.get("name", e.get("text", "")).strip()
                if not name:
                    continue

                # Use config-driven default entity type
                from engine.config_loader import load_entity_config
                entity_config = load_entity_config()
                default_type = entity_config["entity_types"][0]["name"] if entity_config.get("entity_types") else "entity"
                entities.append(ExtractedEntity(
                    name=name,
                    entity_type=e.get("type", e.get("entity_type", default_type)),
                    source_event_id=event_id,
                    confidence=0.8,  # LLM extraction confidence
                    context=transcript[:100],
                    is_new=e.get("is_new", True)
                ))

        return entities

    def _validate_new_entity(self, entity: ExtractedEntity) -> bool:
        """
        Queue new entity for validation via Kaizen queue.

        The Cortex NEVER prompts directly (Invariant #6 compliance).
        All entity proposals go to the queue and are processed through
        the pipeline at startup or via the 'queue' command.

        Args:
            entity: The entity to validate

        Returns:
            False (entity not created yet - deferred to queue processing)
        """
        # Create proposal dict for the queue (purity-audit-v1)
        proposal = create_entity_validation_proposal(
            entity_name=entity.name,
            entity_type=entity.entity_type,
            context=entity.context
        )

        # Write to queue using existing mechanism
        self._queue_entity_proposal(proposal)

        # Return False - entity creation deferred to queue processing
        return False

    def _queue_entity_proposal(self, proposal: dict) -> bool:
        """
        Add an entity validation proposal to the pending queue.

        Similar to _queue_kaizen but for dict-based proposals.
        """
        queue_dir = get_queue_dir()
        pending_path = get_pending_queue_path()
        queue_dir.mkdir(parents=True, exist_ok=True)

        # Load existing queue
        pending = []
        if pending_path.exists():
            content = pending_path.read_text(encoding="utf-8")
            if content.strip():
                pending = yaml.safe_load(content) or []

        # Check for duplicates by ID
        existing_ids = {p.get("id") for p in pending}
        if proposal.get("id") in existing_ids:
            return False

        # Add the proposal
        pending.append(proposal)

        # Save the queue
        with open(pending_path, "w", encoding="utf-8") as f:
            yaml.dump(pending, f, default_flow_style=False, sort_keys=False)

        return True

    def _create_entity_profile(self, entity: ExtractedEntity) -> bool:
        """
        Create a Markdown profile for an extracted entity.

        Returns True if a new profile was created.
        """
        # Determine the correct subfolder from config
        from engine.config_loader import load_entity_config
        entity_config = load_entity_config()
        type_map = {t["name"]: t["plural"] for t in entity_config.get("entity_types", [])}
        default_plural = list(type_map.values())[0] if type_map else "entities"
        subfolder = type_map.get(entity.entity_type, default_plural)
        entities_dir = get_entities_dir()
        entity_dir = entities_dir / subfolder

        # Create directory if needed
        entity_dir.mkdir(parents=True, exist_ok=True)

        # Normalize filename
        filename = re.sub(r'[^\w\s-]', '', entity.name).strip().replace(' ', '-').lower()
        filepath = entity_dir / f"{filename}.md"

        # Don't overwrite existing profiles
        if filepath.exists():
            return False

        # Create the profile
        profile_content = f"""# {entity.name}

## Profile
- **Type:** {entity.entity_type.title()}
- **First Seen:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
- **Source Event:** {entity.source_event_id[:8]}...
- **Confidence:** {entity.confidence:.0%}

## Context
> {entity.context}

## Notes
_Auto-generated by Cortex. Review and enrich this profile._

## History
- {datetime.now(timezone.utc).strftime('%Y-%m-%d')}: Profile created via entity extraction
"""

        filepath.write_text(profile_content, encoding="utf-8")
        return True

    # =========================================================================
    # Kaizen Generation
    # =========================================================================

    def _generate_kaizen(self, event: dict) -> list[KaizenProposal]:
        """
        Generate Kaizen proposals from a telemetry event.

        Sprint 4: Mock implementation using keyword triggers.
        Future: LLM-powered insight generation.
        """
        transcript = event.get("raw_transcript", "").lower()
        event_id = event.get("id", "unknown")

        proposals = []

        # Generic triggers — domain-specific keywords come from config
        # Trigger: Frustration or struggle
        if "frustrated" in transcript or "struggling" in transcript:
            proposals.append(KaizenProposal(
                id=f"kaizen-{event_id[:8]}",
                proposal="Draft content seed about overcoming this frustration?",
                trigger="frustration_detected",
                source_event_id=event_id,
                created_at=datetime.now(timezone.utc).isoformat()
            ))

        # Trigger: Practice or drill mention
        if "practice" in transcript and ("need" in transcript or "help" in transcript):
            proposals.append(KaizenProposal(
                id=f"kaizen-practice-{event_id[:8]}",
                proposal="Create a new practice sequence for the mentioned skill gap?",
                trigger="practice_need_detected",
                source_event_id=event_id,
                created_at=datetime.now(timezone.utc).isoformat()
            ))

        # Trigger: Communication mention
        if "talk" in transcript or "email" in transcript or "call" in transcript:
            if "need" in transcript or "should" in transcript:
                proposals.append(KaizenProposal(
                    id=f"kaizen-comms-{event_id[:8]}",
                    proposal="Schedule communication touchpoint?",
                    trigger="communication_detected",
                    source_event_id=event_id,
                    created_at=datetime.now(timezone.utc).isoformat()
                ))

        return proposals

    def _queue_kaizen(self, proposal: KaizenProposal) -> bool:
        """
        Add a Kaizen proposal to the pending queue.

        Returns True if the proposal was added.
        """
        queue_dir = get_queue_dir()
        pending_path = get_pending_queue_path()
        queue_dir.mkdir(parents=True, exist_ok=True)

        # Load existing queue
        pending = []
        if pending_path.exists():
            content = pending_path.read_text(encoding="utf-8")
            if content.strip():
                pending = yaml.safe_load(content) or []

        # Check for duplicates by ID
        existing_ids = {p.get("id") for p in pending}
        if proposal.id in existing_ids:
            return False

        # Add the proposal
        pending.append({
            "id": proposal.id,
            "proposal": proposal.proposal,
            "trigger": proposal.trigger,
            "source_event_id": proposal.source_event_id,
            "created_at": proposal.created_at,
            "status": proposal.status
        })

        # Save the queue
        with open(pending_path, "w", encoding="utf-8") as f:
            yaml.dump(pending, f, default_flow_style=False, sort_keys=False)

        return True

    # =========================================================================
    # Lens 2: Content Seed Mining
    # =========================================================================

    def _mine_content_seeds(self, event: dict) -> list[dict]:
        """
        Mine content seeds using Tier 1 LLM (Haiku).

        Lens 2: Identifies moments worth sharing from transcripts.
        Seeds are saved for later compilation by the Content Engine.

        Args:
            event: Telemetry event with raw_transcript

        Returns:
            List of content seed dictionaries
        """
        try:
            from engine.llm_client import call_llm
        except ImportError:
            return []

        transcript = event.get("raw_transcript", "")
        event_id = event.get("id", "unknown")

        if not transcript.strip():
            return []

        # Load content config from profile
        from engine.config_loader import load_entity_config
        entity_config = load_entity_config()
        pillars = entity_config.get("content_pillars", [])
        seed_prompts = entity_config.get("content_seed_prompts", {})
        look_for = seed_prompts.get("look_for", [])

        # Build pillar list string
        pillar_str = ", ".join(pillars) if pillars else "general"
        look_for_str = "\n".join(f"- {item}" for item in look_for) if look_for else "- Notable moments or insights"

        # Build content mining prompt
        prompt = f"""Analyze this transcript for content-worthy moments.
Return JSON with a "content_seeds" array. Each seed should have:
- title: Short catchy title for the content
- content: The core message or insight
- pillar: One of: {pillar_str}
- suggested_platforms: Array of platforms (tiktok, instagram, x)

Look for:
{look_for_str}

Transcript: "{transcript}"

Return ONLY valid JSON with 0-3 content seeds, no explanations:"""

        try:
            response = call_llm(
                prompt=prompt,
                tier=1,  # Haiku for speed/cost
                intent="cortex_extraction"
            )

            # Parse JSON response
            data = json.loads(response)
            seeds = data.get("content_seeds", [])

            # Save each seed
            for seed in seeds:
                self._save_content_seed(seed, event_id)

            return seeds

        except json.JSONDecodeError:
            return []
        except Exception:
            return []

    def _save_content_seed(self, seed: dict, event_id: str) -> bool:
        """
        Save a content seed to entities/content-seeds/.

        Args:
            seed: Content seed dictionary with title, content, pillar
            event_id: Source event ID for tracing

        Returns:
            True if saved successfully
        """
        entities_dir = get_entities_dir()
        seeds_dir = entities_dir / "content-seeds"
        seeds_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename from title
        title = seed.get("title", "untitled")
        filename = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '-').lower()
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        filepath = seeds_dir / f"{timestamp}-{filename}.md"

        content = f"""# {seed.get('title', 'Untitled')}

**Pillar:** {seed.get('pillar', 'general')}
**Mined:** {datetime.now(timezone.utc).isoformat()}
**Source Event:** {event_id[:8]}...

## Content
{seed.get('content', '')}

## Suggested Platforms
{', '.join(seed.get('suggested_platforms', []))}

---
_Auto-generated by Cortex Lens 2. Review before compilation._
"""

        try:
            filepath.write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False

    # =========================================================================
    # Lens 3: Pattern Analysis (Sprint 5)
    # =========================================================================

    def run_pattern_analysis(self, telemetry_events: list[dict]) -> dict:
        """
        Lens 3: Pattern Analysis - identify workflow gaps and Kaizen opportunities.

        Uses Tier 2 (Sonnet) to cross-reference telemetry events against
        dock/goals.md and business-plan.md to detect patterns and propose
        continuous improvement suggestions.

        Sprint 7: Now acts as an ACCOUNTABILITY PARTNER with motivational framing
        tied to the operator's documented goals (tithing targets, content volume, etc.)

        Args:
            telemetry_events: Recent telemetry events to analyze

        Returns:
            Dict with patterns_detected and kaizen_proposals
        """
        from engine.llm_client import call_llm
        from engine.profile import get_dock_dir

        # Load dock context
        dock_dir = get_dock_dir()
        goals_content = self._load_dock_file(dock_dir / "goals.md")
        business_plan = self._load_dock_file(dock_dir / "business-plan.md")

        # Format telemetry for analysis
        telemetry_summary = json.dumps(telemetry_events, indent=2)

        prompt = f"""You are the Coach's ACCOUNTABILITY PARTNER. Analyze telemetry and provide
encouraging Kaizen proposals that remind the operator of their goals and celebrate progress.

TELEMETRY EVENTS:
{telemetry_summary}

BUSINESS GOALS:
{goals_content}

BUSINESS PLAN:
{business_plan}

Your task:
1. Identify recurring patterns across the telemetry
2. Detect workflow gaps - actions the operator repeats that could be automated
3. Cross-reference activity against documented goals (tithing targets, content volume, subscriber milestones)
4. OUTPUT ENCOURAGING KAIZEN PROPOSALS that celebrate momentum and remind the operator how close they are to their goals

IMPORTANT - Motivational Framing:
- When the user is generating content, PRAISE the momentum
- Reference their tithing goals explicitly (e.g., "Coach, 3 great videos this week. We are building the audience for the First Tee donation. Keep it up.")
- When progress is slow, be encouraging not critical (e.g., "One video is still progress. The mission moves forward.")
- Connect activity directly to mission outcomes (subscriber growth → tithing capacity → community impact)

Return JSON with:
- patterns_detected: Array of pattern descriptions
- kaizen_proposals: Array of objects with:
  - id: Unique ID (e.g., "kaizen-001")
  - proposal: Description of the improvement (USE ENCOURAGING LANGUAGE)
  - trigger: What triggered this proposal (e.g., "pattern_detected", "goal_alignment", "momentum_celebration")
  - priority: "high", "medium", or "low"
  - motivational_note: A brief encouraging message tied to their goals (e.g., "Every video gets us closer to that First Tee donation!")

Return ONLY valid JSON, no explanations:"""

        try:
            response = call_llm(
                prompt=prompt,
                tier=2,  # Sonnet for analytical depth
                intent="cortex_pattern_analysis"
            )

            result = json.loads(response)
            return {
                "patterns_detected": result.get("patterns_detected", []),
                "kaizen_proposals": result.get("kaizen_proposals", [])
            }

        except json.JSONDecodeError:
            return {"patterns_detected": [], "kaizen_proposals": [], "error": "parse_failed"}
        except Exception as e:
            return {"patterns_detected": [], "kaizen_proposals": [], "error": str(e)}

    # =========================================================================
    # Lens 4: Ratchet Analysis (Sprint 5)
    # =========================================================================

    def run_ratchet_analysis(
        self,
        llm_telemetry: list[dict],
        routing_patterns: list[dict]
    ) -> dict:
        """
        Lens 4: Ratchet Analysis - propose tier demotions for cost optimization.

        Uses Tier 2 (Sonnet) to analyze LLM usage patterns and identify
        intents that have stabilized enough to be demoted to lower tiers
        (Tier 2 -> Tier 1, or Tier 1 -> Tier 0 deterministic rules).

        Args:
            llm_telemetry: LLM call telemetry with model and intent data
            routing_patterns: Aggregated routing pattern data with confidence

        Returns:
            Dict with ratchet_proposals and potential_savings
        """
        from engine.llm_client import call_llm

        # Format input for analysis
        llm_summary = json.dumps(llm_telemetry, indent=2)
        patterns_summary = json.dumps(routing_patterns, indent=2)

        prompt = f"""Analyze LLM usage patterns and propose tier demotions for cost optimization.

LLM CALL TELEMETRY:
{llm_summary}

ROUTING PATTERNS:
{patterns_summary}

The Ratchet principle: Once an intent achieves high confidence (>0.95) with sufficient samples (>30),
it should be considered for demotion:
- Tier 2 (Sonnet) -> Tier 1 (Haiku): If patterns are predictable
- Tier 1 (Haiku) -> Tier 0 (Deterministic): If keyword matching would suffice

Analyze and propose demotions that maintain quality while reducing costs.

Return JSON with:
- ratchet_proposals: Array of objects with:
  - intent: The intent to demote
  - current_tier: Current tier (1, 2, or 3)
  - proposed_action: "Demote to Tier X" or "Demote to Tier 0"
  - confidence: The pattern confidence (0.0-1.0)
  - sample_count: Number of samples analyzed
  - recommendation: Brief explanation
- total_potential_savings: Estimated monthly savings (e.g., "$0.50/month")

Return ONLY valid JSON, no explanations:"""

        try:
            response = call_llm(
                prompt=prompt,
                tier=2,  # Sonnet for analytical depth
                intent="cortex_ratchet_analysis"
            )

            result = json.loads(response)
            return {
                "ratchet_proposals": result.get("ratchet_proposals", []),
                "total_potential_savings": result.get("total_potential_savings", "$0.00/month")
            }

        except json.JSONDecodeError:
            return {"ratchet_proposals": [], "total_potential_savings": "$0.00/month", "error": "parse_failed"}
        except Exception as e:
            return {"ratchet_proposals": [], "total_potential_savings": "$0.00/month", "error": str(e)}

    # =========================================================================
    # Lens 5: Evolution / Personal Product Manager (Sprint 5)
    # =========================================================================

    def run_evolution_analysis(
        self,
        telemetry_events: list[dict],
        exhaust_board: str,
        vision_board: str = ""
    ) -> dict:
        """
        Lens 5: Evolution Analysis - propose new skills for Pit Crew.

        Uses Tier 2 (Sonnet) to analyze telemetry patterns, the Exhaust Board,
        and the Vision Board to identify opportunities for new skill creation.
        Acts as the Personal Product Manager, generating Pit Crew work orders.

        Sprint 6.5: Now includes Vision Board analysis to match user aspirations
        with actual behavior patterns. Skills that fulfill stated aspirations
        are prioritized.

        Args:
            telemetry_events: Recent telemetry events
            exhaust_board: Contents of exhaust-board.md
            vision_board: Contents of vision-board.md (user aspirations)

        Returns:
            Dict with evolution_proposals (Pit Crew work orders)
        """
        from engine.llm_client import call_llm

        # Format telemetry for analysis
        telemetry_summary = json.dumps(telemetry_events, indent=2)

        # Build Vision Board section if content exists
        vision_section = ""
        if vision_board and vision_board.strip():
            vision_section = f"""
VISION BOARD (User Aspirations):
{vision_board}
"""

        prompt = f"""You are the Personal Product Manager for this Autonomaton.
Analyze telemetry, the Exhaust Board, and the Vision Board to propose new skills.

TELEMETRY EVENTS:
{telemetry_summary}

EXHAUST BOARD (Telemetry Signal Registry):
{exhaust_board}
{vision_section}
Your task:
1. Identify automation opportunities from recurring patterns
2. Cross-reference with Exhaust Board telemetry unlocks
3. **Match user aspirations from the Vision Board with actual telemetry behavior**
4. Propose new skills that would save operator time
5. **Prioritize skills that fulfill stated aspirations when telemetry supports them**

When an aspiration from the Vision Board aligns with observed telemetry patterns,
mark the proposal with "vision_match": true - these get highest priority.

Each proposal becomes a Pit Crew work order for skill generation.

Return JSON with:
- evolution_proposals: Array of objects with:
  - skill_name: Kebab-case name (e.g., "practice-scheduler")
  - description: What the skill does
  - rationale: Why this skill is needed (based on telemetry evidence)
  - spec: Object with:
    - triggers: Array of trigger phrases
    - zone: "green", "yellow", or "red"
    - tier: 1, 2, or 3
  - pit_crew_ready: true if ready for immediate generation
  - vision_match: true if this fulfills a stated aspiration

Return ONLY valid JSON, no explanations:"""

        try:
            response = call_llm(
                prompt=prompt,
                tier=2,  # Sonnet for product thinking
                intent="cortex_evolution_analysis"
            )

            result = json.loads(response)
            return {
                "evolution_proposals": result.get("evolution_proposals", [])
            }

        except json.JSONDecodeError:
            return {"evolution_proposals": [], "error": "parse_failed"}
        except Exception as e:
            return {"evolution_proposals": [], "error": str(e)}

    def _load_dock_file(self, path: Path) -> str:
        """Load a dock file, returning empty string if not found."""
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except Exception:
                return ""
        return ""

    # =========================================================================
    # Lens 6: Context Gardener (Sprint 5)
    # =========================================================================

    def run_context_gardener(
        self,
        telemetry_events: list[dict],
        standing_context: str,
        structured_plan: str,
        vision_board: str,
        exhaust_board: str
    ) -> dict:
        """
        Lens 6: Context Gardener - proposes dock updates based on patterns.

        Produces three types of Kaizen proposals:
        1. gap_alert: Missing data needed by handlers
        2. plan_update: Observations to add to structured-plan.md
        3. stale_alert: Goals not touched in threshold period

        Uses Tier 1 (Haiku) for pattern matching, Tier 2 (Sonnet) for synthesis.

        Args:
            telemetry_events: Recent telemetry events
            standing_context: Current standing context snapshot
            structured_plan: Contents of structured-plan.md
            vision_board: Contents of vision-board.md
            exhaust_board: Contents of exhaust-board.md

        Returns:
            Dict with proposals list and metadata
        """
        proposals = []

        # 1. Gap Alert Detection
        gap_alerts = self._detect_gaps(standing_context)
        proposals.extend(gap_alerts)

        # 2. Plan Update Proposals
        plan_updates = self._generate_plan_updates(
            telemetry_events, structured_plan
        )
        proposals.extend(plan_updates)

        # 3. Stale Item Detection
        stale_alerts = self._detect_stale_items(
            telemetry_events, structured_plan, vision_board
        )
        proposals.extend(stale_alerts)

        return {
            "proposals": proposals,
            "gap_count": len(gap_alerts),
            "update_count": len(plan_updates),
            "stale_count": len(stale_alerts)
        }

    def _detect_gaps(self, standing_context: str) -> list[dict]:
        """
        Detect entity data gaps that block handlers.

        Analyzes standing context for missing required fields
        as defined in entity_config.yaml.

        Returns list of gap_alert proposals.
        """
        from datetime import datetime, timezone
        from engine.config_loader import load_entity_config

        gaps = []
        entity_config = load_entity_config()
        required_fields = entity_config.get("required_entity_fields", {})
        type_map = {t["name"]: t["plural"] for t in entity_config.get("entity_types", [])}

        # Check each entity type for missing required fields
        for entity_type, fields in required_fields.items():
            plural = type_map.get(entity_type, f"{entity_type}s")
            section_marker = f"[entities/{plural}]"

            if section_marker in standing_context:
                entity_section = standing_context.split(section_marker)[1].split("[")[0]

                for field in fields:
                    # Check if field is mentioned in context
                    if field.lower() not in standing_context.lower():
                        gaps.append({
                            "id": f"gap-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{entity_type}-{field}",
                            "proposal": f"{entity_type.title()} entities may be missing {field} data.",
                            "trigger": "context_gardener",
                            "proposal_type": "gap_alert",
                            "target_entity": f"entities/{plural}/",
                            "missing_field": field,
                            "priority": "low",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "status": "pending"
                        })

        return gaps

    def _generate_plan_updates(
        self,
        telemetry_events: list[dict],
        structured_plan: str
    ) -> list[dict]:
        """
        Generate plan update proposals based on telemetry patterns.

        Analyzes recent activity against plan goals to identify
        progress, trends, or recommended actions.

        Returns list of plan_update proposals.
        """
        from datetime import datetime, timezone

        updates = []

        if not telemetry_events or not structured_plan:
            return updates

        # Count intent patterns in telemetry
        intent_counts = {}
        for event in telemetry_events:
            intent = event.get("intent", "unknown")
            intent_counts[intent] = intent_counts.get(intent, 0) + 1

        # Check for content compilation patterns vs goals
        compile_count = intent_counts.get("content_compilation", 0) + intent_counts.get("compile_content", 0)
        if compile_count > 0 and "Goal 2: TikTok" in structured_plan:
            updates.append({
                "id": f"obs-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-content",
                "proposal": f"Content compilation activity detected ({compile_count} events). Goal 2 (TikTok) may need trajectory update.",
                "trigger": "context_gardener",
                "proposal_type": "plan_update",
                "target_file": "dock/system/structured-plan.md",
                "target_section": "Goal 2: TikTok",
                "observation": f"{compile_count} content compilation events in recent telemetry",
                "priority": "medium",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending"
            })

        # Check for strategy session patterns
        strategy_count = intent_counts.get("strategy_session", 0)
        if strategy_count >= 3:
            updates.append({
                "id": f"obs-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-strategy",
                "proposal": f"High strategy session usage ({strategy_count} events). Operator is actively planning. Consider refreshing the structured plan.",
                "trigger": "context_gardener",
                "proposal_type": "plan_update",
                "target_file": "dock/system/structured-plan.md",
                "target_section": "Next Actions",
                "observation": f"{strategy_count} strategy sessions indicate active planning mode",
                "priority": "low",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending"
            })

        return updates

    def _detect_stale_items(
        self,
        telemetry_events: list[dict],
        structured_plan: str,
        vision_board: str,
        stale_days: int = 14
    ) -> list[dict]:
        """
        Detect goals and vision items not touched recently.

        Analyzes telemetry timestamps to find items that haven't
        been interacted with in the configured threshold period.

        Returns list of stale_alert proposals.
        """
        from datetime import datetime, timezone, timedelta

        stale = []
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(days=stale_days)

        # Extract goal-related intents from telemetry
        goal_related = {"tithing", "revenue", "money", "payment", "fee"}
        latest_goal_touch = {}

        for event in telemetry_events:
            intent = event.get("intent", "").lower()
            transcript = event.get("raw_transcript", "").lower()
            timestamp_str = event.get("timestamp", "")

            for goal_key in goal_related:
                if goal_key in intent or goal_key in transcript:
                    try:
                        event_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        if goal_key not in latest_goal_touch or event_time > latest_goal_touch[goal_key]:
                            latest_goal_touch[goal_key] = event_time
                    except (ValueError, TypeError):
                        continue

        # Check for stale revenue/tithing goals
        if "Goal 3" in structured_plan and "Tithing" in structured_plan:
            tithing_touched = latest_goal_touch.get("tithing") or latest_goal_touch.get("revenue")
            if not tithing_touched or tithing_touched < threshold:
                stale.append({
                    "id": f"stale-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-tithing",
                    "proposal": f"Revenue/tithing goals not referenced in {stale_days}+ days. Consider reviewing Goal 3 priority.",
                    "trigger": "context_gardener",
                    "proposal_type": "stale_alert",
                    "target_section": "Goal 3: Tithing",
                    "last_touched": tithing_touched.isoformat() if tithing_touched else "Never",
                    "threshold_days": stale_days,
                    "priority": "low",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "status": "pending"
                })

        # Vision board stale item detection
        # Note: Specific vision item checking should be config-driven
        # This is a generic fallback for detecting untouched vision items
        if vision_board and len(vision_board) > 100:
            # Vision board exists and has content - check for stale items
            # Future: Load specific items to check from profile config
            pass

        return stale


# =========================================================================
# Queue Management
# =========================================================================

def load_pending_queue() -> list[dict]:
    """Load pending Kaizen items from the queue."""
    pending_path = get_pending_queue_path()

    if not pending_path.exists():
        return []

    content = pending_path.read_text(encoding="utf-8")
    if not content.strip():
        return []

    return yaml.safe_load(content) or []


def clear_pending_queue() -> None:
    """Clear all items from the pending queue."""
    pending_path = get_pending_queue_path()
    if pending_path.exists():
        pending_path.write_text("", encoding="utf-8")


def remove_from_queue(item_id: str) -> bool:
    """Remove a specific item from the pending queue."""
    pending_path = get_pending_queue_path()
    pending = load_pending_queue()
    updated = [p for p in pending if p.get("id") != item_id]

    if len(updated) == len(pending):
        return False  # Item not found

    with open(pending_path, "w", encoding="utf-8") as f:
        if updated:
            yaml.dump(updated, f, default_flow_style=False, sort_keys=False)
        else:
            f.write("")

    return True


# Module-level singleton
_cortex_instance: Optional[Cortex] = None

# Context Gardener gating state (session-scoped)
_gardener_events_since_last_run: int = 0
_gardener_runs_this_session: int = 0


def get_cortex() -> Cortex:
    """Get the shared Cortex instance."""
    global _cortex_instance
    if _cortex_instance is None:
        _cortex_instance = Cortex()
    return _cortex_instance


def _load_gardener_config() -> dict:
    """Load Context Gardener configuration from cortex.yaml."""
    from engine.profile import get_config_dir

    config_path = get_config_dir() / "cortex.yaml"

    defaults = {
        "enabled": True,
        "min_events_since_last_run": 10,
        "max_runs_per_session": 1,
        "stale_threshold_days": 14,
        "tier_for_pattern_matching": 1,
        "tier_for_synthesis": 2
    }

    if not config_path.exists():
        return defaults

    try:
        content = config_path.read_text(encoding="utf-8")
        config = yaml.safe_load(content) or {}
        gardener_config = config.get("context_gardener", {})
        # Merge with defaults
        for key, value in defaults.items():
            if key not in gardener_config:
                gardener_config[key] = value
        return gardener_config
    except Exception:
        return defaults


def _should_run_gardener() -> bool:
    """
    Check if Context Gardener should run this tail pass.

    Gating rules:
    1. Must be enabled in config
    2. Must have min_events_since_last_run events
    3. Must not exceed max_runs_per_session
    """
    global _gardener_events_since_last_run, _gardener_runs_this_session

    config = _load_gardener_config()

    if not config.get("enabled", True):
        return False

    min_events = config.get("min_events_since_last_run", 10)
    max_runs = config.get("max_runs_per_session", 1)

    if _gardener_events_since_last_run < min_events:
        return False

    if _gardener_runs_this_session >= max_runs:
        return False

    return True


def _reset_gardener_gating() -> None:
    """Reset gardener gating state (call at session start)."""
    global _gardener_events_since_last_run, _gardener_runs_this_session
    _gardener_events_since_last_run = 0
    _gardener_runs_this_session = 0


def run_tail_pass() -> dict:
    """
    Run a tail-pass analysis on recent telemetry.

    This is the primary interface for the pipeline integration.
    Sprint 5: Now includes gated Context Gardener invocation.
    """
    global _gardener_events_since_last_run, _gardener_runs_this_session

    cortex = get_cortex()
    result = cortex.run_analysis_pass()

    # Increment event counter for gardener gating
    events_processed = result.get("events_processed", 0)
    if events_processed > 0:
        _gardener_events_since_last_run += events_processed

    # Check if Context Gardener should run
    if _should_run_gardener():
        gardener_result = _run_context_gardener_pass(cortex)
        result["gardener"] = gardener_result

        # Reset event counter, increment run counter
        _gardener_events_since_last_run = 0
        _gardener_runs_this_session += 1

    return result


def _run_context_gardener_pass(cortex: Cortex) -> dict:
    """
    Execute Context Gardener and queue proposals.

    Loads all required context and runs the Gardener, then
    queues any proposals through the existing Kaizen mechanism.
    """
    from engine.profile import get_dock_dir, get_telemetry_path
    from engine.compiler import gather_state_snapshot

    # Gather inputs
    standing_context = gather_state_snapshot()

    dock_dir = get_dock_dir()
    plan_path = dock_dir / "system" / "structured-plan.md"
    vision_path = dock_dir / "system" / "vision-board.md"
    exhaust_path = dock_dir / "system" / "exhaust-board.md"

    structured_plan = ""
    if plan_path.exists():
        try:
            structured_plan = plan_path.read_text(encoding="utf-8")
        except Exception:
            pass

    vision_board = ""
    if vision_path.exists():
        try:
            vision_board = vision_path.read_text(encoding="utf-8")
        except Exception:
            pass

    exhaust_board = ""
    if exhaust_path.exists():
        try:
            exhaust_board = exhaust_path.read_text(encoding="utf-8")
        except Exception:
            pass

    # Load recent telemetry
    telemetry_path = get_telemetry_path()
    telemetry_events = []
    if telemetry_path.exists():
        try:
            with open(telemetry_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            telemetry_events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            telemetry_events = telemetry_events[-50:]  # Last 50 events
        except Exception:
            pass

    # Run Context Gardener
    gardener_result = cortex.run_context_gardener(
        telemetry_events=telemetry_events,
        standing_context=standing_context,
        structured_plan=structured_plan,
        vision_board=vision_board,
        exhaust_board=exhaust_board
    )

    # Queue proposals through existing Kaizen mechanism
    proposals_queued = 0
    for proposal in gardener_result.get("proposals", []):
        # Convert to KaizenProposal format and queue
        kaizen = KaizenProposal(
            id=proposal.get("id", f"gardener-{proposals_queued}"),
            proposal=proposal.get("proposal", ""),
            trigger=proposal.get("trigger", "context_gardener"),
            source_event_id="context_gardener_pass",
            created_at=proposal.get("created_at", ""),
            status="pending",
            proposal_type=proposal.get("proposal_type", "general"),
            target_file=proposal.get("target_file", ""),
            target_section=proposal.get("target_section", ""),
            priority=proposal.get("priority", "medium")
        )
        if cortex._queue_kaizen(kaizen):
            proposals_queued += 1

    gardener_result["proposals_queued"] = proposals_queued
    return gardener_result
