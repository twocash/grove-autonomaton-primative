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
from typing import Optional

from engine.profile import (
    get_telemetry_path,
    get_entities_dir,
    get_queue_dir,
    get_pending_queue_path
)


def ask_entity_validation(
    entity_name: str,
    entity_type: str,
    context: str
) -> str:
    """
    Ask operator to validate a new entity (Jidoka).

    This is a Digital Jidoka halt - the system stops and asks
    the human operator to confirm before creating a new entity.

    Args:
        entity_name: The extracted entity name
        entity_type: The inferred entity type
        context: Surrounding context from transcript

    Returns:
        User choice: "1" (approve), "2" (reject), "3" (edit)
    """
    print(f"\n  [JIDOKA] New entity detected: {entity_name}")
    print(f"  Type: {entity_type}")
    print(f"  Context: ...{context}...")
    print()
    print("  Options:")
    print("    1. Approve - Create entity profile")
    print("    2. Reject - This is not a real entity")
    print("    3. Skip - Decide later")
    print()

    try:
        choice = input("  Choice [1/2/3]: ").strip()
        return choice if choice in ("1", "2", "3") else "3"
    except (KeyboardInterrupt, EOFError):
        return "3"


@dataclass
class ExtractedEntity:
    """An entity extracted from a transcript."""
    name: str
    entity_type: str  # player, parent, client, venue
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


class Cortex:
    """
    The Analytical Engine that processes telemetry in the background.

    The Cortex runs after each interaction to:
    1. Extract entities (players, parents, venues)
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
    # Entity Extraction
    # =========================================================================

    def _extract_entities(self, event: dict) -> list[ExtractedEntity]:
        """
        Extract entities from a telemetry event.

        Sprint 4: Mock implementation using regex for capitalized names.
        Future: LLM-powered NER.
        """
        transcript = event.get("raw_transcript", "")
        event_id = event.get("id", "unknown")

        entities = []

        # Pattern: Capitalized words that look like names
        # Matches: "Henderson", "Marcus", "St. Mary's"
        # Excludes: Common words, single letters, all-caps
        name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'

        # Common words to exclude (sentence starters, days, months, domain terms)
        exclude_words = {
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
            # Domain-specific terms
            "Coach", "Player", "Parent", "Client", "Venue", "Session",
            "Green", "Yellow", "Red", "Zone", "Dock", "Action", "Status",
            "Practice", "Lesson", "Tournament", "Team", "Golf", "Swing",
            "Revenue", "Goal", "Target", "Content", "Email", "Call",
            # Common verbs that might be capitalized
            "Schedule", "Send", "Create", "Update", "Delete", "Draft"
        }

        matches = re.findall(name_pattern, transcript)

        for match in matches:
            if match not in exclude_words and len(match) > 2:
                # Extract surrounding context
                context_match = re.search(
                    rf'.{{0,30}}{re.escape(match)}.{{0,30}}',
                    transcript
                )
                context = context_match.group(0) if context_match else ""

                entities.append(ExtractedEntity(
                    name=match,
                    entity_type="player",  # Default to player for this sprint
                    source_event_id=event_id,
                    confidence=0.6,
                    context=context
                ))

        return entities

    def _extract_entities_llm(self, event: dict) -> list[ExtractedEntity]:
        """
        Extract entities using Tier 1 LLM (Haiku).

        Lens 1: Named Entity Recognition that understands context
        and distinguishes real names from action words.

        Args:
            event: Telemetry event with raw_transcript

        Returns:
            List of extracted entities with is_new flag
        """
        try:
            from engine.llm_client import call_llm
        except ImportError:
            return []

        transcript = event.get("raw_transcript", "")
        event_id = event.get("id", "unknown")

        if not transcript.strip():
            return []

        # Build extraction prompt
        prompt = f"""Extract named entities from this transcript.
Return JSON with an "entities" array. Each entity should have:
- name: The full name (e.g., "Marcus Henderson")
- type: One of: player, parent, client, venue
- is_new: true if this appears to be a new person/place, false if existing

IMPORTANT:
- Only extract real person or place names
- Do NOT extract action words like "Generate", "Create", "Update", etc.
- Do NOT extract common nouns or verbs
- Focus on proper nouns that are actual names

Transcript: "{transcript}"

Return ONLY valid JSON, no explanations:"""

        try:
            response = call_llm(
                prompt=prompt,
                tier=1,  # Haiku for speed/cost
                intent="cortex_extraction"
            )

            # Parse JSON response
            data = json.loads(response)
            entities_data = data.get("entities", [])

            entities = []
            for e in entities_data:
                name = e.get("name", "").strip()
                if not name:
                    continue

                entities.append(ExtractedEntity(
                    name=name,
                    entity_type=e.get("type", "player"),
                    source_event_id=event_id,
                    confidence=0.8,  # LLM extraction confidence
                    context=transcript[:100],
                    is_new=e.get("is_new", True)
                ))

            return entities

        except json.JSONDecodeError:
            # Malformed response - return empty list
            return []
        except Exception:
            # LLM failure - return empty list
            return []

    def _validate_new_entity(self, entity: ExtractedEntity) -> bool:
        """
        Validate a new entity with Jidoka approval.

        Only called for entities with is_new=True.

        Args:
            entity: The entity to validate

        Returns:
            True if approved, False if rejected/skipped
        """
        result = ask_entity_validation(
            entity_name=entity.name,
            entity_type=entity.entity_type,
            context=entity.context
        )

        if result == "1":
            # Approved - create the profile
            return self._create_entity_profile(entity)
        elif result == "2":
            # Rejected - do nothing
            return False
        else:
            # Skipped - defer for later
            return False

    def _create_entity_profile(self, entity: ExtractedEntity) -> bool:
        """
        Create a Markdown profile for an extracted entity.

        Returns True if a new profile was created.
        """
        # Determine the correct subfolder
        type_map = {
            "player": "players",
            "parent": "parents",
            "client": "clients",
            "venue": "venues"
        }
        subfolder = type_map.get(entity.entity_type, "players")
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

        # Trigger: Frustration or struggle
        if "frustrated" in transcript or "struggling" in transcript:
            proposals.append(KaizenProposal(
                id=f"kaizen-{event_id[:8]}",
                proposal="Draft content seed about overcoming frustration on the course?",
                trigger="frustration_detected",
                source_event_id=event_id,
                created_at=datetime.now(timezone.utc).isoformat()
            ))

        # Trigger: Practice or drill mention
        if "practice" in transcript and ("need" in transcript or "help" in transcript):
            proposals.append(KaizenProposal(
                id=f"kaizen-practice-{event_id[:8]}",
                proposal="Create a new drill sequence for the mentioned skill gap?",
                trigger="practice_need_detected",
                source_event_id=event_id,
                created_at=datetime.now(timezone.utc).isoformat()
            ))

        # Trigger: Parent mention
        if "parent" in transcript and ("talk" in transcript or "email" in transcript or "call" in transcript):
            proposals.append(KaizenProposal(
                id=f"kaizen-parent-{event_id[:8]}",
                proposal="Schedule parent communication touchpoint?",
                trigger="parent_outreach_detected",
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

        # Build content mining prompt
        prompt = f"""Analyze this transcript for content-worthy moments.
Return JSON with a "content_seeds" array. Each seed should have:
- title: Short catchy title for the content
- content: The core message or insight
- pillar: One of: training, coaching, community, surrender
- suggested_platforms: Array of platforms (tiktok, instagram, x)

Look for:
- Moments of progress or breakthrough
- Coaching insights or wisdom
- Community building opportunities
- Stories of perseverance

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

        prompt = f"""Analyze these telemetry events for workflow patterns and improvement opportunities.

TELEMETRY EVENTS:
{telemetry_summary}

BUSINESS GOALS:
{goals_content}

BUSINESS PLAN:
{business_plan}

Your task:
1. Identify recurring patterns across the telemetry (e.g., Henderson workflow spans scheduling and communication)
2. Detect workflow gaps - actions the operator repeats that could be automated
3. Propose Kaizen improvements that align with business goals

Return JSON with:
- patterns_detected: Array of pattern descriptions
- kaizen_proposals: Array of objects with:
  - id: Unique ID (e.g., "kaizen-001")
  - proposal: Description of the improvement
  - trigger: What triggered this proposal (e.g., "pattern_detected", "goal_alignment")
  - priority: "high", "medium", or "low"

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
        exhaust_board: str
    ) -> dict:
        """
        Lens 5: Evolution Analysis - propose new skills for Pit Crew.

        Uses Tier 2 (Sonnet) to analyze telemetry patterns and the Exhaust Board
        to identify opportunities for new skill creation. Acts as the Personal
        Product Manager, generating Pit Crew work orders.

        Args:
            telemetry_events: Recent telemetry events
            exhaust_board: Contents of exhaust-board.md

        Returns:
            Dict with evolution_proposals (Pit Crew work orders)
        """
        from engine.llm_client import call_llm

        # Format telemetry for analysis
        telemetry_summary = json.dumps(telemetry_events, indent=2)

        prompt = f"""You are the Personal Product Manager for this Autonomaton.
Analyze telemetry and the Exhaust Board to propose new skills.

TELEMETRY EVENTS:
{telemetry_summary}

EXHAUST BOARD (Telemetry Signal Registry):
{exhaust_board}

Your task:
1. Identify automation opportunities from recurring patterns
2. Cross-reference with Exhaust Board telemetry unlocks
3. Propose new skills that would save operator time

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


def get_cortex() -> Cortex:
    """Get the shared Cortex instance."""
    global _cortex_instance
    if _cortex_instance is None:
        _cortex_instance = Cortex()
    return _cortex_instance


def run_tail_pass() -> dict:
    """
    Run a tail-pass analysis on recent telemetry.

    This is the primary interface for the pipeline integration.
    """
    cortex = get_cortex()
    return cortex.run_analysis_pass()
